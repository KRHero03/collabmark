import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, fireEvent, cleanup } from "@testing-library/react";
import { Navbar } from "./Navbar";

const mockNavigate = vi.fn();

vi.mock("react-router", () => ({
  Link: ({ to, children, ...props }: { to: string; children: React.ReactNode }) => (
    <a href={to} {...props}>
      {children}
    </a>
  ),
  useNavigate: () => mockNavigate,
}));

const mockUseAuth = vi.fn();
vi.mock("../../hooks/useAuth", () => ({
  useAuth: () => mockUseAuth(),
}));

const mockUser = {
  id: "user-1",
  name: "Test User",
  email: "test@example.com",
  avatar_url: "https://example.com/avatar.png",
};

describe("Navbar", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    document.documentElement.classList.remove("dark");
    Object.defineProperty(window, "localStorage", {
      value: {
        getItem: vi.fn(),
        setItem: vi.fn(),
        removeItem: vi.fn(),
        clear: vi.fn(),
        length: 0,
        key: vi.fn(),
      },
      writable: true,
    });
  });

  afterEach(cleanup);

  it("renders CollabMark logo/link", () => {
    mockUseAuth.mockReturnValue({ user: null, logout: vi.fn() });
    const { getByText } = render(<Navbar />);
    const logoLink = getByText("CollabMark").closest("a");
    expect(logoLink).toBeInTheDocument();
    expect(logoLink).toHaveAttribute("href", "/");
  });

  it("shows navigation items when user is logged in", () => {
    mockUseAuth.mockReturnValue({ user: mockUser, logout: vi.fn() });
    const { getAllByText } = render(<Navbar />);
    expect(getAllByText("API Docs").length).toBeGreaterThanOrEqual(1);
    expect(getAllByText("Test User").length).toBeGreaterThanOrEqual(1);
  });

  it("does not show navigation items when user is null", () => {
    mockUseAuth.mockReturnValue({ user: null, logout: vi.fn() });
    const { queryByText } = render(<Navbar />);
    expect(queryByText("API Docs")).not.toBeInTheDocument();
    expect(queryByText("Profile")).not.toBeInTheDocument();
  });

  it("hamburger menu button visible on mobile", () => {
    mockUseAuth.mockReturnValue({ user: mockUser, logout: vi.fn() });
    const { getByLabelText } = render(<Navbar />);
    expect(getByLabelText("Open menu")).toBeInTheDocument();
  });

  it("desktop nav items have hidden md:flex classes", () => {
    mockUseAuth.mockReturnValue({ user: mockUser, logout: vi.fn() });
    const { container } = render(<Navbar />);
    const desktopNav = container.querySelector('[class*="md:flex"]');
    expect(desktopNav).toBeInTheDocument();
  });

  it("clicking hamburger opens sidebar (shows Profile, API Docs, Settings, Sign Out)", () => {
    mockUseAuth.mockReturnValue({ user: mockUser, logout: vi.fn() });
    const { getByLabelText, getByText } = render(<Navbar />);

    fireEvent.click(getByLabelText("Open menu"));

    expect(getByText("Profile")).toBeInTheDocument();
    expect(getByText("Sign Out")).toBeInTheDocument();
  });

  it("clicking Sign Out calls logout and navigates to '/'", async () => {
    const mockLogout = vi.fn().mockResolvedValue(undefined);
    mockUseAuth.mockReturnValue({ user: mockUser, logout: mockLogout });
    const { getByLabelText, getByText } = render(<Navbar />);

    fireEvent.click(getByLabelText("Open menu"));
    fireEvent.click(getByText("Sign Out"));

    await vi.waitFor(() => {
      expect(mockLogout).toHaveBeenCalled();
      expect(mockNavigate).toHaveBeenCalledWith("/");
    });
  });

  it("renders UserAvatar component for the user", () => {
    mockUseAuth.mockReturnValue({ user: mockUser, logout: vi.fn() });
    const { container } = render(<Navbar />);
    const img = container.querySelector("img[alt='Test User']");
    expect(img).toBeInTheDocument();
    expect(img).toHaveAttribute("src", "https://example.com/avatar.png");
  });

  it("dark mode toggle works on desktop", () => {
    mockUseAuth.mockReturnValue({ user: mockUser, logout: vi.fn() });
    const { container } = render(<Navbar />);
    const darkModeButtons = container.querySelectorAll(
      'button[title="Dark mode"], button[title="Light mode"]',
    );
    const toggleBtn = Array.from(darkModeButtons).find(
      (b) => b.getAttribute("title") === "Dark mode" || b.getAttribute("title") === "Light mode",
    );
    expect(toggleBtn).toBeInTheDocument();

    fireEvent.click(toggleBtn!);
    expect(document.documentElement.classList.contains("dark")).toBe(true);

    fireEvent.click(toggleBtn!);
    expect(document.documentElement.classList.contains("dark")).toBe(false);
  });

  it("dark mode toggle persists to localStorage", () => {
    const setItem = vi.fn();
    Object.defineProperty(window, "localStorage", {
      value: {
        getItem: vi.fn(),
        setItem,
        removeItem: vi.fn(),
        clear: vi.fn(),
        length: 0,
        key: vi.fn(),
      },
      writable: true,
    });

    mockUseAuth.mockReturnValue({ user: mockUser, logout: vi.fn() });
    document.documentElement.classList.remove("dark");
    const { container } = render(<Navbar />);
    const toggleBtn = container.querySelector(
      'button[title="Dark mode"]',
    ) as HTMLButtonElement;
    fireEvent.click(toggleBtn);
    expect(setItem).toHaveBeenCalledWith("theme", "dark");

    fireEvent.click(toggleBtn);
    expect(setItem).toHaveBeenCalledWith("theme", "light");
  });

  it("sidebar dark mode button toggles dark class", () => {
    mockUseAuth.mockReturnValue({ user: mockUser, logout: vi.fn() });
    document.documentElement.classList.remove("dark");
    const { getByLabelText } = render(<Navbar />);

    fireEvent.click(getByLabelText("Open menu"));

    const sidebar = document.querySelector("[aria-label='Navigation drawer']");
    expect(sidebar).toBeInTheDocument();
    const darkToggle = sidebar?.querySelector(
      'button[title="Dark mode"], button[title="Light mode"]',
    );
    expect(darkToggle).toBeTruthy();

    fireEvent.click(darkToggle!);
    expect(document.documentElement.classList.contains("dark")).toBe(true);
  });

  it("clicking Profile in sidebar closes it", () => {
    mockUseAuth.mockReturnValue({ user: mockUser, logout: vi.fn() });
    const { getByLabelText } = render(<Navbar />);
    fireEvent.click(getByLabelText("Open menu"));

    const sidebar = document.querySelector("[aria-label='Navigation drawer']");
    const profileLink = sidebar?.querySelector('a[href="/profile"]');
    expect(profileLink).toBeTruthy();
    fireEvent.click(profileLink!);

    expect(sidebar?.className).toContain("-translate-x-full");
  });

  it("clicking API Docs in sidebar closes it", () => {
    mockUseAuth.mockReturnValue({ user: mockUser, logout: vi.fn() });
    const { getByLabelText } = render(<Navbar />);
    fireEvent.click(getByLabelText("Open menu"));

    const sidebar = document.querySelector("[aria-label='Navigation drawer']");
    const link = sidebar?.querySelector('a[href="/api-docs"]');
    expect(link).toBeTruthy();
    fireEvent.click(link!);

    expect(sidebar?.className).toContain("-translate-x-full");
  });

  it("clicking Settings in sidebar closes it", () => {
    mockUseAuth.mockReturnValue({ user: mockUser, logout: vi.fn() });
    const { getByLabelText } = render(<Navbar />);
    fireEvent.click(getByLabelText("Open menu"));

    const sidebar = document.querySelector("[aria-label='Navigation drawer']");
    const link = sidebar?.querySelector('a[href="/settings"]');
    expect(link).toBeTruthy();
    fireEvent.click(link!);

    expect(sidebar?.className).toContain("-translate-x-full");
  });

  it("sidebar shows user email", () => {
    mockUseAuth.mockReturnValue({ user: mockUser, logout: vi.fn() });
    const { getByLabelText, getByText } = render(<Navbar />);
    fireEvent.click(getByLabelText("Open menu"));
    expect(getByText("test@example.com")).toBeInTheDocument();
  });

  it("sidebar shows navigation tabs when provided", () => {
    mockUseAuth.mockReturnValue({ user: mockUser, logout: vi.fn() });
    const onTabChange = vi.fn();
    const { getByLabelText, getByText } = render(
      <Navbar activeTab="browse" onTabChange={onTabChange} />,
    );
    fireEvent.click(getByLabelText("Open menu"));

    expect(getByText("Files")).toBeInTheDocument();
    expect(getByText("Shared with me")).toBeInTheDocument();
    expect(getByText("Recently viewed")).toBeInTheDocument();
    expect(getByText("Trash")).toBeInTheDocument();
  });

  it("clicking a navigation tab calls onTabChange and closes sidebar", () => {
    mockUseAuth.mockReturnValue({ user: mockUser, logout: vi.fn() });
    const onTabChange = vi.fn();
    const { getByLabelText, getByText } = render(
      <Navbar activeTab="browse" onTabChange={onTabChange} />,
    );
    fireEvent.click(getByLabelText("Open menu"));
    fireEvent.click(getByText("Shared with me"));

    expect(onTabChange).toHaveBeenCalledWith("shared");
  });

  it("does not show navigation tabs when onTabChange is not provided", () => {
    mockUseAuth.mockReturnValue({ user: mockUser, logout: vi.fn() });
    const { getByLabelText, queryByText } = render(<Navbar />);
    fireEvent.click(getByLabelText("Open menu"));
    expect(queryByText("Navigation")).not.toBeInTheDocument();
  });

  it("close button in sidebar closes it", () => {
    mockUseAuth.mockReturnValue({ user: mockUser, logout: vi.fn() });
    const { getByLabelText } = render(<Navbar />);
    fireEvent.click(getByLabelText("Open menu"));

    const sidebar = document.querySelector("[aria-label='Navigation drawer']");
    expect(sidebar?.className).toContain("translate-x-0");

    fireEvent.click(getByLabelText("Close menu"));
    expect(sidebar?.className).toContain("-translate-x-full");
  });

  it("Escape key closes the sidebar", () => {
    mockUseAuth.mockReturnValue({ user: mockUser, logout: vi.fn() });
    const { getByLabelText } = render(<Navbar />);
    fireEvent.click(getByLabelText("Open menu"));

    const sidebar = document.querySelector("[aria-label='Navigation drawer']");
    expect(sidebar?.className).toContain("translate-x-0");

    fireEvent.keyDown(document, { key: "Escape" });
    expect(sidebar?.className).toContain("-translate-x-full");
  });
});
