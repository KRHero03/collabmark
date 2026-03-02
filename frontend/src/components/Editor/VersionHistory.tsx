/**
 * Slide-out panel showing the version history timeline for a document.
 * Each entry shows author, timestamp, and summary. Clicking an entry
 * loads the read-only snapshot content via VersionPreview.
 */

import { useCallback, useEffect, useState } from "react";
import { Clock, X } from "lucide-react";
import { versionsApi, type VersionListItem, type VersionDetail } from "../../lib/api";
import { MarkdownPreview } from "./MarkdownPreview";

interface VersionHistoryProps {
  /** The document ID. */
  docId: string;
  /** Whether the panel is open. */
  open: boolean;
  /** Callback to close the panel. */
  onClose: () => void;
}

export function VersionHistory({ docId, open, onClose }: VersionHistoryProps) {
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
    <div className="fixed inset-y-0 right-0 z-40 flex w-[480px] flex-col border-l border-[var(--color-border)] bg-white shadow-xl">
      <div className="flex items-center justify-between border-b border-[var(--color-border)] px-4 py-3">
        <h2 className="flex items-center gap-2 text-lg font-semibold">
          <Clock className="h-5 w-5" />
          Version History
        </h2>
        <button onClick={onClose} className="rounded p-1 hover:bg-gray-100">
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
                {new Date(selected.created_at).toLocaleString()}
              </p>
            </div>
            <button
              onClick={() => setSelected(null)}
              className="rounded-md px-3 py-1 text-xs text-[var(--color-primary)] hover:bg-gray-50"
            >
              Back to list
            </button>
          </div>
          <div className="flex-1 overflow-auto">
            {loadingDetail ? (
              <div className="flex justify-center py-10">
                <div className="h-6 w-6 animate-spin rounded-full border-2 border-[var(--color-primary)] border-t-transparent" />
              </div>
            ) : (
              <MarkdownPreview content={selected.content} />
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
              No versions saved yet. Versions are created automatically when
              you save.
            </div>
          ) : (
            <ul className="divide-y divide-[var(--color-border)]">
              {versions.map((ver) => (
                <li
                  key={ver.id}
                  onClick={() => handleSelect(ver)}
                  className="cursor-pointer px-4 py-3 transition hover:bg-gray-50"
                >
                  <div className="flex items-center justify-between">
                    <p className="text-sm font-medium">
                      Version {ver.version_number}
                    </p>
                    <p className="text-xs text-[var(--color-text-muted)]">
                      {new Date(ver.created_at).toLocaleString()}
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
