import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ProfilePage } from "./ProfilePage";

const mockFetchUser = vi.fn();
const mockUseAuth = vi.fn();

vi.mock("../hooks/useAuth", () => ({
  useAuth: () => mockUseAuth(),
}));

vi.mock("../lib/api", () => ({
  authApi: {
    getMe: vi.fn(),
  },
  default: {
    put: vi.fn(),
  },
}));

vi.mock("../components/Layout/Navbar", () => ({
  Navbar: () => <nav data-testid="navbar">Navbar</nav>,
}));

vi.mock("../components/Layout/UserAvatar", () => ({
  UserAvatar: ({ name }: { name: string }) => <div data-testid="user-avatar">{name}</div>,
}));

vi.mock("../lib/dateUtils", () => ({
  formatDateLong: (iso: string) => `formatted:${iso}`,
}));

const mockUser = {
  id: "u1",
  email: "user@example.com",
  name: "John Doe",
  avatar_url: "https://example.com/avatar.png",
  created_at: "2026-01-01T00:00:00Z",
};

describe("ProfilePage", () => {
  const originalTitle = document.title;

  afterEach(() => {
    vi.clearAllMocks();
    document.title = originalTitle;
  });

  beforeEach(() => {
    mockUseAuth.mockReturnValue({
      user: mockUser,
      fetchUser: mockFetchUser,
    });
  });

  it("returns null when user is null", () => {
    mockUseAuth.mockReturnValue({
      user: null,
      fetchUser: mockFetchUser,
    });
    const { container } = render(<ProfilePage />);
    expect(container.firstChild).toBeNull();
  });

  it("renders user info (name, email, member since)", () => {
    render(<ProfilePage />);
    expect(screen.getByDisplayValue("John Doe")).toBeInTheDocument();
    expect(screen.getByDisplayValue("user@example.com")).toBeInTheDocument();
    expect(screen.getByText("formatted:2026-01-01T00:00:00Z")).toBeInTheDocument();
  });

  it("updates name on input change", async () => {
    const user = userEvent.setup();
    render(<ProfilePage />);
    const nameInput = screen.getByDisplayValue("John Doe");
    await user.clear(nameInput);
    await user.type(nameInput, "Jane Smith");
    expect(screen.getByDisplayValue("Jane Smith")).toBeInTheDocument();
  });

  it("save calls API with trimmed name", async () => {
    const { authApi } = await import("../lib/api");
    const api = (await import("../lib/api")).default;
    vi.mocked(authApi.getMe).mockResolvedValue({ data: mockUser } as never);
    vi.mocked(api.put).mockResolvedValue({} as never);
    mockFetchUser.mockResolvedValue(undefined);

    const user = userEvent.setup();
    render(<ProfilePage />);
    const nameInput = screen.getByDisplayValue("John Doe");
    await user.clear(nameInput);
    await user.type(nameInput, "  Trimmed Name  ");
    fireEvent.click(screen.getByRole("button", { name: /save changes/i }));

    await waitFor(() => {
      expect(api.put).toHaveBeenCalledWith("/users/me", {
        name: "Trimmed Name",
      });
    });
  });

  it("shows 'Saved!' after successful save", async () => {
    const { authApi } = await import("../lib/api");
    const api = (await import("../lib/api")).default;
    vi.mocked(authApi.getMe).mockResolvedValue({ data: mockUser } as never);
    vi.mocked(api.put).mockResolvedValue({} as never);
    mockFetchUser.mockResolvedValue(undefined);

    const user = userEvent.setup();
    render(<ProfilePage />);
    const nameInput = screen.getByDisplayValue("John Doe");
    await user.clear(nameInput);
    await user.type(nameInput, "New Name");
    fireEvent.click(screen.getByRole("button", { name: /save changes/i }));

    await waitFor(() => {
      expect(screen.getByText("Saved!")).toBeInTheDocument();
    });
  });

  it("does not save when name is empty", async () => {
    const api = (await import("../lib/api")).default;
    const user = userEvent.setup();
    render(<ProfilePage />);
    const nameInput = screen.getByDisplayValue("John Doe");
    await user.clear(nameInput);
    fireEvent.click(screen.getByRole("button", { name: /save changes/i }));
    expect(api.put).not.toHaveBeenCalled();
  });

  it("does not save when name is only whitespace", async () => {
    const api = (await import("../lib/api")).default;
    const user = userEvent.setup();
    render(<ProfilePage />);
    const nameInput = screen.getByDisplayValue("John Doe");
    await user.clear(nameInput);
    await user.type(nameInput, "   ");
    fireEvent.click(screen.getByRole("button", { name: /save changes/i }));
    expect(api.put).not.toHaveBeenCalled();
  });

  it("sets document title on mount, resets on unmount", () => {
    document.title = "Initial";
    const { unmount } = render(<ProfilePage />);
    expect(document.title).toBe("Profile - CollabMark");
    unmount();
    expect(document.title).toBe("CollabMark");
  });
});
