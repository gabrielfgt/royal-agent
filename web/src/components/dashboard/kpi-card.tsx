import type { LucideIcon } from "lucide-react";

import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";

export function KpiCard({
  label,
  value,
  hint,
  icon: Icon,
  tone = "default",
}: {
  label: string;
  value: string | number;
  hint?: string;
  icon: LucideIcon;
  tone?: "default" | "gold" | "hot" | "success" | "cold";
}) {
  const tones = {
    default: "bg-secondary text-primary",
    gold: "bg-gold-soft text-accent-foreground",
    hot: "bg-hot-soft text-hot",
    success: "bg-success-soft text-success",
    cold: "bg-cold-soft text-cold",
  };
  return (
    <Card className="flex items-start gap-3 p-4">
      <span className={cn("flex size-10 shrink-0 items-center justify-center rounded-lg", tones[tone])}>
        <Icon className="size-5" />
      </span>
      <div className="min-w-0">
        <p className="text-xs leading-tight font-medium text-muted-foreground">{label}</p>
        <p className="text-2xl leading-tight font-semibold tabular-nums">{value}</p>
        {hint && <p className="line-clamp-2 text-xs text-muted-foreground">{hint}</p>}
      </div>
    </Card>
  );
}
