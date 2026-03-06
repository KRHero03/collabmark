/**
 * Zustand store for managing comments on a document.
 * Handles CRUD operations, reply threading, reanchoring, and orphaning.
 */

import { create } from "zustand";
import { commentsApi, type CommentData, type CommentCreatePayload } from "../lib/api";

interface CommentsState {
  /** All top-level comments (with replies nested). */
  comments: CommentData[];
  loading: boolean;
  /** Fetch all comments for a document. */
  fetchComments: (docId: string) => Promise<void>;
  /** Create a new comment (inline or doc-level). */
  addComment: (docId: string, data: CommentCreatePayload) => Promise<CommentData>;
  /** Reply to an existing comment. */
  replyToComment: (commentId: string, content: string) => Promise<void>;
  /** Mark a comment as resolved. */
  resolveComment: (commentId: string) => Promise<void>;
  /** Update a comment's absolute anchor offsets after re-resolution. */
  reanchorComment: (commentId: string, anchorFrom: number, anchorTo: number) => Promise<void>;
  /** Mark a comment as orphaned (its anchored text was deleted). */
  orphanComment: (commentId: string) => Promise<void>;
  /** Delete a comment. */
  deleteComment: (commentId: string) => Promise<void>;
}

export const useComments = create<CommentsState>((set, get) => ({
  comments: [],
  loading: false,

  fetchComments: async (docId: string) => {
    set({ loading: true });
    try {
      const { data } = await commentsApi.list(docId);
      set({ comments: data, loading: false });
    } catch {
      set({ loading: false });
    }
  },

  addComment: async (docId, data) => {
    const { data: comment } = await commentsApi.create(docId, data);
    set({ comments: [comment, ...get().comments] });
    return comment;
  },

  replyToComment: async (commentId, content) => {
    const { data: reply } = await commentsApi.reply(commentId, { content });
    set({
      comments: get().comments.map((c) => (c.id === commentId ? { ...c, replies: [...c.replies, reply] } : c)),
    });
  },

  resolveComment: async (commentId) => {
    const { data: resolved } = await commentsApi.resolve(commentId);
    set({
      comments: get().comments.map((c) => (c.id === commentId ? { ...resolved, replies: c.replies } : c)),
    });
  },

  reanchorComment: async (commentId, anchorFrom, anchorTo) => {
    const { data: updated } = await commentsApi.reanchor(commentId, {
      anchor_from: anchorFrom,
      anchor_to: anchorTo,
    });
    set({
      comments: get().comments.map((c) => (c.id === commentId ? { ...updated, replies: c.replies } : c)),
    });
  },

  orphanComment: async (commentId) => {
    const { data: orphaned } = await commentsApi.orphan(commentId);
    set({
      comments: get().comments.map((c) => (c.id === commentId ? { ...orphaned, replies: c.replies } : c)),
    });
  },

  deleteComment: async (commentId) => {
    await commentsApi.delete(commentId);
    set({
      comments: get().comments.filter((c) => c.id !== commentId),
    });
  },
}));
