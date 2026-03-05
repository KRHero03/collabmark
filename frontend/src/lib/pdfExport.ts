/**
 * Portrait-safe content width in pixels (A4 at 96 DPI minus 20mm margins).
 */
export const PORTRAIT_CONTENT_WIDTH = 720;

/**
 * Checks whether any wide element in the container exceeds portrait width,
 * indicating landscape orientation should be used for PDF export.
 */
export function detectNeedsLandscape(container: HTMLElement): boolean {
  const wideEls = container.querySelectorAll(
    "table, pre, svg, .overflow-x-auto",
  );
  return Array.from(wideEls).some(
    (el) => el.scrollWidth > PORTRAIT_CONTENT_WIDTH,
  );
}
