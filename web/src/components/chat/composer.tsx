import { Mic, Send, Square, Trash2 } from "lucide-react";
import { type FormEvent, type KeyboardEvent, useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import type { RecorderStatus } from "@/hooks/use-recorder";
import { cn } from "@/lib/utils";

const MAX_CHARS = 1500;

function clock(totalSeconds: number) {
  const minutes = Math.floor(totalSeconds / 60);
  const secs = totalSeconds % 60;
  return `${minutes}:${String(secs).padStart(2, "0")}`;
}

export function Composer({
  disabled,
  onSend,
  recorderStatus,
  recordingSeconds,
  onStartRecording,
  onStopRecording,
  onCancelRecording,
}: {
  disabled: boolean;
  onSend: (text: string) => void;
  recorderStatus: RecorderStatus;
  recordingSeconds: number;
  onStartRecording: () => void;
  onStopRecording: () => void;
  onCancelRecording: () => void;
}) {
  const [text, setText] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const element = textareaRef.current;
    if (!element) return;
    element.style.height = "auto";
    element.style.height = `${Math.min(element.scrollHeight + 2, 140)}px`;
    element.style.overflowY = element.scrollHeight > 140 ? "auto" : "hidden";
  }, [text]);

  useEffect(() => {
    if (!disabled) textareaRef.current?.focus({ preventScroll: true });
  }, [disabled]);

  function submit(event?: FormEvent) {
    event?.preventDefault();
    const value = text.trim();
    if (!value || disabled) return;
    onSend(value);
    setText("");
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      submit();
    }
  }

  if (recorderStatus === "recording") {
    return (
      <div className="flex items-center gap-2 border-t bg-card p-3">
        <Button variant="ghost" size="icon" onClick={onCancelRecording} aria-label="Cancelar gravação">
          <Trash2 />
        </Button>
        <div className="flex flex-1 items-center gap-3 rounded-full bg-hot-soft px-4 py-2 text-sm text-hot">
          <span className="size-2.5 animate-pulse-ring rounded-full bg-hot" />
          Gravando… <span className="ml-auto font-mono tabular-nums">{clock(recordingSeconds)}</span>
        </div>
        <Button size="icon" variant="gold" onClick={onStopRecording} aria-label="Enviar áudio">
          <Square className="fill-current" />
        </Button>
      </div>
    );
  }

  return (
    <form onSubmit={submit} className="flex items-end gap-2 border-t bg-card p-3">
      <textarea
        ref={textareaRef}
        rows={1}
        value={text}
        maxLength={MAX_CHARS}
        onChange={(event) => setText(event.target.value)}
        onKeyDown={onKeyDown}
        placeholder={disabled ? "Sofia está respondendo…" : "Escreva sua mensagem"}
        aria-label="Mensagem"
        className="max-h-36 min-h-10 flex-1 resize-none rounded-2xl border border-input bg-background px-4 py-2.5 text-sm outline-none transition-[box-shadow] placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/40"
      />
      {text.trim() ? (
        <Button type="submit" size="icon-lg" className="rounded-full" disabled={disabled} aria-label="Enviar">
          <Send />
        </Button>
      ) : (
        <Button
          type="button"
          size="icon-lg"
          variant="gold"
          className={cn("rounded-full")}
          disabled={disabled}
          onClick={onStartRecording}
          aria-label="Gravar áudio"
          title="Gravar mensagem de voz"
        >
          <Mic />
        </Button>
      )}
    </form>
  );
}
