/**
 * Tests for the useAuth Zustand store.
 *
 * Validates login state management, fetchUser success/failure,
 * and logout behavior.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { useAuth } from "./useAuth";

vi.mock("../lib/api", () => ({
  authApi: {
    getMe: vi.fn(),
    logout: vi.fn(),
  },
}));

import { authApi } from "../lib/api";

describe("useAuth store", () => {
  beforeEach(() => {
    useAuth.setState({ user: null, loading: true });
    vi.clearAllMocks();
  });

  it("should start with null user and loading true", () => {
    const state = useAuth.getState();
    expect(state.user).toBeNull();
    expect(state.loading).toBe(true);
  });

  it("should set user on successful fetchUser", async () => {
    const mockUser = {
      id: "user-1",
      email: "test@example.com",
      name: "Test User",
      avatar_url: null,
      created_at: "2026-01-01T00:00:00Z",
    };
    vi.mocked(authApi.getMe).mockResolvedValue({ data: mockUser } as never);

    await useAuth.getState().fetchUser();

    const state = useAuth.getState();
    expect(state.user).toEqual(mockUser);
    expect(state.loading).toBe(false);
  });

  it("should set user to null on failed fetchUser", async () => {
    vi.mocked(authApi.getMe).mockRejectedValue(new Error("Unauthorized"));

    await useAuth.getState().fetchUser();

    const state = useAuth.getState();
    expect(state.user).toBeNull();
    expect(state.loading).toBe(false);
  });

  it("should clear user on logout", async () => {
    useAuth.setState({
      user: {
        id: "user-1",
        email: "test@example.com",
        name: "Test",
        avatar_url: null,
        created_at: "2026-01-01T00:00:00Z",
      },
      loading: false,
    });
    vi.mocked(authApi.logout).mockResolvedValue({} as never);

    await useAuth.getState().logout();

    expect(useAuth.getState().user).toBeNull();
    expect(authApi.logout).toHaveBeenCalledTimes(1);
  });
});
