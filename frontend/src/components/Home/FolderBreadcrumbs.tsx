import { ChevronRight, Home } from "lucide-react";
import type { Breadcrumb } from "../../lib/api";

interface FolderBreadcrumbsProps {
  breadcrumbs: Breadcrumb[];
  onNavigate: (folderId: string | null) => void;
}

export function FolderBreadcrumbs({
  breadcrumbs,
  onNavigate,
}: FolderBreadcrumbsProps) {
  return (
    <nav className="mb-4 flex items-center gap-1 text-sm" aria-label="Breadcrumb">
      <button
        onClick={() => onNavigate(null)}
        className="flex items-center gap-1 rounded px-2 py-1 text-[var(--color-text-muted)] transition hover:bg-gray-100 hover:text-[var(--color-text)]"
      >
        <Home className="h-4 w-4" />
        <span>Home</span>
      </button>
      {breadcrumbs.map((crumb) => (
        <span key={crumb.id} className="flex items-center gap-1">
          <ChevronRight className="h-4 w-4 text-[var(--color-text-muted)]" />
          <button
            onClick={() => onNavigate(crumb.id)}
            className="rounded px-2 py-1 text-[var(--color-text-muted)] transition hover:bg-gray-100 hover:text-[var(--color-text)]"
          >
            {crumb.name}
          </button>
        </span>
      ))}
    </nav>
  );
}
