import { describe, it, expect } from "vitest";
import { toggleWrap, toggleHtmlWrap, toggleHeading } from "./markdownShortcuts";

describe("toggleWrap", () => {
  it("wraps text with bold markers", () => {
    expect(toggleWrap("hello", "**")).toBe("**hello**");
  });

  it("unwraps already-bold text", () => {
    expect(toggleWrap("**hello**", "**")).toBe("hello");
  });

  it("wraps text with italic markers", () => {
    expect(toggleWrap("hello", "*")).toBe("*hello*");
  });

  it("unwraps already-italic text", () => {
    expect(toggleWrap("*hello*", "*")).toBe("hello");
  });

  it("wraps text with strikethrough markers", () => {
    expect(toggleWrap("hello", "~~")).toBe("~~hello~~");
  });

  it("unwraps already-strikethrough text", () => {
    expect(toggleWrap("~~hello~~", "~~")).toBe("hello");
  });

  it("wraps text with inline code markers", () => {
    expect(toggleWrap("code", "`")).toBe("`code`");
  });

  it("unwraps already-code text", () => {
    expect(toggleWrap("`code`", "`")).toBe("code");
  });

  it("wraps empty string (inserts marker pair)", () => {
    expect(toggleWrap("", "**")).toBe("****");
  });

  it("handles multi-word selections", () => {
    expect(toggleWrap("hello world", "**")).toBe("**hello world**");
  });

  it("does not confuse single * with double **", () => {
    expect(toggleWrap("*hello*", "**")).toBe("***hello***");
  });

  it("unwraps bold that wraps italic", () => {
    expect(toggleWrap("***hello***", "**")).toBe("*hello*");
  });

  it("toggle is idempotent (wrap then unwrap)", () => {
    const original = "some text";
    const wrapped = toggleWrap(original, "**");
    const unwrapped = toggleWrap(wrapped, "**");
    expect(unwrapped).toBe(original);
  });

  it("does not unwrap partial markers", () => {
    expect(toggleWrap("**hello", "**")).toBe("****hello**");
  });
});

describe("toggleHtmlWrap", () => {
  it("wraps text with <u> tags", () => {
    expect(toggleHtmlWrap("hello", "<u>", "</u>")).toBe("<u>hello</u>");
  });

  it("unwraps already-underlined text", () => {
    expect(toggleHtmlWrap("<u>hello</u>", "<u>", "</u>")).toBe("hello");
  });

  it("wraps empty string", () => {
    expect(toggleHtmlWrap("", "<u>", "</u>")).toBe("<u></u>");
  });

  it("toggle is idempotent", () => {
    const original = "text";
    const wrapped = toggleHtmlWrap(original, "<u>", "</u>");
    const unwrapped = toggleHtmlWrap(wrapped, "<u>", "</u>");
    expect(unwrapped).toBe(original);
  });

  it("does not unwrap partial tags", () => {
    expect(toggleHtmlWrap("<u>hello", "<u>", "</u>")).toBe("<u><u>hello</u>");
  });
});

describe("toggleHeading", () => {
  it("adds # prefix to plain text", () => {
    expect(toggleHeading("Hello")).toBe("# Hello");
  });

  it("removes # prefix from heading", () => {
    expect(toggleHeading("# Hello")).toBe("Hello");
  });

  it("toggle is idempotent", () => {
    const original = "My Title";
    const headed = toggleHeading(original);
    const unheaded = toggleHeading(headed);
    expect(unheaded).toBe(original);
  });

  it("handles empty string", () => {
    expect(toggleHeading("")).toBe("# ");
  });

  it("only toggles single # level (does not affect ##)", () => {
    expect(toggleHeading("## Subtitle")).toBe("# ## Subtitle");
  });
});
