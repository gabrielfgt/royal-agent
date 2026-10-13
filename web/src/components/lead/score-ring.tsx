import { temperatureColor } from "@/components/lead/badges";
import type { Temperature } from "@/lib/types";
import { cn } from "@/lib/utils";

export function ScoreRing({
  score,
  temperature,
  size = 88,
  className,
}: {
  score: number;
  temperature: Temperature;
  size?: number;
  className?: string;
}) {
  const stroke = 8;
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const clamped = Math.max(0, Math.min(100, score));
  return (
    <div className={cn("relative shrink-0", className)} style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={radius} stroke="var(--muted)" strokeWidth={stroke} fill="none" />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          stroke={temperatureColor(temperature)}
          strokeWidth={stroke}
          strokeLinecap="round"
          fill="none"
          strokeDasharray={circumference}
          strokeDashoffset={circumference * (1 - clamped / 100)}
          style={{ transition: "stroke-dashoffset 600ms ease, stroke 300ms ease" }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-xl leading-none font-semibold tabular-nums">{clamped}</span>
        <span className="text-[10px] tracking-wide text-muted-foreground uppercase">score</span>
      </div>
    </div>
  );
}
