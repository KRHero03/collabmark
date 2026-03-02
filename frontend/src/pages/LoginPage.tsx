import { useEffect } from "react";
import { FileText } from "lucide-react";
import { GoogleLoginButton } from "../components/Auth/GoogleLoginButton";

export function LoginPage() {
  useEffect(() => {
    document.title = "Sign In - CollabMark";
    return () => { document.title = "CollabMark"; };
  }, []);

  return (
    <div className="flex min-h-screen items-center justify-center bg-[var(--color-bg-secondary)]">
      <div className="w-full max-w-md rounded-xl bg-white p-8 shadow-lg">
        <div className="mb-8 text-center">
          <FileText className="mx-auto mb-4 h-12 w-12 text-[var(--color-primary)]" />
          <h1 className="mb-2 text-2xl font-bold">CollabMark</h1>
          <p className="text-[var(--color-text-muted)]">
            Collaborative Markdown editing, made simple.
          </p>
        </div>
        <div className="flex justify-center">
          <GoogleLoginButton />
        </div>
      </div>
    </div>
  );
}
