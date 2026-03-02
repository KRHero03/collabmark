import { BookOpen, LogOut, Moon, Settings, Sun, User } from "lucide-react";
import { Link, useNavigate } from "react-router";
import { useAuth } from "../../hooks/useAuth";
import { useCallback, useEffect, useState } from "react";

export function Navbar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [dark, setDark] = useState(
    () => document.documentElement.classList.contains("dark")
  );

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
    await logout();
    navigate("/");
  };

  return (
    <nav className="sticky top-0 z-50 flex h-14 items-center justify-between border-b border-[var(--color-border)] bg-white px-6">
      <Link to="/" className="flex items-center gap-2 font-bold text-lg">
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" fill="none" className="h-6 w-6">
          <rect width="64" height="64" rx="14" fill="#2563eb"/>
          <text x="32" y="46" fontFamily="system-ui" fontSize="38" fontWeight="700" fill="white" textAnchor="middle">M</text>
          <circle cx="52" cy="12" r="8" fill="#22c55e"/>
        </svg>
        CollabMark
      </Link>

      {user && (
        <div className="flex items-center gap-4">
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
            Settings
          </Link>

          <Link
            to="/profile"
            className="flex items-center gap-2 text-sm hover:opacity-80"
          >
            {user.avatar_url ? (
              <img
                src={user.avatar_url}
                alt={user.name}
                className="h-8 w-8 rounded-full"
              />
            ) : (
              <User className="h-8 w-8 rounded-full bg-gray-200 p-1" />
            )}
            <span className="font-medium">{user.name}</span>
          </Link>

          <button
            onClick={handleLogout}
            className="flex items-center gap-1 text-sm text-[var(--color-text-muted)] hover:text-[var(--color-danger)]"
          >
            <LogOut className="h-4 w-4" />
          </button>
        </div>
      )}
    </nav>
  );
}
