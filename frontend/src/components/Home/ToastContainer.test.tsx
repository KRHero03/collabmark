import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { render, fireEvent, cleanup } from "@testing-library/react";
import { ToastContainer } from "./ToastContainer";
import { useToast } from "../../hooks/useToast";
import type { Toast } from "../../hooks/useToast";

function makeToast(overrides: Partial<Toast> & { id: string }): Toast {
  return {
    message: "Test",
    type: "success",
    phase: "visible",
    ...overrides,
  };
}

describe("ToastContainer", () => {
  beforeEach(() => {
    useToast.setState({ toasts: [] });
  });

  afterEach(cleanup);

  it("renders nothing when there are no toasts", () => {
    const { container } = render(<ToastContainer />);
    expect(container.innerHTML).toBe("");
  });

  it("renders a success toast", () => {
    useToast.setState({
      toasts: [makeToast({ id: "1", message: "Document deleted", type: "success" })],
    });
    const { getByText, getByTestId } = render(<ToastContainer />);
    expect(getByText("Document deleted")).toBeTruthy();
    expect(getByTestId("toast-success")).toBeTruthy();
  });

  it("renders an error toast", () => {
    useToast.setState({
      toasts: [makeToast({ id: "1", message: "Failed. Please try again.", type: "error" })],
    });
    const { getByText, getByTestId } = render(<ToastContainer />);
    expect(getByText("Failed. Please try again.")).toBeTruthy();
    expect(getByTestId("toast-error")).toBeTruthy();
  });

  it("renders multiple toasts", () => {
    useToast.setState({
      toasts: [
        makeToast({ id: "1", message: "First", type: "success" }),
        makeToast({ id: "2", message: "Second", type: "error" }),
      ],
    });
    const { getByText } = render(<ToastContainer />);
    expect(getByText("First")).toBeTruthy();
    expect(getByText("Second")).toBeTruthy();
  });

  it("removes toast when dismiss button is clicked", () => {
    useToast.setState({
      toasts: [makeToast({ id: "1", message: "Dismiss me" })],
    });
    const { getByLabelText } = render(<ToastContainer />);
    fireEvent.click(getByLabelText("Dismiss"));
  });

  it("success toast has green styling", () => {
    useToast.setState({
      toasts: [makeToast({ id: "1", message: "OK", type: "success" })],
    });
    const { getByTestId } = render(<ToastContainer />);
    expect(getByTestId("toast-success").className).toContain("bg-green-600");
  });

  it("error toast has red styling", () => {
    useToast.setState({
      toasts: [makeToast({ id: "1", message: "Fail", type: "error" })],
    });
    const { getByTestId } = render(<ToastContainer />);
    expect(getByTestId("toast-error").className).toContain("bg-red-600");
  });

  it("renders fixed at bottom-right", () => {
    useToast.setState({
      toasts: [makeToast({ id: "1", message: "Positioned" })],
    });
    const { container } = render(<ToastContainer />);
    const wrapper = container.firstChild as HTMLElement;
    expect(wrapper.className).toContain("fixed");
    expect(wrapper.className).toContain("bottom-4");
    expect(wrapper.className).toContain("right-4");
  });

  it("uses flex-col-reverse for newest-on-top stacking", () => {
    useToast.setState({
      toasts: [makeToast({ id: "1", message: "A" })],
    });
    const { container } = render(<ToastContainer />);
    const wrapper = container.firstChild as HTMLElement;
    expect(wrapper.className).toContain("flex-col-reverse");
  });

  it("applies entering phase class for off-screen position", () => {
    useToast.setState({
      toasts: [makeToast({ id: "1", phase: "entering" })],
    });
    const { getByTestId } = render(<ToastContainer />);
    const el = getByTestId("toast-success");
    expect(el.className).toContain("translate-x-full");
    expect(el.className).toContain("opacity-0");
  });

  it("applies visible phase class for on-screen position", () => {
    useToast.setState({
      toasts: [makeToast({ id: "1", phase: "visible" })],
    });
    const { getByTestId } = render(<ToastContainer />);
    const el = getByTestId("toast-success");
    expect(el.className).toContain("translate-x-0");
    expect(el.className).toContain("opacity-100");
  });

  it("applies exiting phase class", () => {
    useToast.setState({
      toasts: [makeToast({ id: "1", phase: "exiting" })],
    });
    const { getByTestId } = render(<ToastContainer />);
    const el = getByTestId("toast-success");
    expect(el.className).toContain("translate-x-full");
    expect(el.className).toContain("opacity-0");
  });

  it("includes transition duration classes", () => {
    useToast.setState({
      toasts: [makeToast({ id: "1" })],
    });
    const { getByTestId } = render(<ToastContainer />);
    const el = getByTestId("toast-success");
    expect(el.className).toContain("duration-300");
    expect(el.className).toContain("ease-in-out");
  });

  it("exposes data-phase attribute for testing", () => {
    useToast.setState({
      toasts: [makeToast({ id: "1", phase: "visible" })],
    });
    const { getByTestId } = render(<ToastContainer />);
    expect(getByTestId("toast-success").getAttribute("data-phase")).toBe("visible");
  });
});
