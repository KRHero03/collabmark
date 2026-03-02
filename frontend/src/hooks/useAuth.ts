import { create } from "zustand";
import { authApi, type UserProfile } from "../lib/api";

interface AuthState {
  user: UserProfile | null;
  loading: boolean;
  fetchUser: () => Promise<void>;
  logout: () => Promise<void>;
}

export const useAuth = create<AuthState>((set) => ({
  user: null,
  loading: true,

  fetchUser: async () => {
    try {
      const { data } = await authApi.getMe();
      set({ user: data, loading: false });
    } catch {
      set({ user: null, loading: false });
    }
  },

  logout: async () => {
    await authApi.logout();
    set({ user: null });
  },
}));
