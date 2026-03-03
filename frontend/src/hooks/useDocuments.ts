import { create } from "zustand";
import { documentsApi, type MarkdownDocument } from "../lib/api";

interface DocumentsState {
  documents: MarkdownDocument[];
  trash: MarkdownDocument[];
  loading: boolean;
  trashLoading: boolean;
  fetchDocuments: () => Promise<void>;
  createDocument: (title?: string) => Promise<MarkdownDocument>;
  deleteDocument: (id: string) => Promise<void>;
  renameDocument: (id: string, title: string) => Promise<void>;
  fetchTrash: () => Promise<void>;
  restoreDocument: (id: string) => Promise<void>;
  hardDeleteDocument: (id: string) => Promise<void>;
}

export const useDocuments = create<DocumentsState>((set, get) => ({
  documents: [],
  trash: [],
  loading: true,
  trashLoading: false,

  fetchDocuments: async () => {
    set({ loading: true });
    const { data } = await documentsApi.list();
    set({ documents: data, loading: false });
  },

  createDocument: async (title?: string) => {
    const { data } = await documentsApi.create({ title: title || "Untitled" });
    set({ documents: [data, ...get().documents] });
    return data;
  },

  deleteDocument: async (id: string) => {
    await documentsApi.delete(id);
    set({ documents: get().documents.filter((d) => d.id !== id) });
  },

  renameDocument: async (id: string, title: string) => {
    const { data } = await documentsApi.update(id, { title });
    set({
      documents: get().documents.map((d) => (d.id === id ? data : d)),
    });
  },

  fetchTrash: async () => {
    set({ trashLoading: true });
    const { data } = await documentsApi.listTrash();
    set({ trash: data, trashLoading: false });
  },

  restoreDocument: async (id: string) => {
    const { data } = await documentsApi.restore(id);
    set({
      trash: get().trash.filter((d) => d.id !== id),
      documents: [data, ...get().documents],
    });
  },

  hardDeleteDocument: async (id: string) => {
    await documentsApi.hardDelete(id);
    set({ trash: get().trash.filter((d) => d.id !== id) });
  },
}));
