import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { DocumentList } from "./DocumentList";
import type { MarkdownDocument } from "../../lib/api";

const mockNavigate = vi.fn();

vi.mock("react-router", () => ({
  useNavigate: () => mockNavigate,
}));

vi.mock("../../lib/dateUtils", () => ({
  formatDateTime: (iso: string) => `formatted:${iso}`,
}));

const createDoc = (overrides: Partial<MarkdownDocument> = {}): MarkdownDocument =>
  ({
    id: "doc-1",
    title: "Test Document",
    content: "",
    owner_id: "u1",
    owner_name: "User",
    owner_email: "user@example.com",
    folder_id: null,
    general_access: "restricted",
    is_deleted: false,
    deleted_at: null,
    content_length: 0,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-15T14:30:00Z",
    ...overrides,
  }) as MarkdownDocument;

describe("DocumentList", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("renders empty state with 'No documents yet' message", () => {
    render(
      <DocumentList documents={[]} onDelete={vi.fn()} onCreate={vi.fn()} />
    );
    expect(
      screen.getByText("No documents yet. Create your first one!")
    ).toBeInTheDocument();
  });

  it("renders list of documents with correct titles", () => {
    const docs: MarkdownDocument[] = [
      createDoc({ id: "a", title: "First Doc" }),
      createDoc({ id: "b", title: "Second Doc" }),
    ];
    render(
      <DocumentList documents={docs} onDelete={vi.fn()} onCreate={vi.fn()} />
    );
    expect(screen.getByText("First Doc")).toBeInTheDocument();
    expect(screen.getByText("Second Doc")).toBeInTheDocument();
  });

  it("calls onCreate when 'New Document' button clicked", () => {
    const onCreate = vi.fn();
    render(
      <DocumentList documents={[]} onDelete={vi.fn()} onCreate={onCreate} />
    );
    fireEvent.click(screen.getByRole("button", { name: /new document/i }));
    expect(onCreate).toHaveBeenCalledTimes(1);
  });

  it("calls onDelete with exact doc.id when trash button clicked", () => {
    const onDelete = vi.fn();
    const docs: MarkdownDocument[] = [
      createDoc({ id: "doc-abc-123", title: "To Delete" }),
    ];
    render(
      <DocumentList documents={docs} onDelete={onDelete} onCreate={vi.fn()} />
    );
    const row = screen.getByText("To Delete").closest(".group");
    expect(row).toBeInTheDocument();
    const trashBtn = row!.querySelector("button");
    expect(trashBtn).toBeInTheDocument();
    fireEvent.click(trashBtn!);
    expect(onDelete).toHaveBeenCalledTimes(1);
    expect(onDelete).toHaveBeenCalledWith("doc-abc-123");
  });

  it("navigates to /edit/{doc.id} when clicking a document row", () => {
    const docs: MarkdownDocument[] = [
      createDoc({ id: "doc-xyz-789", title: "Click Me" }),
    ];
    render(
      <DocumentList documents={docs} onDelete={vi.fn()} onCreate={vi.fn()} />
    );
    fireEvent.click(screen.getByText("Click Me"));
    expect(mockNavigate).toHaveBeenCalledWith("/edit/doc-xyz-789");
  });

  it("calls onContextMenu with the event and exact doc when right-clicking", () => {
    const onContextMenu = vi.fn();
    const doc = createDoc({ id: "doc-ctx", title: "Context Doc" });
    render(
      <DocumentList
        documents={[doc]}
        onDelete={vi.fn()}
        onCreate={vi.fn()}
        onContextMenu={onContextMenu}
      />
    );
    const row = screen.getByText("Context Doc").closest("div")!;
    const event = new MouseEvent("contextmenu", { bubbles: true });
    Object.defineProperty(event, "preventDefault", { value: vi.fn() });
    fireEvent(row, event);
    expect(onContextMenu).toHaveBeenCalledTimes(1);
    expect(onContextMenu).toHaveBeenCalledWith(
      expect.objectContaining({ type: "contextmenu" }),
      doc
    );
  });

  it("does not crash when onContextMenu is undefined and right-click happens", () => {
    const doc = createDoc({ id: "doc-no-ctx", title: "No Context" });
    render(
      <DocumentList documents={[doc]} onDelete={vi.fn()} onCreate={vi.fn()} />
    );
    const row = screen.getByText("No Context").closest("div")!;
    expect(() => fireEvent.contextMenu(row)).not.toThrow();
  });

  it("shows formatted date for each document", () => {
    const docs: MarkdownDocument[] = [
      createDoc({
        id: "d1",
        title: "Doc One",
        updated_at: "2026-03-01T12:00:00Z",
      }),
    ];
    render(
      <DocumentList documents={docs} onDelete={vi.fn()} onCreate={vi.fn()} />
    );
    expect(
      screen.getByText("Updated formatted:2026-03-01T12:00:00Z")
    ).toBeInTheDocument();
  });
});
