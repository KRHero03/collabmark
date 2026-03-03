import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CommentThread } from "./CommentThread";
import type { CommentData } from "../../lib/api";

vi.mock("../../lib/dateUtils", () => ({
  formatDateTime: (iso: string) => `Formatted: ${iso}`,
}));

function makeComment(overrides: Partial<CommentData> = {}): CommentData {
  return {
    id: "c1",
    document_id: "doc1",
    author_id: "u1",
    author_name: "Alice",
    content: "Test comment body",
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
    created_at: "2026-01-15T10:30:00Z",
    updated_at: "2026-01-15T10:30:00Z",
    replies: [],
    ...overrides,
  };
}

const defaultProps = {
  comment: makeComment(),
  currentUserId: "u1",
  onReply: vi.fn(),
  onResolve: vi.fn(),
  onDelete: vi.fn(),
};

describe("CommentThread", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it("renders comment with author name, body, timestamp", () => {
    render(<CommentThread {...defaultProps} />);

    expect(screen.getByText("Alice")).toBeInTheDocument();
    expect(screen.getByText("Test comment body")).toBeInTheDocument();
    expect(
      screen.getByText("Formatted: 2026-01-15T10:30:00Z"),
    ).toBeInTheDocument();
  });

  it("renders replies", () => {
    const reply = makeComment({
      id: "r1",
      parent_id: "c1",
      author_name: "Bob",
      content: "Reply content",
      created_at: "2026-01-15T11:00:00Z",
    });

    render(
      <CommentThread
        {...defaultProps}
        comment={makeComment({ replies: [reply] })}
      />,
    );

    expect(screen.getByText("Reply content")).toBeInTheDocument();
    expect(screen.getByText("Bob")).toBeInTheDocument();
    expect(
      screen.getByText("Formatted: 2026-01-15T11:00:00Z"),
    ).toBeInTheDocument();
  });

  it("shows resolve button when not resolved", () => {
    render(<CommentThread {...defaultProps} />);

    const resolveButton = screen.getByTitle("Resolve");
    expect(resolveButton).toBeInTheDocument();
  });

  it("does not show resolve button when resolved", () => {
    render(
      <CommentThread
        {...defaultProps}
        comment={makeComment({ is_resolved: true })}
      />,
    );

    expect(screen.queryByTitle("Resolve")).not.toBeInTheDocument();
    expect(screen.getByText("Resolved")).toBeInTheDocument();
  });

  it("resolve button calls onResolve with comment id", async () => {
    const onResolve = vi.fn();
    render(<CommentThread {...defaultProps} onResolve={onResolve} />);

    const resolveButton = screen.getByTitle("Resolve");
    fireEvent.click(resolveButton);

    expect(onResolve).toHaveBeenCalledWith("c1");
    expect(onResolve).toHaveBeenCalledTimes(1);
  });

  it("shows delete button only for comment author", () => {
    render(<CommentThread {...defaultProps} currentUserId="u1" />);

    expect(screen.getByTitle("Delete")).toBeInTheDocument();
  });

  it("hides delete button when current user is not author", () => {
    render(<CommentThread {...defaultProps} currentUserId="u2" />);

    expect(screen.queryByTitle("Delete")).not.toBeInTheDocument();
  });

  it("delete button calls onDelete with comment id", async () => {
    const onDelete = vi.fn();
    render(<CommentThread {...defaultProps} onDelete={onDelete} />);

    const deleteButton = screen.getByTitle("Delete");
    fireEvent.click(deleteButton);

    expect(onDelete).toHaveBeenCalledWith("c1");
    expect(onDelete).toHaveBeenCalledTimes(1);
  });

  it("orphaned state: shows Referenced text was removed badge", () => {
    render(
      <CommentThread
        {...defaultProps}
        comment={makeComment({ is_orphaned: true })}
        anchorStatus="orphaned"
      />,
    );

    expect(screen.getByText("Referenced text was removed")).toBeInTheDocument();
  });

  it("orphaned state: uses orphaned styling for quoted text", () => {
    render(
      <CommentThread
        {...defaultProps}
        comment={makeComment({
          is_orphaned: true,
          quoted_text: "deleted text",
        })}
        anchorStatus="orphaned"
      />,
    );

    expect(screen.getByText("deleted text")).toBeInTheDocument();
  });

  it("modified state: shows Referenced text was modified badge", () => {
    render(
      <CommentThread
        {...defaultProps}
        comment={makeComment()}
        anchorStatus="modified"
      />,
    );

    expect(
      screen.getByText("Referenced text was modified"),
    ).toBeInTheDocument();
  });

  it("resolved state: shows Resolved text and resolved styling", () => {
    render(
      <CommentThread
        {...defaultProps}
        comment={makeComment({ is_resolved: true })}
      />,
    );

    expect(screen.getByText("Resolved")).toBeInTheDocument();
  });

  it("reply flow: shows reply input when Reply clicked", async () => {
    const user = userEvent.setup();
    render(<CommentThread {...defaultProps} />);

    const replyButton = screen.getByText("Reply");
    await user.click(replyButton);

    expect(screen.getByPlaceholderText("Reply...")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Send" })).toBeInTheDocument();
  });

  it("reply flow: calls onReply with comment id and content", async () => {
    const user = userEvent.setup();
    const onReply = vi.fn();
    render(<CommentThread {...defaultProps} onReply={onReply} />);

    const replyButton = screen.getByText("Reply");
    await user.click(replyButton);

    const replyInput = screen.getByPlaceholderText("Reply...");
    await user.type(replyInput, "My reply");

    const sendButton = screen.getByRole("button", { name: "Send" });
    await user.click(sendButton);

    expect(onReply).toHaveBeenCalledWith("c1", "My reply");
    expect(onReply).toHaveBeenCalledTimes(1);
  });

  it("reply flow: Enter key submits reply", async () => {
    const user = userEvent.setup();
    const onReply = vi.fn();
    render(<CommentThread {...defaultProps} onReply={onReply} />);

    const replyButton = screen.getByText("Reply");
    await user.click(replyButton);

    const replyInput = screen.getByPlaceholderText("Reply...");
    await user.type(replyInput, "Quick reply{Enter}");

    expect(onReply).toHaveBeenCalledWith("c1", "Quick reply");
  });

  it("reply flow: does not submit when reply is empty", async () => {
    const user = userEvent.setup();
    const onReply = vi.fn();
    render(<CommentThread {...defaultProps} onReply={onReply} />);

    const replyButton = screen.getByText("Reply");
    await user.click(replyButton);

    const sendButton = screen.getByRole("button", { name: "Send" });
    await user.click(sendButton);

    expect(onReply).not.toHaveBeenCalled();
  });

  it("does not show reply section when resolved", () => {
    render(
      <CommentThread
        {...defaultProps}
        comment={makeComment({ is_resolved: true })}
      />,
    );

    expect(screen.queryByText("Reply")).not.toBeInTheDocument();
  });

  it("renders quoted text when present", () => {
    render(
      <CommentThread
        {...defaultProps}
        comment={makeComment({ quoted_text: "The selected passage" })}
      />,
    );

    expect(screen.getByText("The selected passage")).toBeInTheDocument();
  });

  it("orphaned from comment.is_orphaned without anchorStatus", () => {
    render(
      <CommentThread
        {...defaultProps}
        comment={makeComment({ is_orphaned: true })}
      />,
    );

    expect(
      screen.getByText("Referenced text was removed"),
    ).toBeInTheDocument();
  });
});
