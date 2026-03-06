/**
 * A single comment with optional replies, resolve, and delete actions.
 * Displays anchor status badges for modified or orphaned comments.
 */

import { useState } from "react";
import { AlertTriangle, Check, MessageSquare, Trash2, Unlink } from "lucide-react";
import type { CommentData } from "../../lib/api";
import type { AnchorStatus } from "../../hooks/useCommentAnchors";
import { formatDateTime } from "../../lib/dateUtils";
import { UserAvatar } from "../Layout/UserAvatar";

interface CommentThreadProps {
  comment: CommentData;
  currentUserId: string;
  /** Anchor resolution status: "exact", "modified", or "orphaned". */
  anchorStatus?: AnchorStatus;
  onReply: (commentId: string, content: string) => void;
  onResolve: (commentId: string) => void;
  onDelete: (commentId: string) => void;
}

export function CommentThread({
  comment,
  currentUserId,
  anchorStatus,
  onReply,
  onResolve,
  onDelete,
}: CommentThreadProps) {
  const [replyText, setReplyText] = useState("");
  const [showReply, setShowReply] = useState(false);

  const handleSubmitReply = () => {
    if (!replyText.trim()) return;
    onReply(comment.id, replyText.trim());
    setReplyText("");
    setShowReply(false);
  };

  const isOrphaned = anchorStatus === "orphaned" || comment.is_orphaned;
  const isModified = anchorStatus === "modified";

  return (
    <div
      className={`rounded-lg border p-3 ${
        comment.is_resolved
          ? "border-green-200 bg-green-50/50"
          : isOrphaned
            ? "border-amber-200 bg-amber-50/30"
            : "border-[var(--color-border)]"
      }`}
    >
      {isOrphaned && (
        <div className="mb-2 flex items-center gap-1.5 rounded bg-amber-50 px-2 py-1 text-xs text-amber-700">
          <Unlink className="h-3 w-3 flex-shrink-0" />
          Referenced text was removed
        </div>
      )}

      {isModified && !isOrphaned && (
        <div className="mb-2 flex items-center gap-1.5 rounded bg-amber-50 px-2 py-1 text-xs text-amber-600">
          <AlertTriangle className="h-3 w-3 flex-shrink-0" />
          Referenced text was modified
        </div>
      )}

      <div className="flex items-start justify-between">
        <div className="flex items-center gap-2">
          <UserAvatar url={comment.author_avatar_url} name={comment.author_name} size="sm" className="flex-shrink-0" />
          <div>
            <p className="text-sm font-medium">{comment.author_name}</p>
            <p className="text-xs text-[var(--color-text-muted)]">{formatDateTime(comment.created_at)}</p>
          </div>
        </div>
        <div className="flex gap-1">
          {!comment.is_resolved && (
            <button
              onClick={() => onResolve(comment.id)}
              title="Resolve"
              className="rounded p-1 text-[var(--color-text-muted)] hover:bg-green-50 hover:text-green-600"
            >
              <Check className="h-3.5 w-3.5" />
            </button>
          )}
          {comment.author_id === currentUserId && (
            <button
              onClick={() => onDelete(comment.id)}
              title="Delete"
              className="rounded p-1 text-[var(--color-text-muted)] hover:bg-red-50 hover:text-[var(--color-danger)]"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          )}
        </div>
      </div>

      {comment.quoted_text && (
        <div
          className={`mt-1 rounded border-l-2 px-2 py-1 text-xs italic ${
            isOrphaned
              ? "border-amber-300 bg-amber-50/50 text-[var(--color-text-muted)] line-through"
              : "border-[var(--color-primary)] bg-gray-50 text-[var(--color-text-muted)]"
          }`}
        >
          {comment.quoted_text}
        </div>
      )}

      <p className="mt-1 text-sm">{comment.content}</p>

      {comment.is_resolved && <p className="mt-1 text-xs text-green-600">Resolved</p>}

      {comment.replies.length > 0 && (
        <div className="mt-2 space-y-2 border-l-2 border-gray-200 pl-3">
          {comment.replies.map((reply) => (
            <div key={reply.id} className="flex gap-2">
              <UserAvatar
                url={reply.author_avatar_url}
                name={reply.author_name}
                size="sm"
                className="mt-0.5 flex-shrink-0"
              />
              <div>
                <p className="text-xs font-medium">{reply.author_name}</p>
                <p className="text-xs text-[var(--color-text-muted)]">{formatDateTime(reply.created_at)}</p>
                <p className="text-sm">{reply.content}</p>
              </div>
            </div>
          ))}
        </div>
      )}

      {!comment.is_resolved && (
        <div className="mt-2">
          {showReply ? (
            <div className="flex gap-1">
              <input
                value={replyText}
                onChange={(e) => setReplyText(e.target.value)}
                placeholder="Reply..."
                className="flex-1 rounded border border-[var(--color-border)] px-2 py-1 text-xs outline-none"
                onKeyDown={(e) => e.key === "Enter" && handleSubmitReply()}
              />
              <button
                onClick={handleSubmitReply}
                className="rounded bg-[var(--color-primary)] px-2 py-1 text-xs text-white"
              >
                Send
              </button>
            </div>
          ) : (
            <button
              onClick={() => setShowReply(true)}
              className="flex items-center gap-1 text-xs text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
            >
              <MessageSquare className="h-3 w-3" />
              Reply
            </button>
          )}
        </div>
      )}
    </div>
  );
}
