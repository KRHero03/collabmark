import React from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ApiDocsPage } from "./ApiDocsPage";

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
}));

vi.mock("../hooks/useAuth", () => ({
  useAuth: () => ({ user: null, logout: vi.fn() }),
}));

vi.mock("../components/Layout/Navbar", () => ({
  Navbar: () => <nav data-testid="navbar">Navbar</nav>,
}));

describe("ApiDocsPage", () => {
  const mockSessionStorage: Record<string, string> = {};
  const mockClipboardWrite = vi.fn();
  const originalOrigin = window.location.origin;

  beforeEach(() => {
    vi.clearAllMocks();
    document.title = "";
    Object.keys(mockSessionStorage).forEach((k) => delete mockSessionStorage[k]);

    Object.defineProperty(window, "sessionStorage", {
      value: {
        getItem: vi.fn((key: string) => mockSessionStorage[key] ?? null),
        setItem: vi.fn((key: string, value: string) => {
          mockSessionStorage[key] = value;
        }),
        removeItem: vi.fn((key: string) => {
          delete mockSessionStorage[key];
        }),
        clear: vi.fn(() => {
          Object.keys(mockSessionStorage).forEach((k) => delete mockSessionStorage[k]);
        }),
        length: 0,
        key: vi.fn(),
      },
      writable: true,
      configurable: true,
    });

    Object.defineProperty(navigator, "clipboard", {
      value: {
        writeText: mockClipboardWrite,
        readText: vi.fn(),
      },
      writable: true,
      configurable: true,
    });

    Object.defineProperty(window, "location", {
      value: { origin: "http://localhost:5173" },
      writable: true,
    });
  });

  afterEach(() => {
    document.title = "";
    Object.defineProperty(window, "location", {
      value: { origin: originalOrigin },
      writable: true,
    });
  });

  describe("Rendering", () => {
    it("sets document.title to 'API Docs - CollabMark' on mount", () => {
      render(<ApiDocsPage />);
      expect(document.title).toBe("API Docs - CollabMark");
    });

    it("renders 'API Documentation' heading", () => {
      render(<ApiDocsPage />);
      expect(screen.getByRole("heading", { name: "API Documentation" })).toBeInTheDocument();
    });

    it("renders 'Quick Start' section", () => {
      render(<ApiDocsPage />);
      expect(screen.getByRole("heading", { name: "Quick Start" })).toBeInTheDocument();
    });

    it("renders all 5 endpoint group headings (Documents, Sharing, Versions, Comments, API Keys)", () => {
      render(<ApiDocsPage />);
      expect(screen.getByRole("heading", { name: "Documents" })).toBeInTheDocument();
      expect(screen.getByRole("heading", { name: "Sharing" })).toBeInTheDocument();
      expect(screen.getByRole("heading", { name: "Versions" })).toBeInTheDocument();
      expect(screen.getByRole("heading", { name: "Comments" })).toBeInTheDocument();
      expect(screen.getByRole("heading", { name: "API Keys" })).toBeInTheDocument();
    });

    it("renders base URL note at the bottom", () => {
      render(<ApiDocsPage />);
      expect(screen.getByText(/Base URL:/)).toBeInTheDocument();
      expect(screen.getAllByText(/http:\/\/localhost:5173/).length).toBeGreaterThanOrEqual(1);
    });

    it("renders curl example containing the base URL", () => {
      render(<ApiDocsPage />);
      const curlText = screen.getByText(/curl -H "X-API-Key: YOUR_KEY" http:\/\/localhost:5173\/api\/documents/);
      expect(curlText).toBeInTheDocument();
    });
  });

  describe("API key", () => {
    it("loads API key from sessionStorage on mount", () => {
      mockSessionStorage["collabmark_api_key"] = "cm_test_key_123";
      Object.defineProperty(window, "sessionStorage", {
        value: {
          getItem: vi.fn((key: string) => mockSessionStorage[key] ?? null),
          setItem: vi.fn((key: string, value: string) => {
            mockSessionStorage[key] = value;
          }),
          removeItem: vi.fn(),
          clear: vi.fn(),
          length: 0,
          key: vi.fn(),
        },
        writable: true,
      });
      render(<ApiDocsPage />);
      const input = screen.getByPlaceholderText("cm_...");
      expect(input).toHaveValue("cm_test_key_123");
    });

    it("typing in API key input calls sessionStorage.setItem", async () => {
      const user = userEvent.setup();
      const setItemSpy = vi.fn((key: string, value: string) => {
        mockSessionStorage[key] = value;
      });
      Object.defineProperty(window, "sessionStorage", {
        value: {
          getItem: vi.fn(() => null),
          setItem: setItemSpy,
          removeItem: vi.fn(),
          clear: vi.fn(),
          length: 0,
          key: vi.fn(),
        },
        writable: true,
        configurable: true,
      });
      render(<ApiDocsPage />);
      const input = screen.getByPlaceholderText("cm_...");
      await user.type(input, "cm_abc");
      expect(setItemSpy).toHaveBeenCalledWith("collabmark_api_key", "cm_abc");
    });

    it("API key input has type='password'", () => {
      render(<ApiDocsPage />);
      const input = screen.getByPlaceholderText("cm_...");
      expect(input).toHaveAttribute("type", "password");
    });
  });

  describe("Endpoint cards", () => {
    it("clicking an endpoint card expands it (shows description)", async () => {
      render(<ApiDocsPage />);
      const createDocCard = screen
        .getAllByRole("button")
        .find(
          (b) =>
            b.textContent?.includes("POST") &&
            b.textContent?.includes("/api/documents") &&
            !b.textContent?.includes("{doc_id}"),
        );
      if (!createDocCard) throw new Error("Could not find Create a document card");
      fireEvent.click(createDocCard);
      await waitFor(() => {
        expect(
          screen.getByText(
            "Create a new Markdown document. Both fields are optional and default to 'Untitled' and empty content.",
          ),
        ).toBeInTheDocument();
      });
    });

    it("clicking expanded card collapses it", async () => {
      render(<ApiDocsPage />);
      const createDocCard = screen
        .getAllByRole("button")
        .find(
          (b) =>
            b.textContent?.includes("POST") &&
            b.textContent?.includes("/api/documents") &&
            !b.textContent?.includes("{doc_id}"),
        );
      if (!createDocCard) throw new Error("Could not find Create a document card");
      fireEvent.click(createDocCard);
      await waitFor(() => {
        expect(
          screen.getByText(
            "Create a new Markdown document. Both fields are optional and default to 'Untitled' and empty content.",
          ),
        ).toBeInTheDocument();
      });
      fireEvent.click(createDocCard);
      await waitFor(() => {
        expect(
          screen.queryByText(
            "Create a new Markdown document. Both fields are optional and default to 'Untitled' and empty content.",
          ),
        ).not.toBeInTheDocument();
      });
    });

    it("expanded 'Create a document' card shows its description text", async () => {
      render(<ApiDocsPage />);
      const cards = screen.getAllByRole("button");
      const createDocCard = cards.find(
        (b) =>
          b.textContent?.includes("POST") &&
          b.textContent?.includes("/api/documents") &&
          !b.textContent?.includes("{doc_id}"),
      );
      if (!createDocCard) throw new Error("Could not find Create a document card");
      fireEvent.click(createDocCard);
      await waitFor(() => {
        expect(
          screen.getByText(
            "Create a new Markdown document. Both fields are optional and default to 'Untitled' and empty content.",
          ),
        ).toBeInTheDocument();
      });
    });
  });

  describe("Copy", () => {
    it("copy button calls navigator.clipboard.writeText with the curl example", async () => {
      render(<ApiDocsPage />);
      const copyBtn = screen.getByTitle("Copy");
      fireEvent.click(copyBtn);
      expect(mockClipboardWrite).toHaveBeenCalledWith(
        'curl -H "X-API-Key: YOUR_KEY" http://localhost:5173/api/documents',
      );
    });

    it("shows 'Copied!' text after clicking copy button", async () => {
      vi.useFakeTimers();
      render(<ApiDocsPage />);
      const copyBtn = screen.getByTitle("Copy");
      fireEvent.click(copyBtn);
      expect(screen.getByText("Copied!")).toBeInTheDocument();
      vi.useRealTimers();
    });
  });

  describe("TryIt panel", () => {
    it("Send button is disabled when no API key is provided (disabled attribute)", async () => {
      render(<ApiDocsPage />);
      const cards = screen.getAllByRole("button");
      const createDocCard = cards.find(
        (b) =>
          b.textContent?.includes("POST") &&
          b.textContent?.includes("/api/documents") &&
          !b.textContent?.includes("{doc_id}"),
      );
      if (!createDocCard) throw new Error("Could not find Create a document card");
      fireEvent.click(createDocCard);
      await waitFor(() => {
        expect(
          screen.getByText(
            "Create a new Markdown document. Both fields are optional and default to 'Untitled' and empty content.",
          ),
        ).toBeInTheDocument();
      });
      const sendBtn = screen.getByRole("button", { name: /Send Request/ });
      expect(sendBtn).toBeDisabled();
    });
  });
});
