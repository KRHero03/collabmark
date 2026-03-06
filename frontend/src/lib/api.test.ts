/**
 * Tests for the API client module.
 *
 * Validates that the API functions call the correct endpoints
 * with the correct parameters.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import axios from "axios";
import {
  documentsApi,
  keysApi,
  authApi,
  foldersApi,
  aclApi,
  sharingApi,
  commentsApi,
  versionsApi,
  orgsApi,
} from "./api";

vi.mock("axios", () => {
  const mockAxios = {
    create: vi.fn(() => mockAxios),
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
    interceptors: {
      request: { use: vi.fn() },
      response: { use: vi.fn() },
    },
  };
  return { default: mockAxios };
});

describe("API client", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("authApi", () => {
    it("getMe calls GET /users/me", async () => {
      await authApi.getMe();
      expect(axios.get).toHaveBeenCalledWith("/users/me");
    });

    it("logout calls POST /auth/logout", async () => {
      await authApi.logout();
      expect(axios.post).toHaveBeenCalledWith("/auth/logout");
    });
  });

  describe("documentsApi", () => {
    it("list calls GET /documents", async () => {
      await documentsApi.list();
      expect(axios.get).toHaveBeenCalledWith("/documents");
    });

    it("create sends correct payload", async () => {
      await documentsApi.create({ title: "My Doc", content: "# Hi" });
      expect(axios.post).toHaveBeenCalledWith("/documents", {
        title: "My Doc",
        content: "# Hi",
      });
    });

    it("get calls GET /documents/:id", async () => {
      await documentsApi.get("abc-123");
      expect(axios.get).toHaveBeenCalledWith("/documents/abc-123");
    });

    it("update calls PUT /documents/:id with payload", async () => {
      await documentsApi.update("abc-123", { title: "Updated" });
      expect(axios.put).toHaveBeenCalledWith("/documents/abc-123", {
        title: "Updated",
      });
    });

    it("delete calls DELETE /documents/:id", async () => {
      await documentsApi.delete("abc-123");
      expect(axios.delete).toHaveBeenCalledWith("/documents/abc-123");
    });

    it("restore calls POST /documents/:id/restore", async () => {
      await documentsApi.restore("abc-123");
      expect(axios.post).toHaveBeenCalledWith("/documents/abc-123/restore");
    });

    it("listTrash calls GET /documents/trash", async () => {
      await documentsApi.listTrash();
      expect(axios.get).toHaveBeenCalledWith("/documents/trash");
    });

    it("hardDelete calls DELETE /documents/:id/permanent", async () => {
      await documentsApi.hardDelete("abc-123");
      expect(axios.delete).toHaveBeenCalledWith("/documents/abc-123/permanent");
    });
  });

  describe("foldersApi", () => {
    it("create calls POST /folders", async () => {
      await foldersApi.create({ name: "My Folder" });
      expect(axios.post).toHaveBeenCalledWith("/folders", { name: "My Folder" });
    });

    it("create with parent_id", async () => {
      await foldersApi.create({ name: "Child", parent_id: "parent-1" });
      expect(axios.post).toHaveBeenCalledWith("/folders", {
        name: "Child",
        parent_id: "parent-1",
      });
    });

    it("get calls GET /folders/:id", async () => {
      await foldersApi.get("folder-1");
      expect(axios.get).toHaveBeenCalledWith("/folders/folder-1");
    });

    it("update calls PUT /folders/:id", async () => {
      await foldersApi.update("folder-1", { name: "Renamed" });
      expect(axios.put).toHaveBeenCalledWith("/folders/folder-1", {
        name: "Renamed",
      });
    });

    it("delete calls DELETE /folders/:id", async () => {
      await foldersApi.delete("folder-1");
      expect(axios.delete).toHaveBeenCalledWith("/folders/folder-1");
    });

    it("restore calls POST /folders/:id/restore", async () => {
      await foldersApi.restore("folder-1");
      expect(axios.post).toHaveBeenCalledWith("/folders/folder-1/restore");
    });

    it("hardDelete calls DELETE /folders/:id/permanent", async () => {
      await foldersApi.hardDelete("folder-1");
      expect(axios.delete).toHaveBeenCalledWith("/folders/folder-1/permanent");
    });

    it("listTrash calls GET /folders/trash", async () => {
      await foldersApi.listTrash();
      expect(axios.get).toHaveBeenCalledWith("/folders/trash");
    });

    it("listShared calls GET /folders/shared", async () => {
      await foldersApi.listShared();
      expect(axios.get).toHaveBeenCalledWith("/folders/shared");
    });

    it("listRecentlyViewed calls GET /folders/recent", async () => {
      await foldersApi.listRecentlyViewed();
      expect(axios.get).toHaveBeenCalledWith("/folders/recent");
    });

    it("listContents calls GET /folders/contents without params for root", async () => {
      await foldersApi.listContents(null);
      expect(axios.get).toHaveBeenCalledWith("/folders/contents", { params: {} });
    });

    it("listContents calls GET /folders/contents with folder_id", async () => {
      await foldersApi.listContents("folder-1");
      expect(axios.get).toHaveBeenCalledWith("/folders/contents", {
        params: { folder_id: "folder-1" },
      });
    });

    it("getBreadcrumbs calls GET /folders/breadcrumbs", async () => {
      await foldersApi.getBreadcrumbs("folder-1");
      expect(axios.get).toHaveBeenCalledWith("/folders/breadcrumbs", {
        params: { folder_id: "folder-1" },
      });
    });

    it("addCollaborator calls POST /folders/:id/collaborators", async () => {
      await foldersApi.addCollaborator("folder-1", {
        email: "user@example.com",
        permission: "edit",
      });
      expect(axios.post).toHaveBeenCalledWith("/folders/folder-1/collaborators", {
        email: "user@example.com",
        permission: "edit",
      });
    });

    it("listCollaborators calls GET /folders/:id/collaborators", async () => {
      await foldersApi.listCollaborators("folder-1");
      expect(axios.get).toHaveBeenCalledWith("/folders/folder-1/collaborators");
    });

    it("removeCollaborator calls DELETE /folders/:id/collaborators/:uid", async () => {
      await foldersApi.removeCollaborator("folder-1", "user-1");
      expect(axios.delete).toHaveBeenCalledWith(
        "/folders/folder-1/collaborators/user-1",
      );
    });

    it("recordView calls POST /folders/:id/view", async () => {
      await foldersApi.recordView("folder-123");
      expect(axios.post).toHaveBeenCalledWith("/folders/folder-123/view");
    });
  });

  describe("orgsApi", () => {
    it("create calls POST /orgs with correct data", async () => {
      await orgsApi.create({
        name: "Acme Corp",
        slug: "acme",
        verified_domains: ["acme.com"],
      });
      expect(axios.post).toHaveBeenCalledWith("/orgs", {
        name: "Acme Corp",
        slug: "acme",
        verified_domains: ["acme.com"],
      });
    });

    it("list calls GET /orgs", async () => {
      await orgsApi.list();
      expect(axios.get).toHaveBeenCalledWith("/orgs");
    });

    it("get calls GET /orgs/:id", async () => {
      await orgsApi.get("org-123");
      expect(axios.get).toHaveBeenCalledWith("/orgs/org-123");
    });

    it("update calls PUT /orgs/:id", async () => {
      await orgsApi.update("org-123", { name: "Updated Name" });
      expect(axios.put).toHaveBeenCalledWith("/orgs/org-123", {
        name: "Updated Name",
      });
    });

    it("listMembers calls GET /orgs/:id/members", async () => {
      await orgsApi.listMembers("org-123");
      expect(axios.get).toHaveBeenCalledWith("/orgs/org-123/members");
    });

    it("addMember calls POST /orgs/:id/members", async () => {
      await orgsApi.addMember("org-123", {
        user_id: "user-456",
        role: "member",
      });
      expect(axios.post).toHaveBeenCalledWith("/orgs/org-123/members", {
        user_id: "user-456",
        role: "member",
      });
    });

    it("removeMember calls DELETE /orgs/:id/members/:userId", async () => {
      await orgsApi.removeMember("org-123", "user-456");
      expect(axios.delete).toHaveBeenCalledWith(
        "/orgs/org-123/members/user-456",
      );
    });

    it("getSSOConfig calls GET /orgs/:id/sso", async () => {
      await orgsApi.getSSOConfig("org-123");
      expect(axios.get).toHaveBeenCalledWith("/orgs/org-123/sso");
    });

    it("updateSSOConfig calls PUT /orgs/:id/sso", async () => {
      await orgsApi.updateSSOConfig("org-123", {
        protocol: "oidc",
        enabled: true,
      });
      expect(axios.put).toHaveBeenCalledWith("/orgs/org-123/sso", {
        protocol: "oidc",
        enabled: true,
      });
    });
  });

  describe("keysApi", () => {
    it("list calls GET /keys", async () => {
      await keysApi.list();
      expect(axios.get).toHaveBeenCalledWith("/keys");
    });

    it("create sends name in payload", async () => {
      await keysApi.create("CI Key");
      expect(axios.post).toHaveBeenCalledWith("/keys", { name: "CI Key" });
    });

    it("revoke calls DELETE /keys/:id", async () => {
      await keysApi.revoke("key-456");
      expect(axios.delete).toHaveBeenCalledWith("/keys/key-456");
    });
  });

  describe("aclApi", () => {
    it("getDocumentAcl calls GET /documents/:id/acl with exact doc ID", async () => {
      await aclApi.getDocumentAcl("doc-abc-123");
      expect(axios.get).toHaveBeenCalledWith("/documents/doc-abc-123/acl");
    });

    it("getFolderAcl calls GET /folders/:id/acl with exact folder ID", async () => {
      await aclApi.getFolderAcl("folder-xyz-789");
      expect(axios.get).toHaveBeenCalledWith("/folders/folder-xyz-789/acl");
    });
  });

  describe("sharingApi", () => {
    it("getMyPermission calls GET /documents/:id/permission", async () => {
      await sharingApi.getMyPermission("doc-abc-123");
      expect(axios.get).toHaveBeenCalledWith(
        "/documents/doc-abc-123/permission",
      );
    });

    it("updateGeneralAccess calls PUT /documents/:id/access with payload", async () => {
      await sharingApi.updateGeneralAccess("doc-abc-123", "anyone_view");
      expect(axios.put).toHaveBeenCalledWith(
        "/documents/doc-abc-123/access",
        { general_access: "anyone_view" },
      );
    });

    it("addCollaborator calls POST /documents/:id/collaborators with payload", async () => {
      await sharingApi.addCollaborator("doc-abc-123", {
        email: "collab@example.com",
        permission: "edit",
      });
      expect(axios.post).toHaveBeenCalledWith(
        "/documents/doc-abc-123/collaborators",
        { email: "collab@example.com", permission: "edit" },
      );
    });

    it("listCollaborators calls GET /documents/:id/collaborators", async () => {
      await sharingApi.listCollaborators("doc-abc-123");
      expect(axios.get).toHaveBeenCalledWith(
        "/documents/doc-abc-123/collaborators",
      );
    });

    it("removeCollaborator calls DELETE /documents/:id/collaborators/:userId", async () => {
      await sharingApi.removeCollaborator("doc-abc-123", "user-xyz-789");
      expect(axios.delete).toHaveBeenCalledWith(
        "/documents/doc-abc-123/collaborators/user-xyz-789",
      );
    });

    it("listShared calls GET /documents/shared", async () => {
      await sharingApi.listShared();
      expect(axios.get).toHaveBeenCalledWith("/documents/shared");
    });

    it("recordView calls POST /documents/:id/view", async () => {
      await sharingApi.recordView("doc-abc-123");
      expect(axios.post).toHaveBeenCalledWith("/documents/doc-abc-123/view");
    });

    it("listRecentlyViewed calls GET /documents/recent", async () => {
      await sharingApi.listRecentlyViewed();
      expect(axios.get).toHaveBeenCalledWith("/documents/recent");
    });
  });

  describe("commentsApi", () => {
    it("list calls GET /documents/:id/comments", async () => {
      await commentsApi.list("doc-abc-123");
      expect(axios.get).toHaveBeenCalledWith(
        "/documents/doc-abc-123/comments",
      );
    });

    it("create calls POST /documents/:id/comments with payload", async () => {
      await commentsApi.create("doc-abc-123", {
        content: "Great point!",
        anchor_from: 0,
        anchor_to: 10,
        quoted_text: "hello world",
      });
      expect(axios.post).toHaveBeenCalledWith(
        "/documents/doc-abc-123/comments",
        {
          content: "Great point!",
          anchor_from: 0,
          anchor_to: 10,
          quoted_text: "hello world",
        },
      );
    });

    it("reply calls POST /comments/:id/reply with content payload", async () => {
      await commentsApi.reply("comment-xyz-789", {
        content: "I agree",
      });
      expect(axios.post).toHaveBeenCalledWith(
        "/comments/comment-xyz-789/reply",
        { content: "I agree" },
      );
    });

    it("resolve calls POST /comments/:id/resolve", async () => {
      await commentsApi.resolve("comment-xyz-789");
      expect(axios.post).toHaveBeenCalledWith(
        "/comments/comment-xyz-789/resolve",
      );
    });

    it("reanchor calls PATCH /comments/:id/reanchor with payload", async () => {
      await commentsApi.reanchor("comment-xyz-789", {
        anchor_from: 5,
        anchor_to: 15,
      });
      expect(axios.patch).toHaveBeenCalledWith(
        "/comments/comment-xyz-789/reanchor",
        { anchor_from: 5, anchor_to: 15 },
      );
    });

    it("orphan calls PATCH /comments/:id/orphan", async () => {
      await commentsApi.orphan("comment-xyz-789");
      expect(axios.patch).toHaveBeenCalledWith(
        "/comments/comment-xyz-789/orphan",
      );
    });

    it("delete calls DELETE /comments/:id", async () => {
      await commentsApi.delete("comment-xyz-789");
      expect(axios.delete).toHaveBeenCalledWith(
        "/comments/comment-xyz-789",
      );
    });
  });

  describe("versionsApi", () => {
    it("list calls GET /documents/:id/versions", async () => {
      await versionsApi.list("doc-abc-123");
      expect(axios.get).toHaveBeenCalledWith(
        "/documents/doc-abc-123/versions",
      );
    });

    it("get calls GET /documents/:id/versions/:versionNumber", async () => {
      await versionsApi.get("doc-abc-123", 42);
      expect(axios.get).toHaveBeenCalledWith(
        "/documents/doc-abc-123/versions/42",
      );
    });

    it("create calls POST /documents/:id/versions with payload", async () => {
      await versionsApi.create("doc-abc-123", {
        content: "# Document content",
        summary: "Initial version",
      });
      expect(axios.post).toHaveBeenCalledWith(
        "/documents/doc-abc-123/versions",
        { content: "# Document content", summary: "Initial version" },
      );
    });

    it("create sends minimal payload without summary", async () => {
      await versionsApi.create("doc-abc-123", { content: "minimal" });
      expect(axios.post).toHaveBeenCalledWith(
        "/documents/doc-abc-123/versions",
        { content: "minimal" },
      );
    });
  });
});
