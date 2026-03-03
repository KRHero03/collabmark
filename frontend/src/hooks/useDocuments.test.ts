/**
 * Tests for the useDocuments Zustand store.
 *
 * Validates document listing, creation, deletion, renaming,
 * trash listing, restore, and hard-delete behavior.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { useDocuments } from "./useDocuments";

vi.mock("../lib/api", () => ({
  documentsApi: {
    list: vi.fn(),
    create: vi.fn(),
    delete: vi.fn(),
    update: vi.fn(),
    restore: vi.fn(),
    listTrash: vi.fn(),
    hardDelete: vi.fn(),
  },
}));

import { documentsApi } from "../lib/api";

const mockDoc = {
  id: "doc-1",
  title: "Test Doc",
  content: "# Hello",
  owner_id: "user-1",
  owner_name: "Test User",
  owner_email: "test@example.com",
  folder_id: null,
  general_access: "restricted" as const,
  is_deleted: false,
  deleted_at: null,
  content_length: 7,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

const mockTrashDoc = {
  ...mockDoc,
  id: "doc-trash-1",
  title: "Trashed Doc",
  is_deleted: true,
  deleted_at: "2026-02-01T00:00:00Z",
};

describe("useDocuments store", () => {
  beforeEach(() => {
    useDocuments.setState({
      documents: [],
      trash: [],
      loading: true,
      trashLoading: false,
    });
    vi.clearAllMocks();
  });

  it("should start with empty documents and loading true", () => {
    const state = useDocuments.getState();
    expect(state.documents).toEqual([]);
    expect(state.loading).toBe(true);
  });

  it("should start with empty trash and trashLoading false", () => {
    const state = useDocuments.getState();
    expect(state.trash).toEqual([]);
    expect(state.trashLoading).toBe(false);
  });

  it("should populate documents on fetchDocuments", async () => {
    vi.mocked(documentsApi.list).mockResolvedValue({
      data: [mockDoc],
    } as never);

    await useDocuments.getState().fetchDocuments();

    const state = useDocuments.getState();
    expect(state.documents).toHaveLength(1);
    expect(state.documents[0].id).toBe("doc-1");
    expect(state.documents[0].title).toBe("Test Doc");
    expect(state.loading).toBe(false);
  });

  it("should add new document to state on createDocument", async () => {
    const newDoc = { ...mockDoc, id: "doc-2", title: "New Doc" };
    vi.mocked(documentsApi.create).mockResolvedValue({ data: newDoc } as never);

    const result = await useDocuments.getState().createDocument("New Doc");

    expect(result.id).toBe("doc-2");
    expect(result.title).toBe("New Doc");
    expect(useDocuments.getState().documents[0].id).toBe("doc-2");
    expect(documentsApi.create).toHaveBeenCalledWith({ title: "New Doc" });
  });

  it("should use 'Untitled' as default title when creating", async () => {
    vi.mocked(documentsApi.create).mockResolvedValue({ data: mockDoc } as never);

    await useDocuments.getState().createDocument();

    expect(documentsApi.create).toHaveBeenCalledWith({ title: "Untitled" });
  });

  it("should remove document from state on deleteDocument", async () => {
    useDocuments.setState({ documents: [mockDoc], loading: false });
    vi.mocked(documentsApi.delete).mockResolvedValue({} as never);

    await useDocuments.getState().deleteDocument("doc-1");

    expect(useDocuments.getState().documents).toHaveLength(0);
    expect(documentsApi.delete).toHaveBeenCalledWith("doc-1");
  });

  it("should not remove other documents when deleting", async () => {
    const otherDoc = { ...mockDoc, id: "doc-other", title: "Other" };
    useDocuments.setState({
      documents: [mockDoc, otherDoc],
      loading: false,
    });
    vi.mocked(documentsApi.delete).mockResolvedValue({} as never);

    await useDocuments.getState().deleteDocument("doc-1");

    const docs = useDocuments.getState().documents;
    expect(docs).toHaveLength(1);
    expect(docs[0].id).toBe("doc-other");
  });

  describe("renameDocument", () => {
    it("should update the document title in state", async () => {
      const renamed = { ...mockDoc, title: "Renamed" };
      useDocuments.setState({ documents: [mockDoc], loading: false });
      vi.mocked(documentsApi.update).mockResolvedValue({ data: renamed } as never);

      await useDocuments.getState().renameDocument("doc-1", "Renamed");

      expect(documentsApi.update).toHaveBeenCalledWith("doc-1", { title: "Renamed" });
      expect(useDocuments.getState().documents[0].title).toBe("Renamed");
    });

    it("should not affect other documents", async () => {
      const otherDoc = { ...mockDoc, id: "doc-2", title: "Other" };
      const renamed = { ...mockDoc, title: "Renamed" };
      useDocuments.setState({ documents: [mockDoc, otherDoc], loading: false });
      vi.mocked(documentsApi.update).mockResolvedValue({ data: renamed } as never);

      await useDocuments.getState().renameDocument("doc-1", "Renamed");

      expect(useDocuments.getState().documents[1].title).toBe("Other");
    });
  });

  describe("fetchTrash", () => {
    it("should populate trash on fetchTrash", async () => {
      vi.mocked(documentsApi.listTrash).mockResolvedValue({
        data: [mockTrashDoc],
      } as never);

      await useDocuments.getState().fetchTrash();

      const state = useDocuments.getState();
      expect(state.trash).toHaveLength(1);
      expect(state.trash[0].id).toBe("doc-trash-1");
      expect(state.trashLoading).toBe(false);
    });

    it("should set trashLoading to true while fetching", async () => {
      let resolvePromise: (value: unknown) => void;
      const promise = new Promise((resolve) => { resolvePromise = resolve; });
      vi.mocked(documentsApi.listTrash).mockReturnValue(promise as never);

      const fetchPromise = useDocuments.getState().fetchTrash();
      expect(useDocuments.getState().trashLoading).toBe(true);

      resolvePromise!({ data: [] });
      await fetchPromise;
      expect(useDocuments.getState().trashLoading).toBe(false);
    });
  });

  describe("restoreDocument", () => {
    it("should move doc from trash to documents", async () => {
      useDocuments.setState({ trash: [mockTrashDoc], documents: [], loading: false });
      const restored = { ...mockTrashDoc, is_deleted: false, deleted_at: null };
      vi.mocked(documentsApi.restore).mockResolvedValue({ data: restored } as never);

      await useDocuments.getState().restoreDocument("doc-trash-1");

      expect(documentsApi.restore).toHaveBeenCalledWith("doc-trash-1");
      expect(useDocuments.getState().trash).toHaveLength(0);
      expect(useDocuments.getState().documents).toHaveLength(1);
      expect(useDocuments.getState().documents[0].id).toBe("doc-trash-1");
    });

    it("should not affect other trashed documents", async () => {
      const otherTrash = { ...mockTrashDoc, id: "doc-trash-2" };
      useDocuments.setState({ trash: [mockTrashDoc, otherTrash], documents: [] });
      const restored = { ...mockTrashDoc, is_deleted: false };
      vi.mocked(documentsApi.restore).mockResolvedValue({ data: restored } as never);

      await useDocuments.getState().restoreDocument("doc-trash-1");

      expect(useDocuments.getState().trash).toHaveLength(1);
      expect(useDocuments.getState().trash[0].id).toBe("doc-trash-2");
    });
  });

  describe("hardDeleteDocument", () => {
    it("should remove doc from trash", async () => {
      useDocuments.setState({ trash: [mockTrashDoc] });
      vi.mocked(documentsApi.hardDelete).mockResolvedValue({} as never);

      await useDocuments.getState().hardDeleteDocument("doc-trash-1");

      expect(documentsApi.hardDelete).toHaveBeenCalledWith("doc-trash-1");
      expect(useDocuments.getState().trash).toHaveLength(0);
    });

    it("should not affect other trashed documents", async () => {
      const otherTrash = { ...mockTrashDoc, id: "doc-trash-2" };
      useDocuments.setState({ trash: [mockTrashDoc, otherTrash] });
      vi.mocked(documentsApi.hardDelete).mockResolvedValue({} as never);

      await useDocuments.getState().hardDeleteDocument("doc-trash-1");

      expect(useDocuments.getState().trash).toHaveLength(1);
      expect(useDocuments.getState().trash[0].id).toBe("doc-trash-2");
    });
  });
});
