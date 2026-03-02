/**
 * Custom hook for managing a Yjs document and WebSocket provider.
 *
 * Creates a Y.Doc, a Y.Text shared type, and a y-websocket WebsocketProvider
 * that connects to the backend's `/ws/doc/{documentId}` endpoint for
 * real-time collaborative editing.
 *
 * @param documentId - The document ID to collaborate on.
 * @returns The Yjs document, text type, provider, and awareness instance.
 */

import { useEffect, useRef, useState } from "react";
import * as Y from "yjs";
import { WebsocketProvider } from "y-websocket";

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

export function useYjsProvider(documentId: string | undefined): YjsProviderState {
  const [synced, setSynced] = useState(false);
  const ydocRef = useRef<Y.Doc>(new Y.Doc());
  const providerRef = useRef<WebsocketProvider | null>(null);

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
  }, [documentId]);

  const ytext = ydocRef.current.getText("content");

  return {
    ydoc: ydocRef.current,
    ytext,
    provider: providerRef.current,
    synced,
  };
}
