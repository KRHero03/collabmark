import {
  ArrowLeft,
  Clock,
  Eye,
  FileDown,
  FileText,
  Link,
  MessageSquare,
  Monitor,
  Minimize2,
  Save,
} from "lucide-react";
import { useNavigate } from "react-router";

interface EditorToolbarProps {
  title: string;
  onTitleChange: (title: string) => void;
  onSave: () => void;
  onExportMd: () => void;
  onExportPdf?: () => void;
  onShare?: () => void;
  onHistory?: () => void;
  onComments?: () => void;
  onPresentation?: () => void;
  presentationMode?: boolean;
  saving: boolean;
  readOnly?: boolean;
}

export function EditorToolbar({
  title,
  onTitleChange,
  onSave,
  onExportMd,
  onExportPdf,
  onShare,
  onHistory,
  onComments,
  onPresentation,
  presentationMode,
  saving,
  readOnly,
}: EditorToolbarProps) {
  const navigate = useNavigate();

  if (presentationMode) {
    return (
      <div className="flex h-12 items-center justify-between border-b border-[var(--color-border)] px-4">
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate("/")}
            className="rounded p-1 text-[var(--color-text-muted)] hover:bg-gray-100 dark:hover:bg-gray-800"
          >
            <ArrowLeft className="h-5 w-5" />
          </button>
          <span className="text-lg font-semibold text-[var(--color-text)]">
            {title || "Untitled"}
          </span>
        </div>
        <button
          onClick={onPresentation}
          className="inline-flex items-center gap-1 rounded-md px-3 py-1.5 text-sm text-[var(--color-text-muted)] transition hover:bg-gray-100 dark:hover:bg-gray-800"
        >
          <Minimize2 className="h-4 w-4" />
          Exit Presentation
        </button>
      </div>
    );
  }

  return (
    <div className="flex h-12 items-center justify-between border-b border-[var(--color-border)] px-4">
      <div className="flex min-w-0 flex-1 items-center gap-3">
        <button
          onClick={() => navigate("/")}
          className="flex-shrink-0 rounded p-1 text-[var(--color-text-muted)] hover:bg-gray-100 dark:hover:bg-gray-800"
        >
          <ArrowLeft className="h-5 w-5" />
        </button>
        <input
          value={title}
          onChange={(e) => onTitleChange(e.target.value)}
          className="min-w-0 flex-1 truncate border-none bg-transparent text-lg font-semibold outline-none focus:ring-0"
          placeholder="Document title..."
          readOnly={readOnly}
        />
      </div>

      <div className="flex items-center gap-2">
        {readOnly && (
          <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2.5 py-0.5 text-xs font-medium text-amber-800 dark:bg-amber-900 dark:text-amber-200">
            <Eye className="h-3 w-3" />
            View only
          </span>
        )}

        {onHistory && (
          <button
            onClick={onHistory}
            className="inline-flex items-center gap-1 rounded-md px-3 py-1.5 text-sm text-[var(--color-text-muted)] transition hover:bg-gray-100 dark:hover:bg-gray-800"
          >
            <Clock className="h-4 w-4" />
            History
          </button>
        )}

        {onComments && (
          <button
            onClick={onComments}
            className="inline-flex items-center gap-1 rounded-md px-3 py-1.5 text-sm text-[var(--color-text-muted)] transition hover:bg-gray-100 dark:hover:bg-gray-800"
          >
            <MessageSquare className="h-4 w-4" />
            Comments
          </button>
        )}

        {onShare && (
          <button
            onClick={onShare}
            className="inline-flex items-center gap-1 rounded-md px-3 py-1.5 text-sm text-[var(--color-text-muted)] transition hover:bg-gray-100 dark:hover:bg-gray-800"
          >
            <Link className="h-4 w-4" />
            Share
          </button>
        )}

        {onPresentation && (
          <button
            onClick={onPresentation}
            className="inline-flex items-center gap-1 rounded-md px-3 py-1.5 text-sm text-[var(--color-text-muted)] transition hover:bg-gray-100 dark:hover:bg-gray-800"
            title="Presentation mode"
          >
            <Monitor className="h-4 w-4" />
          </button>
        )}

        <button
          onClick={onExportMd}
          className="inline-flex items-center gap-1 rounded-md px-3 py-1.5 text-sm text-[var(--color-text-muted)] transition hover:bg-gray-100 dark:hover:bg-gray-800"
        >
          <FileDown className="h-4 w-4" />
          .md
        </button>

        {onExportPdf && (
          <button
            onClick={onExportPdf}
            className="inline-flex items-center gap-1 rounded-md px-3 py-1.5 text-sm text-[var(--color-text-muted)] transition hover:bg-gray-100 dark:hover:bg-gray-800"
          >
            <FileText className="h-4 w-4" />
            PDF
          </button>
        )}

        {!readOnly && (
          <button
            onClick={onSave}
            disabled={saving}
            className="inline-flex items-center gap-1 rounded-md bg-[var(--color-primary)] px-3 py-1.5 text-sm font-medium text-white transition hover:bg-[var(--color-primary-hover)] disabled:opacity-50"
          >
            <Save className="h-4 w-4" />
            {saving ? "Saving..." : "Save"}
          </button>
        )}
      </div>
    </div>
  );
}
