import { describe, it, expect, vi, afterEach } from "vitest";
import { render, fireEvent, cleanup } from "@testing-library/react";
import {
  DocumentContextMenu,
  getEntityActions,
  getOwnedDocActions,
  getSharedDocActions,
  getTrashDocActions,
  getFolderActions,
  getTrashFolderActions,
} from "./DocumentContextMenu";

describe("DocumentContextMenu", () => {
  const onClose = vi.fn();

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  function renderMenu(actions = getOwnedDocActions({
    onOpen: vi.fn(),
    onShare: vi.fn(),
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
    expect(getByText("Share")).toBeDefined();
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
      onShare: vi.fn(),
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
    expect(items.length).toBe(5);
  });

  it("does not call onClose when clicking inside the menu", () => {
    const { getByRole } = renderMenu();
    const menu = getByRole("menu");
    fireEvent.mouseDown(menu);
    expect(onClose).not.toHaveBeenCalled();
  });
});

describe("getOwnedDocActions", () => {
  it("returns 5 actions for owned documents including Share", () => {
    const actions = getOwnedDocActions({
      onOpen: vi.fn(),
      onShare: vi.fn(),
      onRename: vi.fn(),
      onTrash: vi.fn(),
      onInfo: vi.fn(),
    });
    expect(actions).toHaveLength(5);
    expect(actions.map((a) => a.label)).toEqual([
      "Open",
      "Share",
      "Rename",
      "Move to Trash",
      "Info",
    ]);
  });

  it("marks Move to Trash as danger variant", () => {
    const actions = getOwnedDocActions({
      onOpen: vi.fn(),
      onShare: vi.fn(),
      onRename: vi.fn(),
      onTrash: vi.fn(),
      onInfo: vi.fn(),
    });
    const trashAction = actions.find((a) => a.label === "Move to Trash");
    expect(trashAction?.variant).toBe("danger");
  });

  it("calls onShare handler when Share is clicked", () => {
    const onShare = vi.fn();
    const actions = getOwnedDocActions({
      onOpen: vi.fn(),
      onShare,
      onRename: vi.fn(),
      onTrash: vi.fn(),
      onInfo: vi.fn(),
    });
    const shareAction = actions.find((a) => a.label === "Share");
    shareAction?.onClick();
    expect(onShare).toHaveBeenCalledTimes(1);
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

describe("getFolderActions", () => {
  it("returns 5 actions for owned folders including Share", () => {
    const actions = getFolderActions({
      onOpen: vi.fn(),
      onShare: vi.fn(),
      onRename: vi.fn(),
      onTrash: vi.fn(),
      onInfo: vi.fn(),
    });
    expect(actions).toHaveLength(5);
    expect(actions.map((a) => a.label)).toEqual([
      "Open",
      "Share",
      "Rename",
      "Move to Trash",
      "Info",
    ]);
  });

  it("marks Move to Trash as danger variant", () => {
    const actions = getFolderActions({
      onOpen: vi.fn(),
      onShare: vi.fn(),
      onRename: vi.fn(),
      onTrash: vi.fn(),
      onInfo: vi.fn(),
    });
    const trashAction = actions.find((a) => a.label === "Move to Trash");
    expect(trashAction?.variant).toBe("danger");
  });

  it("calls onOpen when Open is clicked", () => {
    const onOpen = vi.fn();
    const actions = getFolderActions({
      onOpen,
      onShare: vi.fn(),
      onRename: vi.fn(),
      onTrash: vi.fn(),
      onInfo: vi.fn(),
    });
    actions[0].onClick();
    expect(onOpen).toHaveBeenCalledTimes(1);
  });

  it("calls onShare when Share is clicked", () => {
    const onShare = vi.fn();
    const actions = getFolderActions({
      onOpen: vi.fn(),
      onShare,
      onRename: vi.fn(),
      onTrash: vi.fn(),
      onInfo: vi.fn(),
    });
    const shareAction = actions.find((a) => a.label === "Share");
    shareAction?.onClick();
    expect(onShare).toHaveBeenCalledTimes(1);
  });

  it("calls onRename when Rename is clicked", () => {
    const onRename = vi.fn();
    const actions = getFolderActions({
      onOpen: vi.fn(),
      onShare: vi.fn(),
      onRename,
      onTrash: vi.fn(),
      onInfo: vi.fn(),
    });
    const renameAction = actions.find((a) => a.label === "Rename");
    renameAction?.onClick();
    expect(onRename).toHaveBeenCalledTimes(1);
  });
});

describe("getEntityActions", () => {
  it("shows all actions when user has full permissions", () => {
    const actions = getEntityActions(
      "document",
      { can_view: true, can_edit: true, can_delete: true, can_share: true },
      { onOpen: vi.fn(), onShare: vi.fn(), onRename: vi.fn(), onTrash: vi.fn(), onInfo: vi.fn() },
    );
    const labels = actions.map((a) => a.label);
    expect(labels).toContain("Open");
    expect(labels).toContain("Share");
    expect(labels).toContain("Rename");
    expect(labels).toContain("Move to Trash");
    expect(labels).toContain("Info");
  });

  it("hides Share when can_share is false", () => {
    const actions = getEntityActions(
      "document",
      { can_view: true, can_edit: true, can_delete: true, can_share: false },
      { onOpen: vi.fn(), onShare: vi.fn(), onRename: vi.fn(), onTrash: vi.fn(), onInfo: vi.fn() },
    );
    expect(actions.map((a) => a.label)).not.toContain("Share");
  });

  it("hides Rename when can_edit is false", () => {
    const actions = getEntityActions(
      "document",
      { can_view: true, can_edit: false, can_delete: false, can_share: false },
      { onOpen: vi.fn(), onRename: vi.fn(), onInfo: vi.fn() },
    );
    expect(actions.map((a) => a.label)).not.toContain("Rename");
  });

  it("hides Move to Trash when can_delete is false", () => {
    const actions = getEntityActions(
      "folder",
      { can_view: true, can_edit: true, can_delete: false, can_share: false },
      { onOpen: vi.fn(), onTrash: vi.fn(), onInfo: vi.fn() },
    );
    expect(actions.map((a) => a.label)).not.toContain("Move to Trash");
  });

  it("shows View Permissions when onViewAcl is provided", () => {
    const actions = getEntityActions(
      "document",
      { can_view: true, can_edit: false, can_delete: false, can_share: false },
      { onOpen: vi.fn(), onInfo: vi.fn(), onViewAcl: vi.fn() },
    );
    expect(actions.map((a) => a.label)).toContain("View Permissions");
  });

  it("shows only Open and Info for viewer with no handlers", () => {
    const actions = getEntityActions(
      "document",
      { can_view: true, can_edit: false, can_delete: false, can_share: false },
      { onOpen: vi.fn(), onInfo: vi.fn() },
    );
    expect(actions.map((a) => a.label)).toEqual(["Open", "Info"]);
  });
});

describe("getTrashFolderActions", () => {
  it("returns 3 actions for trash folders", () => {
    const actions = getTrashFolderActions({
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
    const actions = getTrashFolderActions({
      onRestore: vi.fn(),
      onDeletePermanently: vi.fn(),
      onInfo: vi.fn(),
    });
    const delAction = actions.find((a) => a.label === "Delete permanently");
    expect(delAction?.variant).toBe("danger");
  });

  it("calls onRestore handler", () => {
    const onRestore = vi.fn();
    const actions = getTrashFolderActions({
      onRestore,
      onDeletePermanently: vi.fn(),
      onInfo: vi.fn(),
    });
    actions[0].onClick();
    expect(onRestore).toHaveBeenCalledTimes(1);
  });

  it("calls onDeletePermanently handler", () => {
    const onDeletePermanently = vi.fn();
    const actions = getTrashFolderActions({
      onRestore: vi.fn(),
      onDeletePermanently,
      onInfo: vi.fn(),
    });
    actions[1].onClick();
    expect(onDeletePermanently).toHaveBeenCalledTimes(1);
  });
});
