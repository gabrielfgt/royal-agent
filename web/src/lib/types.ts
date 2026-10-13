export type Intent = "compra" | "aluguel" | "investimento" | "indefinido";
export type Urgency = "imediata" | "ate_3_meses" | "3_a_6_meses" | "acima_6_meses" | "sem_pressa";
export type PaymentMethod = "a_vista" | "financiamento" | "fgts" | "consorcio" | "permuta" | "misto";
export type InvestmentGoal = "renda" | "valorizacao" | "renda_e_valorizacao";
export type PropertyKind = "casa" | "casa_condominio" | "apartamento" | "terreno" | "chacara" | "comercial";
export type Stage = "novo" | "em_qualificacao" | "qualificado" | "agendado" | "handoff" | "perdido" | "opt_out";
export type Temperature = "quente" | "morno" | "frio";
export type Channel = "web" | "telegram";
export type AppointmentKind = "visita" | "reuniao" | "reuniao_especialista";
export type MessageRole = "lead" | "agent" | "system";
export type MessageKind = "text" | "audio" | "followup" | "notice";

export interface LeadProfile {
  name: string | null;
  intent: Intent;
  property_type: PropertyKind | null;
  regions: string[];
  budget_min: number | null;
  budget_max: number | null;
  bedrooms: number | null;
  parking: number | null;
  urgency: Urgency | null;
  payment_method: PaymentMethod | null;
  credit_approved: boolean | null;
  investment_ticket: number | null;
  investment_goal: InvestmentGoal | null;
  expected_return: string | null;
  investment_horizon: string | null;
  preferences: string[];
  objections: string[];
  interested_properties: string[];
  email: string | null;
  phone: string | null;
}

export interface BrokerSummary {
  headline: string;
  profile: string[];
  needs: string[];
  properties_discussed: string[];
  objections: string[];
  next_steps: string[];
  approach_tip: string;
}

export interface Lead {
  id: string;
  channel: Channel;
  channels: Channel[];
  name: string | null;
  stage: Stage;
  score: number;
  temperature: Temperature;
  intent: Intent;
  profile: LeadProfile;
  missing_fields: string[];
  summary: BrokerSummary | null;
  summary_updated_at: string | null;
  handoff_reason: string | null;
  ai_paused: boolean;
  opted_out: boolean;
  followup_count: number;
  reengaged_count: number;
  created_at: string;
  last_inbound_at: string | null;
  last_outbound_at: string | null;
  crm_contact_id: string | null;
  crm_deal_id: string | null;
  crm_url: string | null;
  message_count: number | null;
  last_message: string | null;
}

export interface Message {
  id: number;
  role: MessageRole;
  content: string;
  kind: MessageKind;
  agent: string | null;
  latency_ms: number | null;
  created_at: string;
}

export interface Appointment {
  id: string;
  lead_id: string;
  lead_name: string | null;
  lead_temperature: Temperature | null;
  broker_name: string;
  kind: AppointmentKind;
  starts_at: string;
  property_code: string | null;
  property_title: string | null;
  property_neighborhood: string | null;
  status: string;
  notes: string | null;
}

export interface LeadEvent {
  id: number;
  type: string;
  payload: Record<string, unknown>;
  created_at: string;
}

export interface Property {
  code: string;
  title: string;
  purpose: "venda" | "aluguel";
  kind: PropertyKind;
  neighborhood: string;
  city: string;
  state: string;
  condominium: string | null;
  street: string | null;
  postal_code: string | null;
  latitude: number | null;
  longitude: number | null;
  geo_precision: "endereco" | "bairro" | "cidade" | null;
  price: number;
  condo_fee: number;
  iptu_monthly: number;
  area_m2: number;
  bedrooms: number;
  suites: number;
  bathrooms: number;
  parking: number;
  area_total_m2: number | null;
  year_built: number | null;
  features: string[];
  nearby: string[];
  description: string;
  estimated_rent: number | null;
  pet_friendly: boolean;
  furnished: boolean;
  photos: string[];
  source_url: string | null;
  video_url: string | null;
}

export interface Breakdown {
  key: string;
  count: number;
}

export interface Metrics {
  totals: {
    leads: number;
    hot: number;
    qualified: number;
    scheduled: number;
    handoff: number;
    lost: number;
    opted_out: number;
    reengaged: number;
    leads_today: number;
    followups_sent: number;
    audio_messages: number;
  };
  response_time: { avg_ms: number; p90_ms: number };
  by_stage: Breakdown[];
  by_temperature: Breakdown[];
  by_intent: Breakdown[];
  by_channel: Breakdown[];
  leads_per_day: { date: string; count: number }[];
  upcoming_appointments: Appointment[];
}

export interface LeadDetail {
  lead: Lead;
  messages: Message[];
  appointments: Appointment[];
  events: LeadEvent[];
}

export interface FollowupResult {
  lead_id: string;
  attempt: number;
  message_id: number;
  text: string;
}

export interface FollowupRunResult {
  sent: FollowupResult[];
  lost: string[];
}

export interface ChatHistory {
  lead: Lead | null;
  messages: Message[];
}

export type ChatStreamEvent =
  | { event: "reply"; data: { message_id: number; agent: string; bubbles: string[]; latency_ms: number } }
  | { event: "audio"; data: { message_id: number; mime: string; audio_b64: string } }
  | { event: "notice"; data: { message_id: number; text: string } }
  | { event: "lead"; data: Lead }
  | { event: "transcript"; data: { text: string } }
  | { event: "paused"; data: Record<string, never> }
  | { event: "done"; data: Record<string, never> };
