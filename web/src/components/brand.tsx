import { cn } from "@/lib/utils";

export function BrandMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 64 64" className={cn("size-8", className)} aria-hidden>
      <rect width="64" height="64" rx="14" fill="var(--primary)" />
      <path d="M14 44V24l9 8 9-14 9 14 9-8v20z" fill="var(--gold)" />
      <rect x="14" y="46" width="36" height="5" rx="2" fill="var(--gold)" />
    </svg>
  );
}

export function Brand() {
  return (
    <span className="flex items-center gap-2">
      <BrandMark />
      <span className="leading-none">
        <span className="block text-sm font-semibold tracking-tight">Royal Imóveis</span>
        <span className="block text-[10px] tracking-wider text-muted-foreground uppercase">SDR com IA</span>
      </span>
    </span>
  );
}
