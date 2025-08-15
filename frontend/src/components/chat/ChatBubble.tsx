"use client";

import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { Bot, Shield, User2 } from "lucide-react";

type Role = "assistant" | "user" | "system" | "risk";
type ChatBubbleProps = {
  role: Role;
  text: string;
  badge?: string;
};

export function ChatBubble({ role, text, badge }: ChatBubbleProps) {
  const isUser = role === "user";
  const isRisk = role === "risk";
  const isAssistant = role === "assistant";
  return (
    <motion.div
      initial={{ y: 6, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ duration: 0.2 }}
      className={cn("flex w-full", isUser ? "justify-end" : "justify-start")}
    >
      <div className={cn("flex items-start gap-2 max-w-[85%] sm:max-w-[70%] transition-transform hover:scale-[1.01]", isUser && "flex-row-reverse")}> 
        <div className={cn("shrink-0 mt-0.5")}
          aria-hidden>
          <div className={cn(
            "w-6 h-6 rounded-full grid place-items-center border",
            isUser && "bg-primary text-primary-foreground border-primary/60",
            isAssistant && "bg-accent text-accent-foreground border-accent/60",
            isRisk && "bg-yellow-100 text-yellow-900 dark:bg-yellow-200/20 dark:text-yellow-200 border-yellow-200/40"
          )}>
            {isUser ? <User2 className="w-3.5 h-3.5" /> : isRisk ? <Shield className="w-3.5 h-3.5" /> : <Bot className="w-3.5 h-3.5" />}
          </div>
        </div>
        <div className="flex-1 min-w-0">
          {badge ? (
            <div className="text-[10px] mb-1 text-muted-foreground">{badge}</div>
          ) : null}
          <div
            className={cn(
              "rounded-2xl px-3 py-2 text-sm shadow-sm",
              isUser && "bg-primary text-primary-foreground",
              !isUser && !isRisk && "bg-accent text-accent-foreground",
              isRisk && "bg-yellow-100 text-yellow-900 dark:bg-yellow-200/20 dark:text-yellow-200 border border-yellow-200/40"
            )}
          >
            <div className="whitespace-pre-wrap">{text}</div>
          </div>
        </div>
      </div>
    </motion.div>
  );
}


