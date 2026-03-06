import { useEffect, useState } from "react";
import { Copy, Key, Plus, Trash2 } from "lucide-react";
import { Navbar } from "../components/Layout/Navbar";
import { keysApi, type ApiKeyInfo } from "../lib/api";
import { copyToClipboard } from "../lib/clipboard";
import { formatDateShort } from "../lib/dateUtils";

export function SettingsPage() {
  const [keys, setKeys] = useState<ApiKeyInfo[]>([]);
  const [newKeyName, setNewKeyName] = useState("");
  const [createdKey, setCreatedKey] = useState<string | null>(null);

  useEffect(() => {
    document.title = "Settings - CollabMark";
    return () => {
      document.title = "CollabMark";
    };
  }, []);

  useEffect(() => {
    keysApi.list().then(({ data }) => setKeys(data));
  }, []);

  const handleCreate = async () => {
    if (!newKeyName.trim()) return;
    const { data } = await keysApi.create(newKeyName.trim());
    setCreatedKey(data.raw_key);
    setNewKeyName("");
    const { data: updated } = await keysApi.list();
    setKeys(updated);
  };

  const handleRevoke = async (id: string) => {
    await keysApi.revoke(id);
    setKeys(keys.filter((k) => k.id !== id));
  };

  const handleCopy = (key: string) => {
    copyToClipboard(key);
  };

  return (
    <div className="min-h-screen bg-[var(--color-bg-secondary)]">
      <Navbar />
      <main className="mx-auto max-w-2xl px-6 py-8">
        <h1 className="mb-6 text-2xl font-bold">Settings</h1>

        <section className="rounded-lg border border-[var(--color-border)] bg-white p-6">
          <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold">
            <Key className="h-5 w-5" />
            API Keys
          </h2>
          <p className="mb-4 text-sm text-[var(--color-text-muted)]">
            Use API keys to access your documents programmatically. Include the key in the <code>X-API-Key</code>{" "}
            header.
          </p>

          {createdKey && (
            <div className="mb-4 rounded-md border border-green-200 bg-green-50 p-3">
              <p className="mb-1 text-sm font-medium text-green-800">
                API key created! Copy it now -- it won't be shown again.
              </p>
              <div className="flex items-center gap-2">
                <code className="flex-1 rounded bg-white px-2 py-1 text-xs">{createdKey}</code>
                <button
                  onClick={() => handleCopy(createdKey)}
                  className="rounded p-1 hover:bg-green-100"
                  data-testid="copy-api-key"
                >
                  <Copy className="h-4 w-4 text-green-700" />
                </button>
              </div>
            </div>
          )}

          <div className="mb-4 flex gap-2">
            <input
              value={newKeyName}
              onChange={(e) => setNewKeyName(e.target.value)}
              placeholder="Key name (e.g., CI pipeline)"
              className="flex-1 rounded-md border border-[var(--color-border)] px-3 py-2 text-sm outline-none focus:border-[var(--color-primary)] focus:ring-1 focus:ring-[var(--color-primary)]"
              onKeyDown={(e) => e.key === "Enter" && handleCreate()}
            />
            <button
              onClick={handleCreate}
              className="inline-flex items-center gap-1 rounded-md bg-[var(--color-primary)] px-4 py-2 text-sm font-medium text-white transition hover:bg-[var(--color-primary-hover)]"
            >
              <Plus className="h-4 w-4" />
              Create
            </button>
          </div>

          {keys.length === 0 ? (
            <p className="text-center text-sm text-[var(--color-text-muted)]">No API keys yet.</p>
          ) : (
            <ul className="space-y-2">
              {keys.map((k) => (
                <li
                  key={k.id}
                  className="flex items-center justify-between rounded-md border border-[var(--color-border)] px-3 py-2"
                >
                  <div>
                    <p className="text-sm font-medium">{k.name}</p>
                    <p className="text-xs text-[var(--color-text-muted)]">
                      Created {formatDateShort(k.created_at)}
                      {k.last_used_at && ` | Last used ${formatDateShort(k.last_used_at)}`}
                    </p>
                  </div>
                  <button
                    onClick={() => handleRevoke(k.id)}
                    className="rounded p-1 text-[var(--color-text-muted)] hover:bg-red-50 hover:text-[var(--color-danger)]"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
      </main>
    </div>
  );
}
