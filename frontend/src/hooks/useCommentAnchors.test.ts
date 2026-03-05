/**
 * Tests for useCommentAnchors hook.
 *
 * Uses real Yjs (no mock) and mocks only axios to avoid network calls.
 * Run with: npx vitest run src/hooks/useCommentAnchors.test.ts
 *
 * Note: This file uses vi.mock("axios") which must be hoisted. If tests hang,
 * try running with --no-file-parallelism or run this file in isolation.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import * as Y from "yjs";
import { useCommentAnchors } from "./useCommentAnchors";
import { commentsApi } from "../lib/api";
import type { CommentData } from "../lib/api";

vi.mock("axios", () => {
  const mockAxios = {
    create: vi.fn(() => mockAxios),
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
    interceptors: {
      request: { use: vi.fn() },
      response: { use: vi.fn() },
    },
  };
  return { default: mockAxios };
});

function makeYDocWithText(content: string) {
  const ydoc = new Y.Doc();
  const ytext = ydoc.getText("content");
  ytext.insert(0, content);
  return { ydoc, ytext };
}

function makeComment(overrides: Partial<CommentData> = {}): CommentData {
  return {
    id: "c1",
    document_id: "doc-1",
    author_id: "user-1",
    author_name: "Test User",
    author_avatar_url: null,
    content: "A comment",
    anchor_from: 0,
    anchor_to: 5,
    anchor_from_relative: null,
    anchor_to_relative: null,
    quoted_text: null,
    parent_id: null,
    is_resolved: false,
    resolved_by: null,
    resolved_at: null,
    is_orphaned: false,
    orphaned_at: null,
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T00:00:00Z",
    replies: [],
    ...overrides,
  };
}

function uint8ToBase64(bytes: Uint8Array): string {
  let binary = "";
  for (let i = 0; i < bytes.length; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  return btoa(binary);
}

function createRelativePositions(
  ytext: Y.Text,
  from: number,
  to: number,
): { anchor_from_relative: string; anchor_to_relative: string } {
  const relFrom = Y.createRelativePositionFromTypeIndex(ytext, from);
  const relTo = Y.createRelativePositionFromTypeIndex(ytext, to);
  return {
    anchor_from_relative: uint8ToBase64(Y.encodeRelativePosition(relFrom)),
    anchor_to_relative: uint8ToBase64(Y.encodeRelativePosition(relTo)),
  };
}

// Note: These tests may hang in some environments during module load.
// If they hang, run with: npx vitest run src/hooks/useCommentAnchors.test.ts --no-file-parallelism
describe("useCommentAnchors", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(commentsApi, "orphan").mockResolvedValue(undefined as never);
    vi.spyOn(commentsApi, "reanchor").mockResolvedValue(undefined as never);
  });

  it("returns empty map when no comments provided", () => {
    const { ydoc, ytext } = makeYDocWithText("hello");

    const { result } = renderHook(() =>
      useCommentAnchors({
        ytext,
        ydoc,
        comments: [],
        synced: true,
      }),
    );

    expect(result.current.size).toBe(0);
  });

  it("returns empty map when synced is false", () => {
    const { ydoc, ytext } = makeYDocWithText("hello world");
    const comments = [
      makeComment({ id: "c1", anchor_from: 0, anchor_to: 5 }),
    ];

    const { result } = renderHook(() =>
      useCommentAnchors({
        ytext,
        ydoc,
        comments,
        synced: false,
      }),
    );

    expect(result.current.size).toBe(0);
  });

  it("correctly resolves anchors for comments with valid ranges (no relative positions)", () => {
    const { ydoc, ytext } = makeYDocWithText("hello world");
    const comments = [
      makeComment({
        id: "c1",
        anchor_from: 0,
        anchor_to: 5,
        quoted_text: "hello",
      }),
    ];

    const { result } = renderHook(() =>
      useCommentAnchors({
        ytext,
        ydoc,
        comments,
        synced: true,
      }),
    );

    expect(result.current.size).toBe(1);
    const anchor = result.current.get("c1");
    expect(anchor).toBeDefined();
    expect(anchor?.from).toBe(0);
    expect(anchor?.to).toBe(5);
    expect(anchor?.status).toBe("exact");
  });

  it("returns modified status when quoted text does not match slice", () => {
    const { ydoc, ytext } = makeYDocWithText("hallo world");
    const comments = [
      makeComment({
        id: "c1",
        anchor_from: 0,
        anchor_to: 5,
        quoted_text: "hello",
      }),
    ];

    const { result } = renderHook(() =>
      useCommentAnchors({
        ytext,
        ydoc,
        comments,
        synced: true,
      }),
    );

    const anchor = result.current.get("c1");
    expect(anchor?.status).toBe("modified");
    expect(anchor?.from).toBe(0);
    expect(anchor?.to).toBe(5);
  });

  it("handles orphaned comments (is_orphaned: true)", () => {
    const { ydoc, ytext } = makeYDocWithText("hello world");
    const comments = [
      makeComment({
        id: "c1",
        anchor_from: 2,
        anchor_to: 7,
        is_orphaned: true,
      }),
    ];

    const { result } = renderHook(() =>
      useCommentAnchors({
        ytext,
        ydoc,
        comments,
        synced: true,
      }),
    );

    const anchor = result.current.get("c1");
    expect(anchor).toBeDefined();
    expect(anchor?.from).toBe(2);
    expect(anchor?.to).toBe(7);
    expect(anchor?.status).toBe("orphaned");
  });

  it("handles orphaned comments with null anchor_from/anchor_to", () => {
    const { ydoc, ytext } = makeYDocWithText("hello world");
    const comments = [
      makeComment({
        id: "c1",
        anchor_from: null,
        anchor_to: null,
        is_orphaned: true,
      }),
    ];

    const { result } = renderHook(() =>
      useCommentAnchors({
        ytext,
        ydoc,
        comments,
        synced: true,
      }),
    );

    const anchor = result.current.get("c1");
    expect(anchor?.from).toBe(0);
    expect(anchor?.to).toBe(0);
    expect(anchor?.status).toBe("orphaned");
  });

  it("skips replies (comments with parent_id)", () => {
    const { ydoc, ytext } = makeYDocWithText("hello world");
    const comments = [
      makeComment({
        id: "reply-1",
        parent_id: "parent-1",
        anchor_from: 0,
        anchor_to: 5,
      }),
    ];

    const { result } = renderHook(() =>
      useCommentAnchors({
        ytext,
        ydoc,
        comments,
        synced: true,
      }),
    );

    expect(result.current.size).toBe(0);
    expect(result.current.has("reply-1")).toBe(false);
  });

  it("resolves anchors via relative positions when using real Yjs", () => {
    const { ydoc, ytext } = makeYDocWithText("hello world");
    const { anchor_from_relative, anchor_to_relative } =
      createRelativePositions(ytext, 3, 8);
    const comments = [
      makeComment({
        id: "c1",
        anchor_from: 0,
        anchor_to: 5,
        anchor_from_relative,
        anchor_to_relative,
        quoted_text: "lo wo",
      }),
    ];

    const { result } = renderHook(() =>
      useCommentAnchors({
        ytext,
        ydoc,
        comments,
        synced: true,
      }),
    );

    const anchor = result.current.get("c1");
    expect(anchor?.from).toBe(3);
    expect(anchor?.to).toBe(8);
    expect(anchor?.status).toBe("exact");
  });

  it("returns orphaned when relative position resolves to null (deleted content)", () => {
    const { ydoc, ytext } = makeYDocWithText("hello world");
    const { anchor_from_relative, anchor_to_relative } =
      createRelativePositions(ytext, 3, 8);
    const comments = [
      makeComment({
        id: "c1",
        anchor_from: 0,
        anchor_to: 5,
        anchor_from_relative,
        anchor_to_relative,
      }),
    ];

    ytext.delete(0, 12);
    ytext.insert(0, "x");

    const { result } = renderHook(() =>
      useCommentAnchors({
        ytext,
        ydoc,
        comments,
        synced: true,
      }),
    );

    const anchor = result.current.get("c1");
    expect(anchor?.status).toBe("orphaned");
  });

  it("returns orphaned when from >= to (collapsed range)", () => {
    const { ydoc, ytext } = makeYDocWithText("hello world");
    const { anchor_from_relative, anchor_to_relative } =
      createRelativePositions(ytext, 5, 5);
    const comments = [
      makeComment({
        id: "c1",
        anchor_from: 0,
        anchor_to: 5,
        anchor_from_relative,
        anchor_to_relative,
      }),
    ];

    const { result } = renderHook(() =>
      useCommentAnchors({
        ytext,
        ydoc,
        comments,
        synced: true,
      }),
    );

    const anchor = result.current.get("c1");
    expect(anchor?.status).toBe("orphaned");
    expect(anchor?.from).toBe(5);
    expect(anchor?.to).toBe(5);
  });

  it("returns orphaned when decodeRelativePosition throws (invalid base64)", () => {
    const { ydoc, ytext } = makeYDocWithText("hello world");
    const comments = [
      makeComment({
        id: "c1",
        anchor_from: 0,
        anchor_to: 5,
        anchor_from_relative: "invalid!!!",
        anchor_to_relative: "invalid!!!",
      }),
    ];

    const { result } = renderHook(() =>
      useCommentAnchors({
        ytext,
        ydoc,
        comments,
        synced: true,
      }),
    );

    const anchor = result.current.get("c1");
    expect(anchor?.status).toBe("orphaned");
  });

  it("calls commentsApi.orphan when resolved status is orphaned and comment is not yet orphaned", async () => {
    const { ydoc, ytext } = makeYDocWithText("hello world");
    const { anchor_from_relative, anchor_to_relative } =
      createRelativePositions(ytext, 3, 8);
    const comments = [
      makeComment({
        id: "c1",
        anchor_from: 0,
        anchor_to: 5,
        anchor_from_relative,
        anchor_to_relative,
        is_orphaned: false,
      }),
    ];

    renderHook(() =>
      useCommentAnchors({
        ytext,
        ydoc,
        comments,
        synced: true,
      }),
    );

    ytext.delete(0, 12);

    await act(async () => {
      await new Promise((r) => setTimeout(r, 100));
    });

    expect(commentsApi.orphan).toHaveBeenCalledWith("c1");
  });

  it("does not call commentsApi.orphan when comment is already orphaned", () => {
    const { ydoc, ytext } = makeYDocWithText("hello world");
    const comments = [
      makeComment({
        id: "c1",
        anchor_from: 0,
        anchor_to: 5,
        is_orphaned: true,
      }),
    ];

    renderHook(() =>
      useCommentAnchors({
        ytext,
        ydoc,
        comments,
        synced: true,
      }),
    );

    expect(commentsApi.orphan).not.toHaveBeenCalled();
  });

  it("recalculates when comments change", () => {
    const { ydoc, ytext } = makeYDocWithText("hello world");

    const { result, rerender } = renderHook(
      ({ comments }) =>
        useCommentAnchors({
          ytext,
          ydoc,
          comments,
          synced: true,
        }),
      {
        initialProps: { comments: [] as CommentData[] },
      },
    );

    expect(result.current.size).toBe(0);

    rerender({
      comments: [
        makeComment({ id: "c1", anchor_from: 0, anchor_to: 5 }),
      ],
    });

    expect(result.current.size).toBe(1);
    expect(result.current.get("c1")?.from).toBe(0);
    expect(result.current.get("c1")?.to).toBe(5);
  });

  it("recalculates when ytext content changes via observe", async () => {
    const { ydoc, ytext } = makeYDocWithText("hello");
    const comments = [
      makeComment({
        id: "c1",
        anchor_from: 0,
        anchor_to: 5,
        quoted_text: "hello",
      }),
    ];

    const { result } = renderHook(() =>
      useCommentAnchors({
        ytext,
        ydoc,
        comments,
        synced: true,
      }),
    );

    expect(result.current.get("c1")?.status).toBe("exact");

    ytext.delete(0, 5);
    ytext.insert(0, "hallo");

    await act(async () => {
      await new Promise((r) => setTimeout(r, 600));
    });

    const anchor = result.current.get("c1");
    expect(anchor?.status).toBe("modified");
  });

  it("excludes doc-level comments (null anchor_from and anchor_to, no relative)", () => {
    const { ydoc, ytext } = makeYDocWithText("hello world");
    const comments = [
      makeComment({
        id: "c1",
        anchor_from: null,
        anchor_to: null,
        anchor_from_relative: null,
        anchor_to_relative: null,
      }),
    ];

    const { result } = renderHook(() =>
      useCommentAnchors({
        ytext,
        ydoc,
        comments,
        synced: true,
      }),
    );

    expect(result.current.size).toBe(0);
    expect(result.current.has("c1")).toBe(false);
  });

  it("handles resolved comments (is_resolved does not affect anchor resolution)", () => {
    const { ydoc, ytext } = makeYDocWithText("hello world");
    const comments = [
      makeComment({
        id: "c1",
        anchor_from: 0,
        anchor_to: 5,
        quoted_text: "hello",
        is_resolved: true,
      }),
    ];

    const { result } = renderHook(() =>
      useCommentAnchors({
        ytext,
        ydoc,
        comments,
        synced: true,
      }),
    );

    const anchor = result.current.get("c1");
    expect(anchor).toBeDefined();
    expect(anchor?.status).toBe("exact");
  });
});
