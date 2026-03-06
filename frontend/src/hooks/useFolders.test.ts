import { describe, it, expect, vi, beforeEach } from "vitest";
import { useFolders } from "./useFolders";

vi.mock("../lib/api", () => ({
  foldersApi: {
    create: vi.fn(),
    get: vi.fn(),
    update: vi.fn(),
    delete: vi.fn(),
    restore: vi.fn(),
    hardDelete: vi.fn(),
    listTrash: vi.fn(),
    listShared: vi.fn(),
    listContents: vi.fn(),
    getBreadcrumbs: vi.fn(),
    addCollaborator: vi.fn(),
    listCollaborators: vi.fn(),
    removeCollaborator: vi.fn(),
    recordView: vi.fn(),
    listRecentlyViewed: vi.fn(),
  },
}));

import { foldersApi } from "../lib/api";
import type { FolderItem, MarkdownDocument } from "../lib/api";

const mockFolder: FolderItem = {
  id: "folder-1",
  name: "Test Folder",
  owner_id: "user-1",
  owner_name: "Test User",
  owner_email: "test@example.com",
  owner_avatar_url: null,
  parent_id: null,
  general_access: "restricted",
  is_deleted: false,
  deleted_at: null,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

const mockDoc: MarkdownDocument = {
  id: "doc-1",
  title: "Test Doc",
  content: "# Hello",
  owner_id: "user-1",
  owner_name: "Test User",
  owner_email: "test@example.com",
  owner_avatar_url: null,
  folder_id: "folder-1",
  general_access: "restricted",
  is_deleted: false,
  deleted_at: null,
  content_length: 7,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

const mockTrashFolder: FolderItem = {
  ...mockFolder,
  id: "folder-trash-1",
  name: "Trashed Folder",
  is_deleted: true,
  deleted_at: "2026-02-01T00:00:00Z",
};

describe("useFolders store", () => {
  beforeEach(() => {
    useFolders.setState({
      currentFolderId: null,
      currentFolderPermission: "edit",
      folders: [],
      documents: [],
      breadcrumbs: [],
      trashFolders: [],
      loading: true,
      trashLoading: false,
      accessError: null,
    });
    vi.clearAllMocks();
    vi.mocked(foldersApi.recordView).mockResolvedValue({} as never);
  });

  it("should start with null currentFolderId", () => {
    expect(useFolders.getState().currentFolderId).toBeNull();
  });

  it("should start with empty folders and documents", () => {
    const state = useFolders.getState();
    expect(state.folders).toEqual([]);
    expect(state.documents).toEqual([]);
    expect(state.breadcrumbs).toEqual([]);
  });

  it("should start with loading true", () => {
    expect(useFolders.getState().loading).toBe(true);
  });

  describe("fetchContents", () => {
    it("should populate folders and documents", async () => {
      vi.mocked(foldersApi.listContents).mockResolvedValue({
        data: { folders: [mockFolder], documents: [mockDoc] },
      } as never);

      await useFolders.getState().fetchContents(null);

      const state = useFolders.getState();
      expect(state.folders).toHaveLength(1);
      expect(state.documents).toHaveLength(1);
      expect(state.loading).toBe(false);
    });

    it("should use current folder id when not specified", async () => {
      useFolders.setState({ currentFolderId: "folder-1" });
      vi.mocked(foldersApi.listContents).mockResolvedValue({
        data: { folders: [], documents: [] },
      } as never);

      await useFolders.getState().fetchContents();

      expect(foldersApi.listContents).toHaveBeenCalledWith("folder-1");
    });

    it("should pass null for root", async () => {
      vi.mocked(foldersApi.listContents).mockResolvedValue({
        data: { folders: [], documents: [] },
      } as never);

      await useFolders.getState().fetchContents(null);

      expect(foldersApi.listContents).toHaveBeenCalledWith(null);
    });
  });

  describe("fetchBreadcrumbs", () => {
    it("should set empty breadcrumbs for null folderId", async () => {
      await useFolders.getState().fetchBreadcrumbs(null);
      expect(useFolders.getState().breadcrumbs).toEqual([]);
    });

    it("should set breadcrumbs from API", async () => {
      const crumbs = [
        { id: "f1", name: "Root" },
        { id: "f2", name: "Child" },
      ];
      vi.mocked(foldersApi.getBreadcrumbs).mockResolvedValue({
        data: crumbs,
      } as never);

      await useFolders.getState().fetchBreadcrumbs("f2");

      expect(useFolders.getState().breadcrumbs).toEqual(crumbs);
      expect(foldersApi.getBreadcrumbs).toHaveBeenCalledWith("f2");
    });
  });

  describe("navigateToFolder", () => {
    it("should update currentFolderId and fetch contents", async () => {
      vi.mocked(foldersApi.listContents).mockResolvedValue({
        data: { folders: [mockFolder], documents: [], permission: "edit" },
      } as never);
      vi.mocked(foldersApi.getBreadcrumbs).mockResolvedValue({
        data: [{ id: "folder-1", name: "Test Folder" }],
      } as never);

      await useFolders.getState().navigateToFolder("folder-1");

      expect(useFolders.getState().currentFolderId).toBe("folder-1");
      expect(foldersApi.listContents).toHaveBeenCalledWith("folder-1");
      expect(foldersApi.getBreadcrumbs).toHaveBeenCalledWith("folder-1");
    });

    it("should navigate to root", async () => {
      useFolders.setState({ currentFolderId: "folder-1" });
      vi.mocked(foldersApi.listContents).mockResolvedValue({
        data: { folders: [], documents: [], permission: "edit" },
      } as never);

      await useFolders.getState().navigateToFolder(null);

      expect(useFolders.getState().currentFolderId).toBeNull();
      expect(useFolders.getState().breadcrumbs).toEqual([]);
    });

    it("should call recordView when navigating to a folder", async () => {
      vi.mocked(foldersApi.listContents).mockResolvedValue({
        data: { folders: [], documents: [], permission: "edit" },
      } as never);
      vi.mocked(foldersApi.getBreadcrumbs).mockResolvedValue({
        data: [{ id: "folder-1", name: "Test Folder" }],
      } as never);

      await useFolders.getState().navigateToFolder("folder-1");

      expect(foldersApi.recordView).toHaveBeenCalledWith("folder-1");
    });

    it("should not call recordView when navigating to root", async () => {
      vi.mocked(foldersApi.listContents).mockResolvedValue({
        data: { folders: [], documents: [], permission: "edit" },
      } as never);

      await useFolders.getState().navigateToFolder(null);

      expect(foldersApi.recordView).not.toHaveBeenCalled();
    });

    it("should set accessError when fetchContents returns 403 during navigateToFolder", async () => {
      vi.mocked(foldersApi.listContents).mockRejectedValue({
        response: { status: 403 },
      });
      vi.mocked(foldersApi.getBreadcrumbs).mockResolvedValue({
        data: [],
      } as never);

      await useFolders.getState().navigateToFolder("no-access");

      expect(useFolders.getState().accessError).toBe("You don't have access to this folder anymore.");
      expect(useFolders.getState().loading).toBe(false);
    });
  });

  describe("permission tracking", () => {
    it("should store folder permission from API response", async () => {
      vi.mocked(foldersApi.listContents).mockResolvedValue({
        data: { folders: [], documents: [], permission: "view" },
      } as never);

      await useFolders.getState().fetchContents("folder-1");

      expect(useFolders.getState().currentFolderPermission).toBe("view");
    });

    it("should default to edit permission for root", async () => {
      vi.mocked(foldersApi.listContents).mockResolvedValue({
        data: { folders: [], documents: [], permission: "edit" },
      } as never);

      await useFolders.getState().fetchContents(null);

      expect(useFolders.getState().currentFolderPermission).toBe("edit");
    });

    it("should set accessError on 403", async () => {
      vi.mocked(foldersApi.listContents).mockRejectedValue({
        response: { status: 403 },
      });

      await useFolders.getState().fetchContents("no-access");

      expect(useFolders.getState().accessError).toBe("You don't have access to this folder anymore.");
      expect(useFolders.getState().loading).toBe(false);
    });

    it("should rethrow when fetchContents fails with non-403 error", async () => {
      const err = new Error("Server error");
      vi.mocked(foldersApi.listContents).mockRejectedValue(err);

      await expect(useFolders.getState().fetchContents("folder-1")).rejects.toThrow("Server error");
      expect(useFolders.getState().loading).toBe(false);
    });

    it("should clear accessError via clearAccessError", () => {
      useFolders.setState({ accessError: "some error" });
      useFolders.getState().clearAccessError();
      expect(useFolders.getState().accessError).toBeNull();
    });
  });

  describe("createFolder", () => {
    it("should add new folder to state", async () => {
      vi.mocked(foldersApi.create).mockResolvedValue({
        data: mockFolder,
      } as never);

      const result = await useFolders.getState().createFolder("Test Folder");

      expect(result.id).toBe("folder-1");
      expect(useFolders.getState().folders[0].id).toBe("folder-1");
    });

    it("should use Untitled Folder as default name", async () => {
      vi.mocked(foldersApi.create).mockResolvedValue({
        data: mockFolder,
      } as never);

      await useFolders.getState().createFolder();

      expect(foldersApi.create).toHaveBeenCalledWith({
        name: "Untitled Folder",
        parent_id: null,
      });
    });

    it("should pass current folder as parent_id", async () => {
      useFolders.setState({ currentFolderId: "parent-1" });
      vi.mocked(foldersApi.create).mockResolvedValue({
        data: { ...mockFolder, parent_id: "parent-1" },
      } as never);

      await useFolders.getState().createFolder("Child");

      expect(foldersApi.create).toHaveBeenCalledWith({
        name: "Child",
        parent_id: "parent-1",
      });
    });
  });

  describe("renameFolder", () => {
    it("should update folder name in state", async () => {
      const renamed = { ...mockFolder, name: "Renamed" };
      useFolders.setState({ folders: [mockFolder] });
      vi.mocked(foldersApi.update).mockResolvedValue({
        data: renamed,
      } as never);

      await useFolders.getState().renameFolder("folder-1", "Renamed");

      expect(foldersApi.update).toHaveBeenCalledWith("folder-1", {
        name: "Renamed",
      });
      expect(useFolders.getState().folders[0].name).toBe("Renamed");
    });

    it("should not affect other folders", async () => {
      const other = { ...mockFolder, id: "folder-2", name: "Other" };
      const renamed = { ...mockFolder, name: "Renamed" };
      useFolders.setState({ folders: [mockFolder, other] });
      vi.mocked(foldersApi.update).mockResolvedValue({
        data: renamed,
      } as never);

      await useFolders.getState().renameFolder("folder-1", "Renamed");

      expect(useFolders.getState().folders[1].name).toBe("Other");
    });
  });

  describe("softDeleteFolder", () => {
    it("should remove folder from state", async () => {
      useFolders.setState({ folders: [mockFolder] });
      vi.mocked(foldersApi.delete).mockResolvedValue({} as never);

      await useFolders.getState().softDeleteFolder("folder-1");

      expect(foldersApi.delete).toHaveBeenCalledWith("folder-1");
      expect(useFolders.getState().folders).toHaveLength(0);
    });

    it("should not affect other folders", async () => {
      const other = { ...mockFolder, id: "folder-2" };
      useFolders.setState({ folders: [mockFolder, other] });
      vi.mocked(foldersApi.delete).mockResolvedValue({} as never);

      await useFolders.getState().softDeleteFolder("folder-1");

      expect(useFolders.getState().folders).toHaveLength(1);
      expect(useFolders.getState().folders[0].id).toBe("folder-2");
    });
  });

  describe("fetchTrashFolders", () => {
    it("should populate trashFolders", async () => {
      vi.mocked(foldersApi.listTrash).mockResolvedValue({
        data: [mockTrashFolder],
      } as never);

      await useFolders.getState().fetchTrashFolders();

      const state = useFolders.getState();
      expect(state.trashFolders).toHaveLength(1);
      expect(state.trashFolders[0].id).toBe("folder-trash-1");
      expect(state.trashLoading).toBe(false);
    });

    it("should set trashLoading during fetch", async () => {
      let resolve: (v: unknown) => void;
      const p = new Promise((r) => {
        resolve = r;
      });
      vi.mocked(foldersApi.listTrash).mockReturnValue(p as never);

      const prom = useFolders.getState().fetchTrashFolders();
      expect(useFolders.getState().trashLoading).toBe(true);

      resolve!({ data: [] });
      await prom;
      expect(useFolders.getState().trashLoading).toBe(false);
    });
  });

  describe("restoreFolder", () => {
    it("should remove folder from trash", async () => {
      useFolders.setState({ trashFolders: [mockTrashFolder] });
      vi.mocked(foldersApi.restore).mockResolvedValue({} as never);

      await useFolders.getState().restoreFolder("folder-trash-1");

      expect(foldersApi.restore).toHaveBeenCalledWith("folder-trash-1");
      expect(useFolders.getState().trashFolders).toHaveLength(0);
    });

    it("should not affect other trashed folders", async () => {
      const other = { ...mockTrashFolder, id: "folder-trash-2" };
      useFolders.setState({ trashFolders: [mockTrashFolder, other] });
      vi.mocked(foldersApi.restore).mockResolvedValue({} as never);

      await useFolders.getState().restoreFolder("folder-trash-1");

      expect(useFolders.getState().trashFolders).toHaveLength(1);
      expect(useFolders.getState().trashFolders[0].id).toBe("folder-trash-2");
    });
  });

  describe("hardDeleteFolder", () => {
    it("should remove folder from trash", async () => {
      useFolders.setState({ trashFolders: [mockTrashFolder] });
      vi.mocked(foldersApi.hardDelete).mockResolvedValue({} as never);

      await useFolders.getState().hardDeleteFolder("folder-trash-1");

      expect(foldersApi.hardDelete).toHaveBeenCalledWith("folder-trash-1");
      expect(useFolders.getState().trashFolders).toHaveLength(0);
    });

    it("should not affect other trashed folders", async () => {
      const other = { ...mockTrashFolder, id: "folder-trash-2" };
      useFolders.setState({ trashFolders: [mockTrashFolder, other] });
      vi.mocked(foldersApi.hardDelete).mockResolvedValue({} as never);

      await useFolders.getState().hardDeleteFolder("folder-trash-1");

      expect(useFolders.getState().trashFolders).toHaveLength(1);
    });
  });
});
