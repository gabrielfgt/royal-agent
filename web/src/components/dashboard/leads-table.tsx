import { Send } from "lucide-react";
import { useNavigate } from "react-router";

import { ChannelBadge, IntentBadge, StageBadge, TemperatureBadge } from "@/components/lead/badges";
import { relative } from "@/lib/format";
import type { Lead } from "@/lib/types";

export function LeadsTable({ leads }: { leads: Lead[] }) {
  const navigate = useNavigate();
  if (!leads.length) {
    return <p className="py-10 text-center text-sm text-muted-foreground">Nenhum lead encontrado com esses filtros.</p>;
  }
  return (
    <div className="scrollbar-thin -mx-5 overflow-x-auto">
      <table className="w-full min-w-[760px] text-sm">
        <thead>
          <tr className="border-b text-left text-xs text-muted-foreground">
            <th className="px-5 py-2 font-medium">Lead</th>
            <th className="px-3 py-2 font-medium">Intenção</th>
            <th className="px-3 py-2 font-medium">Estágio</th>
            <th className="px-3 py-2 font-medium">Temperatura</th>
            <th className="px-3 py-2 font-medium">Última mensagem</th>
            <th className="px-3 py-2 font-medium">Atividade</th>
            <th className="px-5 py-2 text-right font-medium">Follow-ups</th>
          </tr>
        </thead>
        <tbody>
          {leads.map((lead) => (
            <tr
              key={lead.id}
              onClick={() => navigate(`/painel/leads/${lead.id}`)}
              onKeyDown={(event) => event.key === "Enter" && navigate(`/painel/leads/${lead.id}`)}
              tabIndex={0}
              className="cursor-pointer border-b transition-colors last:border-0 hover:bg-accent/60 focus-visible:bg-accent/60 focus-visible:outline-none"
            >
              <td className="px-5 py-3">
                <div className="flex flex-col gap-1">
                  <span className="font-medium">{lead.name ?? "Sem nome"}</span>
                  {(lead.channels?.length ? lead.channels : [lead.channel]).map((channel) => (
                  <ChannelBadge key={channel} channel={channel} />
                ))}
                </div>
              </td>
              <td className="px-3 py-3">
                <IntentBadge intent={lead.intent} />
              </td>
              <td className="px-3 py-3">
                <StageBadge stage={lead.stage} />
              </td>
              <td className="px-3 py-3">
                <TemperatureBadge temperature={lead.temperature} score={lead.score} />
              </td>
              <td className="max-w-64 px-3 py-3">
                <p className="truncate text-muted-foreground">{lead.last_message ?? "—"}</p>
              </td>
              <td className="px-3 py-3 whitespace-nowrap text-muted-foreground">
                {relative(lead.last_inbound_at ?? lead.last_outbound_at ?? lead.created_at)}
              </td>
              <td className="px-5 py-3 text-right">
                <span className="inline-flex items-center gap-1 tabular-nums text-muted-foreground">
                  <Send className="size-3" /> {lead.followup_count}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
