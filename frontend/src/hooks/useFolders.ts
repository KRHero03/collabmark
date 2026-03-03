import { create } from "zustand";
import {
  foldersApi,
  type Breadcrumb,
  type FolderItem,
  type MarkdownDocument,
} from "../lib/api";

export type FolderPermission = "view" | "edit";

interface FoldersState {
  currentFolderId: string | null;
  currentFolderPermission: FolderPermission;
  folders: FolderItem[];
  documents: MarkdownDocument[];
  breadcrumbs: Breadcrumb[];
  trashFolders: FolderItem[];
  loading: boolean;
  trashLoading: boolean;
  accessError: string | null;

  navigateToFolder: (folderId: string | null) => Promise<void>;
  fetchContents: (folderId?: string | null) => Promise<void>;
  fetchBreadcrumbs: (folderId: string | null) => Promise<void>;
  createFolder: (name?: string) => Promise<FolderItem>;
  renameFolder: (id: string, name: string) => Promise<void>;
  softDeleteFolder: (id: string) => Promise<void>;
  restoreFolder: (id: string) => Promise<void>;
  hardDeleteFolder: (id: string) => Promise<void>;
  fetchTrashFolders: () => Promise<void>;
  clearAccessError: () => void;
}

export const useFolders = create<FoldersState>((set, get) => ({
  currentFolderId: null,
  currentFolderPermission: "edit",
  folders: [],
  documents: [],
  breadcrumbs: [],
  trashFolders: [],
  loading: true,
  trashLoading: false,
  accessError: null,

  clearAccessError: () => set({ accessError: null }),

  navigateToFolder: async (folderId: string | null) => {
    set({ currentFolderId: folderId, loading: true, accessError: null });
    if (folderId) {
      foldersApi.recordView(folderId).catch(() => {});
    }
    await Promise.all([
      get().fetchContents(folderId),
      get().fetchBreadcrumbs(folderId),
    ]);
  },

  fetchContents: async (folderId?: string | null) => {
    set({ loading: true });
    const id = folderId !== undefined ? folderId : get().currentFolderId;
    try {
      const { data } = await foldersApi.listContents(id);
      set({
        folders: data.folders,
        documents: data.documents,
        currentFolderPermission: data.permission || "edit",
        loading: false,
        accessError: null,
      });
    } catch (err: unknown) {
      const status = (err as { response?: { status?: number } })?.response?.status;
      if (status === 403) {
        set({
          folders: [],
          documents: [],
          loading: false,
          accessError: "You don't have access to this folder anymore.",
          currentFolderPermission: "view",
        });
      } else {
        set({ loading: false });
        throw err;
      }
    }
  },

  fetchBreadcrumbs: async (folderId: string | null) => {
    if (folderId === null) {
      set({ breadcrumbs: [] });
      return;
    }
    const { data } = await foldersApi.getBreadcrumbs(folderId);
    set({ breadcrumbs: data });
  },

  createFolder: async (name?: string) => {
    const { data } = await foldersApi.create({
      name: name || "Untitled Folder",
      parent_id: get().currentFolderId,
    });
    set({ folders: [data, ...get().folders] });
    return data;
  },

  renameFolder: async (id: string, name: string) => {
    const { data } = await foldersApi.update(id, { name });
    set({
      folders: get().folders.map((f) => (f.id === id ? data : f)),
    });
  },

  softDeleteFolder: async (id: string) => {
    await foldersApi.delete(id);
    set({ folders: get().folders.filter((f) => f.id !== id) });
  },

  restoreFolder: async (id: string) => {
    await foldersApi.restore(id);
    set({
      trashFolders: get().trashFolders.filter((f) => f.id !== id),
    });
  },

  hardDeleteFolder: async (id: string) => {
    await foldersApi.hardDelete(id);
    set({
      trashFolders: get().trashFolders.filter((f) => f.id !== id),
    });
  },

  fetchTrashFolders: async () => {
    set({ trashLoading: true });
    const { data } = await foldersApi.listTrash();
    set({ trashFolders: data, trashLoading: false });
  },
}));
