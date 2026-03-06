import { useEffect, useRef, useState } from "react";

interface CreateFolderDialogProps {
  open: boolean;
  onClose: () => void;
  onCreate: (name: string) => void;
}

export function CreateFolderDialog({ open, onClose, onCreate }: CreateFolderDialogProps) {
  const [name, setName] = useState("Untitled Folder");
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (open) {
      setName("Untitled Folder");
      setTimeout(() => inputRef.current?.select(), 0);
    }
  }, [open]);

  if (!open) return null;

  const trimmed = name.trim();
  const canCreate = trimmed.length > 0;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (canCreate) {
      onCreate(trimmed);
      onClose();
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <form onSubmit={handleSubmit} className="w-[calc(100%-2rem)] max-w-sm rounded-xl bg-white p-6 shadow-lg">
        <h3 className="mb-4 text-lg font-semibold">New Folder</h3>
        <input
          ref={inputRef}
          value={name}
          onChange={(e) => setName(e.target.value)}
          className="mb-4 w-full rounded-lg border border-[var(--color-border)] px-3 py-2 text-sm focus:border-[var(--color-primary)] focus:outline-none"
          placeholder="Folder name"
          autoFocus
        />
        <div className="flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-[var(--color-border)] px-4 py-2 text-sm transition hover:bg-gray-50"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={!canCreate}
            className="rounded-lg bg-[var(--color-primary)] px-4 py-2 text-sm font-medium text-white transition hover:bg-[var(--color-primary-hover)] disabled:opacity-50"
          >
            Create
          </button>
        </div>
      </form>
    </div>
  );
}
