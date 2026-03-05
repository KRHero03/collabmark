import { describe, it, expect, vi, afterEach } from "vitest";
import { render, fireEvent, cleanup } from "@testing-library/react";
import { FolderInfoModal } from "./FolderInfoModal";
import type { FolderItem } from "../../lib/api";

const mockFolder: FolderItem = {
  id: "folder-1",
  name: "Test Folder",
  owner_id: "user-1",
  owner_name: "John Doe",
  owner_email: "john@example.com",
  owner_avatar_url: null,
  parent_id: null,
  general_access: "restricted",
  is_deleted: false,
  deleted_at: null,
  created_at: "2026-01-15T10:30:00Z",
  updated_at: "2026-02-01T14:00:00Z",
};

describe("FolderInfoModal", () => {
  afterEach(cleanup);

  it("renders nothing when open is false", () => {
    const { container } = render(
      <FolderInfoModal folder={mockFolder} open={false} onClose={vi.fn()} />,
    );
    expect(container.innerHTML).toBe("");
  });

  it("renders folder name", () => {
    const { getByText } = render(
      <FolderInfoModal folder={mockFolder} open onClose={vi.fn()} />,
    );
    expect(getByText("Test Folder")).toBeTruthy();
  });

  it("renders owner info", () => {
    const { getByText } = render(
      <FolderInfoModal folder={mockFolder} open onClose={vi.fn()} />,
    );
    expect(getByText(/John Doe/)).toBeTruthy();
    expect(getByText(/john@example.com/)).toBeTruthy();
  });

  it("renders access level", () => {
    const { getByText } = render(
      <FolderInfoModal folder={mockFolder} open onClose={vi.fn()} />,
    );
    expect(getByText("restricted")).toBeTruthy();
  });

  it("renders dates", () => {
    const { container } = render(
      <FolderInfoModal folder={mockFolder} open onClose={vi.fn()} />,
    );
    expect(container.textContent).toContain("Created");
    expect(container.textContent).toContain("Updated");
  });

  it("does not show deleted section for non-deleted folder", () => {
    const { container } = render(
      <FolderInfoModal folder={mockFolder} open onClose={vi.fn()} />,
    );
    expect(container.textContent).not.toContain("Deleted");
  });

  it("shows deleted section for deleted folder", () => {
    const deleted: FolderItem = {
      ...mockFolder,
      is_deleted: true,
      deleted_at: "2026-03-01T00:00:00Z",
    };
    const { container } = render(
      <FolderInfoModal folder={deleted} open onClose={vi.fn()} />,
    );
    const dtElements = container.querySelectorAll("dt");
    const hasDtDeleted = Array.from(dtElements).some((dt) =>
      dt.textContent?.includes("Deleted"),
    );
    expect(hasDtDeleted).toBe(true);
  });

  it("calls onClose when close button is clicked", () => {
    const onClose = vi.fn();
    const { container } = render(
      <FolderInfoModal folder={mockFolder} open onClose={onClose} />,
    );
    const closeBtn = container.querySelector(
      'button[class*="absolute"]',
    ) as HTMLButtonElement;
    fireEvent.click(closeBtn);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("renders anyone_view access correctly", () => {
    const folder: FolderItem = { ...mockFolder, general_access: "anyone_view" };
    const { getByText } = render(
      <FolderInfoModal folder={folder} open onClose={vi.fn()} />,
    );
    expect(getByText("anyone view")).toBeTruthy();
  });

  it("renders anyone_edit access correctly", () => {
    const folder: FolderItem = { ...mockFolder, general_access: "anyone_edit" };
    const { getByText } = render(
      <FolderInfoModal folder={folder} open onClose={vi.fn()} />,
    );
    expect(getByText("anyone edit")).toBeTruthy();
  });
});
