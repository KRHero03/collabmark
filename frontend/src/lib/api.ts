import axios from "axios";

const api = axios.create({
  baseURL: "/api",
  withCredentials: true,
});

export interface UserProfile {
  id: string;
  email: string;
  name: string;
  avatar_url: string | null;
  created_at: string;
}

export type GeneralAccess = "restricted" | "anyone_view" | "anyone_edit";

export interface MarkdownDocument {
  id: string;
  title: string;
  content: string;
  owner_id: string;
  owner_name: string;
  owner_email: string;
  general_access: GeneralAccess;
  is_deleted: boolean;
  created_at: string;
  updated_at: string;
}

export interface ApiKeyInfo {
  id: string;
  name: string;
  is_active: boolean;
  created_at: string;
  last_used_at: string | null;
}

export interface ApiKeyCreated {
  id: string;
  name: string;
  raw_key: string;
  created_at: string;
}

export const authApi = {
  getMe: () => api.get<UserProfile>("/users/me"),
  logout: () => api.post("/auth/logout"),
};

export const documentsApi = {
  list: () => api.get<MarkdownDocument[]>("/documents"),
  create: (data: { title?: string; content?: string }) =>
    api.post<MarkdownDocument>("/documents", data),
  get: (id: string) => api.get<MarkdownDocument>(`/documents/${id}`),
  update: (id: string, data: { title?: string; content?: string }) =>
    api.put<MarkdownDocument>(`/documents/${id}`, data),
  delete: (id: string) => api.delete<MarkdownDocument>(`/documents/${id}`),
  restore: (id: string) =>
    api.post<MarkdownDocument>(`/documents/${id}/restore`),
};

export interface Collaborator {
  id: string;
  user_id: string;
  email: string;
  name: string;
  avatar_url: string | null;
  permission: "view" | "edit";
  granted_at: string;
}

export interface SharedDocument {
  id: string;
  title: string;
  content: string;
  owner_id: string;
  permission: "view" | "edit";
  last_accessed_at: string;
  created_at: string;
  updated_at: string;
}

export const keysApi = {
  list: () => api.get<ApiKeyInfo[]>("/keys"),
  create: (name: string) => api.post<ApiKeyCreated>("/keys", { name }),
  revoke: (id: string) => api.delete(`/keys/${id}`),
};

export interface VersionListItem {
  id: string;
  version_number: number;
  author_id: string;
  author_name: string;
  summary: string;
  created_at: string;
}

export interface VersionDetail extends VersionListItem {
  document_id: string;
  content: string;
}

export type Permission = "view" | "edit";

export const sharingApi = {
  getMyPermission: (docId: string) =>
    api.get<{ permission: Permission }>(`/documents/${docId}/permission`),
  updateGeneralAccess: (docId: string, generalAccess: GeneralAccess) =>
    api.put<MarkdownDocument>(`/documents/${docId}/access`, {
      general_access: generalAccess,
    }),
  addCollaborator: (
    docId: string,
    data: { email: string; permission: "view" | "edit" },
  ) => api.post<Collaborator>(`/documents/${docId}/collaborators`, data),
  listCollaborators: (docId: string) =>
    api.get<Collaborator[]>(`/documents/${docId}/collaborators`),
  removeCollaborator: (docId: string, userId: string) =>
    api.delete(`/documents/${docId}/collaborators/${userId}`),
  listShared: () => api.get<SharedDocument[]>("/documents/shared"),
};

export interface CommentData {
  id: string;
  document_id: string;
  author_id: string;
  author_name: string;
  content: string;
  anchor_from: number | null;
  anchor_to: number | null;
  anchor_from_relative: string | null;
  anchor_to_relative: string | null;
  quoted_text: string | null;
  parent_id: string | null;
  is_resolved: boolean;
  resolved_by: string | null;
  resolved_at: string | null;
  is_orphaned: boolean;
  orphaned_at: string | null;
  created_at: string;
  updated_at: string;
  replies: CommentData[];
}

/** Payload for creating a new comment (inline or doc-level). */
export interface CommentCreatePayload {
  content: string;
  anchor_from?: number;
  anchor_to?: number;
  anchor_from_relative?: string;
  anchor_to_relative?: string;
  quoted_text?: string;
}

export const commentsApi = {
  list: (docId: string) =>
    api.get<CommentData[]>(`/documents/${docId}/comments`),
  create: (docId: string, data: CommentCreatePayload) =>
    api.post<CommentData>(`/documents/${docId}/comments`, data),
  reply: (commentId: string, data: { content: string }) =>
    api.post<CommentData>(`/comments/${commentId}/reply`, data),
  resolve: (commentId: string) =>
    api.post<CommentData>(`/comments/${commentId}/resolve`),
  reanchor: (commentId: string, data: { anchor_from: number; anchor_to: number }) =>
    api.patch<CommentData>(`/comments/${commentId}/reanchor`, data),
  orphan: (commentId: string) =>
    api.patch<CommentData>(`/comments/${commentId}/orphan`),
  delete: (commentId: string) => api.delete(`/comments/${commentId}`),
};

export const versionsApi = {
  list: (docId: string) =>
    api.get<VersionListItem[]>(`/documents/${docId}/versions`),
  get: (docId: string, versionNumber: number) =>
    api.get<VersionDetail>(`/documents/${docId}/versions/${versionNumber}`),
  create: (docId: string, data: { content: string; summary?: string }) =>
    api.post<VersionDetail>(`/documents/${docId}/versions`, data),
};

export default api;
