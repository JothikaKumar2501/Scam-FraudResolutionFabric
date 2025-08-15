"use client";

import { Button } from "@/components/ui/button";
import { ThemeToggle } from "@/components/ui/theme-toggle";
import { motion } from "framer-motion";
import Link from "next/link";
import { useUIStatus } from "@/lib/ui-status";
import { Activity } from "lucide-react";

export function NavBar() {
  const { connected, status, currentStep, totalSteps, streamingAgent, caseId } = useUIStatus();
  return (
    <motion.nav
      initial={{ y: -12, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ duration: 0.4, ease: "easeOut" }}
      className="sticky top-0 z-40 backdrop-blur supports-[backdrop-filter]:bg-background/70 border-b"
      aria-label="Primary"
    >
      <div className="max-w-6xl mx-auto px-4 h-14 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link href="/" className="font-semibold tracking-tight text-sm md:text-base">
            GenAI FraudOps Suite
          </Link>
          <span className="hidden md:inline text-muted-foreground text-xs">Live MAS streaming</span>
        </div>
        <div className="flex items-center gap-3">
          {caseId ? <span className="text-[10px] px-2 py-0.5 rounded-full bg-muted/60" title="Case ID">{caseId}</span> : null}
          <MiniProgress connected={connected} status={status} step={currentStep} total={totalSteps} agent={streamingAgent} />
          <Button asChild variant="ghost" size="xs">
            <a href="https://github.com" target="_blank" rel="noreferrer" aria-label="GitHub">GitHub</a>
          </Button>
          <ThemeToggle />
        </div>
      </div>
    </motion.nav>
  );
}

function MiniProgress({ connected, status, step, total, agent }: { connected: boolean; status: string; step?: number; total?: number; agent?: string }) {
  const pct = step && total ? Math.min(100, Math.round((step / total) * 100)) : undefined;
  return (
    <div className="hidden sm:flex items-center gap-2 min-w-[180px]" aria-live="polite">
      <div className="relative flex items-center gap-1 text-xs">
        <span className={`inline-block w-1.5 h-1.5 rounded-full ${connected ? "bg-green-500" : "bg-red-500"}`}
          aria-hidden />
        <span className={`${connected ? "text-green-600" : "text-red-600"}`}>{connected ? "Connected" : "Disconnected"}</span>
      </div>
      <div className="relative h-2 w-24 overflow-hidden rounded bg-muted/60">
        <div
          className="h-full bg-primary/70 transition-[width]"
          style={{ width: pct != null ? `${pct}%` : (connected ? "33%" : "0%") }}
          aria-label="Progress"
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={pct || 0}
        />
        <Activity className="absolute right-0 top-1/2 -translate-y-1/2 size-3 text-primary/80" />
      </div>
      <div className="text-[10px] text-muted-foreground max-w-[120px] truncate" title={`${status}${agent ? ` · ${agent}` : ""}`}>
        {status}{agent ? ` · ${agent}` : ""}
      </div>
    </div>
  );
}


