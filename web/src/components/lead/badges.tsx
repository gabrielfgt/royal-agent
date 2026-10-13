import { Flame, Snowflake, Sun } from "lucide-react";

import { Badge, type BadgeVariant } from "@/components/ui/badge";
import { CHANNEL_LABELS, INTENT_LABELS, STAGE_LABELS, TEMPERATURE_LABELS } from "@/lib/format";
import type { Channel, Intent, Stage, Temperature } from "@/lib/types";

const STAGE_VARIANTS: Record<Stage, BadgeVariant> = {
  novo: "muted",
  em_qualificacao: "secondary",
  qualificado: "gold",
  agendado: "success",
  handoff: "default",
  perdido: "outline",
  opt_out: "destructive",
};

const TEMPERATURE_VARIANTS: Record<Temperature, BadgeVariant> = { quente: "hot", morno: "warm", frio: "cold" };
const TEMPERATURE_ICONS = { quente: Flame, morno: Sun, frio: Snowflake };

export function StageBadge({ stage }: { stage: Stage }) {
  return <Badge variant={STAGE_VARIANTS[stage] ?? "outline"}>{STAGE_LABELS[stage] ?? stage}</Badge>;
}

export function TemperatureBadge({ temperature, score }: { temperature: Temperature; score?: number }) {
  const Icon = TEMPERATURE_ICONS[temperature] ?? Sun;
  return (
    <Badge variant={TEMPERATURE_VARIANTS[temperature] ?? "outline"}>
      <Icon />
      {TEMPERATURE_LABELS[temperature] ?? temperature}
      {score != null && <span className="tabular-nums opacity-80">· {score}</span>}
    </Badge>
  );
}

export function IntentBadge({ intent }: { intent: Intent }) {
  return <Badge variant={intent === "indefinido" ? "muted" : "outline"}>{INTENT_LABELS[intent] ?? intent}</Badge>;
}

export function ChannelBadge({ channel }: { channel: Channel }) {
  return <Badge variant="muted">{CHANNEL_LABELS[channel] ?? channel}</Badge>;
}

export function temperatureColor(temperature: Temperature) {
  return temperature === "quente" ? "var(--hot)" : temperature === "morno" ? "var(--warm)" : "var(--cold)";
}
