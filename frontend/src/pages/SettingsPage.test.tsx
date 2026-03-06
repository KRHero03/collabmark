import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SettingsPage } from "./SettingsPage";
import { keysApi } from "../lib/api";

vi.mock("../lib/api", () => ({
  keysApi: {
    list: vi.fn(),
    create: vi.fn(),
    revoke: vi.fn(),
  },
}));

vi.mock("../components/Layout/Navbar", () => ({
  Navbar: () => <nav data-testid="navbar">Navbar</nav>,
}));

vi.mock("../lib/dateUtils", () => ({
  formatDateShort: (iso: string) => `formatted:${iso}`,
}));

vi.mock("../lib/clipboard", () => ({
  copyToClipboard: vi.fn(),
}));

import { copyToClipboard } from "../lib/clipboard";

describe("SettingsPage", () => {
  const originalTitle = document.title;

  afterEach(() => {
    vi.clearAllMocks();
    document.title = originalTitle;
  });

  beforeEach(() => {
    vi.mocked(keysApi.list).mockResolvedValue({ data: [] } as never);
  });

  it("empty state shows 'No API keys yet'", async () => {
    vi.mocked(keysApi.list).mockResolvedValue({ data: [] } as never);
    render(<SettingsPage />);
    await waitFor(() => {
      expect(screen.getByText("No API keys yet.")).toBeInTheDocument();
    });
  });

  it("fetches and displays keys on mount", async () => {
    const keys = [
      {
        id: "key-1",
        name: "CI Pipeline",
        is_active: true,
        created_at: "2026-01-10T00:00:00Z",
        last_used_at: "2026-01-15T12:00:00Z",
      },
    ];
    vi.mocked(keysApi).list.mockResolvedValue({ data: keys } as never);
    render(<SettingsPage />);
    await waitFor(() => {
      expect(vi.mocked(keysApi).list).toHaveBeenCalledTimes(1);
    });
    expect(screen.getByText("CI Pipeline")).toBeInTheDocument();
    expect(screen.getByText(/Created formatted:2026-01-10T00:00:00Z/)).toBeInTheDocument();
    expect(screen.getByText(/Last used formatted:2026-01-15T12:00:00Z/)).toBeInTheDocument();
  });

  it("creates key with exact name entered and shows raw_key", async () => {
    const user = userEvent.setup();
    vi.mocked(keysApi).create.mockResolvedValue({
      data: {
        id: "new-key-id",
        name: "My Key",
        raw_key: "sk_test_abc123xyz",
        created_at: "2026-03-01T00:00:00Z",
      },
    } as never);
    vi.mocked(keysApi)
      .list.mockResolvedValueOnce({ data: [] } as never)
      .mockResolvedValueOnce({
        data: [
          {
            id: "new-key-id",
            name: "My Key",
            is_active: true,
            created_at: "2026-03-01T00:00:00Z",
            last_used_at: null,
          },
        ],
      } as never);
    render(<SettingsPage />);
    await waitFor(() => {
      expect(vi.mocked(keysApi).list).toHaveBeenCalled();
    });
    const input = screen.getByPlaceholderText("Key name (e.g., CI pipeline)");
    await user.type(input, "My Key");
    fireEvent.click(screen.getByRole("button", { name: /create/i }));
    await waitFor(() => {
      expect(vi.mocked(keysApi).create).toHaveBeenCalledWith("My Key");
    });
    expect(screen.getByText("sk_test_abc123xyz")).toBeInTheDocument();
  });

  it("does not create when name is empty", async () => {
    render(<SettingsPage />);
    await waitFor(() => {
      expect(vi.mocked(keysApi).list).toHaveBeenCalled();
    });
    fireEvent.click(screen.getByRole("button", { name: /create/i }));
    expect(vi.mocked(keysApi).create).not.toHaveBeenCalled();
  });

  it("does not create when name is only whitespace", async () => {
    const user = userEvent.setup();
    render(<SettingsPage />);
    await waitFor(() => {
      expect(vi.mocked(keysApi).list).toHaveBeenCalled();
    });
    const input = screen.getByPlaceholderText("Key name (e.g., CI pipeline)");
    await user.type(input, "   ");
    fireEvent.click(screen.getByRole("button", { name: /create/i }));
    expect(vi.mocked(keysApi).create).not.toHaveBeenCalled();
  });

  it("revokes key and removes from list", async () => {
    const keys = [
      {
        id: "key-to-revoke",
        name: "Revoke Me",
        is_active: true,
        created_at: "2026-01-01T00:00:00Z",
        last_used_at: null,
      },
    ];
    vi.mocked(keysApi).list.mockResolvedValue({ data: keys } as never);
    vi.mocked(keysApi).revoke.mockResolvedValue(undefined as never);
    render(<SettingsPage />);
    await waitFor(() => {
      expect(screen.getByText("Revoke Me")).toBeInTheDocument();
    });
    const revokeButtons = screen.getAllByRole("button").filter((b) => {
      const svg = b.querySelector("svg");
      return svg && !b.textContent?.includes("Create");
    });
    fireEvent.click(revokeButtons[0]);
    await waitFor(() => {
      expect(vi.mocked(keysApi).revoke).toHaveBeenCalledWith("key-to-revoke");
    });
    expect(screen.queryByText("Revoke Me")).not.toBeInTheDocument();
  });

  it("copy button copies the raw key", async () => {
    vi.mocked(copyToClipboard).mockResolvedValue(undefined);
    const user = userEvent.setup();
    vi.mocked(keysApi).create.mockResolvedValue({
      data: {
        id: "k1",
        name: "Copy Key",
        raw_key: "sk_copy_me_123",
        created_at: "2026-03-01T00:00:00Z",
      },
    } as never);
    vi.mocked(keysApi)
      .list.mockResolvedValueOnce({ data: [] } as never)
      .mockResolvedValueOnce({
        data: [
          {
            id: "k1",
            name: "Copy Key",
            is_active: true,
            created_at: "2026-03-01T00:00:00Z",
            last_used_at: null,
          },
        ],
      } as never);
    render(<SettingsPage />);
    await waitFor(() => {
      expect(vi.mocked(keysApi).list).toHaveBeenCalled();
    });
    const input = screen.getByPlaceholderText("Key name (e.g., CI pipeline)");
    await user.type(input, "Copy Key");
    fireEvent.click(screen.getByRole("button", { name: /create/i }));
    await waitFor(() => {
      expect(screen.getByText("sk_copy_me_123")).toBeInTheDocument();
    });
    const copyBtn = screen.getByTestId("copy-api-key");
    fireEvent.click(copyBtn);
    expect(copyToClipboard).toHaveBeenCalledWith("sk_copy_me_123");
  });

  it("Enter key triggers create", async () => {
    const user = userEvent.setup();
    vi.mocked(keysApi).create.mockResolvedValue({
      data: {
        id: "k1",
        name: "Enter Key",
        raw_key: "sk_enter",
        created_at: "2026-03-01T00:00:00Z",
      },
    } as never);
    vi.mocked(keysApi)
      .list.mockResolvedValueOnce({ data: [] } as never)
      .mockResolvedValueOnce({ data: [] } as never);
    render(<SettingsPage />);
    await waitFor(() => {
      expect(vi.mocked(keysApi).list).toHaveBeenCalled();
    });
    const input = screen.getByPlaceholderText("Key name (e.g., CI pipeline)");
    await user.type(input, "Enter Key{Enter}");
    await waitFor(() => {
      expect(vi.mocked(keysApi).create).toHaveBeenCalledWith("Enter Key");
    });
  });
});
