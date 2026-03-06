import { describe, it, expect, vi, afterEach } from "vitest";
import { render, fireEvent, cleanup } from "@testing-library/react";
import { FolderBreadcrumbs } from "./FolderBreadcrumbs";

describe("FolderBreadcrumbs", () => {
  afterEach(cleanup);

  it("renders Home button", () => {
    const { getByText } = render(<FolderBreadcrumbs breadcrumbs={[]} onNavigate={vi.fn()} />);
    expect(getByText("Home")).toBeTruthy();
  });

  it("calls onNavigate with null when Home is clicked", () => {
    const onNavigate = vi.fn();
    const { getByText } = render(<FolderBreadcrumbs breadcrumbs={[]} onNavigate={onNavigate} />);
    fireEvent.click(getByText("Home"));
    expect(onNavigate).toHaveBeenCalledWith(null);
  });

  it("renders breadcrumb items", () => {
    const crumbs = [
      { id: "f1", name: "Parent" },
      { id: "f2", name: "Child" },
    ];
    const { getByText } = render(<FolderBreadcrumbs breadcrumbs={crumbs} onNavigate={vi.fn()} />);
    expect(getByText("Parent")).toBeTruthy();
    expect(getByText("Child")).toBeTruthy();
  });

  it("calls onNavigate with folder id when breadcrumb is clicked", () => {
    const onNavigate = vi.fn();
    const crumbs = [
      { id: "f1", name: "Parent" },
      { id: "f2", name: "Child" },
    ];
    const { getByText } = render(<FolderBreadcrumbs breadcrumbs={crumbs} onNavigate={onNavigate} />);
    fireEvent.click(getByText("Parent"));
    expect(onNavigate).toHaveBeenCalledWith("f1");
  });

  it("renders nothing extra when breadcrumbs are empty", () => {
    const { container } = render(<FolderBreadcrumbs breadcrumbs={[]} onNavigate={vi.fn()} />);
    const buttons = container.querySelectorAll("button");
    expect(buttons).toHaveLength(1);
  });

  it("renders the correct number of breadcrumb buttons", () => {
    const crumbs = [
      { id: "f1", name: "A" },
      { id: "f2", name: "B" },
      { id: "f3", name: "C" },
    ];
    const { container } = render(<FolderBreadcrumbs breadcrumbs={crumbs} onNavigate={vi.fn()} />);
    const buttons = container.querySelectorAll("button");
    expect(buttons).toHaveLength(4);
  });

  it("has aria-label for accessibility", () => {
    const { container } = render(<FolderBreadcrumbs breadcrumbs={[]} onNavigate={vi.fn()} />);
    const nav = container.querySelector("nav");
    expect(nav?.getAttribute("aria-label")).toBe("Breadcrumb");
  });
});
