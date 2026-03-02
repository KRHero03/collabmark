import { useEffect, useState } from "react";
import { useNavigate } from "react-router";
import { FileText, Users } from "lucide-react";
import { Navbar } from "../components/Layout/Navbar";
import { DocumentList } from "../components/Home/DocumentList";
import { useDocuments } from "../hooks/useDocuments";
import { sharingApi, type SharedDocument } from "../lib/api";

export function HomePage() {
  const { documents, loading, fetchDocuments, createDocument, deleteDocument } =
    useDocuments();
  const navigate = useNavigate();
  const [tab, setTab] = useState<"mine" | "shared">("mine");
  const [sharedDocs, setSharedDocs] = useState<SharedDocument[]>([]);
  const [sharedLoading, setSharedLoading] = useState(false);

  useEffect(() => {
    document.title = "Home - CollabMark";
    return () => { document.title = "CollabMark"; };
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
    }
  }, [tab]);

  const handleCreate = async () => {
    const doc = await createDocument();
    navigate(`/edit/${doc.id}`);
  };

  return (
    <div className="min-h-screen bg-[var(--color-bg-secondary)]">
      <Navbar />
      <main className="mx-auto max-w-4xl px-6 py-8">
        <div className="mb-6 flex gap-1 rounded-lg border border-[var(--color-border)] bg-white p-1">
          <button
            onClick={() => setTab("mine")}
            className={`flex-1 rounded-md px-4 py-2 text-sm font-medium transition ${
              tab === "mine"
                ? "bg-[var(--color-primary)] text-white"
                : "text-[var(--color-text-muted)] hover:bg-gray-50"
            }`}
          >
            My Documents
          </button>
          <button
            onClick={() => setTab("shared")}
            className={`flex-1 rounded-md px-4 py-2 text-sm font-medium transition ${
              tab === "shared"
                ? "bg-[var(--color-primary)] text-white"
                : "text-[var(--color-text-muted)] hover:bg-gray-50"
            }`}
          >
            <span className="inline-flex items-center gap-1">
              <Users className="h-4 w-4" />
              Shared with me
            </span>
          </button>
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
                  >
                    <div className="flex items-center gap-3">
                      <FileText className="h-5 w-5 text-[var(--color-primary)]" />
                      <div>
                        <p className="font-medium">{doc.title}</p>
                        <p className="text-xs text-[var(--color-text-muted)]">
                          {doc.permission} access | Last accessed{" "}
                          {new Date(doc.last_accessed_at).toLocaleDateString(
                            undefined,
                            {
                              month: "short",
                              day: "numeric",
                              year: "numeric",
                              hour: "2-digit",
                              minute: "2-digit",
                            }
                          )}
                        </p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
}
