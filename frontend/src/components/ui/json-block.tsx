"use client";

import { useMemo, useState } from "react";
import { Button } from "@/components/ui/button";

function tryParse(input: unknown): unknown {
  if (typeof input === "string") {
    try { return JSON.parse(input); } catch { return input; }
  }
  return input;
}

export function JsonBlock({ value, initiallyOpen = false }: { value: unknown; initiallyOpen?: boolean }) {
  const [open, setOpen] = useState(initiallyOpen);
  const obj = useMemo(() => tryParse(value), [value]);
  const pretty = useMemo(() => {
    try { return typeof obj === "string" ? obj : JSON.stringify(obj, null, 2); } catch { return String(value ?? ""); }
  }, [obj, value]);
  const highlighted = useMemo(() => highlightJson(pretty), [pretty]);
  return (
    <div className="rounded-md border bg-muted/30">
      <div className="flex items-center justify-between px-2 py-1">
        <div className="text-xs text-muted-foreground">Details</div>
        <Button size="xs" variant="ghost" onClick={() => setOpen(v => !v)} aria-expanded={open} aria-controls="json-body">
          {open ? "Collapse" : "Expand"}
        </Button>
      </div>
      {open ? (
        <pre
          id="json-body"
          className="px-2 py-2 text-xs overflow-auto max-h-40 whitespace-pre-wrap [&_.k]:text-sky-700 dark:[&_.k]:text-sky-300 [&_.s]:text-emerald-700 dark:[&_.s]:text-emerald-300 [&_.n]:text-amber-700 dark:[&_.n]:text-amber-300 [&_.b]:text-fuchsia-700 dark:[&_.b]:text-fuchsia-300 [&_.l]:text-rose-700 dark:[&_.l]:text-rose-300"
          dangerouslySetInnerHTML={{ __html: highlighted }}
        />
      ) : null}
    </div>
  );
}

function escapeHtml(input: string) {
  return input
    .replaceAll(/&/g, "&amp;")
    .replaceAll(/</g, "&lt;")
    .replaceAll(/>/g, "&gt;");
}

function highlightJson(src: string) {
  const s = escapeHtml(src);
  // keys: "key":
  let out = s.replace(/(&quot;)([^&]*?)(&quot;)(\s*:)/g, (_m, a, b, c, d) => `${a}<span class=\"k\">${b}</span>${c}${d}`);
  // strings: "..."
  out = out.replace(/(&quot;)(.*?)(\2)?(&quot;)/g, (m) => {
    // keep already-colored keys
    if (m.includes("class=\\\"k\\\"")) return m;
    return `<span class=\"s\">${m}</span>`;
  });
  // numbers
  out = out.replace(/\b(-?\d+(?:\.\d+)?)\b/g, '<span class="n">$1</span>');
  // booleans
  out = out.replace(/\b(true|false)\b/g, '<span class="b">$1</span>');
  // null
  out = out.replace(/\bnull\b/g, '<span class="l">null</span>');
  return out;
}


