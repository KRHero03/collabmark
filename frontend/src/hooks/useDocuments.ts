import { create } from "zustand";
import { documentsApi, type MarkdownDocument } from "../lib/api";

interface DocumentsState {
  documents: MarkdownDocument[];
  loading: boolean;
  fetchDocuments: () => Promise<void>;
  createDocument: (title?: string) => Promise<MarkdownDocument>;
  deleteDocument: (id: string) => Promise<void>;
}

export const useDocuments = create<DocumentsState>((set, get) => ({
  documents: [],
  loading: true,

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
}));
