import React from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, fireEvent, cleanup, waitFor, screen } from "@testing-library/react";
import { HomePage } from "./HomePage";

const mockNavigate = vi.fn();
const mockSearchParams = new URLSearchParams();
const mockSetSearchParams = vi.fn();

vi.mock("react-router", () => ({
  Link: ({
    to,
    children,
    ...props
  }: {
    to: string;
    children: React.ReactNode;
  }) => (
    <a href={to} {...props}>
      {children}
    </a>
  ),
  useNavigate: () => mockNavigate,
  useSearchParams: () => [mockSearchParams, mockSetSearchParams],
}));

const mockUser = {
  id: "user-1",
  name: "Test User",
  email: "test@example.com",
  avatar_url: null,
};
vi.mock("../hooks/useAuth", () => ({ useAuth: () => ({ user: mockUser }) }));

const mockAddToast = vi.fn();
vi.mock("../hooks/useToast", () => ({
  useToast: () => ({ addToast: mockAddToast }),
}));

const mockDeleteDocument = vi.fn();
const mockRenameDocument = vi.fn();
const mockFetchTrash = vi.fn();
const mockRestoreDocument = vi.fn();
const mockHardDeleteDocument = vi.fn();

let mockUseDocumentsState = {
  trash: [] as any[],
  trashLoading: false,
  deleteDocument: mockDeleteDocument,
  renameDocument: mockRenameDocument,
  fetchTrash: mockFetchTrash,
  restoreDocument: mockRestoreDocument,
  hardDeleteDocument: mockHardDeleteDocument,
};

vi.mock("../hooks/useDocuments", () => ({
  useDocuments: () => mockUseDocumentsState,
}));

const mockNavigateToFolder = vi.fn();
const mockCreateFolder = vi.fn();
const mockRenameFolder = vi.fn();
const mockSoftDeleteFolder = vi.fn();
const mockRestoreFolder = vi.fn();
const mockHardDeleteFolder = vi.fn();
const mockFetchTrashFolders = vi.fn();
const mockFetchContents = vi.fn();
const mockClearAccessError = vi.fn();

let mockFoldersState = {
  currentFolderId: null as string | null,
  currentFolderPermission: "edit" as string,
  accessError: null as string | null,
  clearAccessError: mockClearAccessError,
  folders: [] as any[],
  documents: [] as any[],
  breadcrumbs: [] as any[],
  trashFolders: [] as any[],
  loading: false,
  trashLoading: false,
  navigateToFolder: mockNavigateToFolder,
  createFolder: mockCreateFolder,
  renameFolder: mockRenameFolder,
  softDeleteFolder: mockSoftDeleteFolder,
  restoreFolder: mockRestoreFolder,
  hardDeleteFolder: mockHardDeleteFolder,
  fetchTrashFolders: mockFetchTrashFolders,
  fetchContents: mockFetchContents,
};

vi.mock("../hooks/useFolders", () => ({
  useFolders: () => mockFoldersState,
}));

const mockDocumentsApiCreate = vi.fn();
const mockFoldersApiListShared = vi.fn();
const mockFoldersApiListRecentlyViewed = vi.fn();
const mockSharingApiListShared = vi.fn();
const mockSharingApiListRecentlyViewed = vi.fn();

vi.mock("../lib/api", async (importOriginal) => {
  const actual = (await importOriginal()) as Record<string, unknown>;
  return {
    ...actual,
    documentsApi: {
      ...(actual.documentsApi as object),
      create: (...args: unknown[]) => mockDocumentsApiCreate(...args),
    },
    foldersApi: {
      ...(actual.foldersApi as object),
      listShared: (...args: unknown[]) => mockFoldersApiListShared(...args),
      listRecentlyViewed: (...args: unknown[]) =>
        mockFoldersApiListRecentlyViewed(...args),
    },
    sharingApi: {
      ...(actual.sharingApi as object),
      listShared: (...args: unknown[]) => mockSharingApiListShared(...args),
      listRecentlyViewed: (...args: unknown[]) =>
        mockSharingApiListRecentlyViewed(...args),
    },
  };
});

vi.mock("../components/Layout/Navbar", () => ({
  Navbar: (props: any) => (
    <div data-testid="navbar" data-active-tab={props.activeTab} />
  ),
}));
vi.mock("../components/Home/FolderBreadcrumbs", () => ({
  FolderBreadcrumbs: (props: {
    breadcrumbs: { id: string; name: string }[];
    onNavigate: (id: string | null) => void;
  }) => (
    <nav data-testid="breadcrumbs">
      <button data-testid="breadcrumb-home" onClick={() => props.onNavigate(null)}>
        Home
      </button>
      {props.breadcrumbs.map((c) => (
        <button key={c.id} onClick={() => props.onNavigate(c.id)}>
          {c.name}
        </button>
      ))}
    </nav>
  ),
}));
vi.mock("../components/Home/CreateFolderDialog", () => ({
  CreateFolderDialog: (props: any) =>
    props.open ? (
      <div data-testid="create-folder-dialog">
        <button data-testid="create-folder-submit" onClick={() => props.onCreate("New Folder Name")}>
          Create
        </button>
        <button data-testid="create-folder-cancel" onClick={props.onClose}>
          Cancel
        </button>
      </div>
    ) : null,
}));
vi.mock("../components/Home/FolderInfoModal", () => ({
  FolderInfoModal: (props: any) =>
    props.open ? (
      <div data-testid="folder-info-modal">
        <button data-testid="folder-info-close" onClick={props.onClose}>
          Close
        </button>
      </div>
    ) : null,
}));
vi.mock("../components/Home/FolderShareDialog", () => ({
  FolderShareDialog: (props: any) =>
    props.open ? (
      <div data-testid="folder-share-dialog">
        <button data-testid="folder-share-close" onClick={props.onClose}>
          Close
        </button>
        <button
          data-testid="folder-share-change-access"
          onClick={() => props.onGeneralAccessChange?.("anyone_edit")}
        >
          Change Access
        </button>
      </div>
    ) : null,
}));
vi.mock("../components/Editor/ShareDialog", () => ({
  ShareDialog: (props: any) =>
    props.open ? (
      <div data-testid="share-dialog">
        <button data-testid="share-dialog-close" onClick={props.onClose}>
          Close
        </button>
        <button
          data-testid="share-dialog-change-access"
          onClick={() => props.onGeneralAccessChange?.("anyone_view")}
        >
          Change Access
        </button>
      </div>
    ) : null,
}));
vi.mock("../components/Home/ConfirmDialog", () => ({
  ConfirmDialog: (props: any) =>
    props.open ? (
      <div data-testid="confirm-dialog">
        <button data-testid="confirm-btn" onClick={() => props.onConfirm?.()}>
          Confirm
        </button>
        <button data-testid="confirm-cancel" onClick={props.onCancel}>
          Cancel
        </button>
      </div>
    ) : null,
}));
vi.mock("../components/Home/ToastContainer", () => ({
  ToastContainer: () => <div data-testid="toast-container" />,
}));
vi.mock("../components/Home/DocumentContextMenu", async (importOriginal) => {
  const actual = (await importOriginal()) as {
    DocumentContextMenu: React.ComponentType<any>;
    getEntityActions: typeof import("../components/Home/DocumentContextMenu").getEntityActions;
    getSharedDocActions: typeof import("../components/Home/DocumentContextMenu").getSharedDocActions;
    getTrashDocActions: typeof import("../components/Home/DocumentContextMenu").getTrashDocActions;
    getTrashFolderActions: typeof import("../components/Home/DocumentContextMenu").getTrashFolderActions;
  };
  return {
    ...actual,
    DocumentContextMenu: (props: { actions: { label: string; onClick: () => void }[]; onClose: () => void }) => (
      <div data-testid="context-menu" role="menu">
        {props.actions?.map((action) => (
          <button key={action.label} onClick={() => { action.onClick(); props.onClose(); }}>
            {action.label}
          </button>
        ))}
      </div>
    ),
  };
});
vi.mock("../components/Home/DocumentInfoModal", () => ({
  DocumentInfoModal: (props: any) =>
    props.open ? (
      <div data-testid="doc-info-modal">
        <button data-testid="doc-info-close" onClick={props.onClose}>
          Close
        </button>
      </div>
    ) : null,
}));
vi.mock("../components/Home/RenameDialog", () => ({
  RenameDialog: (props: any) =>
    props.open ? (
      <div data-testid="rename-dialog">
        <button data-testid="rename-save" onClick={() => props.onSave("New Name")}>
          Save
        </button>
        <button data-testid="rename-cancel" onClick={props.onClose}>
          Cancel
        </button>
      </div>
    ) : null,
}));

describe("HomePage", () => {
  const defaultFoldersState = {
    currentFolderId: null as string | null,
    currentFolderPermission: "edit" as string,
    accessError: null as string | null,
    clearAccessError: mockClearAccessError,
    folders: [] as any[],
    documents: [] as any[],
    breadcrumbs: [] as any[],
    trashFolders: [] as any[],
    loading: false,
    trashLoading: false,
    navigateToFolder: mockNavigateToFolder,
    createFolder: mockCreateFolder,
    renameFolder: mockRenameFolder,
    softDeleteFolder: mockSoftDeleteFolder,
    restoreFolder: mockRestoreFolder,
    hardDeleteFolder: mockHardDeleteFolder,
    fetchTrashFolders: mockFetchTrashFolders,
    fetchContents: mockFetchContents,
  };

  beforeEach(() => {
    vi.clearAllMocks();
    mockFoldersState = { ...defaultFoldersState };
    mockUseDocumentsState = {
      trash: [],
      trashLoading: false,
      deleteDocument: mockDeleteDocument,
      renameDocument: mockRenameDocument,
      fetchTrash: mockFetchTrash,
      restoreDocument: mockRestoreDocument,
      hardDeleteDocument: mockHardDeleteDocument,
    };
    mockSharingApiListShared.mockResolvedValue({ data: [] });
    mockFoldersApiListShared.mockResolvedValue({ data: [] });
    mockSharingApiListRecentlyViewed.mockResolvedValue({ data: [] });
    mockFoldersApiListRecentlyViewed.mockResolvedValue({ data: [] });
    mockDocumentsApiCreate.mockResolvedValue({
      data: { id: "doc-new-1", title: "Untitled" },
    });
  });

  afterEach(cleanup);

  it("sets document.title to 'Home - CollabMark' on mount", () => {
    render(<HomePage />);
    expect(document.title).toBe("Home - CollabMark");
  });

  it("renders Navbar with activeTab 'browse'", () => {
    const { getByTestId } = render(<HomePage />);
    const navbar = getByTestId("navbar");
    expect(navbar).toBeInTheDocument();
    expect(navbar).toHaveAttribute("data-active-tab", "browse");
  });

  it("renders ToastContainer", () => {
    const { getByTestId } = render(<HomePage />);
    expect(getByTestId("toast-container")).toBeInTheDocument();
  });

  it("desktop tab bar is rendered with 4 tabs (Files, Shared with me, Recently viewed, Trash)", () => {
    const { getAllByText, getByText } = render(<HomePage />);
    expect(getAllByText("Files").length).toBeGreaterThanOrEqual(1);
    expect(getByText("Shared with me")).toBeInTheDocument();
    expect(getByText("Recently viewed")).toBeInTheDocument();
    expect(getByText("Trash")).toBeInTheDocument();
  });

  it("mobile section label shows 'Files' for browse tab", () => {
    const { container } = render(<HomePage />);
    const mobileSection = container.querySelector(".mb-4.flex.items-center.gap-2");
    expect(mobileSection).toBeInTheDocument();
    expect(mobileSection?.textContent).toContain("Files");
  });

  it("clicking 'Shared with me' tab calls API and shows shared content", async () => {
    const sharedDoc = {
      id: "shared-doc-1",
      title: "Shared Doc",
      content: "",
      owner_id: "owner-1",
      permission: "edit" as const,
      last_accessed_at: "2025-01-01T00:00:00Z",
      created_at: "2025-01-01T00:00:00Z",
      updated_at: "2025-01-01T00:00:00Z",
    };
    mockSharingApiListShared.mockResolvedValue({ data: [sharedDoc] });
    mockFoldersApiListShared.mockResolvedValue({ data: [] });

    const { getByText } = render(<HomePage />);
    fireEvent.click(getByText("Shared with me"));

    await waitFor(() => {
      expect(mockSharingApiListShared).toHaveBeenCalled();
      expect(mockFoldersApiListShared).toHaveBeenCalled();
    });

    await waitFor(() => {
      expect(getByText("Shared Doc")).toBeInTheDocument();
    });
  });

  it("shows breadcrumbs in browse tab", () => {
    const { getByTestId } = render(<HomePage />);
    expect(getByTestId("breadcrumbs")).toBeInTheDocument();
  });

  it("shows 'My Files' heading when no breadcrumbs", () => {
    const { getByText } = render(<HomePage />);
    expect(getByText("My Files")).toBeInTheDocument();
  });

  it("shows 'New Folder' and 'New Document' buttons when permission is 'edit'", () => {
    const { getByText } = render(<HomePage />);
    expect(getByText("New Folder")).toBeInTheDocument();
    expect(getByText("New Document")).toBeInTheDocument();
  });

  it("hides create buttons when permission is 'view'", () => {
    mockFoldersState.currentFolderPermission = "view";
    const { queryByText } = render(<HomePage />);
    expect(queryByText("New Folder")).not.toBeInTheDocument();
    expect(queryByText("New Document")).not.toBeInTheDocument();
  });

  it("shows spinner when loading", () => {
    mockFoldersState.loading = true;
    const { container } = render(<HomePage />);
    const spinner = container.querySelector(".animate-spin");
    expect(spinner).toBeInTheDocument();
  });

  it("shows empty state when no folders/documents", () => {
    const { getByText } = render(<HomePage />);
    expect(
      getByText(
        "This folder is empty. Create a folder or document to get started!",
      ),
    ).toBeInTheDocument();
  });

  it("shows view-only empty state when permission is view", () => {
    mockFoldersState.currentFolderPermission = "view";
    const { getByText } = render(<HomePage />);
    expect(getByText("This folder is empty.")).toBeInTheDocument();
  });

  it("renders folder rows with folder name", () => {
    mockFoldersState.folders = [
      {
        id: "folder-1",
        name: "Test Folder",
        owner_id: "user-1",
        owner_name: "Test User",
        owner_email: "test@example.com",
        owner_avatar_url: null,
        parent_id: null,
        general_access: "restricted",
        is_deleted: false,
        deleted_at: null,
        created_at: "2025-01-01T00:00:00Z",
        updated_at: "2025-01-01T00:00:00Z",
      },
    ];
    const { getByText } = render(<HomePage />);
    expect(getByText("Test Folder")).toBeInTheDocument();
  });

  it("renders document rows with doc title", () => {
    mockFoldersState.documents = [
      {
        id: "doc-1",
        title: "My Document",
        content: "",
        owner_id: "user-1",
        owner_name: "Test User",
        owner_email: "test@example.com",
        owner_avatar_url: null,
        folder_id: null,
        general_access: "restricted",
        is_deleted: false,
        deleted_at: null,
        content_length: 0,
        created_at: "2025-01-01T00:00:00Z",
        updated_at: "2025-01-01T00:00:00Z",
      },
    ];
    const { getByText } = render(<HomePage />);
    expect(getByText("My Document")).toBeInTheDocument();
  });

  it("'New Document' button calls documentsApi.create and navigates to /edit/:id", async () => {
    const { getByText } = render(<HomePage />);
    fireEvent.click(getByText("New Document"));

    await waitFor(() => {
      expect(mockDocumentsApiCreate).toHaveBeenCalledWith({
        title: "Untitled",
        folder_id: null,
      });
    });

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith("/edit/doc-new-1");
    });
  });

  it("clicking a folder row calls navigateToFolder", () => {
    mockFoldersState.folders = [
      {
        id: "folder-1",
        name: "Test Folder",
        owner_id: "user-1",
        owner_name: "Test User",
        owner_email: "test@example.com",
        owner_avatar_url: null,
        parent_id: null,
        general_access: "restricted",
        is_deleted: false,
        deleted_at: null,
        created_at: "2025-01-01T00:00:00Z",
        updated_at: "2025-01-01T00:00:00Z",
      },
    ];
    const { getByText } = render(<HomePage />);
    fireEvent.click(getByText("Test Folder"));
    expect(mockNavigateToFolder).toHaveBeenCalledWith("folder-1");
  });

  it("clicking a document row navigates to /edit/:id", () => {
    mockFoldersState.documents = [
      {
        id: "doc-1",
        title: "My Document",
        content: "",
        owner_id: "user-1",
        owner_name: "Test User",
        owner_email: "test@example.com",
        owner_avatar_url: null,
        folder_id: null,
        general_access: "restricted",
        is_deleted: false,
        deleted_at: null,
        content_length: 0,
        created_at: "2025-01-01T00:00:00Z",
        updated_at: "2025-01-01T00:00:00Z",
      },
    ];
    const { getByText } = render(<HomePage />);
    fireEvent.click(getByText("My Document"));
    expect(mockNavigate).toHaveBeenCalledWith("/edit/doc-1");
  });

  it("fetches shared docs and folders when tab is 'shared'", async () => {
    const { getByText } = render(<HomePage />);
    fireEvent.click(getByText("Shared with me"));

    await waitFor(() => {
      expect(mockSharingApiListShared).toHaveBeenCalled();
      expect(mockFoldersApiListShared).toHaveBeenCalled();
    });
  });

  it("shows empty state when no shared items", async () => {
    const { getByText } = render(<HomePage />);
    fireEvent.click(getByText("Shared with me"));

    await waitFor(() => {
      expect(getByText("No items shared with you yet.")).toBeInTheDocument();
    });
  });

  it("fetches recently viewed items when tab is 'recent'", async () => {
    const { getByText } = render(<HomePage />);
    fireEvent.click(getByText("Recently viewed"));

    await waitFor(() => {
      expect(mockSharingApiListRecentlyViewed).toHaveBeenCalled();
      expect(mockFoldersApiListRecentlyViewed).toHaveBeenCalled();
    });
  });

  it("shows empty state when no recent items", async () => {
    const { getByText } = render(<HomePage />);
    fireEvent.click(getByText("Recently viewed"));

    await waitFor(() => {
      expect(
        getByText("No recently viewed items yet."),
      ).toBeInTheDocument();
    });
  });

  it("fetches trash when tab is 'trash'", async () => {
    const { getByText } = render(<HomePage />);
    fireEvent.click(getByText("Trash"));

    await waitFor(() => {
      expect(mockFetchTrash).toHaveBeenCalled();
      expect(mockFetchTrashFolders).toHaveBeenCalled();
    });
  });

  it("shows empty state when trash is empty", async () => {
    const { getByText } = render(<HomePage />);
    fireEvent.click(getByText("Trash"));

    await waitFor(() => {
      expect(getByText("Trash is empty.")).toBeInTheDocument();
    });
  });

  it("shows 'Empty Trash' button when trash has items", async () => {
    mockUseDocumentsState.trash = [
      {
        id: "doc-trash-1",
        title: "Trashed Doc",
        content: "",
        owner_id: "user-1",
        owner_name: "Test",
        owner_email: "test@example.com",
        owner_avatar_url: null,
        folder_id: null,
        general_access: "restricted",
        is_deleted: true,
        deleted_at: "2025-01-01T00:00:00Z",
        content_length: 0,
        created_at: "2025-01-01T00:00:00Z",
        updated_at: "2025-01-01T00:00:00Z",
      },
    ];

    const { getByText } = render(<HomePage />);
    fireEvent.click(getByText("Trash"));

    await waitFor(() => {
      expect(getByText("Empty Trash")).toBeInTheDocument();
    });
  });

  it("shows toast and navigates to root on accessError", async () => {
    mockFoldersState.accessError = "Access denied";

    render(<HomePage />);

    await waitFor(() => {
      expect(mockAddToast).toHaveBeenCalledWith("Access denied", "error");
      expect(mockClearAccessError).toHaveBeenCalled();
      expect(mockNavigateToFolder).toHaveBeenCalledWith(null);
    });
  });

  // --- Trash tab interactions ---
  it("clicking 'Empty Trash' button opens confirm dialog", async () => {
    mockUseDocumentsState.trash = [
      {
        id: "doc-trash-1",
        title: "Trashed Doc",
        content: "",
        owner_id: "user-1",
        owner_name: "Test",
        owner_email: "test@example.com",
        owner_avatar_url: null,
        folder_id: null,
        general_access: "restricted",
        is_deleted: true,
        deleted_at: "2025-01-01T00:00:00Z",
        content_length: 0,
        created_at: "2025-01-01T00:00:00Z",
        updated_at: "2025-01-01T00:00:00Z",
      },
    ];

    const { getByText, getByTestId } = render(<HomePage />);
    fireEvent.click(getByText("Trash"));

    await waitFor(() => {
      expect(getByText("Empty Trash")).toBeInTheDocument();
    });

    fireEvent.click(getByText("Empty Trash"));
    await waitFor(() => {
      expect(getByTestId("confirm-dialog")).toBeInTheDocument();
    });
  });

  it("confirming 'Empty Trash' calls hardDeleteDocument for each trashed doc and hardDeleteFolder for each trashed folder", async () => {
    const trashedDoc = {
      id: "doc-trash-1",
      title: "Trashed Doc",
      content: "",
      owner_id: "user-1",
      owner_name: "Test",
      owner_email: "test@example.com",
      owner_avatar_url: null,
      folder_id: null,
      general_access: "restricted",
      is_deleted: true,
      deleted_at: "2025-01-01T00:00:00Z",
      content_length: 0,
      created_at: "2025-01-01T00:00:00Z",
      updated_at: "2025-01-01T00:00:00Z",
    };
    const trashedFolder = {
      id: "folder-trash-1",
      name: "Trashed Folder",
      owner_id: "user-1",
      owner_name: "Test",
      owner_email: "test@example.com",
      owner_avatar_url: null,
      parent_id: null,
      general_access: "restricted",
      is_deleted: true,
      deleted_at: "2025-01-01T00:00:00Z",
      created_at: "2025-01-01T00:00:00Z",
      updated_at: "2025-01-01T00:00:00Z",
    };
    mockUseDocumentsState.trash = [trashedDoc];
    mockFoldersState.trashFolders = [trashedFolder];

    const { getByText, getByTestId } = render(<HomePage />);
    fireEvent.click(getByText("Trash"));

    await waitFor(() => {
      expect(getByText("Empty Trash")).toBeInTheDocument();
    });

    fireEvent.click(getByText("Empty Trash"));
    await waitFor(() => {
      expect(getByTestId("confirm-dialog")).toBeInTheDocument();
    });

    fireEvent.click(getByTestId("confirm-btn"));

    await waitFor(() => {
      expect(mockHardDeleteDocument).toHaveBeenCalledWith("doc-trash-1");
      expect(mockHardDeleteFolder).toHaveBeenCalledWith("folder-trash-1");
      expect(mockAddToast).toHaveBeenCalledWith("Trash emptied", "success");
    });
  });

  it("right-clicking a trashed document opens context menu with restore option", async () => {
    mockUseDocumentsState.trash = [
      {
        id: "doc-trash-1",
        title: "Trashed Doc",
        content: "",
        owner_id: "user-1",
        owner_name: "Test",
        owner_email: "test@example.com",
        owner_avatar_url: null,
        folder_id: null,
        general_access: "restricted",
        is_deleted: true,
        deleted_at: "2025-01-01T00:00:00Z",
        content_length: 0,
        created_at: "2025-01-01T00:00:00Z",
        updated_at: "2025-01-01T00:00:00Z",
      },
    ];

    const { getByText, getByTestId, getByRole } = render(<HomePage />);
    fireEvent.click(getByText("Trash"));

    await waitFor(() => {
      expect(getByText("Trashed Doc")).toBeInTheDocument();
    });

    fireEvent.contextMenu(getByText("Trashed Doc"));

    await waitFor(() => {
      expect(getByTestId("context-menu")).toBeInTheDocument();
      expect(getByRole("button", { name: "Restore" })).toBeInTheDocument();
    });
  });

  it("restoring a trashed document calls restoreDocument", async () => {
    mockUseDocumentsState.trash = [
      {
        id: "doc-trash-1",
        title: "Trashed Doc",
        content: "",
        owner_id: "user-1",
        owner_name: "Test",
        owner_email: "test@example.com",
        owner_avatar_url: null,
        folder_id: null,
        general_access: "restricted",
        is_deleted: true,
        deleted_at: "2025-01-01T00:00:00Z",
        content_length: 0,
        created_at: "2025-01-01T00:00:00Z",
        updated_at: "2025-01-01T00:00:00Z",
      },
    ];

    const { getByText, getByTestId, getByRole } = render(<HomePage />);
    fireEvent.click(getByText("Trash"));

    await waitFor(() => {
      expect(getByText("Trashed Doc")).toBeInTheDocument();
    });

    fireEvent.contextMenu(getByText("Trashed Doc"));
    await waitFor(() => {
      expect(getByTestId("context-menu")).toBeInTheDocument();
    });

    fireEvent.click(getByRole("button", { name: "Restore" }));

    await waitFor(() => {
      expect(mockRestoreDocument).toHaveBeenCalledWith("doc-trash-1");
      expect(mockAddToast).toHaveBeenCalledWith("Document restored", "success");
    });
  });

  it("restoring a trashed document failure shows error toast", async () => {
    mockRestoreDocument.mockRejectedValueOnce({
      response: { data: { detail: "Restore failed" } },
    });
    mockUseDocumentsState.trash = [
      {
        id: "doc-trash-1",
        title: "Trashed Doc",
        content: "",
        owner_id: "user-1",
        owner_name: "Test",
        owner_email: "test@example.com",
        owner_avatar_url: null,
        folder_id: null,
        general_access: "restricted",
        is_deleted: true,
        deleted_at: "2025-01-01T00:00:00Z",
        content_length: 0,
        created_at: "2025-01-01T00:00:00Z",
        updated_at: "2025-01-01T00:00:00Z",
      },
    ];

    const { getByText, getByRole } = render(<HomePage />);
    fireEvent.click(getByText("Trash"));
    await waitFor(() => expect(getByText("Trashed Doc")).toBeInTheDocument());
    fireEvent.contextMenu(getByText("Trashed Doc"));
    fireEvent.click(getByRole("button", { name: "Restore" }));

    await waitFor(() => {
      expect(mockAddToast).toHaveBeenCalledWith("Restore failed", "error");
    });
  });

  it("restoring a trashed folder calls restoreFolder", async () => {
    mockFoldersState.trashFolders = [
      {
        id: "folder-trash-1",
        name: "Trashed Folder",
        owner_id: "user-1",
        owner_name: "Test",
        owner_email: "test@example.com",
        owner_avatar_url: null,
        parent_id: null,
        general_access: "restricted",
        is_deleted: true,
        deleted_at: "2025-01-01T00:00:00Z",
        created_at: "2025-01-01T00:00:00Z",
        updated_at: "2025-01-01T00:00:00Z",
      },
    ];

    const { getByText, getByTestId, getByRole } = render(<HomePage />);
    fireEvent.click(getByText("Trash"));

    await waitFor(() => {
      expect(getByText("Trashed Folder")).toBeInTheDocument();
    });

    fireEvent.contextMenu(getByText("Trashed Folder"));
    await waitFor(() => {
      expect(getByTestId("context-menu")).toBeInTheDocument();
    });

    fireEvent.click(getByRole("button", { name: "Restore" }));

    await waitFor(() => {
      expect(mockRestoreFolder).toHaveBeenCalledWith("folder-trash-1");
      expect(mockAddToast).toHaveBeenCalledWith("Folder restored", "success");
    });
  });

  it("restoring a trashed folder failure shows error toast", async () => {
    mockRestoreFolder.mockRejectedValueOnce({
      response: { data: { detail: "Folder restore failed" } },
    });
    mockFoldersState.trashFolders = [
      {
        id: "folder-trash-1",
        name: "Trashed Folder",
        owner_id: "user-1",
        owner_name: "Test",
        owner_email: "test@example.com",
        owner_avatar_url: null,
        parent_id: null,
        general_access: "restricted",
        is_deleted: true,
        deleted_at: "2025-01-01T00:00:00Z",
        created_at: "2025-01-01T00:00:00Z",
        updated_at: "2025-01-01T00:00:00Z",
      },
    ];

    const { getByText, getByRole } = render(<HomePage />);
    fireEvent.click(getByText("Trash"));
    await waitFor(() => expect(getByText("Trashed Folder")).toBeInTheDocument());
    fireEvent.contextMenu(getByText("Trashed Folder"));
    fireEvent.click(getByRole("button", { name: "Restore" }));

    await waitFor(() => {
      expect(mockAddToast).toHaveBeenCalledWith("Folder restore failed", "error");
    });
  });

  // --- Shared tab interactions ---
  it("shared tab renders shared folders alongside shared docs", async () => {
    const sharedDoc = {
      id: "shared-doc-1",
      title: "Shared Doc",
      content: "",
      owner_id: "owner-1",
      permission: "edit" as const,
      last_accessed_at: "2025-01-01T00:00:00Z",
      created_at: "2025-01-01T00:00:00Z",
      updated_at: "2025-01-01T00:00:00Z",
    };
    const sharedFolder = {
      id: "shared-folder-1",
      name: "Shared Folder",
      owner_id: "owner-1",
      owner_name: "Owner",
      owner_email: "owner@example.com",
      permission: "view" as const,
      last_accessed_at: "2025-01-01T00:00:00Z",
      created_at: "2025-01-01T00:00:00Z",
      updated_at: "2025-01-01T00:00:00Z",
    };
    mockSharingApiListShared.mockResolvedValue({ data: [sharedDoc] });
    mockFoldersApiListShared.mockResolvedValue({ data: [sharedFolder] });

    const { getByText } = render(<HomePage />);
    fireEvent.click(getByText("Shared with me"));

    await waitFor(() => {
      expect(getByText("Shared Doc")).toBeInTheDocument();
      expect(getByText("Shared Folder")).toBeInTheDocument();
    });
  });

  it("clicking a shared document navigates to /edit/:id", async () => {
    const sharedDoc = {
      id: "shared-doc-1",
      title: "Shared Doc",
      content: "",
      owner_id: "owner-1",
      permission: "edit" as const,
      last_accessed_at: "2025-01-01T00:00:00Z",
      created_at: "2025-01-01T00:00:00Z",
      updated_at: "2025-01-01T00:00:00Z",
    };
    mockSharingApiListShared.mockResolvedValue({ data: [sharedDoc] });
    mockFoldersApiListShared.mockResolvedValue({ data: [] });

    const { getByText } = render(<HomePage />);
    fireEvent.click(getByText("Shared with me"));

    await waitFor(() => {
      expect(getByText("Shared Doc")).toBeInTheDocument();
    });

    fireEvent.click(getByText("Shared Doc"));
    expect(mockNavigate).toHaveBeenCalledWith("/edit/shared-doc-1");
  });

  it("clicking a shared folder navigates to its folder", async () => {
    const sharedFolder = {
      id: "shared-folder-1",
      name: "Shared Folder",
      owner_id: "owner-1",
      owner_name: "Owner",
      owner_email: "owner@example.com",
      permission: "view" as const,
      last_accessed_at: "2025-01-01T00:00:00Z",
      created_at: "2025-01-01T00:00:00Z",
      updated_at: "2025-01-01T00:00:00Z",
    };
    mockSharingApiListShared.mockResolvedValue({ data: [] });
    mockFoldersApiListShared.mockResolvedValue({ data: [sharedFolder] });

    const { getByText } = render(<HomePage />);
    fireEvent.click(getByText("Shared with me"));

    await waitFor(() => {
      expect(getByText("Shared Folder")).toBeInTheDocument();
    });

    fireEvent.click(getByText("Shared Folder"));
    expect(mockNavigateToFolder).toHaveBeenCalledWith("shared-folder-1");
  });

  // --- Recent tab interactions ---
  it("recent tab renders recently viewed docs and folders", async () => {
    const recentDoc = {
      id: "recent-doc-1",
      title: "Recent Doc",
      content: "",
      owner_id: "owner-1",
      owner_name: "Owner",
      permission: "edit" as const,
      viewed_at: "2025-01-01T00:00:00Z",
      created_at: "2025-01-01T00:00:00Z",
      updated_at: "2025-01-01T00:00:00Z",
    };
    const recentFolder = {
      id: "recent-folder-1",
      name: "Recent Folder",
      owner_id: "owner-1",
      owner_name: "Owner",
      owner_email: "owner@example.com",
      permission: "view" as const,
      viewed_at: "2025-01-01T00:00:00Z",
      created_at: "2025-01-01T00:00:00Z",
      updated_at: "2025-01-01T00:00:00Z",
    };
    mockSharingApiListRecentlyViewed.mockResolvedValue({ data: [recentDoc] });
    mockFoldersApiListRecentlyViewed.mockResolvedValue({ data: [recentFolder] });

    const { getByText } = render(<HomePage />);
    fireEvent.click(getByText("Recently viewed"));

    await waitFor(() => {
      expect(getByText("Recent Doc")).toBeInTheDocument();
      expect(getByText("Recent Folder")).toBeInTheDocument();
    });
  });

  it("clicking a recent document navigates to /edit/:id", async () => {
    const recentDoc = {
      id: "recent-doc-1",
      title: "Recent Doc",
      content: "",
      owner_id: "owner-1",
      owner_name: "Owner",
      permission: "edit" as const,
      viewed_at: "2025-01-01T00:00:00Z",
      created_at: "2025-01-01T00:00:00Z",
      updated_at: "2025-01-01T00:00:00Z",
    };
    mockSharingApiListRecentlyViewed.mockResolvedValue({ data: [recentDoc] });
    mockFoldersApiListRecentlyViewed.mockResolvedValue({ data: [] });

    const { getByText } = render(<HomePage />);
    fireEvent.click(getByText("Recently viewed"));

    await waitFor(() => {
      expect(getByText("Recent Doc")).toBeInTheDocument();
    });

    fireEvent.click(getByText("Recent Doc"));
    expect(mockNavigate).toHaveBeenCalledWith("/edit/recent-doc-1");
  });

  it("three-dot menu button on recent folder opens context menu", async () => {
    const recentFolder = {
      id: "recent-folder-1",
      name: "Recent Folder",
      owner_id: "owner-1",
      owner_name: "Owner",
      owner_email: "owner@example.com",
      permission: "view" as const,
      viewed_at: "2025-01-01T00:00:00Z",
      created_at: "2025-01-01T00:00:00Z",
      updated_at: "2025-01-01T00:00:00Z",
    };
    mockSharingApiListRecentlyViewed.mockResolvedValue({ data: [] });
    mockFoldersApiListRecentlyViewed.mockResolvedValue({ data: [recentFolder] });

    const { getByText, getByTestId, getAllByRole } = render(<HomePage />);
    fireEvent.click(getByText("Recently viewed"));
    await waitFor(() => expect(getByText("Recent Folder")).toBeInTheDocument());
    const moreButtons = getAllByRole("button", { name: "More actions" });
    fireEvent.click(moreButtons[0]);
    expect(getByTestId("context-menu")).toBeInTheDocument();
  });

  it("three-dot menu button on recent document opens context menu", async () => {
    const recentDoc = {
      id: "recent-doc-1",
      title: "Recent Doc",
      content: "",
      owner_id: "owner-1",
      owner_name: "Owner",
      owner_email: "owner@example.com",
      permission: "edit" as const,
      viewed_at: "2025-01-01T00:00:00Z",
      created_at: "2025-01-01T00:00:00Z",
      updated_at: "2025-01-01T00:00:00Z",
    };
    mockSharingApiListRecentlyViewed.mockResolvedValue({ data: [recentDoc] });
    mockFoldersApiListRecentlyViewed.mockResolvedValue({ data: [] });

    const { getByText, getByTestId, getAllByRole } = render(<HomePage />);
    fireEvent.click(getByText("Recently viewed"));
    await waitFor(() => expect(getByText("Recent Doc")).toBeInTheDocument());
    const moreButtons = getAllByRole("button", { name: "More actions" });
    fireEvent.click(moreButtons[0]);
    expect(getByTestId("context-menu")).toBeInTheDocument();
  });

  it("clicking a recent folder navigates to its folder", async () => {
    const recentFolder = {
      id: "recent-folder-1",
      name: "Recent Folder",
      owner_id: "owner-1",
      owner_name: "Owner",
      owner_email: "owner@example.com",
      permission: "view" as const,
      viewed_at: "2025-01-01T00:00:00Z",
      created_at: "2025-01-01T00:00:00Z",
      updated_at: "2025-01-01T00:00:00Z",
    };
    mockSharingApiListRecentlyViewed.mockResolvedValue({ data: [] });
    mockFoldersApiListRecentlyViewed.mockResolvedValue({ data: [recentFolder] });

    const { getByText } = render(<HomePage />);
    fireEvent.click(getByText("Recently viewed"));

    await waitFor(() => {
      expect(getByText("Recent Folder")).toBeInTheDocument();
    });

    fireEvent.click(getByText("Recent Folder"));
    expect(mockNavigateToFolder).toHaveBeenCalledWith("recent-folder-1");
  });

  // --- Context menu / three-dot menu ---
  it("three-dot menu button on trashed folder opens context menu", async () => {
    mockFoldersState.trashFolders = [
      {
        id: "folder-trash-1",
        name: "Trashed Folder",
        owner_id: "user-1",
        owner_name: "Test",
        owner_email: "test@example.com",
        owner_avatar_url: null,
        parent_id: null,
        general_access: "restricted",
        is_deleted: true,
        deleted_at: null,
        created_at: "2025-01-01T00:00:00Z",
        updated_at: "2025-01-01T00:00:00Z",
      },
    ];

    const { getByText, getByTestId, getAllByRole } = render(<HomePage />);
    fireEvent.click(getByText("Trash"));
    await waitFor(() => expect(getByText("Trashed Folder")).toBeInTheDocument());
    const moreButtons = getAllByRole("button", { name: "More actions" });
    fireEvent.click(moreButtons[0]);
    expect(getByTestId("context-menu")).toBeInTheDocument();
  });

  it("three-dot menu button on trashed document opens context menu", async () => {
    mockUseDocumentsState.trash = [
      {
        id: "doc-trash-1",
        title: "Trashed Doc",
        content: "",
        owner_id: "user-1",
        owner_name: "Test",
        owner_email: "test@example.com",
        owner_avatar_url: null,
        folder_id: null,
        general_access: "restricted",
        is_deleted: true,
        deleted_at: null,
        content_length: 0,
        created_at: "2025-01-01T00:00:00Z",
        updated_at: "2025-01-01T00:00:00Z",
      },
    ];

    const { getByText, getByTestId, getAllByRole } = render(<HomePage />);
    fireEvent.click(getByText("Trash"));
    await waitFor(() => expect(getByText("Trashed Doc")).toBeInTheDocument());
    const moreButtons = getAllByRole("button", { name: "More actions" });
    fireEvent.click(moreButtons[0]);
    expect(getByTestId("context-menu")).toBeInTheDocument();
  });

  it("three-dot menu button on document opens context menu", () => {
    mockFoldersState.documents = [
      {
        id: "doc-1",
        title: "My Document",
        content: "",
        owner_id: "user-1",
        owner_name: "Test User",
        owner_email: "test@example.com",
        owner_avatar_url: null,
        folder_id: null,
        general_access: "restricted",
        is_deleted: false,
        deleted_at: null,
        content_length: 0,
        created_at: "2025-01-01T00:00:00Z",
        updated_at: "2025-01-01T00:00:00Z",
      },
    ];

    const { getByTestId, getAllByRole } = render(<HomePage />);
    const moreButtons = getAllByRole("button", { name: "More actions" });
    fireEvent.click(moreButtons[0]);
    expect(getByTestId("context-menu")).toBeInTheDocument();
  });

  it("right-clicking a document opens context menu", () => {
    mockFoldersState.documents = [
      {
        id: "doc-1",
        title: "My Document",
        content: "",
        owner_id: "user-1",
        owner_name: "Test User",
        owner_email: "test@example.com",
        owner_avatar_url: null,
        folder_id: null,
        general_access: "restricted",
        is_deleted: false,
        deleted_at: null,
        content_length: 0,
        created_at: "2025-01-01T00:00:00Z",
        updated_at: "2025-01-01T00:00:00Z",
      },
    ];

    const { getByText, getByTestId } = render(<HomePage />);
    fireEvent.contextMenu(getByText("My Document"));

    expect(getByTestId("context-menu")).toBeInTheDocument();
  });

  it("right-clicking a folder opens context menu", () => {
    mockFoldersState.folders = [
      {
        id: "folder-1",
        name: "Test Folder",
        owner_id: "user-1",
        owner_name: "Test User",
        owner_email: "test@example.com",
        owner_avatar_url: null,
        parent_id: null,
        general_access: "restricted",
        is_deleted: false,
        deleted_at: null,
        created_at: "2025-01-01T00:00:00Z",
        updated_at: "2025-01-01T00:00:00Z",
      },
    ];

    const { getByText, getByTestId } = render(<HomePage />);
    fireEvent.contextMenu(getByText("Test Folder"));

    expect(getByTestId("context-menu")).toBeInTheDocument();
  });

  // --- New Folder creation ---
  it("'New Folder' button opens CreateFolderDialog", () => {
    const { getByText, getByTestId } = render(<HomePage />);
    fireEvent.click(getByText("New Folder"));
    expect(getByTestId("create-folder-dialog")).toBeInTheDocument();
  });

  it("CreateFolderDialog cancel closes without creating", () => {
    const { getByText, getByTestId } = render(<HomePage />);
    fireEvent.click(getByText("New Folder"));
    expect(getByTestId("create-folder-dialog")).toBeInTheDocument();
    fireEvent.click(getByTestId("create-folder-cancel"));
    expect(screen.queryByTestId("create-folder-dialog")).not.toBeInTheDocument();
    expect(mockCreateFolder).not.toHaveBeenCalled();
  });

  it("creating a folder calls createFolder", async () => {
    const { getByText, getByTestId } = render(<HomePage />);
    fireEvent.click(getByText("New Folder"));

    await waitFor(() => {
      expect(getByTestId("create-folder-dialog")).toBeInTheDocument();
    });

    fireEvent.click(getByTestId("create-folder-submit"));

    await waitFor(() => {
      expect(mockCreateFolder).toHaveBeenCalledWith("New Folder Name");
      expect(mockAddToast).toHaveBeenCalledWith("Folder created", "success");
    });
  });

  // --- Error handling ---
  it("new document creation failure shows error toast", async () => {
    mockDocumentsApiCreate.mockRejectedValueOnce({
      response: { data: { detail: "Server error" } },
    });

    const { getByText } = render(<HomePage />);
    fireEvent.click(getByText("New Document"));

    await waitFor(() => {
      expect(mockAddToast).toHaveBeenCalledWith("Server error", "error");
    });
  });

  it("new document creation failure shows fallback when no detail", async () => {
    mockDocumentsApiCreate.mockRejectedValueOnce(new Error("Network error"));

    const { getByText } = render(<HomePage />);
    fireEvent.click(getByText("New Document"));

    await waitFor(() => {
      expect(mockAddToast).toHaveBeenCalledWith(
        "Failed to create document. Please try again.",
        "error",
      );
    });
  });

  it("create folder failure shows fallback when no detail", async () => {
    mockCreateFolder.mockRejectedValueOnce(new Error("Network error"));

    const { getByText, getByTestId } = render(<HomePage />);
    fireEvent.click(getByText("New Folder"));
    await waitFor(() => expect(getByTestId("create-folder-dialog")).toBeInTheDocument());
    fireEvent.click(getByTestId("create-folder-submit"));

    await waitFor(() => {
      expect(mockAddToast).toHaveBeenCalledWith(
        "Failed to create folder. Please try again.",
        "error",
      );
    });
  });

  it("create folder failure shows error toast", async () => {
    mockCreateFolder.mockRejectedValueOnce({
      response: { data: { detail: "Folder creation failed" } },
    });

    const { getByText, getByTestId } = render(<HomePage />);
    fireEvent.click(getByText("New Folder"));
    await waitFor(() => expect(getByTestId("create-folder-dialog")).toBeInTheDocument());
    fireEvent.click(getByTestId("create-folder-submit"));

    await waitFor(() => {
      expect(mockAddToast).toHaveBeenCalledWith("Folder creation failed", "error");
    });
  });

  // --- Rename flow ---
  it("renaming a document via context menu calls renameDocument", async () => {
    mockFoldersState.documents = [
      {
        id: "doc-1",
        title: "My Document",
        content: "",
        owner_id: "user-1",
        owner_name: "Test User",
        owner_email: "test@example.com",
        owner_avatar_url: null,
        folder_id: null,
        general_access: "restricted",
        is_deleted: false,
        deleted_at: null,
        content_length: 0,
        created_at: "2025-01-01T00:00:00Z",
        updated_at: "2025-01-01T00:00:00Z",
      },
    ];

    const { getByText, getByTestId, getByRole } = render(<HomePage />);
    fireEvent.contextMenu(getByText("My Document"));
    fireEvent.click(getByRole("button", { name: "Rename" }));

    await waitFor(() => expect(getByTestId("rename-dialog")).toBeInTheDocument());
    fireEvent.click(getByTestId("rename-save"));

    await waitFor(() => {
      expect(mockRenameDocument).toHaveBeenCalledWith("doc-1", "New Name");
      expect(mockFetchContents).toHaveBeenCalledWith(null);
      expect(mockAddToast).toHaveBeenCalledWith("Renamed successfully", "success");
    });
  });

  it("renaming a folder via context menu calls renameFolder", async () => {
    mockFoldersState.folders = [
      {
        id: "folder-1",
        name: "Test Folder",
        owner_id: "user-1",
        owner_name: "Test User",
        owner_email: "test@example.com",
        owner_avatar_url: null,
        parent_id: null,
        general_access: "restricted",
        is_deleted: false,
        deleted_at: null,
        created_at: "2025-01-01T00:00:00Z",
        updated_at: "2025-01-01T00:00:00Z",
      },
    ];

    const { getByText, getByTestId, getByRole } = render(<HomePage />);
    fireEvent.contextMenu(getByText("Test Folder"));
    fireEvent.click(getByRole("button", { name: "Rename" }));

    await waitFor(() => expect(getByTestId("rename-dialog")).toBeInTheDocument());
    fireEvent.click(getByTestId("rename-save"));

    await waitFor(() => {
      expect(mockRenameFolder).toHaveBeenCalledWith("folder-1", "New Name");
      expect(mockAddToast).toHaveBeenCalledWith("Renamed successfully", "success");
    });
  });

  it("rename folder failure shows error toast", async () => {
    mockRenameFolder.mockRejectedValueOnce({
      response: { data: { detail: "Folder rename failed" } },
    });
    mockFoldersState.folders = [
      {
        id: "folder-1",
        name: "Test Folder",
        owner_id: "user-1",
        owner_name: "Test User",
        owner_email: "test@example.com",
        owner_avatar_url: null,
        parent_id: null,
        general_access: "restricted",
        is_deleted: false,
        deleted_at: null,
        created_at: "2025-01-01T00:00:00Z",
        updated_at: "2025-01-01T00:00:00Z",
      },
    ];

    const { getByText, getByTestId, getByRole } = render(<HomePage />);
    fireEvent.contextMenu(getByText("Test Folder"));
    fireEvent.click(getByRole("button", { name: "Rename" }));
    await waitFor(() => expect(getByTestId("rename-dialog")).toBeInTheDocument());
    fireEvent.click(getByTestId("rename-save"));

    await waitFor(() => {
      expect(mockAddToast).toHaveBeenCalledWith("Folder rename failed", "error");
    });
  });

  it("rename document failure shows fallback when no detail", async () => {
    mockRenameDocument.mockRejectedValueOnce(new Error("Network error"));
    mockFoldersState.documents = [
      {
        id: "doc-1",
        title: "My Document",
        content: "",
        owner_id: "user-1",
        owner_name: "Test User",
        owner_email: "test@example.com",
        owner_avatar_url: null,
        folder_id: null,
        general_access: "restricted",
        is_deleted: false,
        deleted_at: null,
        content_length: 0,
        created_at: "2025-01-01T00:00:00Z",
        updated_at: "2025-01-01T00:00:00Z",
      },
    ];

    const { getByText, getByTestId, getByRole } = render(<HomePage />);
    fireEvent.contextMenu(getByText("My Document"));
    fireEvent.click(getByRole("button", { name: "Rename" }));
    await waitFor(() => expect(getByTestId("rename-dialog")).toBeInTheDocument());
    fireEvent.click(getByTestId("rename-save"));

    await waitFor(() => {
      expect(mockAddToast).toHaveBeenCalledWith("Failed to rename.", "error");
    });
  });

  it("RenameDialog cancel closes without saving", async () => {
    mockFoldersState.documents = [
      {
        id: "doc-1",
        title: "My Document",
        content: "",
        owner_id: "user-1",
        owner_name: "Test User",
        owner_email: "test@example.com",
        owner_avatar_url: null,
        folder_id: null,
        general_access: "restricted",
        is_deleted: false,
        deleted_at: null,
        content_length: 0,
        created_at: "2025-01-01T00:00:00Z",
        updated_at: "2025-01-01T00:00:00Z",
      },
    ];

    const { getByText, getByTestId, getByRole } = render(<HomePage />);
    fireEvent.contextMenu(getByText("My Document"));
    fireEvent.click(getByRole("button", { name: "Rename" }));
    await waitFor(() => expect(getByTestId("rename-dialog")).toBeInTheDocument());
    fireEvent.click(getByTestId("rename-cancel"));
    await waitFor(() => {
      expect(screen.queryByTestId("rename-dialog")).not.toBeInTheDocument();
      expect(mockRenameDocument).not.toHaveBeenCalled();
    });
  });

  it("rename document failure shows error toast", async () => {
    mockRenameDocument.mockRejectedValueOnce({
      response: { data: { detail: "Rename failed" } },
    });
    mockFoldersState.documents = [
      {
        id: "doc-1",
        title: "My Document",
        content: "",
        owner_id: "user-1",
        owner_name: "Test User",
        owner_email: "test@example.com",
        owner_avatar_url: null,
        folder_id: null,
        general_access: "restricted",
        is_deleted: false,
        deleted_at: null,
        content_length: 0,
        created_at: "2025-01-01T00:00:00Z",
        updated_at: "2025-01-01T00:00:00Z",
      },
    ];

    const { getByText, getByTestId, getByRole } = render(<HomePage />);
    fireEvent.contextMenu(getByText("My Document"));
    fireEvent.click(getByRole("button", { name: "Rename" }));
    await waitFor(() => expect(getByTestId("rename-dialog")).toBeInTheDocument());
    fireEvent.click(getByTestId("rename-save"));

    await waitFor(() => {
      expect(mockAddToast).toHaveBeenCalledWith("Rename failed", "error");
    });
  });

  // --- Share flow ---
  it("share document onGeneralAccessChange updates state", async () => {
    mockFoldersState.documents = [
      {
        id: "doc-1",
        title: "My Document",
        content: "",
        owner_id: "user-1",
        owner_name: "Test User",
        owner_email: "test@example.com",
        owner_avatar_url: null,
        folder_id: null,
        general_access: "restricted",
        is_deleted: false,
        deleted_at: null,
        content_length: 0,
        created_at: "2025-01-01T00:00:00Z",
        updated_at: "2025-01-01T00:00:00Z",
      },
    ];

    const { getByText, getByTestId, getByRole } = render(<HomePage />);
    fireEvent.contextMenu(getByText("My Document"));
    fireEvent.click(getByRole("button", { name: "Share" }));
    await waitFor(() => expect(getByTestId("share-dialog")).toBeInTheDocument());
    fireEvent.click(getByTestId("share-dialog-change-access"));
    fireEvent.click(getByTestId("share-dialog-close"));
  });

  it("share document via context menu opens ShareDialog and can close", async () => {
    mockFoldersState.documents = [
      {
        id: "doc-1",
        title: "My Document",
        content: "",
        owner_id: "user-1",
        owner_name: "Test User",
        owner_email: "test@example.com",
        owner_avatar_url: null,
        folder_id: null,
        general_access: "restricted",
        is_deleted: false,
        deleted_at: null,
        content_length: 0,
        created_at: "2025-01-01T00:00:00Z",
        updated_at: "2025-01-01T00:00:00Z",
      },
    ];

    const { getByText, getByTestId, getByRole } = render(<HomePage />);
    fireEvent.contextMenu(getByText("My Document"));
    fireEvent.click(getByRole("button", { name: "Share" }));

    await waitFor(() => expect(getByTestId("share-dialog")).toBeInTheDocument());
    fireEvent.click(getByTestId("share-dialog-close"));
    await waitFor(() => expect(screen.queryByTestId("share-dialog")).not.toBeInTheDocument());
  });

  it("share folder onGeneralAccessChange updates state", async () => {
    mockFoldersState.folders = [
      {
        id: "folder-1",
        name: "Test Folder",
        owner_id: "user-1",
        owner_name: "Test User",
        owner_email: "test@example.com",
        owner_avatar_url: null,
        parent_id: null,
        general_access: "restricted",
        is_deleted: false,
        deleted_at: null,
        created_at: "2025-01-01T00:00:00Z",
        updated_at: "2025-01-01T00:00:00Z",
      },
    ];

    const { getByText, getByTestId, getByRole } = render(<HomePage />);
    fireEvent.contextMenu(getByText("Test Folder"));
    fireEvent.click(getByRole("button", { name: "Share" }));
    await waitFor(() => expect(getByTestId("folder-share-dialog")).toBeInTheDocument());
    fireEvent.click(getByTestId("folder-share-change-access"));
    fireEvent.click(getByTestId("folder-share-close"));
  });

  it("share folder via context menu opens FolderShareDialog and can close", async () => {
    mockFoldersState.folders = [
      {
        id: "folder-1",
        name: "Test Folder",
        owner_id: "user-1",
        owner_name: "Test User",
        owner_email: "test@example.com",
        owner_avatar_url: null,
        parent_id: null,
        general_access: "restricted",
        is_deleted: false,
        deleted_at: null,
        created_at: "2025-01-01T00:00:00Z",
        updated_at: "2025-01-01T00:00:00Z",
      },
    ];

    const { getByText, getByTestId, getByRole } = render(<HomePage />);
    fireEvent.contextMenu(getByText("Test Folder"));
    fireEvent.click(getByRole("button", { name: "Share" }));

    await waitFor(() => expect(getByTestId("folder-share-dialog")).toBeInTheDocument());
    fireEvent.click(getByTestId("folder-share-close"));
    await waitFor(() => expect(screen.queryByTestId("folder-share-dialog")).not.toBeInTheDocument());
  });

  // --- Info modal ---
  it("document info via context menu opens DocumentInfoModal and can close", async () => {
    mockFoldersState.documents = [
      {
        id: "doc-1",
        title: "My Document",
        content: "",
        owner_id: "user-1",
        owner_name: "Test User",
        owner_email: "test@example.com",
        owner_avatar_url: null,
        folder_id: null,
        general_access: "restricted",
        is_deleted: false,
        deleted_at: null,
        content_length: 0,
        created_at: "2025-01-01T00:00:00Z",
        updated_at: "2025-01-01T00:00:00Z",
      },
    ];

    const { getByText, getByTestId, getByRole } = render(<HomePage />);
    fireEvent.contextMenu(getByText("My Document"));
    fireEvent.click(getByRole("button", { name: "Info" }));

    await waitFor(() => expect(getByTestId("doc-info-modal")).toBeInTheDocument());
    fireEvent.click(getByTestId("doc-info-close"));
    await waitFor(() => expect(screen.queryByTestId("doc-info-modal")).not.toBeInTheDocument());
  });

  it("folder info via context menu opens FolderInfoModal and can close", async () => {
    mockFoldersState.folders = [
      {
        id: "folder-1",
        name: "Test Folder",
        owner_id: "user-1",
        owner_name: "Test User",
        owner_email: "test@example.com",
        owner_avatar_url: null,
        parent_id: null,
        general_access: "restricted",
        is_deleted: false,
        deleted_at: null,
        created_at: "2025-01-01T00:00:00Z",
        updated_at: "2025-01-01T00:00:00Z",
      },
    ];

    const { getByText, getByTestId, getByRole } = render(<HomePage />);
    fireEvent.contextMenu(getByText("Test Folder"));
    fireEvent.click(getByRole("button", { name: "Info" }));

    await waitFor(() => expect(getByTestId("folder-info-modal")).toBeInTheDocument());
    fireEvent.click(getByTestId("folder-info-close"));
    await waitFor(() => expect(screen.queryByTestId("folder-info-modal")).not.toBeInTheDocument());
  });

  // --- Move to Trash ---
  it("move document to trash via context menu", async () => {
    mockFoldersState.documents = [
      {
        id: "doc-1",
        title: "My Document",
        content: "",
        owner_id: "user-1",
        owner_name: "Test User",
        owner_email: "test@example.com",
        owner_avatar_url: null,
        folder_id: null,
        general_access: "restricted",
        is_deleted: false,
        deleted_at: null,
        content_length: 0,
        created_at: "2025-01-01T00:00:00Z",
        updated_at: "2025-01-01T00:00:00Z",
      },
    ];

    const { getByText, getByTestId, getByRole } = render(<HomePage />);
    fireEvent.contextMenu(getByText("My Document"));
    fireEvent.click(getByRole("button", { name: "Move to Trash" }));

    await waitFor(() => expect(getByTestId("confirm-dialog")).toBeInTheDocument());
    fireEvent.click(getByTestId("confirm-btn"));

    await waitFor(() => {
      expect(mockDeleteDocument).toHaveBeenCalledWith("doc-1");
      expect(mockFetchContents).toHaveBeenCalledWith(null);
      expect(mockAddToast).toHaveBeenCalledWith("Document moved to trash", "success");
    });
  });

  it("move document to trash failure shows error toast", async () => {
    mockDeleteDocument.mockRejectedValueOnce({
      response: { data: { detail: "Delete failed" } },
    });
    mockFoldersState.documents = [
      {
        id: "doc-1",
        title: "My Document",
        content: "",
        owner_id: "user-1",
        owner_name: "Test User",
        owner_email: "test@example.com",
        owner_avatar_url: null,
        folder_id: null,
        general_access: "restricted",
        is_deleted: false,
        deleted_at: null,
        content_length: 0,
        created_at: "2025-01-01T00:00:00Z",
        updated_at: "2025-01-01T00:00:00Z",
      },
    ];

    const { getByText, getByTestId, getByRole } = render(<HomePage />);
    fireEvent.contextMenu(getByText("My Document"));
    fireEvent.click(getByRole("button", { name: "Move to Trash" }));
    await waitFor(() => expect(getByTestId("confirm-dialog")).toBeInTheDocument());
    fireEvent.click(getByTestId("confirm-btn"));

    await waitFor(() => {
      expect(mockAddToast).toHaveBeenCalledWith("Delete failed", "error");
    });
  });

  it("move folder to trash failure shows error toast", async () => {
    mockSoftDeleteFolder.mockRejectedValueOnce({
      response: { data: { detail: "Folder delete failed" } },
    });
    mockFoldersState.folders = [
      {
        id: "folder-1",
        name: "Test Folder",
        owner_id: "user-1",
        owner_name: "Test User",
        owner_email: "test@example.com",
        owner_avatar_url: null,
        parent_id: null,
        general_access: "restricted",
        is_deleted: false,
        deleted_at: null,
        created_at: "2025-01-01T00:00:00Z",
        updated_at: "2025-01-01T00:00:00Z",
      },
    ];

    const { getByText, getByTestId, getByRole } = render(<HomePage />);
    fireEvent.contextMenu(getByText("Test Folder"));
    fireEvent.click(getByRole("button", { name: "Move to Trash" }));
    await waitFor(() => expect(getByTestId("confirm-dialog")).toBeInTheDocument());
    fireEvent.click(getByTestId("confirm-btn"));

    await waitFor(() => {
      expect(mockAddToast).toHaveBeenCalledWith("Folder delete failed", "error");
    });
  });

  it("move folder to trash via context menu", async () => {
    mockFoldersState.folders = [
      {
        id: "folder-1",
        name: "Test Folder",
        owner_id: "user-1",
        owner_name: "Test User",
        owner_email: "test@example.com",
        owner_avatar_url: null,
        parent_id: null,
        general_access: "restricted",
        is_deleted: false,
        deleted_at: null,
        created_at: "2025-01-01T00:00:00Z",
        updated_at: "2025-01-01T00:00:00Z",
      },
    ];

    const { getByText, getByTestId, getByRole } = render(<HomePage />);
    fireEvent.contextMenu(getByText("Test Folder"));
    fireEvent.click(getByRole("button", { name: "Move to Trash" }));

    await waitFor(() => expect(getByTestId("confirm-dialog")).toBeInTheDocument());
    fireEvent.click(getByTestId("confirm-btn"));

    await waitFor(() => {
      expect(mockSoftDeleteFolder).toHaveBeenCalledWith("folder-1");
      expect(mockAddToast).toHaveBeenCalledWith("Folder moved to trash", "success");
    });
  });

  // --- Delete permanently from trash ---
  it("delete document permanently from trash", async () => {
    mockUseDocumentsState.trash = [
      {
        id: "doc-trash-1",
        title: "Trashed Doc",
        content: "",
        owner_id: "user-1",
        owner_name: "Test",
        owner_email: "test@example.com",
        owner_avatar_url: null,
        folder_id: null,
        general_access: "restricted",
        is_deleted: true,
        deleted_at: "2025-01-01T00:00:00Z",
        content_length: 0,
        created_at: "2025-01-01T00:00:00Z",
        updated_at: "2025-01-01T00:00:00Z",
      },
    ];

    const { getByText, getByTestId, getByRole } = render(<HomePage />);
    fireEvent.click(getByText("Trash"));
    await waitFor(() => expect(getByText("Trashed Doc")).toBeInTheDocument());
    fireEvent.contextMenu(getByText("Trashed Doc"));
    fireEvent.click(getByRole("button", { name: "Delete permanently" }));

    await waitFor(() => expect(getByTestId("confirm-dialog")).toBeInTheDocument());
    fireEvent.click(getByTestId("confirm-btn"));

    await waitFor(() => {
      expect(mockHardDeleteDocument).toHaveBeenCalledWith("doc-trash-1");
      expect(mockAddToast).toHaveBeenCalledWith("Document deleted permanently", "success");
    });
  });

  it("empty trash failure shows error toast", async () => {
    mockHardDeleteDocument.mockRejectedValueOnce({
      response: { data: { detail: "Empty trash failed" } },
    });
    mockUseDocumentsState.trash = [
      {
        id: "doc-trash-1",
        title: "Trashed Doc",
        content: "",
        owner_id: "user-1",
        owner_name: "Test",
        owner_email: "test@example.com",
        owner_avatar_url: null,
        folder_id: null,
        general_access: "restricted",
        is_deleted: true,
        deleted_at: "2025-01-01T00:00:00Z",
        content_length: 0,
        created_at: "2025-01-01T00:00:00Z",
        updated_at: "2025-01-01T00:00:00Z",
      },
    ];

    const { getByText, getByTestId } = render(<HomePage />);
    fireEvent.click(getByText("Trash"));
    fireEvent.click(getByText("Empty Trash"));
    await waitFor(() => expect(getByTestId("confirm-dialog")).toBeInTheDocument());
    fireEvent.click(getByTestId("confirm-btn"));

    await waitFor(() => {
      expect(mockAddToast).toHaveBeenCalledWith("Empty trash failed", "error");
    });
  });

  it("delete folder permanently from trash", async () => {
    mockFoldersState.trashFolders = [
      {
        id: "folder-trash-1",
        name: "Trashed Folder",
        owner_id: "user-1",
        owner_name: "Test",
        owner_email: "test@example.com",
        owner_avatar_url: null,
        parent_id: null,
        general_access: "restricted",
        is_deleted: true,
        deleted_at: "2025-01-01T00:00:00Z",
        created_at: "2025-01-01T00:00:00Z",
        updated_at: "2025-01-01T00:00:00Z",
      },
    ];

    const { getByText, getByTestId, getByRole } = render(<HomePage />);
    fireEvent.click(getByText("Trash"));
    await waitFor(() => expect(getByText("Trashed Folder")).toBeInTheDocument());
    fireEvent.contextMenu(getByText("Trashed Folder"));
    fireEvent.click(getByRole("button", { name: "Delete permanently" }));

    await waitFor(() => expect(getByTestId("confirm-dialog")).toBeInTheDocument());
    fireEvent.click(getByTestId("confirm-btn"));

    await waitFor(() => {
      expect(mockHardDeleteFolder).toHaveBeenCalledWith("folder-trash-1");
      expect(mockAddToast).toHaveBeenCalledWith("Folder deleted permanently", "success");
    });
  });

  it("delete folder permanently failure shows error toast", async () => {
    mockHardDeleteFolder.mockRejectedValueOnce({
      response: { data: { detail: "Folder permanent delete failed" } },
    });
    mockFoldersState.trashFolders = [
      {
        id: "folder-trash-1",
        name: "Trashed Folder",
        owner_id: "user-1",
        owner_name: "Test",
        owner_email: "test@example.com",
        owner_avatar_url: null,
        parent_id: null,
        general_access: "restricted",
        is_deleted: true,
        deleted_at: "2025-01-01T00:00:00Z",
        created_at: "2025-01-01T00:00:00Z",
        updated_at: "2025-01-01T00:00:00Z",
      },
    ];

    const { getByText, getByTestId, getByRole } = render(<HomePage />);
    fireEvent.click(getByText("Trash"));
    fireEvent.contextMenu(getByText("Trashed Folder"));
    fireEvent.click(getByRole("button", { name: "Delete permanently" }));
    await waitFor(() => expect(getByTestId("confirm-dialog")).toBeInTheDocument());
    fireEvent.click(getByTestId("confirm-btn"));

    await waitFor(() => {
      expect(mockAddToast).toHaveBeenCalledWith("Folder permanent delete failed", "error");
    });
  });

  // --- Breadcrumbs ---
  it("shows folder name as heading when in a folder", () => {
    mockFoldersState.breadcrumbs = [
      { id: "root", name: "My Files" },
      { id: "folder-1", name: "Subfolder" },
    ];
    mockFoldersState.currentFolderId = "folder-1";

    const { getByRole } = render(<HomePage />);
    expect(getByRole("heading", { name: "Subfolder" })).toBeInTheDocument();
  });

  it("breadcrumb navigation calls navigateToFolder", () => {
    mockFoldersState.breadcrumbs = [{ id: "folder-1", name: "Subfolder" }];
    mockFoldersState.currentFolderId = "folder-1";

    const { getByTestId } = render(<HomePage />);
    fireEvent.click(getByTestId("breadcrumb-home"));
    expect(mockNavigateToFolder).toHaveBeenCalledWith(null);
  });

  // --- Confirm cancel ---
  it("confirm dialog cancel closes without executing", async () => {
    mockUseDocumentsState.trash = [
      {
        id: "doc-trash-1",
        title: "Trashed Doc",
        content: "",
        owner_id: "user-1",
        owner_name: "Test",
        owner_email: "test@example.com",
        owner_avatar_url: null,
        folder_id: null,
        general_access: "restricted",
        is_deleted: true,
        deleted_at: "2025-01-01T00:00:00Z",
        content_length: 0,
        created_at: "2025-01-01T00:00:00Z",
        updated_at: "2025-01-01T00:00:00Z",
      },
    ];

    const { getByText, getByTestId } = render(<HomePage />);
    fireEvent.click(getByText("Trash"));
    fireEvent.click(getByText("Empty Trash"));
    await waitFor(() => expect(getByTestId("confirm-dialog")).toBeInTheDocument());
    fireEvent.click(getByTestId("confirm-cancel"));

    await waitFor(() => {
      expect(screen.queryByTestId("confirm-dialog")).not.toBeInTheDocument();
      expect(mockHardDeleteDocument).not.toHaveBeenCalled();
    });
  });
});
