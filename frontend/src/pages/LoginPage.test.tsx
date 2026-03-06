import { describe, it, expect, vi, afterEach } from "vitest";
import { render } from "@testing-library/react";
import { LoginPage } from "./LoginPage";

vi.mock("../components/Auth/SSOLoginFlow", () => ({
  SSOLoginFlow: () => (
    <div data-testid="sso-login-flow">
      <input data-testid="sso-email-input" placeholder="Enter your work email" />
      <button data-testid="sso-continue-btn">Continue with email</button>
    </div>
  ),
}));

describe("LoginPage", () => {
  const originalTitle = document.title;

  afterEach(() => {
    document.title = originalTitle;
  });

  it("sets document.title to 'Sign In - CollabMark' on mount", () => {
    document.title = "Initial";
    render(<LoginPage />);
    expect(document.title).toBe("Sign In - CollabMark");
  });

  it("resets document.title to 'CollabMark' on unmount", () => {
    const { unmount } = render(<LoginPage />);
    expect(document.title).toBe("Sign In - CollabMark");
    unmount();
    expect(document.title).toBe("CollabMark");
  });

  it("renders 'CollabMark' heading", () => {
    const { getByRole } = render(<LoginPage />);
    expect(getByRole("heading", { name: "CollabMark" })).toBeInTheDocument();
  });

  it("renders description text", () => {
    const { getByText } = render(<LoginPage />);
    expect(
      getByText("Collaborative Markdown editing, made simple.")
    ).toBeInTheDocument();
  });

  it("renders SSOLoginFlow", () => {
    const { getByTestId } = render(<LoginPage />);
    expect(getByTestId("sso-login-flow")).toBeInTheDocument();
    expect(getByTestId("sso-email-input")).toBeInTheDocument();
    expect(getByTestId("sso-continue-btn")).toBeInTheDocument();
  });
});
