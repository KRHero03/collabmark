---
name: toast-on-action
description: Enforces that every user-triggered async action in the frontend shows a toast notification for both success and failure. Use whenever writing or modifying frontend code that performs an async action (API call, form submit, file upload, delete, toggle, etc.).
---

# Toast on Every Action

Every user-initiated async operation MUST provide visual feedback via a toast notification. Silent successes and swallowed errors are bugs.

## Rules

1. **Success toast** — shown immediately after the async operation resolves. Green styling, concise past-tense message (e.g., "SSO configuration saved", "Member removed", "Logo uploaded").
2. **Error toast** — shown when the operation rejects or returns a non-2xx status. Red styling, include a meaningful message (e.g., "Failed to save SSO configuration"). Never show raw error objects.
3. **Auto-dismiss** — toasts disappear after 4 seconds. No manual close required (but a close button is acceptable).
4. **No duplicate toasts** — if a toast is already showing, replace it rather than stacking.

## Standard Pattern

Follow the established pattern used in `OrgSettingsPage.tsx`:

```tsx
const [toast, setToast] = useState<{ type: "success" | "error"; message: string } | null>(null);

const showToast = (type: "success" | "error", message: string) => {
  setToast({ type, message });
  setTimeout(() => setToast(null), 4000);
};
```

Wrap every async handler:

```tsx
try {
  await someApiCall();
  showToast("success", "Thing updated");
} catch {
  showToast("error", "Failed to update thing");
}
```

## Rendering

```tsx
{toast && (
  <div className={`mb-6 flex items-center gap-2 rounded-lg px-4 py-3 text-sm font-medium ${
    toast.type === "success"
      ? "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400"
      : "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400"
  }`}>
    {toast.type === "success" ? <CheckCircle /> : <XCircle />}
    <span>{toast.message}</span>
  </div>
)}
```

## Checklist

```
- [ ] Every async action has a try/catch with showToast for both success and error
- [ ] Toast messages are user-friendly (no raw error objects, no technical jargon)
- [ ] Success messages use past tense ("Saved", "Removed", "Uploaded")
- [ ] Error messages start with "Failed to..." followed by the action
- [ ] Toast auto-dismisses after 4 seconds
- [ ] No silent failures — every catch block shows a toast
```
