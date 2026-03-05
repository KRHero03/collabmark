/**
 * Google Docs-style share dialog: add collaborators by email,
 * manage the "people with access" list, toggle general access,
 * and copy the document link.
 */

import { useCallback, useEffect, useState } from "react";
import { Copy, Globe, Link2, Lock, Trash2, UserPlus, X } from "lucide-react";
import {
  sharingApi,
  type Collaborator,
  type GeneralAccess,
} from "../../lib/api";
import { UserAvatar } from "../Layout/UserAvatar";

interface ShareDialogProps {
  docId: string;
  open: boolean;
  onClose: () => void;
  isOwner: boolean;
  generalAccess: GeneralAccess;
  ownerEmail: string;
  ownerName: string;
  ownerAvatarUrl?: string | null;
  onGeneralAccessChange: (ga: GeneralAccess) => void;
}

export function ShareDialog({
  docId,
  open,
  onClose,
  isOwner,
  generalAccess,
  ownerEmail,
  ownerName,
  ownerAvatarUrl,
  onGeneralAccessChange,
}: ShareDialogProps) {
  const [collaborators, setCollaborators] = useState<Collaborator[]>([]);
  const [email, setEmail] = useState("");
  const [permission, setPermission] = useState<"view" | "edit">("view");
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const fetchCollaborators = useCallback(async () => {
    if (!isOwner) return;
    try {
      const { data } = await sharingApi.listCollaborators(docId);
      setCollaborators(data);
    } catch {
      setCollaborators([]);
    }
  }, [docId, isOwner]);

  useEffect(() => {
    if (open) {
      fetchCollaborators();
      setError(null);
    }
  }, [open, fetchCollaborators]);

  const handleAdd = async () => {
    if (!email.trim()) return;
    setError(null);
    setLoading(true);
    try {
      await sharingApi.addCollaborator(docId, {
        email: email.trim(),
        permission,
      });
      setEmail("");
      await fetchCollaborators();
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail ?? "Failed to add collaborator";
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  const handleRemove = async (userId: string) => {
    await sharingApi.removeCollaborator(docId, userId);
    setCollaborators((prev) => prev.filter((c) => c.user_id !== userId));
  };

  const handlePermissionChange = async (
    collaborator: Collaborator,
    newPerm: "view" | "edit",
  ) => {
    if (newPerm === collaborator.permission) return;
    try {
      await sharingApi.addCollaborator(docId, {
        email: collaborator.email,
        permission: newPerm,
      });
      setCollaborators((prev) =>
        prev.map((c) =>
          c.user_id === collaborator.user_id
            ? { ...c, permission: newPerm }
            : c,
        ),
      );
    } catch {
      setError("Failed to update permission");
    }
  };

  const handleGeneralAccessChange = async (value: GeneralAccess) => {
    try {
      await sharingApi.updateGeneralAccess(docId, value);
      onGeneralAccessChange(value);
    } catch {
      setError("Failed to update access settings");
    }
  };

  const handleCopyLink = () => {
    navigator.clipboard.writeText(
      `${window.location.origin}/edit/${docId}`,
    );
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (!open) return null;

  const gaLabel: Record<GeneralAccess, string> = {
    restricted: "Restricted",
    anyone_view: "Anyone with the link can view",
    anyone_edit: "Anyone with the link can edit",
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="w-[calc(100%-2rem)] max-w-lg rounded-xl bg-[var(--color-surface)] p-6 shadow-xl">
        {/* Header */}
        <div className="mb-5 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-[var(--color-text)]">
            Share document
          </h2>
          <button
            onClick={onClose}
            className="rounded p-1 text-[var(--color-text-muted)] hover:bg-[var(--color-hover)]"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Add people section (owner only) */}
        {isOwner && (
          <div className="mb-5">
            <label className="mb-1 flex items-center gap-1.5 text-sm font-medium text-[var(--color-text)]">
              <UserPlus className="h-4 w-4" />
              Add people
            </label>
            <div className="flex gap-2">
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleAdd()}
                placeholder="Enter email address"
                className="flex-1 rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2 text-sm text-[var(--color-text)] placeholder-[var(--color-text-muted)] outline-none focus:border-[var(--color-primary)]"
              />
              <select
                value={permission}
                onChange={(e) =>
                  setPermission(e.target.value as "view" | "edit")
                }
                className="rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] px-2 py-2 text-sm text-[var(--color-text)] outline-none"
              >
                <option value="view">Viewer</option>
                <option value="edit">Editor</option>
              </select>
              <button
                onClick={handleAdd}
                disabled={loading || !email.trim()}
                className="rounded-md bg-[var(--color-primary)] px-4 py-2 text-sm font-medium text-white transition hover:bg-[var(--color-primary-hover)] disabled:opacity-50"
              >
                Add
              </button>
            </div>
            {error && (
              <p className="mt-1 text-xs text-red-500">{error}</p>
            )}
          </div>
        )}

        {/* People with access */}
        <div className="mb-5">
          <h3 className="mb-2 text-sm font-medium text-[var(--color-text)]">
            People with access
          </h3>
          <ul className="max-h-48 space-y-1 overflow-auto">
            {/* Owner (always shown) */}
            <li className="flex items-center justify-between rounded-md px-3 py-2">
              <div className="flex items-center gap-3">
                <UserAvatar url={ownerAvatarUrl} name={ownerName || "?"} size="md" />
                <div>
                  <p className="text-sm font-medium text-[var(--color-text)]">
                    {ownerName}{" "}
                    <span className="text-[var(--color-text-muted)]">
                      (Owner)
                    </span>
                  </p>
                  <p className="text-xs text-[var(--color-text-muted)]">
                    {ownerEmail}
                  </p>
                </div>
              </div>
            </li>

            {/* Collaborators */}
            {collaborators.map((c) => (
              <li
                key={c.user_id}
                className="flex items-center justify-between rounded-md px-3 py-2 hover:bg-[var(--color-hover)]"
              >
                <div className="flex items-center gap-3">
                  <UserAvatar url={c.avatar_url} name={c.name || "?"} size="md" />
                  <div>
                    <p className="text-sm font-medium text-[var(--color-text)]">
                      {c.name}
                    </p>
                    <p className="text-xs text-[var(--color-text-muted)]">
                      {c.email}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {isOwner ? (
                    <select
                      value={c.permission}
                      onChange={(e) =>
                        handlePermissionChange(
                          c,
                          e.target.value as "view" | "edit",
                        )
                      }
                      className="rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] px-2 py-0.5 text-xs font-medium text-[var(--color-text)] outline-none"
                    >
                      <option value="view">Viewer</option>
                      <option value="edit">Editor</option>
                    </select>
                  ) : (
                    <span className="rounded bg-[var(--color-hover)] px-2 py-0.5 text-xs font-medium text-[var(--color-text-muted)]">
                      {c.permission === "edit" ? "Editor" : "Viewer"}
                    </span>
                  )}
                  {isOwner && (
                    <button
                      onClick={() => handleRemove(c.user_id)}
                      className="rounded p-1 text-[var(--color-text-muted)] hover:bg-red-50 hover:text-red-600"
                      title="Remove access"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </div>

        {/* General access (owner only) */}
        {isOwner && (
          <div className="mb-5 rounded-lg border border-[var(--color-border)] p-4">
            <h3 className="mb-2 flex items-center gap-2 text-sm font-medium text-[var(--color-text)]">
              {generalAccess === "restricted" ? (
                <Lock className="h-4 w-4" />
              ) : (
                <Globe className="h-4 w-4" />
              )}
              General access
            </h3>
            <select
              value={generalAccess}
              onChange={(e) =>
                handleGeneralAccessChange(e.target.value as GeneralAccess)
              }
              className="w-full rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2 text-sm text-[var(--color-text)] outline-none"
            >
              <option value="restricted">Restricted</option>
              <option value="anyone_view">
                Anyone with the link can view
              </option>
              <option value="anyone_edit">
                Anyone with the link can edit
              </option>
            </select>
            <p className="mt-1 text-xs text-[var(--color-text-muted)]">
              {gaLabel[generalAccess]}
            </p>
          </div>
        )}

        {/* Non-owners see current access level */}
        {!isOwner && (
          <div className="mb-5 rounded-lg border border-[var(--color-border)] p-4">
            <p className="flex items-center gap-2 text-sm text-[var(--color-text-muted)]">
              {generalAccess === "restricted" ? (
                <Lock className="h-4 w-4" />
              ) : (
                <Globe className="h-4 w-4" />
              )}
              {gaLabel[generalAccess]}
            </p>
          </div>
        )}

        {/* Copy link */}
        <button
          onClick={handleCopyLink}
          className="flex w-full items-center justify-center gap-2 rounded-md border border-[var(--color-border)] px-4 py-2.5 text-sm font-medium text-[var(--color-primary)] transition hover:bg-[var(--color-hover)]"
        >
          {copied ? (
            <>
              <Link2 className="h-4 w-4" />
              Link copied!
            </>
          ) : (
            <>
              <Copy className="h-4 w-4" />
              Copy link
            </>
          )}
        </button>
      </div>
    </div>
  );
}
