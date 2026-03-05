import { useEffect, useRef, useState } from "react";
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
  MoreHorizontal,
} from "lucide-react";
import { useNavigate } from "react-router";
import { PresenceAvatars } from "./PresenceAvatars";
import type { PresenceUser } from "../../hooks/usePresence";

interface EditorToolbarProps {
  title: string;
  onTitleChange: (title: string) => void;
  onExportMd: () => void;
  onExportPdf?: () => void;
  onShare?: () => void;
  onHistory?: () => void;
  onComments?: () => void;
  onPresentation?: () => void;
  presentationMode?: boolean;
  readOnly?: boolean;
  presenceUsers?: PresenceUser[];
  currentUserName?: string;
}

export function EditorToolbar({
  title,
  onTitleChange,
  onExportMd,
  onExportPdf,
  onShare,
  onHistory,
  onComments,
  onPresentation,
  presentationMode,
  readOnly,
  presenceUsers = [],
  currentUserName,
}: EditorToolbarProps) {
  const navigate = useNavigate();
  const [moreOpen, setMoreOpen] = useState(false);
  const moreRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!moreOpen) return;
    const handleClickOutside = (e: MouseEvent) => {
      if (moreRef.current && !moreRef.current.contains(e.target as Node)) {
        setMoreOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [moreOpen]);

  const goBack = () => {
    if (window.history.length > 1) {
      navigate(-1);
    } else {
      navigate("/");
    }
  };

  if (presentationMode) {
    return (
      <div className="flex h-12 items-center justify-between border-b border-[var(--color-border)] px-4">
        <div className="flex items-center gap-3">
          <button
            onClick={goBack}
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

  const toolbarButtons = (
    <>
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
    </>
  );

  return (
    <div className="flex h-12 items-center justify-between border-b border-[var(--color-border)] px-4">
      <div className="flex min-w-0 flex-1 items-center gap-3">
        <button
          onClick={goBack}
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

      {/* Desktop: presence + full toolbar */}
      <div className="hidden items-center gap-2 md:flex">
        <PresenceAvatars users={presenceUsers} currentUserName={currentUserName} />
        <div className="mx-1 h-6 w-px bg-[var(--color-border)]" />
        {toolbarButtons}
      </div>

      {/* Mobile: presence + overflow dropdown */}
      <div className="flex items-center gap-2 md:hidden">
        <PresenceAvatars users={presenceUsers} currentUserName={currentUserName} />
        <div className="relative" ref={moreRef}>
          <button
            onClick={() => setMoreOpen((o) => !o)}
            className="inline-flex items-center rounded-md p-2 text-[var(--color-text-muted)] transition hover:bg-gray-100 dark:hover:bg-gray-800"
            aria-label="More options"
          >
            <MoreHorizontal className="h-5 w-5" />
          </button>
        {moreOpen && (
          <div className="absolute right-0 top-full z-50 mt-1 min-w-[180px] rounded-lg border border-[var(--color-border)] bg-white py-1 shadow-lg dark:bg-gray-900">
            {onHistory && (
              <button
                onClick={() => {
                  onHistory();
                  setMoreOpen(false);
                }}
                className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-[var(--color-text)] hover:bg-gray-100 dark:hover:bg-gray-800"
              >
                <Clock className="h-4 w-4" />
                History
              </button>
            )}
            {onComments && (
              <button
                onClick={() => {
                  onComments();
                  setMoreOpen(false);
                }}
                className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-[var(--color-text)] hover:bg-gray-100 dark:hover:bg-gray-800"
              >
                <MessageSquare className="h-4 w-4" />
                Comments
              </button>
            )}
            {onShare && (
              <button
                onClick={() => {
                  onShare();
                  setMoreOpen(false);
                }}
                className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-[var(--color-text)] hover:bg-gray-100 dark:hover:bg-gray-800"
              >
                <Link className="h-4 w-4" />
                Share
              </button>
            )}
            {onPresentation && (
              <button
                onClick={() => {
                  onPresentation?.();
                  setMoreOpen(false);
                }}
                className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-[var(--color-text)] hover:bg-gray-100 dark:hover:bg-gray-800"
              >
                <Monitor className="h-4 w-4" />
                Presentation
              </button>
            )}
            <button
              onClick={() => {
                onExportMd();
                setMoreOpen(false);
              }}
              className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-[var(--color-text)] hover:bg-gray-100 dark:hover:bg-gray-800"
            >
              <FileDown className="h-4 w-4" />
              Export .md
            </button>
            {onExportPdf && (
              <button
                onClick={() => {
                  onExportPdf();
                  setMoreOpen(false);
                }}
                className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-[var(--color-text)] hover:bg-gray-100 dark:hover:bg-gray-800"
              >
                <FileText className="h-4 w-4" />
                Export PDF
              </button>
            )}
          </div>
        )}
        </div>
      </div>
    </div>
  );
}
