import { create } from "zustand";

export type ToastPhase = "entering" | "visible" | "exiting";

export interface Toast {
  id: string;
  message: string;
  type: "success" | "error";
  phase: ToastPhase;
}

let nextId = 1;

const ENTER_DELAY_MS = 50;
const EXIT_ANIMATION_MS = 300;
const AUTO_DISMISS_MS = 4000;

interface ToastState {
  toasts: Toast[];
  addToast: (message: string, type: "success" | "error") => void;
  removeToast: (id: string) => void;
}

export const useToast = create<ToastState>((set, get) => ({
  toasts: [],

  addToast: (message, type) => {
    const id = String(nextId++);
    const toast: Toast = { id, message, type, phase: "entering" };
    set({ toasts: [toast, ...get().toasts] });

    setTimeout(() => {
      set({
        toasts: get().toasts.map((t) =>
          t.id === id ? { ...t, phase: "visible" as ToastPhase } : t,
        ),
      });
    }, ENTER_DELAY_MS);

    setTimeout(() => {
      set({
        toasts: get().toasts.map((t) =>
          t.id === id ? { ...t, phase: "exiting" as ToastPhase } : t,
        ),
      });
      setTimeout(() => {
        set({ toasts: get().toasts.filter((t) => t.id !== id) });
      }, EXIT_ANIMATION_MS);
    }, AUTO_DISMISS_MS);
  },

  removeToast: (id) => {
    const toast = get().toasts.find((t) => t.id === id);
    if (!toast || toast.phase === "exiting") return;

    set({
      toasts: get().toasts.map((t) =>
        t.id === id ? { ...t, phase: "exiting" as ToastPhase } : t,
      ),
    });
    setTimeout(() => {
      set({ toasts: get().toasts.filter((t) => t.id !== id) });
    }, EXIT_ANIMATION_MS);
  },
}));
