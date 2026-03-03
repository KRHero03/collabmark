import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { render, screen, fireEvent, cleanup, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CommentsPanel } from "./CommentsPanel";
import type { CommentData } from "../../lib/api";

const mockFetchComments = vi.fn();
const mockAddComment = vi.fn();
const mockReplyToComment = vi.fn();
const mockResolveComment = vi.fn();
const mockDeleteComment = vi.fn();

let mockComments: CommentData[] = [];
let mockLoading = false;

vi.mock("../../hooks/useComments", () => ({
  useComments: () => ({
    comments: mockComments,
    loading: mockLoading,
    fetchComments: mockFetchComments,
    addComment: mockAddComment,
    replyToComment: mockReplyToComment,
    resolveComment: mockResolveComment,
    deleteComment: mockDeleteComment,
  }),
}));

function makeComment(overrides: Partial<CommentData> = {}): CommentData {
  return {
    id: "c1",
    document_id: "doc1",
    author_id: "u1",
    author_name: "Alice",
    content: "Test comment",
    anchor_from: null,
    anchor_to: null,
    anchor_from_relative: null,
    anchor_to_relative: null,
    quoted_text: null,
    parent_id: null,
    is_resolved: false,
    resolved_by: null,
    resolved_at: null,
    is_orphaned: false,
    orphaned_at: null,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    replies: [],
    ...overrides,
  };
}

const defaultProps = {
  docId: "doc-1",
  open: true,
  onClose: vi.fn(),
  currentUserId: "u1",
};

describe("CommentsPanel", () => {
  beforeEach(() => {
    mockComments = [];
    mockLoading = false;
    vi.clearAllMocks();
    vi.mocked(mockFetchComments).mockResolvedValue(undefined);
    vi.mocked(mockAddComment).mockResolvedValue(makeComment() as never);
    vi.mocked(mockReplyToComment).mockResolvedValue(undefined);
    vi.mocked(mockResolveComment).mockResolvedValue(undefined);
    vi.mocked(mockDeleteComment).mockResolvedValue(undefined);
  });

  afterEach(() => {
    cleanup();
  });

  it("returns null when open is false", () => {
    const { container } = render(
      <CommentsPanel {...defaultProps} open={false} />,
    );
    expect(container.firstChild).toBeNull();
  });

  it("fetches comments when open", () => {
    render(<CommentsPanel {...defaultProps} />);
    expect(mockFetchComments).toHaveBeenCalledWith("doc-1");
  });

  it("does not fetch when not open", () => {
    render(<CommentsPanel {...defaultProps} open={false} />);
    expect(mockFetchComments).not.toHaveBeenCalled();
  });

  it("renders Comments title", () => {
    render(<CommentsPanel {...defaultProps} />);
    expect(screen.getByText("Comments")).toBeInTheDocument();
  });

  it("shows No comments yet when empty", () => {
    render(<CommentsPanel {...defaultProps} />);
    expect(screen.getByText("No comments yet.")).toBeInTheDocument();
  });

  it("renders comment list when comments provided", () => {
    mockComments = [makeComment({ id: "c1", content: "Hello world" })];

    render(<CommentsPanel {...defaultProps} />);

    expect(screen.getByText("Hello world")).toBeInTheDocument();
    expect(screen.getByText("Alice")).toBeInTheDocument();
  });

  it("add comment flow: calls addComment with correct payload", async () => {
    const user = userEvent.setup();

    render(<CommentsPanel {...defaultProps} />);

    const input = screen.getByPlaceholderText("Add a comment...");
    await user.type(input, "My new comment");

    const postButton = screen.getByRole("button", { name: "Post" });
    await user.click(postButton);

    expect(mockAddComment).toHaveBeenCalledWith("doc-1", {
      content: "My new comment",
      anchor_from: undefined,
      anchor_to: undefined,
      anchor_from_relative: undefined,
      anchor_to_relative: undefined,
      quoted_text: undefined,
    });
  });

  it("add comment with selection: includes anchor and quoted text in payload", async () => {
    const user = userEvent.setup();

    render(
      <CommentsPanel
        {...defaultProps}
        selectedText="selected text"
        selectionRange={{ from: 0, to: 14 }}
        selectionRelative={{ from: "AQAAAA==", to: "BQAAAA==" }}
      />,
    );

    const input = screen.getByPlaceholderText("Comment on selection...");
    await user.type(input, "Comment on this");

    const postButton = screen.getByRole("button", { name: "Post" });
    await user.click(postButton);

    expect(mockAddComment).toHaveBeenCalledWith("doc-1", {
      content: "Comment on this",
      anchor_from: 0,
      anchor_to: 14,
      anchor_from_relative: "AQAAAA==",
      anchor_to_relative: "BQAAAA==",
      quoted_text: "selected text",
    });
  });

  it("does not add when comment is empty", async () => {
    const user = userEvent.setup();

    render(<CommentsPanel {...defaultProps} />);

    const postButton = screen.getByRole("button", { name: "Post" });
    await user.click(postButton);

    expect(mockAddComment).not.toHaveBeenCalled();
  });

  it("Enter key triggers add", async () => {
    const user = userEvent.setup();

    render(<CommentsPanel {...defaultProps} />);

    const input = screen.getByPlaceholderText("Add a comment...");
    await user.type(input, "Quick comment{Enter}");

    expect(mockAddComment).toHaveBeenCalledWith("doc-1", {
      content: "Quick comment",
      anchor_from: undefined,
      anchor_to: undefined,
      anchor_from_relative: undefined,
      anchor_to_relative: undefined,
      quoted_text: undefined,
    });
  });

  it("shows loading state", () => {
    mockLoading = true;

    render(<CommentsPanel {...defaultProps} />);

    const spinner = document.querySelector(
      ".animate-spin.rounded-full.border-2",
    );
    expect(spinner).toBeInTheDocument();
  });

  it("shows unresolved count badge when there are unresolved comments", () => {
    mockComments = [
      makeComment({ id: "c1", is_resolved: false }),
      makeComment({ id: "c2", is_resolved: false }),
    ];

    render(<CommentsPanel {...defaultProps} />);

    expect(screen.getByText("2")).toBeInTheDocument();
  });

  it("does not show unresolved count when all resolved", () => {
    mockComments = [
      makeComment({ id: "c1", is_resolved: true }),
    ];

    render(<CommentsPanel {...defaultProps} />);

    expect(screen.queryByText("1")).not.toBeInTheDocument();
  });

  it("close button calls onClose", async () => {
    const onClose = vi.fn();
    render(<CommentsPanel {...defaultProps} onClose={onClose} />);

    const buttons = screen.getAllByRole("button");
    const closeButton = buttons[0];
    fireEvent.click(closeButton);

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("renders doc-level comments in General section", () => {
    mockComments = [
      makeComment({ id: "c1", content: "Doc-level comment", anchor_from: null }),
    ];

    render(<CommentsPanel {...defaultProps} />);

    expect(screen.getByText("Doc-level comment")).toBeInTheDocument();
  });

  it("renders orphaned comments in Orphaned section", () => {
    mockComments = [
      makeComment({
        id: "c1",
        content: "Orphaned comment",
        is_orphaned: true,
      }),
    ];

    render(<CommentsPanel {...defaultProps} />);

    expect(screen.getByText("Orphaned")).toBeInTheDocument();
    expect(screen.getByText("Orphaned comment")).toBeInTheDocument();
  });

  it("renders positioned comments when anchors and positions provided", () => {
    mockComments = [
      makeComment({
        id: "c1",
        content: "Inline comment",
        anchor_from: 0,
        anchor_to: 10,
        anchor_from_relative: "AQAAAA==",
        anchor_to_relative: "BQAAAA==",
      }),
    ];

    const anchors = new Map([
      [
        "c1",
        { from: 0, to: 10, status: "exact" as const },
      ],
    ]);
    const positions = [
      { commentId: "c1", y: 50, idealY: 50, isDisplaced: false },
    ];

    render(
      <CommentsPanel
        {...defaultProps}
        anchors={anchors}
        positions={positions}
      />,
    );

    expect(screen.getByText("Inline comment")).toBeInTheDocument();
  });

  it("shows selected text preview when selection exists", () => {
    render(
      <CommentsPanel
        {...defaultProps}
        selectedText="This is the selected text for commenting"
      />,
    );

    expect(
      screen.getByText("This is the selected text for commenting"),
    ).toBeInTheDocument();
  });

  it("truncates selected text over 100 chars", () => {
    const longText = "a".repeat(150);

    render(
      <CommentsPanel {...defaultProps} selectedText={longText} />,
    );

    expect(screen.getByText(/\.\.\./)).toBeInTheDocument();
  });

  it("reply, resolve, delete flow: CommentThread receives callbacks", () => {
    mockComments = [
      makeComment({
        id: "c1",
        content: "Parent comment",
        author_id: "u1",
      }),
    ];

    render(<CommentsPanel {...defaultProps} />);

    expect(screen.getByText("Parent comment")).toBeInTheDocument();

    const replyButton = screen.getByText("Reply");
    fireEvent.click(replyButton);

    const replyInput = screen.getByPlaceholderText("Reply...");
    expect(replyInput).toBeInTheDocument();
  });

  it("addComment error does not clear input (errors propagate, not swallowed)", async () => {
    const user = userEvent.setup();
    vi.mocked(mockAddComment).mockRejectedValue(new Error("API failed"));

    render(<CommentsPanel {...defaultProps} />);

    const input = screen.getByPlaceholderText("Add a comment...");
    await user.type(input, "Failing comment");

    const postButton = screen.getByRole("button", { name: "Post" });
    await user.click(postButton);

    expect(mockAddComment).toHaveBeenCalledWith("doc-1", {
      content: "Failing comment",
      anchor_from: undefined,
      anchor_to: undefined,
      anchor_from_relative: undefined,
      anchor_to_relative: undefined,
      quoted_text: undefined,
    });
    await waitFor(() => {
      expect(mockAddComment).toHaveBeenCalled();
    });
    expect(input).toHaveValue("Failing comment");
  });

  it("renders displaced comment with connecting line when isDisplaced", () => {
    mockComments = [
      makeComment({
        id: "c1",
        content: "Displaced comment",
        anchor_from: 0,
        anchor_to: 10,
        anchor_from_relative: "AQAAAA==",
        anchor_to_relative: "BQAAAA==",
      }),
    ];

    const anchors = new Map([
      ["c1", { from: 0, to: 10, status: "exact" as const }],
    ]);
    const positions = [
      { commentId: "c1", y: 100, idealY: 50, isDisplaced: true },
    ];

    const { container } = render(
      <CommentsPanel
        {...defaultProps}
        anchors={anchors}
        positions={positions}
      />,
    );

    expect(screen.getByText("Displaced comment")).toBeInTheDocument();
    const svg = container.querySelector("svg line");
    expect(svg).toBeInTheDocument();
  });

  it("renders General divider when both positioned and doc-level comments exist", () => {
    mockComments = [
      makeComment({
        id: "c1",
        content: "Inline",
        anchor_from: 0,
        anchor_to: 5,
        anchor_from_relative: "AQAAAA==",
        anchor_to_relative: "BQAAAA==",
      }),
      makeComment({
        id: "c2",
        content: "Doc-level",
        anchor_from: null,
      }),
    ];

    const anchors = new Map([
      ["c1", { from: 0, to: 5, status: "exact" as const }],
    ]);
    const positions = [
      { commentId: "c1", y: 50, idealY: 50, isDisplaced: false },
    ];

    render(
      <CommentsPanel
        {...defaultProps}
        anchors={anchors}
        positions={positions}
      />,
    );

    expect(screen.getByText("General")).toBeInTheDocument();
    expect(screen.getByText("Inline")).toBeInTheDocument();
    expect(screen.getByText("Doc-level")).toBeInTheDocument();
  });
});
