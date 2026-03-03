/**
 * Right-click context menu for document cards on the home page.
 *
 * Renders a floating menu at the pointer coordinates with actions
 * that vary based on whether the user owns the document. Closes on
 * outside click, Escape key, or any action selection.
 */

import { useEffect, useRef } from "react";
import {
  ExternalLink,
  FolderOpen,
  Pencil,
  Share2,
  Trash2,
  Info,
  RotateCcw,
  XCircle,
} from "lucide-react";

export interface ContextMenuAction {
  label: string;
  icon: React.ReactNode;
  onClick: () => void;
  variant?: "danger";
}

interface DocumentContextMenuProps {
  x: number;
  y: number;
  actions: ContextMenuAction[];
  onClose: () => void;
}

export function DocumentContextMenu({
  x,
  y,
  actions,
  onClose,
}: DocumentContextMenuProps) {
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        onClose();
      }
    };
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("mousedown", handleClick);
    document.addEventListener("keydown", handleKey);
    return () => {
      document.removeEventListener("mousedown", handleClick);
      document.removeEventListener("keydown", handleKey);
    };
  }, [onClose]);

  useEffect(() => {
    if (!menuRef.current) return;
    const rect = menuRef.current.getBoundingClientRect();
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    if (rect.right > vw) {
      menuRef.current.style.left = `${x - rect.width}px`;
    }
    if (rect.bottom > vh) {
      menuRef.current.style.top = `${y - rect.height}px`;
    }
  }, [x, y]);

  return (
    <div
      ref={menuRef}
      role="menu"
      className="fixed z-50 min-w-[180px] rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] py-1 shadow-lg"
      style={{ top: y, left: x }}
    >
      {actions.map((action) => (
        <button
          key={action.label}
          role="menuitem"
          onClick={() => {
            action.onClick();
            onClose();
          }}
          className={`flex w-full items-center gap-2 px-3 py-2 text-left text-sm transition-colors hover:bg-[var(--color-hover)] ${
            action.variant === "danger"
              ? "text-red-600 dark:text-red-400"
              : "text-[var(--color-text)]"
          }`}
        >
          {action.icon}
          {action.label}
        </button>
      ))}
    </div>
  );
}

export interface EntityPermissions {
  can_view: boolean;
  can_edit: boolean;
  can_delete: boolean;
  can_share: boolean;
}

export function getEntityActions(
  entityType: "document" | "folder",
  perms: EntityPermissions,
  handlers: {
    onOpen: () => void;
    onShare?: () => void;
    onRename?: () => void;
    onTrash?: () => void;
    onInfo: () => void;
    onViewAcl?: () => void;
  },
): ContextMenuAction[] {
  const actions: ContextMenuAction[] = [];

  const openIcon = entityType === "folder"
    ? <FolderOpen className="h-4 w-4" />
    : <ExternalLink className="h-4 w-4" />;
  actions.push({ label: "Open", icon: openIcon, onClick: handlers.onOpen });

  if (perms.can_share && handlers.onShare) {
    actions.push({ label: "Share", icon: <Share2 className="h-4 w-4" />, onClick: handlers.onShare });
  }
  if (perms.can_edit && handlers.onRename) {
    actions.push({ label: "Rename", icon: <Pencil className="h-4 w-4" />, onClick: handlers.onRename });
  }
  if (perms.can_delete && handlers.onTrash) {
    actions.push({ label: "Move to Trash", icon: <Trash2 className="h-4 w-4" />, onClick: handlers.onTrash, variant: "danger" });
  }
  if (handlers.onViewAcl) {
    actions.push({ label: "View Permissions", icon: <Info className="h-4 w-4" />, onClick: handlers.onViewAcl });
  }
  actions.push({ label: "Info", icon: <Info className="h-4 w-4" />, onClick: handlers.onInfo });

  return actions;
}

export function getOwnedDocActions(handlers: {
  onOpen: () => void;
  onShare: () => void;
  onRename: () => void;
  onTrash: () => void;
  onInfo: () => void;
}): ContextMenuAction[] {
  return getEntityActions("document", { can_view: true, can_edit: true, can_delete: true, can_share: true }, handlers);
}

export function getSharedDocActions(handlers: {
  onOpen: () => void;
  onInfo: () => void;
}): ContextMenuAction[] {
  return getEntityActions("document", { can_view: true, can_edit: false, can_delete: false, can_share: false }, handlers);
}

export function getTrashDocActions(handlers: {
  onRestore: () => void;
  onDeletePermanently: () => void;
  onInfo: () => void;
}): ContextMenuAction[] {
  return [
    { label: "Restore", icon: <RotateCcw className="h-4 w-4" />, onClick: handlers.onRestore },
    { label: "Delete permanently", icon: <XCircle className="h-4 w-4" />, onClick: handlers.onDeletePermanently, variant: "danger" },
    { label: "Info", icon: <Info className="h-4 w-4" />, onClick: handlers.onInfo },
  ];
}

export function getFolderActions(handlers: {
  onOpen: () => void;
  onShare: () => void;
  onRename: () => void;
  onTrash: () => void;
  onInfo: () => void;
}): ContextMenuAction[] {
  return getEntityActions("folder", { can_view: true, can_edit: true, can_delete: true, can_share: true }, handlers);
}

export function getTrashFolderActions(handlers: {
  onRestore: () => void;
  onDeletePermanently: () => void;
  onInfo: () => void;
}): ContextMenuAction[] {
  return [
    { label: "Restore", icon: <RotateCcw className="h-4 w-4" />, onClick: handlers.onRestore },
    { label: "Delete permanently", icon: <XCircle className="h-4 w-4" />, onClick: handlers.onDeletePermanently, variant: "danger" },
    { label: "Info", icon: <Info className="h-4 w-4" />, onClick: handlers.onInfo },
  ];
}
