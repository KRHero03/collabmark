import React, { useEffect, useState, useCallback } from "react";
import { Loader2, Plus, Pencil, Users, ChevronDown, ChevronRight, X, Check } from "lucide-react";
import { type Organization, type OrgMember, orgsApi } from "../lib/api";
import { useToast } from "../hooks/useToast";
import { formatDateShort } from "../lib/dateUtils";
import { ToastContainer } from "../components/Home/ToastContainer";
import { NotFoundPage } from "./NotFoundPage";

const PLAN_OPTIONS = ["free", "pro", "enterprise"] as const;

function slugFromName(name: string): string {
  return name
    .toLowerCase()
    .trim()
    .replace(/\s+/g, "-")
    .replace(/[^a-z0-9-]/g, "");
}

export function SuperAdminPage() {
  const [orgs, setOrgs] = useState<Organization[]>([]);
  const [loading, setLoading] = useState(true);
  const [accessDenied, setAccessDenied] = useState(false);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [editingOrgId, setEditingOrgId] = useState<string | null>(null);
  const [expandedOrgId, setExpandedOrgId] = useState<string | null>(null);
  const [membersCache, setMembersCache] = useState<Record<string, OrgMember[]>>({});
  const [membersLoading, setMembersLoading] = useState<Record<string, boolean>>({});
  const { addToast } = useToast();

  // Create form state
  const [createName, setCreateName] = useState("");
  const [createSlug, setCreateSlug] = useState("");
  const [createDomains, setCreateDomains] = useState("");
  const [createPlan, setCreatePlan] = useState<string>("free");
  const [createSubmitting, setCreateSubmitting] = useState(false);

  // Edit form state (keyed by org id)
  const [editForm, setEditForm] = useState<
    Record<string, { name: string; slug: string; domains: string; plan: string }>
  >({});
  const [editSubmitting, setEditSubmitting] = useState<Record<string, boolean>>({});

  const loadOrgs = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await orgsApi.list();
      setOrgs(data);
    } catch (err: unknown) {
      const status = (err as { response?: { status?: number } })?.response?.status;
      if (status === 403) {
        setAccessDenied(true);
        return;
      }
      const msg = err instanceof Error ? err.message : "Failed to load organizations";
      addToast(msg, "error");
    } finally {
      setLoading(false);
    }
  }, [addToast]);

  useEffect(() => {
    loadOrgs();
  }, [loadOrgs]);

  const handleCreateNameChange = (name: string) => {
    setCreateName(name);
    if (!createSlug || createSlug === slugFromName(createName)) {
      setCreateSlug(slugFromName(name));
    }
  };

  const handleCreateSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!createName.trim() || !createSlug.trim()) {
      addToast("Name and slug are required", "error");
      return;
    }
    setCreateSubmitting(true);
    try {
      const domains = createDomains
        .split(",")
        .map((d) => d.trim())
        .filter(Boolean);
      await orgsApi.create({
        name: createName.trim(),
        slug: createSlug.trim(),
        verified_domains: domains.length ? domains : undefined,
        plan: createPlan,
      });
      addToast("Organization created", "success");
      setCreateName("");
      setCreateSlug("");
      setCreateDomains("");
      setCreatePlan("free");
      setShowCreateForm(false);
      loadOrgs();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to create organization";
      addToast(msg, "error");
    } finally {
      setCreateSubmitting(false);
    }
  };

  const openEditForm = (org: Organization) => {
    setEditingOrgId(org.id);
    setEditForm((prev) => ({
      ...prev,
      [org.id]: {
        name: org.name,
        slug: org.slug,
        domains: org.verified_domains?.join(", ") ?? "",
        plan: org.plan ?? "free",
      },
    }));
  };

  const handleEditSubmit = async (orgId: string, e: React.FormEvent) => {
    e.preventDefault();
    const form = editForm[orgId];
    if (!form?.name.trim() || !form?.slug.trim()) {
      addToast("Name and slug are required", "error");
      return;
    }
    setEditSubmitting((prev) => ({ ...prev, [orgId]: true }));
    try {
      const domains = form.domains
        .split(",")
        .map((d) => d.trim())
        .filter(Boolean);
      await orgsApi.update(orgId, {
        name: form.name.trim(),
        slug: form.slug.trim(),
        verified_domains: domains,
        plan: form.plan,
      });
      addToast("Organization updated", "success");
      setEditingOrgId(null);
      loadOrgs();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to update organization";
      addToast(msg, "error");
    } finally {
      setEditSubmitting((prev) => ({ ...prev, [orgId]: false }));
    }
  };

  const loadMembers = async (orgId: string) => {
    if (membersCache[orgId]) return;
    setMembersLoading((prev) => ({ ...prev, [orgId]: true }));
    try {
      const { data } = await orgsApi.listMembers(orgId);
      setMembersCache((prev) => ({ ...prev, [orgId]: data }));
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load members";
      addToast(msg, "error");
    } finally {
      setMembersLoading((prev) => ({ ...prev, [orgId]: false }));
    }
  };

  const toggleMembers = (orgId: string) => {
    if (expandedOrgId === orgId) {
      setExpandedOrgId(null);
    } else {
      setExpandedOrgId(orgId);
      loadMembers(orgId);
    }
  };

  if (accessDenied) {
    return <NotFoundPage />;
  }

  return (
    <div className="min-h-screen bg-[var(--color-bg)] dark:bg-[var(--color-bg)]" data-testid="admin-dashboard">
      <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6">
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-[var(--color-text)] sm:text-3xl">Admin Dashboard</h1>
          <p className="mt-1 text-sm text-[var(--color-text-muted)]">Manage organizations and platform settings</p>
        </div>

        <div className="mb-6">
          <button
            type="button"
            onClick={() => setShowCreateForm((v) => !v)}
            className="inline-flex items-center gap-2 rounded-lg bg-[var(--color-primary)] px-4 py-2.5 text-sm font-medium text-white transition hover:bg-[var(--color-primary-hover)] disabled:opacity-50"
            data-testid="create-org-btn"
          >
            <Plus className="h-4 w-4" />
            Create Organization
          </button>
        </div>

        {showCreateForm && (
          <form
            onSubmit={handleCreateSubmit}
            className="mb-8 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6 dark:border-[var(--color-border)] dark:bg-[var(--color-surface)]"
            data-testid="create-org-form"
          >
            <h3 className="mb-4 text-lg font-semibold text-[var(--color-text)]">New Organization</h3>
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label className="mb-1 block text-sm font-medium text-[var(--color-text)]">Name</label>
                <input
                  type="text"
                  value={createName}
                  onChange={(e) => handleCreateNameChange(e.target.value)}
                  placeholder="Acme Inc"
                  className="w-full rounded-md border border-[var(--color-border)] bg-[var(--color-bg)] px-3 py-2 text-sm text-[var(--color-text)] placeholder-[var(--color-text-muted)] outline-none focus:border-[var(--color-primary)] dark:bg-[var(--color-bg)]"
                />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-[var(--color-text)]">Slug</label>
                <input
                  type="text"
                  value={createSlug}
                  onChange={(e) => setCreateSlug(e.target.value)}
                  placeholder="acme-inc"
                  className="w-full rounded-md border border-[var(--color-border)] bg-[var(--color-bg)] px-3 py-2 text-sm text-[var(--color-text)] placeholder-[var(--color-text-muted)] outline-none focus:border-[var(--color-primary)] dark:bg-[var(--color-bg)]"
                />
              </div>
              <div className="sm:col-span-2">
                <label className="mb-1 block text-sm font-medium text-[var(--color-text)]">
                  Verified Domains (comma-separated)
                </label>
                <input
                  type="text"
                  value={createDomains}
                  onChange={(e) => setCreateDomains(e.target.value)}
                  placeholder="acme.com, acme.io"
                  className="w-full rounded-md border border-[var(--color-border)] bg-[var(--color-bg)] px-3 py-2 text-sm text-[var(--color-text)] placeholder-[var(--color-text-muted)] outline-none focus:border-[var(--color-primary)] dark:bg-[var(--color-bg)]"
                />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-[var(--color-text)]">Plan</label>
                <select
                  value={createPlan}
                  onChange={(e) => setCreatePlan(e.target.value)}
                  className="w-full rounded-md border border-[var(--color-border)] bg-[var(--color-bg)] px-3 py-2 text-sm text-[var(--color-text)] outline-none focus:border-[var(--color-primary)] dark:bg-[var(--color-bg)]"
                >
                  {PLAN_OPTIONS.map((p) => (
                    <option key={p} value={p}>
                      {p}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <div className="mt-4 flex gap-2">
              <button
                type="submit"
                disabled={createSubmitting}
                className="inline-flex items-center gap-2 rounded-md bg-[var(--color-primary)] px-4 py-2 text-sm font-medium text-white transition hover:bg-[var(--color-primary-hover)] disabled:opacity-50"
              >
                {createSubmitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />}
                Create
              </button>
              <button
                type="button"
                onClick={() => setShowCreateForm(false)}
                className="inline-flex items-center gap-2 rounded-md border border-[var(--color-border)] px-4 py-2 text-sm font-medium text-[var(--color-text)] transition hover:bg-[var(--color-hover)]"
              >
                <X className="h-4 w-4" />
                Cancel
              </button>
            </div>
          </form>
        )}

        <div
          className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] dark:border-[var(--color-border)] dark:bg-[var(--color-surface)]"
          data-testid="org-list"
        >
          {loading ? (
            <div className="flex items-center justify-center py-16">
              <Loader2 className="h-8 w-8 animate-spin text-[var(--color-primary)]" />
            </div>
          ) : orgs.length === 0 ? (
            <p className="py-12 text-center text-sm text-[var(--color-text-muted)]">No organizations yet.</p>
          ) : (
            <>
              {/* Desktop table */}
              <div className="hidden overflow-x-auto md:block">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-[var(--color-border)]">
                      <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-[var(--color-text-muted)]">
                        Name
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-[var(--color-text-muted)]">
                        Slug
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-[var(--color-text-muted)]">
                        Domains
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-[var(--color-text-muted)]">
                        Plan
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-[var(--color-text-muted)]">
                        Members
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-[var(--color-text-muted)]">
                        Created
                      </th>
                      <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wider text-[var(--color-text-muted)]">
                        Actions
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {orgs.map((org) => (
                      <React.Fragment key={org.id}>
                        <tr
                          key={org.id}
                          className="border-b border-[var(--color-border)] last:border-b-0"
                          data-testid={`org-row-${org.id}`}
                        >
                          {editingOrgId === org.id && editForm[org.id] ? (
                            <td colSpan={7} className="p-4">
                              <form
                                onSubmit={(e) => handleEditSubmit(org.id, e)}
                                className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] p-4 dark:bg-[var(--color-bg)]"
                              >
                                <div className="grid gap-4 sm:grid-cols-2">
                                  <div>
                                    <label className="mb-1 block text-xs font-medium text-[var(--color-text-muted)]">
                                      Name
                                    </label>
                                    <input
                                      type="text"
                                      value={editForm[org.id].name}
                                      onChange={(e) =>
                                        setEditForm((prev) => ({
                                          ...prev,
                                          [org.id]: {
                                            ...prev[org.id],
                                            name: e.target.value,
                                          },
                                        }))
                                      }
                                      className="w-full rounded-md border border-[var(--color-border)] px-2 py-1.5 text-sm"
                                    />
                                  </div>
                                  <div>
                                    <label className="mb-1 block text-xs font-medium text-[var(--color-text-muted)]">
                                      Slug
                                    </label>
                                    <input
                                      type="text"
                                      value={editForm[org.id].slug}
                                      onChange={(e) =>
                                        setEditForm((prev) => ({
                                          ...prev,
                                          [org.id]: {
                                            ...prev[org.id],
                                            slug: e.target.value,
                                          },
                                        }))
                                      }
                                      className="w-full rounded-md border border-[var(--color-border)] px-2 py-1.5 text-sm"
                                    />
                                  </div>
                                  <div className="sm:col-span-2">
                                    <label className="mb-1 block text-xs font-medium text-[var(--color-text-muted)]">
                                      Domains
                                    </label>
                                    <input
                                      type="text"
                                      value={editForm[org.id].domains}
                                      onChange={(e) =>
                                        setEditForm((prev) => ({
                                          ...prev,
                                          [org.id]: {
                                            ...prev[org.id],
                                            domains: e.target.value,
                                          },
                                        }))
                                      }
                                      className="w-full rounded-md border border-[var(--color-border)] px-2 py-1.5 text-sm"
                                    />
                                  </div>
                                  <div>
                                    <label className="mb-1 block text-xs font-medium text-[var(--color-text-muted)]">
                                      Plan
                                    </label>
                                    <select
                                      value={editForm[org.id].plan}
                                      onChange={(e) =>
                                        setEditForm((prev) => ({
                                          ...prev,
                                          [org.id]: {
                                            ...prev[org.id],
                                            plan: e.target.value,
                                          },
                                        }))
                                      }
                                      className="w-full rounded-md border border-[var(--color-border)] px-2 py-1.5 text-sm"
                                    >
                                      {PLAN_OPTIONS.map((p) => (
                                        <option key={p} value={p}>
                                          {p}
                                        </option>
                                      ))}
                                    </select>
                                  </div>
                                </div>
                                <div className="mt-3 flex gap-2">
                                  <button
                                    type="submit"
                                    disabled={editSubmitting[org.id]}
                                    className="inline-flex items-center gap-1 rounded px-2 py-1 text-xs font-medium text-white bg-[var(--color-primary)] disabled:opacity-50"
                                  >
                                    {editSubmitting[org.id] ? (
                                      <Loader2 className="h-3 w-3 animate-spin" />
                                    ) : (
                                      <Check className="h-3 w-3" />
                                    )}
                                    Save
                                  </button>
                                  <button
                                    type="button"
                                    onClick={() => setEditingOrgId(null)}
                                    className="inline-flex items-center gap-1 rounded border border-[var(--color-border)] px-2 py-1 text-xs font-medium"
                                  >
                                    <X className="h-3 w-3" />
                                    Cancel
                                  </button>
                                </div>
                              </form>
                            </td>
                          ) : (
                            <>
                              <td className="px-4 py-3 text-sm font-medium text-[var(--color-text)]">{org.name}</td>
                              <td className="px-4 py-3 text-sm text-[var(--color-text-muted)]">{org.slug}</td>
                              <td className="px-4 py-3 text-sm text-[var(--color-text-muted)]">
                                {org.verified_domains?.length ? org.verified_domains.join(", ") : "—"}
                              </td>
                              <td className="px-4 py-3 text-sm text-[var(--color-text-muted)]">{org.plan}</td>
                              <td className="px-4 py-3 text-sm text-[var(--color-text-muted)]">{org.member_count}</td>
                              <td className="px-4 py-3 text-sm text-[var(--color-text-muted)]">
                                {formatDateShort(org.created_at)}
                              </td>
                              <td className="px-4 py-3 text-right">
                                <div className="flex justify-end gap-1">
                                  <button
                                    type="button"
                                    onClick={() => openEditForm(org)}
                                    className="rounded p-1.5 text-[var(--color-text-muted)] transition hover:bg-[var(--color-hover)] hover:text-[var(--color-text)]"
                                    title="Edit"
                                  >
                                    <Pencil className="h-4 w-4" />
                                  </button>
                                  <button
                                    type="button"
                                    onClick={() => toggleMembers(org.id)}
                                    className="rounded p-1.5 text-[var(--color-text-muted)] transition hover:bg-[var(--color-hover)] hover:text-[var(--color-text)]"
                                    title="View Members"
                                  >
                                    <Users className="h-4 w-4" />
                                  </button>
                                </div>
                              </td>
                            </>
                          )}
                        </tr>
                        {expandedOrgId === org.id && (
                          <tr key={`members-${org.id}`}>
                            <td colSpan={7} className="bg-[var(--color-bg)]/50 p-4 dark:bg-[var(--color-bg)]/30">
                              <div
                                data-testid={`member-list-${org.id}`}
                                className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-4 dark:bg-[var(--color-surface)]"
                              >
                                <h4 className="mb-3 text-sm font-semibold text-[var(--color-text)]">Members</h4>
                                {membersLoading[org.id] ? (
                                  <div className="flex items-center justify-center py-8">
                                    <Loader2 className="h-6 w-6 animate-spin text-[var(--color-primary)]" />
                                  </div>
                                ) : (membersCache[org.id]?.length ?? 0) === 0 ? (
                                  <p className="py-4 text-center text-sm text-[var(--color-text-muted)]">No members</p>
                                ) : (
                                  <div className="overflow-x-auto">
                                    <table className="w-full text-sm">
                                      <thead>
                                        <tr className="border-b border-[var(--color-border)]">
                                          <th className="pb-2 text-left text-xs font-medium text-[var(--color-text-muted)]">
                                            Name
                                          </th>
                                          <th className="pb-2 text-left text-xs font-medium text-[var(--color-text-muted)]">
                                            Email
                                          </th>
                                          <th className="pb-2 text-left text-xs font-medium text-[var(--color-text-muted)]">
                                            Role
                                          </th>
                                          <th className="pb-2 text-left text-xs font-medium text-[var(--color-text-muted)]">
                                            Joined
                                          </th>
                                        </tr>
                                      </thead>
                                      <tbody>
                                        {membersCache[org.id]?.map((m) => (
                                          <tr
                                            key={m.id}
                                            className="border-b border-[var(--color-border)] last:border-b-0"
                                          >
                                            <td className="py-2 text-[var(--color-text)]">{m.user_name}</td>
                                            <td className="py-2 text-[var(--color-text-muted)]">{m.user_email}</td>
                                            <td className="py-2 text-[var(--color-text-muted)]">{m.role}</td>
                                            <td className="py-2 text-[var(--color-text-muted)]">
                                              {formatDateShort(m.joined_at)}
                                            </td>
                                          </tr>
                                        ))}
                                      </tbody>
                                    </table>
                                  </div>
                                )}
                              </div>
                            </td>
                          </tr>
                        )}
                      </React.Fragment>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Mobile stacked cards */}
              <div className="space-y-4 p-4 md:hidden">
                {orgs.map((org) => (
                  <div
                    key={org.id}
                    className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] p-4 dark:bg-[var(--color-bg)]"
                    data-testid={`org-row-${org.id}`}
                  >
                    {editingOrgId === org.id && editForm[org.id] ? (
                      <form onSubmit={(e) => handleEditSubmit(org.id, e)} className="space-y-3">
                        <input
                          type="text"
                          value={editForm[org.id].name}
                          onChange={(e) =>
                            setEditForm((prev) => ({
                              ...prev,
                              [org.id]: { ...prev[org.id], name: e.target.value },
                            }))
                          }
                          placeholder="Name"
                          className="w-full rounded-md border border-[var(--color-border)] px-3 py-2 text-sm"
                        />
                        <input
                          type="text"
                          value={editForm[org.id].slug}
                          onChange={(e) =>
                            setEditForm((prev) => ({
                              ...prev,
                              [org.id]: { ...prev[org.id], slug: e.target.value },
                            }))
                          }
                          placeholder="Slug"
                          className="w-full rounded-md border border-[var(--color-border)] px-3 py-2 text-sm"
                        />
                        <input
                          type="text"
                          value={editForm[org.id].domains}
                          onChange={(e) =>
                            setEditForm((prev) => ({
                              ...prev,
                              [org.id]: { ...prev[org.id], domains: e.target.value },
                            }))
                          }
                          placeholder="Domains (comma-separated)"
                          className="w-full rounded-md border border-[var(--color-border)] px-3 py-2 text-sm"
                        />
                        <select
                          value={editForm[org.id].plan}
                          onChange={(e) =>
                            setEditForm((prev) => ({
                              ...prev,
                              [org.id]: { ...prev[org.id], plan: e.target.value },
                            }))
                          }
                          className="w-full rounded-md border border-[var(--color-border)] px-3 py-2 text-sm"
                        >
                          {PLAN_OPTIONS.map((p) => (
                            <option key={p} value={p}>
                              {p}
                            </option>
                          ))}
                        </select>
                        <div className="flex gap-2">
                          <button
                            type="submit"
                            disabled={editSubmitting[org.id]}
                            className="inline-flex items-center gap-1 rounded-md bg-[var(--color-primary)] px-3 py-1.5 text-sm text-white disabled:opacity-50"
                          >
                            {editSubmitting[org.id] ? (
                              <Loader2 className="h-3 w-3 animate-spin" />
                            ) : (
                              <Check className="h-3 w-3" />
                            )}
                            Save
                          </button>
                          <button
                            type="button"
                            onClick={() => setEditingOrgId(null)}
                            className="rounded-md border border-[var(--color-border)] px-3 py-1.5 text-sm"
                          >
                            Cancel
                          </button>
                        </div>
                      </form>
                    ) : (
                      <>
                        <div className="flex items-start justify-between gap-2">
                          <div>
                            <p className="font-medium text-[var(--color-text)]">{org.name}</p>
                            <p className="text-xs text-[var(--color-text-muted)]">
                              {org.slug} · {org.plan}
                            </p>
                            <p className="mt-1 text-xs text-[var(--color-text-muted)]">
                              {org.verified_domains?.length ? org.verified_domains.join(", ") : "No domains"}
                            </p>
                            <p className="text-xs text-[var(--color-text-muted)]">
                              {org.member_count} members · {formatDateShort(org.created_at)}
                            </p>
                          </div>
                          <div className="flex gap-1">
                            <button
                              type="button"
                              onClick={() => openEditForm(org)}
                              className="rounded p-1.5 text-[var(--color-text-muted)] hover:bg-[var(--color-hover)]"
                            >
                              <Pencil className="h-4 w-4" />
                            </button>
                            <button
                              type="button"
                              onClick={() => toggleMembers(org.id)}
                              className="rounded p-1.5 text-[var(--color-text-muted)] hover:bg-[var(--color-hover)]"
                            >
                              {expandedOrgId === org.id ? (
                                <ChevronDown className="h-4 w-4" />
                              ) : (
                                <ChevronRight className="h-4 w-4" />
                              )}
                            </button>
                          </div>
                        </div>
                        {expandedOrgId === org.id && (
                          <div
                            className="mt-4 rounded-lg border border-[var(--color-border)] p-3"
                            data-testid={`member-list-${org.id}`}
                          >
                            <h4 className="mb-2 text-xs font-semibold text-[var(--color-text-muted)]">Members</h4>
                            {membersLoading[org.id] ? (
                              <div className="flex justify-center py-4">
                                <Loader2 className="h-5 w-5 animate-spin text-[var(--color-primary)]" />
                              </div>
                            ) : (membersCache[org.id]?.length ?? 0) === 0 ? (
                              <p className="text-center text-xs text-[var(--color-text-muted)]">No members</p>
                            ) : (
                              <div className="space-y-2">
                                {membersCache[org.id]?.map((m) => (
                                  <div
                                    key={m.id}
                                    className="flex flex-wrap justify-between gap-1 border-b border-[var(--color-border)] pb-2 last:border-b-0 last:pb-0"
                                  >
                                    <p className="text-sm font-medium text-[var(--color-text)]">{m.user_name}</p>
                                    <p className="text-xs text-[var(--color-text-muted)]">{m.user_email}</p>
                                    <p className="text-xs text-[var(--color-text-muted)]">
                                      {m.role} · {formatDateShort(m.joined_at)}
                                    </p>
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>
                        )}
                      </>
                    )}
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      </main>
      <ToastContainer />
    </div>
  );
}
