import type {
  AppointmentKind,
  Channel,
  Intent,
  InvestmentGoal,
  LeadProfile,
  PaymentMethod,
  PropertyKind,
  Stage,
  Temperature,
  Urgency,
} from "@/lib/types";

const TIME_ZONE = "America/Sao_Paulo";

const brlFormatter = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 });
const numberFormatter = new Intl.NumberFormat("pt-BR");
const percentFormatter = new Intl.NumberFormat("pt-BR", { style: "percent", maximumFractionDigits: 1 });

export function brl(value: number | null | undefined) {
  return value == null ? "—" : brlFormatter.format(value);
}

export function brlShort(value: number) {
  if (value >= 1_000_000) {
    return `R$ ${(value / 1_000_000).toLocaleString("pt-BR", { maximumFractionDigits: 2 })} mi`;
  }
  if (value >= 10_000) return `R$ ${Math.round(value / 1000).toLocaleString("pt-BR")} mil`;
  return brl(value);
}

export function num(value: number | null | undefined) {
  return value == null ? "—" : numberFormatter.format(value);
}

export function percent(value: number) {
  return percentFormatter.format(value);
}

export function seconds(ms: number | null | undefined) {
  if (!ms) return "—";
  return `${(ms / 1000).toLocaleString("pt-BR", { maximumFractionDigits: 1 })} s`;
}

export function time(iso: string | null | undefined) {
  if (!iso) return "";
  return new Intl.DateTimeFormat("pt-BR", { hour: "2-digit", minute: "2-digit", timeZone: TIME_ZONE }).format(
    new Date(iso),
  );
}

export function dateTime(iso: string | null | undefined) {
  if (!iso) return "—";
  return new Intl.DateTimeFormat("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: TIME_ZONE,
  }).format(new Date(iso));
}

export function dayKey(iso: string) {
  return new Intl.DateTimeFormat("en-CA", { timeZone: TIME_ZONE }).format(new Date(iso));
}

export function longDay(iso: string) {
  const label = new Intl.DateTimeFormat("pt-BR", {
    weekday: "long",
    day: "2-digit",
    month: "long",
    timeZone: TIME_ZONE,
  }).format(new Date(iso));
  return label.charAt(0).toUpperCase() + label.slice(1);
}

export function shortDate(isoDate: string) {
  const [, month, day] = isoDate.split("-");
  return `${day}/${month}`;
}

export function relative(iso: string | null | undefined) {
  if (!iso) return "—";
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 45) return "agora";
  if (diff < 3600) return `há ${Math.round(diff / 60)} min`;
  if (diff < 86400) return `há ${Math.round(diff / 3600)} h`;
  if (diff < 86400 * 7) return `há ${Math.round(diff / 86400)} d`;
  return dateTime(iso);
}

export const STAGE_ORDER: Stage[] = ["novo", "em_qualificacao", "qualificado", "agendado", "handoff", "perdido", "opt_out"];

export const STAGE_LABELS: Record<Stage, string> = {
  novo: "Novo",
  em_qualificacao: "Em qualificação",
  qualificado: "Qualificado",
  agendado: "Agendado",
  handoff: "Com corretor",
  perdido: "Perdido",
  opt_out: "Opt-out",
};

export const TEMPERATURE_LABELS: Record<Temperature, string> = { quente: "Quente", morno: "Morno", frio: "Frio" };

export const INTENT_LABELS: Record<Intent, string> = {
  compra: "Compra",
  aluguel: "Aluguel",
  investimento: "Investimento",
  indefinido: "Indefinido",
};

export const URGENCY_LABELS: Record<Urgency, string> = {
  imediata: "Imediata (até 1 mês)",
  ate_3_meses: "Até 3 meses",
  "3_a_6_meses": "De 3 a 6 meses",
  acima_6_meses: "Mais de 6 meses",
  sem_pressa: "Sem pressa",
};

export const PAYMENT_LABELS: Record<PaymentMethod, string> = {
  a_vista: "À vista",
  financiamento: "Financiamento",
  fgts: "FGTS",
  consorcio: "Consórcio",
  permuta: "Permuta",
  misto: "Misto",
};

export const GOAL_LABELS: Record<InvestmentGoal, string> = {
  renda: "Renda com aluguel",
  valorizacao: "Valorização",
  renda_e_valorizacao: "Renda e valorização",
};

export const PROPERTY_KIND_LABELS: Record<PropertyKind, string> = {
  casa: "Casa",
  casa_condominio: "Casa em condomínio",
  apartamento: "Apartamento",
  terreno: "Terreno",
  chacara: "Chácara",
  comercial: "Comercial",
};

export const CHANNEL_LABELS: Record<Channel, string> = { web: "Site", telegram: "Telegram" };

export const APPOINTMENT_LABELS: Record<AppointmentKind, string> = {
  visita: "Visita ao imóvel",
  reuniao: "Reunião por vídeo",
  reuniao_especialista: "Reunião com especialista",
};

export const AGENT_LABELS: Record<string, string> = {
  recepcao: "Recepção",
  consultor: "Consultora residencial",
  investidor: "Consultora de investimentos",
  agendamento: "Agendamento",
  handoff: "Handoff p/ corretor",
  opt_out: "Opt-out",
  safe_reply: "Guardrail",
  followup: "Follow-up",
  fallback: "Fallback",
  sistema: "Sistema",
};

export function agentLabel(agent: string | null | undefined) {
  if (!agent) return "Agente";
  return AGENT_LABELS[agent] ?? agent;
}

export function profileEntries(profile: LeadProfile): { label: string; value: string }[] {
  const rentLabel = profile.intent === "aluguel" ? "/mês" : "";
  const entries: [string, string | null][] = [
    ["Nome", profile.name],
    ["Objetivo", profile.intent !== "indefinido" ? INTENT_LABELS[profile.intent] : null],
    ["Tipo de imóvel", profile.property_type ? PROPERTY_KIND_LABELS[profile.property_type] : null],
    ["Regiões", profile.regions.length ? profile.regions.join(", ") : null],
    ["Orçamento mín.", profile.budget_min != null ? `${brl(profile.budget_min)}${rentLabel}` : null],
    ["Orçamento máx.", profile.budget_max != null ? `${brl(profile.budget_max)}${rentLabel}` : null],
    ["Quartos", profile.bedrooms != null ? `${profile.bedrooms}+` : null],
    ["Vagas", profile.parking != null ? `${profile.parking}+` : null],
    ["Prazo", profile.urgency ? URGENCY_LABELS[profile.urgency] : null],
    ["Pagamento", profile.payment_method ? PAYMENT_LABELS[profile.payment_method] : null],
    ["Crédito aprovado", profile.credit_approved == null ? null : profile.credit_approved ? "Sim" : "Não"],
    ["Ticket p/ investir", profile.investment_ticket != null ? brl(profile.investment_ticket) : null],
    ["Objetivo do investimento", profile.investment_goal ? GOAL_LABELS[profile.investment_goal] : null],
    ["Retorno esperado", profile.expected_return],
    ["Horizonte", profile.investment_horizon],
    ["Preferências", profile.preferences.length ? profile.preferences.join(", ") : null],
    ["Objeções", profile.objections.length ? profile.objections.join(", ") : null],
    ["Imóveis de interesse", profile.interested_properties.length ? profile.interested_properties.join(", ") : null],
    ["E-mail", profile.email],
    ["Telefone", profile.phone],
  ];
  return entries.filter((entry): entry is [string, string] => Boolean(entry[1])).map(([label, value]) => ({ label, value }));
}

export const EVENT_LABELS: Record<string, string> = {
  mudanca_estagio: "Mudança de estágio",
  imoveis_apresentados: "Imóveis apresentados",
  agendamento_criado: "Agendamento criado",
  followup_enviado: "Follow-up enviado",
  handoff: "Encaminhado ao corretor",
  crm_sincronizado: "Sincronizado com CRM",
  crm_erro: "Erro no CRM",
  guardrail_bloqueio: "Bloqueado pelo guardrail",
  opt_out: "Opt-out (LGPD)",
  lead_perdido: "Lead marcado como perdido",
  ia_pausada: "IA pausada",
  ia_retomada: "IA retomada",
};

export function describeEvent(type: string, payload: Record<string, unknown>) {
  const text = (key: string) => (payload[key] == null ? "" : String(payload[key]));
  switch (type) {
    case "mudanca_estagio":
      return `${STAGE_LABELS[text("de") as Stage] ?? text("de")} → ${STAGE_LABELS[text("para") as Stage] ?? text("para")}`;
    case "imoveis_apresentados":
      return Array.isArray(payload.codes) ? (payload.codes as string[]).join(", ") : "";
    case "agendamento_criado":
      return [
        APPOINTMENT_LABELS[text("kind") as AppointmentKind] ?? text("kind"),
        payload.starts_at ? dateTime(text("starts_at")) : "",
        text("broker"),
        text("property"),
      ]
        .filter(Boolean)
        .join(" · ");
    case "followup_enviado":
      return `Tentativa ${text("tentativa")}${payload.entregue === false ? " (não entregue)" : ""}`;
    case "handoff":
      return [text("reason"), text("broker")].filter(Boolean).join(" · ");
    case "crm_sincronizado":
      return `Contato ${text("contact_id")} · Negócio ${text("deal_id")}`;
    case "crm_erro":
      return text("erro");
    case "guardrail_bloqueio":
      return [text("category"), text("reason")].filter(Boolean).join(" · ");
    case "lead_perdido":
      return `${text("followups")} follow-ups sem resposta`;
    default:
      return "";
  }
}
