/**
 * Tests for EditorToolbar component.
 *
 * Validates title, back button, action buttons, presentation mode,
 * and read-only mode.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, fireEvent, within } from "@testing-library/react";
import { EditorToolbar } from "./EditorToolbar";

const mockNavigate = vi.fn();
vi.mock("react-router", () => ({
  useNavigate: () => mockNavigate,
}));

describe("EditorToolbar", () => {
  const defaultProps = {
    title: "My Document",
    onTitleChange: vi.fn(),
    onExportMd: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders title in input", () => {
    const { getByDisplayValue } = render(<EditorToolbar {...defaultProps} />);
    expect(getByDisplayValue("My Document")).toBeDefined();
  });

  it("title change calls onTitleChange", () => {
    const onTitleChange = vi.fn();
    const { getByDisplayValue } = render(<EditorToolbar {...defaultProps} onTitleChange={onTitleChange} />);
    const input = getByDisplayValue("My Document");
    fireEvent.change(input, { target: { value: "New Title" } });
    expect(onTitleChange).toHaveBeenCalledWith("New Title");
  });

  it("back button calls navigate(-1) when history.length > 1", () => {
    Object.defineProperty(window.history, "length", {
      value: 2,
      configurable: true,
    });

    const { container } = render(<EditorToolbar {...defaultProps} />);
    const backBtn = container.querySelector("button");
    fireEvent.click(backBtn!);
    expect(mockNavigate).toHaveBeenCalledWith(-1);
  });

  it("back button calls navigate('/') when history.length <= 1", () => {
    Object.defineProperty(window.history, "length", {
      value: 1,
      configurable: true,
    });

    const { container } = render(<EditorToolbar {...defaultProps} />);
    const backBtn = container.querySelector("button");
    fireEvent.click(backBtn!);
    expect(mockNavigate).toHaveBeenCalledWith("/");
  });

  it("no save button exists", () => {
    const { container } = render(<EditorToolbar {...defaultProps} />);
    const buttons = container.querySelectorAll("button");
    const saveBtn = Array.from(buttons).find((b) => b.textContent?.toLowerCase().includes("save"));
    expect(saveBtn).toBeUndefined();
  });

  it("History button calls onHistory", () => {
    const onHistory = vi.fn();
    const { getByText } = render(<EditorToolbar {...defaultProps} onHistory={onHistory} />);
    fireEvent.click(getByText("History"));
    expect(onHistory).toHaveBeenCalledTimes(1);
  });

  it("Comments button calls onComments", () => {
    const onComments = vi.fn();
    const { getByText } = render(<EditorToolbar {...defaultProps} onComments={onComments} />);
    fireEvent.click(getByText("Comments"));
    expect(onComments).toHaveBeenCalledTimes(1);
  });

  it("Share button calls onShare", () => {
    const onShare = vi.fn();
    const { getByText } = render(<EditorToolbar {...defaultProps} onShare={onShare} />);
    fireEvent.click(getByText("Share"));
    expect(onShare).toHaveBeenCalledTimes(1);
  });

  it("Export .md button calls onExportMd", () => {
    const onExportMd = vi.fn();
    const { getByText } = render(<EditorToolbar {...defaultProps} onExportMd={onExportMd} />);
    fireEvent.click(getByText(".md"));
    expect(onExportMd).toHaveBeenCalledTimes(1);
  });

  it("Export PDF button calls onExportPdf", () => {
    const onExportPdf = vi.fn();
    const { getByText } = render(<EditorToolbar {...defaultProps} onExportPdf={onExportPdf} />);
    fireEvent.click(getByText("PDF"));
    expect(onExportPdf).toHaveBeenCalledTimes(1);
  });

  it("presentation mode shows 'Exit Presentation' button", () => {
    const { getByText } = render(<EditorToolbar {...defaultProps} presentationMode onPresentation={vi.fn()} />);
    expect(getByText("Exit Presentation")).toBeDefined();
  });

  it("read-only mode shows 'View only' badge", () => {
    const { getByText } = render(<EditorToolbar {...defaultProps} readOnly />);
    expect(getByText("View only")).toBeDefined();
  });

  describe("presence avatars", () => {
    it("renders presence widgets (desktop + mobile) when presenceUsers provided", () => {
      const users = [
        { name: "Alice", avatarUrl: null, color: "#f00" },
        { name: "Bob", avatarUrl: null, color: "#0f0" },
      ];
      const { getAllByLabelText } = render(
        <EditorToolbar {...defaultProps} presenceUsers={users} currentUserName="Me" />,
      );
      const buttons = getAllByLabelText("3 active users");
      expect(buttons.length).toBe(2);
    });

    it("renders separator divider between presence and toolbar buttons", () => {
      const users = [{ name: "Alice", avatarUrl: null, color: "#f00" }];
      const { container } = render(<EditorToolbar {...defaultProps} presenceUsers={users} currentUserName="Me" />);
      const separator = container.querySelector(".mx-1.h-6.w-px");
      expect(separator).toBeTruthy();
    });

    it("renders presence widget even with empty presenceUsers (shows current user only)", () => {
      const { getAllByLabelText } = render(<EditorToolbar {...defaultProps} presenceUsers={[]} currentUserName="Me" />);
      const buttons = getAllByLabelText("1 active user");
      expect(buttons.length).toBe(2);
    });

    it("does not render presence widget when no users and no currentUserName", () => {
      const { queryByLabelText } = render(<EditorToolbar {...defaultProps} presenceUsers={[]} />);
      expect(queryByLabelText(/active user/)).toBeNull();
    });
  });

  it("presentation mode back button works", () => {
    Object.defineProperty(window.history, "length", {
      value: 2,
      configurable: true,
    });

    const { container } = render(<EditorToolbar {...defaultProps} presentationMode onPresentation={vi.fn()} />);
    const backBtn = container.querySelector("button");
    fireEvent.click(backBtn!);
    expect(mockNavigate).toHaveBeenCalledWith(-1);
  });

  describe("mobile overflow menu", () => {
    const mobileProps = {
      ...defaultProps,
      onHistory: vi.fn(),
      onComments: vi.fn(),
      onShare: vi.fn(),
      onExportMd: vi.fn(),
      onExportPdf: vi.fn(),
    };

    it('"..." (more) button is present in the rendered output', () => {
      const { getByLabelText } = render(<EditorToolbar {...mobileProps} />);
      expect(getByLabelText("More options")).toBeDefined();
    });

    it('clicking the "..." button opens a dropdown menu', () => {
      const { getByLabelText, getByText, queryByText } = render(<EditorToolbar {...mobileProps} />);
      expect(queryByText("Export .md")).toBeNull();
      fireEvent.click(getByLabelText("More options"));
      expect(getByText("Export .md")).toBeDefined();
    });

    it("dropdown contains History, Comments, Share, .md export, PDF export buttons", () => {
      const { getByLabelText, getByText } = render(<EditorToolbar {...mobileProps} />);
      fireEvent.click(getByLabelText("More options"));
      const dropdown = getByText("Export .md").closest("[class*='absolute']") as HTMLElement;
      expect(dropdown).toBeTruthy();
      const inDropdown = within(dropdown);
      expect(inDropdown.getByText("History")).toBeDefined();
      expect(inDropdown.getByText("Comments")).toBeDefined();
      expect(inDropdown.getByText("Share")).toBeDefined();
      expect(inDropdown.getByText("Export .md")).toBeDefined();
      expect(inDropdown.getByText("Export PDF")).toBeDefined();
    });

    it("clicking a dropdown item calls the corresponding callback and closes the dropdown", () => {
      const onHistory = vi.fn();
      const onExportMd = vi.fn();
      const { getByLabelText, getByText, queryByText } = render(
        <EditorToolbar {...mobileProps} onHistory={onHistory} onExportMd={onExportMd} />,
      );
      fireEvent.click(getByLabelText("More options"));
      const dropdown = getByText("Export .md").closest("[class*='absolute']") as HTMLElement;
      fireEvent.click(within(dropdown).getByText("History"));
      expect(onHistory).toHaveBeenCalledTimes(1);
      expect(queryByText("Export .md")).toBeNull();

      fireEvent.click(getByLabelText("More options"));
      fireEvent.click(getByText("Export .md"));
      expect(onExportMd).toHaveBeenCalledTimes(1);
    });

    it("clicking outside the dropdown closes it", () => {
      const { getByLabelText, getByText, queryByText } = render(<EditorToolbar {...mobileProps} />);
      fireEvent.click(getByLabelText("More options"));
      expect(getByText("Export .md")).toBeDefined();
      fireEvent.mouseDown(document.body);
      expect(queryByText("Export .md")).toBeNull();
    });

    it("mobile menu Presentation button calls onPresentation and closes dropdown", () => {
      const onPresentation = vi.fn();
      const { getByLabelText, getByText, queryByText } = render(
        <EditorToolbar {...mobileProps} onPresentation={onPresentation} />,
      );
      fireEvent.click(getByLabelText("More options"));
      fireEvent.click(getByText("Presentation"));
      expect(onPresentation).toHaveBeenCalledTimes(1);
      expect(queryByText("Export .md")).toBeNull();
    });

    it("mobile menu Export PDF button calls onExportPdf and closes dropdown", () => {
      const onExportPdf = vi.fn();
      const { getByLabelText, getByText, queryByText } = render(
        <EditorToolbar {...mobileProps} onExportPdf={onExportPdf} />,
      );
      fireEvent.click(getByLabelText("More options"));
      fireEvent.click(getByText("Export PDF"));
      expect(onExportPdf).toHaveBeenCalledTimes(1);
      expect(queryByText("Export .md")).toBeNull();
    });

    it("mobile dropdown shows Presentation only when onPresentation provided", () => {
      const propsWithoutPresentation = {
        ...mobileProps,
        onPresentation: undefined,
      };
      const { getByLabelText, queryByText } = render(<EditorToolbar {...propsWithoutPresentation} />);
      fireEvent.click(getByLabelText("More options"));
      expect(queryByText("Presentation")).toBeNull();
    });

    it("mobile dropdown shows Export PDF only when onExportPdf provided", () => {
      const propsWithoutPdf = {
        ...defaultProps,
        onHistory: vi.fn(),
        onComments: vi.fn(),
        onShare: vi.fn(),
        onExportMd: vi.fn(),
      };
      const { getByLabelText, queryByText } = render(<EditorToolbar {...propsWithoutPdf} />);
      fireEvent.click(getByLabelText("More options"));
      expect(queryByText("Export PDF")).toBeNull();
    });
  });
});
