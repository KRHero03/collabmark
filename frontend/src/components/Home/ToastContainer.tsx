import { CheckCircle, XCircle, X } from "lucide-react";
import { useToast, type ToastPhase } from "../../hooks/useToast";

const phaseClasses: Record<ToastPhase, string> = {
  entering: "translate-x-full opacity-0",
  visible: "translate-x-0 opacity-100",
  exiting: "translate-x-full opacity-0",
};

export function ToastContainer() {
  const { toasts, removeToast } = useToast();

  if (toasts.length === 0) return null;

  return (
    <div className="fixed bottom-4 right-4 z-[60] flex flex-col-reverse gap-2">
      {toasts.map((toast) => (
        <div
          key={toast.id}
          data-testid={`toast-${toast.type}`}
          data-phase={toast.phase}
          className={`flex items-center gap-2 rounded-lg px-4 py-3 text-sm font-medium shadow-lg transition-all duration-300 ease-in-out ${phaseClasses[toast.phase]} ${
            toast.type === "success"
              ? "bg-green-600 text-white"
              : "bg-red-600 text-white"
          }`}
        >
          {toast.type === "success" ? (
            <CheckCircle className="h-4 w-4 shrink-0" />
          ) : (
            <XCircle className="h-4 w-4 shrink-0" />
          )}
          <span>{toast.message}</span>
          <button
            onClick={() => removeToast(toast.id)}
            className="ml-2 shrink-0 rounded p-0.5 transition hover:bg-white/20"
            aria-label="Dismiss"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      ))}
    </div>
  );
}
