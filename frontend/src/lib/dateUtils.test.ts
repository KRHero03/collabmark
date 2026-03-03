import { describe, it, expect, vi, afterEach } from "vitest";
import { formatDateTime, formatDateLong, formatDateShort } from "./dateUtils";

/**
 * Pin the timezone to US Eastern (UTC-5) so tests produce deterministic
 * output regardless of where they run.  We achieve this by stubbing
 * toLocaleString / toLocaleDateString on Date.prototype.
 */

const FIXED_TZ = "America/New_York";

function stubLocale() {
  const origLocaleString = Date.prototype.toLocaleString;
  const origLocaleDateString = Date.prototype.toLocaleDateString;

  vi.spyOn(Date.prototype, "toLocaleString").mockImplementation(function (
    this: Date,
    _locale?: string | string[],
    options?: Intl.DateTimeFormatOptions,
  ) {
    return origLocaleString.call(this, "en-US", {
      ...options,
      timeZone: FIXED_TZ,
    });
  });

  vi.spyOn(Date.prototype, "toLocaleDateString").mockImplementation(function (
    this: Date,
    _locale?: string | string[],
    options?: Intl.DateTimeFormatOptions,
  ) {
    return origLocaleDateString.call(this, "en-US", {
      ...options,
      timeZone: FIXED_TZ,
    });
  });
}

describe("dateUtils", () => {
  afterEach(() => vi.restoreAllMocks());

  describe("formatDateTime", () => {
    it("converts a UTC Z-suffixed ISO string to local date+time", () => {
      stubLocale();
      const result = formatDateTime("2026-06-15T18:30:00Z");
      expect(result).toContain("Jun");
      expect(result).toContain("15");
      expect(result).toContain("2026");
      expect(result).toMatch(/2:30/);
    });

    it("appends Z to a bare ISO string (no timezone) and converts correctly", () => {
      stubLocale();
      const withZ = formatDateTime("2026-06-15T18:30:00Z");
      const bare = formatDateTime("2026-06-15T18:30:00");
      expect(bare).toBe(withZ);
    });

    it("preserves an existing +offset suffix", () => {
      stubLocale();
      const result = formatDateTime("2026-06-15T14:30:00+00:00");
      expect(result).toContain("Jun");
      expect(result).toContain("15");
      expect(result).toContain("2026");
    });

    it("preserves a negative offset suffix", () => {
      stubLocale();
      // 14:30 at UTC-5 = 19:30 UTC = 15:30 EDT (3:30 PM)
      const result = formatDateTime("2026-06-15T14:30:00-05:00");
      expect(result).toContain("Jun");
      expect(result).toContain("15");
      expect(result).toContain("2026");
      expect(result).toMatch(/3:30/);
    });

    it("handles midnight UTC correctly", () => {
      stubLocale();
      const result = formatDateTime("2026-01-01T00:00:00Z");
      expect(result).toContain("Dec");
      expect(result).toContain("31");
      expect(result).toContain("2025");
      expect(result).toMatch(/7:00/);
    });
  });

  describe("formatDateLong", () => {
    it("returns a long-form date string", () => {
      stubLocale();
      const result = formatDateLong("2026-03-15T10:00:00Z");
      expect(result).toBe("March 15, 2026");
    });

    it("converts UTC midnight to local previous day when applicable", () => {
      stubLocale();
      const result = formatDateLong("2026-03-01T03:00:00Z");
      expect(result).toContain("February");
      expect(result).toContain("28");
    });

    it("handles bare ISO strings without Z", () => {
      stubLocale();
      const withZ = formatDateLong("2026-07-04T12:00:00Z");
      const bare = formatDateLong("2026-07-04T12:00:00");
      expect(bare).toBe(withZ);
    });
  });

  describe("formatDateShort", () => {
    it("returns a short-form date string", () => {
      stubLocale();
      const result = formatDateShort("2026-11-25T15:00:00Z");
      expect(result).toBe("Nov 25, 2026");
    });

    it("handles bare ISO strings without Z", () => {
      stubLocale();
      const withZ = formatDateShort("2026-11-25T15:00:00Z");
      const bare = formatDateShort("2026-11-25T15:00:00");
      expect(bare).toBe(withZ);
    });

    it("handles year boundary with UTC midnight", () => {
      stubLocale();
      const result = formatDateShort("2027-01-01T00:00:00Z");
      expect(result).toContain("Dec");
      expect(result).toContain("31");
      expect(result).toContain("2026");
    });
  });

  describe("timezone consistency", () => {
    it("bare ISO, Z-suffixed, and +00:00 all produce the same result", () => {
      stubLocale();
      const bare = formatDateTime("2026-08-10T12:00:00");
      const zSuffix = formatDateTime("2026-08-10T12:00:00Z");
      const offset = formatDateTime("2026-08-10T12:00:00+00:00");
      expect(bare).toBe(zSuffix);
      expect(zSuffix).toBe(offset);
    });

    it("different offsets produce different local times", () => {
      stubLocale();
      const utc = formatDateTime("2026-08-10T12:00:00Z");
      const plus5 = formatDateTime("2026-08-10T12:00:00+05:00");
      expect(utc).not.toBe(plus5);
    });
  });
});
