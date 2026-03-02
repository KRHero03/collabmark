/**
 * Tests for the API client module.
 *
 * Validates that the API functions call the correct endpoints
 * with the correct parameters.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import axios from "axios";
import { documentsApi, keysApi, authApi } from "./api";

vi.mock("axios", () => {
  const mockAxios = {
    create: vi.fn(() => mockAxios),
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
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
});
