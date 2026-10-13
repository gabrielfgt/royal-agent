import * as DialogPrimitive from "@radix-ui/react-dialog";
import { BrainCircuit, PanelRightClose, PanelRightOpen, PauseCircle, RotateCcw } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { AgentPanel } from "@/components/chat/agent-panel";
import { SofiaAvatar } from "@/components/chat/avatar";
import { Composer } from "@/components/chat/composer";
import { AgentMessage, LeadMessage, NoticeItem } from "@/components/chat/message-item";
import { TypingIndicator } from "@/components/chat/typing-indicator";
import { Welcome } from "@/components/chat/welcome";
import { Button } from "@/components/ui/button";
import { Dialog, DialogDescription, DialogTitle, SheetContent } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { useChat } from "@/hooks/use-chat";
import { type Recording, useRecorder } from "@/hooks/use-recorder";
import { getDemoMode, setDemoMode } from "@/lib/session";
import { cn } from "@/lib/utils";

export function ChatPage() {
  const chat = useChat();
  const [demo, setDemo] = useState(getDemoMode);
  const [panelOpen, setPanelOpen] = useState(true);
  const [sheetOpen, setSheetOpen] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  const onRecorded = useCallback((recording: Recording) => void chat.sendAudio(recording.blob, recording.filename), [chat]);
  const onRecorderError = useCallback((message: string) => toast.error(message), []);
  const recorder = useRecorder(onRecorded, onRecorderError);

  useEffect(() => {
    const element = scrollRef.current;
    if (element) element.scrollTo({ top: element.scrollHeight, behavior: "smooth" });
  }, [chat.items, chat.typing]);

  function toggleDemo(value: boolean) {
    setDemo(value);
    setDemoMode(value);
  }

  const empty = !chat.loading && chat.items.length === 0;
  const status = chat.typing ? "digitando…" : chat.paused ? "um corretor vai assumir a conversa" : "online · responde em segundos";

  return (
    <div className="mx-auto flex h-[calc(100dvh-3.5rem)] w-full max-w-6xl gap-4 p-0 sm:p-4">
      <section className="flex min-w-0 flex-1 flex-col overflow-hidden border-x bg-card shadow-sm sm:rounded-2xl sm:border">
        <header className="flex items-center gap-3 border-b bg-primary px-4 py-3 text-primary-foreground">
          <SofiaAvatar />
          <div className="min-w-0 flex-1">
            <p className="truncate leading-tight font-semibold">Sofia · Royal Imóveis</p>
            <p className={cn("truncate text-xs opacity-75", chat.typing && "text-gold opacity-100")}>{status}</p>
          </div>
          <div className="hidden items-center gap-2 sm:flex">
            <Switch id="demo-mode" checked={demo} onCheckedChange={toggleDemo} className="data-[state=checked]:bg-gold" />
            <Label htmlFor="demo-mode" className="text-xs font-normal opacity-90">
              Modo demo
            </Label>
          </div>
          <Button
            variant="ghost"
            size="sm"
            className="text-primary-foreground hover:bg-primary-foreground/10 hover:text-primary-foreground"
            onClick={chat.newConversation}
            title="Começar como um novo lead"
          >
            <RotateCcw /> <span className="hidden sm:inline">Nova conversa</span>
          </Button>
          <Button
            variant="ghost"
            size="icon-sm"
            className="text-primary-foreground hover:bg-primary-foreground/10 hover:text-primary-foreground lg:hidden"
            onClick={() => setSheetOpen(true)}
            aria-label="Visão do agente"
          >
            <BrainCircuit />
          </Button>
          <Button
            variant="ghost"
            size="icon-sm"
            className="hidden text-primary-foreground hover:bg-primary-foreground/10 hover:text-primary-foreground lg:inline-flex"
            onClick={() => setPanelOpen((open) => !open)}
            aria-label={panelOpen ? "Ocultar visão do agente" : "Mostrar visão do agente"}
          >
            {panelOpen ? <PanelRightClose /> : <PanelRightOpen />}
          </Button>
        </header>

        <div ref={scrollRef} className="chat-wallpaper scrollbar-thin flex-1 overflow-y-auto px-3 py-4 sm:px-6">
          {chat.loading && (
            <div className="space-y-3">
              <Skeleton className="h-10 w-2/3" />
              <Skeleton className="ml-auto h-10 w-1/2" />
              <Skeleton className="h-14 w-3/4" />
            </div>
          )}
          {empty && <Welcome onPick={chat.sendText} disabled={chat.busy} />}
          <div className="flex flex-col gap-2.5">
            {chat.items.map((item) => {
              if (item.role === "notice") return <NoticeItem key={item.key} text={item.text} />;
              if (item.role === "lead")
                return (
                  <LeadMessage
                    key={item.key}
                    item={item}
                    onRetry={item.retryText ? () => chat.retry(item.key) : undefined}
                    onDismiss={() => chat.dismiss(item.key)}
                  />
                );
              return <AgentMessage key={item.key} item={item} showAgent={demo} />;
            })}
            {chat.typing && !chat.paused && <TypingIndicator />}
          </div>
        </div>

        {chat.paused && (
          <div className="flex items-center gap-2 border-t bg-warm-soft px-4 py-2 text-xs text-accent-foreground">
            <PauseCircle className="size-4" /> A IA está pausada para este lead. As mensagens ficam registradas para o
            corretor.
          </div>
        )}

        <Composer
          disabled={chat.busy}
          onSend={chat.sendText}
          recorderStatus={recorder.status}
          recordingSeconds={recorder.seconds}
          onStartRecording={recorder.start}
          onStopRecording={recorder.stop}
          onCancelRecording={recorder.cancel}
        />
      </section>

      {panelOpen && (
        <aside className="scrollbar-thin hidden w-80 shrink-0 overflow-y-auto rounded-2xl border bg-background/60 p-5 lg:block xl:w-96">
          <PanelHeader />
          <AgentPanel lead={chat.lead} lastAgent={chat.lastAgent} busy={chat.busy} />
        </aside>
      )}

      <Dialog open={sheetOpen} onOpenChange={setSheetOpen}>
        <SheetContent>
          <DialogTitle className="sr-only">Visão do agente</DialogTitle>
          <DialogDescription className="sr-only">Perfil do lead extraído pela IA em tempo real</DialogDescription>
          <PanelHeader />
          <div className="flex items-center gap-2 sm:hidden">
            <Switch id="demo-mode-mobile" checked={demo} onCheckedChange={toggleDemo} />
            <Label htmlFor="demo-mode-mobile" className="text-xs font-normal">
              Modo demo (mostrar agente em cada resposta)
            </Label>
          </div>
          <AgentPanel lead={chat.lead} lastAgent={chat.lastAgent} busy={chat.busy} />
          <DialogPrimitive.Close asChild>
            <Button variant="outline" className="mt-auto">
              Voltar ao chat
            </Button>
          </DialogPrimitive.Close>
        </SheetContent>
      </Dialog>
    </div>
  );
}

function PanelHeader() {
  return (
    <div className="mb-4 flex items-center gap-2">
      <BrainCircuit className="size-5 text-gold" />
      <div>
        <h2 className="leading-tight font-semibold">Visão do agente</h2>
        <p className="text-xs text-muted-foreground">O que a IA entendeu até agora</p>
      </div>
    </div>
  );
}
