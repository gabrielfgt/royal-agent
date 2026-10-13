import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, ExternalLink, LoaderCircle, Pause, Play, Send, Trash2 } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router";
import { toast } from "sonner";

import { AppointmentRow } from "@/components/dashboard/appointment-list";
import { PageShell } from "@/components/layout";
import { ChannelBadge, IntentBadge, StageBadge, TemperatureBadge } from "@/components/lead/badges";
import { EventsTimeline } from "@/components/lead/events-timeline";
import { ProfileFields } from "@/components/lead/profile-fields";
import { ScoreRing } from "@/components/lead/score-ring";
import { SummaryCard } from "@/components/lead/summary-card";
import { Transcript } from "@/components/lead/transcript";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { dashboardApi } from "@/lib/api";
import { dateTime, relative } from "@/lib/format";

export default function LeadDetailPage() {
  const { id = "" } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [confirmDelete, setConfirmDelete] = useState(false);
  const detail = useQuery({ queryKey: ["lead", id], queryFn: () => dashboardApi.lead(id), refetchInterval: 8_000 });

  const refresh = () => queryClient.invalidateQueries({ queryKey: ["lead", id] });

  const summary = useMutation({
    mutationFn: () => dashboardApi.regenerateSummary(id),
    onSuccess: () => {
      toast.success("Resumo atualizado.");
      void refresh();
    },
    onError: (error) => toast.error(error.message),
  });

  const pause = useMutation({
    mutationFn: (paused: boolean) => dashboardApi.pause(id, paused),
    onSuccess: (lead) => {
      toast.success(lead.ai_paused ? "IA pausada. O corretor assume a conversa." : "IA retomada.");
      void refresh();
    },
    onError: (error) => toast.error(error.message),
  });

  const followup = useMutation({
    mutationFn: () => dashboardApi.followupNow(id),
    onSuccess: (result) => {
      if (result.sent) toast.success("Follow-up enviado.");
      else toast.info("Follow-up não enviado: o lead respondeu por último, está pausado/opt-out ou já atingiu o limite.");
      void refresh();
    },
    onError: (error) => toast.error(error.message),
  });

  const remove = useMutation({
    mutationFn: () => dashboardApi.deleteLead(id),
    onSuccess: () => {
      toast.success("Dados do lead excluídos.");
      void queryClient.invalidateQueries();
      navigate("/painel");
    },
    onError: (error) => toast.error(error.message),
  });

  if (detail.isError) {
    return (
      <PageShell className="flex flex-col items-center gap-4 py-20 text-center">
        <p className="text-lg font-semibold">Lead não encontrado</p>
        <Button asChild variant="outline">
          <Link to="/painel">
            <ArrowLeft /> Voltar ao painel
          </Link>
        </Button>
      </PageShell>
    );
  }

  if (!detail.data) {
    return (
      <PageShell>
        <Skeleton className="h-24" />
        <div className="grid gap-4 lg:grid-cols-3">
          <Skeleton className="h-96 lg:col-span-2" />
          <Skeleton className="h-96" />
        </div>
      </PageShell>
    );
  }

  const { lead, messages, appointments, events } = detail.data;

  return (
    <PageShell>
      <Button variant="ghost" size="sm" asChild className="-ml-2 w-fit">
        <Link to="/painel">
          <ArrowLeft /> Painel
        </Link>
      </Button>

      <Card className="p-5">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-center">
          <div className="flex min-w-0 flex-1 items-center gap-4">
            <ScoreRing score={lead.score} temperature={lead.temperature} size={80} />
            <div className="min-w-0 space-y-2">
              <h1 className="truncate text-2xl font-semibold tracking-tight">{lead.name ?? "Lead sem nome"}</h1>
              <div className="flex flex-wrap gap-1.5">
                <TemperatureBadge temperature={lead.temperature} />
                <StageBadge stage={lead.stage} />
                <IntentBadge intent={lead.intent} />
                {(lead.channels?.length ? lead.channels : [lead.channel]).map((channel) => (
                  <ChannelBadge key={channel} channel={channel} />
                ))}
                {lead.ai_paused && <Badge variant="warm">IA pausada</Badge>}
                {lead.opted_out && <Badge variant="destructive">Opt-out</Badge>}
              </div>
              <p className="text-xs text-muted-foreground">
                Criado {dateTime(lead.created_at)} · última mensagem do lead {relative(lead.last_inbound_at)} ·{" "}
                {lead.followup_count} follow-up(s) na sequência atual
              </p>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            {lead.crm_url && (
              <Button variant="outline" size="sm" asChild>
                <a href={lead.crm_url} target="_blank" rel="noreferrer">
                  <ExternalLink /> Abrir no HubSpot
                </a>
              </Button>
            )}
            {!lead.crm_url && lead.crm_contact_id && <Badge variant="success">No CRM · #{lead.crm_contact_id}</Badge>}
            <Button variant="outline" size="sm" onClick={() => pause.mutate(!lead.ai_paused)} disabled={pause.isPending}>
              {lead.ai_paused ? <Play /> : <Pause />}
              {lead.ai_paused ? "Retomar IA" : "Pausar IA"}
            </Button>
            <Button variant="outline" size="sm" onClick={() => followup.mutate()} disabled={followup.isPending}>
              {followup.isPending ? <LoaderCircle className="animate-spin" /> : <Send />}
              Enviar follow-up agora
            </Button>
            <Button variant="ghost" size="sm" className="text-destructive hover:bg-destructive/10 hover:text-destructive" onClick={() => setConfirmDelete(true)}>
              <Trash2 /> Excluir dados (LGPD)
            </Button>
          </div>
        </div>
        {lead.handoff_reason && (
          <p className="mt-4 rounded-lg bg-secondary px-3 py-2 text-sm">
            <span className="font-medium">Encaminhado ao corretor:</span> {lead.handoff_reason}
          </p>
        )}
      </Card>

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="space-y-4 lg:col-span-2">
          <SummaryCard
            summary={lead.summary}
            updatedAt={lead.summary_updated_at}
            onRegenerate={() => summary.mutate()}
            regenerating={summary.isPending}
          />
          <Card>
            <CardHeader>
              <CardTitle>Conversa</CardTitle>
              <CardDescription>{messages.length} mensagens · tags mostram qual especialista respondeu</CardDescription>
            </CardHeader>
            <CardContent>
              <Transcript messages={messages} />
            </CardContent>
          </Card>
        </div>
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Perfil extraído</CardTitle>
              <CardDescription>Preenchido pela IA a cada mensagem</CardDescription>
            </CardHeader>
            <CardContent>
              <ProfileFields profile={lead.profile} missing={lead.missing_fields} compact />
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Compromissos</CardTitle>
            </CardHeader>
            <CardContent>
              {appointments.length ? (
                <div className="divide-y">
                  {appointments.map((appointment) => (
                    <AppointmentRow key={appointment.id} appointment={appointment} />
                  ))}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">Nenhum compromisso agendado.</p>
              )}
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Linha do tempo</CardTitle>
            </CardHeader>
            <CardContent>
              <EventsTimeline events={events} />
            </CardContent>
          </Card>
        </div>
      </div>

      <Dialog open={confirmDelete} onOpenChange={setConfirmDelete}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Excluir todos os dados deste lead?</DialogTitle>
            <DialogDescription>
              Remove perfil, conversa, agendamentos, eventos e a memória do agente (direito de eliminação da LGPD). Esta
              ação não pode ser desfeita. Registros já enviados ao CRM precisam ser removidos lá.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <DialogClose asChild>
              <Button variant="outline">Cancelar</Button>
            </DialogClose>
            <Button variant="destructive" onClick={() => remove.mutate()} disabled={remove.isPending}>
              {remove.isPending ? <LoaderCircle className="animate-spin" /> : <Trash2 />}
              Excluir definitivamente
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </PageShell>
  );
}
