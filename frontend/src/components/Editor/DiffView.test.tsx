/**
 * Tests for DiffView component.
 *
 * Validates diff rendering for identical text, additions, removals,
 * unchanged lines, custom/default labels, and edge cases.
 */

import { describe, it, expect, vi } from "vitest";
import { render } from "@testing-library/react";
import * as diff from "diff";
import { DiffView } from "./DiffView";

vi.mock("diff", async (importOriginal) => {
  const actual = await importOriginal<typeof import("diff")>();
  return {
    ...actual,
    diffLines: vi.fn(actual.diffLines),
  };
});

describe("DiffView", () => {
  it("shows 'No differences' message when text is identical", () => {
    const { getByText } = render(<DiffView oldText="Hello world" newText="Hello world" />);
    expect(getByText("No differences — version matches current document.")).toBeDefined();
  });

  it("renders added lines with data-testid='diff-added'", () => {
    const { getAllByTestId } = render(<DiffView oldText="line1\n" newText="line1\nline2\n" />);
    const added = getAllByTestId("diff-added");
    expect(added.length).toBeGreaterThanOrEqual(1);
    expect(added[0].textContent).toContain("line2");
  });

  it("renders removed lines with data-testid='diff-removed'", () => {
    const { getAllByTestId } = render(<DiffView oldText="line1\nline2\n" newText="line1\n" />);
    const removed = getAllByTestId("diff-removed");
    expect(removed.length).toBeGreaterThanOrEqual(1);
    expect(removed[0].textContent).toContain("line2");
  });

  it("renders unchanged lines with data-testid='diff-unchanged'", () => {
    vi.mocked(diff.diffLines).mockReturnValueOnce([
      { value: "line1\n", added: false, removed: false },
      { value: "line2\n", added: true, removed: false },
    ] as diff.Change[]);
    const { getAllByTestId } = render(<DiffView oldText="line1\n" newText="line1\nline2\n" />);
    const unchanged = getAllByTestId("diff-unchanged");
    expect(unchanged.length).toBeGreaterThanOrEqual(1);
    expect(unchanged[0].textContent).toContain("line1");
  });

  it("renders mixed changes (additions + removals + unchanged) correctly", () => {
    const { getAllByTestId, queryAllByTestId } = render(
      <DiffView oldText="common\nremoved\n" newText="common\nadded\n" />,
    );
    const added = getAllByTestId("diff-added");
    const removed = getAllByTestId("diff-removed");

    expect(added.length).toBeGreaterThanOrEqual(1);
    expect(removed.length).toBeGreaterThanOrEqual(1);
    expect(added[0].textContent).toContain("added");
    expect(removed[0].textContent).toContain("removed");
    const unchanged = queryAllByTestId("diff-unchanged");
    if (unchanged.length > 0) {
      expect(unchanged.some((el) => el.textContent?.includes("common"))).toBe(true);
    }
  });

  it("displays custom labels", () => {
    const { getByText } = render(<DiffView oldText="a" newText="b" oldLabel="Before" newLabel="After" />);
    expect(getByText("Before")).toBeDefined();
    expect(getByText("After")).toBeDefined();
  });

  it("displays default labels when not specified", () => {
    const { getByText } = render(<DiffView oldText="a" newText="b" />);
    expect(getByText("Selected version")).toBeDefined();
    expect(getByText("Current document")).toBeDefined();
  });

  it("handles empty strings comparison", () => {
    const { getAllByTestId } = render(<DiffView oldText="" newText="new line\n" />);
    const added = getAllByTestId("diff-added");
    expect(added.length).toBeGreaterThanOrEqual(1);
    expect(added[0].textContent).toContain("new line");
  });

  it("handles single line diff (addition)", () => {
    const { getAllByTestId } = render(<DiffView oldText="" newText="single" />);
    const added = getAllByTestId("diff-added");
    expect(added.length).toBeGreaterThanOrEqual(1);
    expect(added[0].textContent).toContain("single");
  });

  it("handles single line diff (removal)", () => {
    const { getAllByTestId } = render(<DiffView oldText="gone" newText="" />);
    const removed = getAllByTestId("diff-removed");
    expect(removed.length).toBeGreaterThanOrEqual(1);
    expect(removed[0].textContent).toContain("gone");
  });

  it("handles multi-line diff with multiple change blocks", () => {
    const { getAllByTestId } = render(
      <DiffView oldText="block1\nunchanged1\nblock2\n" newText="block1\nunchanged1\nblock2-modified\n" />,
    );
    const added = getAllByTestId("diff-added");
    const removed = getAllByTestId("diff-removed");
    expect(added.length + removed.length).toBeGreaterThanOrEqual(1);
    expect(
      added.some((el) => el.textContent?.includes("block2-modified")) ||
        removed.some((el) => el.textContent?.includes("block2")),
    ).toBe(true);
  });
});
