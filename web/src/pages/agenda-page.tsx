import { useQuery } from "@tanstack/react-query";
import { CalendarDays } from "lucide-react";

import { AppointmentRow } from "@/components/dashboard/appointment-list";
import { PageHeader, PageShell } from "@/components/layout";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { dashboardApi } from "@/lib/api";
import { dayKey, longDay } from "@/lib/format";
import type { Appointment } from "@/lib/types";

function groupByDay(appointments: Appointment[]) {
  const groups = new Map<string, Appointment[]>();
  for (const appointment of appointments) {
    const key = dayKey(appointment.starts_at);
    groups.set(key, [...(groups.get(key) ?? []), appointment]);
  }
  return [...groups.entries()].sort(([a], [b]) => a.localeCompare(b));
}

export default function AgendaPage() {
  const query = useQuery({ queryKey: ["appointments"], queryFn: () => dashboardApi.appointments(true), refetchInterval: 15_000 });
  const groups = query.data ? groupByDay(query.data.items) : [];

  return (
    <PageShell>
      <PageHeader
        title="Agenda"
        description="Visitas e reuniões agendadas automaticamente pela IA, por corretor e imóvel."
      />
      {!query.data && !query.isError && (
        <div className="space-y-4">
          <Skeleton className="h-40" />
          <Skeleton className="h-40" />
        </div>
      )}
      {query.isError && <p className="text-sm text-destructive">Erro ao carregar a agenda.</p>}
      {query.data && !groups.length && (
        <Card className="flex flex-col items-center gap-3 py-16 text-center">
          <CalendarDays className="size-8 text-gold" />
          <p className="font-medium">Nenhum compromisso por enquanto</p>
          <p className="max-w-sm text-sm text-muted-foreground">
            Quando um lead aceitar uma visita ou reunião no chat, o agendamento aparece aqui.
          </p>
        </Card>
      )}
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {groups.map(([day, items]) => (
          <Card key={day}>
            <CardHeader>
              <CardTitle className="flex items-center justify-between gap-2">
                <span>{longDay(items[0].starts_at)}</span>
                <span className="rounded-full bg-gold-soft px-2 py-0.5 text-xs font-medium text-accent-foreground">
                  {items.length}
                </span>
              </CardTitle>
            </CardHeader>
            <CardContent className="divide-y">
              {items.map((appointment) => (
                <AppointmentRow key={appointment.id} appointment={appointment} showDate={false} />
              ))}
            </CardContent>
          </Card>
        ))}
      </div>
    </PageShell>
  );
}
