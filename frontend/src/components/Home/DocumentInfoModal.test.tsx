import { describe, it, expect, vi, afterEach } from "vitest";
import { render, fireEvent, cleanup } from "@testing-library/react";
import { DocumentInfoModal } from "./DocumentInfoModal";
import type { MarkdownDocument } from "../../lib/api";

const baseDoc: MarkdownDocument = {
  id: "doc-1",
  title: "Test Document",
  content: "Hello world",
  owner_id: "user-1",
  owner_name: "Alice",
  owner_email: "alice@example.com",
  general_access: "restricted",
  is_deleted: false,
  deleted_at: null,
  content_length: 11,
  created_at: "2026-01-15T10:30:00Z",
  updated_at: "2026-02-20T14:45:00Z",
};

describe("DocumentInfoModal", () => {
  afterEach(cleanup);

  it("renders nothing when open is false", () => {
    const { container } = render(
      <DocumentInfoModal doc={baseDoc} open={false} onClose={vi.fn()} />,
    );
    expect(container.innerHTML).toBe("");
  });

  it("renders all metadata fields when open", () => {
    const { getByText } = render(
      <DocumentInfoModal doc={baseDoc} open onClose={vi.fn()} />,
    );
    expect(getByText("Document Info")).toBeDefined();
    expect(getByText("Test Document")).toBeDefined();
    expect(getByText("Alice")).toBeDefined();
    expect(getByText("alice@example.com")).toBeDefined();
    expect(getByText("11 characters")).toBeDefined();
    expect(getByText("Restricted")).toBeDefined();
  });

  it("shows 'anyone can edit' access level", () => {
    const doc = { ...baseDoc, general_access: "anyone_edit" as const };
    const { getByText } = render(
      <DocumentInfoModal doc={doc} open onClose={vi.fn()} />,
    );
    expect(getByText("Anyone with the link can edit")).toBeDefined();
  });

  it("shows 'anyone can view' access level", () => {
    const doc = { ...baseDoc, general_access: "anyone_view" as const };
    const { getByText } = render(
      <DocumentInfoModal doc={doc} open onClose={vi.fn()} />,
    );
    expect(getByText("Anyone with the link can view")).toBeDefined();
  });

  it("shows deleted date for trashed documents", () => {
    const doc = {
      ...baseDoc,
      is_deleted: true,
      deleted_at: "2026-03-01T12:00:00Z",
    };
    const { getByText } = render(
      <DocumentInfoModal doc={doc} open onClose={vi.fn()} />,
    );
    expect(getByText("Deleted")).toBeDefined();
  });

  it("does not show deleted row for non-deleted docs", () => {
    const { queryByText } = render(
      <DocumentInfoModal doc={baseDoc} open onClose={vi.fn()} />,
    );
    expect(queryByText("Deleted")).toBeNull();
  });

  it("handles missing owner info gracefully", () => {
    const doc = { ...baseDoc, owner_name: "", owner_email: "" };
    const { getByText } = render(
      <DocumentInfoModal doc={doc} open onClose={vi.fn()} />,
    );
    expect(getByText("Unknown")).toBeDefined();
    expect(getByText("-")).toBeDefined();
  });

  it("calls onClose when clicking the close button", () => {
    const onClose = vi.fn();
    const { getByText } = render(
      <DocumentInfoModal doc={baseDoc} open onClose={onClose} />,
    );
    fireEvent.click(getByText("Close"));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("calls onClose when clicking the backdrop", () => {
    const onClose = vi.fn();
    const { container } = render(
      <DocumentInfoModal doc={baseDoc} open onClose={onClose} />,
    );
    const backdrop = container.firstChild as HTMLElement;
    fireEvent.click(backdrop);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("does not call onClose when clicking inside the modal", () => {
    const onClose = vi.fn();
    const { getByText } = render(
      <DocumentInfoModal doc={baseDoc} open onClose={onClose} />,
    );
    fireEvent.click(getByText("Document Info"));
    expect(onClose).not.toHaveBeenCalled();
  });

  it("formats large character counts with K suffix", () => {
    const doc = { ...baseDoc, content_length: 5432 };
    const { getByText } = render(
      <DocumentInfoModal doc={doc} open onClose={vi.fn()} />,
    );
    expect(getByText("5.4K characters")).toBeDefined();
  });

  it("formats very large counts with M suffix", () => {
    const doc = { ...baseDoc, content_length: 2_500_000 };
    const { getByText } = render(
      <DocumentInfoModal doc={doc} open onClose={vi.fn()} />,
    );
    expect(getByText("2.5M characters")).toBeDefined();
  });

  it("handles zero content length", () => {
    const doc = { ...baseDoc, content_length: 0 };
    const { getByText } = render(
      <DocumentInfoModal doc={doc} open onClose={vi.fn()} />,
    );
    expect(getByText("0 characters")).toBeDefined();
  });
});
