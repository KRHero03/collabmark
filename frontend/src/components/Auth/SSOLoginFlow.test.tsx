import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, fireEvent, waitFor, cleanup } from "@testing-library/react";
import { SSOLoginFlow } from "./SSOLoginFlow";

const mockDetectSSO = vi.fn();

vi.mock("../../lib/api", () => ({
  authApi: {
    detectSSO: (email: string) => mockDetectSSO(email),
  },
}));

describe("SSOLoginFlow", () => {
  const originalLocation = window.location;

  beforeEach(() => {
    cleanup();
    mockDetectSSO.mockReset();
    Object.defineProperty(window, "location", {
      value: { href: "", search: "", pathname: "/login" },
      writable: true,
    });
    window.history.replaceState = vi.fn();
  });

  afterEach(() => {
    Object.defineProperty(window, "location", {
      value: originalLocation,
      writable: true,
    });
  });

  it("renders email input and continue button", () => {
    const { getByTestId, getByPlaceholderText } = render(<SSOLoginFlow />);
    expect(getByPlaceholderText("Enter your work email")).toBeInTheDocument();
    expect(getByTestId("sso-continue-btn")).toBeInTheDocument();
    expect(getByTestId("sso-continue-btn")).toHaveTextContent("Continue with email");
  });

  it("empty email shows validation error", async () => {
    const { getByTestId } = render(<SSOLoginFlow />);
    fireEvent.click(getByTestId("sso-continue-btn"));
    await waitFor(() => {
      expect(getByTestId("sso-error")).toBeInTheDocument();
      expect(getByTestId("sso-error")).toHaveTextContent("Please enter a valid email address.");
    });
    expect(mockDetectSSO).not.toHaveBeenCalled();
  });

  it("invalid email (no @) shows validation error", async () => {
    const { getByTestId, getByPlaceholderText } = render(<SSOLoginFlow />);
    fireEvent.change(getByPlaceholderText("Enter your work email"), {
      target: { value: "invalid-email" },
    });
    fireEvent.click(getByTestId("sso-continue-btn"));
    await waitFor(() => {
      expect(getByTestId("sso-error")).toBeInTheDocument();
      expect(getByTestId("sso-error")).toHaveTextContent("Please enter a valid email address.");
    });
    expect(mockDetectSSO).not.toHaveBeenCalled();
  });

  it("SSO detected: shows redirecting state and redirects", async () => {
    mockDetectSSO.mockResolvedValue({
      data: {
        sso: true,
        org_id: "org-123",
        org_name: "Acme Corp",
        protocol: "saml",
      },
    });

    const { getByTestId, getByPlaceholderText } = render(<SSOLoginFlow />);
    fireEvent.change(getByPlaceholderText("Enter your work email"), {
      target: { value: "user@acme.com" },
    });
    fireEvent.click(getByTestId("sso-continue-btn"));

    await waitFor(() => {
      expect(getByTestId("sso-redirecting")).toBeInTheDocument();
      expect(getByTestId("sso-redirecting")).toHaveTextContent("Redirecting to Acme Corp");
    });

    expect(window.location.href).toBe("/api/auth/sso/saml/login/org-123");
  });

  it("SSO not detected: shows domain-specific error message and Google fallback", async () => {
    mockDetectSSO.mockResolvedValue({ data: { sso: false } });

    const { getByTestId, getByPlaceholderText, getByRole } = render(<SSOLoginFlow />);
    fireEvent.change(getByPlaceholderText("Enter your work email"), {
      target: { value: "user@example.com" },
    });
    fireEvent.click(getByTestId("sso-continue-btn"));

    await waitFor(() => {
      expect(getByTestId("sso-fallback")).toBeInTheDocument();
      expect(getByTestId("sso-no-org-message")).toBeInTheDocument();
      expect(getByTestId("sso-no-org-message")).toHaveTextContent('No SSO configured for "example.com"');
      expect(getByTestId("sso-no-org-message")).toHaveTextContent("Your organization may not be onboarded yet");
      expect(getByRole("link", { name: /sign in with google/i })).toBeInTheDocument();
    });
  });

  it("network error: shows error message and Google fallback", async () => {
    mockDetectSSO.mockRejectedValue(new Error("Network error"));

    const { getByTestId, getByPlaceholderText, getByRole } = render(<SSOLoginFlow />);
    fireEvent.change(getByPlaceholderText("Enter your work email"), {
      target: { value: "user@example.com" },
    });
    fireEvent.click(getByTestId("sso-continue-btn"));

    await waitFor(() => {
      expect(getByTestId("sso-fallback")).toBeInTheDocument();
      expect(getByTestId("sso-no-org-message")).toHaveTextContent("Could not verify your email domain");
      expect(getByRole("link", { name: /sign in with google/i })).toBeInTheDocument();
    });
  });

  it("Enter key submits the form", async () => {
    mockDetectSSO.mockResolvedValue({ data: { sso: false } });

    const { getByPlaceholderText } = render(<SSOLoginFlow />);
    fireEvent.change(getByPlaceholderText("Enter your work email"), {
      target: { value: "user@example.com" },
    });
    fireEvent.keyDown(getByPlaceholderText("Enter your work email"), {
      key: "Enter",
    });

    await waitFor(() => {
      expect(mockDetectSSO).toHaveBeenCalledWith("user@example.com");
    });
  });

  it("loading state shown during detection", async () => {
    let resolveDetect: (value: unknown) => void;
    mockDetectSSO.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveDetect = resolve;
        }),
    );

    const { getByTestId, getByPlaceholderText } = render(<SSOLoginFlow />);
    fireEvent.change(getByPlaceholderText("Enter your work email"), {
      target: { value: "user@example.com" },
    });
    fireEvent.click(getByTestId("sso-continue-btn"));

    expect(getByTestId("sso-continue-btn")).toHaveTextContent("Checking...");
    expect(getByTestId("sso-continue-btn")).toBeDisabled();

    resolveDetect!({ data: { sso: false } });
    await waitFor(() => {
      expect(getByTestId("sso-fallback")).toBeInTheDocument();
    });
  });

  it("typing after no_sso resets to idle and clears message", async () => {
    mockDetectSSO.mockResolvedValue({ data: { sso: false } });

    const { getByTestId, getByPlaceholderText, queryByTestId } = render(<SSOLoginFlow />);
    const input = getByPlaceholderText("Enter your work email");

    fireEvent.change(input, { target: { value: "user@example.com" } });
    fireEvent.click(getByTestId("sso-continue-btn"));

    await waitFor(() => {
      expect(getByTestId("sso-fallback")).toBeInTheDocument();
      expect(getByTestId("sso-no-org-message")).toBeInTheDocument();
    });

    fireEvent.change(input, { target: { value: "user@example.comx" } });

    await waitFor(() => {
      expect(queryByTestId("sso-fallback")).toBeNull();
      expect(queryByTestId("sso-no-org-message")).toBeNull();
    });
  });

  it("continue button is disabled during detection", async () => {
    let resolveDetect: (value: unknown) => void;
    mockDetectSSO.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveDetect = resolve;
        }),
    );

    const { getByTestId, getByPlaceholderText } = render(<SSOLoginFlow />);
    fireEvent.change(getByPlaceholderText("Enter your work email"), {
      target: { value: "user@example.com" },
    });
    fireEvent.click(getByTestId("sso-continue-btn"));

    expect(getByTestId("sso-continue-btn")).toBeDisabled();

    resolveDetect!({ data: { sso: false } });
    await waitFor(() => {
      expect(getByTestId("sso-fallback")).toBeInTheDocument();
    });
  });

  it("handles ?error=sso_not_configured query param on mount", () => {
    Object.defineProperty(window, "location", {
      value: { href: "", search: "?error=sso_not_configured", pathname: "/login" },
      writable: true,
    });

    const { getByTestId } = render(<SSOLoginFlow />);
    expect(getByTestId("sso-error")).toHaveTextContent("SSO is not configured for this organization");
    expect(window.history.replaceState).toHaveBeenCalled();
  });

  it("handles ?error=saml_invalid query param on mount", () => {
    Object.defineProperty(window, "location", {
      value: { href: "", search: "?error=saml_invalid", pathname: "/login" },
      writable: true,
    });

    const { getByTestId } = render(<SSOLoginFlow />);
    expect(getByTestId("sso-error")).toHaveTextContent("SAML authentication failed");
  });

  it("handles ?error=oidc_config_error query param on mount", () => {
    Object.defineProperty(window, "location", {
      value: { href: "", search: "?error=oidc_config_error", pathname: "/login" },
      writable: true,
    });

    const { getByTestId } = render(<SSOLoginFlow />);
    expect(getByTestId("sso-error")).toHaveTextContent("OIDC configuration error");
  });

  it("ignores unknown error query params", () => {
    Object.defineProperty(window, "location", {
      value: { href: "", search: "?error=unknown_error", pathname: "/login" },
      writable: true,
    });

    const { queryByTestId } = render(<SSOLoginFlow />);
    expect(queryByTestId("sso-error")).toBeNull();
  });

  it("shows different messages for gmail vs work domain", async () => {
    mockDetectSSO.mockResolvedValue({ data: { sso: false } });

    const { getByTestId, getByPlaceholderText } = render(<SSOLoginFlow />);
    fireEvent.change(getByPlaceholderText("Enter your work email"), {
      target: { value: "user@gmail.com" },
    });
    fireEvent.click(getByTestId("sso-continue-btn"));

    await waitFor(() => {
      expect(getByTestId("sso-no-org-message")).toHaveTextContent('No SSO configured for "gmail.com"');
    });
  });

  it("typing after error from query param clears the error", () => {
    Object.defineProperty(window, "location", {
      value: { href: "", search: "?error=sso_not_configured", pathname: "/login" },
      writable: true,
    });

    const { getByTestId, queryByTestId, getByPlaceholderText } = render(<SSOLoginFlow />);
    expect(getByTestId("sso-error")).toBeInTheDocument();

    fireEvent.change(getByPlaceholderText("Enter your work email"), {
      target: { value: "a" },
    });

    expect(queryByTestId("sso-error")).toBeNull();
  });
});
