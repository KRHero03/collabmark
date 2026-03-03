/**
 * Slide-out panel showing the version history timeline for a document.
 * Each entry shows author, timestamp, and summary. Clicking an entry
 * shows a diff between that version's content and the current document,
 * with an option to restore the selected version.
 */

import { useCallback, useEffect, useState } from "react";
import { Clock, RotateCcw, X } from "lucide-react";
import { versionsApi, type VersionListItem, type VersionDetail } from "../../lib/api";
import { formatDateTime } from "../../lib/dateUtils";
import { DiffView } from "./DiffView";

interface VersionHistoryProps {
  docId: string;
  open: boolean;
  onClose: () => void;
  currentContent: string;
  onRestore: (content: string, versionNumber: number) => void;
}

export function VersionHistory({
  docId,
  open,
  onClose,
  currentContent,
  onRestore,
}: VersionHistoryProps) {
  const [versions, setVersions] = useState<VersionListItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState<VersionDetail | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);

  const fetchVersions = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await versionsApi.list(docId);
      setVersions(data);
    } finally {
      setLoading(false);
    }
  }, [docId]);

  useEffect(() => {
    if (open) {
      fetchVersions();
      setSelected(null);
    }
  }, [open, fetchVersions]);

  const handleSelect = async (ver: VersionListItem) => {
    setLoadingDetail(true);
    try {
      const { data } = await versionsApi.get(docId, ver.version_number);
      setSelected(data);
    } finally {
      setLoadingDetail(false);
    }
  };

  if (!open) return null;

  return (
    <div className="fixed inset-y-0 right-0 z-40 flex w-full flex-col border-l border-[var(--color-border)] bg-white shadow-xl dark:bg-gray-900 md:w-[480px]">
      <div className="flex items-center justify-between border-b border-[var(--color-border)] px-4 py-3">
        <h2 className="flex items-center gap-2 text-lg font-semibold">
          <Clock className="h-5 w-5" />
          Version History
        </h2>
        <button onClick={onClose} className="rounded p-1 hover:bg-gray-100 dark:hover:bg-gray-800">
          <X className="h-5 w-5" />
        </button>
      </div>

      {selected ? (
        <div className="flex flex-1 flex-col overflow-hidden">
          <div className="flex items-center justify-between border-b border-[var(--color-border)] px-4 py-2">
            <div>
              <p className="text-sm font-medium">
                Version {selected.version_number}
              </p>
              <p className="text-xs text-[var(--color-text-muted)]">
                {selected.author_name} &middot;{" "}
                {formatDateTime(selected.created_at)}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => onRestore(selected.content, selected.version_number)}
                className="inline-flex items-center gap-1 rounded-md bg-[var(--color-primary)] px-3 py-1.5 text-xs font-medium text-white transition hover:opacity-90"
                data-testid="restore-version-btn"
              >
                <RotateCcw className="h-3.5 w-3.5" />
                Restore
              </button>
              <button
                onClick={() => setSelected(null)}
                className="rounded-md px-3 py-1 text-xs text-[var(--color-primary)] hover:bg-gray-50 dark:hover:bg-gray-800"
              >
                Back to list
              </button>
            </div>
          </div>
          <div className="flex-1 overflow-auto">
            {loadingDetail ? (
              <div className="flex justify-center py-10">
                <div className="h-6 w-6 animate-spin rounded-full border-2 border-[var(--color-primary)] border-t-transparent" />
              </div>
            ) : (
              <DiffView
                oldText={selected.content}
                newText={currentContent}
                oldLabel={`Version ${selected.version_number}`}
                newLabel="Current document"
              />
            )}
          </div>
        </div>
      ) : (
        <div className="flex-1 overflow-auto">
          {loading ? (
            <div className="flex justify-center py-10">
              <div className="h-6 w-6 animate-spin rounded-full border-2 border-[var(--color-primary)] border-t-transparent" />
            </div>
          ) : versions.length === 0 ? (
            <div className="px-4 py-10 text-center text-sm text-[var(--color-text-muted)]">
              No versions yet. Versions are created automatically as you edit.
            </div>
          ) : (
            <ul className="divide-y divide-[var(--color-border)]">
              {versions.map((ver) => (
                <li
                  key={ver.id}
                  onClick={() => handleSelect(ver)}
                  className="cursor-pointer px-4 py-3 transition hover:bg-gray-50 dark:hover:bg-gray-800"
                >
                  <div className="flex items-center justify-between">
                    <p className="text-sm font-medium">
                      Version {ver.version_number}
                    </p>
                    <p className="text-xs text-[var(--color-text-muted)]">
                      {formatDateTime(ver.created_at)}
                    </p>
                  </div>
                  <p className="mt-0.5 text-xs text-[var(--color-text-muted)]">
                    {ver.author_name} &middot; {ver.summary}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
