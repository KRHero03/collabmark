import React from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, fireEvent, cleanup, waitFor } from "@testing-library/react";
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
  FolderBreadcrumbs: () => <div data-testid="breadcrumbs" />,
}));
vi.mock("../components/Home/CreateFolderDialog", () => ({
  CreateFolderDialog: (props: any) =>
    props.open ? <div data-testid="create-folder-dialog" /> : null,
}));
vi.mock("../components/Home/FolderInfoModal", () => ({
  FolderInfoModal: (props: any) =>
    props.open ? <div data-testid="folder-info-modal" /> : null,
}));
vi.mock("../components/Home/FolderShareDialog", () => ({
  FolderShareDialog: (props: any) =>
    props.open ? <div data-testid="folder-share-dialog" /> : null,
}));
vi.mock("../components/Editor/ShareDialog", () => ({
  ShareDialog: (props: any) =>
    props.open ? <div data-testid="share-dialog" /> : null,
}));
vi.mock("../components/Home/ConfirmDialog", () => ({
  ConfirmDialog: (props: any) =>
    props.open ? (
      <div data-testid="confirm-dialog">
        <button data-testid="confirm-btn" onClick={props.onConfirm}>
          Confirm
        </button>
      </div>
    ) : null,
}));
vi.mock("../components/Home/ToastContainer", () => ({
  ToastContainer: () => <div data-testid="toast-container" />,
}));
vi.mock("../components/Home/DocumentContextMenu", () => ({
  DocumentContextMenu: () => <div data-testid="context-menu" />,
  getEntityActions: vi.fn(() => []),
  getSharedDocActions: vi.fn(() => []),
  getTrashDocActions: vi.fn(() => []),
  getTrashFolderActions: vi.fn(() => []),
}));
vi.mock("../components/Home/DocumentInfoModal", () => ({
  DocumentInfoModal: (props: any) =>
    props.open ? <div data-testid="doc-info-modal" /> : null,
}));
vi.mock("../components/Home/RenameDialog", () => ({
  RenameDialog: () => null,
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
});
