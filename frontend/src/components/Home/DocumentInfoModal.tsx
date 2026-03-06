/**
 * Modal showing document metadata: title, owner, dates, size, access level.
 */

import { X, FileText } from "lucide-react";
import type { MarkdownDocument } from "../../lib/api";
import { formatDateTime } from "../../lib/dateUtils";

interface DocumentInfoModalProps {
  doc: MarkdownDocument;
  open: boolean;
  onClose: () => void;
}

function formatAccessLevel(ga: string): string {
  switch (ga) {
    case "anyone_edit":
      return "Anyone with the link can edit";
    case "anyone_view":
      return "Anyone with the link can view";
    default:
      return "Restricted";
  }
}

function formatSize(chars: number): string {
  if (chars < 1000) return `${chars} characters`;
  if (chars < 1_000_000) return `${(chars / 1000).toFixed(1)}K characters`;
  return `${(chars / 1_000_000).toFixed(1)}M characters`;
}

export function DocumentInfoModal({ doc, open, onClose }: DocumentInfoModalProps) {
  if (!open) return null;

  const rows: { label: string; value: string }[] = [
    { label: "Title", value: doc.title || "Untitled" },
    { label: "Owner", value: doc.owner_name || "Unknown" },
    { label: "Owner email", value: doc.owner_email || "-" },
    { label: "Created", value: formatDateTime(doc.created_at) },
    { label: "Last updated", value: formatDateTime(doc.updated_at) },
    { label: "Size", value: formatSize(doc.content_length ?? 0) },
    { label: "Access", value: formatAccessLevel(doc.general_access) },
  ];

  if (doc.is_deleted && doc.deleted_at) {
    rows.push({ label: "Deleted", value: formatDateTime(doc.deleted_at) });
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={onClose}>
      <div
        className="w-[calc(100%-2rem)] max-w-md rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-[var(--color-border)] px-5 py-4">
          <div className="flex items-center gap-2">
            <FileText className="h-5 w-5 text-[var(--color-primary)]" />
            <h2 className="text-lg font-semibold text-[var(--color-text)]">Document Info</h2>
          </div>
          <button
            onClick={onClose}
            className="rounded p-1 text-[var(--color-text-muted)] transition-colors hover:bg-[var(--color-hover)]"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="px-5 py-4">
          <table className="w-full text-sm">
            <tbody>
              {rows.map((row) => (
                <tr key={row.label}>
                  <td className="py-2 pr-4 font-medium text-[var(--color-text-muted)]">{row.label}</td>
                  <td className="py-2 text-[var(--color-text)]">{row.value}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

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
