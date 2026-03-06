import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, fireEvent, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { SuperAdminPage } from "./SuperAdminPage";

const mockList = vi.fn();
const mockCreate = vi.fn();
const mockUpdate = vi.fn();
const mockListMembers = vi.fn();

vi.mock("../lib/api", () => ({
  orgsApi: {
    list: (...args: unknown[]) => mockList(...args),
    create: (...args: unknown[]) => mockCreate(...args),
    update: (...args: unknown[]) => mockUpdate(...args),
    listMembers: (...args: unknown[]) => mockListMembers(...args),
  },
}));

const mockAddToast = vi.fn();
vi.mock("../hooks/useToast", () => ({
  useToast: () => ({ addToast: mockAddToast }),
}));

vi.mock("../lib/dateUtils", () => ({
  formatDateShort: (iso: string) => `formatted:${iso}`,
}));

vi.mock("../components/Home/ToastContainer", () => ({
  ToastContainer: () => <div data-testid="toast-container" />,
}));

function renderPage() {
  return render(
    <MemoryRouter>
      <SuperAdminPage />
    </MemoryRouter>,
  );
}

const mockOrgs = [
  {
    id: "org-1",
    name: "Acme Inc",
    slug: "acme-inc",
    verified_domains: ["acme.com"],
    plan: "pro",
    member_count: 5,
    created_at: "2025-01-15T10:00:00Z",
    updated_at: "2025-01-15T10:00:00Z",
  },
  {
    id: "org-2",
    name: "Beta Corp",
    slug: "beta-corp",
    verified_domains: [],
    plan: "free",
    member_count: 0,
    created_at: "2025-02-01T00:00:00Z",
    updated_at: "2025-02-01T00:00:00Z",
  },
];

const mockMembers = [
  {
    id: "mem-1",
    user_id: "user-1",
    user_name: "Alice User",
    user_email: "alice@acme.com",
    avatar_url: null,
    role: "admin" as const,
    joined_at: "2025-01-15T10:00:00Z",
  },
];

describe("SuperAdminPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockList.mockResolvedValue({ data: [] });
  });

  it("renders the dashboard title and create button", async () => {
    const { getByText, getByTestId } = renderPage();

    await waitFor(() => {
      expect(mockList).toHaveBeenCalled();
    });

    expect(getByText("Admin Dashboard")).toBeInTheDocument();
    expect(getByText("Manage organizations and platform settings")).toBeInTheDocument();
    expect(getByTestId("create-org-btn")).toBeInTheDocument();
    expect(getByText("Create Organization")).toBeInTheDocument();
  });

  it("shows generic loading spinner while orgs are fetching (no admin UI visible)", () => {
    mockList.mockImplementation(() => new Promise(() => {}));

    const { queryByTestId, container } = renderPage();

    expect(queryByTestId("admin-dashboard")).not.toBeInTheDocument();
    const spinner = container.querySelector(".animate-spin");
    expect(spinner).toBeInTheDocument();
  });

  it("renders org list after data loads", async () => {
    mockList.mockResolvedValue({ data: mockOrgs });

    const { getAllByText, getAllByTestId } = renderPage();

    await waitFor(() => {
      expect(mockList).toHaveBeenCalled();
    });

    await waitFor(() => {
      expect(getAllByText("Acme Inc").length).toBeGreaterThanOrEqual(1);
      expect(getAllByText("Beta Corp").length).toBeGreaterThanOrEqual(1);
      expect(getAllByText("acme-inc").length).toBeGreaterThanOrEqual(1);
      expect(getAllByText("beta-corp").length).toBeGreaterThanOrEqual(1);
      expect(getAllByText("acme.com").length).toBeGreaterThanOrEqual(1);
      expect(getAllByText("pro").length).toBeGreaterThanOrEqual(1);
      expect(getAllByText("free").length).toBeGreaterThanOrEqual(1);
    });

    expect(getAllByTestId("org-row-org-1").length).toBeGreaterThanOrEqual(1);
    expect(getAllByTestId("org-row-org-2").length).toBeGreaterThanOrEqual(1);
  });

  it("create org form: opens on button click, submits, and refreshes list", async () => {
    mockList.mockResolvedValueOnce({ data: [] }).mockResolvedValueOnce({ data: mockOrgs });
    mockCreate.mockResolvedValue({ data: mockOrgs[0] });

    const { getByTestId, getByText, getByPlaceholderText, queryByTestId } = renderPage();

    await waitFor(() => expect(mockList).toHaveBeenCalled());

    fireEvent.click(getByTestId("create-org-btn"));

    await waitFor(() => {
      expect(getByTestId("create-org-form")).toBeInTheDocument();
    });

    expect(getByText("New Organization")).toBeInTheDocument();

    fireEvent.change(getByPlaceholderText("Acme Inc"), {
      target: { value: "New Org" },
    });
    fireEvent.change(getByPlaceholderText("acme-inc"), {
      target: { value: "new-org" },
    });
    fireEvent.click(getByText("Create"));

    await waitFor(() => {
      expect(mockCreate).toHaveBeenCalledWith({
        name: "New Org",
        slug: "new-org",
        verified_domains: undefined,
        plan: "free",
      });
    });

    await waitFor(() => {
      expect(mockAddToast).toHaveBeenCalledWith("Organization created", "success");
    });

    await waitFor(() => {
      expect(mockList).toHaveBeenCalledTimes(2);
    });

    await waitFor(() => {
      expect(queryByTestId("create-org-form")).not.toBeInTheDocument();
    });
  });

  it("create org form: shows error for duplicate slug", async () => {
    mockList.mockResolvedValue({ data: [] });
    mockCreate.mockRejectedValueOnce(new Error("Slug already exists"));

    const { getByTestId, getByText, getByPlaceholderText } = renderPage();

    await waitFor(() => expect(mockList).toHaveBeenCalled());

    fireEvent.click(getByTestId("create-org-btn"));

    await waitFor(() => {
      expect(getByTestId("create-org-form")).toBeInTheDocument();
    });

    fireEvent.change(getByPlaceholderText("Acme Inc"), {
      target: { value: "New Org" },
    });
    fireEvent.change(getByPlaceholderText("acme-inc"), {
      target: { value: "new-org" },
    });
    fireEvent.click(getByText("Create"));

    await waitFor(() => {
      expect(mockAddToast).toHaveBeenCalledWith("Slug already exists", "error");
    });

    expect(mockList).toHaveBeenCalledTimes(1);
  });

  it("edit org: toggles edit form, saves changes", async () => {
    mockList.mockResolvedValue({ data: mockOrgs });
    mockUpdate.mockResolvedValue({ data: { ...mockOrgs[0], name: "Acme Updated" } });

    const { getAllByText, getAllByTestId } = renderPage();

    await waitFor(() => {
      expect(getAllByText("Acme Inc").length).toBeGreaterThanOrEqual(1);
    });

    const orgRows = getAllByTestId("org-row-org-1");
    const orgRow = orgRows[0];
    const editBtn = within(orgRow).getByTitle("Edit");
    fireEvent.click(editBtn);

    await waitFor(() => {
      const nameInput = within(orgRow).getByDisplayValue("Acme Inc");
      expect(nameInput).toBeInTheDocument();
    });

    const nameInput = within(orgRow).getByDisplayValue("Acme Inc");
    fireEvent.change(nameInput, { target: { value: "Acme Updated" } });

    const saveBtn = within(orgRow).getByText("Save");
    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(mockUpdate).toHaveBeenCalledWith("org-1", {
        name: "Acme Updated",
        slug: "acme-inc",
        verified_domains: ["acme.com"],
        plan: "pro",
      });
    });

    await waitFor(() => {
      expect(mockAddToast).toHaveBeenCalledWith("Organization updated", "success");
    });

    await waitFor(() => {
      expect(mockList).toHaveBeenCalledTimes(2);
    });
  });

  it("view members: expands to show member list", async () => {
    mockList.mockResolvedValue({ data: mockOrgs });
    mockListMembers.mockResolvedValue({ data: mockMembers });

    const { getAllByText, getAllByTestId } = renderPage();

    await waitFor(() => {
      expect(getAllByText("Acme Inc").length).toBeGreaterThanOrEqual(1);
    });

    const orgRows = getAllByTestId("org-row-org-1");
    const orgRow = orgRows[0];
    const membersBtn = within(orgRow).getByTitle("View Members");
    fireEvent.click(membersBtn);

    await waitFor(() => {
      expect(mockListMembers).toHaveBeenCalledWith("org-1");
    });

    await waitFor(() => {
      const memberLists = getAllByTestId("member-list-org-1");
      expect(memberLists.length).toBeGreaterThanOrEqual(1);
    });

    await waitFor(() => {
      expect(getAllByText("Members").length).toBeGreaterThanOrEqual(1);
      expect(getAllByText("Alice User").length).toBeGreaterThanOrEqual(1);
      expect(getAllByText("alice@acme.com").length).toBeGreaterThanOrEqual(1);
      expect(getAllByText("admin").length).toBeGreaterThanOrEqual(1);
    });
  });

  it("shows error state when API fails", async () => {
    mockList.mockRejectedValueOnce(new Error("Network error"));

    renderPage();

    await waitFor(() => {
      expect(mockAddToast).toHaveBeenCalledWith("Network error", "error");
    });
  });

  it("shows error state when API fails with non-Error object", async () => {
    mockList.mockRejectedValueOnce("Unknown error");

    renderPage();

    await waitFor(() => {
      expect(mockAddToast).toHaveBeenCalledWith("Failed to load organizations", "error");
    });
  });

  it("renders NotFoundPage when API returns 403", async () => {
    mockList.mockRejectedValueOnce({ response: { status: 403 } });

    const { getByText, getByTestId, queryByTestId } = renderPage();

    await waitFor(() => {
      expect(getByText("404")).toBeInTheDocument();
      expect(getByText("Page not found")).toBeInTheDocument();
      expect(getByTestId("go-home-link")).toBeInTheDocument();
    });

    expect(queryByTestId("admin-dashboard")).not.toBeInTheDocument();
    expect(mockAddToast).not.toHaveBeenCalled();
  });

  it("slug auto-generation from name", async () => {
    mockList.mockResolvedValue({ data: [] });

    const { getByTestId, getByPlaceholderText } = renderPage();

    await waitFor(() => expect(mockList).toHaveBeenCalled());

    fireEvent.click(getByTestId("create-org-btn"));

    await waitFor(() => {
      expect(getByTestId("create-org-form")).toBeInTheDocument();
    });

    const nameInput = getByPlaceholderText("Acme Inc");
    fireEvent.change(nameInput, { target: { value: "My Company Inc" } });

    const slugInput = getByPlaceholderText("acme-inc");
    expect(slugInput).toHaveValue("my-company-inc");
  });

  it("slug auto-updates when name changes and slug was auto-generated", async () => {
    mockList.mockResolvedValue({ data: [] });

    const { getByTestId, getByPlaceholderText } = renderPage();

    await waitFor(() => expect(mockList).toHaveBeenCalled());

    fireEvent.click(getByTestId("create-org-btn"));

    await waitFor(() => {
      expect(getByTestId("create-org-form")).toBeInTheDocument();
    });

    const nameInput = getByPlaceholderText("Acme Inc");
    fireEvent.change(nameInput, { target: { value: "First" } });

    const slugInput = getByPlaceholderText("acme-inc");
    expect(slugInput).toHaveValue("first");

    fireEvent.change(nameInput, { target: { value: "Second Name" } });
    expect(slugInput).toHaveValue("second-name");
  });

  it("slug does not auto-update when user has manually edited it", async () => {
    mockList.mockResolvedValue({ data: [] });

    const { getByTestId, getByPlaceholderText } = renderPage();

    await waitFor(() => expect(mockList).toHaveBeenCalled());

    fireEvent.click(getByTestId("create-org-btn"));

    await waitFor(() => {
      expect(getByTestId("create-org-form")).toBeInTheDocument();
    });

    const nameInput = getByPlaceholderText("Acme Inc");
    const slugInput = getByPlaceholderText("acme-inc");

    fireEvent.change(nameInput, { target: { value: "My Company" } });
    expect(slugInput).toHaveValue("my-company");

    fireEvent.change(slugInput, { target: { value: "custom-slug" } });
    fireEvent.change(nameInput, { target: { value: "Different Name" } });

    expect(slugInput).toHaveValue("custom-slug");
  });

  it("create form validates name and slug required", async () => {
    mockList.mockResolvedValue({ data: [] });

    const { getByTestId, getByText } = renderPage();

    await waitFor(() => expect(mockList).toHaveBeenCalled());

    fireEvent.click(getByTestId("create-org-btn"));

    await waitFor(() => {
      expect(getByTestId("create-org-form")).toBeInTheDocument();
    });

    fireEvent.click(getByText("Create"));

    await waitFor(() => {
      expect(mockAddToast).toHaveBeenCalledWith("Name and slug are required", "error");
    });

    expect(mockCreate).not.toHaveBeenCalled();
  });

  it("create form sends domains when provided", async () => {
    mockList.mockResolvedValue({ data: [] });
    mockCreate.mockResolvedValue({ data: mockOrgs[0] });

    const { getByTestId, getByText, getByPlaceholderText } = renderPage();

    await waitFor(() => expect(mockList).toHaveBeenCalled());

    fireEvent.click(getByTestId("create-org-btn"));

    await waitFor(() => {
      expect(getByTestId("create-org-form")).toBeInTheDocument();
    });

    fireEvent.change(getByPlaceholderText("Acme Inc"), {
      target: { value: "New Org" },
    });
    fireEvent.change(getByPlaceholderText("acme-inc"), {
      target: { value: "new-org" },
    });
    fireEvent.change(getByPlaceholderText("acme.com, acme.io"), {
      target: { value: "example.com, example.io" },
    });

    fireEvent.click(getByText("Create"));

    await waitFor(() => {
      expect(mockCreate).toHaveBeenCalledWith({
        name: "New Org",
        slug: "new-org",
        verified_domains: ["example.com", "example.io"],
        plan: "free",
      });
    });
  });

  it("shows empty state when no orgs", async () => {
    mockList.mockResolvedValue({ data: [] });

    const { getByText } = renderPage();

    await waitFor(() => expect(mockList).toHaveBeenCalled());

    expect(getByText("No organizations yet.")).toBeInTheDocument();
  });

  it("cancel create form closes without submitting", async () => {
    mockList.mockResolvedValue({ data: [] });

    const { getByTestId, getByText, queryByTestId } = renderPage();

    await waitFor(() => expect(mockList).toHaveBeenCalled());

    fireEvent.click(getByTestId("create-org-btn"));

    await waitFor(() => {
      expect(getByTestId("create-org-form")).toBeInTheDocument();
    });

    fireEvent.click(getByText("Cancel"));

    await waitFor(() => {
      expect(queryByTestId("create-org-form")).not.toBeInTheDocument();
    });

    expect(mockCreate).not.toHaveBeenCalled();
  });

  it("create org API failure shows error toast", async () => {
    mockList.mockResolvedValue({ data: [] });
    mockCreate.mockRejectedValueOnce(new Error("Failed to create organization"));

    const { getByTestId, getByText, getByPlaceholderText } = renderPage();

    await waitFor(() => expect(mockList).toHaveBeenCalled());

    fireEvent.click(getByTestId("create-org-btn"));

    await waitFor(() => {
      expect(getByTestId("create-org-form")).toBeInTheDocument();
    });

    fireEvent.change(getByPlaceholderText("Acme Inc"), {
      target: { value: "New Org" },
    });
    fireEvent.change(getByPlaceholderText("acme-inc"), {
      target: { value: "new-org" },
    });
    fireEvent.click(getByText("Create"));

    await waitFor(() => {
      expect(mockAddToast).toHaveBeenCalledWith("Failed to create organization", "error");
    });
  });

  it("edit org API failure shows error toast", async () => {
    mockList.mockResolvedValue({ data: mockOrgs });
    mockUpdate.mockRejectedValueOnce(new Error("Update failed"));

    const { getAllByText, getAllByTestId } = renderPage();

    await waitFor(() => expect(getAllByText("Acme Inc").length).toBeGreaterThanOrEqual(1));

    const orgRows = getAllByTestId("org-row-org-1");
    const orgRow = orgRows[0];
    fireEvent.click(within(orgRow).getByTitle("Edit"));

    await waitFor(() => {
      expect(within(orgRow).getByDisplayValue("Acme Inc")).toBeInTheDocument();
    });

    fireEvent.click(within(orgRow).getByText("Save"));

    await waitFor(() => {
      expect(mockAddToast).toHaveBeenCalledWith("Update failed", "error");
    });
  });

  it("view members: shows loading then empty when no members", async () => {
    mockList.mockResolvedValue({ data: mockOrgs });
    mockListMembers.mockResolvedValue({ data: [] });

    const { getAllByText, getAllByTestId } = renderPage();

    await waitFor(() => expect(getAllByText("Acme Inc").length).toBeGreaterThanOrEqual(1));

    const orgRows = getAllByTestId("org-row-org-1");
    const orgRow = orgRows[0];
    fireEvent.click(within(orgRow).getByTitle("View Members"));

    await waitFor(() => {
      expect(getAllByTestId("member-list-org-1").length).toBeGreaterThanOrEqual(1);
    });

    await waitFor(() => {
      expect(getAllByText("No members").length).toBeGreaterThanOrEqual(1);
    });
  });

  it("view members: API failure shows error toast", async () => {
    mockList.mockResolvedValue({ data: mockOrgs });
    mockListMembers.mockRejectedValueOnce(new Error("Failed to load members"));

    const { getAllByText, getAllByTestId } = renderPage();

    await waitFor(() => expect(getAllByText("Acme Inc").length).toBeGreaterThanOrEqual(1));

    const orgRows = getAllByTestId("org-row-org-1");
    const orgRow = orgRows[0];
    fireEvent.click(within(orgRow).getByTitle("View Members"));

    await waitFor(() => {
      expect(mockAddToast).toHaveBeenCalledWith("Failed to load members", "error");
    });
  });
});
