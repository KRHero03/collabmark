import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { render, screen, fireEvent, cleanup, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { FolderShareDialog } from "./FolderShareDialog";
import type { Collaborator, GeneralAccess } from "../../lib/api";

vi.mock("../../lib/api", () => ({
  foldersApi: {
    listCollaborators: vi.fn(),
    addCollaborator: vi.fn(),
    removeCollaborator: vi.fn(),
    update: vi.fn(),
  },
}));

import { foldersApi } from "../../lib/api";

const defaultProps = {
  folderId: "folder-123",
  open: true,
  onClose: vi.fn(),
  isOwner: true,
  generalAccess: "restricted" as GeneralAccess,
  ownerEmail: "owner@example.com",
  ownerName: "Jane Owner",
  onGeneralAccessChange: vi.fn(),
};

const mockCollaborator: Collaborator = {
  id: "collab-1",
  user_id: "user-456",
  email: "collab@example.com",
  name: "Bob Collaborator",
  avatar_url: null,
  permission: "view",
  granted_at: "2026-01-01T00:00:00Z",
};

let mockWriteText: ReturnType<typeof vi.fn>;

describe("FolderShareDialog", () => {
  beforeEach(() => {
    mockWriteText = vi.fn().mockResolvedValue(undefined);
    vi.mocked(foldersApi.listCollaborators).mockResolvedValue({
      data: [],
    } as never);
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText: mockWriteText },
      writable: true,
      configurable: true,
    });
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("returns null when open is false", () => {
    const { container } = render(<FolderShareDialog {...defaultProps} open={false} />);
    expect(container.firstChild).toBeNull();
  });

  it("renders Share folder title when open", () => {
    render(<FolderShareDialog {...defaultProps} />);
    expect(screen.getByText("Share folder")).toBeInTheDocument();
  });

  it("shows owner name and email with (Owner) label", () => {
    render(<FolderShareDialog {...defaultProps} />);
    expect(screen.getByText(/Jane Owner/)).toBeInTheDocument();
    expect(screen.getByText("(Owner)")).toBeInTheDocument();
    expect(screen.getByText("owner@example.com")).toBeInTheDocument();
  });

  it("fetches collaborators on open with exact folderId", async () => {
    vi.mocked(foldersApi.listCollaborators).mockResolvedValue({
      data: [mockCollaborator],
    } as never);

    render(<FolderShareDialog {...defaultProps} />);

    await waitFor(() => {
      expect(foldersApi.listCollaborators).toHaveBeenCalledWith("folder-123");
    });
  });

  it("does NOT fetch collaborators when not isOwner", async () => {
    render(<FolderShareDialog {...defaultProps} isOwner={false} />);

    await waitFor(() => {});

    expect(foldersApi.listCollaborators).not.toHaveBeenCalled();
  });

  it("add collaborator: calls foldersApi.addCollaborator with exact folderId, email, permission", async () => {
    const user = userEvent.setup();
    vi.mocked(foldersApi.addCollaborator).mockResolvedValue({} as never);
    vi.mocked(foldersApi.listCollaborators).mockResolvedValue({
      data: [mockCollaborator],
    } as never);

    render(<FolderShareDialog {...defaultProps} />);

    const emailInput = screen.getByPlaceholderText("Enter email address");
    await user.type(emailInput, "new@example.com");

    const addButton = screen.getByRole("button", { name: /^Add$/ });
    await user.click(addButton);

    await waitFor(() => {
      expect(foldersApi.addCollaborator).toHaveBeenCalledWith("folder-123", {
        email: "new@example.com",
        permission: "view",
      });
    });
  });

  it("add collaborator with edit permission", async () => {
    const user = userEvent.setup();
    vi.mocked(foldersApi.addCollaborator).mockResolvedValue({} as never);
    vi.mocked(foldersApi.listCollaborators).mockResolvedValue({
      data: [],
    } as never);

    render(<FolderShareDialog {...defaultProps} />);

    const emailInput = screen.getByPlaceholderText("Enter email address");
    await user.type(emailInput, "editor@example.com");

    const permissionSelects = screen.getAllByRole("combobox");
    const addPermissionSelect = permissionSelects[0];
    fireEvent.change(addPermissionSelect, { target: { value: "edit" } });

    const addButton = screen.getByRole("button", { name: /^Add$/ });
    await user.click(addButton);

    await waitFor(() => {
      expect(foldersApi.addCollaborator).toHaveBeenCalledWith("folder-123", {
        email: "editor@example.com",
        permission: "edit",
      });
    });
  });

  it("add collaborator error: shows exact error detail from API response", async () => {
    const user = userEvent.setup();
    const apiError = {
      response: { data: { detail: "User not found in system" } },
    };
    vi.mocked(foldersApi.addCollaborator).mockRejectedValue(apiError);

    render(<FolderShareDialog {...defaultProps} />);

    const emailInput = screen.getByPlaceholderText("Enter email address");
    await user.type(emailInput, "bad@example.com");

    const addButton = screen.getByRole("button", { name: /^Add$/ });
    await user.click(addButton);

    await waitFor(() => {
      expect(screen.getByText("User not found in system")).toBeInTheDocument();
    });
  });

  it("add collaborator error: shows fallback when no detail in response", async () => {
    const user = userEvent.setup();
    vi.mocked(foldersApi.addCollaborator).mockRejectedValue(new Error("Network error"));

    render(<FolderShareDialog {...defaultProps} />);

    const emailInput = screen.getByPlaceholderText("Enter email address");
    await user.type(emailInput, "bad@example.com");

    const addButton = screen.getByRole("button", { name: /^Add$/ });
    await user.click(addButton);

    await waitFor(() => {
      expect(screen.getByText("Failed to add collaborator")).toBeInTheDocument();
    });
  });

  it("add collaborator loading: button disabled during request", async () => {
    let resolveAdd: () => void;
    const addPromise = new Promise<void>((r) => {
      resolveAdd = r;
    });
    vi.mocked(foldersApi.addCollaborator).mockReturnValue(addPromise as never);

    const user = userEvent.setup();
    render(<FolderShareDialog {...defaultProps} />);

    const emailInput = screen.getByPlaceholderText("Enter email address");
    await user.type(emailInput, "loading@example.com");

    const addButton = screen.getByRole("button", { name: /^Add$/ });
    await user.click(addButton);

    expect(addButton).toBeDisabled();
    resolveAdd!();
    await addPromise;
  });

  it("remove collaborator: calls foldersApi.removeCollaborator with exact folderId and userId", async () => {
    const user = userEvent.setup();
    vi.mocked(foldersApi.listCollaborators).mockResolvedValue({
      data: [mockCollaborator],
    } as never);
    vi.mocked(foldersApi.removeCollaborator).mockResolvedValue({} as never);

    render(<FolderShareDialog {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("Bob Collaborator")).toBeInTheDocument();
    });

    const removeButton = screen.getByTitle("Remove access");
    await user.click(removeButton);

    await waitFor(() => {
      expect(foldersApi.removeCollaborator).toHaveBeenCalledWith("folder-123", "user-456");
    });
  });

  it("change collaborator permission: calls foldersApi.addCollaborator with new permission", async () => {
    vi.mocked(foldersApi.listCollaborators).mockResolvedValue({
      data: [mockCollaborator],
    } as never);
    vi.mocked(foldersApi.addCollaborator).mockResolvedValue({} as never);

    render(<FolderShareDialog {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("Bob Collaborator")).toBeInTheDocument();
    });

    const collabRow = screen.getByText("Bob Collaborator").closest("li");
    const collaboratorSelect = collabRow?.querySelector("select");
    expect(collaboratorSelect).toBeTruthy();
    fireEvent.change(collaboratorSelect!, { target: { value: "edit" } });

    await waitFor(() => {
      expect(foldersApi.addCollaborator).toHaveBeenCalledWith("folder-123", {
        email: "collab@example.com",
        permission: "edit",
      });
    });
  });

  it("general access change (owner): calls foldersApi.update with exact folderId and new value", async () => {
    vi.mocked(foldersApi.update).mockResolvedValue({} as never);

    render(<FolderShareDialog {...defaultProps} />);

    const generalAccessSelects = screen.getAllByRole("combobox");
    const gaSelect = generalAccessSelects.find((s) =>
      Array.from((s as HTMLSelectElement).options).some((o) => o.value === "anyone_view"),
    ) as HTMLSelectElement;
    fireEvent.change(gaSelect, { target: { value: "anyone_view" } });

    await waitFor(() => {
      expect(foldersApi.update).toHaveBeenCalledWith("folder-123", {
        general_access: "anyone_view",
      });
    });
  });

  it("general access displayed correctly for restricted", () => {
    render(<FolderShareDialog {...defaultProps} generalAccess="restricted" />);
    expect(screen.getAllByText("Restricted").length).toBeGreaterThan(0);
  });

  it("general access displayed correctly for anyone_view", () => {
    render(<FolderShareDialog {...defaultProps} generalAccess="anyone_view" />);
    expect(screen.getAllByText("Anyone with the link can view").length).toBeGreaterThan(0);
  });

  it("general access displayed correctly for anyone_edit", () => {
    render(<FolderShareDialog {...defaultProps} generalAccess="anyone_edit" />);
    expect(screen.getAllByText("Anyone with the link can edit").length).toBeGreaterThan(0);
  });

  it("non-owner: shows permissions as text spans, no edit controls", async () => {
    vi.mocked(foldersApi.listCollaborators).mockResolvedValue({
      data: [mockCollaborator],
    } as never);

    render(<FolderShareDialog {...defaultProps} isOwner={false} />);

    await waitFor(() => {});

    expect(screen.queryByText("Add people")).not.toBeInTheDocument();
    expect(screen.queryByPlaceholderText("Enter email address")).not.toBeInTheDocument();
    expect(screen.queryByTitle("Remove access")).not.toBeInTheDocument();

    expect(screen.getByText("Restricted")).toBeInTheDocument();
  });

  it("copy link: copies correct URL format", async () => {
    const user = userEvent.setup();
    const writeText = vi.fn();
    Object.assign(navigator.clipboard, { writeText });

    render(<FolderShareDialog {...defaultProps} />);

    const copyButton = screen.getByRole("button", { name: /Copy link/i });
    await user.click(copyButton);

    expect(writeText).toHaveBeenCalledWith(`${window.location.origin}/?folder=folder-123`);
  });

  it("copy link: shows Link copied after click", async () => {
    const user = userEvent.setup();

    render(<FolderShareDialog {...defaultProps} />);

    const copyButton = screen.getByRole("button", { name: /Copy link/i });
    await user.click(copyButton);

    expect(screen.getByText("Link copied!")).toBeInTheDocument();
  });

  it("Enter key triggers add", async () => {
    vi.mocked(foldersApi.addCollaborator).mockResolvedValue({} as never);
    vi.mocked(foldersApi.listCollaborators).mockResolvedValue({
      data: [],
    } as never);

    render(<FolderShareDialog {...defaultProps} />);

    const emailInput = screen.getByPlaceholderText("Enter email address");
    fireEvent.change(emailInput, { target: { value: "enter@example.com" } });
    fireEvent.keyDown(emailInput, { key: "Enter" });

    await waitFor(() => {
      expect(foldersApi.addCollaborator).toHaveBeenCalledWith("folder-123", {
        email: "enter@example.com",
        permission: "view",
      });
    });
  });

  it("close button calls onClose", () => {
    const onClose = vi.fn();
    render(<FolderShareDialog {...defaultProps} onClose={onClose} />);

    const buttons = screen.getAllByRole("button");
    const closeButton = buttons[0];
    fireEvent.click(closeButton);

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("add button disabled when email is empty", () => {
    render(<FolderShareDialog {...defaultProps} />);
    const addButton = screen.getByRole("button", { name: /^Add$/ });
    expect(addButton).toBeDisabled();
  });

  it("does not add when email is only whitespace", () => {
    render(<FolderShareDialog {...defaultProps} />);

    const emailInput = screen.getByPlaceholderText("Enter email address");
    fireEvent.change(emailInput, { target: { value: "   " } });

    const addButton = screen.getByRole("button", { name: /^Add$/ });
    expect(addButton).toBeDisabled();
  });

  it("general access error: shows error when foldersApi.update fails", async () => {
    vi.mocked(foldersApi.update).mockRejectedValue(new Error("Forbidden"));

    render(<FolderShareDialog {...defaultProps} />);

    const generalAccessSelects = screen.getAllByRole("combobox");
    const gaSelect = generalAccessSelects.find((s) =>
      Array.from((s as HTMLSelectElement).options).some((o) => o.value === "anyone_view"),
    ) as HTMLSelectElement;
    fireEvent.change(gaSelect, { target: { value: "anyone_view" } });

    await waitFor(() => {
      expect(screen.getByText("Failed to update access settings")).toBeInTheDocument();
    });
  });

  it("permission change error: shows Failed to update permission when addCollaborator fails", async () => {
    vi.mocked(foldersApi.listCollaborators).mockResolvedValue({
      data: [mockCollaborator],
    } as never);
    vi.mocked(foldersApi.addCollaborator).mockRejectedValue(new Error("Forbidden"));

    render(<FolderShareDialog {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("Bob Collaborator")).toBeInTheDocument();
    });

    const collabRow = screen.getByText("Bob Collaborator").closest("li");
    const collaboratorSelect = collabRow?.querySelector("select");
    fireEvent.change(collaboratorSelect!, { target: { value: "edit" } });

    await waitFor(() => {
      expect(screen.getByText("Failed to update permission")).toBeInTheDocument();
    });
  });

  it("fetchCollaborators catch: sets empty collaborators when listCollaborators fails", async () => {
    vi.mocked(foldersApi.listCollaborators).mockRejectedValue(new Error("Network error"));

    render(<FolderShareDialog {...defaultProps} />);

    await waitFor(() => {});

    expect(screen.getByText("Jane Owner")).toBeInTheDocument();
    expect(screen.getByText("(Owner)")).toBeInTheDocument();
  });

  it("owner with empty name shows fallback avatar", async () => {
    vi.mocked(foldersApi.listCollaborators).mockResolvedValue({
      data: [],
    } as never);

    const { getByTestId } = render(<FolderShareDialog {...defaultProps} ownerName="" ownerEmail="owner@example.com" />);

    await waitFor(() => {});

    expect(getByTestId("avatar-fallback")).toBeTruthy();
  });
});
