import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { render } from "@testing-library/react";
import { CLILoginPage } from "./CLILoginPage";

vi.mock("../hooks/useAuth", () => ({
  useAuth: vi.fn(() => ({ user: null, loading: false })),
}));

vi.mock("../components/Auth/SSOLoginFlow", () => ({
  SSOLoginFlow: () => (
    <div data-testid="sso-login-flow">
      <input data-testid="sso-email-input" placeholder="Enter your work email" />
      <button data-testid="sso-continue-btn">Continue with work email</button>
    </div>
  ),
}));

const { useAuth } = await import("../hooks/useAuth");

describe("CLILoginPage", () => {
  const originalTitle = document.title;

  beforeEach(() => {
    vi.mocked(useAuth).mockReturnValue({ user: null, loading: false, fetchUser: vi.fn(), logout: vi.fn() });
    sessionStorage.clear();
    document.documentElement.classList.remove("dark");
    Object.defineProperty(window, "localStorage", {
      value: { getItem: vi.fn(), setItem: vi.fn(), removeItem: vi.fn(), clear: vi.fn(), length: 0, key: vi.fn() },
      writable: true,
    });
    Object.defineProperty(window, "location", {
      writable: true,
      value: { ...window.location, search: "", href: window.location.href, pathname: "/cli-login" },
    });
  });

  afterEach(() => {
    document.title = originalTitle;
  });

  it("sets document.title on mount", () => {
    render(<CLILoginPage />);
    expect(document.title).toBe("CLI Login - CollabMark");
  });

  it("resets document.title on unmount", () => {
    const { unmount } = render(<CLILoginPage />);
    unmount();
    expect(document.title).toBe("CollabMark");
  });

  it("renders login form by default", () => {
    const { getByRole, getByTestId } = render(<CLILoginPage />);
    expect(getByRole("heading", { level: 1 })).toBeInTheDocument();
    expect(getByTestId("sso-login-flow")).toBeInTheDocument();
  });

  it("renders the CollabMark navbar brand as a link", () => {
    const { container } = render(<CLILoginPage />);
    const nav = container.querySelector("nav");
    expect(nav).toBeInTheDocument();
    const brandLink = nav!.querySelector('a[href="/"]');
    expect(brandLink).toBeInTheDocument();
    expect(brandLink!.textContent).toContain("CollabMark");
  });

  it("renders terminal illustration", () => {
    const { getByText } = render(<CLILoginPage />);
    expect(getByText("collabmark login")).toBeInTheDocument();
  });

  it("renders fallback hint with api-key command", () => {
    const { getByText } = render(<CLILoginPage />);
    expect(getByText(/collabmark login --api-key/)).toBeInTheDocument();
  });

  it("stores port from query param in sessionStorage as JSON with timestamp", () => {
    Object.defineProperty(window, "location", {
      writable: true,
      value: { ...window.location, search: "?port=54321", pathname: "/cli-login" },
    });
    render(<CLILoginPage />);
    const raw = sessionStorage.getItem("cli_login_port");
    expect(raw).not.toBeNull();
    const parsed = JSON.parse(raw!);
    expect(parsed.port).toBe("54321");
    expect(typeof parsed.ts).toBe("number");
  });

  it("strips query params from URL after reading port", () => {
    const replaceStateSpy = vi.spyOn(window.history, "replaceState");
    Object.defineProperty(window, "location", {
      writable: true,
      value: { ...window.location, search: "?port=54321", pathname: "/cli-login" },
    });
    render(<CLILoginPage />);
    expect(replaceStateSpy).toHaveBeenCalledWith({}, "", "/cli-login");
    replaceStateSpy.mockRestore();
  });

  it("ignores non-numeric port values", () => {
    Object.defineProperty(window, "location", {
      writable: true,
      value: { ...window.location, search: "?port=abc", pathname: "/cli-login" },
    });
    render(<CLILoginPage />);
    expect(sessionStorage.getItem("cli_login_port")).toBeNull();
  });

  it("redirects to cli/complete when user is authenticated", () => {
    sessionStorage.setItem("cli_login_port", JSON.stringify({ port: "12345", ts: Date.now() }));
    vi.mocked(useAuth).mockReturnValue({
      user: { id: "u1", email: "pm@acme.com", name: "Alice" } as any,
      loading: false,
      fetchUser: vi.fn(),
      logout: vi.fn(),
    });

    render(<CLILoginPage />);
    expect(window.location.href).toContain("/api/auth/cli/complete?port=12345");
    expect(window.location.href).not.toContain("theme=");
    expect(sessionStorage.getItem("cli_login_port")).toBeNull();
  });

  it("shows spinner when loading", () => {
    vi.mocked(useAuth).mockReturnValue({
      user: null,
      loading: true,
      fetchUser: vi.fn(),
      logout: vi.fn(),
    });

    const { container } = render(<CLILoginPage />);
    expect(container.querySelector(".animate-spin")).toBeInTheDocument();
  });

  describe("status=success", () => {
    beforeEach(() => {
      Object.defineProperty(window, "location", {
        writable: true,
        value: { ...window.location, search: "?status=success", pathname: "/cli-login" },
      });
    });

    it("renders success heading and message", () => {
      const { getByText } = render(<CLILoginPage />);
      expect(getByText("signed in!")).toBeInTheDocument();
      expect(getByText(/close this tab/)).toBeInTheDocument();
    });

    it("shows success checkmark in terminal", () => {
      const { container } = render(<CLILoginPage />);
      expect(container.textContent).toContain("✓");
    });

    it("does not render SSOLoginFlow", () => {
      const { queryByTestId } = render(<CLILoginPage />);
      expect(queryByTestId("sso-login-flow")).toBeNull();
    });
  });

  describe("status=error", () => {
    beforeEach(() => {
      Object.defineProperty(window, "location", {
        writable: true,
        value: { ...window.location, search: "?status=error", pathname: "/cli-login" },
      });
    });

    it("renders error heading and message", () => {
      const { getByText } = render(<CLILoginPage />);
      expect(getByText("failed")).toBeInTheDocument();
      expect(getByText(/went wrong/)).toBeInTheDocument();
    });

    it("shows error marker in terminal", () => {
      const { container } = render(<CLILoginPage />);
      expect(container.textContent).toContain("✗");
    });

    it("does not render SSOLoginFlow", () => {
      const { queryByTestId } = render(<CLILoginPage />);
      expect(queryByTestId("sso-login-flow")).toBeNull();
    });
  });
});
