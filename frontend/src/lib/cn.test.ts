import { describe, it, expect } from "vitest";
import { cn } from "./cn";

describe("cn", () => {
  it("returns single class unchanged", () => {
    expect(cn("foo")).toBe("foo");
  });

  it("merges multiple classes with space", () => {
    expect(cn("foo", "bar", "baz")).toBe("foo bar baz");
  });

  it("filters out false", () => {
    expect(cn("foo", false, "bar")).toBe("foo bar");
  });

  it("filters out undefined", () => {
    expect(cn("foo", undefined, "bar")).toBe("foo bar");
  });

  it("filters out null", () => {
    expect(cn("foo", null, "bar")).toBe("foo bar");
  });

  it("handles conditional classes", () => {
    const isActive = true;
    const isDisabled = false;
    expect(cn("base", isActive && "active", isDisabled && "disabled")).toBe("base active");
  });

  it("handles array of classes", () => {
    expect(cn(["foo", "bar"])).toBe("foo bar");
  });

  it("handles object syntax", () => {
    expect(cn({ foo: true, bar: false, baz: true })).toBe("foo baz");
  });

  it("merges conflicting Tailwind classes correctly (last wins)", () => {
    expect(cn("p-4", "p-2")).toBe("p-2");
  });

  it("merges conflicting Tailwind padding classes", () => {
    expect(cn("px-4", "px-6")).toBe("px-6");
  });

  it("merges conflicting Tailwind margin classes", () => {
    expect(cn("m-2", "m-4")).toBe("m-4");
  });

  it("returns empty string for no input", () => {
    expect(cn()).toBe("");
  });

  it("returns empty string when all inputs are falsy", () => {
    expect(cn(false, undefined, null)).toBe("");
  });

  it("handles mixed valid and falsy inputs", () => {
    expect(cn("a", false, "b", undefined, "c", null)).toBe("a b c");
  });
});
