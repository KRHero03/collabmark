import { describe, it, expect, vi, afterEach } from "vitest";
import { render, fireEvent, cleanup } from "@testing-library/react";
import { CreateFolderDialog } from "./CreateFolderDialog";

describe("CreateFolderDialog", () => {
  afterEach(cleanup);

  it("renders nothing when open is false", () => {
    const { container } = render(<CreateFolderDialog open={false} onClose={vi.fn()} onCreate={vi.fn()} />);
    expect(container.innerHTML).toBe("");
  });

  it("renders dialog when open is true", () => {
    const { getByText } = render(<CreateFolderDialog open onClose={vi.fn()} onCreate={vi.fn()} />);
    expect(getByText("New Folder")).toBeTruthy();
  });

  it("pre-fills with Untitled Folder", () => {
    const { container } = render(<CreateFolderDialog open onClose={vi.fn()} onCreate={vi.fn()} />);
    const input = container.querySelector("input") as HTMLInputElement;
    expect(input.value).toBe("Untitled Folder");
  });

  it("calls onCreate with name on submit", () => {
    const onCreate = vi.fn();
    const onClose = vi.fn();
    const { container, getByText } = render(<CreateFolderDialog open onClose={onClose} onCreate={onCreate} />);
    const input = container.querySelector("input") as HTMLInputElement;
    fireEvent.change(input, { target: { value: "My Folder" } });
    fireEvent.click(getByText("Create"));
    expect(onCreate).toHaveBeenCalledWith("My Folder");
    expect(onClose).toHaveBeenCalled();
  });

  it("calls onClose when Cancel is clicked", () => {
    const onClose = vi.fn();
    const { getByText } = render(<CreateFolderDialog open onClose={onClose} onCreate={vi.fn()} />);
    fireEvent.click(getByText("Cancel"));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("disables Create when name is empty", () => {
    const { container, getByText } = render(<CreateFolderDialog open onClose={vi.fn()} onCreate={vi.fn()} />);
    const input = container.querySelector("input") as HTMLInputElement;
    fireEvent.change(input, { target: { value: "" } });
    const btn = getByText("Create") as HTMLButtonElement;
    expect(btn.disabled).toBe(true);
  });

  it("disables Create when name is whitespace only", () => {
    const { container, getByText } = render(<CreateFolderDialog open onClose={vi.fn()} onCreate={vi.fn()} />);
    const input = container.querySelector("input") as HTMLInputElement;
    fireEvent.change(input, { target: { value: "   " } });
    const btn = getByText("Create") as HTMLButtonElement;
    expect(btn.disabled).toBe(true);
  });

  it("trims whitespace before creating", () => {
    const onCreate = vi.fn();
    const { container, getByText } = render(<CreateFolderDialog open onClose={vi.fn()} onCreate={onCreate} />);
    const input = container.querySelector("input") as HTMLInputElement;
    fireEvent.change(input, { target: { value: "  Trimmed  " } });
    fireEvent.click(getByText("Create"));
    expect(onCreate).toHaveBeenCalledWith("Trimmed");
  });

  it("submits on form enter", () => {
    const onCreate = vi.fn();
    const { container } = render(<CreateFolderDialog open onClose={vi.fn()} onCreate={onCreate} />);
    const input = container.querySelector("input") as HTMLInputElement;
    fireEvent.change(input, { target: { value: "Enter Folder" } });
    fireEvent.submit(input.closest("form")!);
    expect(onCreate).toHaveBeenCalledWith("Enter Folder");
  });

  it("does not submit when name is empty", () => {
    const onCreate = vi.fn();
    const { container } = render(<CreateFolderDialog open onClose={vi.fn()} onCreate={onCreate} />);
    const input = container.querySelector("input") as HTMLInputElement;
    fireEvent.change(input, { target: { value: "" } });
    fireEvent.submit(input.closest("form")!);
    expect(onCreate).not.toHaveBeenCalled();
  });
});
