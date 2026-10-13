import { useQuery } from "@tanstack/react-query";
import { CalendarCheck, Flame, Gauge, RefreshCcw, Search, Send, Sparkles, Users } from "lucide-react";
import { useDeferredValue, useState } from "react";
import { Link } from "react-router";

import { AppointmentList } from "@/components/dashboard/appointment-list";
import { FunnelChart, IntentChart, LeadsPerDayChart, TemperatureChart } from "@/components/dashboard/charts";
import { FollowupRunner } from "@/components/dashboard/followup-runner";
import { KpiCard } from "@/components/dashboard/kpi-card";
import { LeadsTable } from "@/components/dashboard/leads-table";
import { PageHeader, PageShell } from "@/components/layout";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { dashboardApi } from "@/lib/api";
import { INTENT_LABELS, num, percent, seconds, STAGE_LABELS, STAGE_ORDER, TEMPERATURE_LABELS } from "@/lib/format";

export default function DashboardPage() {
  const metrics = useQuery({ queryKey: ["metrics"], queryFn: dashboardApi.metrics, refetchInterval: 10_000 });
  const [stage, setStage] = useState("");
  const [temperature, setTemperature] = useState("");
  const [intent, setIntent] = useState("");
  const [search, setSearch] = useState("");
  const q = useDeferredValue(search.trim());
  const leads = useQuery({
    queryKey: ["leads", stage, temperature, intent, q],
    queryFn: () => dashboardApi.leads({ stage, temperature, intent, q }),
    refetchInterval: 10_000,
  });

  const totals = metrics.data?.totals;
  const qualifiedRate = totals && totals.leads ? totals.qualified / totals.leads : 0;

  return (
    <PageShell>
      <PageHeader
        title="Painel comercial"
        description="Acompanhamento em tempo real dos leads atendidos pela Sofia. Atualiza a cada 10 segundos."
        actions={<FollowupRunner />}
      />

      {metrics.isError && (
        <Card className="border-destructive/40 p-4 text-sm">
          Não foi possível carregar as métricas.{" "}
          <Button variant="link" className="h-auto p-0" onClick={() => metrics.refetch()}>
            Tentar de novo
          </Button>
        </Card>
      )}

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4 2xl:grid-cols-7">
        {totals ? (
          <>
            <KpiCard label="Leads" value={num(totals.leads)} hint={`${num(totals.leads_today)} nas últimas 24 h`} icon={Users} />
            <KpiCard label="Quentes" value={num(totals.hot)} hint="score ≥ 70" icon={Flame} tone="hot" />
            <KpiCard label="Qualificados" value={num(totals.qualified)} hint={`${percent(qualifiedRate)} do total`} icon={Sparkles} tone="gold" />
            <KpiCard label="Agendados" value={num(totals.scheduled)} hint={`${num(totals.handoff)} com corretor`} icon={CalendarCheck} tone="success" />
            <KpiCard
              label="Tempo de resposta"
              value={seconds(metrics.data?.response_time.avg_ms)}
              hint={`p90 ${seconds(metrics.data?.response_time.p90_ms)}`}
              icon={Gauge}
              tone="cold"
            />
            <KpiCard label="Follow-ups" value={num(totals.followups_sent)} hint="enviados automaticamente" icon={Send} />
            <KpiCard label="Reengajados" value={num(totals.reengaged)} hint="voltaram após follow-up" icon={RefreshCcw} tone="gold" />
          </>
        ) : (
          Array.from({ length: 7 }, (_, index) => <Skeleton key={index} className="h-[88px] rounded-xl" />)
        )}
      </div>

      {metrics.data ? (
        <div className="grid gap-4 lg:grid-cols-2 xl:grid-cols-3">
          <FunnelChart data={metrics.data.by_stage} />
          <TemperatureChart data={metrics.data.by_temperature} />
          <IntentChart data={metrics.data.by_intent} />
          <div className="lg:col-span-2">
            <LeadsPerDayChart data={metrics.data.leads_per_day} />
          </div>
          <Card>
            <CardHeader className="flex-row items-start justify-between">
              <div className="space-y-1">
                <CardTitle>Próximos compromissos</CardTitle>
                <CardDescription>Visitas e reuniões marcadas pela IA</CardDescription>
              </div>
              <Button variant="ghost" size="sm" asChild>
                <Link to="/painel/agenda">Ver agenda</Link>
              </Button>
            </CardHeader>
            <CardContent className="max-h-64 overflow-y-auto">
              <AppointmentList appointments={metrics.data.upcoming_appointments} />
            </CardContent>
          </Card>
        </div>
      ) : (
        <div className="grid gap-4 lg:grid-cols-3">
          {Array.from({ length: 3 }, (_, index) => (
            <Skeleton key={index} className="h-80 rounded-xl" />
          ))}
        </div>
      )}

      <Card>
        <CardHeader className="gap-4">
          <div className="space-y-1">
            <CardTitle>Leads</CardTitle>
            <CardDescription>Clique em um lead para ver conversa, resumo e histórico.</CardDescription>
          </div>
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
            <div className="relative">
              <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
              <Input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Buscar por nome" className="pl-9" />
            </div>
            <NativeSelect value={stage} onChange={(event) => setStage(event.target.value)} aria-label="Estágio">
              <option value="">Todos os estágios</option>
              {STAGE_ORDER.map((value) => (
                <option key={value} value={value}>
                  {STAGE_LABELS[value]}
                </option>
              ))}
            </NativeSelect>
            <NativeSelect value={temperature} onChange={(event) => setTemperature(event.target.value)} aria-label="Temperatura">
              <option value="">Todas as temperaturas</option>
              {Object.entries(TEMPERATURE_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </NativeSelect>
            <NativeSelect value={intent} onChange={(event) => setIntent(event.target.value)} aria-label="Intenção">
              <option value="">Todas as intenções</option>
              {Object.entries(INTENT_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </NativeSelect>
          </div>
        </CardHeader>
        <CardContent>
          {leads.data ? (
            <LeadsTable leads={leads.data.items} />
          ) : leads.isError ? (
            <p className="py-6 text-center text-sm text-destructive">Erro ao carregar leads.</p>
          ) : (
            <div className="space-y-2">
              {Array.from({ length: 5 }, (_, index) => (
                <Skeleton key={index} className="h-12" />
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </PageShell>
  );
}
