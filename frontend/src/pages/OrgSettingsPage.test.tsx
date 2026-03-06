import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, fireEvent, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { OrgSettingsPage } from "./OrgSettingsPage";

const { mockOrgsApi, mockUseAuth, mockParams } = vi.hoisted(() => {
  const params: { orgId?: string } = { orgId: "org-123" };
  return {
    mockOrgsApi: {
      get: vi.fn(),
      listMembers: vi.fn(),
      getSSOConfig: vi.fn(),
      update: vi.fn(),
      inviteMember: vi.fn(),
      updateMemberRole: vi.fn(),
      removeMember: vi.fn(),
      updateSSOConfig: vi.fn(),
    },
    mockUseAuth: vi.fn(),
    mockParams: params,
  };
});

const mockOrg = {
  id: "org-123",
  name: "Test Org",
  slug: "test-org",
  verified_domains: ["test.com"],
  plan: "free",
  member_count: 2,
  created_at: "2024-01-01",
  updated_at: "2024-01-01",
};

const mockMembers = [
  {
    id: "m1",
    user_id: "u1",
    user_name: "Alice",
    user_email: "alice@test.com",
    avatar_url: null,
    role: "admin",
    joined_at: "2024-01-01",
  },
  {
    id: "m2",
    user_id: "u2",
    user_name: "Bob",
    user_email: "bob@test.com",
    avatar_url: null,
    role: "member",
    joined_at: "2024-01-02",
  },
];

const mockSSOConfig = {
  id: "sso-1",
  org_id: "org-123",
  protocol: "oidc",
  enabled: true,
  idp_entity_id: null,
  idp_sso_url: null,
  sp_entity_id: null,
  sp_acs_url: null,
  oidc_discovery_url: "https://idp.test.com/.well-known",
  oidc_client_id: "client-id",
  scim_enabled: false,
  created_at: "2024-01-01",
  updated_at: "2024-01-01",
};

vi.mock("../lib/api", () => ({
  orgsApi: mockOrgsApi,
}));

vi.mock("react-router", async (importOriginal) => {
  const actual = await importOriginal<typeof import("react-router")>();
  return {
    ...actual,
    useParams: () => mockParams,
  };
});

vi.mock("../hooks/useAuth", () => ({
  useAuth: () => mockUseAuth(),
}));

vi.mock("../components/Layout/Navbar", () => ({
  Navbar: () => <nav data-testid="navbar">Navbar</nav>,
}));

vi.mock("../components/Layout/UserAvatar", () => ({
  UserAvatar: () => <div data-testid="user-avatar" />,
}));

vi.mock("../lib/dateUtils", () => ({
  formatDateShort: (iso: string) => `formatted:${iso}`,
}));

function renderPage() {
  return render(
    <MemoryRouter>
      <OrgSettingsPage />
    </MemoryRouter>,
  );
}

describe("OrgSettingsPage", () => {
  const originalTitle = document.title;

  beforeEach(() => {
    mockParams.orgId = "org-123";
    mockUseAuth.mockReturnValue({ user: { id: "u1" } });
    mockOrgsApi.get.mockResolvedValue({ data: mockOrg });
    mockOrgsApi.listMembers.mockResolvedValue({ data: mockMembers });
    mockOrgsApi.getSSOConfig.mockResolvedValue({ data: mockSSOConfig });
  });

  afterEach(() => {
    vi.clearAllMocks();
    document.title = originalTitle;
  });

  describe("1. Renders General tab by default with org details", () => {
    it("renders org settings with General tab active and org details", async () => {
      const { getByTestId, getByText, getByDisplayValue } = renderPage();

      await waitFor(() => {
        expect(mockOrgsApi.get).toHaveBeenCalledWith("org-123");
        expect(mockOrgsApi.listMembers).toHaveBeenCalledWith("org-123");
        expect(mockOrgsApi.getSSOConfig).toHaveBeenCalledWith("org-123");
      });

      expect(getByTestId("org-settings")).toBeInTheDocument();
      expect(getByText("Test Org Settings")).toBeInTheDocument();
      expect(getByTestId("tab-general")).toBeInTheDocument();
      expect(getByTestId("tab-members")).toBeInTheDocument();
      expect(getByTestId("tab-sso")).toBeInTheDocument();

      expect(getByDisplayValue("Test Org")).toBeInTheDocument();
      expect(getByDisplayValue("test-org")).toBeInTheDocument();
      expect(getByDisplayValue("test.com")).toBeInTheDocument();
      expect(getByDisplayValue("free")).toBeInTheDocument();
    });
  });

  describe("2. Tab switching", () => {
    it("switches between General, Members, and SSO tabs", async () => {
      const { getByTestId, getByText, getByRole } = renderPage();

      await waitFor(() => {
        expect(mockOrgsApi.get).toHaveBeenCalled();
      });

      expect(getByText("Organization Name")).toBeInTheDocument();

      fireEvent.click(getByTestId("tab-members"));
      expect(getByText("Members (2)")).toBeInTheDocument();
      expect(getByText("Alice")).toBeInTheDocument();
      expect(getByText("Bob")).toBeInTheDocument();

      fireEvent.click(getByTestId("tab-sso"));
      expect(getByTestId("sso-form")).toBeInTheDocument();
      expect(getByRole("heading", { name: /sso configuration/i })).toBeInTheDocument();

      fireEvent.click(getByTestId("tab-general"));
      expect(getByText("Organization Name")).toBeInTheDocument();
    });
  });

  describe("3. General tab: edit org name and save", () => {
    it("edits org name and saves successfully", async () => {
      const updatedOrg = { ...mockOrg, name: "Updated Org Name" };
      mockOrgsApi.update.mockResolvedValue({ data: updatedOrg });

      const { getByDisplayValue, getByRole, getByText } = renderPage();

      await waitFor(() => {
        expect(mockOrgsApi.get).toHaveBeenCalled();
      });

      const nameInput = getByDisplayValue("Test Org");
      fireEvent.change(nameInput, { target: { value: "Updated Org Name" } });
      fireEvent.click(getByRole("button", { name: /save/i }));

      await waitFor(() => {
        expect(mockOrgsApi.update).toHaveBeenCalledWith("org-123", {
          name: "Updated Org Name",
          slug: "test-org",
          verified_domains: ["test.com"],
          plan: "free",
        });
      });

      expect(getByText("Organization updated")).toBeInTheDocument();
    });

    it("shows error toast when general save fails", async () => {
      mockOrgsApi.update.mockRejectedValue(new Error("Network error"));

      const { getByRole, getByText } = renderPage();

      await waitFor(() => {
        expect(mockOrgsApi.get).toHaveBeenCalled();
      });

      fireEvent.click(getByRole("button", { name: /save/i }));

      await waitFor(() => {
        expect(getByText("Failed to update organization")).toBeInTheDocument();
      });
    });
  });

  describe("4. Members tab: renders member list", () => {
    it("renders all members with name, email, role, and joined date", async () => {
      const { getByTestId, getByText } = renderPage();

      await waitFor(() => {
        expect(mockOrgsApi.listMembers).toHaveBeenCalled();
      });

      fireEvent.click(getByTestId("tab-members"));

      expect(getByTestId("member-row-u1")).toBeInTheDocument();
      expect(getByTestId("member-row-u2")).toBeInTheDocument();
      expect(getByText("Alice")).toBeInTheDocument();
      expect(getByText("alice@test.com")).toBeInTheDocument();
      expect(getByText("Bob")).toBeInTheDocument();
      expect(getByText("bob@test.com")).toBeInTheDocument();
      expect(getByText("Joined formatted:2024-01-01")).toBeInTheDocument();
      expect(getByText("Joined formatted:2024-01-02")).toBeInTheDocument();
    });
  });

  describe("5. Members tab: invite member form", () => {
    it("shows invite form when Invite Member is clicked", async () => {
      const { getByTestId, queryByTestId } = renderPage();

      await waitFor(() => {
        expect(mockOrgsApi.get).toHaveBeenCalled();
      });

      fireEvent.click(getByTestId("tab-members"));
      expect(queryByTestId("invite-form")).not.toBeInTheDocument();

      fireEvent.click(getByTestId("invite-member-btn"));
      expect(getByTestId("invite-form")).toBeInTheDocument();
    });

    it("hides invite form when Cancel is clicked", async () => {
      const { getByTestId, getByRole, queryByTestId } = renderPage();

      await waitFor(() => {
        expect(mockOrgsApi.get).toHaveBeenCalled();
      });

      fireEvent.click(getByTestId("tab-members"));
      fireEvent.click(getByTestId("invite-member-btn"));
      expect(getByTestId("invite-form")).toBeInTheDocument();

      fireEvent.click(getByRole("button", { name: /cancel/i }));
      expect(queryByTestId("invite-form")).not.toBeInTheDocument();
    });
  });

  describe("6. Members tab: invite member by email", () => {
    it("invites member successfully and shows success toast", async () => {
      const newMember = {
        id: "m3",
        user_id: "u3",
        user_name: "Charlie",
        user_email: "charlie@test.com",
        avatar_url: null,
        role: "member",
        joined_at: "2024-01-03",
      };
      mockOrgsApi.inviteMember.mockResolvedValue({ data: newMember });

      const { getByTestId, getByPlaceholderText, getByRole, getByText } = renderPage();

      await waitFor(() => {
        expect(mockOrgsApi.get).toHaveBeenCalled();
      });

      fireEvent.click(getByTestId("tab-members"));
      fireEvent.click(getByTestId("invite-member-btn"));

      const emailInput = getByPlaceholderText("colleague@example.com");
      fireEvent.change(emailInput, { target: { value: "charlie@test.com" } });
      fireEvent.click(getByRole("button", { name: /send invite/i }));

      await waitFor(() => {
        expect(mockOrgsApi.inviteMember).toHaveBeenCalledWith("org-123", {
          email: "charlie@test.com",
          role: "member",
        });
      });

      expect(getByText("Invitation sent")).toBeInTheDocument();
      expect(getByText("Charlie")).toBeInTheDocument();
    });

    it("invites member with admin role when selected", async () => {
      const newMember = {
        id: "m3",
        user_id: "u3",
        user_name: "Admin User",
        user_email: "admin@test.com",
        avatar_url: null,
        role: "admin",
        joined_at: "2024-01-03",
      };
      mockOrgsApi.inviteMember.mockResolvedValue({ data: newMember });

      const { getByTestId, getByPlaceholderText, getByRole } = renderPage();

      await waitFor(() => {
        expect(mockOrgsApi.get).toHaveBeenCalled();
      });

      fireEvent.click(getByTestId("tab-members"));
      fireEvent.click(getByTestId("invite-member-btn"));

      const inviteForm = getByTestId("invite-form");
      const emailInput = getByPlaceholderText("colleague@example.com");
      fireEvent.change(emailInput, { target: { value: "admin@test.com" } });
      const roleSelect = within(inviteForm).getByRole("combobox");
      fireEvent.change(roleSelect, { target: { value: "admin" } });
      fireEvent.click(getByRole("button", { name: /send invite/i }));

      await waitFor(() => {
        expect(mockOrgsApi.inviteMember).toHaveBeenCalledWith("org-123", {
          email: "admin@test.com",
          role: "admin",
        });
      });
    });

    it("shows error toast when invite fails", async () => {
      mockOrgsApi.inviteMember.mockRejectedValue(new Error("Invite failed"));

      const { getByTestId, getByPlaceholderText, getByRole, getByText } = renderPage();

      await waitFor(() => {
        expect(mockOrgsApi.get).toHaveBeenCalled();
      });

      fireEvent.click(getByTestId("tab-members"));
      fireEvent.click(getByTestId("invite-member-btn"));

      const emailInput = getByPlaceholderText("colleague@example.com");
      fireEvent.change(emailInput, { target: { value: "fail@test.com" } });
      fireEvent.click(getByRole("button", { name: /send invite/i }));

      await waitFor(() => {
        expect(getByText("Failed to send invitation")).toBeInTheDocument();
      });
    });

    it("does not invite when email is empty", async () => {
      const { getByTestId, getByRole } = renderPage();

      await waitFor(() => {
        expect(mockOrgsApi.get).toHaveBeenCalled();
      });

      fireEvent.click(getByTestId("tab-members"));
      fireEvent.click(getByTestId("invite-member-btn"));

      const sendBtn = getByRole("button", { name: /send invite/i });
      expect(sendBtn).toBeDisabled();
      fireEvent.click(sendBtn);
      expect(mockOrgsApi.inviteMember).not.toHaveBeenCalled();
    });
  });

  describe("7. Members tab: change member role", () => {
    it("updates member role and shows success toast", async () => {
      const updatedMember = { ...mockMembers[1], role: "admin" as const };
      mockOrgsApi.updateMemberRole.mockResolvedValue({ data: updatedMember });

      const { getByTestId, getByText } = renderPage();

      await waitFor(() => {
        expect(mockOrgsApi.listMembers).toHaveBeenCalled();
      });

      fireEvent.click(getByTestId("tab-members"));

      const bobRoleSelect = getByTestId("member-row-u2").querySelector("select");
      expect(bobRoleSelect).toBeInTheDocument();
      fireEvent.change(bobRoleSelect!, { target: { value: "admin" } });

      await waitFor(() => {
        expect(mockOrgsApi.updateMemberRole).toHaveBeenCalledWith("org-123", "u2", "admin");
      });

      expect(getByText("Role updated")).toBeInTheDocument();
    });

    it("shows error toast when role update fails", async () => {
      mockOrgsApi.updateMemberRole.mockRejectedValue(new Error("Update failed"));

      const { getByTestId, getByText } = renderPage();

      await waitFor(() => {
        expect(mockOrgsApi.listMembers).toHaveBeenCalled();
      });

      fireEvent.click(getByTestId("tab-members"));

      const bobRoleSelect = getByTestId("member-row-u2").querySelector("select");
      fireEvent.change(bobRoleSelect!, { target: { value: "admin" } });

      await waitFor(() => {
        expect(getByText("Failed to update role")).toBeInTheDocument();
      });
    });
  });

  describe("8. Members tab: remove member", () => {
    it("removes member and shows success toast", async () => {
      mockOrgsApi.removeMember.mockResolvedValue(undefined);

      const { getByTestId, getByText, queryByTestId } = renderPage();

      await waitFor(() => {
        expect(mockOrgsApi.listMembers).toHaveBeenCalled();
      });

      fireEvent.click(getByTestId("tab-members"));

      const bobRow = getByTestId("member-row-u2");
      const removeBtn = bobRow.querySelector('button[title="Remove member"]');
      expect(removeBtn).toBeInTheDocument();
      fireEvent.click(removeBtn!);

      await waitFor(() => {
        expect(mockOrgsApi.removeMember).toHaveBeenCalledWith("org-123", "u2");
      });

      expect(getByText("Member removed")).toBeInTheDocument();
      expect(queryByTestId("member-row-u2")).not.toBeInTheDocument();
    });

    it("cannot remove self (current user)", async () => {
      const { getByTestId } = renderPage();

      await waitFor(() => {
        expect(mockOrgsApi.listMembers).toHaveBeenCalled();
      });

      fireEvent.click(getByTestId("tab-members"));

      const aliceRow = getByTestId("member-row-u1");
      const removeBtn = aliceRow.querySelector('button[title="Cannot remove yourself"]');
      expect(removeBtn).toBeInTheDocument();
      expect(removeBtn).toBeDisabled();
      fireEvent.click(removeBtn!);
      expect(mockOrgsApi.removeMember).not.toHaveBeenCalled();
    });

    it("shows error toast when remove fails", async () => {
      mockOrgsApi.removeMember.mockRejectedValue(new Error("Remove failed"));

      const { getByTestId, getByText } = renderPage();

      await waitFor(() => {
        expect(mockOrgsApi.listMembers).toHaveBeenCalled();
      });

      fireEvent.click(getByTestId("tab-members"));

      const bobRow = getByTestId("member-row-u2");
      const removeBtn = bobRow.querySelector('button[title="Remove member"]');
      fireEvent.click(removeBtn!);

      await waitFor(() => {
        expect(getByText("Failed to remove member")).toBeInTheDocument();
      });
    });
  });

  describe("9. SSO tab: renders current config", () => {
    it("renders SSO config status and form with OIDC values", async () => {
      const { getByTestId, getByText, getByDisplayValue } = renderPage();

      await waitFor(() => {
        expect(mockOrgsApi.getSSOConfig).toHaveBeenCalled();
      });

      fireEvent.click(getByTestId("tab-sso"));

      expect(getByText("Configured & Enabled")).toBeInTheDocument();
      expect(getByDisplayValue("https://idp.test.com/.well-known")).toBeInTheDocument();
      expect(getByDisplayValue("client-id")).toBeInTheDocument();
    });

    it("shows Not configured when no SSO config", async () => {
      mockOrgsApi.getSSOConfig.mockResolvedValue({ data: null });

      const { getByTestId, getByText } = renderPage();

      await waitFor(() => {
        expect(mockOrgsApi.getSSOConfig).toHaveBeenCalled();
      });

      fireEvent.click(getByTestId("tab-sso"));

      expect(getByText("Not configured")).toBeInTheDocument();
    });
  });

  describe("10. SSO tab: toggle between SAML and OIDC", () => {
    it("shows SAML fields when SAML is selected", async () => {
      const { getByTestId, getByDisplayValue, getByText } = renderPage();

      await waitFor(() => {
        expect(mockOrgsApi.getSSOConfig).toHaveBeenCalled();
      });

      fireEvent.click(getByTestId("tab-sso"));

      const protocolSelect = getByDisplayValue("OIDC");
      fireEvent.change(protocolSelect, { target: { value: "saml" } });

      expect(getByText("IdP Entity ID")).toBeInTheDocument();
      expect(getByText("IdP SSO URL")).toBeInTheDocument();
      expect(getByText("SP Entity ID")).toBeInTheDocument();
      expect(getByText("SP ACS URL")).toBeInTheDocument();
    });

    it("shows OIDC fields when OIDC is selected", async () => {
      mockOrgsApi.getSSOConfig.mockResolvedValue({
        data: { ...mockSSOConfig, protocol: "saml" },
      });

      const { getByTestId, getByDisplayValue, getByText } = renderPage();

      await waitFor(() => {
        expect(mockOrgsApi.getSSOConfig).toHaveBeenCalled();
      });

      fireEvent.click(getByTestId("tab-sso"));

      const protocolSelect = getByDisplayValue("SAML 2.0");
      fireEvent.change(protocolSelect, { target: { value: "oidc" } });

      expect(getByText("Discovery URL")).toBeInTheDocument();
      expect(getByText("Client ID")).toBeInTheDocument();
      expect(getByText("Client Secret")).toBeInTheDocument();
    });
  });

  describe("11. SSO tab: save SSO configuration", () => {
    it("saves OIDC config and shows success toast", async () => {
      const savedConfig = { ...mockSSOConfig, updated_at: "2024-01-02" };
      mockOrgsApi.updateSSOConfig.mockResolvedValue({ data: savedConfig });

      const { getByTestId, getByText } = renderPage();

      await waitFor(() => {
        expect(mockOrgsApi.getSSOConfig).toHaveBeenCalled();
      });

      fireEvent.click(getByTestId("tab-sso"));
      fireEvent.submit(getByTestId("sso-form"));

      await waitFor(() => {
        expect(mockOrgsApi.updateSSOConfig).toHaveBeenCalledWith("org-123", {
          protocol: "oidc",
          enabled: true,
          oidc_discovery_url: "https://idp.test.com/.well-known",
          oidc_client_id: "client-id",
        });
      });

      expect(getByText("SSO configuration saved")).toBeInTheDocument();
    });

    it("saves SAML config with SAML fields", async () => {
      mockOrgsApi.getSSOConfig.mockResolvedValue({
        data: { ...mockSSOConfig, protocol: "saml" },
      });
      mockOrgsApi.updateSSOConfig.mockResolvedValue({ data: mockSSOConfig });

      const { getByTestId, getByDisplayValue, getByPlaceholderText } = renderPage();

      await waitFor(() => {
        expect(mockOrgsApi.getSSOConfig).toHaveBeenCalled();
      });

      fireEvent.click(getByTestId("tab-sso"));

      const protocolSelect = getByDisplayValue("SAML 2.0");
      expect(protocolSelect).toBeInTheDocument();

      fireEvent.change(getByPlaceholderText("https://idp.example.com/entity"), {
        target: { value: "https://idp.example.com/entity" },
      });
      fireEvent.change(getByPlaceholderText("https://idp.example.com/sso"), {
        target: { value: "https://idp.example.com/sso" },
      });

      fireEvent.submit(getByTestId("sso-form"));

      await waitFor(() => {
        expect(mockOrgsApi.updateSSOConfig).toHaveBeenCalledWith("org-123", {
          protocol: "saml",
          enabled: true,
          idp_entity_id: "https://idp.example.com/entity",
          idp_sso_url: "https://idp.example.com/sso",
          idp_certificate: null,
          sp_entity_id: null,
          sp_acs_url: null,
        });
      });
    });

    it("shows error toast when SSO save fails", async () => {
      mockOrgsApi.updateSSOConfig.mockRejectedValue(new Error("Save failed"));

      const { getByTestId, getByText } = renderPage();

      await waitFor(() => {
        expect(mockOrgsApi.getSSOConfig).toHaveBeenCalled();
      });

      fireEvent.click(getByTestId("tab-sso"));
      fireEvent.submit(getByTestId("sso-form"));

      await waitFor(() => {
        expect(getByText("Failed to save SSO configuration")).toBeInTheDocument();
      });
    });
  });

  describe("12. SSO tab: enable/disable toggle", () => {
    it("toggles SSO enabled checkbox", async () => {
      const { getByTestId, getByRole } = renderPage();

      await waitFor(() => {
        expect(mockOrgsApi.getSSOConfig).toHaveBeenCalled();
      });

      fireEvent.click(getByTestId("tab-sso"));

      const enableCheckbox = getByRole("checkbox", { name: /enable sso/i });
      expect(enableCheckbox).toBeChecked();

      fireEvent.click(enableCheckbox);
      expect(enableCheckbox).not.toBeChecked();

      fireEvent.submit(getByTestId("sso-form"));

      await waitFor(() => {
        expect(mockOrgsApi.updateSSOConfig).toHaveBeenCalledWith(
          "org-123",
          expect.objectContaining({ enabled: false }),
        );
      });
    });
  });

  describe("13. Loading states", () => {
    it("shows loading spinner while fetching data", () => {
      mockOrgsApi.get.mockImplementation(() => new Promise(() => {}));
      mockOrgsApi.listMembers.mockImplementation(() => new Promise(() => {}));
      mockOrgsApi.getSSOConfig.mockImplementation(() => new Promise(() => {}));

      const { container } = renderPage();

      expect(container.querySelector(".animate-spin")).toBeInTheDocument();
      expect(mockOrgsApi.get).toHaveBeenCalled();
    });

    it("disables Save button while saving general", async () => {
      mockOrgsApi.update.mockImplementation(() => new Promise(() => {}));

      const { getByRole } = renderPage();

      await waitFor(() => {
        expect(mockOrgsApi.get).toHaveBeenCalled();
      });

      const saveBtn = getByRole("button", { name: /save/i });
      fireEvent.click(saveBtn);

      await waitFor(() => {
        expect(saveBtn).toBeDisabled();
      });
    });
  });

  describe("14. Error handling for API failures", () => {
    it("shows error toast when initial load fails", async () => {
      mockOrgsApi.get.mockRejectedValue(new Error("Load failed"));

      const { getByText } = renderPage();

      await waitFor(() => {
        expect(getByText("Failed to load organization data")).toBeInTheDocument();
      });
    });

    it("shows Organization not found when orgId is missing", async () => {
      mockParams.orgId = undefined;
      const { getByText } = render(
        <MemoryRouter>
          <OrgSettingsPage />
        </MemoryRouter>,
      );

      await waitFor(() => {
        expect(getByText("Organization not found.")).toBeInTheDocument();
      });

      mockParams.orgId = "org-123";
    });
  });
});
