/**
 * Hook for resolving inline comment anchors against a live Yjs document.
 *
 * Takes stored Yjs RelativePositions (Base64-encoded) and resolves them to
 * current absolute character offsets using the live Y.Doc. Detects three
 * anchor states:
 * - "exact": resolved range text matches the stored quoted_text
 * - "modified": range resolves but text has changed
 * - "orphaned": range collapsed (text was deleted) or already marked orphaned
 *
 * Also handles drift detection: when resolved offsets diverge from stored
 * absolute offsets, batches reanchor API calls (debounced).
 */

import { useCallback, useEffect, useRef, useState } from "react";
import * as Y from "yjs";
import type { CommentData } from "../lib/api";
import { commentsApi } from "../lib/api";

export type AnchorStatus = "exact" | "modified" | "orphaned";

export interface ResolvedAnchor {
  from: number;
  to: number;
  status: AnchorStatus;
}

/** Decode a Base64 string to a Uint8Array. */
function base64ToUint8(b64: string): Uint8Array {
  const binary = atob(b64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes;
}

/**
 * Resolve a single comment's anchors against the current Y.Doc state.
 *
 * Returns null for doc-level comments or if relative positions are missing.
 */
function resolveComment(
  comment: CommentData,
  ytext: Y.Text,
  ydoc: Y.Doc,
): ResolvedAnchor | null {
  if (comment.is_orphaned) {
    return {
      from: comment.anchor_from ?? 0,
      to: comment.anchor_to ?? 0,
      status: "orphaned",
    };
  }

  if (!comment.anchor_from_relative || !comment.anchor_to_relative) {
    if (comment.anchor_from != null && comment.anchor_to != null) {
      const docText = ytext.toString();
      const slice = docText.slice(comment.anchor_from, comment.anchor_to);
      const status: AnchorStatus =
        comment.quoted_text && slice === comment.quoted_text
          ? "exact"
          : comment.quoted_text
            ? "modified"
            : "exact";
      return { from: comment.anchor_from, to: comment.anchor_to, status };
    }
    return null;
  }

  try {
    const relFrom = Y.decodeRelativePosition(
      base64ToUint8(comment.anchor_from_relative),
    );
    const relTo = Y.decodeRelativePosition(
      base64ToUint8(comment.anchor_to_relative),
    );

    const absFrom = Y.createAbsolutePositionFromRelativePosition(
      relFrom,
      ydoc,
    );
    const absTo = Y.createAbsolutePositionFromRelativePosition(relTo, ydoc);

    if (!absFrom || !absTo) {
      return {
        from: comment.anchor_from ?? 0,
        to: comment.anchor_to ?? 0,
        status: "orphaned",
      };
    }

    const from = absFrom.index;
    const to = absTo.index;

    if (from >= to) {
      return { from, to, status: "orphaned" };
    }

    const docText = ytext.toString();
    const currentSlice = docText.slice(from, to);

    let status: AnchorStatus;
    if (comment.quoted_text && currentSlice === comment.quoted_text) {
      status = "exact";
    } else if (comment.quoted_text) {
      status = "modified";
    } else {
      status = "exact";
    }

    return { from, to, status };
  } catch {
    return {
      from: comment.anchor_from ?? 0,
      to: comment.anchor_to ?? 0,
      status: "orphaned",
    };
  }
}

interface UseCommentAnchorsOptions {
  /** The shared Y.Text for the document. */
  ytext: Y.Text;
  /** The Yjs document instance. */
  ydoc: Y.Doc;
  /** The list of comments to resolve. */
  comments: CommentData[];
  /** Whether the Yjs provider has synced. */
  synced: boolean;
}

/**
 * Resolves inline comment anchors against a live Yjs document.
 *
 * @returns A map from comment ID to its resolved anchor (position + status).
 *          Doc-level comments (no anchor) are not included in the map.
 */
export function useCommentAnchors({
  ytext,
  ydoc,
  comments,
  synced,
}: UseCommentAnchorsOptions): Map<string, ResolvedAnchor> {
  const [anchors, setAnchors] = useState<Map<string, ResolvedAnchor>>(
    new Map(),
  );
  const reanchorTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const orphanQueueRef = useRef<Set<string>>(new Set());

  const resolveAll = useCallback(() => {
    if (!synced) return;

    const newAnchors = new Map<string, ResolvedAnchor>();
    const driftedComments: Array<{
      id: string;
      from: number;
      to: number;
    }> = [];

    for (const comment of comments) {
      if (comment.parent_id) continue;

      const resolved = resolveComment(comment, ytext, ydoc);
      if (!resolved) continue;

      newAnchors.set(comment.id, resolved);

      if (
        resolved.status === "orphaned" &&
        !comment.is_orphaned &&
        !orphanQueueRef.current.has(comment.id)
      ) {
        orphanQueueRef.current.add(comment.id);
        commentsApi.orphan(comment.id).catch(() => {
          orphanQueueRef.current.delete(comment.id);
        });
      }

      if (
        resolved.status !== "orphaned" &&
        comment.anchor_from != null &&
        (resolved.from !== comment.anchor_from ||
          resolved.to !== comment.anchor_to)
      ) {
        driftedComments.push({
          id: comment.id,
          from: resolved.from,
          to: resolved.to,
        });
      }
    }

    setAnchors(newAnchors);

    if (driftedComments.length > 0) {
      if (reanchorTimerRef.current) clearTimeout(reanchorTimerRef.current);
      reanchorTimerRef.current = setTimeout(() => {
        for (const { id, from, to } of driftedComments) {
          commentsApi
            .reanchor(id, { anchor_from: from, anchor_to: to })
            .catch(() => {});
        }
      }, 2000);
    }
  }, [comments, ytext, ydoc, synced]);

  useEffect(() => {
    resolveAll();
  }, [resolveAll]);

  useEffect(() => {
    if (!synced) return;

    let debounceTimer: ReturnType<typeof setTimeout> | null = null;

    const handler = () => {
      if (debounceTimer) clearTimeout(debounceTimer);
      debounceTimer = setTimeout(resolveAll, 500);
    };

    ytext.observe(handler);
    return () => {
      ytext.unobserve(handler);
      if (debounceTimer) clearTimeout(debounceTimer);
    };
  }, [ytext, synced, resolveAll]);

  useEffect(() => {
    return () => {
      if (reanchorTimerRef.current) clearTimeout(reanchorTimerRef.current);
    };
  }, []);

  return anchors;
}
