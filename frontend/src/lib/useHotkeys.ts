"use client";

import { useEffect } from "react";

type Handler = (ev: KeyboardEvent) => void;

export function useHotkeys(map: Record<string, Handler>) {
  useEffect(() => {
    const handler = (ev: KeyboardEvent) => {
      const key = normalize(ev);
      const fn = map[key];
      if (fn) fn(ev);
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [map]);
}

function normalize(ev: KeyboardEvent): string {
  const parts = [] as string[];
  if (ev.ctrlKey || ev.metaKey) parts.push("ctrl");
  if (ev.altKey) parts.push("alt");
  if (ev.shiftKey) parts.push("shift");
  parts.push(ev.key.toLowerCase());
  return parts.join("+");
}




