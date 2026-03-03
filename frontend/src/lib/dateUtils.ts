/**
 * Centralized date formatting utilities.
 *
 * All backend timestamps are UTC. These helpers ensure correct
 * conversion to the user's local timezone before formatting.
 */

function ensureUtc(iso: string): string {
  if (iso.endsWith("Z") || /[+-]\d{2}:\d{2}$/.test(iso)) return iso;
  return iso + "Z";
}

/**
 * Format a UTC ISO string as a local date+time string.
 * Example: "Jan 15, 2026, 02:30 PM"
 */
export function formatDateTime(iso: string): string {
  return new Date(ensureUtc(iso)).toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/**
 * Format a UTC ISO string as a local date-only string.
 * Example: "January 15, 2026"
 */
export function formatDateLong(iso: string): string {
  return new Date(ensureUtc(iso)).toLocaleDateString(undefined, {
    year: "numeric",
    month: "long",
    day: "numeric",
  });
}

/**
 * Format a UTC ISO string as a short local date string.
 * Example: "Jan 15, 2026"
 */
export function formatDateShort(iso: string): string {
  return new Date(ensureUtc(iso)).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}
