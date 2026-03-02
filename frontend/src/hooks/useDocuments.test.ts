/**
 * Tests for the useDocuments Zustand store.
 *
 * Validates document listing, creation, and deletion behavior
 * including correct state transitions.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { useDocuments } from "./useDocuments";

vi.mock("../lib/api", () => ({
  documentsApi: {
    list: vi.fn(),
    create: vi.fn(),
    delete: vi.fn(),
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
  general_access: "restricted" as const,
  is_deleted: false,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

describe("useDocuments store", () => {
  beforeEach(() => {
    useDocuments.setState({ documents: [], loading: true });
    vi.clearAllMocks();
  });

  it("should start with empty documents and loading true", () => {
    const state = useDocuments.getState();
    expect(state.documents).toEqual([]);
    expect(state.loading).toBe(true);
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
});
