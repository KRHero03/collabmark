import { useCallback, useState } from "react";
import { groupsApi, type Collaborator, type GroupCollaborator } from "../lib/api";

export interface ShareCollaboratorApi {
  listCollaborators: (entityId: string) => Promise<{ data: Collaborator[] }>;
  addCollaborator: (entityId: string, data: { email: string; permission: "view" | "edit" }) => Promise<unknown>;
  removeCollaborator: (entityId: string, userId: string) => Promise<unknown>;
  listGroupCollaborators: (entityId: string) => Promise<{ data: GroupCollaborator[] }>;
  addGroupCollaborator: (entityId: string, data: { group_id: string; permission: "view" | "edit" }) => Promise<unknown>;
  removeGroupCollaborator: (entityId: string, groupId: string) => Promise<unknown>;
}

export function useShareCollaborators(
  entityId: string,
  isOwner: boolean,
  api: ShareCollaboratorApi,
  orgId?: string | null,
) {
  const [collaborators, setCollaborators] = useState<Collaborator[]>([]);
  const [groupCollaborators, setGroupCollaborators] = useState<GroupCollaborator[]>([]);
  const [groupSearchQuery, setGroupSearchQuery] = useState("");
  const [groupSearchResults, setGroupSearchResults] = useState<Array<{ id: string; name: string }>>([]);
  const [showGroupSearch, setShowGroupSearch] = useState(false);
  const [email, setEmail] = useState("");
  const [permission, setPermission] = useState<"view" | "edit">("view");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const fetchCollaborators = useCallback(async () => {
    if (!isOwner) return;
    try {
      const { data } = await api.listCollaborators(entityId);
      setCollaborators(data);
    } catch {
      setCollaborators([]);
    }
    try {
      const { data } = await api.listGroupCollaborators(entityId);
      setGroupCollaborators(data);
    } catch {
      setGroupCollaborators([]);
    }
  }, [entityId, isOwner, api]);

  const resetOnOpen = useCallback(() => {
    fetchCollaborators();
    setError(null);
  }, [fetchCollaborators]);

  const handleAdd = async () => {
    if (!email.trim()) return;
    setError(null);
    setLoading(true);
    try {
      await api.addCollaborator(entityId, { email: email.trim(), permission });
      setEmail("");
      await fetchCollaborators();
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Failed to add collaborator";
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  const handleRemove = async (userId: string) => {
    await api.removeCollaborator(entityId, userId);
    setCollaborators((prev) => prev.filter((c) => c.user_id !== userId));
  };

  const handleGroupSearch = async (query: string) => {
    setGroupSearchQuery(query);
    if (!orgId || query.length < 2) {
      setGroupSearchResults([]);
      return;
    }
    try {
      const { data } = await groupsApi.search(orgId, query);
      setGroupSearchResults(data.map((g) => ({ id: g.id, name: g.name })));
    } catch {
      setGroupSearchResults([]);
    }
  };

  const handleAddGroup = async (groupId: string) => {
    try {
      await api.addGroupCollaborator(entityId, { group_id: groupId, permission });
      setGroupSearchQuery("");
      setGroupSearchResults([]);
      setShowGroupSearch(false);
      await fetchCollaborators();
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Failed to add group";
      setError(msg);
    }
  };

  const handleRemoveGroup = async (groupId: string) => {
    await api.removeGroupCollaborator(entityId, groupId);
    setGroupCollaborators((prev) => prev.filter((g) => g.group_id !== groupId));
  };

  const handlePermissionChange = async (collaborator: Collaborator, newPerm: "view" | "edit") => {
    if (newPerm === collaborator.permission) return;
    try {
      await api.addCollaborator(entityId, { email: collaborator.email, permission: newPerm });
      setCollaborators((prev) =>
        prev.map((c) => (c.user_id === collaborator.user_id ? { ...c, permission: newPerm } : c)),
      );
    } catch {
      setError("Failed to update permission");
    }
  };

  return {
    collaborators,
    groupCollaborators,
    groupSearchQuery,
    groupSearchResults,
    showGroupSearch,
    setShowGroupSearch,
    email,
    setEmail,
    permission,
    setPermission,
    error,
    setError,
    loading,
    resetOnOpen,
    handleAdd,
    handleRemove,
    handleGroupSearch,
    handleAddGroup,
    handleRemoveGroup,
    handlePermissionChange,
  };
}
