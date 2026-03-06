import { describe, it, expect, afterEach } from "vitest";
import { render, cleanup } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { NotFoundPage } from "./NotFoundPage";

describe("NotFoundPage", () => {
  afterEach(cleanup);

  it("renders the 404 heading", () => {
    const { getByText } = render(
      <MemoryRouter>
        <NotFoundPage />
      </MemoryRouter>,
    );
    expect(getByText("404")).toBeInTheDocument();
  });

  it("renders 'Page not found' subtitle", () => {
    const { getByText } = render(
      <MemoryRouter>
        <NotFoundPage />
      </MemoryRouter>,
    );
    expect(getByText("Page not found")).toBeInTheDocument();
  });

  it("renders a friendly description", () => {
    const { getByText } = render(
      <MemoryRouter>
        <NotFoundPage />
      </MemoryRouter>,
    );
    expect(
      getByText("The page you're looking for doesn't exist or you don't have permission to view it."),
    ).toBeInTheDocument();
  });

  it("renders a 'Go Home' link pointing to /", () => {
    const { getByTestId } = render(
      <MemoryRouter>
        <NotFoundPage />
      </MemoryRouter>,
    );
    const link = getByTestId("go-home-link");
    expect(link).toBeInTheDocument();
    expect(link).toHaveAttribute("href", "/");
    expect(link).toHaveTextContent("Go Home");
  });

  it("renders the CollabMark icon", () => {
    const { container } = render(
      <MemoryRouter>
        <NotFoundPage />
      </MemoryRouter>,
    );
    const svg = container.querySelector("svg");
    expect(svg).toBeInTheDocument();
  });
});
