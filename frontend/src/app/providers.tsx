"use client";

import { ThemeProvider } from "next-themes";
import { UIStatusProvider } from "@/lib/ui-status";

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <ThemeProvider attribute="class" defaultTheme="system" enableSystem>
      <UIStatusProvider>
        {children}
      </UIStatusProvider>
    </ThemeProvider>
  );
}


