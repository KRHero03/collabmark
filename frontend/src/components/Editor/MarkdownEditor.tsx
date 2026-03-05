/**
 * Collaborative Markdown editor component using CodeMirror 6 and Yjs.
 *
 * When `ytext` and `awareness` are provided, the editor operates in
 * collaborative mode with real-time sync and cursor presence. Otherwise
 * it falls back to a simple controlled editor.
 *
 * Exposes the EditorView via `onViewReady` so the parent can query pixel
 * coordinates for comment positioning. Emits text selection events via
 * `onSelectionChange` and shows a floating "Comment" button on selection.
 *
 * Renders inline comment highlights using CodeMirror Decoration.mark for
 * any anchored comments whose resolved positions are supplied via `commentRanges`.
 */

import { useEffect, useRef, useCallback, useState } from "react";
import { EditorView, basicSetup } from "codemirror";
import { EditorState } from "@codemirror/state";
import { Decoration, type DecorationSet } from "@codemirror/view";
import { StateField, StateEffect } from "@codemirror/state";
import { markdown } from "@codemirror/lang-markdown";
import { languages } from "@codemirror/language-data";
import { yCollab } from "y-codemirror.next";
import { MessageSquarePlus } from "lucide-react";
import * as Y from "yjs";
import type { Awareness } from "y-protocols/awareness";
import type { AnchorStatus } from "../../hooks/useCommentAnchors";
import { markdownKeymap } from "./markdownShortcuts";

/** Selection range in absolute character offsets. */
export interface EditorSelection {
  from: number;
  to: number;
  text: string;
}

/** A resolved comment range for highlight decoration. */
export interface CommentRange {
  from: number;
  to: number;
  status: AnchorStatus;
  commentId: string;
}

interface MarkdownEditorProps {
  /** The shared Y.Text type for collaborative content sync. */
  ytext: Y.Text;
  /** The Yjs awareness instance for cursor presence. */
  awareness: Awareness;
  /** The current user's display name (shown in remote cursors). */
  userName?: string;
  /** The current user's avatar URL for presence display. */
  userAvatarUrl?: string | null;
  /** The current user's cursor color. */
  userColor?: string;
  /** Callback when the EditorView is ready (for pixel coordinate queries). */
  onViewReady?: (view: EditorView) => void;
  /** Callback when the user's text selection changes. */
  onSelectionChange?: (selection: EditorSelection | null) => void;
  /** Callback when the user clicks the floating "Comment" button. */
  onAddComment?: (selection: EditorSelection) => void;
  /** Resolved comment ranges to highlight in the editor. */
  commentRanges?: CommentRange[];
  /** When true, the editor is non-editable (view-only users). */
  readOnly?: boolean;
}

function randomColor(): string {
  const colors = [
    "#30bced", "#6eeb83", "#ffbc42", "#e84855",
    "#8ac926", "#ff595e", "#1982c4", "#6a4c93",
  ];
  return colors[Math.floor(Math.random() * colors.length)];
}

const setCommentDecorations = StateEffect.define<DecorationSet>();

const commentDecoField = StateField.define<DecorationSet>({
  create() {
    return Decoration.none;
  },
  update(decos, tr) {
    for (const e of tr.effects) {
      if (e.is(setCommentDecorations)) return e.value;
    }
    return decos.map(tr.changes);
  },
  provide: (f) => EditorView.decorations.from(f),
});

const exactMark = Decoration.mark({ class: "cm-comment-highlight-exact" });
const modifiedMark = Decoration.mark({ class: "cm-comment-highlight-modified" });

function buildDecorations(ranges: CommentRange[], docLength: number): DecorationSet {
  const builder: Array<{ from: number; to: number; deco: typeof exactMark }> = [];

  for (const r of ranges) {
    if (r.status === "orphaned") continue;
    const from = Math.max(0, Math.min(r.from, docLength));
    const to = Math.max(from, Math.min(r.to, docLength));
    if (from === to) continue;
    builder.push({
      from,
      to,
      deco: r.status === "modified" ? modifiedMark : exactMark,
    });
  }

  builder.sort((a, b) => a.from - b.from || a.to - b.to);
  const sorted = builder.map(({ from, to, deco }) => deco.range(from, to));
  return Decoration.set(sorted);
}

export function MarkdownEditor({
  ytext,
  awareness,
  userName = "Anonymous",
  userAvatarUrl,
  userColor,
  onViewReady,
  onSelectionChange,
  onAddComment,
  commentRanges,
  readOnly = false,
}: MarkdownEditorProps) {
  const editorRef = useRef<HTMLDivElement>(null);
  const viewRef = useRef<EditorView | null>(null);
  const [floatingBtn, setFloatingBtn] = useState<{
    x: number;
    y: number;
    selection: EditorSelection;
  } | null>(null);

  const onSelectionChangeRef = useRef(onSelectionChange);
  onSelectionChangeRef.current = onSelectionChange;

  const handleCommentClick = useCallback(() => {
    if (floatingBtn && onAddComment) {
      onAddComment(floatingBtn.selection);
    }
    setFloatingBtn(null);
  }, [floatingBtn, onAddComment]);

  useEffect(() => {
    if (!editorRef.current) return;

    const color = userColor || randomColor();

    awareness.setLocalStateField("user", {
      name: userName,
      avatarUrl: userAvatarUrl ?? null,
      color,
      colorLight: color + "33",
    });

    const selectionListener = EditorView.updateListener.of((update) => {
      if (!update.selectionSet && !update.focusChanged) return;

      const sel = update.state.selection.main;
      if (sel.from === sel.to) {
        onSelectionChangeRef.current?.(null);
        setFloatingBtn(null);
        return;
      }

      const text = update.state.doc.sliceString(sel.from, sel.to);
      const editorSel: EditorSelection = {
        from: sel.from,
        to: sel.to,
        text,
      };
      onSelectionChangeRef.current?.(editorSel);

      const coords = update.view.coordsAtPos(sel.to);
      if (coords) {
        const editorRect = editorRef.current?.getBoundingClientRect();
        if (editorRect) {
          setFloatingBtn({
            x: coords.left - editorRect.left,
            y: coords.top - editorRect.top - 36,
            selection: editorSel,
          });
        }
      }
    });

    const readOnlyExtensions = readOnly
      ? [EditorState.readOnly.of(true), EditorView.editable.of(false)]
      : [];

    const state = EditorState.create({
      doc: ytext.toString(),
      extensions: [
        basicSetup,
        markdown({ codeLanguages: languages }),
        EditorView.lineWrapping,
        ...(!readOnly ? [markdownKeymap] : []),
        yCollab(ytext, awareness),
        commentDecoField,
        selectionListener,
        ...readOnlyExtensions,
        EditorView.theme({
          "&": { height: "100%" },
          ".cm-scroller": { overflow: "auto" },
          ".cm-comment-highlight-exact": {
            backgroundColor: "rgba(37, 99, 235, 0.12)",
            borderBottom: "2px solid rgba(37, 99, 235, 0.4)",
          },
          ".cm-comment-highlight-modified": {
            backgroundColor: "rgba(245, 158, 11, 0.12)",
            borderBottom: "2px solid rgba(245, 158, 11, 0.4)",
          },
        }),
      ],
    });

    const view = new EditorView({
      state,
      parent: editorRef.current,
    });
    viewRef.current = view;
    onViewReady?.(view);

    return () => {
      view.destroy();
      viewRef.current = null;
    };
  }, [ytext, awareness, userName, userAvatarUrl, userColor, onViewReady, readOnly]);

  useEffect(() => {
    const view = viewRef.current;
    if (!view || !commentRanges) return;

    const decos = buildDecorations(commentRanges, view.state.doc.length);
    view.dispatch({ effects: setCommentDecorations.of(decos) });
  }, [commentRanges]);

  return (
    <div ref={editorRef} className="relative h-full text-sm">
      {floatingBtn && onAddComment && (
        <button
          onClick={handleCommentClick}
          className="absolute z-50 flex items-center gap-1 rounded-md bg-[var(--color-primary)] px-2 py-1 text-xs font-medium text-white shadow-lg transition hover:bg-[var(--color-primary-hover)]"
          style={{ left: floatingBtn.x, top: floatingBtn.y }}
          title="Add comment on selection"
        >
          <MessageSquarePlus className="h-3.5 w-3.5" />
          Comment
        </button>
      )}
    </div>
  );
}
