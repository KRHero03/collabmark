/**
 * User profile page showing avatar, name, email, and account info.
 */

import { useEffect, useState } from "react";
import { User } from "lucide-react";
import { Navbar } from "../components/Layout/Navbar";
import { useAuth } from "../hooks/useAuth";
import { authApi } from "../lib/api";

export function ProfilePage() {
  const { user, fetchUser } = useAuth();
  const [name, setName] = useState(user?.name || "");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    document.title = "Profile - CollabMark";
    return () => { document.title = "CollabMark"; };
  }, []);

  const handleSave = async () => {
    if (!name.trim()) return;
    setSaving(true);
    try {
      await authApi.getMe(); // Verify session
      const api = (await import("../lib/api")).default;
      await api.put("/users/me", { name: name.trim() });
      await fetchUser();
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } finally {
      setSaving(false);
    }
  };

  if (!user) return null;

  return (
    <div className="min-h-screen bg-[var(--color-bg-secondary)]">
      <Navbar />
      <main className="mx-auto max-w-2xl px-6 py-8">
        <h1 className="mb-6 text-2xl font-bold">Profile</h1>

        <section className="rounded-lg border border-[var(--color-border)] bg-white p-6">
          <div className="mb-6 flex items-center gap-4">
            {user.avatar_url ? (
              <img
                src={user.avatar_url}
                alt={user.name}
                className="h-16 w-16 rounded-full"
              />
            ) : (
              <User className="h-16 w-16 rounded-full bg-gray-200 p-3" />
            )}
            <div>
              <p className="text-lg font-semibold">{user.name}</p>
              <p className="text-sm text-[var(--color-text-muted)]">
                {user.email}
              </p>
            </div>
          </div>

          <div className="space-y-4">
            <div>
              <label className="mb-1 block text-sm font-medium">
                Display Name
              </label>
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full rounded-md border border-[var(--color-border)] px-3 py-2 text-sm outline-none focus:border-[var(--color-primary)] focus:ring-1 focus:ring-[var(--color-primary)]"
              />
            </div>

            <div>
              <label className="mb-1 block text-sm font-medium">Email</label>
              <input
                value={user.email}
                readOnly
                className="w-full rounded-md border border-[var(--color-border)] bg-gray-50 px-3 py-2 text-sm text-[var(--color-text-muted)]"
              />
            </div>

            <div>
              <label className="mb-1 block text-sm font-medium">
                Member Since
              </label>
              <p className="text-sm text-[var(--color-text-muted)]">
                {new Date(user.created_at).toLocaleDateString(undefined, {
                  year: "numeric",
                  month: "long",
                  day: "numeric",
                })}
              </p>
            </div>
          </div>

          <div className="mt-6 flex items-center gap-3">
            <button
              onClick={handleSave}
              disabled={saving}
              className="rounded-md bg-[var(--color-primary)] px-4 py-2 text-sm font-medium text-white transition hover:bg-[var(--color-primary-hover)] disabled:opacity-50"
            >
              {saving ? "Saving..." : "Save Changes"}
            </button>
            {saved && (
              <span className="text-sm text-green-600">Saved!</span>
            )}
          </div>
        </section>
      </main>
    </div>
  );
}
