/**
 * Hook that subscribes to Yjs awareness state and returns a deduplicated
 * list of active collaborators (excluding the local client).
 */

import { useEffect, useState, useCallback } from "react";
import type { Awareness } from "y-protocols/awareness";

export interface PresenceUser {
  name: string;
  avatarUrl: string | null;
  color: string;
}

export function usePresence(awareness: Awareness | null): PresenceUser[] {
  const [peers, setPeers] = useState<PresenceUser[]>([]);

  const sync = useCallback(() => {
    if (!awareness) {
      setPeers([]);
      return;
    }

    const localId = awareness.clientID;
    const seen = new Map<string, PresenceUser>();

    awareness.getStates().forEach((state, clientId) => {
      if (clientId === localId) return;
      const u = state.user as { name?: string; avatarUrl?: string | null; color?: string } | undefined;
      if (!u?.name) return;

      if (!seen.has(u.name)) {
        seen.set(u.name, {
          name: u.name,
          avatarUrl: u.avatarUrl ?? null,
          color: u.color ?? "#6b7280",
        });
      }
    });

    setPeers(Array.from(seen.values()));
  }, [awareness]);

  useEffect(() => {
    if (!awareness) {
      setPeers([]);
      return;
    }

    sync();
    awareness.on("change", sync);
    return () => {
      awareness.off("change", sync);
    };
  }, [awareness, sync]);

  return peers;
}
