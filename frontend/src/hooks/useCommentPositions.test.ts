/**
 * Tests for the useCommentPositions stacking algorithm.
 *
 * Tests the positioning logic by mocking EditorView.coordsAtPos to return
 * controlled pixel coordinates, then verifying the stacking behavior when
 * multiple comments land on the same line.
 */

import { describe, it, expect, vi } from "vitest";
import { renderHook } from "@testing-library/react";
import { useCommentPositions } from "./useCommentPositions";
import type { ResolvedAnchor } from "./useCommentAnchors";

class MockResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver = MockResizeObserver as unknown as typeof ResizeObserver;

function makeMockEditorView(posToCoords: Record<number, { top: number; left: number; bottom: number }>) {
  return {
    coordsAtPos: vi.fn((pos: number) => posToCoords[pos] ?? null),
    state: { doc: { length: 1000 } },
  } as unknown as import("codemirror").EditorView;
}

function makeMockContainer(rect: Partial<DOMRect> = {}) {
  const el = document.createElement("div");

  el.getBoundingClientRect = () =>
    ({
      top: 0,
      left: 0,
      bottom: 600,
      right: 800,
      width: 800,
      height: 600,
      x: 0,
      y: 0,
      toJSON: () => ({}),
      ...rect,
    }) as DOMRect;

  Object.defineProperty(el, "scrollTop", { value: 0, writable: true });

  return el;
}

describe("useCommentPositions", () => {
  it("should return empty array when editorView is null", () => {
    const anchors = new Map<string, ResolvedAnchor>();
    const { result } = renderHook(() => useCommentPositions(null, anchors, null));
    expect(result.current).toEqual([]);
  });

  it("should position a single comment at its ideal Y", () => {
    const view = makeMockEditorView({
      10: { top: 100, left: 50, bottom: 120 },
    });
    const container = makeMockContainer();
    const anchors = new Map<string, ResolvedAnchor>([["c1", { from: 10, to: 20, status: "exact" }]]);

    const { result } = renderHook(() => useCommentPositions(view, anchors, container));

    expect(result.current).toHaveLength(1);
    expect(result.current[0].commentId).toBe("c1");
    expect(result.current[0].y).toBe(100);
    expect(result.current[0].idealY).toBe(100);
    expect(result.current[0].isDisplaced).toBe(false);
  });

  it("should stack comments on the same line", () => {
    const view = makeMockEditorView({
      10: { top: 100, left: 50, bottom: 120 },
      15: { top: 100, left: 80, bottom: 120 },
    });
    const container = makeMockContainer();
    const anchors = new Map<string, ResolvedAnchor>([
      ["c1", { from: 10, to: 14, status: "exact" }],
      ["c2", { from: 15, to: 20, status: "modified" }],
    ]);

    const { result } = renderHook(() => useCommentPositions(view, anchors, container));

    expect(result.current).toHaveLength(2);
    expect(result.current[0].commentId).toBe("c1");
    expect(result.current[0].y).toBe(100);
    expect(result.current[0].isDisplaced).toBe(false);

    expect(result.current[1].commentId).toBe("c2");
    expect(result.current[1].y).toBe(208); // 100 + 100 (card height) + 8 (gap)
    expect(result.current[1].idealY).toBe(100);
    expect(result.current[1].isDisplaced).toBe(true);
  });

  it("should skip orphaned comments", () => {
    const view = makeMockEditorView({
      10: { top: 100, left: 50, bottom: 120 },
    });
    const container = makeMockContainer();
    const anchors = new Map<string, ResolvedAnchor>([["c1", { from: 10, to: 20, status: "orphaned" }]]);

    const { result } = renderHook(() => useCommentPositions(view, anchors, container));

    expect(result.current).toEqual([]);
  });

  it("should sort comments by their ideal Y position", () => {
    const view = makeMockEditorView({
      50: { top: 300, left: 50, bottom: 320 },
      10: { top: 100, left: 50, bottom: 120 },
    });
    const container = makeMockContainer();
    const anchors = new Map<string, ResolvedAnchor>([
      ["c-lower", { from: 50, to: 60, status: "exact" }],
      ["c-upper", { from: 10, to: 20, status: "exact" }],
    ]);

    const { result } = renderHook(() => useCommentPositions(view, anchors, container));

    expect(result.current[0].commentId).toBe("c-upper");
    expect(result.current[1].commentId).toBe("c-lower");
  });

  it("should cascade stacking for three comments on same line", () => {
    const view = makeMockEditorView({
      10: { top: 50, left: 50, bottom: 70 },
      12: { top: 50, left: 60, bottom: 70 },
      14: { top: 50, left: 70, bottom: 70 },
    });
    const container = makeMockContainer();
    const anchors = new Map<string, ResolvedAnchor>([
      ["c1", { from: 10, to: 11, status: "exact" }],
      ["c2", { from: 12, to: 13, status: "exact" }],
      ["c3", { from: 14, to: 15, status: "exact" }],
    ]);

    const { result } = renderHook(() => useCommentPositions(view, anchors, container));

    expect(result.current).toHaveLength(3);
    expect(result.current[0].y).toBe(50);
    expect(result.current[1].y).toBe(158); // 50 + 100 + 8
    expect(result.current[2].y).toBe(266); // 158 + 100 + 8
  });
});
