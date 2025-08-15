"use client";

import { useEffect, useRef, useState } from "react";

export function useIncrementalStream(fullText: string | undefined, speedMs: number = 10) {
  const [displayed, setDisplayed] = useState<string>(fullText || "");
  const prevRef = useRef<string>(fullText || "");
  const timerRef = useRef<number | null>(null);

  useEffect(() => {
    const next = fullText || "";
    const prev = prevRef.current || "";
    if (next.length <= prev.length) {
      // Replace or same length: snap
      prevRef.current = next;
      setDisplayed(next);
      return;
    }
    // Reveal only the appended part
    const base = next.slice(0, prev.length);
    const added = next.slice(prev.length);
    let i = 0;
    if (timerRef.current) window.clearInterval(timerRef.current);
    setDisplayed(base);
    timerRef.current = window.setInterval(() => {
      i += 1;
      setDisplayed(base + added.slice(0, i));
      if (i >= added.length) {
        if (timerRef.current) window.clearInterval(timerRef.current);
        prevRef.current = next;
        timerRef.current = null;
      }
    }, speedMs) as unknown as number;
    return () => { if (timerRef.current) window.clearInterval(timerRef.current); };
  }, [fullText, speedMs]);

  return displayed;
}


