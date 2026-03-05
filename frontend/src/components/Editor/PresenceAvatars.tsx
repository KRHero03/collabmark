/**
 * Displays stacked avatar circles for active collaborators.
 * Shows up to MAX_VISIBLE avatars with a "+N" overflow badge.
 * Hovering (desktop) or tapping (mobile) reveals a scrollable user list.
 */

import { useState, useRef, useEffect } from "react";
import type { PresenceUser } from "../../hooks/usePresence";

const MAX_VISIBLE = 3;

function getInitials(name: string): string {
  return name
    .split(/\s+/)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase() ?? "")
    .join("");
}

function Avatar({
  user,
  size = 32,
  className = "",
}: {
  user: PresenceUser;
  size?: number;
  className?: string;
}) {
  const [imgFailed, setImgFailed] = useState(false);

  if (user.avatarUrl && !imgFailed) {
    return (
      <img
        src={user.avatarUrl}
        alt={user.name}
        referrerPolicy="no-referrer"
        onError={() => setImgFailed(true)}
        className={`rounded-full border-2 border-white dark:border-gray-900 ${className}`}
        style={{ width: size, height: size }}
        title={user.name}
      />
    );
  }

  return (
    <span
      className={`inline-flex items-center justify-center rounded-full border-2 border-white text-xs font-semibold text-white dark:border-gray-900 ${className}`}
      style={{ width: size, height: size, backgroundColor: user.color }}
      title={user.name}
    >
      {getInitials(user.name)}
    </span>
  );
}

interface PresenceAvatarsProps {
  users: PresenceUser[];
  currentUserName?: string;
}

export function PresenceAvatars({ users, currentUserName }: PresenceAvatarsProps) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const handleClick = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [open]);

  const allUsers: PresenceUser[] = currentUserName
    ? [
        { name: `${currentUserName} (you)`, avatarUrl: null, color: "#3b82f6" },
        ...users,
      ]
    : users;

  const totalCount = allUsers.length;

  if (totalCount === 0) return null;

  const visible = allUsers.slice(0, MAX_VISIBLE);
  const overflow = totalCount - MAX_VISIBLE;

  return (
    <div ref={containerRef} className="relative flex items-center">
      {/* Stacked avatar row */}
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center -space-x-2 focus:outline-none"
        aria-label={`${totalCount} active user${totalCount !== 1 ? "s" : ""}`}
      >
        {visible.map((u) => (
          <Avatar
            key={u.name}
            user={u}
            size={28}
            className=""
          />
        ))}
        {overflow > 0 && (
          <span className="relative z-10 inline-flex h-7 w-7 items-center justify-center rounded-full border-2 border-white bg-gray-200 text-[10px] font-bold text-gray-700 dark:border-gray-900 dark:bg-gray-700 dark:text-gray-200">
            +{overflow}
          </span>
        )}
      </button>

      {/* Count badge */}
      <span className="ml-2 hidden text-xs font-medium text-[var(--color-text-muted)] sm:inline">
        {totalCount} active
      </span>

      {/* Dropdown user list */}
      {open && (
        <div className="absolute right-0 top-full z-50 mt-2 max-h-64 w-56 max-w-[calc(100vw-2rem)] overflow-y-auto rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] shadow-xl">
          <div className="sticky top-0 border-b border-[var(--color-border)] bg-[var(--color-bg)] px-3 py-2">
            <span className="text-xs font-semibold text-[var(--color-text-muted)] uppercase tracking-wide">
              Active now ({totalCount})
            </span>
          </div>
          {allUsers.map((u) => (
            <div
              key={u.name}
              className="flex items-center gap-3 px-3 py-2 hover:bg-black/5 dark:hover:bg-white/10"
            >
              <Avatar user={u} size={24} />
              <span className="min-w-0 truncate text-sm text-[var(--color-text)]">
                {u.name}
              </span>
              <span
                className="ml-auto h-2 w-2 flex-shrink-0 rounded-full"
                style={{ backgroundColor: "#22c55e" }}
                title="Online"
              />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
