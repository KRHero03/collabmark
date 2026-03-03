import { BookOpen, FileText, LogOut, Menu, Moon, Settings, Sun, X } from "lucide-react";
import { Link, useNavigate } from "react-router";
import { useAuth } from "../../hooks/useAuth";
import { UserAvatar } from "./UserAvatar";
import { useCallback, useEffect, useState } from "react";

export function Navbar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [dark, setDark] = useState(
    () => document.documentElement.classList.contains("dark"),
  );
  const [menuOpen, setMenuOpen] = useState(false);

  const toggleDark = useCallback(() => {
    const next = !dark;
    setDark(next);
    document.documentElement.classList.toggle("dark", next);
    localStorage.setItem("theme", next ? "dark" : "light");
  }, [dark]);

  useEffect(() => {
    const saved = localStorage.getItem("theme");
    if (saved === "dark") {
      document.documentElement.classList.add("dark");
      setDark(true);
    }
  }, []);

  const handleLogout = async () => {
    setMenuOpen(false);
    await logout();
    navigate("/");
  };

  return (
    <nav className="sticky top-0 z-50 border-b border-[var(--color-border)] bg-white px-3 dark:bg-[var(--color-bg-secondary)] md:px-6">
      <div className="flex h-14 items-center justify-between">
        <Link to="/" className="flex items-center gap-2 text-lg font-bold">
          <FileText className="h-6 w-6 text-[var(--color-primary)]" />
          <span className="hidden sm:inline">CollabMark</span>
        </Link>

        {user && (
          <>
            {/* Desktop nav */}
            <div className="hidden items-center gap-4 md:flex">
              <button
                onClick={toggleDark}
                className="rounded p-1 text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
                title={dark ? "Light mode" : "Dark mode"}
              >
                {dark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
              </button>

              <Link
                to="/api-docs"
                className="flex items-center gap-1 text-sm text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
              >
                <BookOpen className="h-4 w-4" />
                API Docs
              </Link>

              <Link
                to="/settings"
                className="flex items-center gap-1 text-sm text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
              >
                <Settings className="h-4 w-4" />
              </Link>

              <Link
                to="/profile"
                className="flex items-center gap-2 text-sm hover:opacity-80"
              >
                <UserAvatar url={user.avatar_url} name={user.name} size="md" />
                <span className="font-medium">{user.name}</span>
              </Link>

              <button
                onClick={handleLogout}
                className="flex items-center gap-1 text-sm text-[var(--color-text-muted)] hover:text-[var(--color-danger)]"
              >
                <LogOut className="h-4 w-4" />
              </button>
            </div>

            {/* Mobile hamburger */}
            <div className="flex items-center gap-2 md:hidden">
              <button
                onClick={toggleDark}
                className="rounded p-1.5 text-[var(--color-text-muted)]"
              >
                {dark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
              </button>
              <button
                onClick={() => setMenuOpen((p) => !p)}
                className="rounded p-1.5 text-[var(--color-text-muted)]"
                aria-label="Toggle menu"
              >
                {menuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
              </button>
            </div>
          </>
        )}
      </div>

      {/* Mobile dropdown */}
      {user && menuOpen && (
        <div className="border-t border-[var(--color-border)] pb-4 pt-2 md:hidden">
          <div className="mb-3 flex items-center gap-3 px-1">
            <UserAvatar url={user.avatar_url} name={user.name} size="md" />
            <div className="min-w-0">
              <p className="truncate text-sm font-medium">{user.name}</p>
              <p className="truncate text-xs text-[var(--color-text-muted)]">
                {user.email}
              </p>
            </div>
          </div>
          <div className="flex flex-col gap-1">
            <Link
              to="/profile"
              onClick={() => setMenuOpen(false)}
              className="rounded-md px-2 py-2 text-sm hover:bg-[var(--color-hover)]"
            >
              Profile
            </Link>
            <Link
              to="/api-docs"
              onClick={() => setMenuOpen(false)}
              className="rounded-md px-2 py-2 text-sm hover:bg-[var(--color-hover)]"
            >
              API Docs
            </Link>
            <Link
              to="/settings"
              onClick={() => setMenuOpen(false)}
              className="rounded-md px-2 py-2 text-sm hover:bg-[var(--color-hover)]"
            >
              Settings
            </Link>
            <button
              onClick={handleLogout}
              className="rounded-md px-2 py-2 text-left text-sm text-[var(--color-danger)] hover:bg-[var(--color-hover)]"
            >
              Sign Out
            </button>
          </div>
        </div>
      )}
    </nav>
  );
}
