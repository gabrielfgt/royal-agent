import { Bot, Lock, Mic, Timer } from "lucide-react";

import { agentLabel, dateTime, seconds } from "@/lib/format";
import type { Message } from "@/lib/types";
import { cn, splitBubbles } from "@/lib/utils";

export function Transcript({ messages }: { messages: Message[] }) {
  if (!messages.length) return <p className="py-6 text-center text-sm text-muted-foreground">Sem mensagens.</p>;
  return (
    <div className="chat-wallpaper scrollbar-thin flex max-h-[560px] flex-col gap-2.5 overflow-y-auto rounded-xl p-3 sm:p-4">
      {messages.map((message) => {
        if (message.kind === "notice" || message.role === "system") {
          return (
            <p key={message.id} className="mx-auto flex max-w-md items-start gap-1.5 rounded-lg bg-card/80 px-3 py-1.5 text-center text-xs text-muted-foreground">
              <Lock className="mt-0.5 size-3 shrink-0" />
              {message.content.replace(/^🔒\s*/, "")}
            </p>
          );
        }
        const isLead = message.role === "lead";
        return (
          <div key={message.id} className={cn("flex flex-col gap-1", isLead ? "items-end" : "items-start")}>
            {!isLead && (
              <span className="flex items-center gap-1 pl-1 text-[10px] font-medium text-muted-foreground">
                {message.kind === "followup" ? <Timer className="size-3" /> : <Bot className="size-3" />}
                {agentLabel(message.kind === "followup" ? "followup" : message.agent)}
                {message.latency_ms ? ` · ${seconds(message.latency_ms)}` : ""}
              </span>
            )}
            {(isLead ? [message.content] : splitBubbles(message.content)).map((bubble, index) => (
              <div
                key={index}
                className={cn(
                  "max-w-[85%] rounded-2xl px-3.5 py-2 text-sm whitespace-pre-wrap shadow-xs",
                  isLead ? "rounded-tr-sm bg-bubble-lead text-bubble-lead-foreground" : "bg-bubble-agent",
                  !isLead && index === 0 && "rounded-tl-sm",
                )}
              >
                {isLead && message.kind === "audio" && (
                  <span className="mb-0.5 flex items-center gap-1 text-[11px] opacity-80">
                    <Mic className="size-3" /> áudio transcrito
                  </span>
                )}
                {bubble}
              </div>
            ))}
            <span className="px-1 text-[10px] text-muted-foreground">{dateTime(message.created_at)}</span>
          </div>
        );
      })}
    </div>
  );
}
