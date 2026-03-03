import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { useToast } from "./useToast";

describe("useToast store", () => {
  beforeEach(() => {
    useToast.setState({ toasts: [] });
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("should start with empty toasts", () => {
    expect(useToast.getState().toasts).toEqual([]);
  });

  it("should add a success toast", () => {
    useToast.getState().addToast("Done!", "success");
    const toasts = useToast.getState().toasts;
    expect(toasts).toHaveLength(1);
    expect(toasts[0].message).toBe("Done!");
    expect(toasts[0].type).toBe("success");
  });

  it("should add an error toast", () => {
    useToast.getState().addToast("Failed", "error");
    const toasts = useToast.getState().toasts;
    expect(toasts).toHaveLength(1);
    expect(toasts[0].type).toBe("error");
  });

  it("should generate unique IDs for each toast", () => {
    useToast.getState().addToast("First", "success");
    useToast.getState().addToast("Second", "success");
    const toasts = useToast.getState().toasts;
    expect(toasts).toHaveLength(2);
    expect(toasts[0].id).not.toBe(toasts[1].id);
  });

  it("should remove a toast by id with exit animation", () => {
    useToast.getState().addToast("Remove me", "success");
    vi.advanceTimersByTime(50);
    const id = useToast.getState().toasts[0].id;
    useToast.getState().removeToast(id);
    expect(useToast.getState().toasts[0].phase).toBe("exiting");
    vi.advanceTimersByTime(300);
    expect(useToast.getState().toasts).toHaveLength(0);
  });

  it("should not remove other toasts when removing by id", () => {
    useToast.getState().addToast("Keep", "success");
    useToast.getState().addToast("Remove", "error");
    const toasts = useToast.getState().toasts;
    const removeId = toasts.find((t) => t.message === "Remove")!.id;
    useToast.getState().removeToast(removeId);
    vi.advanceTimersByTime(300);
    expect(useToast.getState().toasts).toHaveLength(1);
    expect(useToast.getState().toasts[0].message).toBe("Keep");
  });

  it("should auto-dismiss toast after 4 seconds with exit animation", () => {
    useToast.getState().addToast("Auto dismiss", "success");
    expect(useToast.getState().toasts).toHaveLength(1);
    vi.advanceTimersByTime(4000);
    expect(useToast.getState().toasts[0].phase).toBe("exiting");
    vi.advanceTimersByTime(300);
    expect(useToast.getState().toasts).toHaveLength(0);
  });

  it("should not auto-dismiss before 4 seconds", () => {
    useToast.getState().addToast("Still here", "success");
    vi.advanceTimersByTime(3999);
    expect(useToast.getState().toasts).toHaveLength(1);
    expect(useToast.getState().toasts[0].phase).toBe("visible");
  });

  it("should handle multiple toasts with independent timeouts", () => {
    useToast.getState().addToast("First", "success");
    vi.advanceTimersByTime(2000);
    useToast.getState().addToast("Second", "error");
    expect(useToast.getState().toasts).toHaveLength(2);

    vi.advanceTimersByTime(2300);
    expect(useToast.getState().toasts).toHaveLength(1);
    expect(useToast.getState().toasts[0].message).toBe("Second");

    vi.advanceTimersByTime(2300);
    expect(useToast.getState().toasts).toHaveLength(0);
  });

  it("should start new toast in entering phase", () => {
    useToast.getState().addToast("Hello", "success");
    expect(useToast.getState().toasts[0].phase).toBe("entering");
  });

  it("should transition to visible phase after 50ms", () => {
    useToast.getState().addToast("Hello", "success");
    vi.advanceTimersByTime(50);
    expect(useToast.getState().toasts[0].phase).toBe("visible");
  });

  it("should transition to exiting phase before removal", () => {
    useToast.getState().addToast("Bye", "success");
    vi.advanceTimersByTime(4000);
    expect(useToast.getState().toasts).toHaveLength(1);
    expect(useToast.getState().toasts[0].phase).toBe("exiting");
  });

  it("should prepend newest toast to the front of the array", () => {
    useToast.getState().addToast("First", "success");
    useToast.getState().addToast("Second", "error");
    const toasts = useToast.getState().toasts;
    expect(toasts[0].message).toBe("Second");
    expect(toasts[1].message).toBe("First");
  });

  it("should ignore removeToast for already-exiting toast", () => {
    useToast.getState().addToast("Test", "success");
    vi.advanceTimersByTime(50);
    const id = useToast.getState().toasts[0].id;
    useToast.getState().removeToast(id);
    expect(useToast.getState().toasts[0].phase).toBe("exiting");
    useToast.getState().removeToast(id);
    expect(useToast.getState().toasts).toHaveLength(1);
  });

  it("should ignore removeToast for unknown id", () => {
    useToast.getState().addToast("Test", "success");
    useToast.getState().removeToast("nonexistent");
    expect(useToast.getState().toasts).toHaveLength(1);
  });
});
