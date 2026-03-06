/**
 * Tests for useYjsProvider hook.
 *
 * Validates Yjs document creation, WebSocket provider lifecycle,
 * sync state, cleanup on unmount/documentId change, and ytext from ydoc.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act, cleanup } from "@testing-library/react";
import * as Y from "yjs";
import { useYjsProvider } from "./useYjsProvider";

const mockOn = vi.fn();
const mockDisconnect = vi.fn();
const mockDestroy = vi.fn();
const providerCallArgs = vi.hoisted(() => [] as unknown[][]);

vi.mock("y-websocket", () => {
  class MockWebsocketProvider {
    constructor(...args: unknown[]) {
      providerCallArgs.push(args);
    }
    on = mockOn;
    disconnect = mockDisconnect;
    destroy = mockDestroy;
    awareness = {
      setLocalStateField: vi.fn(),
      on: vi.fn(),
      off: vi.fn(),
      getStates: vi.fn(() => new Map()),
      clientID: 1,
    };
  }
  return { WebsocketProvider: MockWebsocketProvider };
});

describe("useYjsProvider", () => {
  const originalLocation = window.location;

  beforeEach(() => {
    vi.clearAllMocks();
    providerCallArgs.length = 0;
    Object.defineProperty(window, "location", {
      value: { ...originalLocation, protocol: "http:", host: "localhost:5173" },
      writable: true,
    });
  });

  afterEach(() => {
    cleanup();
    Object.defineProperty(window, "location", {
      value: originalLocation,
      writable: true,
    });
  });

  it("returns ydoc, ytext, provider=null, synced=false when documentId is undefined", () => {
    const { result } = renderHook(() => useYjsProvider(undefined));

    expect(result.current.ydoc).toBeInstanceOf(Y.Doc);
    expect(result.current.ytext).toBeInstanceOf(Y.Text);
    expect(result.current.provider).toBeNull();
    expect(result.current.synced).toBe(false);
  });

  it("creates WebsocketProvider when documentId is provided", () => {
    const { result } = renderHook(() => useYjsProvider("doc-123"));

    expect(providerCallArgs).toHaveLength(1);
    expect(providerCallArgs[0][0]).toBe("ws://localhost:5173/ws/doc");
    expect(providerCallArgs[0][1]).toBe("doc-123");
    expect(providerCallArgs[0][2]).toBeInstanceOf(Y.Doc);

    // Trigger re-render via sync callback so providerRef is flushed to result
    const syncCallback = mockOn.mock.calls.find((c) => c[0] === "sync")?.[1];
    act(() => syncCallback(true));

    expect(result.current.provider).not.toBeNull();
    expect(result.current.ydoc).toBeInstanceOf(Y.Doc);
    expect(result.current.ytext).toBeInstanceOf(Y.Text);
  });

  it("provider is created with correct WS URL (ws:// for http:, wss:// for https:)", () => {
    Object.defineProperty(window, "location", {
      value: { ...originalLocation, protocol: "http:", host: "example.com:8080" },
      writable: true,
    });

    const { unmount } = renderHook(() => useYjsProvider("doc-http"));
    expect(providerCallArgs[0][0]).toBe("ws://example.com:8080/ws/doc");
    unmount();

    providerCallArgs.length = 0;
    Object.defineProperty(window, "location", {
      value: { ...originalLocation, protocol: "https:", host: "example.com" },
      writable: true,
    });

    renderHook(() => useYjsProvider("doc-https"));
    expect(providerCallArgs[0][0]).toBe("wss://example.com/ws/doc");
  });

  it("sets synced=true when provider emits 'sync' with true", () => {
    const { result } = renderHook(() => useYjsProvider("doc-sync"));

    expect(result.current.synced).toBe(false);

    const syncCallback = mockOn.mock.calls.find((c) => c[0] === "sync")?.[1];
    expect(syncCallback).toBeDefined();

    act(() => {
      syncCallback(true);
    });

    expect(result.current.synced).toBe(true);
  });

  it("sets synced=false when provider emits 'sync' with false", () => {
    const { result } = renderHook(() => useYjsProvider("doc-sync"));

    const syncCallback = mockOn.mock.calls.find((c) => c[0] === "sync")?.[1];
    act(() => {
      syncCallback(true);
    });
    expect(result.current.synced).toBe(true);

    act(() => {
      syncCallback(false);
    });
    expect(result.current.synced).toBe(false);
  });

  it("cleans up (disconnect, destroy) on unmount", () => {
    const { unmount } = renderHook(() => useYjsProvider("doc-cleanup"));

    expect(mockDisconnect).not.toHaveBeenCalled();
    expect(mockDestroy).not.toHaveBeenCalled();

    unmount();

    expect(mockDisconnect).toHaveBeenCalled();
    expect(mockDestroy).toHaveBeenCalled();
  });

  it("cleans up and recreates when documentId changes", () => {
    const { rerender } = renderHook(({ documentId }) => useYjsProvider(documentId), {
      initialProps: { documentId: "doc-1" as string },
    });

    expect(providerCallArgs).toHaveLength(1);
    expect(providerCallArgs[0][1]).toBe("doc-1");
    expect(mockDisconnect).not.toHaveBeenCalled();

    rerender({ documentId: "doc-2" });

    expect(mockDisconnect).toHaveBeenCalled();
    expect(mockDestroy).toHaveBeenCalled();
    expect(providerCallArgs).toHaveLength(2);
    expect(providerCallArgs[1][1]).toBe("doc-2");
  });

  it("returns ytext from ydoc.getText('content')", () => {
    const { result } = renderHook(() => useYjsProvider("doc-ytext"));

    const expectedYtext = result.current.ydoc.getText("content");
    expect(result.current.ytext).toBe(expectedYtext);
  });
});
