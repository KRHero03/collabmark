/**
 * Tests for PresenceAvatars component.
 *
 * Validates rendering of stacked avatars, overflow badge, dropdown list,
 * outside-click dismissal, avatar fallback initials, image error handling,
 * aria labels, current user "(you)" label, and empty state.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, fireEvent } from "@testing-library/react";
import { PresenceAvatars } from "./PresenceAvatars";
import type { PresenceUser } from "../../hooks/usePresence";

const alice: PresenceUser = {
  name: "Alice Johnson",
  avatarUrl: "https://img/alice.png",
  color: "#f00",
};
const bob: PresenceUser = {
  name: "Bob Smith",
  avatarUrl: null,
  color: "#0f0",
};
const carol: PresenceUser = {
  name: "Carol Davis",
  avatarUrl: "https://img/carol.png",
  color: "#00f",
};
const dave: PresenceUser = {
  name: "Dave Wilson",
  avatarUrl: null,
  color: "#ff0",
};

describe("PresenceAvatars", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders nothing when no users and no currentUserName", () => {
    const { container } = render(
      <PresenceAvatars users={[]} />,
    );
    expect(container.innerHTML).toBe("");
  });

  it("renders current user when currentUserName is provided even with no peers", () => {
    const { getByLabelText, getByText } = render(
      <PresenceAvatars users={[]} currentUserName="Me" />,
    );
    expect(getByLabelText("1 active user")).toBeDefined();
    expect(getByText("1 active")).toBeDefined();
  });

  it("renders stacked avatars for peers", () => {
    const { getByTitle, getByLabelText } = render(
      <PresenceAvatars users={[alice, bob]} />,
    );
    expect(getByTitle("Alice Johnson")).toBeDefined();
    expect(getByTitle("Bob Smith")).toBeDefined();
    expect(getByLabelText("2 active users")).toBeDefined();
  });

  it("shows current user first with (you) suffix", () => {
    const { getByLabelText, getByText } = render(
      <PresenceAvatars users={[alice]} currentUserName="Me" />,
    );
    expect(getByLabelText("2 active users")).toBeDefined();

    fireEvent.click(getByLabelText("2 active users"));

    expect(getByText("Me (you)")).toBeDefined();
    expect(getByText("Alice Johnson")).toBeDefined();
  });

  it("renders img tag for users with avatarUrl", () => {
    const { container } = render(
      <PresenceAvatars users={[alice]} />,
    );
    const img = container.querySelector("img");
    expect(img).toBeTruthy();
    expect(img!.getAttribute("src")).toBe("https://img/alice.png");
    expect(img!.getAttribute("alt")).toBe("Alice Johnson");
    expect(img!.getAttribute("referrerpolicy")).toBe("no-referrer");
  });

  it("renders initials fallback for users without avatarUrl", () => {
    const { getByTitle } = render(
      <PresenceAvatars users={[bob]} />,
    );
    const avatar = getByTitle("Bob Smith");
    expect(avatar.tagName).toBe("SPAN");
    expect(avatar.textContent).toBe("BS");
  });

  it("falls back to initials when image fails to load", () => {
    const { container, getByTitle } = render(
      <PresenceAvatars users={[alice]} />,
    );
    const img = container.querySelector("img")!;
    fireEvent.error(img);

    const fallback = getByTitle("Alice Johnson");
    expect(fallback.tagName).toBe("SPAN");
    expect(fallback.textContent).toBe("AJ");
  });

  it("shows overflow badge when more than MAX_VISIBLE users", () => {
    const { getByText } = render(
      <PresenceAvatars
        users={[alice, bob, carol, dave]}
        currentUserName="Me"
      />,
    );
    // 5 total (Me + 4 peers), MAX_VISIBLE = 3, overflow = 2
    expect(getByText("+2")).toBeDefined();
  });

  it("does not show overflow badge when users <= MAX_VISIBLE", () => {
    const { queryByText } = render(
      <PresenceAvatars users={[alice, bob]} />,
    );
    expect(queryByText(/^\+\d+$/)).toBeNull();
  });

  it("shows active count text", () => {
    const { getByText } = render(
      <PresenceAvatars users={[alice, bob, carol]} />,
    );
    expect(getByText("3 active")).toBeDefined();
  });

  it("singular 'user' for aria-label when exactly 1 user", () => {
    const { getByLabelText } = render(
      <PresenceAvatars users={[alice]} />,
    );
    expect(getByLabelText("1 active user")).toBeDefined();
  });

  it("plural 'users' for aria-label when more than 1 user", () => {
    const { getByLabelText } = render(
      <PresenceAvatars users={[alice, bob]} />,
    );
    expect(getByLabelText("2 active users")).toBeDefined();
  });

  describe("dropdown", () => {
    it("toggles dropdown open and closed on button click", () => {
      const { getByLabelText, queryByText, getByText } = render(
        <PresenceAvatars users={[alice, bob]} />,
      );

      expect(queryByText("Active now (2)")).toBeNull();

      fireEvent.click(getByLabelText("2 active users"));
      expect(getByText("Active now (2)")).toBeDefined();

      fireEvent.click(getByLabelText("2 active users"));
      expect(queryByText("Active now (2)")).toBeNull();
    });

    it("lists all users in the dropdown with names", () => {
      const { getByLabelText, getByText } = render(
        <PresenceAvatars
          users={[alice, bob, carol]}
          currentUserName="Me"
        />,
      );

      fireEvent.click(getByLabelText("4 active users"));

      expect(getByText("Me (you)")).toBeDefined();
      expect(getByText("Alice Johnson")).toBeDefined();
      expect(getByText("Bob Smith")).toBeDefined();
      expect(getByText("Carol Davis")).toBeDefined();
    });

    it("shows online status indicators for each user", () => {
      const { getByLabelText, container } = render(
        <PresenceAvatars users={[alice, bob]} />,
      );

      fireEvent.click(getByLabelText("2 active users"));

      const onlineDots = container.querySelectorAll('[title="Online"]');
      expect(onlineDots).toHaveLength(2);
    });

    it("closes when clicking outside", () => {
      const { getByLabelText, getByText, queryByText } = render(
        <PresenceAvatars users={[alice]} />,
      );

      fireEvent.click(getByLabelText("1 active user"));
      expect(getByText("Active now (1)")).toBeDefined();

      fireEvent.mouseDown(document.body);
      expect(queryByText("Active now (1)")).toBeNull();
    });

    it("does not close when clicking inside the dropdown", () => {
      const { getByLabelText, getByText } = render(
        <PresenceAvatars users={[alice]} />,
      );

      fireEvent.click(getByLabelText("1 active user"));
      const dropdownHeader = getByText("Active now (1)");
      fireEvent.mouseDown(dropdownHeader);

      expect(getByText("Active now (1)")).toBeDefined();
    });

    it("avatars do not have scale-on-hover class", () => {
      const { getByTitle } = render(
        <PresenceAvatars users={[alice]} />,
      );
      const avatar = getByTitle("Alice Johnson");
      expect(avatar.className).not.toContain("scale");
    });

    it("cleans up mousedown listener when dropdown closes", () => {
      const addSpy = vi.spyOn(document, "addEventListener");
      const removeSpy = vi.spyOn(document, "removeEventListener");

      const { getByLabelText } = render(
        <PresenceAvatars users={[alice]} />,
      );

      fireEvent.click(getByLabelText("1 active user"));
      const mousedownCalls = addSpy.mock.calls.filter(
        (c) => c[0] === "mousedown",
      );
      expect(mousedownCalls.length).toBeGreaterThan(0);

      fireEvent.click(getByLabelText("1 active user"));
      const removeCalls = removeSpy.mock.calls.filter(
        (c) => c[0] === "mousedown",
      );
      expect(removeCalls.length).toBeGreaterThan(0);

      addSpy.mockRestore();
      removeSpy.mockRestore();
    });

    it("cleans up mousedown listener on unmount", () => {
      const removeSpy = vi.spyOn(document, "removeEventListener");

      const { getByLabelText, unmount } = render(
        <PresenceAvatars users={[alice]} />,
      );

      fireEvent.click(getByLabelText("1 active user"));
      unmount();

      const removeCalls = removeSpy.mock.calls.filter(
        (c) => c[0] === "mousedown",
      );
      expect(removeCalls.length).toBeGreaterThan(0);

      removeSpy.mockRestore();
    });
  });

  describe("initials generation", () => {
    it("generates single initial for single-word name", () => {
      const singleName: PresenceUser = {
        name: "Alice",
        avatarUrl: null,
        color: "#f00",
      };
      const { getByTitle } = render(
        <PresenceAvatars users={[singleName]} />,
      );
      expect(getByTitle("Alice").textContent).toBe("A");
    });

    it("generates two initials for multi-word name", () => {
      const { getByTitle } = render(
        <PresenceAvatars users={[bob]} />,
      );
      expect(getByTitle("Bob Smith").textContent).toBe("BS");
    });

    it("generates at most two initials for names with 3+ words", () => {
      const longName: PresenceUser = {
        name: "John Michael Smith Jr",
        avatarUrl: null,
        color: "#f00",
      };
      const { getByTitle } = render(
        <PresenceAvatars users={[longName]} />,
      );
      expect(getByTitle("John Michael Smith Jr").textContent).toBe("JM");
    });
  });

  describe("edge cases", () => {
    it("handles user with empty string avatarUrl as fallback", () => {
      const emptyUrl: PresenceUser = {
        name: "Test User",
        avatarUrl: "",
        color: "#abc",
      };
      const { getByTitle } = render(
        <PresenceAvatars users={[emptyUrl]} />,
      );
      const avatar = getByTitle("Test User");
      expect(avatar.tagName).toBe("SPAN");
      expect(avatar.textContent).toBe("TU");
    });

    it("renders exactly MAX_VISIBLE avatars without overflow badge", () => {
      const { queryByText, container } = render(
        <PresenceAvatars users={[alice, bob, carol]} />,
      );
      const avatarElements = container.querySelectorAll(
        '[title="Alice Johnson"], [title="Bob Smith"], [title="Carol Davis"]',
      );
      expect(avatarElements).toHaveLength(3);
      expect(queryByText(/^\+\d+$/)).toBeNull();
    });

    it("renders overflow badge at exactly MAX_VISIBLE + 1", () => {
      const { getByText } = render(
        <PresenceAvatars users={[alice, bob, carol, dave]} />,
      );
      expect(getByText("+1")).toBeDefined();
    });

    it("avatar uses user.color as background for initials fallback", () => {
      const { getByTitle } = render(
        <PresenceAvatars users={[bob]} />,
      );
      const avatar = getByTitle("Bob Smith");
      expect(avatar.getAttribute("style")).toContain("background-color: rgb(0, 255, 0)");
    });
  });
});
