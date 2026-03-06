/**
 * Tests for VersionHistory component.
 *
 * Validates version list display, detail view with DiffView,
 * restore flow, and API integration.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, fireEvent, waitFor } from "@testing-library/react";
import { VersionHistory } from "./VersionHistory";
import type { VersionListItem, VersionDetail } from "../../lib/api";

vi.mock("../../lib/api", () => ({
  versionsApi: {
    list: vi.fn(),
    get: vi.fn(),
  },
}));

import { versionsApi } from "../../lib/api";

const mockVersionsApi = versionsApi as unknown as {
  list: ReturnType<typeof vi.fn>;
  get: ReturnType<typeof vi.fn>;
};

const mockVersionListItem: VersionListItem = {
  id: "v1",
  version_number: 1,
  author_id: "user-1",
  author_name: "Alice",
  summary: "Initial version",
  created_at: "2026-01-15T10:00:00Z",
};

const mockVersionDetail: VersionDetail = {
  ...mockVersionListItem,
  document_id: "doc-1",
  content: "Old content\nline2",
};

describe("VersionHistory", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("returns null when open is false", () => {
    const { container } = render(
      <VersionHistory docId="doc-1" open={false} onClose={vi.fn()} currentContent="Current" onRestore={vi.fn()} />,
    );
    expect(container.firstChild).toBeNull();
  });

  it("shows loading spinner when fetching versions", async () => {
    mockVersionsApi.list.mockImplementation(() => new Promise(() => {}));

    const { container } = render(
      <VersionHistory docId="doc-1" open onClose={vi.fn()} currentContent="Current" onRestore={vi.fn()} />,
    );

    const spinner = container.querySelector(".animate-spin.rounded-full.border-2");
    expect(spinner).toBeTruthy();
  });

  it("shows empty state message when no versions", async () => {
    mockVersionsApi.list.mockResolvedValue({ data: [] });

    const { getByText } = render(
      <VersionHistory docId="doc-1" open onClose={vi.fn()} currentContent="Current" onRestore={vi.fn()} />,
    );

    await waitFor(() => {
      expect(getByText("No versions yet. Versions are created automatically as you edit.")).toBeDefined();
    });
  });

  it("renders version list with version numbers, authors, summaries", async () => {
    mockVersionsApi.list.mockResolvedValue({
      data: [mockVersionListItem],
    });

    const { getByText } = render(
      <VersionHistory docId="doc-1" open onClose={vi.fn()} currentContent="Current" onRestore={vi.fn()} />,
    );

    await waitFor(() => {
      expect(getByText("Version 1")).toBeDefined();
      expect(getByText(/Alice/)).toBeDefined();
      expect(getByText(/Initial version/)).toBeDefined();
    });
  });

  it("clicking a version shows detail view with DiffView", async () => {
    mockVersionsApi.list.mockResolvedValue({
      data: [mockVersionListItem],
    });
    mockVersionsApi.get.mockResolvedValue({
      data: mockVersionDetail,
    });

    const { getAllByText, getAllByTestId } = render(
      <VersionHistory docId="doc-1" open onClose={vi.fn()} currentContent="Current content" onRestore={vi.fn()} />,
    );

    await waitFor(() => {
      expect(getAllByText("Version 1").length).toBeGreaterThan(0);
    });

    fireEvent.click(getAllByText("Version 1")[0]);

    await waitFor(() => {
      const added = getAllByTestId("diff-added");
      const removed = getAllByTestId("diff-removed");
      expect(added.length + removed.length).toBeGreaterThan(0);
    });
  });

  it("Restore button is visible in the detail view", async () => {
    mockVersionsApi.list.mockResolvedValue({
      data: [mockVersionListItem],
    });
    mockVersionsApi.get.mockResolvedValue({
      data: mockVersionDetail,
    });

    const { getAllByText, getByTestId } = render(
      <VersionHistory docId="doc-1" open onClose={vi.fn()} currentContent="Current" onRestore={vi.fn()} />,
    );

    await waitFor(() => {
      expect(getAllByText("Version 1").length).toBeGreaterThan(0);
    });

    fireEvent.click(getAllByText("Version 1")[0]);

    await waitFor(() => {
      expect(getByTestId("restore-version-btn")).toBeDefined();
    });
  });

  it("clicking Restore calls onRestore with correct content and version number", async () => {
    mockVersionsApi.list.mockResolvedValue({
      data: [mockVersionListItem],
    });
    mockVersionsApi.get.mockResolvedValue({
      data: mockVersionDetail,
    });

    const onRestore = vi.fn();
    const { getAllByText, getByTestId } = render(
      <VersionHistory docId="doc-1" open onClose={vi.fn()} currentContent="Current" onRestore={onRestore} />,
    );

    await waitFor(() => {
      expect(getAllByText("Version 1").length).toBeGreaterThan(0);
    });

    fireEvent.click(getAllByText("Version 1")[0]);

    await waitFor(() => {
      expect(getByTestId("restore-version-btn")).toBeDefined();
    });

    fireEvent.click(getByTestId("restore-version-btn"));

    expect(onRestore).toHaveBeenCalledWith("Old content\nline2", 1);
  });

  it("'Back to list' button returns to version list", async () => {
    mockVersionsApi.list.mockResolvedValue({
      data: [mockVersionListItem],
    });
    mockVersionsApi.get.mockResolvedValue({
      data: mockVersionDetail,
    });

    const { getAllByText, getByText } = render(
      <VersionHistory docId="doc-1" open onClose={vi.fn()} currentContent="Current" onRestore={vi.fn()} />,
    );

    await waitFor(() => {
      expect(getAllByText("Version 1").length).toBeGreaterThan(0);
    });

    fireEvent.click(getAllByText("Version 1")[0]);

    await waitFor(() => {
      expect(getByText("Back to list")).toBeDefined();
    });

    fireEvent.click(getByText("Back to list"));

    await waitFor(() => {
      expect(getByText(/Initial version/)).toBeDefined();
    });
  });

  it("calls versionsApi.list when opened", async () => {
    mockVersionsApi.list.mockResolvedValue({ data: [] });

    render(<VersionHistory docId="doc-1" open onClose={vi.fn()} currentContent="Current" onRestore={vi.fn()} />);

    await waitFor(() => {
      expect(mockVersionsApi.list).toHaveBeenCalledWith("doc-1");
    });
  });

  it("calls versionsApi.get when version selected", async () => {
    mockVersionsApi.list.mockResolvedValue({
      data: [mockVersionListItem],
    });
    mockVersionsApi.get.mockResolvedValue({
      data: mockVersionDetail,
    });

    const { getAllByText } = render(
      <VersionHistory docId="doc-1" open onClose={vi.fn()} currentContent="Current" onRestore={vi.fn()} />,
    );

    await waitFor(() => {
      expect(getAllByText("Version 1").length).toBeGreaterThan(0);
    });

    fireEvent.click(getAllByText("Version 1")[0]);

    await waitFor(() => {
      expect(mockVersionsApi.get).toHaveBeenCalledWith("doc-1", 1);
    });
  });
});
