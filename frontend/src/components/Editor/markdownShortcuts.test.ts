import { describe, it, expect } from "vitest";
import { EditorState } from "@codemirror/state";
import { EditorView } from "codemirror";
import {
  toggleWrap,
  toggleHtmlWrap,
  toggleHeading,
  _wrapCommand,
  _htmlWrapCommand,
  _headingCommand,
} from "./markdownShortcuts";

function createEditorWithContent(
  content: string,
  selFrom: number,
  selTo: number,
): EditorView {
  const state = EditorState.create({
    doc: content,
    selection: { anchor: selFrom, head: selTo },
  });
  const view = new EditorView({ state, parent: document.createElement("div") });
  return view;
}

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

describe("CodeMirror commands", () => {
  it("wrapCommand bold wraps selected text with **", () => {
    const view = createEditorWithContent("hello world", 0, 5);
    _wrapCommand("**")(view);
    expect(view.state.doc.toString()).toBe("**hello** world");
    view.destroy();
  });

  it("wrapCommand bold on empty selection inserts ****", () => {
    const view = createEditorWithContent("hello", 2, 2);
    _wrapCommand("**")(view);
    expect(view.state.doc.toString()).toBe("he****llo");
    view.destroy();
  });

  it("wrapCommand italic wraps selected text", () => {
    const view = createEditorWithContent("text", 0, 4);
    _wrapCommand("*")(view);
    expect(view.state.doc.toString()).toBe("*text*");
    view.destroy();
  });

  it("wrapCommand strikethrough wraps selected text", () => {
    const view = createEditorWithContent("done", 0, 4);
    _wrapCommand("~~")(view);
    expect(view.state.doc.toString()).toBe("~~done~~");
    view.destroy();
  });

  it("wrapCommand code wraps selected text with backticks", () => {
    const view = createEditorWithContent("code", 0, 4);
    _wrapCommand("`")(view);
    expect(view.state.doc.toString()).toBe("`code`");
    view.destroy();
  });

  it("wrapCommand unwraps already-wrapped text", () => {
    const view = createEditorWithContent("**hello**", 0, 9);
    _wrapCommand("**")(view);
    expect(view.state.doc.toString()).toBe("hello");
    view.destroy();
  });

  it("htmlWrapCommand wraps with <u> tags", () => {
    const view = createEditorWithContent("hello", 0, 5);
    _htmlWrapCommand("<u>", "</u>")(view);
    expect(view.state.doc.toString()).toBe("<u>hello</u>");
    view.destroy();
  });

  it("htmlWrapCommand on empty selection inserts tags", () => {
    const view = createEditorWithContent("ab", 1, 1);
    _htmlWrapCommand("<u>", "</u>")(view);
    expect(view.state.doc.toString()).toBe("a<u></u>b");
    view.destroy();
  });

  it("htmlWrapCommand unwraps already-wrapped text", () => {
    const content = "<u>text</u>";
    const view = createEditorWithContent(content, 0, content.length);
    _htmlWrapCommand("<u>", "</u>")(view);
    expect(view.state.doc.toString()).toBe("text");
    view.destroy();
  });

  it("headingCommand adds # prefix to line", () => {
    const view = createEditorWithContent("Hello", 0, 0);
    _headingCommand(view);
    expect(view.state.doc.toString()).toBe("# Hello");
    view.destroy();
  });

  it("headingCommand removes # prefix from heading", () => {
    const view = createEditorWithContent("# Hello", 0, 0);
    _headingCommand(view);
    expect(view.state.doc.toString()).toBe("Hello");
    view.destroy();
  });

  it("headingCommand works when cursor is mid-line", () => {
    const view = createEditorWithContent("Title here", 5, 5);
    _headingCommand(view);
    expect(view.state.doc.toString()).toBe("# Title here");
    view.destroy();
  });

  it("headingCommand handles empty line", () => {
    const view = createEditorWithContent("", 0, 0);
    _headingCommand(view);
    expect(view.state.doc.toString()).toBe("# ");
    view.destroy();
  });
});
