import { describe, it, expect, afterEach, beforeEach, vi } from "vitest";
import { render, fireEvent, cleanup, act } from "@testing-library/react";
import { LandingPage } from "./LandingPage";

describe("LandingPage", () => {
  beforeEach(() => {
    document.documentElement.classList.remove("dark");
    Object.defineProperty(window, "localStorage", {
      value: { getItem: vi.fn(), setItem: vi.fn(), removeItem: vi.fn(), clear: vi.fn(), length: 0, key: vi.fn() },
      writable: true,
    });
  });

  afterEach(cleanup);

  it("renders the hero headline 'Collaborative Markdown, Supercharged'", () => {
    const { getByText } = render(<LandingPage />);
    expect(getByText("Collaborative Markdown,")).toBeInTheDocument();
    expect(getByText("Supercharged")).toBeInTheDocument();
  });

  it("renders navbar without Sign In link and SSOLoginFlow in hero/footer", () => {
    const { getAllByPlaceholderText, getAllByTestId } = render(<LandingPage />);
    const nav = document.querySelector("nav");
    expect(nav).toBeInTheDocument();
    expect(nav!.querySelector('a[href="#get-started"]')).toBeNull();
    const googleBtns = document.querySelectorAll('a[href="/api/auth/google/login"]');
    const navGoogleBtns = Array.from(googleBtns).filter((el) => el.closest("nav") !== null);
    expect(navGoogleBtns.length).toBe(0);
    const emailInputs = getAllByPlaceholderText("Enter your work email");
    expect(emailInputs.length).toBe(2);
    const continueBtns = getAllByTestId("sso-continue-btn");
    expect(continueBtns.length).toBe(2);
  });

  it("renders View API Docs link to /api-docs", () => {
    const { getByText } = render(<LandingPage />);
    const apiDocsLink = getByText("View API Docs");
    expect(apiDocsLink).toBeInTheDocument();
    expect(apiDocsLink).toHaveAttribute("href", "/api-docs");
  });

  it("renders all 6 feature cards in the feature grid section", () => {
    render(<LandingPage />);
    const featureTitles = [
      "Real-time Collaboration",
      "Version History & Diff",
      "Inline Comments",
      "Spaces & Folders",
      "Markdown & Mermaid",
      "Seamless Sharing",
    ];
    featureTitles.forEach((title) => {
      const all = document.querySelectorAll(`*`);
      const found = Array.from(all).some((el) => el.textContent?.includes(title));
      expect(found).toBe(true);
    });
  });

  it("renders carousel arrows that are hidden by default (opacity-0, visible on hover)", () => {
    const { getByLabelText } = render(<LandingPage />);
    const prevBtn = getByLabelText("Previous slide");
    const nextBtn = getByLabelText("Next slide");
    expect(prevBtn).toBeInTheDocument();
    expect(nextBtn).toBeInTheDocument();
    expect(prevBtn.className).toContain("opacity-0");
    expect(nextBtn.className).toContain("opacity-0");
  });

  it("renders dot indicators matching the number of features", () => {
    const { container } = render(<LandingPage />);
    const dotButtons = container.querySelectorAll('[aria-label^="Go to slide"]');
    expect(dotButtons.length).toBe(6);
  });

  it("clicking dot indicators changes the slide", () => {
    const { container } = render(<LandingPage />);
    const carouselTrack = container.querySelector(".flex.transition-transform") as HTMLElement;
    expect(carouselTrack).toBeInTheDocument();

    const dots = container.querySelectorAll('[aria-label^="Go to slide"]');

    expect(carouselTrack.style.transform).toBe("translateX(-0%)");

    fireEvent.click(dots[2]);
    expect(carouselTrack.style.transform).toBe("translateX(-200%)");

    fireEvent.click(dots[0]);
    expect(carouselTrack.style.transform).toBe("translateX(-0%)");
  });

  it("clicking prev/next arrows changes the slide", () => {
    const { getByLabelText, container } = render(<LandingPage />);
    const carouselTrack = container.querySelector(".flex.transition-transform") as HTMLElement;

    const prevBtn = getByLabelText("Previous slide");
    const nextBtn = getByLabelText("Next slide");

    expect(carouselTrack.style.transform).toBe("translateX(-0%)");

    fireEvent.click(nextBtn);
    expect(carouselTrack.style.transform).toBe("translateX(-100%)");

    fireEvent.click(nextBtn);
    expect(carouselTrack.style.transform).toBe("translateX(-200%)");

    fireEvent.click(prevBtn);
    expect(carouselTrack.style.transform).toBe("translateX(-100%)");
  });

  it("does not render a tech stack / powered by section", () => {
    render(<LandingPage />);
    const poweredByText = document.body.textContent;
    expect(poweredByText).not.toContain("Powered by");
    expect(poweredByText).not.toContain("React 19");
    expect(poweredByText).not.toContain("Yjs CRDTs");
  });

  it("renders the stats section with correct labels", () => {
    const { getByText } = render(<LandingPage />);
    expect(getByText("Real-time")).toBeInTheDocument();
    expect(getByText("Collaboration")).toBeInTheDocument();
    expect(getByText("Auto")).toBeInTheDocument();
    expect(getByText("Versioning")).toBeInTheDocument();
    expect(getByText("Granular")).toBeInTheDocument();
    expect(getByText("Access Control")).toBeInTheDocument();
  });

  it("does not mention Google Docs anywhere on the page", () => {
    render(<LandingPage />);
    const bodyText = document.body.textContent ?? "";
    expect(bodyText).not.toContain("Google Docs");
  });

  it("renders the footer with CollabMark branding", () => {
    const { getByText } = render(<LandingPage />);
    const footer = document.querySelector("footer");
    expect(footer).toBeInTheDocument();
    expect(footer).toHaveTextContent("CollabMark");
    expect(getByText("API Docs")).toBeInTheDocument();
  });

  it("renders the final CTA section with sign-in option", () => {
    const { getByText, getAllByPlaceholderText } = render(<LandingPage />);
    expect(getByText("Start collaborating now")).toBeInTheDocument();
    const emailInputs = getAllByPlaceholderText("Enter your work email");
    expect(emailInputs.length).toBeGreaterThanOrEqual(1);
  });

  it("renders the sticky top bar with CollabMark logo", () => {
    const { getAllByText } = render(<LandingPage />);
    const nav = document.querySelector("nav");
    expect(nav).toBeInTheDocument();
    expect(nav).toHaveTextContent("CollabMark");
    const collabMarkTexts = getAllByText("CollabMark");
    expect(collabMarkTexts.length).toBeGreaterThanOrEqual(1);
  });

  describe("carousel touch/drag interaction", () => {
    it("touch swipe right goes to previous slide", () => {
      const { container } = render(<LandingPage />);
      const carousel = container.querySelector(".group\\/carousel");
      expect(carousel).toBeInTheDocument();

      const track = container.querySelector(".flex.transition-transform") as HTMLElement;
      expect(track?.style.transform).toBe("translateX(-0%)");

      fireEvent.touchStart(carousel!, {
        touches: [{ clientX: 200 }],
      });
      fireEvent.touchEnd(carousel!, {
        changedTouches: [{ clientX: 300 }],
      });

      expect(track?.style.transform).toBe("translateX(-500%)");
    });

    it("touch swipe left goes to next slide", () => {
      const { container } = render(<LandingPage />);
      const carousel = container.querySelector(".group\\/carousel");
      const track = container.querySelector(".flex.transition-transform") as HTMLElement;

      fireEvent.touchStart(carousel!, {
        touches: [{ clientX: 200 }],
      });
      fireEvent.touchEnd(carousel!, {
        changedTouches: [{ clientX: 100 }],
      });

      expect(track?.style.transform).toBe("translateX(-100%)");
    });

    it("touch swipe with small delta does not change slide", () => {
      const { container } = render(<LandingPage />);
      const carousel = container.querySelector(".group\\/carousel");
      const track = container.querySelector(".flex.transition-transform") as HTMLElement;

      fireEvent.touchStart(carousel!, {
        touches: [{ clientX: 100 }],
      });
      fireEvent.touchEnd(carousel!, {
        changedTouches: [{ clientX: 130 }],
      });

      expect(track?.style.transform).toBe("translateX(-0%)");
    });
  });

  describe("carousel mouse pause", () => {
    it("pauses auto-scroll when mouse enters carousel", () => {
      vi.useFakeTimers();
      const { container } = render(<LandingPage />);
      const carousel = container.querySelector(".group\\/carousel");
      const track = container.querySelector(".flex.transition-transform") as HTMLElement;

      expect(track?.style.transform).toBe("translateX(-0%)");

      act(() => {
        fireEvent.mouseEnter(carousel!);
      });
      act(() => {
        vi.advanceTimersByTime(10000);
      });

      expect(track?.style.transform).toBe("translateX(-0%)");

      act(() => {
        fireEvent.mouseLeave(carousel!);
      });
      act(() => {
        vi.advanceTimersByTime(5000);
      });

      expect(track?.style.transform).toBe("translateX(-100%)");

      vi.useRealTimers();
    });
  });

  describe("footer", () => {
    it("footer contains API Docs link with correct href", () => {
      const { getByText } = render(<LandingPage />);
      const footer = document.querySelector("footer");
      const apiDocsLink = footer?.querySelector('a[href="/api-docs"]');
      expect(apiDocsLink).toBeInTheDocument();
      expect(getByText("API Docs")).toBeInTheDocument();
    });
  });
});
