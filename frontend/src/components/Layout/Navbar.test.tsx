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
    const { getByText } = render(<Navbar />);
    expect(getByText("API Docs")).toBeInTheDocument();
    expect(getByText("Test User")).toBeInTheDocument();
  });

  it("does not show navigation items when user is null", () => {
    mockUseAuth.mockReturnValue({ user: null, logout: vi.fn() });
    const { queryByText } = render(<Navbar />);
    expect(queryByText("API Docs")).not.toBeInTheDocument();
    expect(queryByText("Profile")).not.toBeInTheDocument();
  });

  it("hamburger menu button visible on mobile (check aria-label='Toggle menu')", () => {
    mockUseAuth.mockReturnValue({ user: mockUser, logout: vi.fn() });
    const { getByLabelText } = render(<Navbar />);
    expect(getByLabelText("Toggle menu")).toBeInTheDocument();
  });

  it("desktop nav items have hidden md:flex classes", () => {
    mockUseAuth.mockReturnValue({ user: mockUser, logout: vi.fn() });
    const { container } = render(<Navbar />);
    const desktopNav = container.querySelector('[class*="md:flex"]');
    expect(desktopNav).toBeInTheDocument();
  });

  it("clicking hamburger opens mobile menu (shows Profile, API Docs, Settings, Sign Out links)", () => {
    mockUseAuth.mockReturnValue({ user: mockUser, logout: vi.fn() });
    const { getByLabelText, getByText, queryByText, getAllByText } = render(
      <Navbar />,
    );
    const hamburger = getByLabelText("Toggle menu");

    expect(queryByText("Sign Out")).not.toBeInTheDocument();
    fireEvent.click(hamburger);

    expect(getByText("Profile")).toBeInTheDocument();
    expect(getAllByText("API Docs").length).toBeGreaterThanOrEqual(1);
    expect(getByText("Settings")).toBeInTheDocument();
    expect(getByText("Sign Out")).toBeInTheDocument();
  });

  it("clicking Sign Out calls logout and navigates to '/'", async () => {
    const mockLogout = vi.fn().mockResolvedValue(undefined);
    mockUseAuth.mockReturnValue({ user: mockUser, logout: mockLogout });
    const { getByLabelText, getByText } = render(<Navbar />);

    fireEvent.click(getByLabelText("Toggle menu"));
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

  it("dark mode toggle calls toggleDark", () => {
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

  it("mobile dark mode button toggles dark class on documentElement", () => {
    mockUseAuth.mockReturnValue({ user: mockUser, logout: vi.fn() });
    document.documentElement.classList.remove("dark");
    const { container } = render(<Navbar />);
    const mobileSection = container.querySelector(".md\\:hidden");
    expect(mobileSection).toBeInTheDocument();
    const mobileButtons = mobileSection?.querySelectorAll("button") ?? [];
    const darkToggle = Array.from(mobileButtons).find(
      (b) => !b.getAttribute("aria-label"),
    );
    expect(darkToggle).toBeTruthy();

    fireEvent.click(darkToggle!);
    expect(document.documentElement.classList.contains("dark")).toBe(true);

    fireEvent.click(darkToggle!);
    expect(document.documentElement.classList.contains("dark")).toBe(false);
  });

  it("clicking Profile in mobile menu closes the menu", () => {
    mockUseAuth.mockReturnValue({ user: mockUser, logout: vi.fn() });
    const { getByLabelText, getByText, queryByText } = render(<Navbar />);
    fireEvent.click(getByLabelText("Toggle menu"));
    expect(getByText("Profile")).toBeInTheDocument();
    fireEvent.click(getByText("Profile"));
    expect(queryByText("Sign Out")).not.toBeInTheDocument();
  });

  it("clicking API Docs in mobile menu closes the menu", () => {
    mockUseAuth.mockReturnValue({ user: mockUser, logout: vi.fn() });
    const { getByLabelText, queryByText } = render(<Navbar />);
    fireEvent.click(getByLabelText("Toggle menu"));
    const signOutBtn = queryByText("Sign Out");
    expect(signOutBtn).toBeInTheDocument();
    const mobileMenu = signOutBtn?.closest(".md\\:hidden");
    const apiDocsLink = mobileMenu?.querySelector('a[href="/api-docs"]');
    expect(apiDocsLink).toBeTruthy();
    fireEvent.click(apiDocsLink!);
    expect(queryByText("Sign Out")).not.toBeInTheDocument();
  });

  it("clicking Settings in mobile menu closes the menu", () => {
    mockUseAuth.mockReturnValue({ user: mockUser, logout: vi.fn() });
    const { getByLabelText, getByText, queryByText } = render(<Navbar />);
    fireEvent.click(getByLabelText("Toggle menu"));
    expect(getByText("Settings")).toBeInTheDocument();
    fireEvent.click(getByText("Settings"));
    expect(queryByText("Sign Out")).not.toBeInTheDocument();
  });

  it("mobile menu shows user email", () => {
    mockUseAuth.mockReturnValue({ user: mockUser, logout: vi.fn() });
    const { getByLabelText, getByText } = render(<Navbar />);
    fireEvent.click(getByLabelText("Toggle menu"));
    expect(getByText("test@example.com")).toBeInTheDocument();
  });
});
