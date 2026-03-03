import { describe, it, expect, afterEach } from "vitest";
import { render, fireEvent, cleanup } from "@testing-library/react";
import { UserAvatar } from "./UserAvatar";

describe("UserAvatar", () => {
  afterEach(cleanup);

  it("renders img tag when url is provided", () => {
    const { container } = render(
      <UserAvatar url="https://example.com/avatar.png" name="John Doe" />,
    );
    const img = container.querySelector("img");
    expect(img).toBeInTheDocument();
    expect(img).toHaveAttribute("src", "https://example.com/avatar.png");
  });

  it("sets referrerPolicy='no-referrer' on the img tag", () => {
    const { container } = render(
      <UserAvatar url="https://example.com/avatar.png" name="Jane" />,
    );
    const img = container.querySelector("img");
    expect(img).toHaveAttribute("referrerPolicy", "no-referrer");
  });

  it("sets correct alt text from name prop", () => {
    const { container } = render(
      <UserAvatar url="https://example.com/avatar.png" name="Alice Smith" />,
    );
    const img = container.querySelector("img");
    expect(img).toHaveAttribute("alt", "Alice Smith");
  });

  it("shows fallback icon (data-testid='avatar-fallback') when url is null", () => {
    const { getByTestId } = render(<UserAvatar url={null} name="User" />);
    expect(getByTestId("avatar-fallback")).toBeInTheDocument();
  });

  it("shows fallback icon when url is undefined", () => {
    const { getByTestId } = render(
      <UserAvatar url={undefined} name="User" />,
    );
    expect(getByTestId("avatar-fallback")).toBeInTheDocument();
  });

  it("shows fallback icon when url is empty string", () => {
    const { getByTestId } = render(<UserAvatar url="" name="User" />);
    expect(getByTestId("avatar-fallback")).toBeInTheDocument();
  });

  it("shows fallback icon after img onError fires", () => {
    const { container, queryByTestId, getByTestId } = render(
      <UserAvatar url="https://example.com/invalid.png" name="User" />,
    );
    const img = container.querySelector("img");
    expect(img).toBeInTheDocument();
    expect(queryByTestId("avatar-fallback")).not.toBeInTheDocument();

    fireEvent.error(img!);
    expect(getByTestId("avatar-fallback")).toBeInTheDocument();
  });

  it("renders correct size classes for 'sm'", () => {
    const { container } = render(
      <UserAvatar url="https://example.com/a.png" name="User" size="sm" />,
    );
    const img = container.querySelector("img");
    expect(img?.className).toContain("h-6");
    expect(img?.className).toContain("w-6");
  });

  it("renders correct size classes for 'md'", () => {
    const { container } = render(
      <UserAvatar url="https://example.com/a.png" name="User" size="md" />,
    );
    const img = container.querySelector("img");
    expect(img?.className).toContain("h-8");
    expect(img?.className).toContain("w-8");
  });

  it("renders correct size classes for 'lg'", () => {
    const { container } = render(
      <UserAvatar url="https://example.com/a.png" name="User" size="lg" />,
    );
    const img = container.querySelector("img");
    expect(img?.className).toContain("h-16");
    expect(img?.className).toContain("w-16");
  });

  it("default size is 'md' when not specified", () => {
    const { container } = render(
      <UserAvatar url="https://example.com/a.png" name="User" />,
    );
    const img = container.querySelector("img");
    expect(img?.className).toContain("h-8");
    expect(img?.className).toContain("w-8");
  });

  it("applies additional className prop", () => {
    const { container } = render(
      <UserAvatar
        url="https://example.com/a.png"
        name="User"
        className="custom-class"
      />,
    );
    const img = container.querySelector("img");
    expect(img?.className).toContain("custom-class");
  });

  it("applies additional className prop to fallback icon", () => {
    const { getByTestId } = render(
      <UserAvatar url={null} name="User" className="my-extra-class" />,
    );
    const fallback = getByTestId("avatar-fallback");
    const classAttr = fallback.getAttribute("class") ?? fallback.className ?? "";
    expect(classAttr).toContain("my-extra-class");
  });
});
