import { useMemo } from "react";
import { diffLines, type Change } from "diff";

interface DiffViewProps {
  oldText: string;
  newText: string;
  oldLabel?: string;
  newLabel?: string;
}

export function DiffView({
  oldText,
  newText,
  oldLabel = "Selected version",
  newLabel = "Current document",
}: DiffViewProps) {
  const changes = useMemo(
    () => diffLines(oldText, newText),
    [oldText, newText],
  );

  const identical = changes.length === 1 && !changes[0].added && !changes[0].removed;

  if (identical) {
    return (
      <div className="flex items-center justify-center py-10 text-sm text-[var(--color-text-muted)]">
        No differences — version matches current document.
      </div>
    );
  }

  return (
    <div className="overflow-auto text-sm">
      <div className="flex items-center gap-4 border-b border-[var(--color-border)] px-4 py-2 text-xs text-[var(--color-text-muted)]">
        <span className="flex items-center gap-1">
          <span className="inline-block h-2.5 w-2.5 rounded-sm bg-red-200" />
          {oldLabel}
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block h-2.5 w-2.5 rounded-sm bg-green-200" />
          {newLabel}
        </span>
      </div>
      <pre className="m-0 p-0 font-mono text-[13px] leading-6">
        {changes.map((change: Change, i: number) => (
          <DiffBlock key={i} change={change} />
        ))}
      </pre>
    </div>
  );
}

function DiffBlock({ change }: { change: Change }) {
  if (change.added) {
    return (
      <div
        data-testid="diff-added"
        className="bg-green-50 text-green-900 dark:bg-green-900/30 dark:text-green-200"
      >
        {renderLines(change.value, "+")}
      </div>
    );
  }
  if (change.removed) {
    return (
      <div
        data-testid="diff-removed"
        className="bg-red-50 text-red-900 dark:bg-red-900/30 dark:text-red-200"
      >
        {renderLines(change.value, "-")}
      </div>
    );
  }
  return (
    <div data-testid="diff-unchanged" className="text-[var(--color-text)]">
      {renderLines(change.value, " ")}
    </div>
  );
}

function renderLines(text: string, prefix: string) {
  const lines = text.endsWith("\n") ? text.slice(0, -1).split("\n") : text.split("\n");
  return lines.map((line, i) => (
    <div key={i} className="whitespace-pre-wrap px-4">
      <span className="mr-3 inline-block w-4 select-none text-right opacity-50">
        {prefix}
      </span>
      {line}
    </div>
  ));
}
