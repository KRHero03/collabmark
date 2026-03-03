import { describe, it, expect, vi, afterEach } from "vitest";
import { render, fireEvent, cleanup } from "@testing-library/react";
import { RenameDialog } from "./RenameDialog";

describe("RenameDialog", () => {
  afterEach(cleanup);

  it("renders nothing when open is false", () => {
    const { container } = render(
      <RenameDialog currentTitle="Doc" open={false} onClose={vi.fn()} onSave={vi.fn()} />,
    );
    expect(container.innerHTML).toBe("");
  });

  it("pre-fills the current title", () => {
    const { container } = render(
      <RenameDialog currentTitle="My Document" open onClose={vi.fn()} onSave={vi.fn()} />,
    );
    const input = container.querySelector("input") as HTMLInputElement;
    expect(input.value).toBe("My Document");
  });

  it("calls onSave with new title on save", () => {
    const onSave = vi.fn();
    const onClose = vi.fn();
    const { container, getByText } = render(
      <RenameDialog currentTitle="Old Title" open onClose={onClose} onSave={onSave} />,
    );
    const input = container.querySelector("input") as HTMLInputElement;
    fireEvent.change(input, { target: { value: "New Title" } });
    fireEvent.click(getByText("Save"));
    expect(onSave).toHaveBeenCalledWith("New Title");
    expect(onClose).toHaveBeenCalled();
  });

  it("calls onClose when Cancel is clicked", () => {
    const onClose = vi.fn();
    const { getByText } = render(
      <RenameDialog currentTitle="Doc" open onClose={onClose} onSave={vi.fn()} />,
    );
    fireEvent.click(getByText("Cancel"));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("disables Save button when title is empty", () => {
    const { container, getByText } = render(
      <RenameDialog currentTitle="Doc" open onClose={vi.fn()} onSave={vi.fn()} />,
    );
    const input = container.querySelector("input") as HTMLInputElement;
    fireEvent.change(input, { target: { value: "" } });
    const saveBtn = getByText("Save") as HTMLButtonElement;
    expect(saveBtn.disabled).toBe(true);
  });

  it("disables Save button when title is whitespace only", () => {
    const { container, getByText } = render(
      <RenameDialog currentTitle="Doc" open onClose={vi.fn()} onSave={vi.fn()} />,
    );
    const input = container.querySelector("input") as HTMLInputElement;
    fireEvent.change(input, { target: { value: "   " } });
    const saveBtn = getByText("Save") as HTMLButtonElement;
    expect(saveBtn.disabled).toBe(true);
  });

  it("disables Save button when title is unchanged", () => {
    const { getByText } = render(
      <RenameDialog currentTitle="Same Title" open onClose={vi.fn()} onSave={vi.fn()} />,
    );
    const saveBtn = getByText("Save") as HTMLButtonElement;
    expect(saveBtn.disabled).toBe(true);
  });

  it("trims whitespace before saving", () => {
    const onSave = vi.fn();
    const { container, getByText } = render(
      <RenameDialog currentTitle="Old" open onClose={vi.fn()} onSave={onSave} />,
    );
    const input = container.querySelector("input") as HTMLInputElement;
    fireEvent.change(input, { target: { value: "  Trimmed  " } });
    fireEvent.click(getByText("Save"));
    expect(onSave).toHaveBeenCalledWith("Trimmed");
  });

  it("calls onClose when clicking the backdrop", () => {
    const onClose = vi.fn();
    const { container } = render(
      <RenameDialog currentTitle="Doc" open onClose={onClose} onSave={vi.fn()} />,
    );
    const backdrop = container.firstChild as HTMLElement;
    fireEvent.click(backdrop);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("does not call onClose when clicking inside the dialog", () => {
    const onClose = vi.fn();
    const { getByText } = render(
      <RenameDialog currentTitle="Doc" open onClose={onClose} onSave={vi.fn()} />,
    );
    fireEvent.click(getByText("Rename document"));
    expect(onClose).not.toHaveBeenCalled();
  });

  it("submits on form enter key", () => {
    const onSave = vi.fn();
    const { container } = render(
      <RenameDialog currentTitle="Old" open onClose={vi.fn()} onSave={onSave} />,
    );
    const input = container.querySelector("input") as HTMLInputElement;
    fireEvent.change(input, { target: { value: "New" } });
    fireEvent.submit(input.closest("form")!);
    expect(onSave).toHaveBeenCalledWith("New");
  });

  it("does not submit form when title is unchanged", () => {
    const onSave = vi.fn();
    const { container } = render(
      <RenameDialog currentTitle="Same" open onClose={vi.fn()} onSave={onSave} />,
    );
    const form = container.querySelector("form")!;
    fireEvent.submit(form);
    expect(onSave).not.toHaveBeenCalled();
  });
});
