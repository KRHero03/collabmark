import { BookOpen, Building2, FileText, LogOut, Menu, Moon, Settings, Sun } from "lucide-react";
import { Link, useNavigate } from "react-router";
import { useAuth } from "../../hooks/useAuth";
import { UserAvatar } from "./UserAvatar";
import { MobileSidebar, type SidebarTab } from "./MobileSidebar";
import { useCallback, useEffect, useState } from "react";

interface NavbarProps {
  activeTab?: SidebarTab;
  onTabChange?: (tab: SidebarTab) => void;
}

export function Navbar({ activeTab, onTabChange }: NavbarProps) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [dark, setDark] = useState(() => document.documentElement.classList.contains("dark"));
  const [sidebarOpen, setSidebarOpen] = useState(false);

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
    setSidebarOpen(false);
    await logout();
    navigate("/");
  };

  return (
    <>
      <nav className="sticky top-0 z-50 border-b border-[var(--color-border)] bg-white px-3 dark:bg-[var(--color-bg-secondary)] md:px-6">
        <div className="flex h-14 items-center justify-between">
          {/* Left: hamburger (mobile) + logo */}
          <div className="flex items-center gap-2">
            {user && (
              <button
                onClick={() => setSidebarOpen(true)}
                className="rounded p-1.5 text-[var(--color-text-muted)] hover:bg-black/5 dark:hover:bg-white/10 md:hidden"
                aria-label="Open menu"
              >
                <Menu className="h-5 w-5" />
              </button>
            )}
            <Link to="/" className="flex items-center gap-2 text-lg font-bold">
              <FileText className="h-6 w-6 text-[var(--color-primary)]" />
              <span className="hidden sm:inline">CollabMark</span>
            </Link>
          </div>

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

                {user.org_id && (
                  <Link
                    to={`/org/${user.org_id}/settings`}
                    className="flex items-center gap-1 text-sm text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
                    title="Org Settings"
                  >
                    <Building2 className="h-4 w-4" />
                  </Link>
                )}

                <Link
                  to="/settings"
                  className="flex items-center gap-1 text-sm text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
                >
                  <Settings className="h-4 w-4" />
                </Link>

                <Link to="/profile" className="flex items-center gap-2 text-sm hover:opacity-80">
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

              {/* Mobile: just the avatar on the right as a visual indicator */}
              <div className="flex items-center md:hidden">
                <UserAvatar url={user.avatar_url} name={user.name} size="sm" />
              </div>
            </>
          )}
        </div>
      </nav>

      {/* Mobile side drawer */}
      {user && (
        <MobileSidebar
          open={sidebarOpen}
          onClose={() => setSidebarOpen(false)}
          user={user}
          dark={dark}
          onToggleDark={toggleDark}
          onLogout={handleLogout}
          activeTab={activeTab}
          onTabChange={onTabChange}
        />
      )}
    </>
  );
}
