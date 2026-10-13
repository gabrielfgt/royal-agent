import { Bot, BrainCircuit, CalendarCheck, PauseCircle, Route, UserRound } from "lucide-react";

import { IntentBadge, StageBadge, TemperatureBadge } from "@/components/lead/badges";
import { ProfileFields } from "@/components/lead/profile-fields";
import { ScoreRing } from "@/components/lead/score-ring";
import { Badge } from "@/components/ui/badge";
import { agentLabel, STAGE_LABELS, STAGE_ORDER } from "@/lib/format";
import type { Lead, Stage } from "@/lib/types";
import { cn } from "@/lib/utils";

const FUNNEL: Stage[] = ["novo", "em_qualificacao", "qualificado", "agendado"];

function StageTrack({ stage }: { stage: Stage }) {
  const reached = stage === "handoff" ? 3 : FUNNEL.indexOf(stage);
  return (
    <ol className="grid grid-cols-4 gap-1">
      {FUNNEL.map((step, index) => (
        <li key={step} className="flex flex-col gap-1">
          <span className={cn("h-1.5 rounded-full bg-muted transition-colors", index <= reached && "bg-gold")} />
          <span className={cn("text-[10px] leading-tight text-muted-foreground", index === reached && "font-semibold text-foreground")}>
            {STAGE_LABELS[step]}
          </span>
        </li>
      ))}
    </ol>
  );
}

export function AgentPanel({ lead, lastAgent, busy }: { lead: Lead | null; lastAgent: string | null; busy: boolean }) {
  if (!lead) {
    return (
      <div className="flex flex-col items-center gap-3 px-2 py-10 text-center text-sm text-muted-foreground">
        <BrainCircuit className="size-8 text-gold" />
        <p className="text-balance">
          Aqui você acompanha, em tempo real, o que o agente entende do lead: intenção, perfil extraído, score e qual
          especialista está respondendo.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-4">
        <ScoreRing score={lead.score} temperature={lead.temperature} />
        <div className="min-w-0 space-y-1.5">
          <p className="flex items-center gap-1.5 truncate font-semibold">
            <UserRound className="size-4 shrink-0 text-muted-foreground" />
            {lead.name ?? "Lead sem nome"}
          </p>
          <div className="flex flex-wrap gap-1.5">
            <TemperatureBadge temperature={lead.temperature} />
            <StageBadge stage={lead.stage} />
            <IntentBadge intent={lead.intent} />
          </div>
        </div>
      </div>

      {STAGE_ORDER.indexOf(lead.stage) <= 4 && <StageTrack stage={lead.stage} />}

      <div className="rounded-xl border bg-card p-3">
        <p className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
          <Route className="size-3.5" /> Especialista na última resposta
        </p>
        <p className="mt-1 flex items-center gap-2 text-sm font-semibold">
          <Bot className={cn("size-4 text-gold", busy && "animate-pulse")} />
          {busy ? "Pensando…" : agentLabel(lastAgent)}
        </p>
      </div>

      {lead.ai_paused && (
        <Badge variant="warm" className="w-full justify-center py-1">
          <PauseCircle /> IA pausada — um corretor assumiu
        </Badge>
      )}
      {lead.stage === "agendado" && (
        <Badge variant="success" className="w-full justify-center py-1">
          <CalendarCheck /> Compromisso agendado
        </Badge>
      )}

      <div className="space-y-2">
        <h3 className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">Perfil extraído</h3>
        <ProfileFields profile={lead.profile} missing={lead.missing_fields} compact />
      </div>

      {lead.summary?.headline && (
        <div className="space-y-1.5 rounded-xl bg-gold-soft p-3">
          <h3 className="text-xs font-semibold tracking-wide text-accent-foreground uppercase">Resumo p/ corretor</h3>
          <p className="text-sm">{lead.summary.headline}</p>
        </div>
      )}
    </div>
  );
}
