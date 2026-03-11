import { useRef } from "react";
import { Bold, Italic, Heading, Strikethrough, Code, List, ListOrdered, Link, Paperclip } from "lucide-react";
import type { EditorView } from "codemirror";
import { wrapCommand, headingCommand, listCommand, linkCommand } from "./markdownShortcuts";
import { documentsApi, extractErrorDetail } from "../../lib/api";
import { useToast } from "../../hooks/useToast";

const ATTACHMENT_MAX_SIZE = 5 * 1024 * 1024;

interface FormattingToolbarProps {
  editorView: EditorView | null;
  docId?: string;
}

export function FormattingToolbar({ editorView, docId }: FormattingToolbarProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { addToast } = useToast();

  const run = (cmd: (view: EditorView) => boolean) => {
    if (!editorView) return;
    cmd(editorView);
    editorView.focus();
  };

  const handleAttachment = () => {
    fileInputRef.current?.click();
  };

  const handleFileSelected = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !editorView || !docId) return;

    e.target.value = "";

    if (file.size > ATTACHMENT_MAX_SIZE) {
      addToast(`File too large (${(file.size / 1024 / 1024).toFixed(1)}MB). Maximum is 5MB.`, "error");
      return;
    }

    const isImage = file.type.startsWith("image/");
    const placeholder = isImage ? `![Uploading ${file.name}...]()` : `[Uploading ${file.name}...]()`;

    const pos = editorView.state.selection.main.head;
    editorView.dispatch({ changes: { from: pos, insert: placeholder } });

    try {
      const { data } = await documentsApi.uploadAttachment(docId, file);
      const doc = editorView.state.doc.toString();
      const idx = doc.indexOf(placeholder);
      if (idx !== -1) {
        const replacement = isImage ? `![${data.original_name}](${data.url})` : `[${data.original_name}](${data.url})`;
        editorView.dispatch({
          changes: { from: idx, to: idx + placeholder.length, insert: replacement },
        });
      }
      addToast("File uploaded successfully", "success");
    } catch (err) {
      const doc = editorView.state.doc.toString();
      const idx = doc.indexOf(placeholder);
      if (idx !== -1) {
        editorView.dispatch({ changes: { from: idx, to: idx + placeholder.length } });
      }
      addToast(extractErrorDetail(err, "Failed to upload file"), "error");
    }
  };

  const btnClass =
    "rounded p-1.5 text-[var(--color-text-muted)] transition hover:bg-[var(--color-bg-secondary)] hover:text-[var(--color-text)] disabled:opacity-30";

  return (
    <div
      className="flex items-center gap-0.5 border-b border-[var(--color-border)] bg-white px-2 py-1 dark:bg-[var(--color-surface)]"
      data-testid="formatting-toolbar"
    >
      <button onClick={() => run(wrapCommand("**"))} className={btnClass} title="Bold (Ctrl+B)" data-testid="fmt-bold">
        <Bold className="h-4 w-4" />
      </button>
      <button
        onClick={() => run(wrapCommand("*"))}
        className={btnClass}
        title="Italic (Ctrl+I)"
        data-testid="fmt-italic"
      >
        <Italic className="h-4 w-4" />
      </button>
      <button
        onClick={() => run(headingCommand)}
        className={btnClass}
        title="Heading (Ctrl+Shift+H)"
        data-testid="fmt-heading"
      >
        <Heading className="h-4 w-4" />
      </button>
      <button
        onClick={() => run(wrapCommand("~~"))}
        className={btnClass}
        title="Strikethrough (Ctrl+Shift+S)"
        data-testid="fmt-strikethrough"
      >
        <Strikethrough className="h-4 w-4" />
      </button>
      <button
        onClick={() => run(wrapCommand("`"))}
        className={btnClass}
        title="Inline code (Ctrl+E)"
        data-testid="fmt-code"
      >
        <Code className="h-4 w-4" />
      </button>

      <div className="mx-1 h-4 w-px bg-[var(--color-border)]" />

      <button onClick={() => run(listCommand(false))} className={btnClass} title="Unordered list" data-testid="fmt-ul">
        <List className="h-4 w-4" />
      </button>
      <button onClick={() => run(listCommand(true))} className={btnClass} title="Ordered list" data-testid="fmt-ol">
        <ListOrdered className="h-4 w-4" />
      </button>

      <div className="mx-1 h-4 w-px bg-[var(--color-border)]" />

      <button
        onClick={() => run(linkCommand)}
        className={btnClass}
        title="Insert link (Ctrl+Shift+L)"
        data-testid="fmt-link"
      >
        <Link className="h-4 w-4" />
      </button>
      <button
        onClick={handleAttachment}
        className={btnClass}
        title="Upload attachment"
        data-testid="fmt-attachment"
        disabled={!docId}
      >
        <Paperclip className="h-4 w-4" />
      </button>

      <input
        ref={fileInputRef}
        type="file"
        className="hidden"
        onChange={handleFileSelected}
        data-testid="fmt-file-input"
      />
    </div>
  );
}
