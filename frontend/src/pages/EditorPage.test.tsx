/**
 * Comprehensive tests for EditorPage component.
 *
 * Covers loading, toolbar interactions, presentation mode,
 * collaboration sync, read-only, export, version restore, and Ctrl+S.
 */

import React from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, fireEvent, cleanup, waitFor, act } from "@testing-library/react";
import { EditorPage } from "./EditorPage";

// Mock yjs for createRelativePositionFromTypeIndex / encodeRelativePosition
const mockEncodeRelativePosition = vi.fn(() => new Uint8Array([1, 2, 3]));
const mockCreateRelativePositionFromTypeIndex = vi.fn(() => ({}));
vi.mock("yjs", async () => {
  const actual = await vi.importActual<typeof import("yjs")>("yjs");
  return {
    ...actual,
    createRelativePositionFromTypeIndex: (...args: unknown[]) =>
      (mockCreateRelativePositionFromTypeIndex as Function)(...args),
    encodeRelativePosition: (...args: unknown[]) =>
      (mockEncodeRelativePosition as Function)(...args),
  };
});

// Mock react-router
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
  useNavigate: () => vi.fn(),
  useParams: () => ({ id: "doc-123" }),
}));

// Mock useAuth
const mockUser = {
  id: "user-1",
  name: "Test User",
  email: "test@example.com",
  avatar_url: "https://example.com/avatar.png",
};
vi.mock("../hooks/useAuth", () => ({ useAuth: () => ({ user: mockUser }) }));

// Mock useToast
const mockAddToast = vi.fn();
vi.mock("../hooks/useToast", () => ({ useToast: () => ({ addToast: mockAddToast }) }));

// Mock usePresence
vi.mock("../hooks/usePresence", () => ({ usePresence: () => [] }));

// Mock useComments
vi.mock("../hooks/useComments", () => ({ useComments: () => ({ comments: [] }) }));

// Mock useCommentAnchors
vi.mock("../hooks/useCommentAnchors", () => ({ useCommentAnchors: () => new Map() }));

// Mock useCommentPositions
vi.mock("../hooks/useCommentPositions", () => ({ useCommentPositions: () => new Map() }));

// Mock pdfExport
const mockDetectNeedsLandscape = vi.fn(() => false);
vi.mock("../lib/pdfExport", () => ({
  detectNeedsLandscape: (...args: unknown[]) =>
    (mockDetectNeedsLandscape as Function)(...args),
}));

// Mock useYjsProvider - key mock
const mockYtext = {
  toString: vi.fn(() => "# Hello World"),
  observe: vi.fn(),
  unobserve: vi.fn(),
  insert: vi.fn(),
  delete: vi.fn(),
  length: 13,
};
const mockYdoc = {
  getText: vi.fn(() => mockYtext),
  transact: vi.fn((fn: () => void) => fn()),
};
const mockAwareness = {
  setLocalStateField: vi.fn(),
  on: vi.fn(),
  off: vi.fn(),
  getStates: vi.fn(() => new Map()),
  clientID: 1,
};
const mockProvider = { awareness: mockAwareness };

const useYjsProviderMock = vi.fn(() => ({
  ydoc: mockYdoc,
  ytext: mockYtext,
  provider: mockProvider,
  synced: true,
}));
vi.mock("../hooks/useYjsProvider", () => ({
  useYjsProvider: () => useYjsProviderMock(),
}));

// Mock API
const mockDocumentsGet = vi.fn();
const mockSharingGetPermission = vi.fn();
const mockSharingRecordView = vi.fn();
const mockDocumentsUpdate = vi.fn();
const mockVersionsCreate = vi.fn();
const mockVersionsList = vi.fn();

vi.mock("../lib/api", () => ({
  documentsApi: {
    get: (id: string) => mockDocumentsGet(id),
    update: (id: string, data: unknown) => mockDocumentsUpdate(id, data),
  },
  sharingApi: {
    getMyPermission: (id: string) => mockSharingGetPermission(id),
    recordView: (id: string) => mockSharingRecordView(id),
  },
  versionsApi: {
    create: (id: string, data: unknown) => mockVersionsCreate(id, data),
    list: (id: string) => mockVersionsList(id),
  },
}));

// Stub heavy child components
vi.mock("../components/Layout/Navbar", () => ({ Navbar: () => <div data-testid="navbar" /> }));

vi.mock("../components/Editor/MarkdownEditor", () => ({
  MarkdownEditor: (props: {
    ytext?: { toString?: () => string };
    readOnly?: boolean;
    onSelectionChange?: (sel: { from: number; to: number; text: string }) => void;
    onAddComment?: (sel: { from: number; to: number; text: string }) => void;
  }) => (
    <div data-testid="markdown-editor" data-readonly={props.readOnly}>
      {props.ytext?.toString?.()}
      {props.onSelectionChange && (
        <button
          data-testid="trigger-selection"
          onClick={() =>
            props.onSelectionChange!({ from: 0, to: 5, text: "Hello" })
          }
        >
          Select
        </button>
      )}
      {props.onAddComment && (
        <button
          data-testid="trigger-add-comment"
          onClick={() =>
            props.onAddComment!({ from: 0, to: 5, text: "Hello" })
          }
        >
          Add comment
        </button>
      )}
    </div>
  ),
}));

vi.mock("../components/Editor/MarkdownPreview", () => ({
  MarkdownPreview: (props: { content?: string }) => (
    <div data-testid="markdown-preview">{props.content}</div>
  ),
}));

vi.mock("../components/Editor/EditorToolbar", () => ({
  EditorToolbar: (props: {
    title: string;
    onTitleChange: (t: string) => void;
    onShare?: () => void;
    onHistory?: () => void;
    onComments?: () => void;
    onPresentation?: () => void;
    onExportMd?: () => void;
    onExportPdf?: () => void;
    readOnly?: boolean;
  }) => (
    <div data-testid="editor-toolbar">
      <input
        data-testid="title-input"
        value={props.title}
        onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
          props.onTitleChange(e.target.value)
        }
      />
      {props.onShare && (
        <button data-testid="share-btn" onClick={props.onShare}>
          Share
        </button>
      )}
      {props.onHistory && (
        <button data-testid="history-btn" onClick={props.onHistory}>
          History
        </button>
      )}
      {props.onComments && (
        <button data-testid="comments-btn" onClick={props.onComments}>
          Comments
        </button>
      )}
      {props.onPresentation && (
        <button data-testid="presentation-btn" onClick={props.onPresentation}>
          Present
        </button>
      )}
      {props.onExportMd && (
        <button data-testid="export-md-btn" onClick={props.onExportMd}>
          Export MD
        </button>
      )}
      {props.onExportPdf && (
        <button data-testid="export-pdf-btn" onClick={props.onExportPdf}>
          Export PDF
        </button>
      )}
      {props.readOnly && <span data-testid="readonly-indicator">View only</span>}
    </div>
  ),
}));

vi.mock("../components/Editor/ShareDialog", () => ({
  ShareDialog: (props: { open?: boolean }) =>
    props.open ? <div data-testid="share-dialog" /> : null,
}));

vi.mock("../components/Editor/VersionHistory", () => ({
  VersionHistory: (props: {
    open?: boolean;
    onRestore?: (content: string, versionNumber: number) => void;
  }) =>
    props.open ? (
      <div data-testid="version-history">
        <button
          data-testid="restore-btn"
          onClick={() => props.onRestore?.("restored content", 3)}
        >
          Restore
        </button>
      </div>
    ) : null,
}));

vi.mock("../components/Editor/CommentsPanel", () => ({
  CommentsPanel: (props: { open?: boolean; onClose?: () => void }) =>
    props.open ? (
      <div data-testid="comments-panel">
        <button data-testid="comments-close-btn" onClick={props.onClose}>
          Close
        </button>
      </div>
    ) : null,
}));

const defaultDocResponse = {
  data: {
    id: "doc-123",
    title: "Test Document",
    content: "# Hello World",
    owner_id: "user-1",
    owner_name: "Test User",
    owner_email: "test@example.com",
    owner_avatar_url: "https://example.com/avatar.png",
    general_access: "restricted",
  },
};

const defaultPermResponse = { data: { permission: "edit" as const } };

describe("EditorPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useRealTimers();
    mockDetectNeedsLandscape.mockReturnValue(false);
    mockDocumentsGet.mockResolvedValue(defaultDocResponse);
    mockSharingGetPermission.mockResolvedValue(defaultPermResponse);
    mockSharingRecordView.mockResolvedValue({});
    mockDocumentsUpdate.mockResolvedValue({ data: {} });
    mockVersionsCreate.mockResolvedValue({ data: {} });
    mockVersionsList.mockResolvedValue({ data: [] });
    useYjsProviderMock.mockReturnValue({
      ydoc: mockYdoc,
      ytext: mockYtext,
      provider: mockProvider,
      synced: true,
    });
    mockYtext.toString.mockReturnValue("# Hello World");

    Object.defineProperty(window, "matchMedia", {
      writable: true,
      value: vi.fn().mockImplementation((query: string) => ({
        matches: false,
        media: query,
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      })),
    });
    Object.defineProperty(window, "localStorage", {
      value: {
        getItem: vi.fn(() => "50"),
        setItem: vi.fn(),
        removeItem: vi.fn(),
      },
      writable: true,
    });
  });

  afterEach(() => {
    cleanup();
  });

  describe("Loading / init", () => {
    it("shows loading spinner initially (before API resolves)", async () => {
      let resolveDoc: (v: unknown) => void;
      let resolvePerm: (v: unknown) => void;
      const docPromise = new Promise((r) => {
        resolveDoc = r;
      });
      const permPromise = new Promise((r) => {
        resolvePerm = r;
      });
      mockDocumentsGet.mockReturnValue(docPromise);
      mockSharingGetPermission.mockReturnValue(permPromise);

      const { container } = render(<EditorPage />);

      expect(container.querySelector(".animate-spin")).toBeInTheDocument();
      expect(container.querySelector("[data-testid='editor-toolbar']")).not.toBeInTheDocument();

      await act(async () => {
        resolveDoc!(defaultDocResponse);
        resolvePerm!(defaultPermResponse);
      });
    });

    it("after API resolves, shows editor toolbar and editor", async () => {
      const { getByTestId } = render(<EditorPage />);

      await waitFor(() => {
        expect(getByTestId("editor-toolbar")).toBeInTheDocument();
      });

      await waitFor(() => {
        expect(getByTestId("markdown-editor")).toBeInTheDocument();
      });
    });

    it("sets document.title to 'Test Document - CollabMark'", async () => {
      render(<EditorPage />);

      await waitFor(() => {
        expect(document.title).toBe("Test Document - CollabMark");
      });
    });

    it("calls documentsApi.get and sharingApi.getMyPermission on mount", async () => {
      render(<EditorPage />);

      await waitFor(() => {
        expect(mockDocumentsGet).toHaveBeenCalledWith("doc-123");
        expect(mockSharingGetPermission).toHaveBeenCalledWith("doc-123");
      });
    });

    it("calls sharingApi.recordView on mount", async () => {
      render(<EditorPage />);

      await waitFor(() => {
        expect(mockSharingRecordView).toHaveBeenCalledWith("doc-123");
      });
    });
  });

  describe("Toolbar interactions", () => {
    it("title input shows document title", async () => {
      const { getByTestId } = render(<EditorPage />);

      await waitFor(() => {
        expect(getByTestId("title-input")).toHaveValue("Test Document");
      });
    });

    it("changing title in toolbar triggers API update (with debounce)", async () => {
      const { getByTestId } = render(<EditorPage />);

      await waitFor(() => {
        expect(getByTestId("title-input")).toBeInTheDocument();
      });

      const input = getByTestId("title-input");
      fireEvent.change(input, { target: { value: "New Title" } });

      expect(mockDocumentsUpdate).not.toHaveBeenCalled();

      vi.useFakeTimers();
      await act(async () => {
        vi.advanceTimersByTime(800);
      });
      vi.useRealTimers();

      await waitFor(() => {
        expect(mockDocumentsUpdate).toHaveBeenCalledWith("doc-123", { title: "New Title" });
      });
    });

    it("share button opens ShareDialog", async () => {
      const { getByTestId } = render(<EditorPage />);

      await waitFor(() => {
        expect(getByTestId("share-btn")).toBeInTheDocument();
      });

      fireEvent.click(getByTestId("share-btn"));

      expect(getByTestId("share-dialog")).toBeInTheDocument();
    });

    it("history button toggles VersionHistory", async () => {
      const { getByTestId } = render(<EditorPage />);

      await waitFor(() => {
        expect(getByTestId("history-btn")).toBeInTheDocument();
      });

      fireEvent.click(getByTestId("history-btn"));
      expect(getByTestId("version-history")).toBeInTheDocument();

      // Click backdrop to close (VersionHistory has onClose via backdrop)
      const backdrop = document.querySelector(".fixed.inset-0.z-30");
      if (backdrop) fireEvent.click(backdrop);
    });

    it("comments button toggles CommentsPanel", async () => {
      const { getByTestId } = render(<EditorPage />);

      await waitFor(() => {
        expect(getByTestId("comments-btn")).toBeInTheDocument();
      });

      fireEvent.click(getByTestId("comments-btn"));
      expect(getByTestId("comments-panel")).toBeInTheDocument();
    });

    it("opening History closes Comments (mutual exclusion)", async () => {
      const { getByTestId, queryByTestId } = render(<EditorPage />);

      await waitFor(() => {
        expect(getByTestId("comments-btn")).toBeInTheDocument();
      });

      fireEvent.click(getByTestId("comments-btn"));
      expect(getByTestId("comments-panel")).toBeInTheDocument();

      fireEvent.click(getByTestId("history-btn"));
      await waitFor(() => {
        expect(getByTestId("version-history")).toBeInTheDocument();
      });
      expect(queryByTestId("comments-panel")).not.toBeInTheDocument();
    });
  });

  describe("Presentation mode", () => {
    it("clicking presentation button shows preview full-width", async () => {
      const { getByTestId } = render(<EditorPage />);

      await waitFor(() => {
        expect(getByTestId("presentation-btn")).toBeInTheDocument();
      });

      fireEvent.click(getByTestId("presentation-btn"));

      expect(getByTestId("markdown-preview")).toBeInTheDocument();
      // In presentation mode, the split editor is hidden and only preview is shown
      const preview = getByTestId("markdown-preview");
      expect(preview).toBeInTheDocument();
    });

    it("history and comments buttons are hidden in presentation mode", async () => {
      const { getByTestId, queryByTestId } = render(<EditorPage />);

      await waitFor(() => {
        expect(getByTestId("presentation-btn")).toBeInTheDocument();
      });

      fireEvent.click(getByTestId("presentation-btn"));

      // In presentation mode, EditorToolbar gets onHistory: undefined, onComments: undefined
      // Our mock only renders those buttons when props are defined
      expect(queryByTestId("history-btn")).not.toBeInTheDocument();
      expect(queryByTestId("comments-btn")).not.toBeInTheDocument();
    });
  });

  describe("Collaboration", () => {
    it("shows 'Connecting...' banner when synced=false", async () => {
      useYjsProviderMock.mockReturnValue({
        ydoc: mockYdoc,
        ytext: mockYtext,
        provider: mockProvider,
        synced: false,
      });

      const { getByText } = render(<EditorPage />);

      await waitFor(() => {
        expect(getByText(/Connecting to collaboration server/)).toBeInTheDocument();
      });
    });
  });

  describe("Read-only", () => {
    it("when permission=view, readOnly=true is passed to MarkdownEditor", async () => {
      mockSharingGetPermission.mockResolvedValue({ data: { permission: "view" } });

      const { getByTestId } = render(<EditorPage />);

      await waitFor(() => {
        const editor = getByTestId("markdown-editor");
        expect(editor).toHaveAttribute("data-readonly", "true");
      });
    });

    it("when permission=view, read-only indicator shows", async () => {
      mockSharingGetPermission.mockResolvedValue({ data: { permission: "view" } });

      const { getByTestId } = render(<EditorPage />);

      await waitFor(() => {
        expect(getByTestId("readonly-indicator")).toBeInTheDocument();
      });
    });
  });

  describe("Export", () => {
    it("export MD button triggers download", async () => {
      const originalCreateElement = document.createElement.bind(document);
      const createElementSpy = vi.spyOn(document, "createElement");
      const createObjectURLSpy = vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:mock");
      const revokeObjectURLSpy = vi.spyOn(URL, "revokeObjectURL");

      const mockClick = vi.fn();
      createElementSpy.mockImplementation((tagName: string) => {
        const el = originalCreateElement(tagName);
        if (tagName === "a") {
          el.click = mockClick;
        }
        return el;
      });

      const { getByTestId } = render(<EditorPage />);

      await waitFor(() => {
        expect(getByTestId("export-md-btn")).toBeInTheDocument();
      });

      fireEvent.click(getByTestId("export-md-btn"));

      expect(createObjectURLSpy).toHaveBeenCalled();
      expect(mockClick).toHaveBeenCalled();
      expect(revokeObjectURLSpy).toHaveBeenCalledWith("blob:mock");

      createElementSpy.mockRestore();
      createObjectURLSpy.mockRestore();
      revokeObjectURLSpy.mockRestore();
    });

    it("export PDF button triggers print window", async () => {
      const mockPrint = vi.fn();
      const mockClose = vi.fn();
      const mockOpen = vi.fn().mockReturnValue({
        document: {
          write: vi.fn(),
          close: vi.fn(),
        },
        print: mockPrint,
        close: mockClose,
      });

      Object.defineProperty(window, "open", {
        value: mockOpen,
        writable: true,
      });

      const { getByTestId } = render(<EditorPage />);

      await waitFor(() => {
        expect(getByTestId("export-pdf-btn")).toBeInTheDocument();
      });

      fireEvent.click(getByTestId("export-pdf-btn"));

      expect(mockOpen).toHaveBeenCalledWith("", "_blank");

      // Advance past the 500ms setTimeout for print
      await act(async () => {
        await new Promise((r) => setTimeout(r, 600));
      });

      expect(mockPrint).toHaveBeenCalled();
      expect(mockClose).toHaveBeenCalled();
    });

    it("export PDF uses landscape when detectNeedsLandscape returns true", async () => {
      mockDetectNeedsLandscape.mockReturnValue(true);
      const mockWrite = vi.fn();
      const mockOpen = vi.fn().mockReturnValue({
        document: {
          write: mockWrite,
          close: vi.fn(),
        },
        print: vi.fn(),
        close: vi.fn(),
      });

      Object.defineProperty(window, "open", {
        value: mockOpen,
        writable: true,
      });

      const { getByTestId } = render(<EditorPage />);

      await waitFor(() => {
        expect(getByTestId("export-pdf-btn")).toBeInTheDocument();
      });

      fireEvent.click(getByTestId("export-pdf-btn"));

      expect(mockWrite).toHaveBeenCalledWith(
        expect.stringContaining("landscape")
      );
    });
  });

  describe("Version restore", () => {
    it("when VersionHistory onRestore is called, ytext is updated and toast shows", async () => {
      const { getByTestId } = render(<EditorPage />);

      await waitFor(() => {
        expect(getByTestId("history-btn")).toBeInTheDocument();
      });

      fireEvent.click(getByTestId("history-btn"));

      await waitFor(() => {
        expect(getByTestId("restore-btn")).toBeInTheDocument();
      });

      fireEvent.click(getByTestId("restore-btn"));

      expect(mockYdoc.transact).toHaveBeenCalled();
      expect(mockYtext.delete).toHaveBeenCalledWith(0, mockYtext.length);
      expect(mockYtext.insert).toHaveBeenCalledWith(0, "restored content");
      expect(mockAddToast).toHaveBeenCalledWith("Restored to version 3", "success");
    });
  });

  describe("Keyboard shortcuts", () => {
    it("Ctrl+S is intercepted (no default browser save dialog)", async () => {
      render(<EditorPage />);

      await waitFor(() => {
        expect(document.querySelector("[data-testid='editor-toolbar']")).toBeInTheDocument();
      });

      const event = new KeyboardEvent("keydown", {
        key: "s",
        ctrlKey: true,
        bubbles: true,
      });
      const preventDefaultSpy = vi.spyOn(event, "preventDefault");

      window.dispatchEvent(event);

      expect(preventDefaultSpy).toHaveBeenCalled();
    });
  });

  describe("Document not found (404)", () => {
    it("shows error when documentsApi.get rejects with 404", async () => {
      const err = new Error("Not found") as Error & { response?: { status?: number } };
      err.response = { status: 404 };
      mockDocumentsGet.mockRejectedValue(err);
      mockSharingGetPermission.mockRejectedValue(err);

      const { getByTestId } = render(<EditorPage />);

      await waitFor(() => {
        expect(getByTestId("load-error")).toBeInTheDocument();
        expect(getByTestId("load-error")).toHaveTextContent("Document not found");
      });
    });
  });

  describe("Permission denied (403)", () => {
    it("shows error when documentsApi.get rejects with 403", async () => {
      const err = new Error("Forbidden") as Error & { response?: { status?: number } };
      err.response = { status: 403 };
      mockDocumentsGet.mockRejectedValue(err);
      mockSharingGetPermission.mockRejectedValue(err);

      const { getByTestId } = render(<EditorPage />);

      await waitFor(() => {
        expect(getByTestId("load-error")).toBeInTheDocument();
        expect(getByTestId("load-error")).toHaveTextContent("Permission denied");
      });
    });

    it("shows read-only when doc owned by someone else and permission is view", async () => {
      mockSharingGetPermission.mockResolvedValue({ data: { permission: "view" } });
      mockDocumentsGet.mockResolvedValue({
        ...defaultDocResponse,
        data: { ...defaultDocResponse.data, owner_id: "other-user-id" },
      });

      const { getByTestId } = render(<EditorPage />);

      await waitFor(() => {
        expect(getByTestId("readonly-indicator")).toBeInTheDocument();
        expect(getByTestId("markdown-editor")).toHaveAttribute("data-readonly", "true");
      });
    });
  });

  describe("Split pane resize", () => {
    it("resizes split pane on mousedown, mousemove, mouseup", async () => {
      const { getByTestId } = render(<EditorPage />);

      await waitFor(() => {
        expect(getByTestId("resize-divider")).toBeInTheDocument();
      });

      const divider = getByTestId("resize-divider");
      const container = divider.parentElement!;
      vi.spyOn(container, "getBoundingClientRect").mockReturnValue({
        left: 0,
        top: 0,
        width: 1000,
        height: 600,
        right: 1000,
        bottom: 600,
        x: 0,
        y: 0,
        toJSON: () => ({}),
      });

      fireEvent.mouseDown(divider);

      act(() => {
        window.dispatchEvent(
          new MouseEvent("mousemove", { clientX: 300, bubbles: true })
        );
      });

      act(() => {
        window.dispatchEvent(new MouseEvent("mouseup", { bubbles: true }));
      });

      expect(container.querySelector("[style*='width']")).toBeInTheDocument();
    });
  });

  describe("Presentation mode exit", () => {
    it("exits presentation mode when clicking exit button", async () => {
      const { getByTestId, queryByTestId } = render(<EditorPage />);

      await waitFor(() => {
        expect(getByTestId("presentation-btn")).toBeInTheDocument();
      });

      fireEvent.click(getByTestId("presentation-btn"));
      expect(getByTestId("exit-presentation-btn")).toBeInTheDocument();

      fireEvent.click(getByTestId("exit-presentation-btn"));

      await waitFor(() => {
        expect(queryByTestId("exit-presentation-btn")).not.toBeInTheDocument();
      });
    });

    it("exits presentation mode on Escape key", async () => {
      const { getByTestId, queryByTestId } = render(<EditorPage />);

      await waitFor(() => {
        expect(getByTestId("presentation-btn")).toBeInTheDocument();
      });

      fireEvent.click(getByTestId("presentation-btn"));
      expect(getByTestId("exit-presentation-btn")).toBeInTheDocument();

      fireEvent.keyDown(document, { key: "Escape" });

      await waitFor(() => {
        expect(queryByTestId("exit-presentation-btn")).not.toBeInTheDocument();
      });
    });
  });

  describe("Comments panel toggle", () => {
    it("clicking comments button twice opens then closes", async () => {
      const { getByTestId, queryByTestId } = render(<EditorPage />);

      await waitFor(() => {
        expect(getByTestId("comments-btn")).toBeInTheDocument();
      });

      fireEvent.click(getByTestId("comments-btn"));
      expect(getByTestId("comments-panel")).toBeInTheDocument();

      fireEvent.click(getByTestId("comments-btn"));
      await waitFor(() => {
        expect(queryByTestId("comments-panel")).not.toBeInTheDocument();
      });
    });

    it("opening Comments closes History (mutual exclusion)", async () => {
      const { getByTestId, queryByTestId } = render(<EditorPage />);

      await waitFor(() => {
        expect(getByTestId("history-btn")).toBeInTheDocument();
      });

      fireEvent.click(getByTestId("history-btn"));
      expect(getByTestId("version-history")).toBeInTheDocument();

      fireEvent.click(getByTestId("comments-btn"));
      await waitFor(() => {
        expect(getByTestId("comments-panel")).toBeInTheDocument();
      });
      expect(queryByTestId("version-history")).not.toBeInTheDocument();
    });
  });

  describe("Backdrop and panel close", () => {
    it("clicking backdrop closes History panel", async () => {
      const { getByTestId, queryByTestId } = render(<EditorPage />);

      await waitFor(() => {
        expect(getByTestId("history-btn")).toBeInTheDocument();
      });

      fireEvent.click(getByTestId("history-btn"));
      expect(getByTestId("version-history")).toBeInTheDocument();

      const backdrop = document.querySelector(".fixed.inset-0.z-30");
      expect(backdrop).toBeInTheDocument();
      fireEvent.click(backdrop!);

      await waitFor(() => {
        expect(queryByTestId("version-history")).not.toBeInTheDocument();
      });
    });
  });

  describe("Preview stale and flush", () => {
    it("flush preview button updates debounced content when preview is stale", async () => {
      mockYtext.toString.mockReturnValue("# Hello World");
      const { getByTestId, getByText } = render(<EditorPage />);

      await waitFor(() => {
        expect(getByTestId("markdown-preview")).toBeInTheDocument();
      });

      // Change content to make preview stale (content changes, debounced hasn't caught up)
      mockYtext.toString.mockReturnValue("# Updated Content");
      // Trigger ytext observer - we need to simulate the observer firing
      const updateContent = mockYtext.observe.mock.calls[0]?.[0];
      if (updateContent) {
        act(() => updateContent());
      }

      await waitFor(() => {
        const refreshBtn = getByText(/Refresh preview|Preview outdated/);
        if (refreshBtn) {
          fireEvent.click(refreshBtn);
        }
      });
    });
  });

  describe("Mobile layout", () => {
    it("shows mobile tabs when isMobile is true", async () => {
      Object.defineProperty(window, "matchMedia", {
        writable: true,
        value: vi.fn().mockImplementation((query: string) => ({
          matches: true,
          media: query,
          onchange: null,
          addListener: vi.fn(),
          removeListener: vi.fn(),
          addEventListener: vi.fn(),
          removeEventListener: vi.fn(),
          dispatchEvent: vi.fn(),
        })),
      });

      const { getByText } = render(<EditorPage />);

      await waitFor(() => {
        expect(getByText("Editor")).toBeInTheDocument();
        expect(getByText("Preview")).toBeInTheDocument();
      });
    });

    it("switching mobile tabs shows editor and preview", async () => {
      Object.defineProperty(window, "matchMedia", {
        writable: true,
        value: vi.fn().mockImplementation((query: string) => ({
          matches: true,
          media: query,
          onchange: null,
          addListener: vi.fn(),
          removeListener: vi.fn(),
          addEventListener: vi.fn(),
          removeEventListener: vi.fn(),
          dispatchEvent: vi.fn(),
        })),
      });

      const { getByText, getByTestId } = render(<EditorPage />);

      await waitFor(() => {
        expect(getByText("Editor")).toBeInTheDocument();
      });

      fireEvent.click(getByText("Preview"));
      await waitFor(() => {
        expect(getByTestId("markdown-preview")).toBeInTheDocument();
      });

      fireEvent.click(getByText("Editor"));
      await waitFor(() => {
        expect(getByTestId("markdown-editor")).toBeInTheDocument();
      });
    });

    it("CommentsPanel onClose closes panel in mobile layout", async () => {
      Object.defineProperty(window, "matchMedia", {
        writable: true,
        value: vi.fn().mockImplementation((query: string) => ({
          matches: true,
          media: query,
          onchange: null,
          addListener: vi.fn(),
          removeListener: vi.fn(),
          addEventListener: vi.fn(),
          removeEventListener: vi.fn(),
          dispatchEvent: vi.fn(),
        })),
      });

      const { getByTestId, queryByTestId } = render(<EditorPage />);

      await waitFor(() => {
        expect(getByTestId("comments-btn")).toBeInTheDocument();
      });

      fireEvent.click(getByTestId("comments-btn"));
      await waitFor(() => {
        expect(getByTestId("comments-panel")).toBeInTheDocument();
      });

      fireEvent.click(getByTestId("comments-close-btn"));
      await waitFor(() => {
        expect(queryByTestId("comments-panel")).not.toBeInTheDocument();
      });
    });
  });

  describe("Generic load error", () => {
    it("shows generic error when API rejects without 404/403", async () => {
      mockDocumentsGet.mockRejectedValue(new Error("Network error"));
      mockSharingGetPermission.mockRejectedValue(new Error("Network error"));

      const { getByTestId } = render(<EditorPage />);

      await waitFor(() => {
        expect(getByTestId("load-error")).toBeInTheDocument();
        expect(getByTestId("load-error")).toHaveTextContent("Failed to load document");
      });
    });
  });

  describe("Selection and add comment", () => {
    it("add comment button opens CommentsPanel and closes History", async () => {
      const { getByTestId } = render(<EditorPage />);

      await waitFor(() => {
        expect(getByTestId("trigger-add-comment")).toBeInTheDocument();
      });

      fireEvent.click(getByTestId("trigger-add-comment"));

      await waitFor(() => {
        expect(getByTestId("comments-panel")).toBeInTheDocument();
      });
    });

    it("selection change updates selection state when synced", async () => {
      const { getByTestId, queryByTestId } = render(<EditorPage />);

      await waitFor(() => {
        expect(getByTestId("trigger-selection")).toBeInTheDocument();
      });

      fireEvent.click(getByTestId("trigger-selection"));

      expect(queryByTestId("comments-panel")).not.toBeInTheDocument();
    });
  });

  describe("Auto-save", () => {
    it("does not create version when content has not changed", async () => {
      mockYtext.toString.mockReturnValue("# Hello World");

      render(<EditorPage />);

      await waitFor(() => {
        expect(mockDocumentsGet).toHaveBeenCalled();
      });

      vi.useFakeTimers();
      act(() => {
        vi.advanceTimersByTime(31_000);
      });
      vi.useRealTimers();

      expect(mockVersionsCreate).not.toHaveBeenCalled();
    });
  });

  describe("Export error handling", () => {
    it("handles URL.createObjectURL error gracefully in export MD", async () => {
      const createObjectURLSpy = vi
        .spyOn(URL, "createObjectURL")
        .mockImplementation(() => {
          throw new Error("createObjectURL failed");
        });

      const { getByTestId } = render(<EditorPage />);

      await waitFor(() => {
        expect(getByTestId("export-md-btn")).toBeInTheDocument();
      });

      fireEvent.click(getByTestId("export-md-btn"));

      expect(mockAddToast).toHaveBeenCalledWith("Failed to export Markdown", "error");

      createObjectURLSpy.mockRestore();
    });

    it("handles window.open returning null in export PDF", async () => {
      const mockOpen = vi.fn().mockReturnValue(null);
      Object.defineProperty(window, "open", {
        value: mockOpen,
        writable: true,
      });

      const { getByTestId } = render(<EditorPage />);

      await waitFor(() => {
        expect(getByTestId("export-pdf-btn")).toBeInTheDocument();
      });

      expect(() => fireEvent.click(getByTestId("export-pdf-btn"))).not.toThrow();

      Object.defineProperty(window, "open", {
        value: globalThis.open,
        writable: true,
      });
    });
  });

});
