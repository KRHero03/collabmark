import { FileText } from "lucide-react";
import { Link } from "react-router";

/**
 * Beautiful themed 404 page.
 *
 * Rendered for unknown URLs and when a user lacks access to a protected page
 * (we deliberately show "not found" instead of "forbidden" to avoid revealing
 * that the page exists).
 */
export function NotFoundPage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-[var(--color-bg)] px-4">
      <div className="animate-gradient absolute inset-0 bg-gradient-to-br from-blue-600 via-indigo-600 to-purple-700 opacity-[0.04] dark:opacity-[0.10]" />

      <div className="relative z-10 flex max-w-md flex-col items-center text-center">
        <div className="mb-6 flex h-16 w-16 items-center justify-center rounded-2xl bg-[var(--color-primary)]/10">
          <FileText className="h-8 w-8 text-[var(--color-primary)]" />
        </div>

        <h1 className="mb-2 text-7xl font-extrabold tracking-tight">
          <span className="bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent dark:from-blue-400 dark:to-purple-400">
            404
          </span>
        </h1>

        <h2 className="mb-3 text-2xl font-bold text-[var(--color-text)]">Page not found</h2>

        <p className="mb-8 text-[var(--color-text-muted)]">
          The page you're looking for doesn't exist or you don't have permission to view it.
        </p>

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
