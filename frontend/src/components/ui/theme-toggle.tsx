"use client";

import { useTheme } from "next-themes";
import { Button } from "@/components/ui/button";
import { Moon, Sun } from "lucide-react";
import { motion } from "framer-motion";
import { useEffect, useState } from "react";

export function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  const isDark = theme === "dark";
  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
      <Button
        variant="outline"
        size="sm"
        aria-label="Toggle dark mode"
        onClick={() => setTheme(isDark ? "light" : "dark")}
      >
        {mounted && isDark ? <Sun className="size-4" /> : <Moon className="size-4" />}
      </Button>
    </motion.div>
  );
}


