import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { render, screen, fireEvent, cleanup, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ShareDialog } from "./ShareDialog";
import type { Collaborator, GeneralAccess } from "../../lib/api";

vi.mock("../../lib/api", () => ({
  sharingApi: {
    listCollaborators: vi.fn(),
    addCollaborator: vi.fn(),
    removeCollaborator: vi.fn(),
    updateGeneralAccess: vi.fn(),
  },
}));

import { sharingApi } from "../../lib/api";

const defaultProps = {
  docId: "doc-456",
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
  user_id: "user-789",
  email: "collab@example.com",
  name: "Bob Collaborator",
  avatar_url: null,
  permission: "view",
  granted_at: "2026-01-01T00:00:00Z",
};

let mockWriteText: ReturnType<typeof vi.fn>;

describe("ShareDialog", () => {
  beforeEach(() => {
    mockWriteText = vi.fn();
    vi.mocked(sharingApi.listCollaborators).mockResolvedValue({
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
    const { container } = render(<ShareDialog {...defaultProps} open={false} />);
    expect(container.firstChild).toBeNull();
  });

  it("renders Share document title when open", () => {
    render(<ShareDialog {...defaultProps} />);
    expect(screen.getByText("Share document")).toBeInTheDocument();
  });

  it("shows owner name and email with (Owner) label", () => {
    render(<ShareDialog {...defaultProps} />);
    expect(screen.getByText(/Jane Owner/)).toBeInTheDocument();
    expect(screen.getByText("(Owner)")).toBeInTheDocument();
    expect(screen.getByText("owner@example.com")).toBeInTheDocument();
  });

  it("fetches collaborators on open with exact docId", async () => {
    vi.mocked(sharingApi.listCollaborators).mockResolvedValue({
      data: [mockCollaborator],
    } as never);

    render(<ShareDialog {...defaultProps} />);

    await waitFor(() => {
      expect(sharingApi.listCollaborators).toHaveBeenCalledWith("doc-456");
    });
  });

  it("does NOT fetch collaborators when not isOwner", async () => {
    render(<ShareDialog {...defaultProps} isOwner={false} />);

    await waitFor(() => {});

    expect(sharingApi.listCollaborators).not.toHaveBeenCalled();
  });

  it("add collaborator: calls sharingApi.addCollaborator with exact docId, email, permission", async () => {
    const user = userEvent.setup();
    vi.mocked(sharingApi.addCollaborator).mockResolvedValue({} as never);
    vi.mocked(sharingApi.listCollaborators).mockResolvedValue({
      data: [mockCollaborator],
    } as never);

    render(<ShareDialog {...defaultProps} />);

    const emailInput = screen.getByPlaceholderText("Enter email address");
    await user.type(emailInput, "new@example.com");

    const addButton = screen.getByRole("button", { name: /^Add$/ });
    await user.click(addButton);

    await waitFor(() => {
      expect(sharingApi.addCollaborator).toHaveBeenCalledWith("doc-456", {
        email: "new@example.com",
        permission: "view",
      });
    });
  });

  it("add collaborator error: shows exact error detail from API response", async () => {
    const user = userEvent.setup();
    const apiError = {
      response: { data: { detail: "User not found in system" } },
    };
    vi.mocked(sharingApi.addCollaborator).mockRejectedValue(apiError);

    render(<ShareDialog {...defaultProps} />);

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
    vi.mocked(sharingApi.addCollaborator).mockRejectedValue(new Error("Network error"));

    render(<ShareDialog {...defaultProps} />);

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
    vi.mocked(sharingApi.addCollaborator).mockReturnValue(addPromise as never);

    const user = userEvent.setup();
    render(<ShareDialog {...defaultProps} />);

    const emailInput = screen.getByPlaceholderText("Enter email address");
    await user.type(emailInput, "loading@example.com");

    const addButton = screen.getByRole("button", { name: /^Add$/ });
    await user.click(addButton);

    expect(addButton).toBeDisabled();
    resolveAdd!();
    await addPromise;
  });

  it("remove collaborator: calls sharingApi.removeCollaborator with exact docId and userId", async () => {
    const user = userEvent.setup();
    vi.mocked(sharingApi.listCollaborators).mockResolvedValue({
      data: [mockCollaborator],
    } as never);
    vi.mocked(sharingApi.removeCollaborator).mockResolvedValue({} as never);

    render(<ShareDialog {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("Bob Collaborator")).toBeInTheDocument();
    });

    const removeButton = screen.getByTitle("Remove access");
    await user.click(removeButton);

    await waitFor(() => {
      expect(sharingApi.removeCollaborator).toHaveBeenCalledWith("doc-456", "user-789");
    });
  });

  it("change collaborator permission: calls sharingApi.addCollaborator with new permission", async () => {
    vi.mocked(sharingApi.listCollaborators).mockResolvedValue({
      data: [mockCollaborator],
    } as never);
    vi.mocked(sharingApi.addCollaborator).mockResolvedValue({} as never);

    render(<ShareDialog {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("Bob Collaborator")).toBeInTheDocument();
    });

    const collabRow = screen.getByText("Bob Collaborator").closest("li");
    const collaboratorSelect = collabRow?.querySelector("select");
    expect(collaboratorSelect).toBeTruthy();
    fireEvent.change(collaboratorSelect!, { target: { value: "edit" } });

    await waitFor(() => {
      expect(sharingApi.addCollaborator).toHaveBeenCalledWith("doc-456", {
        email: "collab@example.com",
        permission: "edit",
      });
    });
  });

  it("general access change (owner): calls sharingApi.updateGeneralAccess with exact docId and new value", async () => {
    vi.mocked(sharingApi.updateGeneralAccess).mockResolvedValue({} as never);

    render(<ShareDialog {...defaultProps} />);

    const generalAccessSelects = screen.getAllByRole("combobox");
    const gaSelect = generalAccessSelects.find((s) =>
      Array.from((s as HTMLSelectElement).options).some((o) => o.value === "anyone_edit"),
    ) as HTMLSelectElement;
    fireEvent.change(gaSelect, { target: { value: "anyone_edit" } });

    await waitFor(() => {
      expect(sharingApi.updateGeneralAccess).toHaveBeenCalledWith("doc-456", "anyone_edit");
    });
  });

  it("general access change: calls onGeneralAccessChange with new value", async () => {
    const onGeneralAccessChange = vi.fn();
    vi.mocked(sharingApi.updateGeneralAccess).mockResolvedValue({} as never);

    render(<ShareDialog {...defaultProps} onGeneralAccessChange={onGeneralAccessChange} />);

    const generalAccessSelects = screen.getAllByRole("combobox");
    const gaSelect = generalAccessSelects.find((s) =>
      Array.from((s as HTMLSelectElement).options).some((o) => o.value === "anyone_view"),
    ) as HTMLSelectElement;
    fireEvent.change(gaSelect, { target: { value: "anyone_view" } });

    await waitFor(() => {
      expect(onGeneralAccessChange).toHaveBeenCalledWith("anyone_view");
    });
  });

  it("general access displayed correctly for all 3 values", () => {
    const { rerender } = render(<ShareDialog {...defaultProps} generalAccess="restricted" />);
    expect(screen.getAllByText("Restricted").length).toBeGreaterThan(0);

    rerender(<ShareDialog {...defaultProps} generalAccess="anyone_view" />);
    expect(screen.getAllByText("Anyone with the link can view").length).toBeGreaterThan(0);

    rerender(<ShareDialog {...defaultProps} generalAccess="anyone_edit" />);
    expect(screen.getAllByText("Anyone with the link can edit").length).toBeGreaterThan(0);
  });

  it("non-owner: hides Add people, shows general access as text", async () => {
    render(<ShareDialog {...defaultProps} isOwner={false} />);

    await waitFor(() => {});

    expect(screen.queryByText("Add people")).not.toBeInTheDocument();
    expect(screen.queryByPlaceholderText("Enter email address")).not.toBeInTheDocument();
    expect(screen.queryByTitle("Remove access")).not.toBeInTheDocument();
    expect(screen.getByText("Restricted")).toBeInTheDocument();
  });

  it("copy link: copies correct URL format", () => {
    render(<ShareDialog {...defaultProps} />);

    const copyButton = screen.getByRole("button", { name: /Copy link/i });
    fireEvent.click(copyButton);

    expect(mockWriteText).toHaveBeenCalledWith(`${window.location.origin}/edit/doc-456`);
  });

  it("copy link: shows Link copied after click", async () => {
    const user = userEvent.setup();

    render(<ShareDialog {...defaultProps} />);

    const copyButton = screen.getByRole("button", { name: /Copy link/i });
    await user.click(copyButton);

    expect(screen.getByText("Link copied!")).toBeInTheDocument();
  });

  it("Enter key triggers add", async () => {
    vi.mocked(sharingApi.addCollaborator).mockResolvedValue({} as never);
    vi.mocked(sharingApi.listCollaborators).mockResolvedValue({
      data: [],
    } as never);

    render(<ShareDialog {...defaultProps} />);

    const emailInput = screen.getByPlaceholderText("Enter email address");
    fireEvent.change(emailInput, { target: { value: "enter@example.com" } });
    fireEvent.keyDown(emailInput, { key: "Enter" });

    await waitFor(() => {
      expect(sharingApi.addCollaborator).toHaveBeenCalledWith("doc-456", {
        email: "enter@example.com",
        permission: "view",
      });
    });
  });

  it("close button calls onClose", () => {
    const onClose = vi.fn();
    render(<ShareDialog {...defaultProps} onClose={onClose} />);

    const buttons = screen.getAllByRole("button");
    const closeButton = buttons[0];
    fireEvent.click(closeButton);

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("general access error: shows error when updateGeneralAccess fails", async () => {
    vi.mocked(sharingApi.updateGeneralAccess).mockRejectedValue(new Error("Forbidden"));

    render(<ShareDialog {...defaultProps} />);

    const generalAccessSelects = screen.getAllByRole("combobox");
    const gaSelect = generalAccessSelects.find((s) =>
      Array.from((s as HTMLSelectElement).options).some((o) => o.value === "anyone_view"),
    ) as HTMLSelectElement;
    fireEvent.change(gaSelect, { target: { value: "anyone_view" } });

    await waitFor(
      () => {
        expect(screen.getByText("Failed to update access settings")).toBeInTheDocument();
      },
      { timeout: 1000 },
    );
  });

  it("permission change error: shows Failed to update permission when addCollaborator fails", async () => {
    vi.mocked(sharingApi.listCollaborators).mockResolvedValue({
      data: [mockCollaborator],
    } as never);
    vi.mocked(sharingApi.addCollaborator).mockRejectedValue(new Error("Forbidden"));

    render(<ShareDialog {...defaultProps} />);

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
    vi.mocked(sharingApi.listCollaborators).mockRejectedValue(new Error("Network error"));

    render(<ShareDialog {...defaultProps} />);

    await waitFor(() => {});

    expect(screen.getByText("Jane Owner")).toBeInTheDocument();
    expect(screen.getByText("(Owner)")).toBeInTheDocument();
  });

  it("owner with empty name shows fallback avatar", async () => {
    vi.mocked(sharingApi.listCollaborators).mockResolvedValue({
      data: [],
    } as never);

    const { getByTestId } = render(<ShareDialog {...defaultProps} ownerName="" ownerEmail="owner@example.com" />);

    await waitFor(() => {});

    expect(getByTestId("avatar-fallback")).toBeTruthy();
  });
});
