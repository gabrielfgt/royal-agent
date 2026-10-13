import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { ApiError, chatApi } from "@/lib/api";
import { getSessionId, resetSessionId } from "@/lib/session";
import type { ChatStreamEvent, Lead, Message } from "@/lib/types";
import { randomId, sleep, splitBubbles } from "@/lib/utils";

const POLL_INTERVAL = 4000;

export type ChatItem =
  | {
      key: string;
      role: "lead";
      text: string;
      kind: "text" | "audio";
      status: "sending" | "sent" | "failed";
      audioUrl?: string;
      createdAt: string;
      retryText?: string;
    }
  | {
      key: string;
      role: "agent";
      id: number;
      bubbles: string[];
      agent: string | null;
      kind: "text" | "followup";
      latencyMs: number | null;
      audioUrl?: string;
      autoplay?: boolean;
      createdAt: string;
    }
  | { key: string; role: "notice"; id: number; text: string; createdAt: string };

function fromMessage(message: Message): ChatItem {
  if (message.role === "lead") {
    return {
      key: `m${message.id}`,
      role: "lead",
      text: message.content,
      kind: message.kind === "audio" ? "audio" : "text",
      status: "sent",
      createdAt: message.created_at,
    };
  }
  if (message.kind === "notice" || message.role === "system") {
    return { key: `m${message.id}`, role: "notice", id: message.id, text: message.content, createdAt: message.created_at };
  }
  return {
    key: `m${message.id}`,
    role: "agent",
    id: message.id,
    bubbles: splitBubbles(message.content),
    agent: message.agent,
    kind: message.kind === "followup" ? "followup" : "text",
    latencyMs: message.latency_ms,
    createdAt: message.created_at,
  };
}

function base64ToUrl(base64: string, mime: string) {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) bytes[index] = binary.charCodeAt(index);
  return URL.createObjectURL(new Blob([bytes], { type: mime }));
}

function bubbleDelay(text: string, first: boolean) {
  return first ? 250 : Math.min(450 + text.length * 14, 1700);
}

export function useChat() {
  const [sessionId, setSessionId] = useState(getSessionId);
  const [items, setItems] = useState<ChatItem[]>([]);
  const [lead, setLead] = useState<Lead | null>(null);
  const [busy, setBusy] = useState(false);
  const [typing, setTyping] = useState(false);
  const [loading, setLoading] = useState(true);
  const [paused, setPaused] = useState(false);
  const [lastAgent, setLastAgent] = useState<string | null>(null);
  const lastIdRef = useRef(0);
  const busyRef = useRef(false);
  const abortRef = useRef<AbortController | null>(null);

  const trackIds = useCallback((ids: number[]) => {
    lastIdRef.current = Math.max(lastIdRef.current, ...ids);
  }, []);

  const appendMessages = useCallback(
    (messages: Message[]) => {
      if (!messages.length) return;
      trackIds(messages.map((message) => message.id));
      setItems((current) => {
        const known = new Set(current.map((item) => item.key));
        const fresh = messages.map(fromMessage).filter((item) => !known.has(item.key));
        return fresh.length ? [...current, ...fresh] : current;
      });
      const agentMessage = [...messages].reverse().find((message) => message.role === "agent" && message.kind !== "notice");
      if (agentMessage?.agent) setLastAgent(agentMessage.agent);
    },
    [trackIds],
  );

  useEffect(() => {
    let cancelled = false;
    lastIdRef.current = 0;
    setItems([]);
    setLead(null);
    setLastAgent(null);
    setPaused(false);
    setLoading(true);
    chatApi
      .history(sessionId)
      .then((history) => {
        if (cancelled) return;
        setLead(history.lead);
        setPaused(Boolean(history.lead?.ai_paused));
        appendMessages(history.messages);
      })
      .catch(() => {
        if (!cancelled) toast.error("Não consegui carregar a conversa. Verifique se a API está no ar.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [sessionId, appendMessages]);

  useEffect(() => {
    const timer = window.setInterval(async () => {
      if (busyRef.current || document.visibilityState !== "visible" || !lastIdRef.current) return;
      try {
        const history = await chatApi.history(sessionId, lastIdRef.current);
        if (busyRef.current) return;
        if (history.lead) setLead(history.lead);
        appendMessages(history.messages);
      } catch {
        return;
      }
    }, POLL_INTERVAL);
    return () => window.clearInterval(timer);
  }, [sessionId, appendMessages]);

  useEffect(() => () => abortRef.current?.abort(), []);

  const updateLeadItem = useCallback((key: string, patch: Partial<Extract<ChatItem, { role: "lead" }>>) => {
    setItems((current) =>
      current.map((item) => (item.key === key && item.role === "lead" ? { ...item, ...patch } : item)),
    );
  }, []);

  const handleEvent = useCallback(
    async (event: ChatStreamEvent, leadKey: string) => {
      switch (event.event) {
        case "transcript":
          updateLeadItem(leadKey, { text: event.data.text });
          break;
        case "reply": {
          const { message_id, agent, bubbles, latency_ms } = event.data;
          trackIds([message_id]);
          setLastAgent(agent);
          const key = `m${message_id}`;
          for (const [index, bubble] of bubbles.entries()) {
            setTyping(true);
            await sleep(bubbleDelay(bubble, index === 0));
            setTyping(false);
            setItems((current) => {
              const existing = current.find((item) => item.key === key);
              if (existing && existing.role === "agent") {
                return current.map((item) =>
                  item.key === key && item.role === "agent" ? { ...item, bubbles: [...item.bubbles, bubble] } : item,
                );
              }
              return [
                ...current,
                {
                  key,
                  role: "agent",
                  id: message_id,
                  bubbles: [bubble],
                  agent,
                  kind: "text",
                  latencyMs: latency_ms,
                  createdAt: new Date().toISOString(),
                },
              ];
            });
          }
          break;
        }
        case "audio": {
          const url = base64ToUrl(event.data.audio_b64, event.data.mime);
          const key = `m${event.data.message_id}`;
          setItems((current) =>
            current.map((item) => (item.key === key && item.role === "agent" ? { ...item, audioUrl: url, autoplay: true } : item)),
          );
          break;
        }
        case "notice":
          trackIds([event.data.message_id]);
          await sleep(500);
          setItems((current) => [
            ...current,
            {
              key: `m${event.data.message_id}`,
              role: "notice",
              id: event.data.message_id,
              text: event.data.text,
              createdAt: new Date().toISOString(),
            },
          ]);
          break;
        case "lead":
          setLead(event.data);
          setPaused(event.data.ai_paused);
          break;
        case "paused":
          setPaused(true);
          break;
        default:
          break;
      }
    },
    [trackIds, updateLeadItem],
  );

  const run = useCallback(
    async (leadKey: string, start: (signal: AbortSignal) => Promise<AsyncGenerator<ChatStreamEvent>>) => {
      const controller = new AbortController();
      abortRef.current = controller;
      busyRef.current = true;
      setBusy(true);
      setTyping(true);
      try {
        const events = await start(controller.signal);
        updateLeadItem(leadKey, { status: "sent" });
        for await (const event of events) {
          await handleEvent(event, leadKey);
        }
      } catch (error) {
        if (controller.signal.aborted) return;
        updateLeadItem(leadKey, { status: "failed" });
        if (error instanceof ApiError && error.status === 429) {
          toast.warning("Calma, são muitas mensagens em pouco tempo. Espere alguns segundos e tente de novo.");
        } else if (error instanceof ApiError) {
          toast.error(error.message);
        } else {
          toast.error("Falha de conexão com o agente. Toque em “Tentar de novo”.");
        }
      } finally {
        busyRef.current = false;
        setBusy(false);
        setTyping(false);
      }
    },
    [handleEvent, updateLeadItem],
  );

  const sendText = useCallback(
    async (raw: string) => {
      const text = raw.trim();
      if (!text || busyRef.current) return;
      const key = `local-${randomId(8)}`;
      setItems((current) => [
        ...current,
        { key, role: "lead", text, kind: "text", status: "sending", createdAt: new Date().toISOString(), retryText: text },
      ]);
      await run(key, (signal) => chatApi.sendText(sessionId, text, signal));
    },
    [run, sessionId],
  );

  const sendAudio = useCallback(
    async (blob: Blob, filename: string) => {
      if (busyRef.current) return;
      const key = `local-${randomId(8)}`;
      setItems((current) => [
        ...current,
        {
          key,
          role: "lead",
          text: "",
          kind: "audio",
          status: "sending",
          audioUrl: URL.createObjectURL(blob),
          createdAt: new Date().toISOString(),
        },
      ]);
      await run(key, (signal) => chatApi.sendAudio(sessionId, blob, filename, signal));
    },
    [run, sessionId],
  );

  const retry = useCallback(
    (key: string) => {
      const item = items.find((candidate) => candidate.key === key);
      if (!item || item.role !== "lead" || !item.retryText) return;
      setItems((current) => current.filter((candidate) => candidate.key !== key));
      void sendText(item.retryText);
    },
    [items, sendText],
  );

  const dismiss = useCallback((key: string) => {
    setItems((current) => current.filter((candidate) => candidate.key !== key));
  }, []);

  const newConversation = useCallback(() => {
    abortRef.current?.abort();
    setSessionId(resetSessionId());
  }, []);

  return {
    sessionId,
    items,
    lead,
    busy,
    typing,
    loading,
    paused,
    lastAgent,
    sendText,
    sendAudio,
    retry,
    dismiss,
    newConversation,
  };
}
