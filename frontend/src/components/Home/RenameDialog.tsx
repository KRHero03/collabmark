/**
 * Small modal for renaming a document from the home page.
 *
 * Pre-fills the current title and calls onSave with the new value.
 * The Save button is disabled when the title is empty or unchanged.
 */

import { useEffect, useRef, useState } from "react";
import { X } from "lucide-react";

interface RenameDialogProps {
  currentTitle: string;
  open: boolean;
  onClose: () => void;
  onSave: (newTitle: string) => void;
}

export function RenameDialog({
  currentTitle,
  open,
  onClose,
  onSave,
}: RenameDialogProps) {
  const [title, setTitle] = useState(currentTitle);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (open) {
      setTitle(currentTitle);
      setTimeout(() => inputRef.current?.select(), 0);
    }
  }, [open, currentTitle]);

  if (!open) return null;

  const canSave = title.trim().length > 0 && title.trim() !== currentTitle;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (canSave) {
      onSave(title.trim());
      onClose();
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      onClick={onClose}
    >
      <div
        className="w-full max-w-sm rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-[var(--color-border)] px-5 py-4">
          <h2 className="text-lg font-semibold text-[var(--color-text)]">
            Rename document
          </h2>
          <button
            onClick={onClose}
            className="rounded p-1 text-[var(--color-text-muted)] transition-colors hover:bg-[var(--color-hover)]"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="px-5 py-4">
          <input
            ref={inputRef}
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Document title"
            className="w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] px-3 py-2 text-sm text-[var(--color-text)] outline-none focus:border-[var(--color-primary)]"
            autoFocus
          />
        </form>

        <div className="flex justify-end gap-2 border-t border-[var(--color-border)] px-5 py-3">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-[var(--color-border)] px-4 py-2 text-sm font-medium text-[var(--color-text)] transition-colors hover:bg-[var(--color-hover)]"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleSubmit as () => void}
            disabled={!canSave}
            className="rounded-lg bg-[var(--color-primary)] px-4 py-2 text-sm font-medium text-white transition-colors hover:opacity-90 disabled:opacity-50"
          >
            Save
          </button>
        </div>
      </div>
    </div>
  );
}
