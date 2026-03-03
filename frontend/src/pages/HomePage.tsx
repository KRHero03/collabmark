import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router";
import {
  Clock,
  FileText,
  RotateCcw,
  Trash2,
  Users,
  XCircle,
} from "lucide-react";
import { Navbar } from "../components/Layout/Navbar";
import { DocumentList } from "../components/Home/DocumentList";
import { formatDateTime } from "../lib/dateUtils";
import {
  DocumentContextMenu,
  getOwnedDocActions,
  getSharedDocActions,
  getTrashDocActions,
  type ContextMenuAction,
} from "../components/Home/DocumentContextMenu";
import { DocumentInfoModal } from "../components/Home/DocumentInfoModal";
import { RenameDialog } from "../components/Home/RenameDialog";
import { useDocuments } from "../hooks/useDocuments";
import { useAuth } from "../hooks/useAuth";
import {
  sharingApi,
  type MarkdownDocument,
  type SharedDocument,
  type RecentlyViewedDocument,
} from "../lib/api";

type Tab = "mine" | "shared" | "recent" | "trash";

interface ContextMenuState {
  x: number;
  y: number;
  actions: ContextMenuAction[];
}

export function HomePage() {
  const {
    documents,
    trash,
    loading,
    trashLoading,
    fetchDocuments,
    createDocument,
    deleteDocument,
    renameDocument,
    fetchTrash,
    restoreDocument,
    hardDeleteDocument,
  } = useDocuments();
  const { user } = useAuth();
  const navigate = useNavigate();
  const [tab, setTab] = useState<Tab>("mine");
  const [sharedDocs, setSharedDocs] = useState<SharedDocument[]>([]);
  const [sharedLoading, setSharedLoading] = useState(false);
  const [recentDocs, setRecentDocs] = useState<RecentlyViewedDocument[]>([]);
  const [recentLoading, setRecentLoading] = useState(false);

  const [contextMenu, setContextMenu] = useState<ContextMenuState | null>(
    null,
  );
  const [infoDoc, setInfoDoc] = useState<MarkdownDocument | null>(null);
  const [renameDoc, setRenameDoc] = useState<MarkdownDocument | null>(null);

  useEffect(() => {
    document.title = "Home - CollabMark";
    return () => {
      document.title = "CollabMark";
    };
  }, []);

  useEffect(() => {
    fetchDocuments();
  }, [fetchDocuments]);

  useEffect(() => {
    if (tab === "shared") {
      setSharedLoading(true);
      sharingApi.listShared().then(({ data }) => {
        setSharedDocs(data);
        setSharedLoading(false);
      });
    } else if (tab === "recent") {
      setRecentLoading(true);
      sharingApi.listRecentlyViewed().then(({ data }) => {
        setRecentDocs(data);
        setRecentLoading(false);
      });
    } else if (tab === "trash") {
      fetchTrash();
    }
  }, [tab, fetchTrash]);

  const handleCreate = async () => {
    const doc = await createDocument();
    navigate(`/edit/${doc.id}`);
  };

  const closeContextMenu = useCallback(() => setContextMenu(null), []);

  const handleOwnedContextMenu = useCallback(
    (e: React.MouseEvent, doc: MarkdownDocument) => {
      setContextMenu({
        x: e.clientX,
        y: e.clientY,
        actions: getOwnedDocActions({
          onOpen: () => window.open(`/edit/${doc.id}`, "_blank"),
          onRename: () => setRenameDoc(doc),
          onTrash: () => deleteDocument(doc.id),
          onInfo: () => setInfoDoc(doc),
        }),
      });
    },
    [navigate, deleteDocument],
  );

  const handleSharedContextMenu = useCallback(
    (e: React.MouseEvent, doc: SharedDocument | RecentlyViewedDocument) => {
      const asMarkdown: MarkdownDocument = {
        id: doc.id,
        title: doc.title,
        content: "",
        owner_id: doc.owner_id,
        owner_name: "owner_name" in doc ? doc.owner_name : "",
        owner_email: "owner_email" in doc ? doc.owner_email : "",
        general_access: "restricted",
        is_deleted: false,
        deleted_at: null,
        content_length: 0,
        created_at: doc.created_at,
        updated_at: doc.updated_at,
      };
      setContextMenu({
        x: e.clientX,
        y: e.clientY,
        actions: getSharedDocActions({
          onOpen: () => window.open(`/edit/${doc.id}`, "_blank"),
          onInfo: () => setInfoDoc(asMarkdown),
        }),
      });
    },
    [navigate],
  );

  const handleTrashContextMenu = useCallback(
    (e: React.MouseEvent, doc: MarkdownDocument) => {
      setContextMenu({
        x: e.clientX,
        y: e.clientY,
        actions: getTrashDocActions({
          onRestore: () => restoreDocument(doc.id),
          onDeletePermanently: () => hardDeleteDocument(doc.id),
          onInfo: () => setInfoDoc(doc),
        }),
      });
    },
    [restoreDocument, hardDeleteDocument],
  );

  const handleEmptyTrash = async () => {
    const ids = trash.map((d) => d.id);
    for (const id of ids) {
      await hardDeleteDocument(id);
    }
  };

  const tabBtn = (t: Tab, label: React.ReactNode) => (
    <button
      onClick={() => setTab(t)}
      className={`flex-1 rounded-md px-4 py-2 text-sm font-medium transition ${
        tab === t
          ? "bg-[var(--color-primary)] text-white"
          : "text-[var(--color-text-muted)] hover:bg-gray-50"
      }`}
    >
      {label}
    </button>
  );

  return (
    <div className="min-h-screen bg-[var(--color-bg-secondary)]">
      <Navbar />
      <main className="mx-auto max-w-4xl px-6 py-8">
        <div className="mb-6 flex gap-1 rounded-lg border border-[var(--color-border)] bg-white p-1">
          {tabBtn("mine", "My Documents")}
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

        {tab === "mine" && (
          <>
            {loading ? (
              <div className="flex justify-center py-20">
                <div className="h-8 w-8 animate-spin rounded-full border-2 border-[var(--color-primary)] border-t-transparent" />
              </div>
            ) : (
              <DocumentList
                documents={documents}
                onCreate={handleCreate}
                onDelete={deleteDocument}
                onContextMenu={handleOwnedContextMenu}
              />
            )}
          </>
        )}

        {tab === "shared" && (
          <>
            {sharedLoading ? (
              <div className="flex justify-center py-20">
                <div className="h-8 w-8 animate-spin rounded-full border-2 border-[var(--color-primary)] border-t-transparent" />
              </div>
            ) : sharedDocs.length === 0 ? (
              <div className="rounded-lg border border-dashed border-[var(--color-border)] p-12 text-center">
                <Users className="mx-auto mb-3 h-10 w-10 text-[var(--color-text-muted)]" />
                <p className="text-[var(--color-text-muted)]">
                  No documents shared with you yet.
                </p>
              </div>
            ) : (
              <div className="space-y-2">
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
                      <FileText className="h-5 w-5 text-[var(--color-primary)]" />
                      <div>
                        <p className="font-medium">{doc.title}</p>
                        <p className="text-xs text-[var(--color-text-muted)]">
                          {doc.permission} access | Last accessed{" "}
                          {formatDateTime(doc.last_accessed_at)}
                        </p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </>
        )}

        {tab === "recent" && (
          <>
            {recentLoading ? (
              <div className="flex justify-center py-20">
                <div className="h-8 w-8 animate-spin rounded-full border-2 border-[var(--color-primary)] border-t-transparent" />
              </div>
            ) : recentDocs.length === 0 ? (
              <div className="rounded-lg border border-dashed border-[var(--color-border)] p-12 text-center">
                <Clock className="mx-auto mb-3 h-10 w-10 text-[var(--color-text-muted)]" />
                <p className="text-[var(--color-text-muted)]">
                  No recently viewed documents yet.
                </p>
              </div>
            ) : (
              <div className="space-y-2">
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
                      <FileText className="h-5 w-5 text-[var(--color-primary)]" />
                      <div>
                        <p className="font-medium">{doc.title}</p>
                        <p className="text-xs text-[var(--color-text-muted)]">
                          by {doc.owner_name} · {doc.permission} access · Viewed{" "}
                          {formatDateTime(doc.viewed_at)}
                        </p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </>
        )}

        {tab === "trash" && (
          <>
            <div className="mb-6 flex items-center justify-between">
              <h2 className="text-xl font-semibold">Trash</h2>
              {trash.length > 0 && (
                <button
                  onClick={handleEmptyTrash}
                  className="inline-flex items-center gap-2 rounded-lg border border-red-300 px-4 py-2 text-sm font-medium text-red-600 transition hover:bg-red-50 dark:border-red-700 dark:text-red-400 dark:hover:bg-red-900/20"
                >
                  <XCircle className="h-4 w-4" />
                  Empty Trash
                </button>
              )}
            </div>
            {trashLoading ? (
              <div className="flex justify-center py-20">
                <div className="h-8 w-8 animate-spin rounded-full border-2 border-[var(--color-primary)] border-t-transparent" />
              </div>
            ) : trash.length === 0 ? (
              <div className="rounded-lg border border-dashed border-[var(--color-border)] p-12 text-center">
                <Trash2 className="mx-auto mb-3 h-10 w-10 text-[var(--color-text-muted)]" />
                <p className="text-[var(--color-text-muted)]">
                  Trash is empty.
                </p>
              </div>
            ) : (
              <div className="space-y-2">
                {trash.map((doc) => (
                  <div
                    key={doc.id}
                    className="group flex items-center justify-between rounded-lg border border-[var(--color-border)] p-4 transition hover:bg-[var(--color-bg-secondary)]"
                    onContextMenu={(e) => {
                      e.preventDefault();
                      handleTrashContextMenu(e, doc);
                    }}
                  >
                    <div className="flex items-center gap-3">
                      <FileText className="h-5 w-5 text-[var(--color-text-muted)]" />
                      <div>
                        <p className="font-medium text-[var(--color-text)]">
                          {doc.title}
                        </p>
                        <p className="text-xs text-[var(--color-text-muted)]">
                          Deleted{" "}
                          {doc.deleted_at
                            ? formatDateTime(doc.deleted_at)
                            : "recently"}
                        </p>
                      </div>
                    </div>
                    <div className="flex gap-1">
                      <button
                        onClick={() => restoreDocument(doc.id)}
                        title="Restore"
                        className="invisible rounded p-1.5 text-[var(--color-text-muted)] transition hover:bg-green-50 hover:text-green-600 group-hover:visible"
                      >
                        <RotateCcw className="h-4 w-4" />
                      </button>
                      <button
                        onClick={() => hardDeleteDocument(doc.id)}
                        title="Delete permanently"
                        className="invisible rounded p-1.5 text-[var(--color-text-muted)] transition hover:bg-red-50 hover:text-[var(--color-danger)] group-hover:visible"
                      >
                        <XCircle className="h-4 w-4" />
                      </button>
                    </div>
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

      <DocumentInfoModal
        doc={infoDoc!}
        open={infoDoc !== null}
        onClose={() => setInfoDoc(null)}
      />

      {renameDoc && (
        <RenameDialog
          currentTitle={renameDoc.title}
          open
          onClose={() => setRenameDoc(null)}
          onSave={(newTitle) => renameDocument(renameDoc.id, newTitle)}
        />
      )}
    </div>
  );
}
