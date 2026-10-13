import { Search } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { profileEntries } from "@/lib/format";
import type { LeadProfile } from "@/lib/types";

export function ProfileFields({ profile, missing, compact = false }: { profile: LeadProfile; missing?: string[]; compact?: boolean }) {
  const entries = profileEntries(profile);
  return (
    <div className="space-y-4">
      {entries.length ? (
        <dl className={compact ? "divide-y rounded-xl border bg-card" : "grid grid-cols-1 gap-x-6 gap-y-2.5 sm:grid-cols-2"}>
          {entries.map(({ label, value }) =>
            compact ? (
              <div key={label} className="flex items-baseline justify-between gap-3 px-3 py-2 animate-in fade-in-0">
                <dt className="shrink-0 text-xs text-muted-foreground">{label}</dt>
                <dd className="min-w-0 text-right text-sm font-medium break-words">{value}</dd>
              </div>
            ) : (
              <div key={label} className="flex flex-col gap-0.5 animate-in fade-in-0 slide-in-from-left-1">
                <dt className="text-[11px] font-medium tracking-wide text-muted-foreground uppercase">{label}</dt>
                <dd className="text-sm font-medium break-words">{value}</dd>
              </div>
            ),
          )}
        </dl>
      ) : (
        <p className="text-sm text-muted-foreground">Nada extraído ainda. O perfil aparece aqui conforme a conversa avança.</p>
      )}
      {missing && missing.length > 0 && (
        <div className="space-y-2">
          <p className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
            <Search className="size-3.5" /> Ainda falta descobrir
          </p>
          <div className="flex flex-wrap gap-1.5">
            {missing.map((field) => (
              <Badge key={field} variant="gold">
                {field}
              </Badge>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
