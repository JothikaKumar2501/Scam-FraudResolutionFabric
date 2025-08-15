"use client";

import { motion } from "framer-motion";

export function TypingDots() {
  const dot = {
    hidden: { opacity: 0.2, y: 0 },
    visible: (i: number) => ({
      opacity: [0.2, 1, 0.2],
      y: [0, -2, 0],
      transition: { duration: 0.9, repeat: Infinity, delay: i * 0.15 },
    }),
  };
  return (
    <div className="flex items-center gap-1 h-5">
      {[0, 1, 2].map((i) => (
        <motion.span
          key={i}
          custom={i}
          variants={dot}
          initial="hidden"
          animate="visible"
          className="w-1.5 h-1.5 rounded-full bg-muted-foreground/70"
        />
      ))}
    </div>
  );
}



