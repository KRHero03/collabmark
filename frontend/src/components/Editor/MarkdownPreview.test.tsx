/**
 * Tests for MarkdownPreview component.
 *
 * Validates that markdown content renders correctly, mermaid blocks
 * are handled, and the component memoizes properly to avoid
 * unnecessary re-renders.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render } from "@testing-library/react";

const mockUseDarkMode = vi.fn(() => false);
vi.mock("../../hooks/useDarkMode", () => ({
  useDarkMode: () => mockUseDarkMode(),
}));

vi.mock("mermaid", () => ({
  default: {
    initialize: vi.fn(),
    render: vi.fn().mockResolvedValue({ svg: "<svg>diagram</svg>", diagramType: "flowchart" }),
  },
}));

import { MarkdownPreview } from "./MarkdownPreview";

describe("MarkdownPreview", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders plain text markdown", () => {
    const { getByText } = render(<MarkdownPreview content="Hello world" />);
    expect(getByText("Hello world")).toBeDefined();
  });

  it("renders headings correctly", () => {
    const { getByRole } = render(
      <MarkdownPreview content={"# Heading 1\n\n## Heading 2"} />,
    );
    expect(getByRole("heading", { level: 1 })).toBeDefined();
    expect(getByRole("heading", { level: 2 })).toBeDefined();
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

  describe("MermaidBlock", () => {
    it("renders placeholder 'Rendering diagram...' while mermaid is loading", async () => {
      let resolveRender: (v: { svg: string; diagramType: string }) => void;
      const renderPromise = new Promise<{ svg: string; diagramType: string }>((r) => {
        resolveRender = r;
      });
      const mermaid = await import("mermaid");
      vi.mocked(mermaid.default.render).mockReturnValue(renderPromise as never);

      const { getByText } = render(
        <MarkdownPreview content={"```mermaid\ngraph TD\nA-->B\n```"} />,
      );
      expect(getByText("Rendering diagram...")).toBeInTheDocument();

      resolveRender!({ svg: "<svg>diagram</svg>", diagramType: "flowchart" });
      await renderPromise;
    });

    it("renders mermaid SVG when render succeeds", async () => {
      const mermaid = await import("mermaid");
      vi.mocked(mermaid.default.render).mockResolvedValue({
        svg: "<svg data-testid='mermaid-svg'>flowchart</svg>",
        diagramType: "flowchart",
      });

      const { getByTestId } = render(
        <MarkdownPreview content={"```mermaid\ngraph TD\nA-->B\n```"} />,
      );

      await vi.waitFor(() => {
        const svg = getByTestId("mermaid-svg");
        expect(svg).toBeInTheDocument();
      });
    });

    it("renders Mermaid error when mermaid.render throws", async () => {
      const mermaid = await import("mermaid");
      vi.mocked(mermaid.default.render).mockRejectedValue(
        new Error("Invalid diagram syntax"),
      );

      const { getByText } = render(
        <MarkdownPreview content={"```mermaid\ninvalid\n```"} />,
      );

      await vi.waitFor(() => {
        expect(getByText(/Mermaid error:/)).toBeInTheDocument();
        expect(getByText(/Invalid diagram syntax/)).toBeInTheDocument();
      });
    });

    it("calls mermaid.initialize with dark theme when isDark is true", async () => {
      mockUseDarkMode.mockReturnValue(true);

      const mermaid = await import("mermaid");
      vi.mocked(mermaid.default.render).mockResolvedValue({
        svg: "<svg>ok</svg>",
        diagramType: "flowchart",
      });

      render(
        <MarkdownPreview content={"```mermaid\ngraph TD\nA-->B\n```"} />,
      );

      await vi.waitFor(() => {
        expect(mermaid.default.initialize).toHaveBeenCalledWith({
          startOnLoad: false,
          theme: "dark",
          securityLevel: "loose",
        });
      });
    });

    it("calls mermaid.initialize with default theme when isDark is false", async () => {
      mockUseDarkMode.mockReturnValue(false);

      const mermaid = await import("mermaid");
      vi.mocked(mermaid.default.render).mockResolvedValue({
        svg: "<svg>ok</svg>",
        diagramType: "flowchart",
      });

      render(
        <MarkdownPreview content={"```mermaid\ngraph TD\nA-->B\n```"} />,
      );

      await vi.waitFor(() => {
        expect(mermaid.default.initialize).toHaveBeenCalledWith({
          startOnLoad: false,
          theme: "default",
          securityLevel: "loose",
        });
      });
    });
  });

  describe("useHighlightTheme", () => {
    it("injects hljs light theme link when isDark is false", () => {
      mockUseDarkMode.mockReturnValue(false);

      const linkId = "hljs-theme-link";
      const existing = document.getElementById(linkId);
      if (existing) existing.remove();

      render(<MarkdownPreview content="code" />);

      const link = document.getElementById(linkId) as HTMLLinkElement | null;
      expect(link).toBeTruthy();
      expect(link?.tagName).toBe("LINK");
      expect(link?.rel).toBe("stylesheet");
      expect(link?.href).toContain("github.css");
    });

    it("injects hljs dark theme link when isDark is true", () => {
      mockUseDarkMode.mockReturnValue(true);

      const linkId = "hljs-theme-link";
      const existing = document.getElementById(linkId);
      if (existing) existing.remove();

      render(<MarkdownPreview content="code" />);

      const link = document.getElementById(linkId) as HTMLLinkElement | null;
      expect(link).toBeTruthy();
      expect(link?.href).toContain("github-dark.css");
    });
  });

  describe("MarkdownPreview edge cases", () => {
    it("renders long content without error", () => {
      const longContent = "# Title\n\n" + "Lorem ipsum. ".repeat(500);
      const { container } = render(<MarkdownPreview content={longContent} />);
      expect(container.firstElementChild?.classList.contains("prose")).toBe(
        true,
      );
    });

    it("renders strikethrough via GFM", () => {
      render(<MarkdownPreview content="~~strikethrough~~" />);
      const del = document.querySelector("del");
      expect(del).not.toBeNull();
      expect(del?.textContent).toBe("strikethrough");
    });

    it("always includes dark:prose-invert for CSS-based dark mode", () => {
      mockUseDarkMode.mockReturnValue(false);

      const { container } = render(<MarkdownPreview content="x" />);
      expect(container.firstElementChild?.className).toContain(
        "dark:prose-invert",
      );
    });
  });
});
