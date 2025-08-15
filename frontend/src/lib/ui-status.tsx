"use client";

import { createContext, useContext, useMemo, useState } from "react";

export type UIStatusState = {
  connected: boolean;
  status: string;
  currentStep?: number;
  totalSteps?: number;
  streamingAgent?: string;
  sessionId?: string | null;
  caseId?: string | null;
};

type UIStatusContextValue = UIStatusState & {
  setUIStatus: (next: Partial<UIStatusState>) => void;
};

const UIStatusContext = createContext<UIStatusContextValue | undefined>(undefined);

export function UIStatusProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<UIStatusState>({ connected: false, status: "Idle" });
  const value = useMemo(
    () => ({
      ...state,
      setUIStatus: (next: Partial<UIStatusState>) => setState((prev) => ({ ...prev, ...next })),
    }),
    [state]
  );
  return <UIStatusContext.Provider value={value}>{children}</UIStatusContext.Provider>;
}

export function useUIStatus() {
  const ctx = useContext(UIStatusContext);
  if (!ctx) throw new Error("useUIStatus must be used within UIStatusProvider");
  return ctx;
}


