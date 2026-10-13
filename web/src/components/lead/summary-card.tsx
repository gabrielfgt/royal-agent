import { Lightbulb, RefreshCw, Sparkles } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { relative } from "@/lib/format";
import type { BrokerSummary } from "@/lib/types";

const SECTIONS: { key: keyof Omit<BrokerSummary, "headline" | "approach_tip">; title: string }[] = [
  { key: "profile", title: "Perfil" },
  { key: "needs", title: "Necessidades" },
  { key: "properties_discussed", title: "Imóveis discutidos" },
  { key: "objections", title: "Objeções" },
  { key: "next_steps", title: "Próximos passos" },
];

export function SummaryCard({
  summary,
  updatedAt,
  onRegenerate,
  regenerating,
}: {
  summary: BrokerSummary | null;
  updatedAt?: string | null;
  onRegenerate?: () => void;
  regenerating?: boolean;
}) {
  return (
    <Card className="border-gold/40">
      <CardHeader className="flex-row items-start justify-between gap-3">
        <div className="space-y-1">
          <CardTitle className="flex items-center gap-2">
            <Sparkles className="size-4 text-gold" /> Resumo para o corretor
          </CardTitle>
          <CardDescription>
            Gerado pela IA{updatedAt ? ` · atualizado ${relative(updatedAt)}` : ""}
          </CardDescription>
        </div>
        {onRegenerate && (
          <Button variant="outline" size="sm" onClick={onRegenerate} disabled={regenerating}>
            <RefreshCw className={regenerating ? "animate-spin" : ""} />
            {regenerating ? "Gerando…" : "Regenerar"}
          </Button>
        )}
      </CardHeader>
      <CardContent>
        {summary ? (
          <div className="space-y-4">
            <p className="rounded-lg bg-gold-soft px-3 py-2.5 text-sm font-medium text-balance">{summary.headline}</p>
            <div className="grid gap-4 sm:grid-cols-2">
              {SECTIONS.filter(({ key }) => summary[key]?.length).map(({ key, title }) => (
                <div key={key} className="space-y-1.5">
                  <h4 className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">{title}</h4>
                  <ul className="space-y-1 text-sm">
                    {summary[key].map((item, index) => (
                      <li key={index} className="flex gap-2">
                        <span className="mt-2 size-1.5 shrink-0 rounded-full bg-gold" />
                        <span>{item}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
            {summary.approach_tip && (
              <div className="flex gap-2 rounded-lg border border-dashed p-3 text-sm">
                <Lightbulb className="mt-0.5 size-4 shrink-0 text-gold" />
                <p>
                  <span className="font-medium">Dica de abordagem: </span>
                  {summary.approach_tip}
                </p>
              </div>
            )}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">
            O resumo é gerado automaticamente quando o lead avança (qualificado, agendado ou encaminhado) ou a cada
            algumas mensagens. Você também pode gerar agora.
          </p>
        )}
      </CardContent>
    </Card>
  );
}
