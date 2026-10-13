from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, RootModel

from sdr.models import AppointmentKind, BrokerSummary, Channel, Intent, LeadProfile, PropertyKind, Stage, Temperature

Purpose = Literal["venda", "aluguel"]
MessageRole = Literal["lead", "agent", "system"]
MessageKind = Literal["text", "audio", "followup", "notice"]
AppointmentStatus = Literal["agendado", "remarcado", "cancelado"]

UUID_PATTERN = r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
SESSION_PATTERN = r"^[A-Za-z0-9_-]{8,64}$"

LEAD_ID_EXAMPLE = "9b49ab0b-dd4f-4ca2-8bc0-472e3d0d7b31"
TIMESTAMP_EXAMPLE = "2026-10-12T23:56:30.697195+00:00"


def timestamp(description: str, *, nullable: bool = True) -> Any:
    return Field(
        default=None if nullable else ...,
        description=f"{description} (ISO 8601 com fuso horário).",
        examples=[TIMESTAMP_EXAMPLE],
        json_schema_extra={"format": "date-time"},
    )


class ErrorOut(BaseModel):
    detail: str = Field(description="Mensagem de erro em português.", examples=["Lead não encontrado"])


class LeadOut(BaseModel):
    model_config = ConfigDict(
        title="Lead",
        json_schema_extra={
            "description": "Lead atendido pelo agente, com perfil extraído pela IA, score, estágio do funil e resumo."
        },
    )

    id: str = Field(description="Identificador do lead (UUID).", examples=[LEAD_ID_EXAMPLE])
    channel: Channel = Field(description="Canal de origem do lead.", examples=["web"])
    channels: list[Channel] = Field(
        description="Canais vinculados ao lead (unificados pelo telefone), na ordem em que apareceram.",
        examples=[["web", "telegram"]],
    )
    name: str | None = Field(description="Nome informado pelo lead ou o nome do perfil no canal.", examples=["Marcos"])
    stage: Stage = Field(description="Estágio no funil comercial.", examples=["agendado"])
    score: int = Field(ge=0, le=100, description="Score de qualificação (0–100).", examples=[70])
    temperature: Temperature = Field(
        description="Temperatura derivada do score: quente ≥ 70, morno ≥ 40, frio abaixo disso.", examples=["quente"]
    )
    intent: Intent = Field(description="Intenção identificada pela IA.", examples=["investimento"])
    profile: LeadProfile = Field(description="Perfil estruturado extraído da conversa a cada mensagem.")
    missing_fields: list[str] = Field(
        description="Informações de qualificação que ainda faltam descobrir, em linguagem natural.",
        examples=[["faixa de preço", "prazo/urgência"]],
    )
    summary: BrokerSummary | dict[str, Any] | None = Field(
        description="Resumo estruturado para o corretor (gerado pela IA quando o lead avança no funil)."
    )
    summary_updated_at: str | None = timestamp("Momento da última geração do resumo")
    handoff_reason: str | None = Field(
        description="Motivo do encaminhamento para um corretor humano, quando houver.",
        examples=["Lead pediu atendimento humano"],
    )
    ai_paused: bool = Field(description="Se a IA está pausada para este lead (corretor assumiu).", examples=[False])
    opted_out: bool = Field(description="Se o lead pediu para não receber mais mensagens (LGPD).", examples=[False])
    followup_count: int = Field(ge=0, description="Tentativas de follow-up na sequência atual.", examples=[1])
    reengaged_count: int = Field(
        ge=0, description="Vezes em que o lead voltou a responder após follow-up.", examples=[0]
    )
    created_at: str = timestamp("Criação do lead", nullable=False)
    last_inbound_at: str | None = timestamp("Última mensagem enviada pelo lead")
    last_outbound_at: str | None = timestamp("Última mensagem enviada pelo agente")
    crm_contact_id: str | None = Field(description="ID do contato no HubSpot.", examples=["987654321"])
    crm_deal_id: str | None = Field(description="ID do negócio no HubSpot.", examples=["123456789"])
    crm_url: str | None = Field(
        description="Link do contato no HubSpot (requer HUBSPOT_PORTAL_ID).",
        examples=["https://app.hubspot.com/contacts/12345678/record/0-1/987654321"],
    )
    message_count: int | None = Field(
        description="Total de mensagens da conversa (preenchido na listagem de leads).", examples=[12]
    )
    last_message: str | None = Field(
        description="Última mensagem da conversa (preenchido na listagem de leads).",
        examples=["Pronto, Marcos! Sua reunião ficou marcada para quinta-feira, 15/10, às 10h."],
    )


class MessageOut(BaseModel):
    model_config = ConfigDict(title="Mensagem")

    id: int = Field(description="ID sequencial da mensagem (use em `after_id` no polling).", examples=[27])
    role: MessageRole = Field(description="Autor: lead, agente (Sofia) ou sistema.", examples=["agent"])
    content: str = Field(
        description="Texto da mensagem. Mensagens do agente usam linha em branco para separar balões.",
        examples=["Oi, Marcos! Separei três opções com foco em renda.\n\nQual delas chamou mais sua atenção?"],
    )
    kind: MessageKind = Field(
        description="text: texto; audio: áudio transcrito; followup: retomada automática; notice: aviso do sistema.",
        examples=["text"],
    )
    agent: str | None = Field(
        description=(
            "Especialista que respondeu: recepcao, consultor, investidor, agendamento, handoff, opt_out, "
            "safe_reply, followup, fallback ou sistema."
        ),
        examples=["investidor"],
    )
    latency_ms: int | None = Field(description="Tempo até a resposta do agente, em milissegundos.", examples=[5433])
    created_at: str = timestamp("Envio da mensagem", nullable=False)


class AppointmentOut(BaseModel):
    model_config = ConfigDict(title="Compromisso")

    id: str = Field(description="ID do compromisso (UUID).", examples=["a01f3394-f0f9-4614-b7c6-93f4a08d55c6"])
    lead_id: str = Field(description="ID do lead (UUID).", examples=[LEAD_ID_EXAMPLE])
    lead_name: str | None = Field(description="Nome do lead (preenchido na agenda geral).", examples=["Marcos"])
    lead_temperature: Temperature | None = Field(
        description="Temperatura do lead (preenchido na agenda geral).", examples=["quente"]
    )
    broker_name: str = Field(description="Corretor ou especialista responsável.", examples=["Juliana Prado"])
    kind: AppointmentKind = Field(
        description="visita: no imóvel; reuniao: vídeo com corretor; reuniao_especialista: vídeo com especialista.",
        examples=["reuniao_especialista"],
    )
    starts_at: str = timestamp("Início do compromisso", nullable=False)
    property_code: str | None = Field(description="Código do imóvel visitado.", examples=["RY-018"])
    property_title: str | None = Field(description="Título do imóvel.", examples=["Apartamento de 3 dorms em Saúde"])
    property_neighborhood: str | None = Field(description="Bairro do imóvel.", examples=["Saúde"])
    status: AppointmentStatus = Field(description="Situação do compromisso.", examples=["agendado"])
    notes: str | None = Field(description="Observações registradas pelo agente.", examples=[None])


class EventOut(BaseModel):
    model_config = ConfigDict(title="Evento")

    id: int = Field(description="ID sequencial do evento.", examples=[47])
    type: str = Field(
        description=(
            "Tipo: mudanca_estagio, imoveis_apresentados, agendamento_criado, transferencia_agente, followup_enviado, "
            "handoff, crm_sincronizado, crm_erro, guardrail_bloqueio, opt_out, lead_perdido, ia_pausada, ia_retomada."
        ),
        examples=["imoveis_apresentados"],
    )
    payload: dict[str, Any] = Field(
        description="Dados do evento, conforme o tipo.",
        examples=[{"agent": "consultor", "codes": ["RY-018", "RY-019"]}],
    )
    created_at: str = timestamp("Momento do evento", nullable=False)


class PropertyOut(BaseModel):
    model_config = ConfigDict(title="Imóvel")

    code: str = Field(description="Referência do imóvel no portfólio.", examples=["277"])
    title: str = Field(description="Título comercial.", examples=["Casa em Vila Santa Emília"])
    purpose: Purpose = Field(description="Finalidade.", examples=["venda"])
    kind: PropertyKind = Field(description="Tipo de imóvel.", examples=["casa"])
    neighborhood: str = Field(description="Bairro.", examples=["Vila Santa Emília"])
    city: str = Field(description="Cidade.", examples=["Tatuí"])
    state: str = Field(description="UF.", examples=["SP"])
    condominium: str | None = Field(description="Condomínio, quando houver.", examples=["Reserva dos Ipês I"])
    street: str | None = Field(description="Logradouro informado no anúncio.", examples=["Rua das Palmeiras, 100"])
    postal_code: str | None = Field(description="CEP.", examples=["18270000"])
    latitude: float | None = Field(description="Latitude geocodificada (OpenStreetMap).", examples=[-23.352])
    longitude: float | None = Field(description="Longitude geocodificada (OpenStreetMap).", examples=[-47.8625])
    geo_precision: Literal["endereco", "bairro", "cidade"] | None = Field(
        description="Precisão da geocodificação.", examples=["endereco"]
    )
    price: float = Field(description="Preço de venda ou aluguel mensal, em reais.", examples=[440000.0])
    condo_fee: float = Field(description="Condomínio mensal, em reais.", examples=[253.0])
    iptu_monthly: float = Field(description="IPTU mensal aproximado, em reais.", examples=[83.33])
    area_m2: int = Field(description="Área útil/privativa em m² (0 quando não informada).", examples=[189])
    area_total_m2: int | None = Field(description="Área total ou do terreno em m².", examples=[150])
    bedrooms: int = Field(description="Quartos.", examples=[3])
    suites: int = Field(description="Suítes.", examples=[3])
    bathrooms: int = Field(description="Banheiros.", examples=[4])
    parking: int = Field(description="Vagas de garagem.", examples=[2])
    year_built: int | None = Field(description="Ano de construção.", examples=[2012])
    features: list[str] = Field(description="Características do imóvel.", examples=[["Ar Condicionado"]])
    nearby: list[str] = Field(description="Proximidades.", examples=[["Escola", "Supermercado"]])
    description: str = Field(description="Descrição do anúncio, usada na busca semântica (RAG).")
    estimated_rent: float | None = Field(
        description="Aluguel mensal estimado (imóveis residenciais à venda; base do cálculo de yield).",
        examples=[1980.0],
    )
    pet_friendly: bool = Field(description="Aceita pet.", examples=[True])
    furnished: bool = Field(description="Mobiliado.", examples=[False])
    photos: list[str] = Field(description="URLs das fotos, na ordem da galeria.", examples=[["https://..."]])
    source_url: str | None = Field(description="Página de origem do anúncio importado.")
    video_url: str | None = Field(description="Vídeo do imóvel, quando houver.")


class MetricsTotals(BaseModel):
    leads: int = Field(description="Total de leads.", examples=[12])
    hot: int = Field(description="Leads quentes.", examples=[2])
    qualified: int = Field(description="Leads qualificados, agendados ou com corretor.", examples=[6])
    scheduled: int = Field(description="Leads com compromisso agendado.", examples=[2])
    handoff: int = Field(description="Leads encaminhados para corretor.", examples=[2])
    lost: int = Field(description="Leads perdidos (esgotaram os follow-ups).", examples=[0])
    opted_out: int = Field(description="Leads que pediram opt-out.", examples=[0])
    reengaged: int = Field(description="Respostas recebidas após follow-up.", examples=[1])
    leads_today: int = Field(description="Leads criados nas últimas 24 horas.", examples=[12])
    followups_sent: int = Field(description="Follow-ups enviados.", examples=[8])
    audio_messages: int = Field(description="Mensagens de áudio recebidas.", examples=[6])


class ResponseTime(BaseModel):
    avg_ms: int = Field(description="Tempo médio de resposta do agente, em ms.", examples=[7482])
    p90_ms: int = Field(description="Percentil 90 do tempo de resposta, em ms.", examples=[9745])


class BreakdownItem(BaseModel):
    key: str = Field(description="Valor agrupado (estágio, temperatura, intenção ou canal).", examples=["agendado"])
    count: int = Field(description="Quantidade de leads.", examples=[2])


class DailyCount(BaseModel):
    date: str = Field(
        description="Dia (fuso America/Sao_Paulo).", examples=["2026-10-12"], json_schema_extra={"format": "date"}
    )
    count: int = Field(description="Leads criados no dia.", examples=[12])


class MetricsOut(BaseModel):
    model_config = ConfigDict(title="Métricas do painel")

    totals: MetricsTotals
    response_time: ResponseTime
    by_stage: list[BreakdownItem] = Field(description="Leads por estágio do funil.")
    by_temperature: list[BreakdownItem] = Field(description="Leads por temperatura.")
    by_intent: list[BreakdownItem] = Field(description="Leads por intenção.")
    by_channel: list[BreakdownItem] = Field(description="Leads por canal.")
    leads_per_day: list[DailyCount] = Field(description="Novos leads por dia nos últimos 14 dias.")
    upcoming_appointments: list[AppointmentOut] = Field(description="Próximos compromissos (até 8).")


class LeadListOut(BaseModel):
    items: list[LeadOut] = Field(description="Leads ordenados pela atividade mais recente.")


class LeadDetailOut(BaseModel):
    model_config = ConfigDict(title="Detalhe do lead")

    lead: LeadOut
    messages: list[MessageOut] = Field(description="Transcrição completa da conversa.")
    appointments: list[AppointmentOut] = Field(description="Compromissos futuros do lead.")
    events: list[EventOut] = Field(description="Linha do tempo de eventos (mais recentes primeiro).")


class SummaryOut(BaseModel):
    summary: BrokerSummary | dict[str, Any] = Field(description="Resumo recém-gerado para o corretor.")


class PauseIn(BaseModel):
    paused: bool = Field(description="true pausa a IA para o lead; false retoma o atendimento.", examples=[True])


class FollowupRunIn(BaseModel):
    force: bool = Field(
        False,
        description="Ignora o intervalo mínimo entre tentativas (útil em demonstrações).",
        examples=[True],
    )


class FollowupItem(BaseModel):
    model_config = ConfigDict(title="Follow-up enviado")

    lead_id: str = Field(description="ID do lead (UUID).", examples=[LEAD_ID_EXAMPLE])
    attempt: int = Field(description="Número da tentativa na sequência (1, 2 ou 3).", examples=[1])
    message_id: int = Field(description="ID da mensagem gravada.", examples=[91])
    text: str = Field(
        description="Mensagem de retomada gerada pela IA.",
        examples=["Oi, Paula! Tudo certo? Conseguiu pensar nas opções da Saúde que te mandei?"],
    )


class FollowupNowOut(BaseModel):
    sent: bool = Field(description="Se um follow-up foi enviado.", examples=[True])
    followup: FollowupItem | None = Field(description="Detalhes do follow-up enviado.")


class FollowupRunOut(BaseModel):
    model_config = ConfigDict(title="Resultado da rodada de follow-up")

    sent: list[FollowupItem] = Field(description="Follow-ups enviados nesta rodada.")
    lost: list[str] = Field(
        description="IDs dos leads marcados como perdidos (esgotaram as tentativas).", examples=[[LEAD_ID_EXAMPLE]]
    )


class AppointmentListOut(BaseModel):
    items: list[AppointmentOut] = Field(description="Compromissos ordenados por data.")


class PropertyListOut(BaseModel):
    items: list[PropertyOut] = Field(description="Imóveis do portfólio simulado.")


class GraphOut(BaseModel):
    mermaid: str = Field(
        description="Diagrama Mermaid gerado a partir do grafo LangGraph compilado.",
        examples=["graph TD;\n\t__start__ --> guardrail;\n\t__start__ --> extract;"],
    )


class AuthCheckOut(BaseModel):
    ok: bool = Field(description="Token válido.", examples=[True])


class HealthOut(BaseModel):
    status: Literal["ok"] = Field(description="API e banco respondendo.", examples=["ok"])
    model: str = Field(description="Modelo de linguagem dos especialistas.", examples=["gpt-6-luna"])
    telegram: bool = Field(description="Canal Telegram configurado.", examples=[True])
    crm: bool = Field(description="Integração com HubSpot configurada.", examples=[True])
    tracing: bool = Field(description="Tracing no Langfuse habilitado.", examples=[False])


class ChatHistoryOut(BaseModel):
    model_config = ConfigDict(title="Histórico do chat")

    lead: LeadOut | None = Field(description="Lead da sessão, ou null se a sessão ainda não conversou.")
    messages: list[MessageOut] = Field(description="Mensagens com id maior que `after_id`.")


class TelegramWebhookOut(BaseModel):
    ok: bool = Field(description="Update aceito.", examples=[True])
    duplicate: bool | None = Field(None, description="Presente quando o update já tinha sido processado.")


class ChatIn(BaseModel):
    model_config = ConfigDict(
        title="Mensagem do lead",
        json_schema_extra={
            "examples": [
                {"session_id": "a8f3k2m9x7q1w5e4r6t0y2u3", "message": "Estou procurando apartamento na zona sul."},
                {
                    "session_id": "inv3st1d0r-r0b3rt0-2026",
                    "message": "Quero investir uns 700 mil em imóveis para renda.",
                    "name": "Roberto",
                },
            ]
        },
    )

    session_id: str = Field(
        pattern=SESSION_PATTERN,
        description="Identificador da sessão do navegador (8–64 caracteres `[A-Za-z0-9_-]`). Identifica o lead web.",
    )
    message: str = Field(min_length=1, description="Texto enviado pelo lead (cortado em 1.500 caracteres).")
    name: str | None = Field(default=None, max_length=60, description="Nome do lead, se conhecido.")


class ReplyData(BaseModel):
    model_config = ConfigDict(title="Evento reply")

    message_id: int = Field(description="ID da mensagem gravada.", examples=[86])
    agent: str = Field(description="Especialista que respondeu.", examples=["consultor"])
    bubbles: list[str] = Field(
        description="Resposta já dividida em balões, na ordem de exibição.",
        examples=[["Boa! Zona sul tem ótimas opções. 😊", "Você está pensando em comprar ou alugar?"]],
    )
    latency_ms: int = Field(description="Tempo desde a mensagem do lead até a resposta.", examples=[5508])


class AudioData(BaseModel):
    model_config = ConfigDict(title="Evento audio")

    message_id: int = Field(description="Mensagem à qual o áudio corresponde.", examples=[86])
    mime: Literal["audio/mpeg", "audio/ogg"] = Field(description="Formato do áudio.", examples=["audio/mpeg"])
    audio_b64: str = Field(
        description="Áudio da resposta em base64 (voz da Sofia).", examples=["SUQzBAAAAAAAI1RTU0U..."]
    )


class NoticeData(BaseModel):
    model_config = ConfigDict(title="Evento notice")

    message_id: int = Field(description="ID do aviso gravado.", examples=[84])
    text: str = Field(
        description="Aviso do sistema (ex.: privacidade/LGPD no primeiro contato).",
        examples=[
            "🔒 Seus dados são usados só para este atendimento, conforme a LGPD. "
            "Se não quiser mais receber mensagens, é só enviar PARAR."
        ],
    )


class TranscriptData(BaseModel):
    model_config = ConfigDict(title="Evento transcript")

    text: str = Field(
        description="Transcrição do áudio enviado pelo lead.",
        examples=["Oi, tudo bem? Eu queria comprar um apartamento de dois quartos em Moema."],
    )


class EmptyData(BaseModel):
    model_config = ConfigDict(title="Sem dados")


class ReplyFrame(BaseModel):
    event: Literal["reply"] = Field(description="Resposta do agente.")
    data: ReplyData


class AudioFrame(BaseModel):
    event: Literal["audio"] = Field(description="Áudio da resposta (quando o lead enviou áudio).")
    data: AudioData


class NoticeFrame(BaseModel):
    event: Literal["notice"] = Field(description="Aviso do sistema exibido no chat.")
    data: NoticeData


class TranscriptFrame(BaseModel):
    event: Literal["transcript"] = Field(description="Transcrição do áudio do lead (primeiro evento em /audio).")
    data: TranscriptData


class LeadFrame(BaseModel):
    event: Literal["lead"] = Field(description="Estado atualizado do lead após o turno (alimenta a Visão do agente).")
    data: LeadOut


class PausedFrame(BaseModel):
    event: Literal["paused"] = Field(description="IA pausada para o lead: a mensagem foi registrada sem resposta.")
    data: EmptyData


class DoneFrame(BaseModel):
    event: Literal["done"] = Field(description="Fim do stream.")
    data: EmptyData


class ChatStreamEvent(
    RootModel[
        Annotated[
            ReplyFrame | AudioFrame | NoticeFrame | TranscriptFrame | LeadFrame | PausedFrame | DoneFrame,
            Field(discriminator="event"),
        ]
    ]
):
    model_config = ConfigDict(
        title="Evento do stream de chat",
        json_schema_extra={
            "description": (
                "Cada evento chega no formato Server-Sent Events: `event: <tipo>` seguido de `data: <JSON>` e uma linha "
                "em branco. Este schema descreve o par tipo/payload de cada evento."
            )
        },
    )
