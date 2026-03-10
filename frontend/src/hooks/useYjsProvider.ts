/**
 * Custom hook for managing a Yjs document and WebSocket provider.
 *
 * Creates a Y.Doc, a Y.Text shared type, and a y-websocket WebsocketProvider
 * that connects to the backend's `/ws/doc/{documentId}` endpoint for
 * real-time collaborative editing.
 *
 * When {@link permission} transitions from `"view"` to `"edit"`, the
 * provider is torn down and recreated so the backend WebSocket adapter
 * starts with the correct write-enabled state immediately.
 *
 * @param documentId - The document ID to collaborate on.
 * @param permission - Current user permission; triggers reconnect on upgrade.
 * @returns The Yjs document, text type, provider, and awareness instance.
 */

import { useEffect, useRef, useState } from "react";
import * as Y from "yjs";
import { WebsocketProvider } from "y-websocket";

import type { Permission } from "../lib/api";

interface YjsProviderState {
  /** The Yjs document instance. */
  ydoc: Y.Doc;
  /** The shared Y.Text type for the editor content. */
  ytext: Y.Text;
  /** The WebSocket provider for network sync. */
  provider: WebsocketProvider | null;
  /** Whether the provider has synced initial state. */
  synced: boolean;
}

export function useYjsProvider(documentId: string | undefined, permission: Permission = "edit"): YjsProviderState {
  const [synced, setSynced] = useState(false);
  const ydocRef = useRef<Y.Doc>(new Y.Doc());
  const providerRef = useRef<WebsocketProvider | null>(null);
  const prevPermissionRef = useRef<Permission>(permission);
  const [reconnectKey, setReconnectKey] = useState(0);

  useEffect(() => {
    const prev = prevPermissionRef.current;
    prevPermissionRef.current = permission;
    if (prev === "view" && permission === "edit") {
      setReconnectKey((k) => k + 1);
    }
  }, [permission]);

  useEffect(() => {
    if (!documentId) return;

    const ydoc = new Y.Doc();
    ydocRef.current = ydoc;

    const wsUrl = `${window.location.protocol === "https:" ? "wss:" : "ws:"}//${window.location.host}/ws/doc`;

    const provider = new WebsocketProvider(wsUrl, documentId, ydoc);
    providerRef.current = provider;

    provider.on("sync", (isSynced: boolean) => {
      setSynced(isSynced);
    });

    return () => {
      provider.disconnect();
      provider.destroy();
      ydoc.destroy();
      providerRef.current = null;
      setSynced(false);
    };
  }, [documentId, reconnectKey]);

  const ytext = ydocRef.current.getText("content");

  return {
    ydoc: ydocRef.current,
    ytext,
    provider: providerRef.current,
    synced,
  };
}
