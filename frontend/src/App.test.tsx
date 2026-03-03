import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import App from "./App";

const mockFetchUser = vi.fn();

vi.mock("./hooks/useAuth", () => ({
  useAuth: vi.fn(),
}));

vi.mock("./pages/LandingPage", () => ({
  LandingPage: () => <div data-testid="landing-page">LandingPage</div>,
}));

vi.mock("./pages/HomePage", () => ({
  HomePage: () => <div data-testid="home-page">HomePage</div>,
}));

vi.mock("./pages/EditorPage", () => ({
  EditorPage: () => <div data-testid="editor-page">EditorPage</div>,
}));

vi.mock("./pages/SettingsPage", () => ({
  SettingsPage: () => <div data-testid="settings-page">SettingsPage</div>,
}));

vi.mock("./pages/ProfilePage", () => ({
  ProfilePage: () => <div data-testid="profile-page">ProfilePage</div>,
}));

vi.mock("./pages/ApiDocsPage", () => ({
  ApiDocsPage: () => <div data-testid="api-docs-page">ApiDocsPage</div>,
}));

import { useAuth } from "./hooks/useAuth";

describe("App", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  beforeEach(() => {
    vi.mocked(useAuth).mockReturnValue({
      user: null,
      loading: false,
      fetchUser: mockFetchUser,
    });
  });

  it("calls fetchUser on mount", () => {
    render(<App />);
    expect(mockFetchUser).toHaveBeenCalledTimes(1);
  });

  it("shows spinner when loading", () => {
    vi.mocked(useAuth).mockReturnValue({
      user: null,
      loading: true,
      fetchUser: mockFetchUser,
    });
    render(<App />);
    const spinner = document.querySelector(
      ".animate-spin.rounded-full.border-2"
    );
    expect(spinner).toBeInTheDocument();
  });

  it("redirects to /login when not authenticated for protected routes", () => {
    window.history.pushState({}, "", "/edit/test-id");
    render(<App />);
    expect(screen.getByTestId("landing-page")).toBeInTheDocument();
    expect(screen.queryByTestId("editor-page")).not.toBeInTheDocument();
  });

  it("renders HomePage when authenticated at /", () => {
    vi.mocked(useAuth).mockReturnValue({
      user: { id: "u1", email: "u@x.com", name: "User" } as never,
      loading: false,
      fetchUser: mockFetchUser,
    });
    window.history.pushState({}, "", "/");
    render(<App />);
    expect(screen.getByTestId("home-page")).toBeInTheDocument();
    expect(screen.queryByTestId("landing-page")).not.toBeInTheDocument();
  });

  it("renders LandingPage when not authenticated at /", () => {
    window.history.pushState({}, "", "/");
    render(<App />);
    expect(screen.getByTestId("landing-page")).toBeInTheDocument();
    expect(screen.queryByTestId("home-page")).not.toBeInTheDocument();
  });

  describe("ProtectedRoute", () => {
    it("shows spinner during loading state", () => {
      vi.mocked(useAuth).mockReturnValue({
        user: null,
        loading: true,
        fetchUser: mockFetchUser,
      });
      window.history.pushState({}, "", "/edit/doc-123");
      render(<App />);

      const spinner = document.querySelector(
        ".animate-spin.rounded-full.border-2",
      );
      expect(spinner).toBeInTheDocument();
      expect(screen.queryByTestId("editor-page")).not.toBeInTheDocument();
    });

    it("renders children when authenticated", () => {
      vi.mocked(useAuth).mockReturnValue({
        user: { id: "u1", email: "u@x.com", name: "User" } as never,
        loading: false,
        fetchUser: mockFetchUser,
      });
      window.history.pushState({}, "", "/edit/doc-123");
      render(<App />);

      expect(screen.getByTestId("editor-page")).toBeInTheDocument();
      expect(screen.queryByTestId("landing-page")).not.toBeInTheDocument();
    });
  });
});
