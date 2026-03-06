/**
 * Position-synced comments gutter (Google Docs style).
 *
 * Active inline comments are positioned at the Y-coordinate of their
 * anchored text in the editor. When multiple comments are on the same
 * line, a stacking algorithm pushes cards below each other with a gap.
 * Displaced cards show a connecting line to their ideal position.
 *
 * Orphaned comments (whose text was deleted) are displayed in a
 * separate section at the bottom of the panel.
 *
 * Doc-level comments (no anchor) appear in a general section.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { MessageSquare, Unlink, X } from "lucide-react";
import { CommentThread } from "./CommentThread";
import { useComments } from "../../hooks/useComments";
import type { ResolvedAnchor } from "../../hooks/useCommentAnchors";
import type { PositionedComment } from "../../hooks/useCommentPositions";
import type { CommentData, CommentCreatePayload } from "../../lib/api";

interface CommentsPanelProps {
  /** The document ID. */
  docId: string;
  /** Whether the panel is open. */
  open: boolean;
  /** Callback to close the panel. */
  onClose: () => void;
  /** Current user's ID for author checks. */
  currentUserId: string;
  /** Text currently selected in the editor, if any. */
  selectedText?: string;
  /** Selection range in the editor. */
  selectionRange?: { from: number; to: number };
  /** Base64-encoded Yjs RelativePositions for the current selection. */
  selectionRelative?: { from: string; to: string };
  /** Resolved anchor map from useCommentAnchors. */
  anchors?: Map<string, ResolvedAnchor>;
  /** Positioned comments from useCommentPositions. */
  positions?: PositionedComment[];
}

export function CommentsPanel({
  docId,
  open,
  onClose,
  currentUserId,
  selectedText,
  selectionRange,
  selectionRelative,
  anchors,
  positions,
}: CommentsPanelProps) {
  const { comments, loading, fetchComments, addComment, replyToComment, resolveComment, deleteComment } = useComments();

  const [newComment, setNewComment] = useState("");

  useEffect(() => {
    if (open) fetchComments(docId);
  }, [open, docId, fetchComments]);

  const handleCreate = useCallback(async () => {
    if (!newComment.trim()) return;

    const payload: CommentCreatePayload = {
      content: newComment.trim(),
      anchor_from: selectionRange?.from,
      anchor_to: selectionRange?.to,
      anchor_from_relative: selectionRelative?.from,
      anchor_to_relative: selectionRelative?.to,
      quoted_text: selectedText || undefined,
    };

    try {
      await addComment(docId, payload);
      setNewComment("");
    } catch {
      // Error is already handled inside useComments hook
    }
  }, [docId, newComment, selectedText, selectionRange, selectionRelative, addComment]);

  const { positionedComments, orphanedComments, docLevelComments } = useMemo(() => {
    const positioned: Array<{
      comment: CommentData;
      position: PositionedComment;
      anchor: ResolvedAnchor;
    }> = [];
    const orphaned: CommentData[] = [];
    const docLevel: CommentData[] = [];

    for (const comment of comments) {
      const anchor = anchors?.get(comment.id);
      const position = positions?.find((p) => p.commentId === comment.id);

      if (comment.is_orphaned || anchor?.status === "orphaned") {
        orphaned.push(comment);
      } else if (position && anchor) {
        positioned.push({ comment, position, anchor });
      } else {
        docLevel.push(comment);
      }
    }

    positioned.sort((a, b) => a.position.y - b.position.y);
    return {
      positionedComments: positioned,
      orphanedComments: orphaned,
      docLevelComments: docLevel,
    };
  }, [comments, anchors, positions]);

  if (!open) return null;

  const unresolvedCount = comments.filter((c) => !c.is_resolved).length;

  return (
    <div className="flex h-full w-full flex-col border-l border-[var(--color-border)] bg-white md:w-[360px]">
      <div className="flex items-center justify-between border-b border-[var(--color-border)] px-4 py-3">
        <h2 className="flex items-center gap-2 text-lg font-semibold">
          <MessageSquare className="h-5 w-5" />
          Comments
          {unresolvedCount > 0 && (
            <span className="rounded-full bg-[var(--color-primary)] px-2 py-0.5 text-xs text-white">
              {unresolvedCount}
            </span>
          )}
        </h2>
        <button onClick={onClose} className="rounded p-1 hover:bg-gray-100">
          <X className="h-5 w-5" />
        </button>
      </div>

      <div className="border-b border-[var(--color-border)] p-3">
        {selectedText && (
          <div className="mb-2 rounded border-l-2 border-[var(--color-primary)] bg-gray-50 px-2 py-1 text-xs italic text-[var(--color-text-muted)]">
            {selectedText.slice(0, 100)}
            {selectedText.length > 100 ? "..." : ""}
          </div>
        )}
        <div className="flex gap-2">
          <input
            value={newComment}
            onChange={(e) => setNewComment(e.target.value)}
            placeholder={selectedText ? "Comment on selection..." : "Add a comment..."}
            className="flex-1 rounded-md border border-[var(--color-border)] px-3 py-2 text-sm outline-none focus:border-[var(--color-primary)]"
            onKeyDown={(e) => e.key === "Enter" && handleCreate()}
          />
          <button
            onClick={handleCreate}
            className="rounded-md bg-[var(--color-primary)] px-3 py-2 text-sm font-medium text-white transition hover:bg-[var(--color-primary-hover)]"
          >
            Post
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-auto">
        {loading ? (
          <div className="flex justify-center py-10">
            <div className="h-6 w-6 animate-spin rounded-full border-2 border-[var(--color-primary)] border-t-transparent" />
          </div>
        ) : comments.length === 0 ? (
          <p className="py-10 text-center text-sm text-[var(--color-text-muted)]">No comments yet.</p>
        ) : (
          <>
            {/* Position-synced inline comments */}
            {positionedComments.length > 0 && (
              <div className="relative" style={{ minHeight: getMinHeight(positionedComments) }}>
                {positionedComments.map(({ comment, position, anchor }) => (
                  <div key={comment.id} className="absolute left-0 right-0 px-3" style={{ top: position.y }}>
                    {position.isDisplaced && (
                      <svg
                        className="pointer-events-none absolute -left-1 w-4"
                        style={{
                          top: 0,
                          height: Math.abs(position.y - position.idealY),
                          transform: `translateY(-${Math.abs(position.y - position.idealY)}px)`,
                        }}
                      >
                        <line
                          x1="8"
                          y1="0"
                          x2="8"
                          y2="100%"
                          stroke="var(--color-border)"
                          strokeWidth="1"
                          strokeDasharray="3 2"
                        />
                      </svg>
                    )}
                    <CommentThread
                      comment={comment}
                      currentUserId={currentUserId}
                      anchorStatus={anchor.status}
                      onReply={replyToComment}
                      onResolve={resolveComment}
                      onDelete={deleteComment}
                    />
                  </div>
                ))}
              </div>
            )}

            {/* Doc-level comments */}
            {docLevelComments.length > 0 && (
              <div className="space-y-2 p-3">
                {positionedComments.length > 0 && (
                  <div className="flex items-center gap-2 py-1 text-xs text-[var(--color-text-muted)]">
                    <div className="flex-1 border-t border-[var(--color-border)]" />
                    General
                    <div className="flex-1 border-t border-[var(--color-border)]" />
                  </div>
                )}
                {docLevelComments.map((comment) => (
                  <CommentThread
                    key={comment.id}
                    comment={comment}
                    currentUserId={currentUserId}
                    onReply={replyToComment}
                    onResolve={resolveComment}
                    onDelete={deleteComment}
                  />
                ))}
              </div>
            )}

            {/* Orphaned comments */}
            {orphanedComments.length > 0 && (
              <div className="space-y-2 p-3">
                <div className="flex items-center gap-2 py-1 text-xs text-amber-600">
                  <div className="flex-1 border-t border-amber-200" />
                  <Unlink className="h-3 w-3" />
                  Orphaned
                  <div className="flex-1 border-t border-amber-200" />
                </div>
                {orphanedComments.map((comment) => (
                  <CommentThread
                    key={comment.id}
                    comment={comment}
                    currentUserId={currentUserId}
                    anchorStatus="orphaned"
                    onReply={replyToComment}
                    onResolve={resolveComment}
                    onDelete={deleteComment}
                  />
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

/** Estimate the minimum height needed to contain all positioned cards. */
function getMinHeight(items: Array<{ position: PositionedComment }>): number {
  if (items.length === 0) return 0;
  const last = items[items.length - 1];
  return last.position.y + 120;
}
