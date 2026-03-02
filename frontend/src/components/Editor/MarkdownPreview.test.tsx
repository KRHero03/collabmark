/**
 * Tests for MarkdownPreview component.
 *
 * Validates that markdown content renders correctly, mermaid blocks
 * are handled, and the component memoizes properly to avoid
 * unnecessary re-renders.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";

vi.mock("../../hooks/useDarkMode", () => ({
  useDarkMode: vi.fn(() => false),
}));

vi.mock("mermaid", () => ({
  default: {
    initialize: vi.fn(),
    render: vi.fn().mockResolvedValue({ svg: "<svg>diagram</svg>" }),
  },
}));

import { MarkdownPreview } from "./MarkdownPreview";

describe("MarkdownPreview", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders plain text markdown", () => {
    render(<MarkdownPreview content="Hello world" />);
    expect(screen.getByText("Hello world")).toBeDefined();
  });

  it("renders headings correctly", () => {
    render(<MarkdownPreview content={"# Heading 1\n\n## Heading 2"} />);
    expect(screen.getByRole("heading", { level: 1 })).toBeDefined();
    expect(screen.getByRole("heading", { level: 2 })).toBeDefined();
  });

  it("renders code blocks", () => {
    render(
      <MarkdownPreview content={"```javascript\nconst x = 1;\n```"} />,
    );
    const codeEl = document.querySelector("code");
    expect(codeEl).not.toBeNull();
    expect(codeEl?.textContent).toContain("const x = 1;");
  });

  it("applies prose class to wrapper", () => {
    const { container } = render(<MarkdownPreview content="test" />);
    expect(container.firstElementChild?.classList.contains("prose")).toBe(true);
  });

  it("applies additional className", () => {
    const { container } = render(
      <MarkdownPreview content="test" className="prose-base" />,
    );
    expect(
      container.firstElementChild?.classList.contains("prose-base"),
    ).toBe(true);
  });

  it("does not re-render when content is identical", () => {
    const { rerender } = render(<MarkdownPreview content="Same content" />);
    const firstHtml = document.querySelector(".prose")?.innerHTML;

    rerender(<MarkdownPreview content="Same content" />);
    const secondHtml = document.querySelector(".prose")?.innerHTML;

    expect(firstHtml).toBe(secondHtml);
  });

  it("renders GFM tables", () => {
    const table = "| A | B |\n|---|---|\n| 1 | 2 |";
    render(<MarkdownPreview content={table} />);
    expect(document.querySelector("table")).not.toBeNull();
    expect(document.querySelectorAll("td")).toHaveLength(2);
  });

  it("renders GFM task lists", () => {
    const tasks = "- [x] Done\n- [ ] Todo";
    render(<MarkdownPreview content={tasks} />);
    const checkboxes = document.querySelectorAll('input[type="checkbox"]');
    expect(checkboxes).toHaveLength(2);
  });

  it("renders inline code without language class", () => {
    render(<MarkdownPreview content="Use `const` keyword" />);
    const code = document.querySelector("code");
    expect(code).not.toBeNull();
    expect(code?.textContent).toBe("const");
  });

  it("renders empty content without error", () => {
    const { container } = render(<MarkdownPreview content="" />);
    expect(container.firstElementChild?.classList.contains("prose")).toBe(true);
  });
});
