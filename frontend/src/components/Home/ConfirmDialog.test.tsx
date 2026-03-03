import { describe, it, expect, vi, afterEach } from "vitest";
import { render, fireEvent, cleanup } from "@testing-library/react";
import { ConfirmDialog } from "./ConfirmDialog";

describe("ConfirmDialog", () => {
  afterEach(cleanup);

  it("renders nothing when open is false", () => {
    const { container } = render(
      <ConfirmDialog
        open={false}
        title="Delete"
        message="Are you sure?"
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />,
    );
    expect(container.innerHTML).toBe("");
  });

  it("renders title and message when open", () => {
    const { getByText } = render(
      <ConfirmDialog
        open
        title="Confirm Delete"
        message="This will be permanently removed."
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />,
    );
    expect(getByText("Confirm Delete")).toBeTruthy();
    expect(getByText("This will be permanently removed.")).toBeTruthy();
  });

  it("renders default confirm label as Delete", () => {
    const { container } = render(
      <ConfirmDialog
        open
        title="Confirm"
        message="Sure?"
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />,
    );
    const buttons = container.querySelectorAll("button");
    const confirmBtn = buttons[1];
    expect(confirmBtn.textContent).toBe("Delete");
  });

  it("renders custom confirm label", () => {
    const { getByText } = render(
      <ConfirmDialog
        open
        title="Empty"
        message="Sure?"
        confirmLabel="Empty Trash"
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />,
    );
    expect(getByText("Empty Trash")).toBeTruthy();
  });

  it("calls onConfirm when confirm button is clicked", () => {
    const onConfirm = vi.fn();
    const { container } = render(
      <ConfirmDialog
        open
        title="Confirm"
        message="Sure?"
        confirmLabel="Remove"
        onConfirm={onConfirm}
        onCancel={vi.fn()}
      />,
    );
    const buttons = container.querySelectorAll("button");
    fireEvent.click(buttons[1]);
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });

  it("calls onCancel when Cancel button is clicked", () => {
    const onCancel = vi.fn();
    const { getByText } = render(
      <ConfirmDialog
        open
        title="Confirm"
        message="Sure?"
        onConfirm={vi.fn()}
        onCancel={onCancel}
      />,
    );
    fireEvent.click(getByText("Cancel"));
    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it("calls onCancel when Escape is pressed", () => {
    const onCancel = vi.fn();
    render(
      <ConfirmDialog
        open
        title="Confirm"
        message="Sure?"
        onConfirm={vi.fn()}
        onCancel={onCancel}
      />,
    );
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it("calls onCancel when clicking the backdrop", () => {
    const onCancel = vi.fn();
    const { container } = render(
      <ConfirmDialog
        open
        title="Confirm"
        message="Sure?"
        onConfirm={vi.fn()}
        onCancel={onCancel}
      />,
    );
    const backdrop = container.firstChild as HTMLElement;
    fireEvent.click(backdrop);
    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it("does not call onCancel when clicking inside the dialog", () => {
    const onCancel = vi.fn();
    const { getByText } = render(
      <ConfirmDialog
        open
        title="Confirm"
        message="Sure?"
        onConfirm={vi.fn()}
        onCancel={onCancel}
      />,
    );
    fireEvent.click(getByText("Sure?"));
    expect(onCancel).not.toHaveBeenCalled();
  });

  it("renders danger icon for danger variant", () => {
    const { container } = render(
      <ConfirmDialog
        open
        title="Confirm"
        message="Sure?"
        variant="danger"
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />,
    );
    const icon = container.querySelector(".bg-red-100");
    expect(icon).toBeTruthy();
  });

  it("does not render danger icon for default variant", () => {
    const { container } = render(
      <ConfirmDialog
        open
        title="Confirm"
        message="Sure?"
        variant="default"
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />,
    );
    const icon = container.querySelector(".bg-red-100");
    expect(icon).toBeNull();
  });

  it("renders confirm button with red styling for danger variant", () => {
    const { container } = render(
      <ConfirmDialog
        open
        title="Confirm"
        message="Sure?"
        variant="danger"
        confirmLabel="Remove"
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />,
    );
    const buttons = container.querySelectorAll("button");
    const confirmBtn = buttons[1];
    expect(confirmBtn.className).toContain("bg-red-600");
  });

  it("renders confirm button with primary styling for default variant", () => {
    const { getByText } = render(
      <ConfirmDialog
        open
        title="Confirm"
        message="Sure?"
        variant="default"
        confirmLabel="OK"
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />,
    );
    const btn = getByText("OK") as HTMLButtonElement;
    expect(btn.className).toContain("bg-[var(--color-primary)]");
  });
});
