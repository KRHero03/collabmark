import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { render, cleanup, waitFor } from "@testing-library/react";
import { AclPanel } from "./AclPanel";

vi.mock("../../lib/api", () => ({
  aclApi: {
    getDocumentAcl: vi.fn(),
    getFolderAcl: vi.fn(),
  },
}));

import { aclApi } from "../../lib/api";

const mockEntries = [
  {
    user_id: "u1",
    user_name: "Alice Owner",
    user_email: "alice@example.com",
    avatar_url: null,
    can_view: true,
    can_edit: true,
    can_delete: true,
    can_share: true,
    role: "owner" as const,
    inherited_from_id: null,
    inherited_from_name: null,
  },
  {
    user_id: "u2",
    user_name: "Bob Editor",
    user_email: "bob@example.com",
    avatar_url: "https://example.com/bob.png",
    can_view: true,
    can_edit: true,
    can_delete: false,
    can_share: false,
    role: "editor" as const,
    inherited_from_id: "f1",
    inherited_from_name: "Parent Folder",
  },
  {
    user_id: "u3",
    user_name: "Carol Viewer",
    user_email: "carol@example.com",
    avatar_url: null,
    can_view: true,
    can_edit: false,
    can_delete: false,
    can_share: false,
    role: "viewer" as const,
    inherited_from_id: null,
    inherited_from_name: null,
  },
];

describe("AclPanel", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  beforeEach(() => {
    vi.mocked(aclApi.getDocumentAcl).mockResolvedValue({ data: mockEntries } as any);
    vi.mocked(aclApi.getFolderAcl).mockResolvedValue({ data: mockEntries } as any);
  });

  it("does not render when open is false", () => {
    const { container } = render(
      <AclPanel entityType="document" entityId="d1" entityName="Test Doc" open={false} onClose={vi.fn()} />,
    );
    expect(container.firstChild).toBeNull();
  });

  it("fetches document ACL and renders entries", async () => {
    const { getByText } = render(
      <AclPanel entityType="document" entityId="d1" entityName="Test Doc" open={true} onClose={vi.fn()} />,
    );
    expect(aclApi.getDocumentAcl).toHaveBeenCalledWith("d1");

    await waitFor(() => {
      expect(getByText("Alice Owner")).toBeDefined();
      expect(getByText("Bob Editor")).toBeDefined();
      expect(getByText("Carol Viewer")).toBeDefined();
    });
  });

  it("fetches folder ACL when entityType is folder", async () => {
    const { getByText } = render(
      <AclPanel entityType="folder" entityId="f1" entityName="Test Folder" open={true} onClose={vi.fn()} />,
    );
    expect(aclApi.getFolderAcl).toHaveBeenCalledWith("f1");

    await waitFor(() => {
      expect(getByText("Alice Owner")).toBeDefined();
    });
  });

  it("displays role labels", async () => {
    const { getByText } = render(
      <AclPanel entityType="document" entityId="d1" entityName="Doc" open={true} onClose={vi.fn()} />,
    );

    await waitFor(() => {
      expect(getByText("Owner")).toBeDefined();
      expect(getByText("Editor")).toBeDefined();
      expect(getByText("Viewer")).toBeDefined();
    });
  });

  it("displays entity name in header", async () => {
    const { getByText } = render(
      <AclPanel entityType="document" entityId="d1" entityName="My Special Doc" open={true} onClose={vi.fn()} />,
    );
    expect(getByText("My Special Doc")).toBeDefined();
  });

  it("displays inherited from info", async () => {
    const { getByText } = render(
      <AclPanel entityType="document" entityId="d1" entityName="Doc" open={true} onClose={vi.fn()} />,
    );

    await waitFor(() => {
      expect(getByText("via Parent Folder")).toBeDefined();
    });
  });

  it("shows loading state", () => {
    vi.mocked(aclApi.getDocumentAcl).mockReturnValue(new Promise(() => {}) as any);
    const { getByText } = render(
      <AclPanel entityType="document" entityId="d1" entityName="Doc" open={true} onClose={vi.fn()} />,
    );
    expect(getByText("Loading permissions...")).toBeDefined();
  });

  it("shows error state on failure", async () => {
    vi.mocked(aclApi.getDocumentAcl).mockRejectedValue(new Error("fail"));
    const { getByText } = render(
      <AclPanel entityType="document" entityId="d1" entityName="Doc" open={true} onClose={vi.fn()} />,
    );

    await waitFor(() => {
      expect(getByText("Failed to load permissions")).toBeDefined();
    });
  });

  it("calls onClose when Close button is clicked", async () => {
    const onClose = vi.fn();
    const { getByText } = render(
      <AclPanel entityType="document" entityId="d1" entityName="Doc" open={true} onClose={onClose} />,
    );

    await waitFor(() => {
      expect(getByText("Alice Owner")).toBeDefined();
    });

    const closeBtn = getByText("Close");
    closeBtn.click();
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("calls onClose when clicking the backdrop", async () => {
    const onClose = vi.fn();
    const { container } = render(
      <AclPanel entityType="document" entityId="d1" entityName="Doc" open={true} onClose={onClose} />,
    );

    await waitFor(() => {});

    const backdrop = container.querySelector(".fixed.inset-0");
    backdrop?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    expect(onClose).toHaveBeenCalled();
  });

  it("renders avatar image when url is provided", async () => {
    const { container } = render(
      <AclPanel entityType="document" entityId="d1" entityName="Doc" open={true} onClose={vi.fn()} />,
    );

    await waitFor(() => {
      const img = container.querySelector("img[src='https://example.com/bob.png']");
      expect(img).not.toBeNull();
    });
  });

  it("renders initials when no avatar url", async () => {
    const { getByText } = render(
      <AclPanel entityType="document" entityId="d1" entityName="Doc" open={true} onClose={vi.fn()} />,
    );

    await waitFor(() => {
      expect(getByText("AO")).toBeDefined(); // Alice Owner
      expect(getByText("CV")).toBeDefined(); // Carol Viewer
    });
  });
});
