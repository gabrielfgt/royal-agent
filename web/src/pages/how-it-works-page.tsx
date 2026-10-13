import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  BrainCircuit,
  CalendarCheck,
  Database,
  FileText,
  GitBranch,
  Gauge,
  Lock,
  type LucideIcon,
  MessagesSquare,
  Mic,
  Network,
  Send,
  ShieldCheck,
  Timer,
  Users,
} from "lucide-react";
import { Link } from "react-router";

import { PageHeader, PageShell } from "@/components/layout";
import { MermaidDiagram } from "@/components/mermaid-diagram";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useAuth } from "@/hooks/use-auth";
import { dashboardApi } from "@/lib/api";

const STATIC_GRAPH = `flowchart TD
  IN([Mensagem do lead<br/>texto ou áudio]) --> G[guardrail]
  IN --> E[extract]
  G --> T{triage}
  E --> T
  T -->|injection / abuso| SR[safe_reply]
  T -->|PARAR| OO[opt_out]
  T -->|pediu humano| H[handoff]
  T -->|quer agendar| AG[agendamento]
  T -->|investimento| INV[investidor]
  T -->|compra / aluguel| C[consultor]
  T -->|indefinido| R[recepcao]
  R --> F[finalize<br/>score + estágio]
  C --> F
  INV --> F
  AG --> F
  H --> F
  F -->|avançou de estágio| S[summarize]
  S --> CRM[crm_sync]
  F --> FIM([fim])
  CRM --> FIM
  SR --> FIM
  OO --> FIM
  CRON([cron de follow-up]) --> FU[followup] --> FIM`;

const BLOCKS: { icon: LucideIcon; title: string; text: string; tag?: string }[] = [
  {
    icon: ShieldCheck,
    title: "Guardrail + extrator em paralelo",
    text: "A cada mensagem, dois nós rodam ao mesmo tempo: um classifica segurança (prompt injection, abuso, opt-out) e outro extrai o perfil estruturado do lead (intenção, orçamento, quartos, região, urgência, ticket…). Paralelizar corta latência.",
    tag: "structured output",
  },
  {
    icon: GitBranch,
    title: "Triagem determinística",
    text: "O roteamento não fica à mercê do LLM: regras explícitas sobre o perfil e os sinais da mensagem escolhem o especialista. Fluxo previsível, testável e auditável.",
  },
  {
    icon: Users,
    title: "Especialistas (multiagente)",
    text: "Recepção descobre a intenção; consultora residencial qualifica compra/aluguel e mostra imóveis; consultora de investimentos calcula rentabilidade e leva à especialista; agendamento consulta a agenda e marca visitas. Cada um é um agente ReAct com suas ferramentas.",
    tag: "LangGraph + LangChain",
  },
  {
    icon: Database,
    title: "RAG híbrido",
    text: "Busca de imóveis combina filtros SQL (finalidade, preço, quartos, região) com similaridade semântica no pgvector, relaxando critérios com transparência quando não há match exato. FAQ (financiamento, ITBI, garantias…) também via embeddings.",
    tag: "pgvector",
  },
  {
    icon: Gauge,
    title: "Score e estágio",
    text: "O nó finalize calcula score 0–100 (completude do perfil, urgência, forma de pagamento, engajamento, agendamento) e classifica o lead em quente, morno ou frio, movendo-o no funil.",
  },
  {
    icon: FileText,
    title: "Resumo inteligente",
    text: "Quando o lead avança (qualificado, agendado, encaminhado) ou a cada algumas mensagens, a IA gera um resumo estruturado para o corretor: perfil, necessidades, objeções, próximos passos e dica de abordagem.",
  },
  {
    icon: Network,
    title: "Integração com CRM",
    text: "Leads qualificados viram contato + negócio + nota no HubSpot, com o resumo anexado, sem digitação manual.",
    tag: "HubSpot",
  },
  {
    icon: Timer,
    title: "Follow-up automático",
    text: "Um job periódico encontra leads que pararam de responder e o agente escreve uma retomada contextual (3 tentativas com estratégias diferentes). Sem resposta, o lead vira perdido.",
  },
  {
    icon: BrainCircuit,
    title: "Memória conversacional",
    text: "O histórico vive no checkpointer Postgres do LangGraph (por thread/lead) e o perfil extraído é persistido no banco — a conversa continua de onde parou, inclusive após dias.",
    tag: "checkpointer",
  },
  {
    icon: Mic,
    title: "Voz",
    text: "Áudios do lead (site ou Telegram) são transcritos (STT) e o agente responde também em áudio (TTS), com tom de consultora.",
  },
  {
    icon: Lock,
    title: "LGPD e segurança",
    text: "Aviso de privacidade no primeiro contato, opt-out com PARAR, exclusão total dos dados pelo painel, mascaramento de PII em logs/traces, rate limit e tokens para painel, cron e webhook.",
  },
  {
    icon: Activity,
    title: "Observabilidade",
    text: "Cada turno é rastreado no Langfuse (nós, tool calls, latência, custo), com sessão por lead. O painel mostra tempo de resposta médio e p90.",
    tag: "Langfuse",
  },
];

export default function HowItWorksPage() {
  const { token } = useAuth();
  const graph = useQuery({ queryKey: ["agent-graph"], queryFn: dashboardApi.graph, enabled: Boolean(token), staleTime: Infinity });
  const definition = graph.data?.mermaid ?? STATIC_GRAPH;

  return (
    <PageShell>
      <PageHeader
        title="Como a IA funciona"
        description="Arquitetura do agente SDR: um grafo LangGraph com supervisor determinístico e especialistas."
      />

      <Card>
        <CardHeader className="flex-row items-start justify-between gap-3">
          <div className="space-y-1">
            <CardTitle className="flex items-center gap-2">
              <MessagesSquare className="size-4 text-gold" /> Grafo do agente
            </CardTitle>
            <CardDescription>
              {graph.data
                ? "Gerado ao vivo a partir do grafo compilado no backend."
                : "Versão ilustrativa. Entre no painel para ver o grafo gerado ao vivo pelo backend."}
            </CardDescription>
          </div>
          {!token && (
            <Button variant="outline" size="sm" asChild>
              <Link to="/painel">Entrar</Link>
            </Button>
          )}
        </CardHeader>
        <CardContent>
          <MermaidDiagram definition={definition} />
        </CardContent>
      </Card>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {BLOCKS.map(({ icon: Icon, title, text, tag }) => (
          <Card key={title} className="flex flex-col gap-3 p-5">
            <div className="flex items-center justify-between gap-2">
              <span className="flex size-9 items-center justify-center rounded-lg bg-gold-soft text-accent-foreground">
                <Icon className="size-4" />
              </span>
              {tag && <Badge variant="muted">{tag}</Badge>}
            </div>
            <h3 className="font-semibold">{title}</h3>
            <p className="text-sm text-muted-foreground">{text}</p>
          </Card>
        ))}
      </div>

      <Card className="flex flex-col gap-4 p-5 sm:flex-row sm:items-center">
        <Send className="size-6 shrink-0 text-gold" />
        <p className="flex-1 text-sm text-muted-foreground">
          Os canais (chat do site e Telegram) chegam no mesmo serviço de conversa, então o agente, a memória e o painel são
          os mesmos independentemente de onde o lead escreve.
        </p>
        <Button asChild>
          <Link to="/">
            <CalendarCheck /> Testar no chat
          </Link>
        </Button>
      </Card>
    </PageShell>
  );
}
