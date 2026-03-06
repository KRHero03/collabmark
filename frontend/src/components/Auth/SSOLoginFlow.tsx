import { useEffect, useState } from "react";
import { Mail, Loader2, AlertCircle } from "lucide-react";
import { authApi } from "../../lib/api";
import { GoogleLoginButton } from "./GoogleLoginButton";

type DetectState = "idle" | "detecting" | "sso_found" | "no_sso" | "error";

const SSO_ERROR_MESSAGES: Record<string, string> = {
  sso_not_configured: "SSO is not configured for this organization. Please contact your admin.",
  saml_invalid: "SAML authentication failed. Please try again or contact your admin.",
  oidc_config_error: "OIDC configuration error. Please contact your admin.",
  org_not_found: "Organization not found. Please contact your admin.",
};

export function SSOLoginFlow() {
  const [email, setEmail] = useState("");
  const [state, setState] = useState<DetectState>("idle");
  const [orgName, setOrgName] = useState("");
  const [errorMsg, setErrorMsg] = useState("");
  const [noSsoMsg, setNoSsoMsg] = useState("");

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const errorCode = params.get("error");
    if (errorCode && SSO_ERROR_MESSAGES[errorCode]) {
      setErrorMsg(SSO_ERROR_MESSAGES[errorCode]);
      setState("error");
      window.history.replaceState({}, "", window.location.pathname);
    }
  }, []);

  const handleDetect = async () => {
    const trimmed = email.trim().toLowerCase();
    if (!trimmed || !trimmed.includes("@")) {
      setErrorMsg("Please enter a valid email address.");
      setState("error");
      return;
    }
    setState("detecting");
    setErrorMsg("");
    setNoSsoMsg("");
    try {
      const { data } = await authApi.detectSSO(trimmed);
      if (data.sso && data.org_id && data.protocol) {
        setOrgName(data.org_name || "your organization");
        setState("sso_found");
        window.location.href = `/api/auth/sso/${data.protocol}/login/${data.org_id}`;
      } else {
        const domain = trimmed.split("@")[1];
        setNoSsoMsg(
          `No SSO configured for "${domain}". Your organization may not be onboarded yet. Please sign in with Google or contact your admin.`,
        );
        setState("no_sso");
      }
    } catch {
      setNoSsoMsg("Could not verify your email domain. Please try signing in with Google instead.");
      setState("no_sso");
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") handleDetect();
  };

  if (state === "sso_found") {
    return (
      <div className="flex flex-col items-center gap-3 text-center" data-testid="sso-redirecting">
        <Loader2 className="h-6 w-6 animate-spin text-[var(--color-primary)]" />
        <p className="text-sm text-[var(--color-text-muted)]">
          Redirecting to <strong>{orgName}</strong> for sign-in...
        </p>
      </div>
    );
  }

  return (
    <div className="flex w-full max-w-sm flex-col gap-4" data-testid="sso-login-flow">
      <div className="relative">
        <Mail className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--color-text-muted)]" />
        <input
          type="email"
          placeholder="Enter your work email"
          value={email}
          onChange={(e) => {
            setEmail(e.target.value);
            if (state === "no_sso" || state === "error") {
              setState("idle");
              setNoSsoMsg("");
              setErrorMsg("");
            }
          }}
          onKeyDown={handleKeyDown}
          className="w-full rounded-lg border border-[var(--color-border)] bg-white py-3 pl-10 pr-4 text-sm shadow-sm transition focus:border-[var(--color-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]/20 dark:bg-[var(--color-surface)]"
          data-testid="sso-email-input"
        />
      </div>

      {state === "error" && errorMsg && (
        <div
          className="flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 p-3 dark:border-red-800 dark:bg-red-950"
          data-testid="sso-error"
        >
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-red-500" />
          <p className="text-xs text-red-600 dark:text-red-400">{errorMsg}</p>
        </div>
      )}

      <button
        onClick={handleDetect}
        disabled={state === "detecting"}
        className="flex items-center justify-center gap-2 rounded-lg bg-[var(--color-primary)] px-6 py-3 text-sm font-medium text-white shadow-sm transition hover:opacity-90 disabled:opacity-50"
        data-testid="sso-continue-btn"
      >
        {state === "detecting" ? (
          <>
            <Loader2 className="h-4 w-4 animate-spin" />
            Checking...
          </>
        ) : (
          "Continue with email"
        )}
      </button>

      {state === "no_sso" && (
        <div className="flex flex-col items-center gap-3" data-testid="sso-fallback">
          <div
            className="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 p-3 dark:border-amber-800 dark:bg-amber-950"
            data-testid="sso-no-org-message"
          >
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-amber-500" />
            <p className="text-xs text-amber-700 dark:text-amber-400">{noSsoMsg}</p>
          </div>
          <div className="flex w-full items-center gap-3">
            <div className="h-px flex-1 bg-[var(--color-border)]" />
            <span className="text-xs text-[var(--color-text-muted)]">or</span>
            <div className="h-px flex-1 bg-[var(--color-border)]" />
          </div>
          <GoogleLoginButton />
        </div>
      )}

      {state === "idle" && (
        <div className="flex flex-col items-center gap-3">
          <div className="flex w-full items-center gap-3">
            <div className="h-px flex-1 bg-[var(--color-border)]" />
            <span className="text-xs text-[var(--color-text-muted)]">or</span>
            <div className="h-px flex-1 bg-[var(--color-border)]" />
          </div>
          <GoogleLoginButton />
        </div>
      )}
    </div>
  );
}
