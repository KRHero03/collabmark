import { useEffect, useState } from "react";
import { useParams } from "react-router";
import {
  CheckCircle,
  ClipboardCopy,
  Info,
  Key,
  Loader2,
  Mail,
  RefreshCw,
  Save,
  Settings,
  Shield,
  Trash2,
  UserPlus,
  Users,
  XCircle,
} from "lucide-react";
import { type Organization, type OrgMember, type OrgSSOConfig, orgsApi } from "../lib/api";
import { UserAvatar } from "../components/Layout/UserAvatar";
import { Navbar } from "../components/Layout/Navbar";
import { useAuth } from "../hooks/useAuth";
import { formatDateShort } from "../lib/dateUtils";
import { NotFoundPage } from "./NotFoundPage";

function InfoTooltip({ text }: { text: string }) {
  return (
    <span className="group relative ml-1 inline-flex cursor-help">
      <Info className="h-3.5 w-3.5 text-[var(--color-text-muted)]" />
      <span className="pointer-events-none absolute bottom-full left-1/2 z-50 mb-1 -translate-x-1/2 whitespace-nowrap rounded bg-gray-900 px-2 py-1 text-xs text-white opacity-0 shadow-lg transition-opacity group-hover:opacity-100 dark:bg-gray-700">
        {text}
      </span>
    </span>
  );
}

type Tab = "general" | "members" | "sso";

export function OrgSettingsPage() {
  const { orgId } = useParams<{ orgId: string }>();
  const { user } = useAuth();
  const [activeTab, setActiveTab] = useState<Tab>("general");

  const [org, setOrg] = useState<Organization | null>(null);
  const [members, setMembers] = useState<OrgMember[]>([]);
  const [ssoConfig, setSsoConfig] = useState<OrgSSOConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [accessDenied, setAccessDenied] = useState(false);
  const [saving, setSaving] = useState(false);

  const [toast, setToast] = useState<{
    type: "success" | "error";
    message: string;
  } | null>(null);

  // General form
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [verifiedDomains, setVerifiedDomains] = useState("");
  const [plan, setPlan] = useState("");

  // Members
  const [showInviteForm, setShowInviteForm] = useState(false);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState<"admin" | "member">("member");
  const [inviting, setInviting] = useState(false);
  const [updatingRole, setUpdatingRole] = useState<string | null>(null);
  const [removing, setRemoving] = useState<string | null>(null);

  // SSO form
  const [ssoProtocol, setSsoProtocol] = useState<"saml" | "oidc">("saml");
  const [ssoEnabled, setSsoEnabled] = useState(false);
  const [idpEntityId, setIdpEntityId] = useState("");
  const [idpSsoUrl, setIdpSsoUrl] = useState("");
  const [idpCertificate, setIdpCertificate] = useState("");
  const [spEntityId, setSpEntityId] = useState("");
  const [spAcsUrl, setSpAcsUrl] = useState("");
  const [oidcDiscoveryUrl, setOidcDiscoveryUrl] = useState("");
  const [oidcClientId, setOidcClientId] = useState("");
  const [oidcClientSecret, setOidcClientSecret] = useState("");
  const [savingSso, setSavingSso] = useState(false);

  // SSO / SCIM view mode
  const [ssoEditMode, setSsoEditMode] = useState(false);
  const [scimEditMode, setScimEditMode] = useState(false);

  // SCIM
  const [scimEnabled, setScimEnabled] = useState(false);
  const [scimToken, setScimToken] = useState<string | null>(null);
  const [generatingToken, setGeneratingToken] = useState(false);
  const [revokingToken, setRevokingToken] = useState(false);
  const [scimCopied, setScimCopied] = useState<"url" | "token" | null>(null);

  const showToast = (type: "success" | "error", message: string) => {
    setToast({ type, message });
    setTimeout(() => setToast(null), 4000);
  };

  const scimActive = scimEnabled || !!ssoConfig?.scim_enabled;
  const membersReadOnly = scimActive && !user?.is_super_admin;

  useEffect(() => {
    document.title = "Organization Settings - CollabMark";
    return () => {
      document.title = "CollabMark";
    };
  }, []);

  useEffect(() => {
    if (!orgId) return;
    setLoading(true);
    Promise.all([
      orgsApi.get(orgId).then(({ data }) => {
        setOrg(data);
        setName(data.name);
        setSlug(data.slug);
        setVerifiedDomains(data.verified_domains.join(", "));
        setPlan(data.plan);
      }),
      orgsApi.listMembers(orgId).then(({ data }) => setMembers(data)),
      orgsApi.getSSOConfig(orgId).then(({ data }) => {
        if (data) {
          setSsoConfig(data);
          setSsoProtocol(data.protocol);
          setSsoEnabled(data.enabled);
          setIdpEntityId(data.idp_entity_id || "");
          setIdpSsoUrl(data.idp_sso_url || "");
          setSpEntityId(data.sp_entity_id || "");
          setSpAcsUrl(data.sp_acs_url || "");
          setOidcDiscoveryUrl(data.oidc_discovery_url || "");
          setOidcClientId(data.oidc_client_id || "");
          setScimEnabled(data.scim_enabled);
        }
      }),
    ])
      .catch((err: unknown) => {
        const status = (err as { response?: { status?: number } })?.response?.status;
        if (status === 403) {
          setAccessDenied(true);
          return;
        }
        showToast("error", "Failed to load organization data");
      })
      .finally(() => setLoading(false));
  }, [orgId]);

  const handleSaveGeneral = async () => {
    if (!orgId || saving) return;
    setSaving(true);
    try {
      const { data } = await orgsApi.update(orgId, {
        name: name.trim(),
        slug: slug.trim(),
        verified_domains: verifiedDomains
          .split(",")
          .map((d) => d.trim())
          .filter(Boolean),
        plan: plan.trim() || undefined,
      });
      setOrg(data);
      showToast("success", "Organization updated");
    } catch {
      showToast("error", "Failed to update organization");
    } finally {
      setSaving(false);
    }
  };

  const handleLogoUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !orgId) return;
    try {
      const { data } = await orgsApi.uploadLogo(orgId, file);
      setOrg(data);
      showToast("success", "Logo uploaded");
    } catch {
      showToast("error", "Failed to upload logo");
    }
  };

  const handleDeleteLogo = async () => {
    if (!orgId) return;
    try {
      await orgsApi.deleteLogo(orgId);
      setOrg((prev) => (prev ? { ...prev, logo_url: null } : null));
      showToast("success", "Logo removed");
    } catch {
      showToast("error", "Failed to remove logo");
    }
  };

  const handleInvite = async () => {
    if (!orgId || !inviteEmail.trim() || inviting) return;
    setInviting(true);
    try {
      const { data } = await orgsApi.inviteMember(orgId, {
        email: inviteEmail.trim(),
        role: inviteRole,
      });
      setMembers((prev) => [...prev, data]);
      setInviteEmail("");
      setShowInviteForm(false);
      showToast("success", "Invitation sent");
    } catch {
      showToast("error", "Failed to send invitation");
    } finally {
      setInviting(false);
    }
  };

  const handleUpdateRole = async (userId: string, role: "admin" | "member") => {
    if (!orgId || updatingRole) return;
    setUpdatingRole(userId);
    try {
      const { data } = await orgsApi.updateMemberRole(orgId, userId, role);
      setMembers((prev) => prev.map((m) => (m.user_id === userId ? data : m)));
      showToast("success", "Role updated");
    } catch {
      showToast("error", "Failed to update role");
    } finally {
      setUpdatingRole(null);
    }
  };

  const handleRemoveMember = async (userId: string) => {
    if (!orgId || removing || userId === user?.id) return;
    setRemoving(userId);
    try {
      await orgsApi.removeMember(orgId, userId);
      setMembers((prev) => prev.filter((m) => m.user_id !== userId));
      showToast("success", "Member removed");
    } catch {
      showToast("error", "Failed to remove member");
    } finally {
      setRemoving(null);
    }
  };

  const handleSaveSso = async () => {
    if (!orgId || savingSso) return;
    setSavingSso(true);
    try {
      const payload: Record<string, unknown> = {
        protocol: ssoProtocol,
        enabled: ssoEnabled,
      };
      if (ssoProtocol === "saml") {
        payload.idp_entity_id = idpEntityId.trim() || null;
        payload.idp_sso_url = idpSsoUrl.trim() || null;
        payload.idp_certificate = idpCertificate.trim() || null;
        payload.sp_entity_id = spEntityId.trim() || null;
        payload.sp_acs_url = spAcsUrl.trim() || null;
      } else {
        payload.oidc_discovery_url = oidcDiscoveryUrl.trim() || null;
        payload.oidc_client_id = oidcClientId.trim() || null;
        if (oidcClientSecret) payload.oidc_client_secret = oidcClientSecret;
      }
      const { data } = await orgsApi.updateSSOConfig(orgId, payload);
      setSsoConfig(data);
      setOidcClientSecret("");
      setSsoEditMode(false);
      showToast("success", "SSO configuration saved");
    } catch {
      showToast("error", "Failed to save SSO configuration");
    } finally {
      setSavingSso(false);
    }
  };

  const handleGenerateScimToken = async () => {
    if (!orgId || generatingToken) return;
    setGeneratingToken(true);
    try {
      const { data } = await orgsApi.generateScimToken(orgId);
      setScimToken(data.token);
      setScimEnabled(true);
      if (ssoConfig) {
        setSsoConfig({ ...ssoConfig, scim_enabled: true });
      }
      showToast("success", "SCIM token generated");
    } catch {
      showToast("error", "Failed to generate SCIM token");
    } finally {
      setGeneratingToken(false);
    }
  };

  const handleRevokeScimToken = async () => {
    if (!orgId || revokingToken) return;
    setRevokingToken(true);
    try {
      await orgsApi.revokeScimToken(orgId);
      setScimToken(null);
      setScimEnabled(false);
      if (ssoConfig) {
        setSsoConfig({ ...ssoConfig, scim_enabled: false });
      }
      showToast("success", "SCIM token revoked");
    } catch {
      showToast("error", "Failed to revoke SCIM token");
    } finally {
      setRevokingToken(false);
    }
  };

  const handleCopyScim = (text: string, kind: "url" | "token") => {
    navigator.clipboard.writeText(text);
    setScimCopied(kind);
    setTimeout(() => setScimCopied(null), 2000);
  };

  if (accessDenied) {
    return <NotFoundPage />;
  }

  if (!orgId) {
    return <NotFoundPage />;
  }

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[var(--color-bg)]">
        <Loader2 className="h-8 w-8 animate-spin text-[var(--color-text-muted)]" />
      </div>
    );
  }

  const tabs: { id: Tab; label: string; icon: React.ReactNode; testId: string }[] = [
    { id: "general", label: "General", icon: <Settings className="h-4 w-4" />, testId: "tab-general" },
    { id: "members", label: "Members", icon: <Users className="h-4 w-4" />, testId: "tab-members" },
    { id: "sso", label: "SSO Configuration", icon: <Key className="h-4 w-4" />, testId: "tab-sso" },
  ];

  return (
    <div className="min-h-screen bg-[var(--color-bg)]" data-testid="org-settings">
      <Navbar />
      <main className="mx-auto max-w-4xl px-6 py-8">
        {toast && (
          <div
            className={`mb-6 flex items-center gap-2 rounded-lg px-4 py-3 text-sm font-medium ${
              toast.type === "success"
                ? "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400"
                : "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400"
            }`}
          >
            {toast.type === "success" ? (
              <CheckCircle className="h-4 w-4 shrink-0" />
            ) : (
              <XCircle className="h-4 w-4 shrink-0" />
            )}
            <span>{toast.message}</span>
          </div>
        )}

        <div className="mb-6 flex items-center gap-3">
          <Shield className="h-8 w-8 text-[var(--color-primary)]" />
          <div>
            <h1 className="text-2xl font-bold text-[var(--color-text)]">{org?.name ?? "Organization"} Settings</h1>
            <p className="text-sm text-[var(--color-text-muted)]">Manage your organization</p>
          </div>
        </div>

        <div className="flex gap-1 border-b border-[var(--color-border)]">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              data-testid={tab.testId}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 border-b-2 px-4 py-3 text-sm font-medium transition ${
                activeTab === tab.id
                  ? "border-[var(--color-primary)] text-[var(--color-primary)]"
                  : "border-transparent text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
              }`}
            >
              {tab.icon}
              {tab.label}
            </button>
          ))}
        </div>

        <div className="mt-6 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-6 dark:bg-[var(--color-surface)]">
          {activeTab === "general" && (
            <div className="space-y-4">
              <div>
                <label className="mb-1 flex items-center text-sm font-medium text-[var(--color-text)]">
                  Organization Name
                  <InfoTooltip text="The display name of your organization" />
                </label>
                <input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="w-full rounded-md border border-[var(--color-border)] bg-[var(--color-bg)] px-3 py-2 text-sm text-[var(--color-text)] outline-none focus:border-[var(--color-primary)] focus:ring-1 focus:ring-[var(--color-primary)]"
                />
              </div>
              <div>
                <label className="mb-1 flex items-center text-sm font-medium text-[var(--color-text)]">
                  Slug
                  <InfoTooltip text="A unique URL-friendly identifier for your organization" />
                </label>
                <input
                  value={slug}
                  onChange={(e) => setSlug(e.target.value)}
                  className="w-full rounded-md border border-[var(--color-border)] bg-[var(--color-bg)] px-3 py-2 text-sm text-[var(--color-text)] outline-none focus:border-[var(--color-primary)] focus:ring-1 focus:ring-[var(--color-primary)]"
                />
              </div>
              <div>
                <label className="mb-1 flex items-center text-sm font-medium text-[var(--color-text)]">
                  Verified Domains (comma-separated)
                  <InfoTooltip text="Email domains verified for SSO routing (comma-separated)" />
                </label>
                <input
                  value={verifiedDomains}
                  onChange={(e) => setVerifiedDomains(e.target.value)}
                  placeholder="example.com, corp.example.com"
                  className="w-full rounded-md border border-[var(--color-border)] bg-[var(--color-bg)] px-3 py-2 text-sm text-[var(--color-text)] outline-none focus:border-[var(--color-primary)] focus:ring-1 focus:ring-[var(--color-primary)]"
                />
              </div>
              <div>
                <label className="mb-1 flex items-center text-sm font-medium text-[var(--color-text)]">
                  Plan
                  <InfoTooltip text="Your organization's subscription plan" />
                </label>
                <input
                  value={plan}
                  onChange={(e) => setPlan(e.target.value)}
                  placeholder="free, pro, enterprise"
                  className="w-full rounded-md border border-[var(--color-border)] bg-[var(--color-bg)] px-3 py-2 text-sm text-[var(--color-text)] outline-none focus:border-[var(--color-primary)] focus:ring-1 focus:ring-[var(--color-primary)]"
                />
              </div>
              <div>
                <label className="mb-1 flex items-center text-sm font-medium text-[var(--color-text)]">
                  Organization Logo
                  <InfoTooltip text="Upload your organization logo (128x128 to 512x512 recommended)" />
                </label>
                {org?.logo_url && (
                  <div className="mb-2 flex items-center gap-3">
                    <img
                      src={org.logo_url}
                      alt="Org logo"
                      className="h-16 w-16 rounded-lg border border-[var(--color-border)] object-cover"
                    />
                    <button
                      onClick={handleDeleteLogo}
                      className="text-sm text-red-600 hover:text-red-700 dark:text-red-400"
                    >
                      Remove logo
                    </button>
                  </div>
                )}
                <div>
                  <input
                    type="file"
                    accept=".png,.jpg,.jpeg,.svg,.webp"
                    onChange={handleLogoUpload}
                    className="text-sm text-[var(--color-text-muted)] file:mr-3 file:rounded-md file:border-0 file:bg-[var(--color-primary)] file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-white hover:file:opacity-90"
                  />
                  <p className="mt-1 text-xs text-[var(--color-text-muted)]">
                    PNG, JPG, SVG, or WebP. Max 2MB. Recommended: 128x128 to 512x512px (square).
                  </p>
                </div>
              </div>
              <button
                onClick={handleSaveGeneral}
                disabled={saving}
                className="inline-flex items-center gap-2 rounded-md bg-[var(--color-primary)] px-4 py-2 text-sm font-medium text-white transition hover:opacity-90 disabled:opacity-50"
              >
                {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
                Save
              </button>
            </div>
          )}

          {activeTab === "members" && (
            <div className="space-y-4">
              {scimActive && (
                <div className="mb-4 flex items-center gap-2 rounded-lg bg-blue-50 px-4 py-3 text-sm text-blue-800 dark:bg-blue-900/20 dark:text-blue-300">
                  <Info className="h-4 w-4 shrink-0" />
                  <span>
                    {membersReadOnly
                      ? "Members are automatically synced from your identity provider via SCIM. To manage members, use your IdP."
                      : "Members are synced via SCIM. As a super admin you can still manage members directly."}
                  </span>
                </div>
              )}
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-semibold text-[var(--color-text)]">Members ({members.length})</h3>
                {!membersReadOnly && (
                  <button
                    data-testid="invite-member-btn"
                    onClick={() => setShowInviteForm(!showInviteForm)}
                    className="inline-flex items-center gap-2 rounded-md bg-[var(--color-primary)] px-4 py-2 text-sm font-medium text-white transition hover:opacity-90"
                  >
                    <UserPlus className="h-4 w-4" />
                    Invite Member
                  </button>
                )}
              </div>

              {showInviteForm && !membersReadOnly && (
                <div
                  data-testid="invite-form"
                  className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] p-4"
                >
                  <div className="flex flex-wrap items-end gap-3">
                    <div className="flex-1 min-w-[200px]">
                      <label className="mb-1 flex items-center text-sm font-medium text-[var(--color-text)]">
                        Email
                        <InfoTooltip text="Enter the email of an existing CollabMark user to add to the organization" />
                      </label>
                      <div className="relative">
                        <Mail className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--color-text-muted)]" />
                        <input
                          type="email"
                          value={inviteEmail}
                          onChange={(e) => setInviteEmail(e.target.value)}
                          placeholder="colleague@example.com"
                          className="w-full rounded-md border border-[var(--color-border)] bg-[var(--color-bg)] py-2 pl-9 pr-3 text-sm text-[var(--color-text)] outline-none focus:border-[var(--color-primary)]"
                        />
                      </div>
                    </div>
                    <div className="w-32">
                      <label className="mb-1 flex items-center text-sm font-medium text-[var(--color-text)]">
                        Role
                        <InfoTooltip text="Admin members can manage organization settings; Members have standard access" />
                      </label>
                      <select
                        value={inviteRole}
                        onChange={(e) => setInviteRole(e.target.value as "admin" | "member")}
                        className="w-full rounded-md border border-[var(--color-border)] bg-[var(--color-bg)] px-3 py-2 text-sm text-[var(--color-text)] outline-none focus:border-[var(--color-primary)]"
                      >
                        <option value="member">Member</option>
                        <option value="admin">Admin</option>
                      </select>
                    </div>
                    <div className="flex gap-2">
                      <button
                        onClick={handleInvite}
                        disabled={!inviteEmail.trim() || inviting}
                        className="inline-flex items-center gap-1 rounded-md bg-[var(--color-primary)] px-4 py-2 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50"
                      >
                        {inviting ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                        Send Invite
                      </button>
                      <button
                        onClick={() => {
                          setShowInviteForm(false);
                          setInviteEmail("");
                        }}
                        className="rounded-md border border-[var(--color-border)] px-4 py-2 text-sm font-medium text-[var(--color-text)] hover:bg-[var(--color-bg)]"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                </div>
              )}

              <ul className="divide-y divide-[var(--color-border)]">
                {members.map((member) => {
                  const isSsoUser = member.auth_provider === "saml" || member.auth_provider === "oidc";
                  return (
                    <li
                      key={member.user_id}
                      data-testid={`member-row-${member.user_id}`}
                      className="flex items-center justify-between py-4 first:pt-0 last:pb-0"
                    >
                      <div className="flex items-center gap-3">
                        <UserAvatar url={member.avatar_url} name={member.user_name} size="md" className="shrink-0" />
                        <div>
                          <div className="flex items-center gap-2">
                            <p className="font-medium text-[var(--color-text)]">{member.user_name}</p>
                            {member.is_super_admin && (
                              <span className="inline-flex items-center gap-1 rounded-full bg-indigo-100 px-2 py-0.5 text-xs font-semibold text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-300">
                                <Shield className="h-3 w-3" />
                                Super Admin
                              </span>
                            )}
                          </div>
                          <p className="text-sm text-[var(--color-text-muted)]">{member.user_email}</p>
                          <div className="flex items-center gap-2 text-xs text-[var(--color-text-muted)]">
                            <span>Joined {formatDateShort(member.joined_at)}</span>
                            {isSsoUser && (
                              <span className="inline-flex items-center gap-0.5 rounded bg-gray-100 px-1.5 py-0.5 text-[10px] font-medium text-gray-600 dark:bg-gray-700 dark:text-gray-400">
                                SSO
                              </span>
                            )}
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        {member.is_super_admin ? (
                          <span className="text-sm font-medium text-indigo-600 dark:text-indigo-400">
                            Platform Admin
                          </span>
                        ) : membersReadOnly ? (
                          <span className="text-sm text-[var(--color-text-muted)] capitalize">{member.role}</span>
                        ) : (
                          <>
                            <select
                              value={member.role}
                              onChange={(e) => handleUpdateRole(member.user_id, e.target.value as "admin" | "member")}
                              disabled={updatingRole === member.user_id}
                              className="rounded-md border border-[var(--color-border)] bg-[var(--color-bg)] px-3 py-1.5 text-sm text-[var(--color-text)] outline-none focus:border-[var(--color-primary)] disabled:opacity-50"
                            >
                              <option value="member">Member</option>
                              <option value="admin">Admin</option>
                            </select>
                            <button
                              onClick={() => handleRemoveMember(member.user_id)}
                              disabled={member.user_id === user?.id || removing === member.user_id}
                              title={member.user_id === user?.id ? "Cannot remove yourself" : "Remove member"}
                              className="rounded p-1.5 text-[var(--color-text-muted)] hover:bg-red-50 hover:text-red-600 disabled:cursor-not-allowed disabled:opacity-40 dark:hover:bg-red-900/20"
                            >
                              {removing === member.user_id ? (
                                <Loader2 className="h-4 w-4 animate-spin" />
                              ) : (
                                <Trash2 className="h-4 w-4" />
                              )}
                            </button>
                          </>
                        )}
                      </div>
                    </li>
                  );
                })}
              </ul>
            </div>
          )}

          {activeTab === "sso" && (
            <div className="space-y-6">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-lg font-semibold text-[var(--color-text)]">SSO Configuration</h3>
                  <p className="mt-1 text-sm text-[var(--color-text-muted)]">
                    Configure SAML or OIDC for single sign-on
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <span
                    className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium ${
                      ssoConfig?.enabled
                        ? "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400"
                        : ssoConfig
                          ? "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400"
                          : "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400"
                    }`}
                  >
                    {ssoConfig?.enabled ? (
                      <>
                        <CheckCircle className="h-3.5 w-3.5" />
                        Configured & Enabled
                      </>
                    ) : ssoConfig ? (
                      <>
                        <XCircle className="h-3.5 w-3.5" />
                        Configured (disabled)
                      </>
                    ) : (
                      "Not configured"
                    )}
                  </span>
                  {ssoConfig?.enabled && !ssoEditMode && (
                    <button
                      onClick={() => setSsoEditMode(true)}
                      className="rounded-md border border-[var(--color-border)] px-3 py-1.5 text-sm font-medium text-[var(--color-text)] hover:bg-[var(--color-bg)]"
                    >
                      Edit
                    </button>
                  )}
                </div>
              </div>

              {ssoConfig?.enabled && !ssoEditMode ? (
                <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] px-4 py-3 text-sm text-[var(--color-text-muted)]">
                  Protocol: {ssoConfig.protocol === "saml" ? "SAML 2.0" : "OIDC"}
                </div>
              ) : (
                <form
                  data-testid="sso-form"
                  onSubmit={(e) => {
                    e.preventDefault();
                    handleSaveSso();
                  }}
                  className="space-y-4"
                >
                  <div className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      id="sso-enabled"
                      checked={ssoEnabled}
                      onChange={(e) => setSsoEnabled(e.target.checked)}
                      className="h-4 w-4 rounded border-[var(--color-border)] text-[var(--color-primary)] focus:ring-[var(--color-primary)]"
                    />
                    <label
                      htmlFor="sso-enabled"
                      className="flex items-center text-sm font-medium text-[var(--color-text)]"
                    >
                      Enable SSO
                      <InfoTooltip text="When enabled, users with verified domain emails will be redirected to your IdP" />
                    </label>
                  </div>

                  <div>
                    <label className="mb-1 flex items-center text-sm font-medium text-[var(--color-text)]">
                      Protocol
                      <InfoTooltip text="Choose SAML 2.0 or OpenID Connect based on your identity provider" />
                    </label>
                    <select
                      value={ssoProtocol}
                      onChange={(e) => setSsoProtocol(e.target.value as "saml" | "oidc")}
                      className="w-full rounded-md border border-[var(--color-border)] bg-[var(--color-bg)] px-3 py-2 text-sm text-[var(--color-text)] outline-none focus:border-[var(--color-primary)]"
                    >
                      <option value="saml">SAML 2.0</option>
                      <option value="oidc">OIDC</option>
                    </select>
                  </div>

                  {ssoProtocol === "saml" ? (
                    <>
                      <div>
                        <label className="mb-1 flex items-center text-sm font-medium text-[var(--color-text)]">
                          IdP Entity ID
                          <InfoTooltip text="The unique identifier of your identity provider (from IdP metadata)" />
                        </label>
                        <input
                          value={idpEntityId}
                          onChange={(e) => setIdpEntityId(e.target.value)}
                          placeholder="https://idp.example.com/entity"
                          className="w-full rounded-md border border-[var(--color-border)] bg-[var(--color-bg)] px-3 py-2 text-sm text-[var(--color-text)] outline-none focus:border-[var(--color-primary)]"
                        />
                      </div>
                      <div>
                        <label className="mb-1 flex items-center text-sm font-medium text-[var(--color-text)]">
                          IdP SSO URL
                          <InfoTooltip text="The SSO login URL provided by your identity provider" />
                        </label>
                        <input
                          value={idpSsoUrl}
                          onChange={(e) => setIdpSsoUrl(e.target.value)}
                          placeholder="https://idp.example.com/sso"
                          className="w-full rounded-md border border-[var(--color-border)] bg-[var(--color-bg)] px-3 py-2 text-sm text-[var(--color-text)] outline-none focus:border-[var(--color-primary)]"
                        />
                      </div>
                      <div>
                        <label className="mb-1 flex items-center text-sm font-medium text-[var(--color-text)]">
                          IdP Certificate (X.509)
                          <InfoTooltip text="X.509 certificate from your IdP for SAML assertion verification" />
                        </label>
                        <textarea
                          value={idpCertificate}
                          onChange={(e) => setIdpCertificate(e.target.value)}
                          placeholder="-----BEGIN CERTIFICATE-----..."
                          rows={4}
                          className="w-full rounded-md border border-[var(--color-border)] bg-[var(--color-bg)] px-3 py-2 font-mono text-sm text-[var(--color-text)] outline-none focus:border-[var(--color-primary)]"
                        />
                      </div>
                      <div>
                        <label className="mb-1 flex items-center text-sm font-medium text-[var(--color-text)]">
                          SP Entity ID
                          <InfoTooltip text="CollabMark's identifier as a service provider (configure in your IdP)" />
                        </label>
                        <input
                          value={spEntityId}
                          onChange={(e) => setSpEntityId(e.target.value)}
                          placeholder="https://app.example.com/saml"
                          className="w-full rounded-md border border-[var(--color-border)] bg-[var(--color-bg)] px-3 py-2 text-sm text-[var(--color-text)] outline-none focus:border-[var(--color-primary)]"
                        />
                      </div>
                      <div>
                        <label className="mb-1 flex items-center text-sm font-medium text-[var(--color-text)]">
                          SP ACS URL
                          <InfoTooltip text="CollabMark's Assertion Consumer Service URL (configure in your IdP)" />
                        </label>
                        <input
                          value={spAcsUrl}
                          onChange={(e) => setSpAcsUrl(e.target.value)}
                          placeholder="https://app.example.com/api/auth/saml/acs"
                          className="w-full rounded-md border border-[var(--color-border)] bg-[var(--color-bg)] px-3 py-2 text-sm text-[var(--color-text)] outline-none focus:border-[var(--color-primary)]"
                        />
                      </div>
                    </>
                  ) : (
                    <>
                      <div>
                        <label className="mb-1 flex items-center text-sm font-medium text-[var(--color-text)]">
                          Discovery URL
                          <InfoTooltip text="Your OIDC provider's .well-known/openid-configuration URL" />
                        </label>
                        <input
                          value={oidcDiscoveryUrl}
                          onChange={(e) => setOidcDiscoveryUrl(e.target.value)}
                          placeholder="https://idp.example.com/.well-known/openid-configuration"
                          className="w-full rounded-md border border-[var(--color-border)] bg-[var(--color-bg)] px-3 py-2 text-sm text-[var(--color-text)] outline-none focus:border-[var(--color-primary)]"
                        />
                      </div>
                      <div>
                        <label className="mb-1 flex items-center text-sm font-medium text-[var(--color-text)]">
                          Client ID
                          <InfoTooltip text="The OAuth client ID registered with your OIDC provider" />
                        </label>
                        <input
                          value={oidcClientId}
                          onChange={(e) => setOidcClientId(e.target.value)}
                          placeholder="your-client-id"
                          className="w-full rounded-md border border-[var(--color-border)] bg-[var(--color-bg)] px-3 py-2 text-sm text-[var(--color-text)] outline-none focus:border-[var(--color-primary)]"
                        />
                      </div>
                      <div>
                        <label className="mb-1 flex items-center text-sm font-medium text-[var(--color-text)]">
                          Client Secret
                          <InfoTooltip text="The OAuth client secret (leave blank to keep existing)" />
                        </label>
                        <input
                          type="password"
                          value={oidcClientSecret}
                          onChange={(e) => setOidcClientSecret(e.target.value)}
                          placeholder="Leave blank to keep existing"
                          className="w-full rounded-md border border-[var(--color-border)] bg-[var(--color-bg)] px-3 py-2 text-sm text-[var(--color-text)] outline-none focus:border-[var(--color-primary)]"
                        />
                      </div>
                    </>
                  )}

                  <div className="flex gap-2">
                    <button
                      type="submit"
                      data-testid="sso-save-btn"
                      disabled={savingSso}
                      className="inline-flex items-center gap-2 rounded-md bg-[var(--color-primary)] px-4 py-2 text-sm font-medium text-white transition hover:opacity-90 disabled:opacity-50"
                    >
                      {savingSso ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
                      Save Configuration
                    </button>
                    {ssoEditMode && (
                      <button
                        type="button"
                        onClick={() => setSsoEditMode(false)}
                        className="rounded-md border border-[var(--color-border)] px-4 py-2 text-sm font-medium text-[var(--color-text)] hover:bg-[var(--color-bg)]"
                      >
                        Cancel
                      </button>
                    )}
                  </div>
                </form>
              )}

              <hr className="border-[var(--color-border)]" />

              <div data-testid="scim-section">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-lg font-semibold text-[var(--color-text)]">SCIM Provisioning</h3>
                    <p className="mt-1 text-sm text-[var(--color-text-muted)]">
                      Automatically sync users from your identity provider
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <span
                      data-testid="scim-status"
                      className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium ${
                        scimEnabled
                          ? "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400"
                          : "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400"
                      }`}
                    >
                      {scimEnabled ? (
                        <>
                          <CheckCircle className="h-3.5 w-3.5" />
                          Active
                        </>
                      ) : (
                        "Inactive"
                      )}
                    </span>
                    {scimEnabled && !scimEditMode && (
                      <button
                        onClick={() => setScimEditMode(true)}
                        className="rounded-md border border-[var(--color-border)] px-3 py-1.5 text-sm font-medium text-[var(--color-text)] hover:bg-[var(--color-bg)]"
                      >
                        Edit
                      </button>
                    )}
                  </div>
                </div>

                {scimEnabled && !scimEditMode ? (
                  <div className="mt-4 space-y-4">
                    <div>
                      <label className="mb-1 flex items-center text-sm font-medium text-[var(--color-text)]">
                        SCIM Endpoint URL
                        <InfoTooltip text="Copy this URL into your IdP's SCIM provisioning configuration" />
                      </label>
                      <div className="flex items-center gap-2">
                        <input
                          readOnly
                          data-testid="scim-endpoint-url"
                          value={`${window.location.origin}/scim/v2/Users`}
                          className="flex-1 rounded-md border border-[var(--color-border)] bg-[var(--color-bg)] px-3 py-2 font-mono text-sm text-[var(--color-text-muted)]"
                        />
                        <button
                          data-testid="copy-scim-url"
                          onClick={() => handleCopyScim(`${window.location.origin}/scim/v2/Users`, "url")}
                          className="inline-flex items-center gap-1 rounded-md border border-[var(--color-border)] px-3 py-2 text-sm text-[var(--color-text-muted)] hover:bg-[var(--color-bg)] hover:text-[var(--color-text)]"
                        >
                          <ClipboardCopy className="h-4 w-4" />
                          {scimCopied === "url" ? "Copied!" : "Copy"}
                        </button>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="mt-4 space-y-4">
                    <div>
                      <label className="mb-1 flex items-center text-sm font-medium text-[var(--color-text)]">
                        SCIM Endpoint URL
                        <InfoTooltip text="Copy this URL into your IdP's SCIM provisioning configuration" />
                      </label>
                      <div className="flex items-center gap-2">
                        <input
                          readOnly
                          data-testid="scim-endpoint-url"
                          value={`${window.location.origin}/scim/v2/Users`}
                          className="flex-1 rounded-md border border-[var(--color-border)] bg-[var(--color-bg)] px-3 py-2 font-mono text-sm text-[var(--color-text-muted)]"
                        />
                        <button
                          data-testid="copy-scim-url"
                          onClick={() => handleCopyScim(`${window.location.origin}/scim/v2/Users`, "url")}
                          className="inline-flex items-center gap-1 rounded-md border border-[var(--color-border)] px-3 py-2 text-sm text-[var(--color-text-muted)] hover:bg-[var(--color-bg)] hover:text-[var(--color-text)]"
                        >
                          <ClipboardCopy className="h-4 w-4" />
                          {scimCopied === "url" ? "Copied!" : "Copy"}
                        </button>
                      </div>
                    </div>

                    {scimToken && (
                      <div
                        data-testid="scim-token-display"
                        className="rounded-lg border border-amber-300 bg-amber-50 p-4 dark:border-amber-700 dark:bg-amber-900/20"
                      >
                        <p className="mb-2 text-sm font-medium text-amber-800 dark:text-amber-300">
                          Copy this token now -- it will not be shown again.
                        </p>
                        <div className="flex items-center gap-2">
                          <code className="flex-1 rounded bg-white px-3 py-2 font-mono text-sm text-amber-900 dark:bg-gray-900 dark:text-amber-200">
                            {scimToken}
                          </code>
                          <button
                            data-testid="copy-scim-token"
                            onClick={() => handleCopyScim(scimToken, "token")}
                            className="inline-flex items-center gap-1 rounded-md border border-amber-400 px-3 py-2 text-sm text-amber-800 hover:bg-amber-100 dark:border-amber-600 dark:text-amber-200 dark:hover:bg-amber-900/40"
                          >
                            <ClipboardCopy className="h-4 w-4" />
                            {scimCopied === "token" ? "Copied!" : "Copy"}
                          </button>
                        </div>
                      </div>
                    )}

                    <div className="flex gap-2">
                      <button
                        data-testid="generate-scim-token"
                        onClick={handleGenerateScimToken}
                        disabled={generatingToken}
                        className="inline-flex items-center gap-2 rounded-md bg-[var(--color-primary)] px-4 py-2 text-sm font-medium text-white transition hover:opacity-90 disabled:opacity-50"
                      >
                        {generatingToken ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                          <RefreshCw className="h-4 w-4" />
                        )}
                        {scimEnabled ? "Regenerate Token" : "Generate Token"}
                      </button>
                      {scimEnabled && (
                        <button
                          data-testid="revoke-scim-token"
                          onClick={handleRevokeScimToken}
                          disabled={revokingToken}
                          className="inline-flex items-center gap-2 rounded-md border border-red-300 px-4 py-2 text-sm font-medium text-red-700 transition hover:bg-red-50 disabled:opacity-50 dark:border-red-700 dark:text-red-400 dark:hover:bg-red-900/20"
                        >
                          {revokingToken ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                          ) : (
                            <Trash2 className="h-4 w-4" />
                          )}
                          Revoke Token
                        </button>
                      )}
                      {scimEditMode && (
                        <button
                          onClick={() => setScimEditMode(false)}
                          className="rounded-md border border-[var(--color-border)] px-4 py-2 text-sm font-medium text-[var(--color-text)] hover:bg-[var(--color-bg)]"
                        >
                          Cancel
                        </button>
                      )}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
