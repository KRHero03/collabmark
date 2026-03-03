import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { GoogleLoginButton } from "./GoogleLoginButton";

describe("GoogleLoginButton", () => {
  it("renders 'Sign in with Google' text", () => {
    render(<GoogleLoginButton />);
    expect(screen.getByText("Sign in with Google")).toBeInTheDocument();
  });

  it("has correct href='/api/auth/google/login'", () => {
    render(<GoogleLoginButton />);
    const link = screen.getByRole("link", { name: /sign in with google/i });
    expect(link).toHaveAttribute("href", "/api/auth/google/login");
  });

  it("renders Google SVG icon", () => {
    const { container } = render(<GoogleLoginButton />);
    const svg = container.querySelector("svg[viewBox='0 0 24 24']");
    expect(svg).toBeInTheDocument();
    const paths = container.querySelectorAll("svg path");
    expect(paths.length).toBeGreaterThanOrEqual(4);
  });

  it("is an anchor tag (not a button)", () => {
    render(<GoogleLoginButton />);
    const link = screen.getByRole("link", { name: /sign in with google/i });
    expect(link.tagName).toBe("A");
    expect(link).not.toHaveAttribute("role", "button");
  });
});
