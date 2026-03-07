import { useEffect, useRef } from "react";
import { Link } from "react-router";
import {
  BookOpen,
  Building2,
  Clock,
  Folder,
  Home,
  LogOut,
  Moon,
  Settings,
  Sun,
  Trash2,
  Users,
  User,
  X,
} from "lucide-react";
import { UserAvatar } from "./UserAvatar";

export type SidebarTab = "browse" | "shared" | "recent" | "trash";

interface MobileSidebarProps {
  open: boolean;
  onClose: () => void;
  user: {
    name: string;
    email: string;
    avatar_url: string | null;
    org_id?: string | null;
    org_role?: string | null;
    is_super_admin?: boolean;
  } | null;
  dark: boolean;
  onToggleDark: () => void;
  onLogout: () => void;
  activeTab?: SidebarTab;
  onTabChange?: (tab: SidebarTab) => void;
}

const NAV_TABS: { key: SidebarTab; label: string; icon: typeof Folder }[] = [
  { key: "browse", label: "Files", icon: Folder },
  { key: "shared", label: "Shared with me", icon: Users },
  { key: "recent", label: "Recently viewed", icon: Clock },
  { key: "trash", label: "Trash", icon: Trash2 },
];

export function MobileSidebar({
  open,
  onClose,
  user,
  dark,
  onToggleDark,
  onLogout,
  activeTab,
  onTabChange,
}: MobileSidebarProps) {
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [open, onClose]);

  return (
    <>
      {/* Backdrop */}
      <div
        className={`fixed inset-0 z-[60] bg-black/40 transition-opacity duration-300 md:hidden ${
          open ? "opacity-100" : "pointer-events-none opacity-0"
        }`}
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Drawer panel */}
      <aside
        ref={panelRef}
        className={`fixed inset-y-0 left-0 z-[70] flex w-72 max-w-[85vw] flex-col bg-[var(--color-bg)] shadow-2xl transition-transform duration-300 ease-in-out md:hidden ${
          open ? "translate-x-0" : "-translate-x-full"
        }`}
        aria-label="Navigation drawer"
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-[var(--color-border)] px-4 py-3">
          <Link to="/" onClick={onClose} className="text-lg font-bold text-[var(--color-text)] hover:opacity-80">
            CollabMark
          </Link>
          <div className="flex items-center gap-2">
            <button
              onClick={onToggleDark}
              className="rounded-md p-1.5 text-[var(--color-text-muted)] hover:bg-black/5 dark:hover:bg-white/10"
              title={dark ? "Light mode" : "Dark mode"}
            >
              {dark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            </button>
            <button
              onClick={onClose}
              className="rounded-md p-1.5 text-[var(--color-text-muted)] hover:bg-black/5 dark:hover:bg-white/10"
              aria-label="Close menu"
            >
              <X className="h-5 w-5" />
            </button>
          </div>
        </div>

        {/* User profile */}
        {user && (
          <div className="border-b border-[var(--color-border)] px-4 py-4">
            <div className="flex items-center gap-3">
              <UserAvatar url={user.avatar_url} name={user.name} size="lg" />
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-semibold text-[var(--color-text)]">{user.name}</p>
                <p className="truncate text-xs text-[var(--color-text-muted)]">{user.email}</p>
              </div>
            </div>
          </div>
        )}

        {/* Navigation tabs */}
        {onTabChange && (
          <div className="border-b border-[var(--color-border)] px-3 py-3">
            <p className="mb-2 px-2 text-[10px] font-semibold uppercase tracking-wider text-[var(--color-text-muted)]">
              Navigation
            </p>
            <nav className="flex flex-col gap-0.5">
              {NAV_TABS.map(({ key, label, icon: Icon }) => (
                <button
                  key={key}
                  onClick={() => {
                    onTabChange(key);
                    onClose();
                  }}
                  className={`flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition ${
                    activeTab === key
                      ? "bg-[var(--color-primary)] text-white"
                      : "text-[var(--color-text)] hover:bg-black/5 dark:hover:bg-white/10"
                  }`}
                >
                  <Icon className="h-4 w-4 flex-shrink-0" />
                  {label}
                </button>
              ))}
            </nav>
          </div>
        )}

        {/* Account links */}
        <div className="flex-1 overflow-y-auto px-3 py-3">
          <p className="mb-2 px-2 text-[10px] font-semibold uppercase tracking-wider text-[var(--color-text-muted)]">
            Account
          </p>
          <nav className="flex flex-col gap-0.5">
            <Link
              to="/"
              onClick={onClose}
              className="flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm text-[var(--color-text)] hover:bg-black/5 dark:hover:bg-white/10"
            >
              <Home className="h-4 w-4 flex-shrink-0 text-[var(--color-text-muted)]" />
              Home
            </Link>
            <Link
              to="/profile"
              onClick={onClose}
              className="flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm text-[var(--color-text)] hover:bg-black/5 dark:hover:bg-white/10"
            >
              <User className="h-4 w-4 flex-shrink-0 text-[var(--color-text-muted)]" />
              Profile
            </Link>
            <Link
              to="/api-docs"
              onClick={onClose}
              className="flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm text-[var(--color-text)] hover:bg-black/5 dark:hover:bg-white/10"
            >
              <BookOpen className="h-4 w-4 flex-shrink-0 text-[var(--color-text-muted)]" />
              API Docs
            </Link>
            {user?.org_id && user?.org_role === "admin" && !user?.is_super_admin && (
              <Link
                to={`/org/${user.org_id}/settings`}
                onClick={onClose}
                className="flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm text-[var(--color-text)] hover:bg-black/5 dark:hover:bg-white/10"
              >
                <Building2 className="h-4 w-4 flex-shrink-0 text-[var(--color-text-muted)]" />
                Org Settings
              </Link>
            )}
            <Link
              to="/settings"
              onClick={onClose}
              className="flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm text-[var(--color-text)] hover:bg-black/5 dark:hover:bg-white/10"
            >
              <Settings className="h-4 w-4 flex-shrink-0 text-[var(--color-text-muted)]" />
              Settings
            </Link>
          </nav>
        </div>

        {/* Sign Out at bottom */}
        <div className="border-t border-[var(--color-border)] px-3 py-3">
          <button
            onClick={() => {
              onClose();
              onLogout();
            }}
            className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium text-[var(--color-danger)] hover:bg-red-50 dark:hover:bg-red-900/20"
          >
            <LogOut className="h-4 w-4 flex-shrink-0" />
            Sign Out
          </button>
        </div>
      </aside>
    </>
  );
}
