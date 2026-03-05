/**
 * Tests for usePresence hook.
 *
 * Validates awareness state subscription, deduplication by name,
 * local client exclusion, missing/partial user fields, cleanup,
 * and null awareness handling.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { usePresence } from "./usePresence";

type ChangeHandler = () => void;

function createMockAwareness(
  localId: number,
  states: Map<number, Record<string, unknown>>,
) {
  const listeners = new Map<string, Set<ChangeHandler>>();

  return {
    clientID: localId,
    getStates: vi.fn(() => states),
    on: vi.fn((event: string, fn: ChangeHandler) => {
      if (!listeners.has(event)) listeners.set(event, new Set());
      listeners.get(event)!.add(fn);
    }),
    off: vi.fn((event: string, fn: ChangeHandler) => {
      listeners.get(event)?.delete(fn);
    }),
    _emit(event: string) {
      listeners.get(event)?.forEach((fn) => fn());
    },
    _listeners: listeners,
  };
}

describe("usePresence", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("returns empty array when awareness is null", () => {
    const { result } = renderHook(() => usePresence(null));
    expect(result.current).toEqual([]);
  });

  it("returns empty array when no remote clients exist", () => {
    const states = new Map<number, Record<string, unknown>>();
    states.set(1, { user: { name: "Me", color: "#abc" } });
    const awareness = createMockAwareness(1, states);

    const { result } = renderHook(() =>
      usePresence(awareness as never),
    );
    expect(result.current).toEqual([]);
  });

  it("returns remote peers excluding local client", () => {
    const states = new Map<number, Record<string, unknown>>();
    states.set(1, { user: { name: "Me", color: "#abc" } });
    states.set(2, {
      user: { name: "Alice", avatarUrl: "https://img/a.png", color: "#f00" },
    });
    states.set(3, {
      user: { name: "Bob", avatarUrl: null, color: "#0f0" },
    });
    const awareness = createMockAwareness(1, states);

    const { result } = renderHook(() =>
      usePresence(awareness as never),
    );

    expect(result.current).toHaveLength(2);
    expect(result.current).toEqual([
      { name: "Alice", avatarUrl: "https://img/a.png", color: "#f00" },
      { name: "Bob", avatarUrl: null, color: "#0f0" },
    ]);
  });

  it("deduplicates peers by name (keeps first occurrence)", () => {
    const states = new Map<number, Record<string, unknown>>();
    states.set(1, { user: { name: "Me" } });
    states.set(2, {
      user: { name: "Alice", avatarUrl: "https://img/a1.png", color: "#f00" },
    });
    states.set(3, {
      user: { name: "Alice", avatarUrl: "https://img/a2.png", color: "#00f" },
    });
    const awareness = createMockAwareness(1, states);

    const { result } = renderHook(() =>
      usePresence(awareness as never),
    );

    expect(result.current).toHaveLength(1);
    expect(result.current[0].avatarUrl).toBe("https://img/a1.png");
    expect(result.current[0].color).toBe("#f00");
  });

  it("skips clients with no user field", () => {
    const states = new Map<number, Record<string, unknown>>();
    states.set(1, { user: { name: "Me" } });
    states.set(2, {});
    states.set(3, { user: { name: "Bob", color: "#0f0" } });
    const awareness = createMockAwareness(1, states);

    const { result } = renderHook(() =>
      usePresence(awareness as never),
    );

    expect(result.current).toHaveLength(1);
    expect(result.current[0].name).toBe("Bob");
  });

  it("skips clients with user field but no name", () => {
    const states = new Map<number, Record<string, unknown>>();
    states.set(1, { user: { name: "Me" } });
    states.set(2, { user: { color: "#f00" } });
    states.set(3, { user: { name: "", color: "#0f0" } });
    const awareness = createMockAwareness(1, states);

    const { result } = renderHook(() =>
      usePresence(awareness as never),
    );

    expect(result.current).toEqual([]);
  });

  it("defaults avatarUrl to null when missing", () => {
    const states = new Map<number, Record<string, unknown>>();
    states.set(1, { user: { name: "Me" } });
    states.set(2, { user: { name: "Alice", color: "#f00" } });
    const awareness = createMockAwareness(1, states);

    const { result } = renderHook(() =>
      usePresence(awareness as never),
    );

    expect(result.current[0].avatarUrl).toBeNull();
  });

  it("defaults color to #6b7280 when missing", () => {
    const states = new Map<number, Record<string, unknown>>();
    states.set(1, { user: { name: "Me" } });
    states.set(2, { user: { name: "Alice" } });
    const awareness = createMockAwareness(1, states);

    const { result } = renderHook(() =>
      usePresence(awareness as never),
    );

    expect(result.current[0].color).toBe("#6b7280");
  });

  it("subscribes to 'change' event and updates on awareness changes", () => {
    const states = new Map<number, Record<string, unknown>>();
    states.set(1, { user: { name: "Me" } });
    const awareness = createMockAwareness(1, states);

    const { result } = renderHook(() =>
      usePresence(awareness as never),
    );
    expect(result.current).toEqual([]);
    expect(awareness.on).toHaveBeenCalledWith("change", expect.any(Function));

    states.set(2, { user: { name: "Alice", color: "#f00" } });

    act(() => {
      awareness._emit("change");
    });

    expect(result.current).toHaveLength(1);
    expect(result.current[0].name).toBe("Alice");
  });

  it("unsubscribes from 'change' event on unmount", () => {
    const states = new Map<number, Record<string, unknown>>();
    states.set(1, { user: { name: "Me" } });
    const awareness = createMockAwareness(1, states);

    const { unmount } = renderHook(() =>
      usePresence(awareness as never),
    );

    const registeredFn = awareness.on.mock.calls.find(
      (c: [string, ChangeHandler]) => c[0] === "change",
    )?.[1];
    expect(registeredFn).toBeDefined();

    unmount();

    expect(awareness.off).toHaveBeenCalledWith("change", registeredFn);
  });

  it("resets peers to empty when awareness changes to null", () => {
    const states = new Map<number, Record<string, unknown>>();
    states.set(1, { user: { name: "Me" } });
    states.set(2, { user: { name: "Alice", color: "#f00" } });
    const awareness = createMockAwareness(1, states);

    const { result, rerender } = renderHook(
      ({ a }) => usePresence(a as never),
      { initialProps: { a: awareness } },
    );

    expect(result.current).toHaveLength(1);

    rerender({ a: null as never });

    expect(result.current).toEqual([]);
  });

  it("handles awareness with only local client state", () => {
    const states = new Map<number, Record<string, unknown>>();
    states.set(42, { user: { name: "Only Me", color: "#abc" } });
    const awareness = createMockAwareness(42, states);

    const { result } = renderHook(() =>
      usePresence(awareness as never),
    );
    expect(result.current).toEqual([]);
  });

  it("handles clients disappearing on awareness change", () => {
    const states = new Map<number, Record<string, unknown>>();
    states.set(1, { user: { name: "Me" } });
    states.set(2, { user: { name: "Alice", color: "#f00" } });
    states.set(3, { user: { name: "Bob", color: "#0f0" } });
    const awareness = createMockAwareness(1, states);

    const { result } = renderHook(() =>
      usePresence(awareness as never),
    );
    expect(result.current).toHaveLength(2);

    states.delete(3);

    act(() => {
      awareness._emit("change");
    });

    expect(result.current).toHaveLength(1);
    expect(result.current[0].name).toBe("Alice");
  });
});
