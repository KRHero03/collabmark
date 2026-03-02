/**
 * Hook for mapping resolved comment anchors to pixel Y-coordinates
 * in the editor viewport, with a stacking algorithm for overlapping cards.
 *
 * Uses CodeMirror's `coordsAtPos` to translate character offsets into
 * pixel positions. When multiple comments resolve to the same line,
 * the stacking algorithm pushes subsequent cards below the previous one
 * with a small gap so they don't overlap.
 */

import { useCallback, useEffect, useState } from "react";
import type { EditorView } from "codemirror";
import type { ResolvedAnchor } from "./useCommentAnchors";

const CARD_HEIGHT_ESTIMATE = 100;
const CARD_GAP = 8;

export interface PositionedComment {
  commentId: string;
  /** Calculated Y position (px) relative to the editor container. */
  y: number;
  /** Ideal Y position before stacking adjustment. */
  idealY: number;
  /** True when the card was pushed away from its ideal position. */
  isDisplaced: boolean;
}

/**
 * Maps resolved comment anchors to pixel positions for the comment gutter.
 *
 * @param editorView - The CodeMirror EditorView instance (null if not ready).
 * @param anchors - Map of comment ID to resolved anchor from useCommentAnchors.
 * @param containerEl - The editor container DOM element for offset calculation.
 * @returns An array of positioned comments sorted by Y coordinate.
 */
export function useCommentPositions(
  editorView: EditorView | null,
  anchors: Map<string, ResolvedAnchor>,
  containerEl: HTMLElement | null,
): PositionedComment[] {
  const [positions, setPositions] = useState<PositionedComment[]>([]);

  const calculate = useCallback(() => {
    if (!editorView || !containerEl) {
      setPositions([]);
      return;
    }

    const containerRect = containerEl.getBoundingClientRect();
    const items: Array<{ commentId: string; idealY: number }> = [];

    for (const [commentId, anchor] of anchors) {
      if (anchor.status === "orphaned") continue;

      const coords = editorView.coordsAtPos(anchor.from);
      if (!coords) continue;

      const idealY = coords.top - containerRect.top + containerEl.scrollTop;
      items.push({ commentId, idealY });
    }

    items.sort((a, b) => a.idealY - b.idealY);

    const result: PositionedComment[] = [];
    let prevBottom = -Infinity;

    for (const item of items) {
      const y = Math.max(item.idealY, prevBottom + CARD_GAP);
      const isDisplaced = y !== item.idealY;

      result.push({
        commentId: item.commentId,
        y,
        idealY: item.idealY,
        isDisplaced,
      });

      prevBottom = y + CARD_HEIGHT_ESTIMATE;
    }

    setPositions(result);
  }, [editorView, anchors, containerEl]);

  useEffect(() => {
    calculate();
  }, [calculate]);

  useEffect(() => {
    if (!containerEl) return;

    const scrollTarget =
      containerEl.querySelector(".cm-scroller") || containerEl;

    const onScroll = () => calculate();
    scrollTarget.addEventListener("scroll", onScroll, { passive: true });

    const observer = new ResizeObserver(() => calculate());
    observer.observe(containerEl);

    return () => {
      scrollTarget.removeEventListener("scroll", onScroll);
      observer.disconnect();
    };
  }, [containerEl, calculate]);

  return positions;
}
