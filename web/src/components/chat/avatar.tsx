import { cn } from "@/lib/utils";

export function SofiaAvatar({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        "relative flex size-10 shrink-0 items-center justify-center rounded-full bg-gold text-sm font-semibold text-gold-foreground ring-2 ring-card",
        className,
      )}
      aria-hidden
    >
      S
      <span className="absolute -right-0.5 -bottom-0.5 size-3 rounded-full border-2 border-card bg-success" />
    </div>
  );
}
