import { FileText, Trash2 } from "lucide-react";
import { Link } from "react-router";

interface NotFoundPageProps {
  code?: string;
  title?: string;
  message?: string;
  icon?: "file" | "trash";
}

/**
 * Beautiful themed error page.
 *
 * Defaults to a 404 "not found" message but accepts custom overrides
 * for other error states (e.g. 410 Gone for deleted documents).
 */
export function NotFoundPage({
  code = "404",
  title = "Page not found",
  message = "The page you're looking for doesn't exist or you don't have permission to view it.",
  icon = "file",
}: NotFoundPageProps) {
  const Icon = icon === "trash" ? Trash2 : FileText;

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-[var(--color-bg)] px-4">
      <div className="animate-gradient absolute inset-0 bg-gradient-to-br from-blue-600 via-indigo-600 to-purple-700 opacity-[0.04] dark:opacity-[0.10]" />

      <div className="relative z-10 flex max-w-md flex-col items-center text-center">
        <div className="mb-6 flex h-16 w-16 items-center justify-center rounded-2xl bg-[var(--color-primary)]/10">
          <Icon className="h-8 w-8 text-[var(--color-primary)]" />
        </div>

        <h1 className="mb-2 text-7xl font-extrabold tracking-tight">
          <span className="bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent dark:from-blue-400 dark:to-purple-400">
            {code}
          </span>
        </h1>

        <h2 className="mb-3 text-2xl font-bold text-[var(--color-text)]">{title}</h2>

        <p className="mb-8 text-[var(--color-text-muted)]">{message}</p>

        <Link
          to="/"
          className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 px-8 py-3 text-base font-semibold text-white shadow-lg shadow-blue-500/25 transition hover:shadow-xl hover:shadow-blue-500/30 dark:from-blue-500 dark:to-indigo-500"
          data-testid="go-home-link"
        >
          Go Home
        </Link>
      </div>
    </div>
  );
}
