/**
 * Interactive API documentation page. Users enter their API key and can
 * test any endpoint directly from the browser. Endpoints are grouped by
 * feature and each has a collapsible "Try it" panel.
 */

import { useCallback, useEffect, useState } from "react";
import { BookOpen, ChevronDown, ChevronRight, Copy, Key, Play } from "lucide-react";
import { Navbar } from "../components/Layout/Navbar";

/* ------------------------------------------------------------------ */
/*  Endpoint definitions                                               */
/* ------------------------------------------------------------------ */

interface Param {
  name: string;
  in: "path" | "query";
  required?: boolean;
  description: string;
  default?: string;
}

interface EndpointDef {
  method: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  path: string;
  summary: string;
  description: string;
  params?: Param[];
  body?: string;
  responseExample?: string;
}

interface EndpointGroup {
  name: string;
  endpoints: EndpointDef[];
}

const GROUPS: EndpointGroup[] = [
  {
    name: "Documents",
    endpoints: [
      {
        method: "POST",
        path: "/api/documents",
        summary: "Create a document",
        description:
          "Create a new Markdown document. Both fields are optional and default to 'Untitled' and empty content.",
        body: JSON.stringify({ title: "My Document", content: "# Hello World", folder_id: null }, null, 2),
        responseExample: JSON.stringify(
          {
            id: "abc123",
            title: "My Document",
            content: "# Hello World",
            owner_id: "user123",
            folder_id: null,
            general_access: "restricted",
            is_deleted: false,
            created_at: "2026-01-01T00:00:00Z",
            updated_at: "2026-01-01T00:00:00Z",
          },
          null,
          2,
        ),
      },
      {
        method: "GET",
        path: "/api/documents",
        summary: "List your documents",
        description: "Returns all documents owned by the authenticated user, sorted by most recently updated.",
        params: [
          {
            name: "include_deleted",
            in: "query",
            description: "Include soft-deleted documents",
            default: "false",
          },
        ],
      },
      {
        method: "GET",
        path: "/api/documents/{doc_id}",
        summary: "Get a document",
        description:
          "Fetch a single document by ID. Returns 410 Gone if the document has been soft-deleted. Works for documents you own or have access to (via sharing).",
        params: [
          {
            name: "doc_id",
            in: "path",
            required: true,
            description: "Document ID",
          },
        ],
      },
      {
        method: "PUT",
        path: "/api/documents/{doc_id}",
        summary: "Update a document",
        description:
          "Update a document's title and/or content. Returns 410 Gone if the document has been soft-deleted. To append text, GET the document first, modify the content string, then PUT the full content back.",
        params: [
          {
            name: "doc_id",
            in: "path",
            required: true,
            description: "Document ID",
          },
        ],
        body: JSON.stringify({ title: "Updated Title", content: "# Updated content" }, null, 2),
      },
      {
        method: "DELETE",
        path: "/api/documents/{doc_id}",
        summary: "Delete a document",
        description:
          "Soft-delete a document (moves to trash). Owner only. Breaks the folder hierarchy so the document restores to root.",
        params: [
          {
            name: "doc_id",
            in: "path",
            required: true,
            description: "Document ID",
          },
        ],
      },
      {
        method: "POST",
        path: "/api/documents/{doc_id}/restore",
        summary: "Restore a document",
        description:
          "Restore a soft-deleted document from trash. Owner only. If the document's parent folder is still deleted, it restores to root.",
        params: [
          {
            name: "doc_id",
            in: "path",
            required: true,
            description: "Document ID",
          },
        ],
      },
    ],
  },
  {
    name: "Folders",
    endpoints: [
      {
        method: "POST",
        path: "/api/folders",
        summary: "Create a folder",
        description: "Create a new folder. Optionally nest it under a parent folder by providing parent_id.",
        body: JSON.stringify({ name: "My Folder", parent_id: null }, null, 2),
        responseExample: JSON.stringify(
          {
            id: "folder123",
            name: "My Folder",
            owner_id: "user123",
            parent_id: null,
            general_access: "restricted",
            is_deleted: false,
            created_at: "2026-01-01T00:00:00Z",
            updated_at: "2026-01-01T00:00:00Z",
          },
          null,
          2,
        ),
      },
      {
        method: "GET",
        path: "/api/folders/contents",
        summary: "List folder contents",
        description:
          "List folders and documents at a given level. Omit folder_id for root. Returns folders, documents, and the user's permission level.",
        params: [
          {
            name: "folder_id",
            in: "query",
            description: "Parent folder ID (omit for root)",
          },
        ],
      },
      {
        method: "GET",
        path: "/api/folders/{folder_id}",
        summary: "Get a folder",
        description:
          "Fetch a single folder by ID. Returns 410 Gone if the folder has been soft-deleted. Requires VIEW permission.",
        params: [
          {
            name: "folder_id",
            in: "path",
            required: true,
            description: "Folder ID",
          },
        ],
      },
      {
        method: "PUT",
        path: "/api/folders/{folder_id}",
        summary: "Update a folder",
        description: "Rename a folder or move it to a different parent.",
        params: [
          {
            name: "folder_id",
            in: "path",
            required: true,
            description: "Folder ID",
          },
        ],
        body: JSON.stringify({ name: "Renamed Folder" }, null, 2),
      },
      {
        method: "DELETE",
        path: "/api/folders/{folder_id}",
        summary: "Delete a folder",
        description:
          "Cascade soft-delete a folder and all its nested folders and documents. Owner only. Access is deactivated for non-owners.",
        params: [
          {
            name: "folder_id",
            in: "path",
            required: true,
            description: "Folder ID",
          },
        ],
      },
      {
        method: "POST",
        path: "/api/folders/{folder_id}/restore",
        summary: "Restore a folder",
        description:
          "Cascade restore a folder and all its children. If the parent folder is still deleted, restores to root. Own ACLs are preserved; parent ACLs are broken.",
        params: [
          {
            name: "folder_id",
            in: "path",
            required: true,
            description: "Folder ID",
          },
        ],
      },
      {
        method: "GET",
        path: "/api/folders/breadcrumbs",
        summary: "Get breadcrumb trail",
        description: "Return the breadcrumb trail from root to the given folder for navigation.",
        params: [
          {
            name: "folder_id",
            in: "query",
            required: true,
            description: "Folder ID",
          },
        ],
      },
      {
        method: "GET",
        path: "/api/folders/{folder_id}/tree",
        summary: "Get folder tree",
        description:
          "Recursively list all nested folders and documents under a folder in a single request. Used by the CLI sync engine.",
        params: [
          {
            name: "folder_id",
            in: "path",
            required: true,
            description: "Folder ID",
          },
        ],
      },
    ],
  },
  {
    name: "Trash",
    endpoints: [
      {
        method: "GET",
        path: "/api/documents/trash",
        summary: "List trashed documents",
        description:
          "List all soft-deleted documents owned by the current user. Only shows individually deleted documents (not cascade-deleted children).",
      },
      {
        method: "GET",
        path: "/api/folders/trash",
        summary: "List trashed folders",
        description: "List all soft-deleted top-level folders owned by the current user.",
      },
      {
        method: "GET",
        path: "/api/folders/trash/{folder_id}/contents",
        summary: "Drill into trashed folder",
        description:
          "List deleted subfolders and documents inside a trashed folder. Returns an ancestors array for breadcrumb navigation.",
        params: [
          {
            name: "folder_id",
            in: "path",
            required: true,
            description: "Trashed folder ID",
          },
        ],
      },
      {
        method: "DELETE",
        path: "/api/documents/{doc_id}/permanent",
        summary: "Hard-delete a document",
        description: "Permanently delete a document. Cannot be undone. Owner only.",
        params: [
          {
            name: "doc_id",
            in: "path",
            required: true,
            description: "Document ID",
          },
        ],
      },
      {
        method: "DELETE",
        path: "/api/folders/{folder_id}/permanent",
        summary: "Hard-delete a folder",
        description: "Permanently delete a folder and all its nested content. Cannot be undone. Owner only.",
        params: [
          {
            name: "folder_id",
            in: "path",
            required: true,
            description: "Folder ID",
          },
        ],
      },
    ],
  },
  {
    name: "Sharing",
    endpoints: [
      {
        method: "PUT",
        path: "/api/documents/{doc_id}/access",
        summary: "Update general access",
        description:
          'Set who can access the document via its URL. Values: "restricted", "anyone_view", "anyone_edit". Owner only.',
        params: [
          {
            name: "doc_id",
            in: "path",
            required: true,
            description: "Document ID",
          },
        ],
        body: JSON.stringify({ general_access: "anyone_view" }, null, 2),
      },
      {
        method: "POST",
        path: "/api/documents/{doc_id}/collaborators",
        summary: "Add a collaborator",
        description: "Add a user by email as a collaborator with view or edit permission. Owner only.",
        params: [
          {
            name: "doc_id",
            in: "path",
            required: true,
            description: "Document ID",
          },
        ],
        body: JSON.stringify({ email: "user@example.com", permission: "edit" }, null, 2),
      },
      {
        method: "GET",
        path: "/api/documents/{doc_id}/collaborators",
        summary: "List collaborators",
        description: "List all users with explicit access to this document. Owner only.",
        params: [
          {
            name: "doc_id",
            in: "path",
            required: true,
            description: "Document ID",
          },
        ],
      },
      {
        method: "DELETE",
        path: "/api/documents/{doc_id}/collaborators/{user_id}",
        summary: "Remove a collaborator",
        description: "Remove a user's access to this document. Owner only.",
        params: [
          {
            name: "doc_id",
            in: "path",
            required: true,
            description: "Document ID",
          },
          {
            name: "user_id",
            in: "path",
            required: true,
            description: "User ID to remove",
          },
        ],
      },
      {
        method: "GET",
        path: "/api/documents/shared",
        summary: "List shared documents",
        description: "List documents shared with you, sorted by most recently accessed.",
      },
    ],
  },
  {
    name: "Versions",
    endpoints: [
      {
        method: "POST",
        path: "/api/documents/{doc_id}/versions",
        summary: "Create a version snapshot",
        description: "Manually create a version snapshot of the document.",
        params: [
          {
            name: "doc_id",
            in: "path",
            required: true,
            description: "Document ID",
          },
        ],
        body: JSON.stringify({ content: "# Snapshot content", summary: "Manual save" }, null, 2),
      },
      {
        method: "GET",
        path: "/api/documents/{doc_id}/versions",
        summary: "List version history",
        description: "List all version snapshots for a document, newest first.",
        params: [
          {
            name: "doc_id",
            in: "path",
            required: true,
            description: "Document ID",
          },
        ],
      },
      {
        method: "GET",
        path: "/api/documents/{doc_id}/versions/{version_number}",
        summary: "Get a specific version",
        description: "Retrieve a specific version snapshot including the full content.",
        params: [
          {
            name: "doc_id",
            in: "path",
            required: true,
            description: "Document ID",
          },
          {
            name: "version_number",
            in: "path",
            required: true,
            description: "Version number (1-based)",
          },
        ],
      },
    ],
  },
  {
    name: "Comments",
    endpoints: [
      {
        method: "POST",
        path: "/api/documents/{doc_id}/comments",
        summary: "Create a comment",
        description: "Add an inline or document-level comment. Omit anchor fields for a doc-level comment.",
        params: [
          {
            name: "doc_id",
            in: "path",
            required: true,
            description: "Document ID",
          },
        ],
        body: JSON.stringify(
          {
            content: "This needs revision.",
            anchor_from: 10,
            anchor_to: 25,
            quoted_text: "selected text",
          },
          null,
          2,
        ),
      },
      {
        method: "GET",
        path: "/api/documents/{doc_id}/comments",
        summary: "List comments",
        description: "List all top-level comments with nested replies for a document.",
        params: [
          {
            name: "doc_id",
            in: "path",
            required: true,
            description: "Document ID",
          },
        ],
      },
      {
        method: "POST",
        path: "/api/comments/{comment_id}/reply",
        summary: "Reply to a comment",
        description: "Add a single-depth reply to a comment.",
        params: [
          {
            name: "comment_id",
            in: "path",
            required: true,
            description: "Parent comment ID",
          },
        ],
        body: JSON.stringify({ content: "I agree, fixing now." }, null, 2),
      },
      {
        method: "POST",
        path: "/api/comments/{comment_id}/resolve",
        summary: "Resolve a comment",
        description: "Mark a comment as resolved.",
        params: [
          {
            name: "comment_id",
            in: "path",
            required: true,
            description: "Comment ID",
          },
        ],
      },
      {
        method: "DELETE",
        path: "/api/comments/{comment_id}",
        summary: "Delete a comment",
        description: "Delete a comment and its replies.",
        params: [
          {
            name: "comment_id",
            in: "path",
            required: true,
            description: "Comment ID",
          },
        ],
      },
    ],
  },
  {
    name: "Users",
    endpoints: [
      {
        method: "GET",
        path: "/api/users/me",
        summary: "Get current user",
        description: "Return the authenticated user's profile including name, email, avatar, and organization context.",
        responseExample: JSON.stringify(
          {
            id: "user123",
            name: "Jane Doe",
            email: "jane@example.com",
            avatar_url: null,
            org_id: "org123",
            org_name: "Acme Corp",
          },
          null,
          2,
        ),
      },
    ],
  },
  {
    name: "API Keys",
    endpoints: [
      {
        method: "POST",
        path: "/api/keys",
        summary: "Create an API key",
        description: 'Generate a new API key. The raw key is only shown once in the response. Prefix: "cm_".',
        body: JSON.stringify({ name: "My Agent Key" }, null, 2),
      },
      {
        method: "GET",
        path: "/api/keys",
        summary: "List API keys",
        description: "List all API keys for the authenticated user (raw key not included).",
      },
      {
        method: "DELETE",
        path: "/api/keys/{key_id}",
        summary: "Revoke an API key",
        description: "Permanently revoke an API key.",
        params: [
          {
            name: "key_id",
            in: "path",
            required: true,
            description: "API key ID",
          },
        ],
      },
    ],
  },
];

/* ------------------------------------------------------------------ */
/*  Method badge colors                                                */
/* ------------------------------------------------------------------ */

const METHOD_STYLES: Record<string, string> = {
  GET: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900 dark:text-emerald-200",
  POST: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200",
  PUT: "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200",
  PATCH: "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200",
  DELETE: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200",
};

/* ------------------------------------------------------------------ */
/*  TryItPanel                                                         */
/* ------------------------------------------------------------------ */

function TryItPanel({ endpoint, apiKey }: { endpoint: EndpointDef; apiKey: string }) {
  const [paramValues, setParamValues] = useState<Record<string, string>>({});
  const [bodyText, setBodyText] = useState(endpoint.body ?? "");
  const [response, setResponse] = useState<{
    status: number;
    body: string;
  } | null>(null);
  const [loading, setLoading] = useState(false);

  const buildUrl = useCallback(() => {
    let url = endpoint.path;
    for (const p of endpoint.params ?? []) {
      if (p.in === "path") {
        url = url.replace(`{${p.name}}`, paramValues[p.name] ?? "");
      }
    }
    const queryParams = (endpoint.params ?? [])
      .filter((p) => p.in === "query" && paramValues[p.name])
      .map((p) => `${encodeURIComponent(p.name)}=${encodeURIComponent(paramValues[p.name])}`);
    if (queryParams.length) url += `?${queryParams.join("&")}`;
    return url;
  }, [endpoint, paramValues]);

  const execute = async () => {
    setLoading(true);
    setResponse(null);
    try {
      const url = buildUrl();
      const headers: Record<string, string> = {
        "X-API-Key": apiKey,
      };
      const opts: RequestInit = { method: endpoint.method, headers };
      if (bodyText && ["POST", "PUT", "PATCH"].includes(endpoint.method)) {
        headers["Content-Type"] = "application/json";
        opts.body = bodyText;
      }
      const res = await fetch(url, opts);
      let text: string;
      const ct = res.headers.get("content-type") ?? "";
      if (ct.includes("json")) {
        const json = await res.json();
        text = JSON.stringify(json, null, 2);
      } else {
        text = await res.text();
        if (text.length > 2000) text = text.slice(0, 2000) + "\n... (truncated)";
      }
      setResponse({ status: res.status, body: text });
    } catch (err) {
      setResponse({
        status: 0,
        body: `Network error: ${(err as Error).message}`,
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="mt-3 space-y-3 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
      {/* Params */}
      {(endpoint.params ?? []).length > 0 && (
        <div className="space-y-2">
          <h4 className="text-xs font-semibold uppercase tracking-wide text-[var(--color-text-muted)]">Parameters</h4>
          {(endpoint.params ?? []).map((p) => (
            <div key={p.name} className="flex items-center gap-2">
              <label className="w-32 text-xs font-medium text-[var(--color-text)]">
                {p.name}
                {p.required && <span className="text-red-500"> *</span>}
              </label>
              <input
                type="text"
                placeholder={p.description}
                value={paramValues[p.name] ?? ""}
                onChange={(e) =>
                  setParamValues((prev) => ({
                    ...prev,
                    [p.name]: e.target.value,
                  }))
                }
                className="flex-1 rounded border border-[var(--color-border)] bg-[var(--color-surface)] px-2 py-1 text-xs text-[var(--color-text)] placeholder-[var(--color-text-muted)] outline-none focus:border-[var(--color-primary)]"
              />
            </div>
          ))}
        </div>
      )}

      {/* Body */}
      {endpoint.body !== undefined && (
        <div className="space-y-1">
          <h4 className="text-xs font-semibold uppercase tracking-wide text-[var(--color-text-muted)]">
            Request Body (JSON)
          </h4>
          <textarea
            value={bodyText}
            onChange={(e) => setBodyText(e.target.value)}
            rows={Math.min(bodyText.split("\n").length + 1, 12)}
            className="w-full rounded border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2 font-mono text-xs text-[var(--color-text)] outline-none focus:border-[var(--color-primary)]"
          />
        </div>
      )}

      {/* Execute */}
      <div className="flex items-center gap-3">
        <button
          onClick={execute}
          disabled={loading || !apiKey}
          className="flex items-center gap-1.5 rounded-md bg-[var(--color-primary)] px-4 py-2 text-sm font-medium text-white transition hover:bg-[var(--color-primary-hover)] disabled:opacity-50"
        >
          <Play className="h-3.5 w-3.5" />
          {loading ? "Sending..." : "Send Request"}
        </button>
        <span className="font-mono text-xs text-[var(--color-text-muted)]">
          {endpoint.method} {buildUrl()}
        </span>
      </div>

      {/* Response */}
      {response && (
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <span
              className={`rounded px-2 py-0.5 text-xs font-bold ${
                response.status >= 200 && response.status < 300
                  ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-900 dark:text-emerald-200"
                  : response.status >= 400
                    ? "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200"
                    : "bg-gray-100 text-gray-700"
              }`}
            >
              {response.status || "ERR"}
            </span>
            <span className="text-xs text-[var(--color-text-muted)]">Response</span>
          </div>
          <pre className="max-h-80 overflow-auto rounded-md bg-gray-900 p-3 text-xs text-gray-100">{response.body}</pre>
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  EndpointCard                                                       */
/* ------------------------------------------------------------------ */

function EndpointCard({ endpoint, apiKey }: { endpoint: EndpointDef; apiKey: string }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)]">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-center gap-3 px-4 py-3 text-left hover:bg-[var(--color-hover)]"
      >
        <span
          className={`inline-block w-16 rounded px-2 py-0.5 text-center text-xs font-bold ${METHOD_STYLES[endpoint.method] ?? ""}`}
        >
          {endpoint.method}
        </span>
        <code className="flex-1 text-sm font-medium text-[var(--color-text)]">{endpoint.path}</code>
        <span className="hidden text-xs text-[var(--color-text-muted)] sm:inline">{endpoint.summary}</span>
        {expanded ? (
          <ChevronDown className="h-4 w-4 shrink-0 text-[var(--color-text-muted)]" />
        ) : (
          <ChevronRight className="h-4 w-4 shrink-0 text-[var(--color-text-muted)]" />
        )}
      </button>

      {expanded && (
        <div className="border-t border-[var(--color-border)] px-4 py-3">
          <p className="mb-2 text-sm text-[var(--color-text-muted)]">{endpoint.description}</p>

          {endpoint.responseExample && (
            <details className="mb-2">
              <summary className="cursor-pointer text-xs font-medium text-[var(--color-text-muted)]">
                Example response
              </summary>
              <pre className="mt-1 max-h-48 overflow-auto rounded bg-gray-900 p-2 text-xs text-gray-100">
                {endpoint.responseExample}
              </pre>
            </details>
          )}

          <TryItPanel endpoint={endpoint} apiKey={apiKey} />
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Main Page                                                          */
/* ------------------------------------------------------------------ */

export function ApiDocsPage() {
  useEffect(() => {
    document.title = "API Docs - CollabMark";
    return () => {
      document.title = "CollabMark";
    };
  }, []);

  const [apiKey, setApiKey] = useState(() => sessionStorage.getItem("collabmark_api_key") ?? "");
  const [copied, setCopied] = useState(false);

  const handleKeyChange = (value: string) => {
    setApiKey(value);
    sessionStorage.setItem("collabmark_api_key", value);
  };

  const copyCode = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  const baseUrl = window.location.origin;
  const curlExample = `curl -H "X-API-Key: YOUR_KEY" ${baseUrl}/api/documents`;

  return (
    <div className="flex min-h-screen flex-col bg-[var(--color-bg)]">
      <Navbar />

      <div className="mx-auto w-full max-w-4xl px-6 py-8">
        {/* Header */}
        <div className="mb-8">
          <h1 className="flex items-center gap-2 text-2xl font-bold text-[var(--color-text)]">
            <BookOpen className="h-6 w-6 text-[var(--color-primary)]" />
            API Documentation
          </h1>
          <p className="mt-2 text-sm text-[var(--color-text-muted)]">
            Use the CollabMark API to programmatically manage Markdown documents, sharing, comments, and more.
            Authenticate with an API key via the{" "}
            <code className="rounded bg-[var(--color-hover)] px-1 py-0.5 text-xs">X-API-Key</code> header.
          </p>
        </div>

        {/* Quick start */}
        <div className="mb-8 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-5">
          <h2 className="mb-3 text-lg font-semibold text-[var(--color-text)]">Quick Start</h2>
          <ol className="mb-4 list-inside list-decimal space-y-1 text-sm text-[var(--color-text-muted)]">
            <li>
              Go to <strong>Settings</strong> and generate an API key
            </li>
            <li>
              Copy the key (it starts with{" "}
              <code className="rounded bg-[var(--color-hover)] px-1 py-0.5 text-xs">cm_</code>)
            </li>
            <li>
              Pass it in the <code className="rounded bg-[var(--color-hover)] px-1 py-0.5 text-xs">X-API-Key</code>{" "}
              header with every request
            </li>
          </ol>
          <div className="relative rounded-md bg-gray-900 p-3">
            <pre className="overflow-x-auto text-xs text-gray-100">{curlExample}</pre>
            <button
              onClick={() => copyCode(curlExample)}
              className="absolute right-2 top-2 rounded p-1 text-gray-400 hover:text-white"
              title="Copy"
            >
              <Copy className="h-3.5 w-3.5" />
            </button>
            {copied && <span className="absolute right-8 top-2.5 text-xs text-emerald-400">Copied!</span>}
          </div>
        </div>

        {/* API key input */}
        <div className="mb-8 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-5">
          <h2 className="mb-2 flex items-center gap-2 text-sm font-semibold text-[var(--color-text)]">
            <Key className="h-4 w-4" />
            Your API Key
          </h2>
          <p className="mb-3 text-xs text-[var(--color-text-muted)]">
            Enter your API key to use the &quot;Try it&quot; panels below. The key is stored in session storage and
            cleared when you close the tab.
          </p>
          <input
            type="password"
            value={apiKey}
            onChange={(e) => handleKeyChange(e.target.value)}
            placeholder="cm_..."
            className="w-full rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2 text-sm text-[var(--color-text)] placeholder-[var(--color-text-muted)] outline-none focus:border-[var(--color-primary)]"
          />
        </div>

        {/* Endpoint groups */}
        {GROUPS.map((group) => (
          <section key={group.name} className="mb-8">
            <h2 className="mb-3 border-b border-[var(--color-border)] pb-2 text-lg font-semibold text-[var(--color-text)]">
              {group.name}
            </h2>
            <div className="space-y-2">
              {group.endpoints.map((ep) => (
                <EndpointCard key={`${ep.method} ${ep.path}`} endpoint={ep} apiKey={apiKey} />
              ))}
            </div>
          </section>
        ))}

        {/* Base URL note */}
        <div className="mt-4 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-4 text-xs text-[var(--color-text-muted)]">
          <strong>Base URL:</strong> <code className="rounded bg-[var(--color-hover)] px-1 py-0.5">{baseUrl}</code>. All
          API paths shown above are relative to this origin.
        </div>
      </div>
    </div>
  );
}
