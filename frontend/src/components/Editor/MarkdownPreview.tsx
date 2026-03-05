/**
 * Live Markdown preview with syntax highlighting and Mermaid diagram support.
 *
 * Uses react-markdown with remark-gfm (tables, strikethrough, task lists),
 * rehype-highlight (code block syntax coloring), and a custom code component
 * that detects ```mermaid blocks and renders them as inline SVGs.
 *
 * Dark mode is handled reactively via the useDarkMode hook:
 * - Mermaid diagrams re-render with the "dark" theme
 * - highlight.js stylesheet swaps between github and github-dark
 * - Tailwind Typography switches to prose-invert
 */

import { memo, useEffect, useMemo, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import { useDarkMode } from "../../hooks/useDarkMode";
import hljsLight from "highlight.js/styles/github.css?url";
import hljsDark from "highlight.js/styles/github-dark.css?url";

let mermaidIdCounter = 0;

interface MarkdownPreviewProps {
  /** Raw Markdown string to render. */
  content: string;
  /** Extra CSS classes merged onto the prose wrapper. */
  className?: string;
}

/**
 * Renders a Mermaid diagram from its source definition.
 * Lazily imports the mermaid library and converts the definition into an SVG.
 * Re-renders when chart content or dark mode changes.
 */
const MermaidBlock = memo(function MermaidBlock({
  chart,
  isDark,
}: {
  chart: string;
  isDark: boolean;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [svg, setSvg] = useState<string>("");
  const [error, setError] = useState<string>("");
  const stableId = useRef(`mermaid-${++mermaidIdCounter}`);

  useEffect(() => {
    let cancelled = false;

    (async () => {
      try {
        const mermaid = (await import("mermaid")).default;
        mermaid.initialize({
          startOnLoad: false,
          theme: isDark ? "dark" : "default",
          securityLevel: "loose",
        });

        const { svg: rendered } = await mermaid.render(
          stableId.current,
          chart.trim(),
        );
        if (!cancelled) {
          setSvg(rendered);
          setError("");
        }
      } catch (e) {
        if (!cancelled) setError(String(e));
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [chart, isDark]);

  if (error) {
    return (
      <pre className="rounded-md border border-red-200 bg-red-50 p-3 text-xs text-red-600">
        Mermaid error: {error}
      </pre>
    );
  }

  if (!svg) {
    return (
      <div className="flex items-center justify-center py-4 text-sm text-gray-400">
        Rendering diagram...
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className="my-4 overflow-x-auto"
      dangerouslySetInnerHTML={{ __html: svg }}
    />
  );
});

/**
 * Injects the correct highlight.js stylesheet into the document head,
 * swapping between light (github) and dark (github-dark) themes.
 */
function useHighlightTheme(isDark: boolean) {
  useEffect(() => {
    const LINK_ID = "hljs-theme-link";
    let link = document.getElementById(LINK_ID) as HTMLLinkElement | null;
    if (!link) {
      link = document.createElement("link");
      link.id = LINK_ID;
      link.rel = "stylesheet";
      document.head.appendChild(link);
    }

    link.href = isDark ? hljsDark : hljsLight;

    return () => {
      // Leave the link in place; the next effect invocation will update href.
    };
  }, [isDark]);
}

export function MarkdownPreview({ content, className }: MarkdownPreviewProps) {
  const isDark = useDarkMode();
  useHighlightTheme(isDark);

  const components = useMemo(
    () => ({
      code({
        className: cn,
        children,
        ...props
      }: React.ComponentPropsWithoutRef<"code"> & { className?: string }) {
        if (/language-mermaid/.test(cn || "")) {
          return <MermaidBlock chart={String(children)} isDark={isDark} />;
        }
        return (
          <code className={cn} {...props}>
            {children}
          </code>
        );
      },
    }),
    [isDark],
  );

  return (
    <div
      className={`prose prose-sm dark:prose-invert max-w-none overflow-auto p-6 ${className ?? ""}`}
    >
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeHighlight]}
        components={components}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
