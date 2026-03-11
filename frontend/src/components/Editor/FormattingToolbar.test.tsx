import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, fireEvent, waitFor } from "@testing-library/react";
import { EditorState } from "@codemirror/state";
import { EditorView } from "codemirror";
import { FormattingToolbar } from "./FormattingToolbar";

const mockUploadAttachment = vi.fn();
const mockAddToast = vi.fn();

vi.mock("../../lib/api", () => ({
  documentsApi: {
    uploadAttachment: (docId: string, file: File) => mockUploadAttachment(docId, file),
  },
  extractErrorDetail: (_err: unknown, fallback: string) => fallback,
}));

vi.mock("../../hooks/useToast", () => ({
  useToast: () => ({ toasts: [], addToast: mockAddToast, removeToast: vi.fn() }),
}));

function createEditorView(content = "hello world"): EditorView {
  const state = EditorState.create({
    doc: content,
    selection: { anchor: 0, head: 5 },
  });
  return new EditorView({ state, parent: document.createElement("div") });
}

describe("FormattingToolbar", () => {
  let view: EditorView;

  beforeEach(() => {
    vi.clearAllMocks();
    view = createEditorView();
  });

  it("renders all formatting buttons", () => {
    const { getByTestId } = render(<FormattingToolbar editorView={view} docId="doc-1" />);
    expect(getByTestId("fmt-bold")).toBeInTheDocument();
    expect(getByTestId("fmt-italic")).toBeInTheDocument();
    expect(getByTestId("fmt-heading")).toBeInTheDocument();
    expect(getByTestId("fmt-strikethrough")).toBeInTheDocument();
    expect(getByTestId("fmt-code")).toBeInTheDocument();
    expect(getByTestId("fmt-ul")).toBeInTheDocument();
    expect(getByTestId("fmt-ol")).toBeInTheDocument();
    expect(getByTestId("fmt-link")).toBeInTheDocument();
    expect(getByTestId("fmt-attachment")).toBeInTheDocument();
  });

  it("bold button wraps selected text", () => {
    const { getByTestId } = render(<FormattingToolbar editorView={view} docId="doc-1" />);
    fireEvent.click(getByTestId("fmt-bold"));
    expect(view.state.doc.toString()).toBe("**hello** world");
    view.destroy();
  });

  it("italic button wraps selected text", () => {
    const { getByTestId } = render(<FormattingToolbar editorView={view} docId="doc-1" />);
    fireEvent.click(getByTestId("fmt-italic"));
    expect(view.state.doc.toString()).toBe("*hello* world");
    view.destroy();
  });

  it("heading button adds # prefix", () => {
    const { getByTestId } = render(<FormattingToolbar editorView={view} docId="doc-1" />);
    fireEvent.click(getByTestId("fmt-heading"));
    expect(view.state.doc.toString()).toBe("# hello world");
    view.destroy();
  });

  it("strikethrough button wraps selected text", () => {
    const { getByTestId } = render(<FormattingToolbar editorView={view} docId="doc-1" />);
    fireEvent.click(getByTestId("fmt-strikethrough"));
    expect(view.state.doc.toString()).toBe("~~hello~~ world");
    view.destroy();
  });

  it("code button wraps selected text", () => {
    const { getByTestId } = render(<FormattingToolbar editorView={view} docId="doc-1" />);
    fireEvent.click(getByTestId("fmt-code"));
    expect(view.state.doc.toString()).toBe("`hello` world");
    view.destroy();
  });

  it("unordered list button adds prefix", () => {
    const { getByTestId } = render(<FormattingToolbar editorView={view} docId="doc-1" />);
    fireEvent.click(getByTestId("fmt-ul"));
    expect(view.state.doc.toString()).toBe("- hello world");
    view.destroy();
  });

  it("ordered list button adds prefix", () => {
    const { getByTestId } = render(<FormattingToolbar editorView={view} docId="doc-1" />);
    fireEvent.click(getByTestId("fmt-ol"));
    expect(view.state.doc.toString()).toBe("1. hello world");
    view.destroy();
  });

  it("link button inserts link markdown", () => {
    const { getByTestId } = render(<FormattingToolbar editorView={view} docId="doc-1" />);
    fireEvent.click(getByTestId("fmt-link"));
    expect(view.state.doc.toString()).toBe("[hello](url) world");
    view.destroy();
  });

  it("attachment button is disabled when docId is missing", () => {
    const { getByTestId } = render(<FormattingToolbar editorView={view} />);
    expect(getByTestId("fmt-attachment")).toBeDisabled();
    view.destroy();
  });

  it("attachment upload success inserts link and shows toast", async () => {
    mockUploadAttachment.mockResolvedValue({
      data: { url: "/media/documents/x/attachments/abc.pdf", name: "abc.pdf", original_name: "report.pdf" },
    });

    const { getByTestId } = render(<FormattingToolbar editorView={view} docId="doc-1" />);
    const fileInput = getByTestId("fmt-file-input") as HTMLInputElement;

    const file = new File(["content"], "report.pdf", { type: "application/pdf" });
    Object.defineProperty(fileInput, "files", { value: [file] });
    fireEvent.change(fileInput);

    await waitFor(() => {
      expect(mockUploadAttachment).toHaveBeenCalledWith("doc-1", file);
    });

    await waitFor(() => {
      expect(view.state.doc.toString()).toContain("[report.pdf](/media/documents/x/attachments/abc.pdf)");
    });

    expect(mockAddToast).toHaveBeenCalledWith("File uploaded successfully", "success");
    view.destroy();
  });

  it("attachment upload failure removes placeholder and shows error toast", async () => {
    mockUploadAttachment.mockRejectedValue(new Error("upload failed"));

    const { getByTestId } = render(<FormattingToolbar editorView={view} docId="doc-1" />);
    const fileInput = getByTestId("fmt-file-input") as HTMLInputElement;

    const file = new File(["content"], "report.pdf", { type: "application/pdf" });
    Object.defineProperty(fileInput, "files", { value: [file] });
    fireEvent.change(fileInput);

    await waitFor(() => {
      expect(mockAddToast).toHaveBeenCalledWith("Failed to upload file", "error");
    });

    expect(view.state.doc.toString()).not.toContain("Uploading");
    view.destroy();
  });

  it("oversized file shows error toast without uploading", () => {
    const { getByTestId } = render(<FormattingToolbar editorView={view} docId="doc-1" />);
    const fileInput = getByTestId("fmt-file-input") as HTMLInputElement;

    const bigFile = new File(["x".repeat(6 * 1024 * 1024)], "huge.pdf", { type: "application/pdf" });
    Object.defineProperty(fileInput, "files", { value: [bigFile] });
    fireEvent.change(fileInput);

    expect(mockUploadAttachment).not.toHaveBeenCalled();
    expect(mockAddToast).toHaveBeenCalledWith(expect.stringContaining("too large"), "error");
    view.destroy();
  });

  it("image attachment uses image markdown syntax", async () => {
    mockUploadAttachment.mockResolvedValue({
      data: { url: "/media/documents/x/attachments/img.png", name: "img.png", original_name: "photo.png" },
    });

    const { getByTestId } = render(<FormattingToolbar editorView={view} docId="doc-1" />);
    const fileInput = getByTestId("fmt-file-input") as HTMLInputElement;

    const file = new File(["img"], "photo.png", { type: "image/png" });
    Object.defineProperty(fileInput, "files", { value: [file] });
    fireEvent.change(fileInput);

    await waitFor(() => {
      expect(view.state.doc.toString()).toContain("![photo.png](/media/documents/x/attachments/img.png)");
    });
    view.destroy();
  });

  it("buttons do nothing when editorView is null", () => {
    const { getByTestId } = render(<FormattingToolbar editorView={null} docId="doc-1" />);
    fireEvent.click(getByTestId("fmt-bold"));
    fireEvent.click(getByTestId("fmt-italic"));
    fireEvent.click(getByTestId("fmt-heading"));
  });
});
