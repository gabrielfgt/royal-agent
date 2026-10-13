import { AlertCircle, Bot, Check, Clock, Lock, Mic, RotateCcw, Timer, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import type { ChatItem } from "@/hooks/use-chat";
import { agentLabel, seconds, time } from "@/lib/format";
import { cn } from "@/lib/utils";

function Linkified({ text }: { text: string }) {
  return <span className="break-words whitespace-pre-wrap">{text}</span>;
}

export function NoticeItem({ text }: { text: string }) {
  return (
    <div className="flex justify-center py-1">
      <p className="flex max-w-md items-start gap-1.5 rounded-lg bg-card/80 px-3 py-1.5 text-center text-xs text-muted-foreground shadow-xs backdrop-blur">
        <Lock className="mt-0.5 size-3 shrink-0" />
        {text.replace(/^🔒\s*/, "")}
      </p>
    </div>
  );
}

export function LeadMessage({
  item,
  onRetry,
  onDismiss,
}: {
  item: Extract<ChatItem, { role: "lead" }>;
  onRetry?: () => void;
  onDismiss?: () => void;
}) {
  return (
    <div className="flex flex-col items-end gap-1 animate-in fade-in-0 slide-in-from-bottom-1">
      <div
        className={cn(
          "max-w-[85%] rounded-2xl rounded-tr-sm bg-bubble-lead px-3.5 py-2 text-sm text-bubble-lead-foreground shadow-xs sm:max-w-[75%]",
          item.status === "failed" && "opacity-70",
        )}
      >
        {item.kind === "audio" && (
          <div className="mb-1 flex flex-col gap-1.5">
            <span className="flex items-center gap-1.5 text-xs opacity-80">
              <Mic className="size-3.5" /> Mensagem de voz
            </span>
            {item.audioUrl && <audio src={item.audioUrl} controls className="h-8 w-56 max-w-full" />}
          </div>
        )}
        {item.text ? (
          <Linkified text={item.text} />
        ) : (
          item.kind === "audio" && <span className="text-xs italic opacity-80">transcrevendo…</span>
        )}
        <span className="mt-0.5 flex items-center justify-end gap-1 text-[10px] opacity-70">
          {time(item.createdAt)}
          {item.status === "sending" && <Clock className="size-3" />}
          {item.status === "sent" && <Check className="size-3" />}
          {item.status === "failed" && <AlertCircle className="size-3" />}
        </span>
      </div>
      {item.status === "failed" && (
        <div className="flex items-center gap-1">
          <span className="text-xs text-destructive">Não enviada.</span>
          {onRetry && (
            <Button variant="ghost" size="sm" onClick={onRetry} className="h-6 px-2 text-xs">
              <RotateCcw /> Tentar de novo
            </Button>
          )}
          {onDismiss && (
            <Button variant="ghost" size="icon-sm" onClick={onDismiss} className="size-6" aria-label="Descartar">
              <X />
            </Button>
          )}
        </div>
      )}
    </div>
  );
}

export function AgentMessage({ item, showAgent }: { item: Extract<ChatItem, { role: "agent" }>; showAgent: boolean }) {
  return (
    <div className="flex flex-col items-start gap-1">
      {(showAgent || item.kind === "followup") && (
        <div className="flex flex-wrap items-center gap-1.5 pl-1">
          {item.kind === "followup" && (
            <span className="flex items-center gap-1 rounded-full bg-gold-soft px-2 py-0.5 text-[10px] font-medium text-accent-foreground">
              <Timer className="size-3" /> follow-up automático
            </span>
          )}
          {showAgent && item.agent && item.kind !== "followup" && (
            <span className="flex items-center gap-1 rounded-full bg-secondary px-2 py-0.5 text-[10px] font-medium text-secondary-foreground">
              <Bot className="size-3" /> {agentLabel(item.agent)}
              {item.latencyMs ? <span className="opacity-70">· {seconds(item.latencyMs)}</span> : null}
            </span>
          )}
        </div>
      )}
      {item.audioUrl && (
        <div className="max-w-[85%] rounded-2xl rounded-tl-sm bg-bubble-agent px-3 py-2 shadow-xs">
          <span className="mb-1 flex items-center gap-1.5 text-xs text-muted-foreground">
            <Mic className="size-3.5" /> Resposta em áudio
          </span>
          <audio src={item.audioUrl} controls autoPlay={item.autoplay} className="h-8 w-60 max-w-full" />
        </div>
      )}
      {item.bubbles.map((bubble, index) => (
        <div
          key={index}
          className={cn(
            "max-w-[85%] rounded-2xl bg-bubble-agent px-3.5 py-2 text-sm shadow-xs animate-in fade-in-0 slide-in-from-bottom-1 sm:max-w-[75%]",
            index === 0 && !item.audioUrl ? "rounded-tl-sm" : "",
          )}
        >
          <Linkified text={bubble} />
          {index === item.bubbles.length - 1 && (
            <span className="mt-0.5 block text-right text-[10px] text-muted-foreground">{time(item.createdAt)}</span>
          )}
        </div>
      ))}
    </div>
  );
}
