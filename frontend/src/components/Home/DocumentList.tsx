import { FileText, Plus, Trash2 } from "lucide-react";
import { useNavigate } from "react-router";
import type { MarkdownDocument } from "../../lib/api";
import { formatDateTime } from "../../lib/dateUtils";

interface DocumentListProps {
  documents: MarkdownDocument[];
  onDelete: (id: string) => void;
  onCreate: () => void;
  onContextMenu?: (e: React.MouseEvent, doc: MarkdownDocument) => void;
}

export function DocumentList({
  documents,
  onDelete,
  onCreate,
  onContextMenu,
}: DocumentListProps) {
  const navigate = useNavigate();

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h2 className="text-xl font-semibold">My Documents</h2>
        <button
          onClick={onCreate}
          className="inline-flex items-center gap-2 rounded-lg bg-[var(--color-primary)] px-4 py-2 text-sm font-medium text-white transition hover:bg-[var(--color-primary-hover)]"
        >
          <Plus className="h-4 w-4" />
          New Document
        </button>
      </div>

      {documents.length === 0 ? (
        <div className="rounded-lg border border-dashed border-[var(--color-border)] p-12 text-center">
          <FileText className="mx-auto mb-3 h-10 w-10 text-[var(--color-text-muted)]" />
          <p className="text-[var(--color-text-muted)]">
            No documents yet. Create your first one!
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          {documents.map((doc) => (
            <div
              key={doc.id}
              className="group flex items-center justify-between rounded-lg border border-[var(--color-border)] p-4 transition hover:bg-[var(--color-bg-secondary)] cursor-pointer"
              onClick={() => navigate(`/edit/${doc.id}`)}
              onContextMenu={(e) => {
                if (onContextMenu) {
                  e.preventDefault();
                  onContextMenu(e, doc);
                }
              }}
            >
              <div className="flex items-center gap-3">
                <FileText className="h-5 w-5 text-[var(--color-primary)]" />
                <div>
                  <p className="font-medium">{doc.title}</p>
                  <p className="text-xs text-[var(--color-text-muted)]">
                    Updated {formatDateTime(doc.updated_at)}
                  </p>
                </div>
              </div>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onDelete(doc.id);
                }}
                className="invisible rounded p-1 text-[var(--color-text-muted)] transition hover:bg-red-50 hover:text-[var(--color-danger)] group-hover:visible"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
