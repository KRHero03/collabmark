import { useCallback, useEffect, useState } from "react";
import { FileText, Terminal, ArrowLeft, Moon, Sun, CheckCircle2, XCircle } from "lucide-react";
import { SSOLoginFlow } from "../components/Auth/SSOLoginFlow";
import { useAuth } from "../hooks/useAuth";

const CLI_PORT_KEY = "cli_login_port";

type PageStatus = "login" | "success" | "error";

export function CLILoginPage() {
  const { user, loading } = useAuth();
  const [dark, setDark] = useState(() => document.documentElement.classList.contains("dark"));
  const [status] = useState<PageStatus>(() => {
    const params = new URLSearchParams(window.location.search);
    const s = params.get("status");
    if (s === "success") return "success";
    if (s === "error") return "error";
    return "login";
  });

  const toggleDark = useCallback(() => {
    const next = !dark;
    setDark(next);
    document.documentElement.classList.toggle("dark", next);
    localStorage.setItem("theme", next ? "dark" : "light");
  }, [dark]);

  useEffect(() => {
    const saved = localStorage.getItem("theme");
    if (saved === "dark" && !dark) {
      document.documentElement.classList.add("dark");
      setDark(true);
    }
  }, []);

  useEffect(() => {
    document.title = "CLI Login - CollabMark";
    const params = new URLSearchParams(window.location.search);
    const port = params.get("port");
    if (port && /^\d+$/.test(port)) {
      sessionStorage.setItem(CLI_PORT_KEY, JSON.stringify({ port, ts: Date.now() }));
    }
    if (window.location.search) {
      window.history.replaceState({}, "", window.location.pathname);
    }
    return () => {
      document.title = "CollabMark";
    };
  }, []);

  useEffect(() => {
    if (loading || !user || status !== "login") return;
    const raw = sessionStorage.getItem(CLI_PORT_KEY);
    if (!raw) return;
    try {
      const { port } = JSON.parse(raw);
      if (port) {
        sessionStorage.removeItem(CLI_PORT_KEY);
        window.location.href = `/api/auth/cli/complete?port=${port}`;
      }
    } catch {
      sessionStorage.removeItem(CLI_PORT_KEY);
    }
  }, [user, loading, status]);

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[var(--color-bg)]">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-[var(--color-primary)] border-t-transparent" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[var(--color-bg)]">
      {/* Sticky Top Bar */}
      <nav className="fixed inset-x-0 top-0 z-50 flex h-16 items-center justify-between border-b border-[var(--color-border)] bg-gradient-to-r from-white via-white to-blue-50/60 px-4 shadow-sm backdrop-blur-lg dark:from-[#0f172a]/90 dark:via-[#0f172a]/90 dark:to-indigo-950/40 md:px-8">
        <a
          href="/"
          className="flex items-center gap-2 text-lg font-bold no-underline text-inherit transition hover:opacity-80"
        >
          <FileText className="h-6 w-6 text-[var(--color-primary)]" />
          <span>CollabMark</span>
        </a>
        <div className="flex items-center gap-2">
          <button
            onClick={toggleDark}
            className="rounded-lg p-2 text-[var(--color-text-muted)] transition hover:bg-[var(--color-hover)] hover:text-[var(--color-text)]"
            title={dark ? "Light mode" : "Dark mode"}
            aria-label={dark ? "Switch to light mode" : "Switch to dark mode"}
          >
            {dark ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
          </button>
          <a
            href="/"
            className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm text-[var(--color-text-muted)] transition hover:bg-[var(--color-hover)] hover:text-[var(--color-text)]"
          >
            <ArrowLeft className="h-4 w-4" />
            Home
          </a>
        </div>
      </nav>

      {/* Hero-style background */}
      <section className="relative flex min-h-screen items-center justify-center overflow-hidden px-4 pt-16">
        <div className="animate-gradient absolute inset-0 bg-gradient-to-br from-blue-600 via-indigo-600 to-purple-700 opacity-[0.07] dark:opacity-[0.15]" />
        <div className="animate-float absolute left-[10%] top-[20%] h-64 w-64 rounded-full bg-blue-400/10 blur-3xl dark:bg-blue-400/5" />
        <div
          className="animate-float absolute bottom-[15%] right-[10%] h-80 w-80 rounded-full bg-purple-400/10 blur-3xl dark:bg-purple-400/5"
          style={{ animationDelay: "2s" }}
        />
        <div
          className="animate-float absolute right-[30%] top-[60%] h-48 w-48 rounded-full bg-cyan-400/10 blur-3xl dark:bg-cyan-400/5"
          style={{ animationDelay: "4s" }}
        />

        <div className="relative z-10 mx-auto w-full max-w-lg">
          {/* Terminal illustration */}
          <div className="animate-fade-in-up mb-8" style={{ animationDelay: "0.1s" }}>
            <div className="overflow-hidden rounded-xl border border-[var(--color-border)] bg-white shadow-2xl shadow-black/10 dark:bg-[var(--color-surface)]">
              <div className="flex items-center gap-2 border-b border-[var(--color-border)] px-4 py-3">
                <div className="h-3 w-3 rounded-full bg-red-400" />
                <div className="h-3 w-3 rounded-full bg-yellow-400" />
                <div className="h-3 w-3 rounded-full bg-green-400" />
                <span className="ml-3 text-xs text-[var(--color-text-muted)]">Terminal</span>
              </div>
              <div className="bg-[#1e293b] px-5 py-4 font-mono text-xs leading-6 text-slate-300 sm:text-sm">
                <div>
                  <span className="text-green-400">$</span> collabmark login
                </div>
                {status === "success" ? (
                  <div className="mt-1 text-green-400">&#10003; Authentication successful</div>
                ) : status === "error" ? (
                  <div className="mt-1 text-red-400">&#10007; Authentication failed</div>
                ) : (
                  <>
                    <div className="mt-1 text-slate-400">Opening your browser to log in...</div>
                    <div className="text-slate-400">Waiting for authentication...</div>
                    <div className="mt-1 inline-block">
                      <span className="animate-pulse text-blue-400">_</span>
                    </div>
                  </>
                )}
              </div>
            </div>
          </div>

          {/* Main card -- content depends on status */}
          <div
            className="animate-fade-in-up overflow-hidden rounded-xl border border-[var(--color-border)] bg-white p-8 shadow-2xl shadow-black/10 dark:bg-[var(--color-surface)]"
            style={{ animationDelay: "0.3s" }}
          >
            {status === "success" ? (
              <div className="text-center">
                <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-green-500 to-emerald-600">
                  <CheckCircle2 className="h-7 w-7 text-white" />
                </div>
                <h1 className="mb-2 text-2xl font-extrabold tracking-tight">
                  You're{" "}
                  <span className="bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent dark:from-blue-400 dark:to-purple-400">
                    signed in!
                  </span>
                </h1>
                <p className="text-sm text-[var(--color-text-muted)]">
                  Authentication complete. You can close this tab and return to your terminal.
                </p>
                <p className="mt-2 text-xs text-[var(--color-text-muted)]">
                  Your session is stored securely in your OS keychain.
                </p>
              </div>
            ) : status === "error" ? (
              <div className="text-center">
                <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-red-500 to-rose-600">
                  <XCircle className="h-7 w-7 text-white" />
                </div>
                <h1 className="mb-2 text-2xl font-extrabold tracking-tight">
                  Login{" "}
                  <span className="bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent dark:from-blue-400 dark:to-purple-400">
                    failed
                  </span>
                </h1>
                <p className="text-sm text-[var(--color-text-muted)]">
                  Something went wrong during authentication. Please return to your terminal and try again.
                </p>
              </div>
            ) : (
              <>
                <div className="mb-8 text-center">
                  <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-blue-500 to-indigo-500">
                    <Terminal className="h-7 w-7 text-white" />
                  </div>
                  <h1 className="mb-2 text-2xl font-extrabold tracking-tight">
                    Sign in to{" "}
                    <span className="bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent dark:from-blue-400 dark:to-purple-400">
                      CollabMark CLI
                    </span>
                  </h1>
                  <p className="text-sm text-[var(--color-text-muted)]">
                    Connect your terminal to CollabMark. After signing in, you'll be redirected back automatically.
                  </p>
                </div>
                <div className="flex justify-center">
                  <SSOLoginFlow />
                </div>
              </>
            )}
          </div>

          {/* Footer hint */}
          <p
            className="animate-fade-in-up mt-6 text-center text-xs text-[var(--color-text-muted)]"
            style={{ animationDelay: "0.5s" }}
          >
            Having trouble? Run{" "}
            <code className="rounded bg-[var(--color-bg-secondary)] px-1.5 py-0.5 font-mono text-[var(--color-text)]">
              collabmark login --api-key YOUR_KEY
            </code>{" "}
            as a fallback.
          </p>
        </div>
      </section>
    </div>
  );
}
