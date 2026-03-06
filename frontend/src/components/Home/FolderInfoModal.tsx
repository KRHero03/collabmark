import { X } from "lucide-react";
import type { FolderItem } from "../../lib/api";
import { formatDateTime } from "../../lib/dateUtils";

interface FolderInfoModalProps {
  folder: FolderItem;
  open: boolean;
  onClose: () => void;
}

export function FolderInfoModal({ folder, open, onClose }: FolderInfoModalProps) {
  if (!open || !folder) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="relative w-[calc(100%-2rem)] max-w-md rounded-xl bg-white p-6 shadow-lg">
        <button
          onClick={onClose}
          className="absolute right-4 top-4 rounded p-1 text-[var(--color-text-muted)] transition hover:bg-gray-100"
        >
          <X className="h-5 w-5" />
        </button>
        <h3 className="mb-4 text-lg font-semibold">Folder Info</h3>
        <dl className="space-y-3 text-sm">
          <div>
            <dt className="font-medium text-[var(--color-text-muted)]">Name</dt>
            <dd>{folder.name}</dd>
          </div>
          {folder.owner_name && (
            <div>
              <dt className="font-medium text-[var(--color-text-muted)]">Owner</dt>
              <dd>
                {folder.owner_name}
                {folder.owner_email && (
                  <span className="ml-1 text-[var(--color-text-muted)]">({folder.owner_email})</span>
                )}
              </dd>
            </div>
          )}
          <div>
            <dt className="font-medium text-[var(--color-text-muted)]">Created</dt>
            <dd>{formatDateTime(folder.created_at)}</dd>
          </div>
          <div>
            <dt className="font-medium text-[var(--color-text-muted)]">Updated</dt>
            <dd>{formatDateTime(folder.updated_at)}</dd>
          </div>
          <div>
            <dt className="font-medium text-[var(--color-text-muted)]">Access</dt>
            <dd className="capitalize">{folder.general_access.replace("_", " ")}</dd>
          </div>
          {folder.is_deleted && folder.deleted_at && (
            <div>
              <dt className="font-medium text-red-600">Deleted</dt>
              <dd className="text-red-600">{formatDateTime(folder.deleted_at)}</dd>
            </div>
          )}
        </dl>
      </div>
    </div>
  );
}
