import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useDarkMode } from "./useDarkMode";

describe("useDarkMode", () => {
  beforeEach(() => {
    document.documentElement.classList.remove("dark");
  });

  afterEach(() => {
    document.documentElement.classList.remove("dark");
  });

  it("returns false when no dark class is present", () => {
    document.documentElement.classList.remove("dark");
    const { result } = renderHook(() => useDarkMode());
    expect(result.current).toBe(false);
  });

  it("returns true when dark class is present initially", () => {
    document.documentElement.classList.add("dark");
    const { result } = renderHook(() => useDarkMode());
    expect(result.current).toBe(true);
  });

  it("updates to true when dark class is added", async () => {
    document.documentElement.classList.remove("dark");
    const { result } = renderHook(() => useDarkMode());
    expect(result.current).toBe(false);

    await act(async () => {
      document.documentElement.classList.add("dark");
    });

    expect(result.current).toBe(true);
  });

  it("updates to false when dark class is removed", async () => {
    document.documentElement.classList.add("dark");
    const { result } = renderHook(() => useDarkMode());
    expect(result.current).toBe(true);

    await act(async () => {
      document.documentElement.classList.remove("dark");
    });

    expect(result.current).toBe(false);
  });

  it("disconnects observer on unmount", () => {
    const disconnectSpy = vi.fn();
    const OriginalMutationObserver = (globalThis as typeof globalThis & { MutationObserver: typeof MutationObserver }).MutationObserver;

    class MockMutationObserver {
      observe = vi.fn();
      disconnect = disconnectSpy;
      takeRecords = vi.fn(() => []);
    }
    (globalThis as typeof globalThis & { MutationObserver: typeof MutationObserver }).MutationObserver = MockMutationObserver as unknown as typeof MutationObserver;

    const { unmount } = renderHook(() => useDarkMode());
    expect(disconnectSpy).not.toHaveBeenCalled();

    unmount();
    expect(disconnectSpy).toHaveBeenCalledTimes(1);

    (globalThis as typeof globalThis & { MutationObserver: typeof MutationObserver }).MutationObserver = OriginalMutationObserver;
  });
});
