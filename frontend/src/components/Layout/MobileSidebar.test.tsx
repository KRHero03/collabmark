import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, fireEvent, cleanup } from "@testing-library/react";
import { MobileSidebar } from "./MobileSidebar";

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

const defaultProps = {
  open: true,
  onClose: vi.fn(),
  user: {
    name: "Test User",
    email: "test@example.com",
    avatar_url: "https://example.com/avatar.png",
  },
  dark: false,
  onToggleDark: vi.fn(),
  onLogout: vi.fn(),
};

describe("MobileSidebar", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(cleanup);

  it("drawer has translate-x-0 when open=true", () => {
    const { container } = render(<MobileSidebar {...defaultProps} open={true} />);
    const drawer = container.querySelector('[aria-label="Navigation drawer"]');
    expect(drawer).toBeInTheDocument();
    expect(drawer?.className).toContain("translate-x-0");
  });

  it("drawer has -translate-x-full when open=false", () => {
    const { container } = render(<MobileSidebar {...defaultProps} open={false} />);
    const drawer = container.querySelector('[aria-label="Navigation drawer"]');
    expect(drawer).toBeInTheDocument();
    expect(drawer?.className).toContain("-translate-x-full");
  });

  it("shows user profile (name, email) when user is provided", () => {
    const { getByText } = render(<MobileSidebar {...defaultProps} />);
    expect(getByText("Test User")).toBeInTheDocument();
    expect(getByText("test@example.com")).toBeInTheDocument();
  });

  it("shows CollabMark title in header", () => {
    const { getByText } = render(<MobileSidebar {...defaultProps} />);
    expect(getByText("CollabMark")).toBeInTheDocument();
  });

  it("navigation tabs render when onTabChange is provided", () => {
    const onTabChange = vi.fn();
    const { getByText } = render(
      <MobileSidebar {...defaultProps} onTabChange={onTabChange} />,
    );
    expect(getByText("Files")).toBeInTheDocument();
    expect(getByText("Shared with me")).toBeInTheDocument();
    expect(getByText("Recently viewed")).toBeInTheDocument();
    expect(getByText("Trash")).toBeInTheDocument();
  });

  it("navigation tabs are hidden when onTabChange is not provided", () => {
    const { queryByText } = render(<MobileSidebar {...defaultProps} />);
    expect(queryByText("Navigation")).not.toBeInTheDocument();
    expect(queryByText("Files")).not.toBeInTheDocument();
  });

  it("clicking a tab calls onTabChange with correct key and calls onClose", () => {
    const onTabChange = vi.fn();
    const onClose = vi.fn();
    const { getByText } = render(
      <MobileSidebar
        {...defaultProps}
        onTabChange={onTabChange}
        onClose={onClose}
      />,
    );
    fireEvent.click(getByText("Shared with me"));
    expect(onTabChange).toHaveBeenCalledWith("shared");
    expect(onClose).toHaveBeenCalled();
  });

  it("active tab has highlighted styling (contains primary bg class)", () => {
    const onTabChange = vi.fn();
    const { getByText } = render(
      <MobileSidebar
        {...defaultProps}
        activeTab="shared"
        onTabChange={onTabChange}
      />,
    );
    const sharedTab = getByText("Shared with me").closest("button");
    expect(sharedTab?.className).toContain("color-primary");
  });

  it("account links (Profile, API Docs, Settings) have correct hrefs", () => {
    const { container } = render(<MobileSidebar {...defaultProps} />);
    const profileLink = container.querySelector('a[href="/profile"]');
    const apiDocsLink = container.querySelector('a[href="/api-docs"]');
    const settingsLink = container.querySelector('a[href="/settings"]');
    expect(profileLink).toBeInTheDocument();
    expect(apiDocsLink).toBeInTheDocument();
    expect(settingsLink).toBeInTheDocument();
  });

  it("clicking Sign Out calls onLogout and onClose", () => {
    const onLogout = vi.fn();
    const onClose = vi.fn();
    const { getByText } = render(
      <MobileSidebar {...defaultProps} onLogout={onLogout} onClose={onClose} />,
    );
    fireEvent.click(getByText("Sign Out"));
    expect(onLogout).toHaveBeenCalled();
    expect(onClose).toHaveBeenCalled();
  });

  it("clicking backdrop calls onClose", () => {
    const onClose = vi.fn();
    const { container } = render(
      <MobileSidebar {...defaultProps} open={true} onClose={onClose} />,
    );
    const backdrop = container.querySelector('[class*="bg-black/40"]');
    expect(backdrop).toBeInTheDocument();
    fireEvent.click(backdrop!);
    expect(onClose).toHaveBeenCalled();
  });

  it("close button calls onClose", () => {
    const onClose = vi.fn();
    const { getByLabelText } = render(
      <MobileSidebar {...defaultProps} onClose={onClose} />,
    );
    fireEvent.click(getByLabelText("Close menu"));
    expect(onClose).toHaveBeenCalled();
  });

  it("dark mode toggle button calls onToggleDark", () => {
    const onToggleDark = vi.fn();
    const { container } = render(
      <MobileSidebar {...defaultProps} onToggleDark={onToggleDark} />,
    );
    const darkToggle = container.querySelector(
      'button[title="Dark mode"]',
    ) as HTMLButtonElement;
    expect(darkToggle).toBeInTheDocument();
    fireEvent.click(darkToggle);
    expect(onToggleDark).toHaveBeenCalled();
  });

  it("Escape key calls onClose (fires keydown event on document)", () => {
    const onClose = vi.fn();
    render(<MobileSidebar {...defaultProps} open={true} onClose={onClose} />);
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).toHaveBeenCalled();
  });
});
