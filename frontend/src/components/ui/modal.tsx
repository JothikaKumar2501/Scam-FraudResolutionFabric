"use client";

import { motion, AnimatePresence } from "framer-motion";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

type ModalProps = {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  title?: string;
  children?: React.ReactNode;
  className?: string;
};

export function Modal({ open, onOpenChange, title, children, className }: ModalProps) {
  return (
    <AnimatePresence>
      {open ? (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-50 flex items-center justify-center"
          aria-modal
          role="dialog"
        >
          <div
            className="absolute inset-0 bg-black/40"
            onClick={() => onOpenChange(false)}
            aria-hidden="true"
          />
          <motion.div
            initial={{ scale: 0.96, y: 10, opacity: 0 }}
            animate={{ scale: 1, y: 0, opacity: 1 }}
            exit={{ scale: 0.96, y: 10, opacity: 0 }}
            transition={{ duration: 0.18, ease: "easeOut" }}
            className={cn(
              "relative z-10 w-[92vw] max-w-2xl rounded-2xl border bg-background p-4 shadow-xl",
              className
            )}
          >
            <div className="flex items-center justify-between pb-2">
              <h3 className="text-sm font-medium">{title}</h3>
              <Button size="sm" variant="ghost" onClick={() => onOpenChange(false)} aria-label="Close">Close</Button>
            </div>
            <div className="max-h-[70vh] overflow-auto text-sm">{children}</div>
          </motion.div>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}


