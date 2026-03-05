import { useCallback, useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router";
import {
  Clock,
  FileText,
  Folder,
  FolderPlus,
  MoreVertical,
  Plus,
  Trash2,
  Users,
  XCircle,
} from "lucide-react";
import { Navbar } from "../components/Layout/Navbar";
import { FolderBreadcrumbs } from "../components/Home/FolderBreadcrumbs";
import { CreateFolderDialog } from "../components/Home/CreateFolderDialog";
import { FolderInfoModal } from "../components/Home/FolderInfoModal";
import { FolderShareDialog } from "../components/Home/FolderShareDialog";
import { ShareDialog } from "../components/Editor/ShareDialog";
import { ConfirmDialog } from "../components/Home/ConfirmDialog";
import { ToastContainer } from "../components/Home/ToastContainer";
import { formatDateTime } from "../lib/dateUtils";
import {
  DocumentContextMenu,
  getEntityActions,
  getSharedDocActions,
  getTrashDocActions,
  getTrashFolderActions,
  type ContextMenuAction,
  type EntityPermissions,
} from "../components/Home/DocumentContextMenu";
import { DocumentInfoModal } from "../components/Home/DocumentInfoModal";
import { RenameDialog } from "../components/Home/RenameDialog";
import { useDocuments } from "../hooks/useDocuments";
import { useFolders } from "../hooks/useFolders";
import { useAuth } from "../hooks/useAuth";
import { useToast } from "../hooks/useToast";
import {
  documentsApi,
  foldersApi,
  sharingApi,
  type FolderItem,
  type MarkdownDocument,
  type SharedDocument,
  type SharedFolder,
  type RecentlyViewedDocument,
  type RecentlyViewedFolder,
} from "../lib/api";

function extractApiError(err: unknown, fallback: string): string {
  const detail = (err as { response?: { data?: { detail?: string } } })
    ?.response?.data?.detail;
  return detail || fallback;
}

type Tab = "browse" | "shared" | "recent" | "trash";

interface ContextMenuState {
  x: number;
  y: number;
  actions: ContextMenuAction[];
}

interface ConfirmState {
  title: string;
  message: string;
  confirmLabel: string;
  variant: "danger" | "default";
  onConfirm: () => void;
}

export function HomePage() {
  const {
    trash,
    trashLoading,
    deleteDocument,
    renameDocument,
    fetchTrash,
    restoreDocument,
    hardDeleteDocument,
  } = useDocuments();
  const {
    currentFolderId,
    currentFolderPermission,
    accessError,
    clearAccessError,
    folders,
    documents,
    breadcrumbs,
    trashFolders,
    loading,
    trashLoading: folderTrashLoading,
    navigateToFolder,
    createFolder,
    renameFolder,
    softDeleteFolder,
    restoreFolder,
    hardDeleteFolder,
    fetchTrashFolders,
    fetchContents,
  } = useFolders();
  const { user } = useAuth();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const { addToast } = useToast();
  const [tab, setTab] = useState<Tab>("browse");
  const [sharedDocs, setSharedDocs] = useState<SharedDocument[]>([]);
  const [sharedFolders, setSharedFolders] = useState<SharedFolder[]>([]);
  const [sharedLoading, setSharedLoading] = useState(false);
  const [recentDocs, setRecentDocs] = useState<RecentlyViewedDocument[]>([]);
  const [recentFolders, setRecentFolders] = useState<RecentlyViewedFolder[]>([]);
  const [recentLoading, setRecentLoading] = useState(false);

  const [contextMenu, setContextMenu] = useState<ContextMenuState | null>(null);
  const [infoDoc, setInfoDoc] = useState<MarkdownDocument | null>(null);
  const [infoFolder, setInfoFolder] = useState<FolderItem | null>(null);
  const [renameDoc, setRenameDoc] = useState<MarkdownDocument | null>(null);
  const [renameFolderItem, setRenameFolderItem] = useState<FolderItem | null>(null);
  const [showCreateFolder, setShowCreateFolder] = useState(false);
  const [shareDoc, setShareDoc] = useState<MarkdownDocument | null>(null);
  const [shareFolder, setShareFolder] = useState<FolderItem | null>(null);
  const [confirmState, setConfirmState] = useState<ConfirmState | null>(null);

  const requestConfirm = useCallback(
    (state: ConfirmState) => setConfirmState(state),
    [],
  );
  const closeConfirm = useCallback(() => setConfirmState(null), []);

  useEffect(() => {
    document.title = "Home - CollabMark";
    return () => {
      document.title = "CollabMark";
    };
  }, []);

  useEffect(() => {
    const folderParam = searchParams.get("folder");
    navigateToFolder(folderParam || null);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      if (currentFolderId) {
        next.set("folder", currentFolderId);
      } else {
        next.delete("folder");
      }
      return next;
    }, { replace: true });
  }, [currentFolderId, setSearchParams]);

  useEffect(() => {
    if (accessError) {
      addToast(accessError, "error");
      clearAccessError();
      navigateToFolder(null);
    }
  }, [accessError, addToast, clearAccessError, navigateToFolder]);

  useEffect(() => {
    if (tab === "shared") {
      setSharedLoading(true);
      Promise.all([
        sharingApi.listShared(),
        foldersApi.listShared(),
      ]).then(([docsRes, foldersRes]) => {
        setSharedDocs(docsRes.data);
        setSharedFolders(foldersRes.data);
        setSharedLoading(false);
      });
    } else if (tab === "recent") {
      setRecentLoading(true);
      Promise.all([
        sharingApi.listRecentlyViewed(),
        foldersApi.listRecentlyViewed(),
      ]).then(([docsRes, foldersRes]) => {
        setRecentDocs(docsRes.data);
        setRecentFolders(foldersRes.data);
        setRecentLoading(false);
      });
    } else if (tab === "trash") {
      fetchTrash();
      fetchTrashFolders();
    }
  }, [tab, fetchTrash, fetchTrashFolders]);

  const handleCreateDoc = async () => {
    try {
      const { data } = await documentsApi.create({
        title: "Untitled",
        folder_id: currentFolderId,
      });
      addToast("Document created", "success");
      navigate(`/edit/${data.id}`);
    } catch (err) {
      addToast(extractApiError(err, "Failed to create document. Please try again."), "error");
    }
  };

  const handleCreateFolder = async (name: string) => {
    try {
      await createFolder(name);
      addToast("Folder created", "success");
    } catch (err) {
      addToast(extractApiError(err, "Failed to create folder. Please try again."), "error");
    }
  };

  const closeContextMenu = useCallback(() => setContextMenu(null), []);

  const getPermsForEntity = useCallback(
    (entityOwnerId: string): EntityPermissions => {
      const isOwner = user?.id === entityOwnerId;
      if (isOwner) {
        return { can_view: true, can_edit: true, can_delete: true, can_share: true };
      }
      const isEditor = currentFolderPermission === "edit";
      return {
        can_view: true,
        can_edit: isEditor,
        can_delete: false,
        can_share: false,
      };
    },
    [user?.id, currentFolderPermission],
  );

  const buildFolderActions = useCallback(
    (folder: FolderItem) => {
      const perms = getPermsForEntity(folder.owner_id);
      return getEntityActions("folder", perms, {
        onOpen: () => navigateToFolder(folder.id),
        onShare: () => setShareFolder(folder),
        onRename: () => setRenameFolderItem(folder),
        onTrash: () =>
          requestConfirm({
            title: "Move to Trash",
            message: `Move folder "${folder.name}" and all its contents to trash?`,
            confirmLabel: "Move to Trash",
            variant: "danger",
            onConfirm: async () => {
              closeConfirm();
              try {
                await softDeleteFolder(folder.id);
                addToast("Folder moved to trash", "success");
              } catch (err) {
                addToast(extractApiError(err, "Failed to delete folder."), "error");
              }
            },
          }),
        onInfo: () => setInfoFolder(folder),
      });
    },
    [getPermsForEntity, navigateToFolder, softDeleteFolder, requestConfirm, closeConfirm, addToast],
  );

  const buildOwnedDocActions = useCallback(
    (doc: MarkdownDocument) => {
      const perms = getPermsForEntity(doc.owner_id);
      return getEntityActions("document", perms, {
        onOpen: () => window.open(`/edit/${doc.id}`, "_blank"),
        onShare: () => setShareDoc(doc),
        onRename: () => setRenameDoc(doc),
        onTrash: () =>
          requestConfirm({
            title: "Move to Trash",
            message: `Move "${doc.title}" to trash?`,
            confirmLabel: "Move to Trash",
            variant: "danger",
            onConfirm: async () => {
              closeConfirm();
              try {
                await deleteDocument(doc.id);
                await fetchContents(currentFolderId);
                addToast("Document moved to trash", "success");
              } catch (err) {
                addToast(extractApiError(err, "Failed to delete document."), "error");
              }
            },
          }),
        onInfo: () => setInfoDoc(doc),
      });
    },
    [getPermsForEntity, deleteDocument, fetchContents, currentFolderId, requestConfirm, closeConfirm, addToast],
  );

  const toMarkdownDoc = useCallback(
    (doc: SharedDocument | RecentlyViewedDocument): MarkdownDocument => ({
      id: doc.id,
      title: doc.title,
      content: "",
      owner_id: doc.owner_id,
      owner_name: "owner_name" in doc ? doc.owner_name : "",
      owner_email: "owner_email" in doc ? doc.owner_email : "",
      owner_avatar_url: null,
      folder_id: null,
      general_access: "restricted",
      is_deleted: false,
      deleted_at: null,
      content_length: 0,
      created_at: doc.created_at,
      updated_at: doc.updated_at,
    }),
    [],
  );

  const buildSharedDocActions = useCallback(
    (doc: SharedDocument | RecentlyViewedDocument) =>
      getSharedDocActions({
        onOpen: () => window.open(`/edit/${doc.id}`, "_blank"),
        onInfo: () => setInfoDoc(toMarkdownDoc(doc)),
      }),
    [toMarkdownDoc],
  );

  const handleSharedContextMenu = useCallback(
    (e: React.MouseEvent, doc: SharedDocument | RecentlyViewedDocument) => {
      setContextMenu({
        x: e.clientX,
        y: e.clientY,
        actions: buildSharedDocActions(doc),
      });
    },
    [buildSharedDocActions],
  );

  const toFolderItem = useCallback(
    (f: SharedFolder | RecentlyViewedFolder): FolderItem => ({
      id: f.id,
      name: f.name,
      owner_id: f.owner_id,
      owner_name: f.owner_name,
      owner_email: f.owner_email,
      owner_avatar_url: null,
      parent_id: null,
      general_access: "restricted",
      is_deleted: false,
      deleted_at: null,
      created_at: f.created_at,
      updated_at: f.updated_at,
    }),
    [],
  );

  const buildSharedFolderActions = useCallback(
    (f: SharedFolder | RecentlyViewedFolder) =>
      getSharedDocActions({
        onOpen: () => {
          setTab("browse");
          navigateToFolder(f.id);
        },
        onInfo: () => setInfoFolder(toFolderItem(f)),
      }),
    [navigateToFolder, toFolderItem],
  );

  const handleSharedFolderContextMenu = useCallback(
    (e: React.MouseEvent, f: SharedFolder | RecentlyViewedFolder) => {
      e.preventDefault();
      setContextMenu({
        x: e.clientX,
        y: e.clientY,
        actions: buildSharedFolderActions(f),
      });
    },
    [buildSharedFolderActions],
  );

  const buildTrashDocActions = useCallback(
    (doc: MarkdownDocument) =>
      getTrashDocActions({
        onRestore: async () => {
          try {
            await restoreDocument(doc.id);
            addToast("Document restored", "success");
          } catch (err) {
            addToast(extractApiError(err, "Failed to restore document."), "error");
          }
        },
        onDeletePermanently: () =>
          requestConfirm({
            title: "Delete Permanently",
            message: `Permanently delete "${doc.title}"? This cannot be undone.`,
            confirmLabel: "Delete Permanently",
            variant: "danger",
            onConfirm: async () => {
              closeConfirm();
              try {
                await hardDeleteDocument(doc.id);
                addToast("Document deleted permanently", "success");
              } catch (err) {
                addToast(extractApiError(err, "Failed to delete document."), "error");
              }
            },
          }),
        onInfo: () => setInfoDoc(doc),
      }),
    [restoreDocument, hardDeleteDocument, requestConfirm, closeConfirm, addToast],
  );

  const handleTrashDocContextMenu = useCallback(
    (e: React.MouseEvent, doc: MarkdownDocument) => {
      setContextMenu({
        x: e.clientX,
        y: e.clientY,
        actions: buildTrashDocActions(doc),
      });
    },
    [buildTrashDocActions],
  );

  const buildTrashFolderActions = useCallback(
    (folder: FolderItem) =>
      getTrashFolderActions({
        onRestore: async () => {
          try {
            await restoreFolder(folder.id);
            addToast("Folder restored", "success");
          } catch (err) {
            addToast(extractApiError(err, "Failed to restore folder."), "error");
          }
        },
        onDeletePermanently: () =>
          requestConfirm({
            title: "Delete Permanently",
            message: `Permanently delete folder "${folder.name}" and all its contents? This cannot be undone.`,
            confirmLabel: "Delete Permanently",
            variant: "danger",
            onConfirm: async () => {
              closeConfirm();
              try {
                await hardDeleteFolder(folder.id);
                addToast("Folder deleted permanently", "success");
              } catch (err) {
                addToast(extractApiError(err, "Failed to delete folder."), "error");
              }
            },
          }),
        onInfo: () => setInfoFolder(folder),
      }),
    [restoreFolder, hardDeleteFolder, requestConfirm, closeConfirm, addToast],
  );

  const handleTrashFolderContextMenu = useCallback(
    (e: React.MouseEvent, folder: FolderItem) => {
      e.preventDefault();
      setContextMenu({
        x: e.clientX,
        y: e.clientY,
        actions: buildTrashFolderActions(folder),
      });
    },
    [buildTrashFolderActions],
  );

  const openMenuFromButton = useCallback(
    (e: React.MouseEvent<HTMLButtonElement>, actions: ContextMenuAction[]) => {
      e.stopPropagation();
      const rect = e.currentTarget.getBoundingClientRect();
      setContextMenu({ x: rect.right, y: rect.bottom, actions });
    },
    [],
  );

  const handleEmptyTrash = () => {
    requestConfirm({
      title: "Empty Trash",
      message:
        "Permanently delete all items in trash? This cannot be undone.",
      confirmLabel: "Empty Trash",
      variant: "danger",
      onConfirm: async () => {
        closeConfirm();
        try {
          for (const doc of trash) {
            await hardDeleteDocument(doc.id);
          }
          for (const folder of trashFolders) {
            await hardDeleteFolder(folder.id);
          }
          addToast("Trash emptied", "success");
        } catch (err) {
          addToast(extractApiError(err, "Failed to empty trash."), "error");
        }
      },
    });
  };

  const tabBtn = (t: Tab, label: React.ReactNode) => (
    <button
      onClick={() => setTab(t)}
      className={`flex-shrink-0 flex-1 rounded-md px-4 py-2 text-sm font-medium transition ${
        tab === t
          ? "bg-[var(--color-primary)] text-white"
          : "text-[var(--color-text-muted)] hover:bg-gray-50"
      }`}
    >
      {label}
    </button>
  );

  const Spinner = () => (
    <div className="flex justify-center py-20">
      <div className="h-8 w-8 animate-spin rounded-full border-2 border-[var(--color-primary)] border-t-transparent" />
    </div>
  );

  return (
    <div className="min-h-screen bg-[var(--color-bg-secondary)]">
      <Navbar />
      <main className="mx-auto max-w-4xl px-3 py-4 md:px-6 md:py-8">
        <div className="mb-6 flex flex-nowrap gap-1 overflow-x-auto rounded-lg border border-[var(--color-border)] bg-white p-1">
          {tabBtn(
            "browse",
            <span className="inline-flex items-center gap-1">
              <Folder className="h-4 w-4" />
              Files
            </span>,
          )}
          {tabBtn(
            "shared",
            <span className="inline-flex items-center gap-1">
              <Users className="h-4 w-4" />
              Shared with me
            </span>,
          )}
          {tabBtn(
            "recent",
            <span className="inline-flex items-center gap-1">
              <Clock className="h-4 w-4" />
              Recently viewed
            </span>,
          )}
          {tabBtn(
            "trash",
            <span className="inline-flex items-center gap-1">
              <Trash2 className="h-4 w-4" />
              Trash
            </span>,
          )}
        </div>

        {/* ========== BROWSE (File Browser) ========== */}
        {tab === "browse" && (
          <>
            <FolderBreadcrumbs
              breadcrumbs={breadcrumbs}
              onNavigate={navigateToFolder}
            />
            <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <h2 className="text-xl font-semibold">
                {breadcrumbs.length > 0
                  ? breadcrumbs[breadcrumbs.length - 1].name
                  : "My Files"}
              </h2>
              {currentFolderPermission === "edit" && (
                <div className="flex gap-2">
                  <button
                    onClick={() => setShowCreateFolder(true)}
                    className="inline-flex items-center gap-2 rounded-lg border border-[var(--color-border)] px-4 py-2 text-sm font-medium transition hover:bg-gray-50"
                  >
                    <FolderPlus className="h-4 w-4" />
                    <span className="hidden sm:inline">New Folder</span>
                  </button>
                  <button
                    onClick={handleCreateDoc}
                    className="inline-flex items-center gap-2 rounded-lg bg-[var(--color-primary)] px-4 py-2 text-sm font-medium text-white transition hover:bg-[var(--color-primary-hover)]"
                  >
                    <Plus className="h-4 w-4" />
                    <span className="hidden sm:inline">New Document</span>
                  </button>
                </div>
              )}
            </div>

            {loading ? (
              <Spinner />
            ) : folders.length === 0 && documents.length === 0 ? (
              <div className="rounded-lg border border-dashed border-[var(--color-border)] p-12 text-center">
                <Folder className="mx-auto mb-3 h-10 w-10 text-[var(--color-text-muted)]" />
                <p className="text-[var(--color-text-muted)]">
                  {currentFolderPermission === "view"
                    ? "This folder is empty."
                    : "This folder is empty. Create a folder or document to get started!"}
                </p>
              </div>
            ) : (
              <div className="space-y-2">
                {folders.map((folder) => {
                  const actions = buildFolderActions(folder);
                  return (
                    <div
                      key={folder.id}
                      className="group flex items-center justify-between rounded-lg border border-[var(--color-border)] p-4 transition hover:bg-[var(--color-bg-secondary)] cursor-pointer"
                      onClick={() => navigateToFolder(folder.id)}
                      onContextMenu={(e) => {
                        e.preventDefault();
                        setContextMenu({ x: e.clientX, y: e.clientY, actions });
                      }}
                    >
                      <div className="flex items-center gap-3">
                        <Folder className="h-5 w-5 flex-shrink-0 text-amber-500" />
                        <div>
                          <p className="font-medium">{folder.name}</p>
                          <p className="text-xs text-[var(--color-text-muted)]">
                            Updated {formatDateTime(folder.updated_at)}
                          </p>
                        </div>
                      </div>
                      <button
                        onClick={(e) => openMenuFromButton(e, actions)}
                        className="rounded p-1 text-[var(--color-text-muted)] transition hover:bg-[var(--color-hover)] sm:invisible sm:group-hover:visible"
                        aria-label="More actions"
                      >
                        <MoreVertical className="h-4 w-4" />
                      </button>
                    </div>
                  );
                })}
                {documents.map((doc) => {
                  const actions = buildOwnedDocActions(doc);
                  return (
                    <div
                      key={doc.id}
                      className="group flex items-center justify-between rounded-lg border border-[var(--color-border)] p-4 transition hover:bg-[var(--color-bg-secondary)] cursor-pointer"
                      onClick={() => navigate(`/edit/${doc.id}`)}
                      onContextMenu={(e) => {
                        e.preventDefault();
                        setContextMenu({ x: e.clientX, y: e.clientY, actions });
                      }}
                    >
                      <div className="flex items-center gap-3">
                        <FileText className="h-5 w-5 flex-shrink-0 text-[var(--color-primary)]" />
                        <div>
                          <p className="font-medium">{doc.title}</p>
                          <p className="text-xs text-[var(--color-text-muted)]">
                            Updated {formatDateTime(doc.updated_at)}
                          </p>
                        </div>
                      </div>
                      <button
                        onClick={(e) => openMenuFromButton(e, actions)}
                        className="rounded p-1 text-[var(--color-text-muted)] transition hover:bg-[var(--color-hover)] sm:invisible sm:group-hover:visible"
                        aria-label="More actions"
                      >
                        <MoreVertical className="h-4 w-4" />
                      </button>
                    </div>
                  );
                })}
              </div>
            )}
          </>
        )}

        {/* ========== SHARED ========== */}
        {tab === "shared" && (
          <>
            {sharedLoading ? (
              <Spinner />
            ) : sharedDocs.length === 0 && sharedFolders.length === 0 ? (
              <div className="rounded-lg border border-dashed border-[var(--color-border)] p-12 text-center">
                <Users className="mx-auto mb-3 h-10 w-10 text-[var(--color-text-muted)]" />
                <p className="text-[var(--color-text-muted)]">
                  No items shared with you yet.
                </p>
              </div>
            ) : (
              <div className="space-y-2">
                {sharedFolders.map((f) => (
                  <div
                    key={`folder-${f.id}`}
                    className="group flex items-center justify-between rounded-lg border border-[var(--color-border)] p-4 transition hover:bg-[var(--color-bg-secondary)] cursor-pointer"
                    onClick={() => {
                      setTab("browse");
                      navigateToFolder(f.id);
                    }}
                    onContextMenu={(e) => handleSharedFolderContextMenu(e, f)}
                  >
                    <div className="flex items-center gap-3">
                      <Folder className="h-5 w-5 flex-shrink-0 text-amber-500" />
                      <div>
                        <p className="font-medium">{f.name}</p>
                        <p className="text-xs text-[var(--color-text-muted)]">
                          by {f.owner_name} · {f.permission} access · Shared{" "}
                          {formatDateTime(f.last_accessed_at)}
                        </p>
                      </div>
                    </div>
                    <button
                      onClick={(e) => openMenuFromButton(e, buildSharedFolderActions(f))}
                      className="rounded p-1 text-[var(--color-text-muted)] transition hover:bg-[var(--color-hover)] sm:invisible sm:group-hover:visible"
                      aria-label="More actions"
                    >
                      <MoreVertical className="h-4 w-4" />
                    </button>
                  </div>
                ))}
                {sharedDocs.map((doc) => (
                  <div
                    key={doc.id}
                    className="group flex items-center justify-between rounded-lg border border-[var(--color-border)] p-4 transition hover:bg-[var(--color-bg-secondary)] cursor-pointer"
                    onClick={() => navigate(`/edit/${doc.id}`)}
                    onContextMenu={(e) => {
                      e.preventDefault();
                      handleSharedContextMenu(e, doc);
                    }}
                  >
                    <div className="flex items-center gap-3">
                      <FileText className="h-5 w-5 flex-shrink-0 text-[var(--color-primary)]" />
                      <div>
                        <p className="font-medium">{doc.title}</p>
                        <p className="text-xs text-[var(--color-text-muted)]">
                          {doc.permission} access | Last accessed{" "}
                          {formatDateTime(doc.last_accessed_at)}
                        </p>
                      </div>
                    </div>
                    <button
                      onClick={(e) => openMenuFromButton(e, buildSharedDocActions(doc))}
                      className="rounded p-1 text-[var(--color-text-muted)] transition hover:bg-[var(--color-hover)] sm:invisible sm:group-hover:visible"
                      aria-label="More actions"
                    >
                      <MoreVertical className="h-4 w-4" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </>
        )}

        {/* ========== RECENT ========== */}
        {tab === "recent" && (
          <>
            {recentLoading ? (
              <Spinner />
            ) : recentDocs.length === 0 && recentFolders.length === 0 ? (
              <div className="rounded-lg border border-dashed border-[var(--color-border)] p-12 text-center">
                <Clock className="mx-auto mb-3 h-10 w-10 text-[var(--color-text-muted)]" />
                <p className="text-[var(--color-text-muted)]">
                  No recently viewed items yet.
                </p>
              </div>
            ) : (
              <div className="space-y-2">
                {recentFolders.map((f) => (
                  <div
                    key={`folder-${f.id}`}
                    className="group flex items-center justify-between rounded-lg border border-[var(--color-border)] p-4 transition hover:bg-[var(--color-bg-secondary)] cursor-pointer"
                    onClick={() => {
                      setTab("browse");
                      navigateToFolder(f.id);
                    }}
                    onContextMenu={(e) => handleSharedFolderContextMenu(e, f)}
                  >
                    <div className="flex items-center gap-3">
                      <Folder className="h-5 w-5 flex-shrink-0 text-amber-500" />
                      <div>
                        <p className="font-medium">{f.name}</p>
                        <p className="text-xs text-[var(--color-text-muted)]">
                          by {f.owner_name} · {f.permission} access · Viewed{" "}
                          {formatDateTime(f.viewed_at)}
                        </p>
                      </div>
                    </div>
                    <button
                      onClick={(e) => openMenuFromButton(e, buildSharedFolderActions(f))}
                      className="rounded p-1 text-[var(--color-text-muted)] transition hover:bg-[var(--color-hover)] sm:invisible sm:group-hover:visible"
                      aria-label="More actions"
                    >
                      <MoreVertical className="h-4 w-4" />
                    </button>
                  </div>
                ))}
                {recentDocs.map((doc) => (
                  <div
                    key={doc.id}
                    className="group flex items-center justify-between rounded-lg border border-[var(--color-border)] p-4 transition hover:bg-[var(--color-bg-secondary)] cursor-pointer"
                    onClick={() => navigate(`/edit/${doc.id}`)}
                    onContextMenu={(e) => {
                      e.preventDefault();
                      handleSharedContextMenu(e, doc);
                    }}
                  >
                    <div className="flex items-center gap-3">
                      <FileText className="h-5 w-5 flex-shrink-0 text-[var(--color-primary)]" />
                      <div>
                        <p className="font-medium">{doc.title}</p>
                        <p className="text-xs text-[var(--color-text-muted)]">
                          by {doc.owner_name} · {doc.permission} access · Viewed{" "}
                          {formatDateTime(doc.viewed_at)}
                        </p>
                      </div>
                    </div>
                    <button
                      onClick={(e) => openMenuFromButton(e, buildSharedDocActions(doc))}
                      className="rounded p-1 text-[var(--color-text-muted)] transition hover:bg-[var(--color-hover)] sm:invisible sm:group-hover:visible"
                      aria-label="More actions"
                    >
                      <MoreVertical className="h-4 w-4" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </>
        )}

        {/* ========== TRASH ========== */}
        {tab === "trash" && (
          <>
            <div className="mb-6 flex justify-end">
              {(trash.length > 0 || trashFolders.length > 0) && (
                <button
                  onClick={handleEmptyTrash}
                  className="inline-flex items-center gap-2 rounded-lg border border-red-300 px-4 py-2 text-sm font-medium text-red-600 transition hover:bg-red-50 dark:border-red-700 dark:text-red-400 dark:hover:bg-red-900/20"
                >
                  <XCircle className="h-4 w-4" />
                  <span className="hidden sm:inline">Empty Trash</span>
                </button>
              )}
            </div>
            {trashLoading || folderTrashLoading ? (
              <Spinner />
            ) : trash.length === 0 && trashFolders.length === 0 ? (
              <div className="rounded-lg border border-dashed border-[var(--color-border)] p-12 text-center">
                <Trash2 className="mx-auto mb-3 h-10 w-10 text-[var(--color-text-muted)]" />
                <p className="text-[var(--color-text-muted)]">Trash is empty.</p>
              </div>
            ) : (
              <div className="space-y-2">
                {trashFolders.map((folder) => (
                  <div
                    key={`folder-${folder.id}`}
                    className="group flex items-center justify-between rounded-lg border border-[var(--color-border)] p-4 transition hover:bg-[var(--color-bg-secondary)]"
                    onContextMenu={(e) => handleTrashFolderContextMenu(e, folder)}
                  >
                    <div className="flex items-center gap-3">
                      <Folder className="h-5 w-5 flex-shrink-0 text-[var(--color-text-muted)]" />
                      <div>
                        <p className="font-medium text-[var(--color-text)]">
                          {folder.name}
                        </p>
                        <p className="text-xs text-[var(--color-text-muted)]">
                          Folder · Deleted{" "}
                          {folder.deleted_at
                            ? formatDateTime(folder.deleted_at)
                            : "recently"}
                        </p>
                      </div>
                    </div>
                    <button
                      onClick={(e) => openMenuFromButton(e, buildTrashFolderActions(folder))}
                      className="rounded p-1 text-[var(--color-text-muted)] transition hover:bg-[var(--color-hover)] sm:invisible sm:group-hover:visible"
                      aria-label="More actions"
                    >
                      <MoreVertical className="h-4 w-4" />
                    </button>
                  </div>
                ))}
                {trash.map((doc) => (
                  <div
                    key={doc.id}
                    className="group flex items-center justify-between rounded-lg border border-[var(--color-border)] p-4 transition hover:bg-[var(--color-bg-secondary)]"
                    onContextMenu={(e) => {
                      e.preventDefault();
                      handleTrashDocContextMenu(e, doc);
                    }}
                  >
                    <div className="flex items-center gap-3">
                      <FileText className="h-5 w-5 flex-shrink-0 text-[var(--color-text-muted)]" />
                      <div>
                        <p className="font-medium text-[var(--color-text)]">
                          {doc.title}
                        </p>
                        <p className="text-xs text-[var(--color-text-muted)]">
                          Document · Deleted{" "}
                          {doc.deleted_at
                            ? formatDateTime(doc.deleted_at)
                            : "recently"}
                        </p>
                      </div>
                    </div>
                    <button
                      onClick={(e) => openMenuFromButton(e, buildTrashDocActions(doc))}
                      className="rounded p-1 text-[var(--color-text-muted)] transition hover:bg-[var(--color-hover)] sm:invisible sm:group-hover:visible"
                      aria-label="More actions"
                    >
                      <MoreVertical className="h-4 w-4" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </>
        )}
      </main>

      {contextMenu && (
        <DocumentContextMenu
          x={contextMenu.x}
          y={contextMenu.y}
          actions={contextMenu.actions}
          onClose={closeContextMenu}
        />
      )}

      <ConfirmDialog
        open={confirmState !== null}
        title={confirmState?.title ?? ""}
        message={confirmState?.message ?? ""}
        confirmLabel={confirmState?.confirmLabel}
        variant={confirmState?.variant}
        onConfirm={confirmState?.onConfirm ?? closeConfirm}
        onCancel={closeConfirm}
      />

      <DocumentInfoModal
        doc={infoDoc!}
        open={infoDoc !== null}
        onClose={() => setInfoDoc(null)}
      />

      <FolderInfoModal
        folder={infoFolder!}
        open={infoFolder !== null}
        onClose={() => setInfoFolder(null)}
      />

      {renameDoc && (
        <RenameDialog
          currentTitle={renameDoc.title}
          open
          onClose={() => setRenameDoc(null)}
          onSave={async (newTitle) => {
            try {
              await renameDocument(renameDoc.id, newTitle);
              await fetchContents(currentFolderId);
              addToast("Renamed successfully", "success");
            } catch (err) {
              addToast(extractApiError(err, "Failed to rename."), "error");
            }
          }}
        />
      )}

      {renameFolderItem && (
        <RenameDialog
          currentTitle={renameFolderItem.name}
          open
          onClose={() => setRenameFolderItem(null)}
          onSave={async (newName) => {
            try {
              await renameFolder(renameFolderItem.id, newName);
              addToast("Renamed successfully", "success");
            } catch (err) {
              addToast(extractApiError(err, "Failed to rename."), "error");
            }
          }}
        />
      )}

      <CreateFolderDialog
        open={showCreateFolder}
        onClose={() => setShowCreateFolder(false)}
        onCreate={handleCreateFolder}
      />

      {shareDoc && (
        <ShareDialog
          docId={shareDoc.id}
          open
          onClose={() => setShareDoc(null)}
          isOwner={shareDoc.owner_id === user?.id}
          generalAccess={shareDoc.general_access as "restricted" | "anyone_view" | "anyone_edit"}
          ownerEmail={shareDoc.owner_email}
          ownerName={shareDoc.owner_name}
          ownerAvatarUrl={shareDoc.owner_avatar_url}
          onGeneralAccessChange={(ga) =>
            setShareDoc((prev) => (prev ? { ...prev, general_access: ga } : prev))
          }
        />
      )}

      {shareFolder && (
        <FolderShareDialog
          folderId={shareFolder.id}
          open
          onClose={() => setShareFolder(null)}
          isOwner={shareFolder.owner_id === user?.id}
          generalAccess={shareFolder.general_access as "restricted" | "anyone_view" | "anyone_edit"}
          ownerEmail={shareFolder.owner_email}
          ownerName={shareFolder.owner_name}
          ownerAvatarUrl={shareFolder.owner_avatar_url}
          onGeneralAccessChange={(ga) =>
            setShareFolder((prev) => (prev ? { ...prev, general_access: ga } : prev))
          }
        />
      )}

      <ToastContainer />
    </div>
  );
}
