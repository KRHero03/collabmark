import { useEffect, useState } from "react";
import { useParams } from "react-router";
import {
  CheckCircle,
  ClipboardCopy,
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
                <label className="mb-1 block text-sm font-medium text-[var(--color-text)]">Organization Name</label>
                <input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="w-full rounded-md border border-[var(--color-border)] bg-[var(--color-bg)] px-3 py-2 text-sm text-[var(--color-text)] outline-none focus:border-[var(--color-primary)] focus:ring-1 focus:ring-[var(--color-primary)]"
                />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-[var(--color-text)]">Slug</label>
                <input
                  value={slug}
                  onChange={(e) => setSlug(e.target.value)}
                  className="w-full rounded-md border border-[var(--color-border)] bg-[var(--color-bg)] px-3 py-2 text-sm text-[var(--color-text)] outline-none focus:border-[var(--color-primary)] focus:ring-1 focus:ring-[var(--color-primary)]"
                />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-[var(--color-text)]">
                  Verified Domains (comma-separated)
                </label>
                <input
                  value={verifiedDomains}
                  onChange={(e) => setVerifiedDomains(e.target.value)}
                  placeholder="example.com, corp.example.com"
                  className="w-full rounded-md border border-[var(--color-border)] bg-[var(--color-bg)] px-3 py-2 text-sm text-[var(--color-text)] outline-none focus:border-[var(--color-primary)] focus:ring-1 focus:ring-[var(--color-primary)]"
                />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-[var(--color-text)]">Plan</label>
                <input
                  value={plan}
                  onChange={(e) => setPlan(e.target.value)}
                  placeholder="free, pro, enterprise"
                  className="w-full rounded-md border border-[var(--color-border)] bg-[var(--color-bg)] px-3 py-2 text-sm text-[var(--color-text)] outline-none focus:border-[var(--color-primary)] focus:ring-1 focus:ring-[var(--color-primary)]"
                />
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
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-semibold text-[var(--color-text)]">Members ({members.length})</h3>
                <button
                  data-testid="invite-member-btn"
                  onClick={() => setShowInviteForm(!showInviteForm)}
                  className="inline-flex items-center gap-2 rounded-md bg-[var(--color-primary)] px-4 py-2 text-sm font-medium text-white transition hover:opacity-90"
                >
                  <UserPlus className="h-4 w-4" />
                  Invite Member
                </button>
              </div>

              {showInviteForm && (
                <div
                  data-testid="invite-form"
                  className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] p-4"
                >
                  <div className="flex flex-wrap items-end gap-3">
                    <div className="flex-1 min-w-[200px]">
                      <label className="mb-1 block text-sm font-medium text-[var(--color-text)]">Email</label>
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
                      <label className="mb-1 block text-sm font-medium text-[var(--color-text)]">Role</label>
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
                {members.map((member) => (
                  <li
                    key={member.user_id}
                    data-testid={`member-row-${member.user_id}`}
                    className="flex items-center justify-between py-4 first:pt-0 last:pb-0"
                  >
                    <div className="flex items-center gap-3">
                      <UserAvatar url={member.avatar_url} name={member.user_name} size="md" className="shrink-0" />
                      <div>
                        <p className="font-medium text-[var(--color-text)]">{member.user_name}</p>
                        <p className="text-sm text-[var(--color-text-muted)]">{member.user_email}</p>
                        <p className="text-xs text-[var(--color-text-muted)]">
                          Joined {formatDateShort(member.joined_at)}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
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
                    </div>
                  </li>
                ))}
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
                </div>
              </div>

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
                  <label htmlFor="sso-enabled" className="text-sm font-medium text-[var(--color-text)]">
                    Enable SSO
                  </label>
                </div>

                <div>
                  <label className="mb-1 block text-sm font-medium text-[var(--color-text)]">Protocol</label>
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
                      <label className="mb-1 block text-sm font-medium text-[var(--color-text)]">IdP Entity ID</label>
                      <input
                        value={idpEntityId}
                        onChange={(e) => setIdpEntityId(e.target.value)}
                        placeholder="https://idp.example.com/entity"
                        className="w-full rounded-md border border-[var(--color-border)] bg-[var(--color-bg)] px-3 py-2 text-sm text-[var(--color-text)] outline-none focus:border-[var(--color-primary)]"
                      />
                    </div>
                    <div>
                      <label className="mb-1 block text-sm font-medium text-[var(--color-text)]">IdP SSO URL</label>
                      <input
                        value={idpSsoUrl}
                        onChange={(e) => setIdpSsoUrl(e.target.value)}
                        placeholder="https://idp.example.com/sso"
                        className="w-full rounded-md border border-[var(--color-border)] bg-[var(--color-bg)] px-3 py-2 text-sm text-[var(--color-text)] outline-none focus:border-[var(--color-primary)]"
                      />
                    </div>
                    <div>
                      <label className="mb-1 block text-sm font-medium text-[var(--color-text)]">
                        IdP Certificate (X.509)
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
                      <label className="mb-1 block text-sm font-medium text-[var(--color-text)]">SP Entity ID</label>
                      <input
                        value={spEntityId}
                        onChange={(e) => setSpEntityId(e.target.value)}
                        placeholder="https://app.example.com/saml"
                        className="w-full rounded-md border border-[var(--color-border)] bg-[var(--color-bg)] px-3 py-2 text-sm text-[var(--color-text)] outline-none focus:border-[var(--color-primary)]"
                      />
                    </div>
                    <div>
                      <label className="mb-1 block text-sm font-medium text-[var(--color-text)]">SP ACS URL</label>
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
                      <label className="mb-1 block text-sm font-medium text-[var(--color-text)]">Discovery URL</label>
                      <input
                        value={oidcDiscoveryUrl}
                        onChange={(e) => setOidcDiscoveryUrl(e.target.value)}
                        placeholder="https://idp.example.com/.well-known/openid-configuration"
                        className="w-full rounded-md border border-[var(--color-border)] bg-[var(--color-bg)] px-3 py-2 text-sm text-[var(--color-text)] outline-none focus:border-[var(--color-primary)]"
                      />
                    </div>
                    <div>
                      <label className="mb-1 block text-sm font-medium text-[var(--color-text)]">Client ID</label>
                      <input
                        value={oidcClientId}
                        onChange={(e) => setOidcClientId(e.target.value)}
                        placeholder="your-client-id"
                        className="w-full rounded-md border border-[var(--color-border)] bg-[var(--color-bg)] px-3 py-2 text-sm text-[var(--color-text)] outline-none focus:border-[var(--color-primary)]"
                      />
                    </div>
                    <div>
                      <label className="mb-1 block text-sm font-medium text-[var(--color-text)]">Client Secret</label>
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

                <button
                  type="submit"
                  data-testid="sso-save-btn"
                  disabled={savingSso}
                  className="inline-flex items-center gap-2 rounded-md bg-[var(--color-primary)] px-4 py-2 text-sm font-medium text-white transition hover:opacity-90 disabled:opacity-50"
                >
                  {savingSso ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
                  Save Configuration
                </button>
              </form>

              <hr className="border-[var(--color-border)]" />

              <div data-testid="scim-section">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-lg font-semibold text-[var(--color-text)]">SCIM Provisioning</h3>
                    <p className="mt-1 text-sm text-[var(--color-text-muted)]">
                      Automatically sync users from your identity provider
                    </p>
                  </div>
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
                </div>

                <div className="mt-4 space-y-4">
                  <div>
                    <label className="mb-1 block text-sm font-medium text-[var(--color-text)]">SCIM Endpoint URL</label>
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
                        {revokingToken ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}
                        Revoke Token
                      </button>
                    )}
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
