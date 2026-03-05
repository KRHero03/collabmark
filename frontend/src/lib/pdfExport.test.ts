import { describe, it, expect } from "vitest";
import { detectNeedsLandscape, PORTRAIT_CONTENT_WIDTH } from "./pdfExport";

function makeContainer(innerHTML: string, widths: Record<string, number> = {}): HTMLElement {
  const div = document.createElement("div");
  div.innerHTML = innerHTML;

  for (const [selector, width] of Object.entries(widths)) {
    div.querySelectorAll(selector).forEach((el) => {
      Object.defineProperty(el, "scrollWidth", { value: width, configurable: true });
    });
  }

  return div;
}

describe("detectNeedsLandscape", () => {
  it("returns false when container has no wide elements", () => {
    const container = makeContainer("<p>Short paragraph</p>");
    expect(detectNeedsLandscape(container)).toBe(false);
  });

  it("returns false when tables/pre/svg are within portrait width", () => {
    const container = makeContainer(
      "<table><tr><td>data</td></tr></table><pre>code</pre>",
      { table: 600, pre: 400 },
    );
    expect(detectNeedsLandscape(container)).toBe(false);
  });

  it("returns true when a table exceeds portrait width", () => {
    const container = makeContainer(
      "<table><tr><td>wide</td></tr></table>",
      { table: PORTRAIT_CONTENT_WIDTH + 1 },
    );
    expect(detectNeedsLandscape(container)).toBe(true);
  });

  it("returns true when a pre block exceeds portrait width", () => {
    const container = makeContainer(
      "<pre>very long code line</pre>",
      { pre: 900 },
    );
    expect(detectNeedsLandscape(container)).toBe(true);
  });

  it("returns true when an SVG exceeds portrait width", () => {
    const container = makeContainer(
      '<svg width="1200"></svg>',
      { svg: 1200 },
    );
    expect(detectNeedsLandscape(container)).toBe(true);
  });

  it("returns true when a .overflow-x-auto element exceeds portrait width", () => {
    const container = makeContainer(
      '<div class="overflow-x-auto"><div>wide diagram</div></div>',
      { ".overflow-x-auto": 800 },
    );
    expect(detectNeedsLandscape(container)).toBe(true);
  });

  it("returns false when wide element is exactly at the threshold", () => {
    const container = makeContainer(
      "<table><tr><td>edge</td></tr></table>",
      { table: PORTRAIT_CONTENT_WIDTH },
    );
    expect(detectNeedsLandscape(container)).toBe(false);
  });

  it("returns true if any one of multiple elements exceeds width", () => {
    const div = document.createElement("div");
    div.innerHTML = "<table><tr><td>narrow</td></tr></table><pre>wide code</pre>";

    div.querySelectorAll("table").forEach((el) => {
      Object.defineProperty(el, "scrollWidth", { value: 300, configurable: true });
    });
    div.querySelectorAll("pre").forEach((el) => {
      Object.defineProperty(el, "scrollWidth", { value: 1000, configurable: true });
    });

    expect(detectNeedsLandscape(div)).toBe(true);
  });

  it("returns false for an empty container", () => {
    const container = makeContainer("");
    expect(detectNeedsLandscape(container)).toBe(false);
  });
});
