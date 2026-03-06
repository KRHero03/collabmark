import { useState } from "react";
import { Mail, Loader2 } from "lucide-react";
import { authApi } from "../../lib/api";
import { GoogleLoginButton } from "./GoogleLoginButton";

type DetectState = "idle" | "detecting" | "sso_found" | "no_sso" | "error";

export function SSOLoginFlow() {
  const [email, setEmail] = useState("");
  const [state, setState] = useState<DetectState>("idle");
  const [orgName, setOrgName] = useState("");
  const [errorMsg, setErrorMsg] = useState("");

  const handleDetect = async () => {
    const trimmed = email.trim().toLowerCase();
    if (!trimmed || !trimmed.includes("@")) {
      setErrorMsg("Please enter a valid email address.");
      setState("error");
      return;
    }
    setState("detecting");
    setErrorMsg("");
    try {
      const { data } = await authApi.detectSSO(trimmed);
      if (data.sso && data.org_id && data.protocol) {
        setOrgName(data.org_name || "your organization");
        setState("sso_found");
        // Redirect to SSO login
        window.location.href = `/api/auth/sso/${data.protocol}/login/${data.org_id}`;
      } else {
        setState("no_sso");
      }
    } catch {
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
            if (state === "no_sso" || state === "error") setState("idle");
          }}
          onKeyDown={handleKeyDown}
          className="w-full rounded-lg border border-[var(--color-border)] bg-white py-3 pl-10 pr-4 text-sm shadow-sm transition focus:border-[var(--color-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]/20 dark:bg-[var(--color-surface)]"
          data-testid="sso-email-input"
        />
      </div>

      {state === "error" && (
        <p className="text-xs text-red-500" data-testid="sso-error">{errorMsg}</p>
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
