/**
 * Markdown formatting keyboard shortcuts for the CodeMirror editor.
 *
 * Provides toggle-wrap logic for inline markers (bold, italic, underline,
 * strikethrough, code), a line-prefix toggle for headings and lists,
 * and a link insertion command.
 *
 * Each shortcut is idempotent: applying it twice returns to the original text.
 */

import { keymap } from "@codemirror/view";
import type { EditorView } from "codemirror";
import type { KeyBinding } from "@codemirror/view";

/**
 * Toggle an inline symmetric marker around text.
 * If `text` is already wrapped in `marker`, strips it; otherwise wraps it.
 */
export function toggleWrap(text: string, marker: string): string {
  if (text.startsWith(marker) && text.endsWith(marker) && text.length >= marker.length * 2) {
    return text.slice(marker.length, text.length - marker.length);
  }
  return `${marker}${text}${marker}`;
}

/**
 * Toggle asymmetric HTML-style markers (e.g. `<u>` / `</u>`).
 */
export function toggleHtmlWrap(text: string, open: string, close: string): string {
  if (text.startsWith(open) && text.endsWith(close) && text.length >= open.length + close.length) {
    return text.slice(open.length, text.length - close.length);
  }
  return `${open}${text}${close}`;
}

/**
 * Toggle a `# ` heading prefix on a line.
 * If the line already starts with `# `, removes it; otherwise prepends it.
 */
export function toggleHeading(lineText: string): string {
  if (lineText.startsWith("# ")) {
    return lineText.slice(2);
  }
  return `# ${lineText}`;
}

/**
 * Toggle a list prefix on a line.
 * `ordered` = false → `- `, `ordered` = true → `1. `.
 */
export function toggleListPrefix(lineText: string, ordered: boolean): string {
  const prefix = ordered ? "1. " : "- ";
  if (lineText.startsWith(prefix)) {
    return lineText.slice(prefix.length);
  }
  return `${prefix}${lineText}`;
}

/**
 * Wrap selected text as a markdown link, or insert a link placeholder.
 * With selection: `[selected](url)`. Without: `[](url)`.
 */
export function toLinkMarkdown(selectedText: string): string {
  if (selectedText.length > 0) {
    return `[${selectedText}](url)`;
  }
  return "[](url)";
}

export function wrapCommand(marker: string) {
  return (view: EditorView): boolean => {
    const { from, to } = view.state.selection.main;
    const selected = view.state.doc.sliceString(from, to);
    const result = toggleWrap(selected, marker);
    view.dispatch({
      changes: { from, to, insert: result },
      selection: {
        anchor: selected.length === 0 ? from + marker.length : from,
        head: selected.length === 0 ? from + marker.length : from + result.length,
      },
    });
    return true;
  };
}

export function htmlWrapCommand(open: string, close: string) {
  return (view: EditorView): boolean => {
    const { from, to } = view.state.selection.main;
    const selected = view.state.doc.sliceString(from, to);
    const result = toggleHtmlWrap(selected, open, close);
    view.dispatch({
      changes: { from, to, insert: result },
      selection: {
        anchor: selected.length === 0 ? from + open.length : from,
        head: selected.length === 0 ? from + open.length : from + result.length,
      },
    });
    return true;
  };
}

export function headingCommand(view: EditorView): boolean {
  const { from } = view.state.selection.main;
  const line = view.state.doc.lineAt(from);
  const result = toggleHeading(line.text);
  view.dispatch({
    changes: { from: line.from, to: line.to, insert: result },
  });
  return true;
}

export function listCommand(ordered: boolean) {
  return (view: EditorView): boolean => {
    const { from } = view.state.selection.main;
    const line = view.state.doc.lineAt(from);
    const result = toggleListPrefix(line.text, ordered);
    view.dispatch({
      changes: { from: line.from, to: line.to, insert: result },
    });
    return true;
  };
}

export function linkCommand(view: EditorView): boolean {
  const { from, to } = view.state.selection.main;
  const selected = view.state.doc.sliceString(from, to);
  const result = toLinkMarkdown(selected);
  view.dispatch({
    changes: { from, to, insert: result },
    selection: {
      anchor: from + result.length - 4,
      head: from + result.length - 1,
    },
  });
  return true;
}

const markdownBindings: KeyBinding[] = [
  { key: "Mod-b", run: wrapCommand("**") },
  { key: "Mod-i", run: wrapCommand("*") },
  { key: "Mod-u", run: htmlWrapCommand("<u>", "</u>") },
  { key: "Mod-Shift-s", run: wrapCommand("~~") },
  { key: "Mod-e", run: wrapCommand("`") },
  { key: "Mod-Shift-h", run: headingCommand },
  { key: "Mod-Shift-l", run: linkCommand },
];

/**
 * CodeMirror extension that registers all markdown formatting shortcuts.
 */
export const markdownKeymap = keymap.of(markdownBindings);
