/**
 * Consolidated ACL view panel showing all users with effective permissions
 * on a document or folder, including role and inheritance information.
 */

import { useEffect, useState } from "react";
import { X, Shield, Check, Minus } from "lucide-react";
import { aclApi, type AclEntry } from "../../lib/api";

interface AclPanelProps {
  entityType: "document" | "folder";
  entityId: string;
  entityName: string;
  open: boolean;
  onClose: () => void;
}

const ROLE_LABELS: Record<string, string> = {
  root_owner: "Root Owner",
  owner: "Owner",
  editor: "Editor",
  viewer: "Viewer",
  none: "No Access",
};

const ROLE_COLORS: Record<string, string> = {
  root_owner: "text-purple-600 dark:text-purple-400",
  owner: "text-blue-600 dark:text-blue-400",
  editor: "text-green-600 dark:text-green-400",
  viewer: "text-gray-600 dark:text-gray-400",
  none: "text-red-600 dark:text-red-400",
};

function PermIcon({ granted }: { granted: boolean }) {
  return granted ? (
    <Check className="h-4 w-4 text-green-500" />
  ) : (
    <Minus className="h-4 w-4 text-[var(--color-text-muted)]" />
  );
}

function AvatarBubble({ name, url }: { name: string; url: string | null }) {
  if (url) {
    return (
      <img
        src={url}
        alt={name}
        className="h-8 w-8 rounded-full object-cover"
      />
    );
  }
  const initials = name
    .split(" ")
    .map((w) => w[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
  return (
    <div className="flex h-8 w-8 items-center justify-center rounded-full bg-[var(--color-primary)] text-xs font-medium text-white">
      {initials}
    </div>
  );
}

export function AclPanel({
  entityType,
  entityId,
  entityName,
  open,
  onClose,
}: AclPanelProps) {
  const [entries, setEntries] = useState<AclEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setLoading(true);
    setError(null);

    const fetch = entityType === "document"
      ? aclApi.getDocumentAcl(entityId)
      : aclApi.getFolderAcl(entityId);

    fetch
      .then((res) => setEntries(res.data))
      .catch(() => setError("Failed to load permissions"))
      .finally(() => setLoading(false));
  }, [open, entityType, entityId]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      onClick={onClose}
    >
      <div
        className="w-[calc(100%-2rem)] max-w-2xl rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-[var(--color-border)] px-5 py-4">
          <div className="flex items-center gap-2">
            <Shield className="h-5 w-5 text-[var(--color-primary)]" />
            <div>
              <h2 className="text-lg font-semibold text-[var(--color-text)]">
                Permissions
              </h2>
              <p className="text-xs text-[var(--color-text-muted)]">
                {entityName}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="rounded p-1 text-[var(--color-text-muted)] transition-colors hover:bg-[var(--color-hover)]"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Body */}
        <div className="max-h-[60vh] overflow-y-auto px-5 py-4">
          {loading && (
            <p className="py-8 text-center text-sm text-[var(--color-text-muted)]">
              Loading permissions...
            </p>
          )}
          {error && (
            <p className="py-8 text-center text-sm text-red-500">{error}</p>
          )}
          {!loading && !error && entries.length === 0 && (
            <p className="py-8 text-center text-sm text-[var(--color-text-muted)]">
              No permission entries found.
            </p>
          )}
          {!loading && !error && entries.length > 0 && (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--color-border)] text-left text-[var(--color-text-muted)]">
                  <th className="pb-2 pr-3 font-medium">User</th>
                  <th className="pb-2 px-2 font-medium text-center">View</th>
                  <th className="pb-2 px-2 font-medium text-center">Edit</th>
                  <th className="pb-2 px-2 font-medium text-center">Delete</th>
                  <th className="pb-2 px-2 font-medium text-center">Share</th>
                  <th className="pb-2 pl-2 font-medium">Role</th>
                </tr>
              </thead>
              <tbody>
                {entries.map((entry) => (
                  <tr
                    key={entry.user_id}
                    className="border-b border-[var(--color-border)] last:border-0"
                  >
                    <td className="py-3 pr-3">
                      <div className="flex items-center gap-2">
                        <AvatarBubble
                          name={entry.user_name}
                          url={entry.avatar_url}
                        />
                        <div className="min-w-0">
                          <p className="truncate font-medium text-[var(--color-text)]">
                            {entry.user_name}
                          </p>
                          <p className="truncate text-xs text-[var(--color-text-muted)]">
                            {entry.user_email}
                          </p>
                          {entry.inherited_from_name && (
                            <p className="truncate text-xs italic text-[var(--color-text-muted)]">
                              via {entry.inherited_from_name}
                            </p>
                          )}
                        </div>
                      </div>
                    </td>
                    <td className="px-2 text-center">
                      <PermIcon granted={entry.can_view} />
                    </td>
                    <td className="px-2 text-center">
                      <PermIcon granted={entry.can_edit} />
                    </td>
                    <td className="px-2 text-center">
                      <PermIcon granted={entry.can_delete} />
                    </td>
                    <td className="px-2 text-center">
                      <PermIcon granted={entry.can_share} />
                    </td>
                    <td className="pl-2">
                      <span
                        className={`text-xs font-medium ${ROLE_COLORS[entry.role] || ""}`}
                      >
                        {ROLE_LABELS[entry.role] || entry.role}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Footer */}
        <div className="flex justify-end border-t border-[var(--color-border)] px-5 py-3">
          <button
            onClick={onClose}
            className="rounded-lg bg-[var(--color-primary)] px-4 py-2 text-sm font-medium text-white transition-colors hover:opacity-90"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
