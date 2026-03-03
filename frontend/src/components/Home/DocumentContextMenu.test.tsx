import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, fireEvent, cleanup } from "@testing-library/react";
import {
  DocumentContextMenu,
  getOwnedDocActions,
  getSharedDocActions,
  getTrashDocActions,
} from "./DocumentContextMenu";

describe("DocumentContextMenu", () => {
  const onClose = vi.fn();

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  function renderMenu(actions = getOwnedDocActions({
    onOpen: vi.fn(),
    onRename: vi.fn(),
    onTrash: vi.fn(),
    onInfo: vi.fn(),
  })) {
    return render(
      <DocumentContextMenu
        x={100}
        y={200}
        actions={actions}
        onClose={onClose}
      />
    );
  }

  it("renders all owned doc actions", () => {
    const { getByText } = renderMenu();
    expect(getByText("Open")).toBeDefined();
    expect(getByText("Rename")).toBeDefined();
    expect(getByText("Move to Trash")).toBeDefined();
    expect(getByText("Info")).toBeDefined();
  });

  it("renders shared doc actions (Open and Info only)", () => {
    const actions = getSharedDocActions({ onOpen: vi.fn(), onInfo: vi.fn() });
    const { getByText, queryByText } = renderMenu(actions);
    expect(getByText("Open")).toBeDefined();
    expect(getByText("Info")).toBeDefined();
    expect(queryByText("Rename")).toBeNull();
    expect(queryByText("Move to Trash")).toBeNull();
  });

  it("renders trash doc actions", () => {
    const actions = getTrashDocActions({
      onRestore: vi.fn(),
      onDeletePermanently: vi.fn(),
      onInfo: vi.fn(),
    });
    const { getByText } = renderMenu(actions);
    expect(getByText("Restore")).toBeDefined();
    expect(getByText("Delete permanently")).toBeDefined();
    expect(getByText("Info")).toBeDefined();
  });

  it("calls onClose when clicking outside", () => {
    renderMenu();
    fireEvent.mouseDown(document.body);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("calls onClose when pressing Escape", () => {
    renderMenu();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("calls action handler and closes on click", () => {
    const onOpen = vi.fn();
    const actions = getOwnedDocActions({
      onOpen,
      onRename: vi.fn(),
      onTrash: vi.fn(),
      onInfo: vi.fn(),
    });
    const { getByText } = renderMenu(actions);

    fireEvent.click(getByText("Open"));
    expect(onOpen).toHaveBeenCalledTimes(1);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("renders with correct position styles", () => {
    const { container } = renderMenu();
    const menu = container.firstChild as HTMLElement;
    expect(menu.style.top).toBe("200px");
    expect(menu.style.left).toBe("100px");
  });

  it("renders menu items with role=menuitem", () => {
    const { getAllByRole } = renderMenu();
    const items = getAllByRole("menuitem");
    expect(items.length).toBe(4);
  });

  it("does not call onClose when clicking inside the menu", () => {
    const { getByRole } = renderMenu();
    const menu = getByRole("menu");
    fireEvent.mouseDown(menu);
    expect(onClose).not.toHaveBeenCalled();
  });
});

describe("getOwnedDocActions", () => {
  it("returns 4 actions for owned documents", () => {
    const actions = getOwnedDocActions({
      onOpen: vi.fn(),
      onRename: vi.fn(),
      onTrash: vi.fn(),
      onInfo: vi.fn(),
    });
    expect(actions).toHaveLength(4);
    expect(actions.map((a) => a.label)).toEqual([
      "Open",
      "Rename",
      "Move to Trash",
      "Info",
    ]);
  });

  it("marks Move to Trash as danger variant", () => {
    const actions = getOwnedDocActions({
      onOpen: vi.fn(),
      onRename: vi.fn(),
      onTrash: vi.fn(),
      onInfo: vi.fn(),
    });
    const trashAction = actions.find((a) => a.label === "Move to Trash");
    expect(trashAction?.variant).toBe("danger");
  });
});

describe("getSharedDocActions", () => {
  it("returns 2 actions for shared documents", () => {
    const actions = getSharedDocActions({ onOpen: vi.fn(), onInfo: vi.fn() });
    expect(actions).toHaveLength(2);
    expect(actions.map((a) => a.label)).toEqual(["Open", "Info"]);
  });
});

describe("getTrashDocActions", () => {
  it("returns 3 actions for trash documents", () => {
    const actions = getTrashDocActions({
      onRestore: vi.fn(),
      onDeletePermanently: vi.fn(),
      onInfo: vi.fn(),
    });
    expect(actions).toHaveLength(3);
    expect(actions.map((a) => a.label)).toEqual([
      "Restore",
      "Delete permanently",
      "Info",
    ]);
  });

  it("marks Delete permanently as danger variant", () => {
    const actions = getTrashDocActions({
      onRestore: vi.fn(),
      onDeletePermanently: vi.fn(),
      onInfo: vi.fn(),
    });
    const delAction = actions.find((a) => a.label === "Delete permanently");
    expect(delAction?.variant).toBe("danger");
  });
});
