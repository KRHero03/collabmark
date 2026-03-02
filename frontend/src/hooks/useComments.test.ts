/**
 * Tests for the useComments Zustand store.
 *
 * Validates CRUD operations, reply threading, reanchoring, and orphaning
 * of comments via the commentsApi mock.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { useComments } from "./useComments";

vi.mock("../lib/api", () => ({
  commentsApi: {
    list: vi.fn(),
    create: vi.fn(),
    reply: vi.fn(),
    resolve: vi.fn(),
    reanchor: vi.fn(),
    orphan: vi.fn(),
    delete: vi.fn(),
  },
}));

import { commentsApi } from "../lib/api";
import type { CommentData } from "../lib/api";

function makeComment(overrides: Partial<CommentData> = {}): CommentData {
  return {
    id: "c1",
    document_id: "doc1",
    author_id: "u1",
    author_name: "Alice",
    content: "Test comment",
    anchor_from: null,
    anchor_to: null,
    anchor_from_relative: null,
    anchor_to_relative: null,
    quoted_text: null,
    parent_id: null,
    is_resolved: false,
    resolved_by: null,
    resolved_at: null,
    is_orphaned: false,
    orphaned_at: null,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    replies: [],
    ...overrides,
  };
}

describe("useComments store", () => {
  beforeEach(() => {
    useComments.setState({ comments: [], loading: false });
    vi.clearAllMocks();
  });

  it("should start with empty comments and loading false", () => {
    const state = useComments.getState();
    expect(state.comments).toEqual([]);
    expect(state.loading).toBe(false);
  });

  it("fetchComments should populate the store", async () => {
    const comments = [makeComment({ id: "c1" }), makeComment({ id: "c2" })];
    vi.mocked(commentsApi.list).mockResolvedValue({ data: comments } as never);

    await useComments.getState().fetchComments("doc1");

    const state = useComments.getState();
    expect(state.comments).toHaveLength(2);
    expect(state.comments[0].id).toBe("c1");
    expect(state.loading).toBe(false);
  });

  it("addComment should prepend to comments list", async () => {
    useComments.setState({ comments: [makeComment({ id: "c1" })] });
    const newComment = makeComment({ id: "c2", content: "New" });
    vi.mocked(commentsApi.create).mockResolvedValue({ data: newComment } as never);

    const result = await useComments.getState().addComment("doc1", { content: "New" });

    expect(result.id).toBe("c2");
    expect(useComments.getState().comments).toHaveLength(2);
    expect(useComments.getState().comments[0].id).toBe("c2");
  });

  it("replyToComment should add reply to parent", async () => {
    useComments.setState({
      comments: [makeComment({ id: "c1" })],
    });
    const reply = makeComment({ id: "r1", parent_id: "c1", content: "Reply" });
    vi.mocked(commentsApi.reply).mockResolvedValue({ data: reply } as never);

    await useComments.getState().replyToComment("c1", "Reply");

    const parent = useComments.getState().comments[0];
    expect(parent.replies).toHaveLength(1);
    expect(parent.replies[0].id).toBe("r1");
  });

  it("resolveComment should update the comment", async () => {
    useComments.setState({
      comments: [makeComment({ id: "c1" })],
    });
    const resolved = makeComment({ id: "c1", is_resolved: true, resolved_by: "u1" });
    vi.mocked(commentsApi.resolve).mockResolvedValue({ data: resolved } as never);

    await useComments.getState().resolveComment("c1");

    expect(useComments.getState().comments[0].is_resolved).toBe(true);
    expect(useComments.getState().comments[0].resolved_by).toBe("u1");
  });

  it("reanchorComment should update anchor offsets", async () => {
    useComments.setState({
      comments: [
        makeComment({
          id: "c1",
          anchor_from: 10,
          anchor_to: 20,
          anchor_from_relative: "AQAAAA==",
          anchor_to_relative: "BQAAAA==",
        }),
      ],
    });
    const updated = makeComment({
      id: "c1",
      anchor_from: 15,
      anchor_to: 25,
      anchor_from_relative: "AQAAAA==",
      anchor_to_relative: "BQAAAA==",
    });
    vi.mocked(commentsApi.reanchor).mockResolvedValue({ data: updated } as never);

    await useComments.getState().reanchorComment("c1", 15, 25);

    const comment = useComments.getState().comments[0];
    expect(comment.anchor_from).toBe(15);
    expect(comment.anchor_to).toBe(25);
    expect(commentsApi.reanchor).toHaveBeenCalledWith("c1", {
      anchor_from: 15,
      anchor_to: 25,
    });
  });

  it("orphanComment should mark comment as orphaned", async () => {
    useComments.setState({
      comments: [
        makeComment({
          id: "c1",
          anchor_from: 0,
          anchor_to: 10,
          quoted_text: "some text",
        }),
      ],
    });
    const orphaned = makeComment({
      id: "c1",
      is_orphaned: true,
      orphaned_at: "2026-03-02T12:00:00Z",
      anchor_from: 0,
      anchor_to: 10,
      quoted_text: "some text",
    });
    vi.mocked(commentsApi.orphan).mockResolvedValue({ data: orphaned } as never);

    await useComments.getState().orphanComment("c1");

    const comment = useComments.getState().comments[0];
    expect(comment.is_orphaned).toBe(true);
    expect(comment.orphaned_at).toBe("2026-03-02T12:00:00Z");
    expect(comment.quoted_text).toBe("some text");
  });

  it("deleteComment should remove from store", async () => {
    useComments.setState({
      comments: [makeComment({ id: "c1" }), makeComment({ id: "c2" })],
    });
    vi.mocked(commentsApi.delete).mockResolvedValue({} as never);

    await useComments.getState().deleteComment("c1");

    expect(useComments.getState().comments).toHaveLength(1);
    expect(useComments.getState().comments[0].id).toBe("c2");
  });

  it("orphanComment should preserve replies", async () => {
    const reply = makeComment({ id: "r1", parent_id: "c1", content: "Reply" });
    useComments.setState({
      comments: [makeComment({ id: "c1", replies: [reply] })],
    });
    const orphaned = makeComment({ id: "c1", is_orphaned: true });
    vi.mocked(commentsApi.orphan).mockResolvedValue({ data: orphaned } as never);

    await useComments.getState().orphanComment("c1");

    const comment = useComments.getState().comments[0];
    expect(comment.is_orphaned).toBe(true);
    expect(comment.replies).toHaveLength(1);
    expect(comment.replies[0].id).toBe("r1");
  });
});
