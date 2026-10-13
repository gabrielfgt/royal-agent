import {
  AlertTriangle,
  ArrowRightLeft,
  Ban,
  Building2,
  CalendarPlus,
  CircleDot,
  CloudUpload,
  Pause,
  Play,
  Send,
  ShieldAlert,
  UserCheck,
  UserX,
  type LucideIcon,
} from "lucide-react";

import { describeEvent, EVENT_LABELS, relative } from "@/lib/format";
import type { LeadEvent } from "@/lib/types";
import { cn } from "@/lib/utils";

const ICONS: Record<string, { icon: LucideIcon; tone: string }> = {
  mudanca_estagio: { icon: ArrowRightLeft, tone: "bg-secondary text-primary" },
  imoveis_apresentados: { icon: Building2, tone: "bg-gold-soft text-accent-foreground" },
  agendamento_criado: { icon: CalendarPlus, tone: "bg-success-soft text-success" },
  followup_enviado: { icon: Send, tone: "bg-cold-soft text-cold" },
  handoff: { icon: UserCheck, tone: "bg-primary text-primary-foreground" },
  crm_sincronizado: { icon: CloudUpload, tone: "bg-success-soft text-success" },
  crm_erro: { icon: AlertTriangle, tone: "bg-destructive/10 text-destructive" },
  guardrail_bloqueio: { icon: ShieldAlert, tone: "bg-hot-soft text-hot" },
  opt_out: { icon: Ban, tone: "bg-destructive/10 text-destructive" },
  lead_perdido: { icon: UserX, tone: "bg-muted text-muted-foreground" },
  ia_pausada: { icon: Pause, tone: "bg-warm-soft text-accent-foreground" },
  ia_retomada: { icon: Play, tone: "bg-success-soft text-success" },
};

export function EventsTimeline({ events }: { events: LeadEvent[] }) {
  if (!events.length) return <p className="text-sm text-muted-foreground">Nenhum evento registrado ainda.</p>;
  return (
    <ol className="relative space-y-4 before:absolute before:top-2 before:bottom-2 before:left-[15px] before:w-px before:bg-border">
      {events.map((event) => {
        const { icon: Icon, tone } = ICONS[event.type] ?? { icon: CircleDot, tone: "bg-muted text-muted-foreground" };
        const detail = describeEvent(event.type, event.payload);
        return (
          <li key={event.id} className="relative flex gap-3">
            <span className={cn("z-10 flex size-8 shrink-0 items-center justify-center rounded-full ring-4 ring-card", tone)}>
              <Icon className="size-3.5" />
            </span>
            <div className="min-w-0 pt-1">
              <p className="text-sm font-medium">{EVENT_LABELS[event.type] ?? event.type}</p>
              {detail && <p className="text-xs break-words text-muted-foreground">{detail}</p>}
              <p className="text-[11px] text-muted-foreground">{relative(event.created_at)}</p>
            </div>
          </li>
        );
      })}
    </ol>
  );
}
