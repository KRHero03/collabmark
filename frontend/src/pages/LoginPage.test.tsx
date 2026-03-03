import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { LoginPage } from "./LoginPage";

vi.mock("../components/Auth/GoogleLoginButton", () => ({
  GoogleLoginButton: () => <div data-testid="google-login-button">GoogleLoginButton</div>,
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
    render(<LoginPage />);
    expect(screen.getByRole("heading", { name: "CollabMark" })).toBeInTheDocument();
  });

  it("renders description text", () => {
    render(<LoginPage />);
    expect(
      screen.getByText("Collaborative Markdown editing, made simple.")
    ).toBeInTheDocument();
  });

  it("renders GoogleLoginButton", () => {
    render(<LoginPage />);
    expect(screen.getByTestId("google-login-button")).toBeInTheDocument();
  });
});
