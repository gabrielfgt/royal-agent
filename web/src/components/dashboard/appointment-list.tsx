import { CalendarClock, Home, Video } from "lucide-react";
import { Link } from "react-router";

import { TemperatureBadge } from "@/components/lead/badges";
import { APPOINTMENT_LABELS, dateTime, time } from "@/lib/format";
import type { Appointment } from "@/lib/types";

export function AppointmentRow({ appointment, showDate = true }: { appointment: Appointment; showDate?: boolean }) {
  const Icon = appointment.kind === "visita" ? Home : Video;
  return (
    <Link
      to={`/painel/leads/${appointment.lead_id}`}
      className="flex items-start gap-3 rounded-lg p-2.5 transition-colors hover:bg-accent"
    >
      <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-gold-soft text-accent-foreground">
        <Icon className="size-4" />
      </span>
      <div className="min-w-0 flex-1 space-y-0.5">
        <p className="flex flex-wrap items-center gap-x-2 text-sm font-medium">
          <span className="tabular-nums">{showDate ? dateTime(appointment.starts_at) : time(appointment.starts_at)}</span>
          <span className="text-muted-foreground">·</span>
          <span className="truncate">{appointment.lead_name ?? "Lead"}</span>
          {appointment.lead_temperature && <TemperatureBadge temperature={appointment.lead_temperature} />}
        </p>
        <p className="truncate text-xs text-muted-foreground">
          {APPOINTMENT_LABELS[appointment.kind]} com {appointment.broker_name}
          {appointment.property_code &&
            ` · ${appointment.property_code}${appointment.property_neighborhood ? ` (${appointment.property_neighborhood})` : ""}`}
        </p>
      </div>
    </Link>
  );
}

export function AppointmentList({ appointments }: { appointments: Appointment[] }) {
  if (!appointments.length) {
    return (
      <div className="flex flex-col items-center gap-2 py-8 text-center text-sm text-muted-foreground">
        <CalendarClock className="size-6" />
        Nenhum compromisso agendado ainda.
      </div>
    );
  }
  return (
    <div className="divide-y">
      {appointments.map((appointment) => (
        <AppointmentRow key={appointment.id} appointment={appointment} />
      ))}
    </div>
  );
}
