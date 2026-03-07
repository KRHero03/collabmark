import { useEffect, useMemo, useState } from "react";
import { Copy, Globe, Info, Link2, Lock, Trash2, UserPlus, Users, X } from "lucide-react";
import { foldersApi, type GeneralAccess } from "../../lib/api";
import { useShareCollaborators } from "../../hooks/useShareCollaborators";
import { UserAvatar } from "../Layout/UserAvatar";

interface FolderShareDialogProps {
  folderId: string;
  open: boolean;
  onClose: () => void;
  isOwner: boolean;
  generalAccess: GeneralAccess;
  ownerEmail: string;
  ownerName: string;
  ownerAvatarUrl?: string | null;
  onGeneralAccessChange: (ga: GeneralAccess) => void;
  orgName?: string | null;
  orgId?: string | null;
}

export function FolderShareDialog({
  folderId,
  open,
  onClose,
  isOwner,
  generalAccess,
  ownerEmail,
  ownerName,
  ownerAvatarUrl,
  onGeneralAccessChange,
  orgName,
  orgId,
}: FolderShareDialogProps) {
  const folderShareApi = useMemo(
    () => ({
      listCollaborators: foldersApi.listCollaborators,
      addCollaborator: foldersApi.addCollaborator,
      removeCollaborator: foldersApi.removeCollaborator,
      listGroupCollaborators: foldersApi.listGroupCollaborators,
      addGroupCollaborator: foldersApi.addGroupCollaborator,
      removeGroupCollaborator: foldersApi.removeGroupCollaborator,
    }),
    [],
  );

  const {
    collaborators,
    groupCollaborators,
    groupSearchQuery,
    groupSearchResults,
    showGroupSearch,
    setShowGroupSearch,
    email,
    setEmail,
    permission,
    setPermission,
    error,
    setError,
    loading,
    resetOnOpen,
    handleAdd,
    handleRemove,
    handleGroupSearch,
    handleAddGroup,
    handleRemoveGroup,
    handlePermissionChange,
  } = useShareCollaborators(folderId, isOwner, folderShareApi, orgId);

  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (open) resetOnOpen();
  }, [open, resetOnOpen]);

  const handleGeneralAccessChange = async (value: GeneralAccess) => {
    try {
      await foldersApi.update(folderId, { general_access: value });
      onGeneralAccessChange(value);
    } catch {
      setError("Failed to update access settings");
    }
  };

  const handleCopyLink = () => {
    navigator.clipboard.writeText(`${window.location.origin}/?folder=${folderId}`);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (!open) return null;

  const scope = orgName ? `Anyone in ${orgName}` : "Anyone";
  const gaLabel: Record<GeneralAccess, string> = {
    restricted: "Restricted",
    anyone_view: `${scope} with the link can view`,
    anyone_edit: `${scope} with the link can edit`,
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="w-[calc(100%-2rem)] max-w-lg rounded-xl bg-[var(--color-surface)] p-6 shadow-xl">
        <div className="mb-5 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-[var(--color-text)]">Share folder</h2>
          <button
            onClick={onClose}
            className="rounded p-1 text-[var(--color-text-muted)] hover:bg-[var(--color-hover)]"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {orgName && (
          <div className="mb-4 flex items-center gap-2 rounded-lg bg-blue-50 px-3 py-2.5 text-xs text-blue-700 dark:bg-blue-900/20 dark:text-blue-300">
            <Info className="h-3.5 w-3.5 shrink-0" />
            <span>This folder can only be shared with members of {orgName}</span>
          </div>
        )}

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
                onChange={(e) => setPermission(e.target.value as "view" | "edit")}
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
            {error && <p className="mt-1 text-xs text-red-500">{error}</p>}
            {isOwner && orgId && (
              <div className="mb-5 mt-4">
                <button
                  onClick={() => setShowGroupSearch(!showGroupSearch)}
                  className="mb-2 flex items-center gap-1.5 text-sm font-medium text-[var(--color-primary)] hover:opacity-80"
                >
                  <Users className="h-4 w-4" />
                  {showGroupSearch ? "Hide group search" : "Add a group"}
                </button>
                {showGroupSearch && (
                  <div className="relative">
                    <input
                      type="text"
                      value={groupSearchQuery}
                      onChange={(e) => handleGroupSearch(e.target.value)}
                      placeholder="Search groups by name..."
                      className="w-full rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2 text-sm text-[var(--color-text)] placeholder-[var(--color-text-muted)] outline-none focus:border-[var(--color-primary)]"
                    />
                    {groupSearchResults.length > 0 && (
                      <ul className="absolute z-10 mt-1 max-h-40 w-full overflow-auto rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] shadow-lg">
                        {groupSearchResults.map((g) => (
                          <li key={g.id}>
                            <button
                              onClick={() => handleAddGroup(g.id)}
                              className="flex w-full items-center gap-2 px-3 py-2 text-sm text-[var(--color-text)] hover:bg-[var(--color-hover)]"
                            >
                              <Users className="h-4 w-4 text-[var(--color-text-muted)]" />
                              {g.name}
                            </button>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        <div className="mb-5">
          <h3 className="mb-2 text-sm font-medium text-[var(--color-text)]">People with access</h3>
          <ul className="max-h-48 space-y-1 overflow-auto">
            <li className="flex items-center justify-between rounded-md px-3 py-2">
              <div className="flex items-center gap-3">
                <UserAvatar url={ownerAvatarUrl} name={ownerName || "?"} size="md" />
                <div>
                  <p className="text-sm font-medium text-[var(--color-text)]">
                    {ownerName} <span className="text-[var(--color-text-muted)]">(Owner)</span>
                  </p>
                  <p className="text-xs text-[var(--color-text-muted)]">{ownerEmail}</p>
                </div>
              </div>
            </li>

            {collaborators.map((c) => (
              <li
                key={c.user_id}
                className="flex items-center justify-between rounded-md px-3 py-2 hover:bg-[var(--color-hover)]"
              >
                <div className="flex items-center gap-3">
                  <UserAvatar url={c.avatar_url} name={c.name || "?"} size="md" />
                  <div>
                    <p className="text-sm font-medium text-[var(--color-text)]">{c.name}</p>
                    <p className="text-xs text-[var(--color-text-muted)]">{c.email}</p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {isOwner ? (
                    <select
                      value={c.permission}
                      onChange={(e) => handlePermissionChange(c, e.target.value as "view" | "edit")}
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
            {groupCollaborators.map((gc) => (
              <li
                key={gc.group_id}
                className="flex items-center justify-between rounded-md px-3 py-2 hover:bg-[var(--color-hover)]"
              >
                <div className="flex items-center gap-3">
                  <div className="flex h-8 w-8 items-center justify-center rounded-full bg-[var(--color-primary)]/10">
                    <Users className="h-4 w-4 text-[var(--color-primary)]" />
                  </div>
                  <div>
                    <p className="text-sm font-medium text-[var(--color-text)]">{gc.group_name}</p>
                    <p className="text-xs text-[var(--color-text-muted)]">Group</p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <span className="rounded bg-[var(--color-hover)] px-2 py-0.5 text-xs font-medium text-[var(--color-text-muted)]">
                    {gc.permission === "edit" ? "Editor" : "Viewer"}
                  </span>
                  {isOwner && (
                    <button
                      onClick={() => handleRemoveGroup(gc.group_id)}
                      className="rounded p-1 text-[var(--color-text-muted)] hover:bg-red-50 hover:text-red-600"
                      title="Remove group access"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </div>

        {isOwner && (
          <div className="mb-5 rounded-lg border border-[var(--color-border)] p-4">
            <h3 className="mb-2 flex items-center gap-2 text-sm font-medium text-[var(--color-text)]">
              {generalAccess === "restricted" ? <Lock className="h-4 w-4" /> : <Globe className="h-4 w-4" />}
              General access
            </h3>
            <select
              value={generalAccess}
              onChange={(e) => handleGeneralAccessChange(e.target.value as GeneralAccess)}
              className="w-full rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2 text-sm text-[var(--color-text)] outline-none"
            >
              <option value="restricted">Restricted</option>
              <option value="anyone_view">{scope} with the link can view</option>
              <option value="anyone_edit">{scope} with the link can edit</option>
            </select>
            <p className="mt-1 text-xs text-[var(--color-text-muted)]">{gaLabel[generalAccess]}</p>
          </div>
        )}

        {!isOwner && (
          <div className="mb-5 rounded-lg border border-[var(--color-border)] p-4">
            <p className="flex items-center gap-2 text-sm text-[var(--color-text-muted)]">
              {generalAccess === "restricted" ? <Lock className="h-4 w-4" /> : <Globe className="h-4 w-4" />}
              {gaLabel[generalAccess]}
            </p>
          </div>
        )}

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
