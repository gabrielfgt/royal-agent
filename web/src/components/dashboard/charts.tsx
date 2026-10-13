import { Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { INTENT_LABELS, shortDate, STAGE_LABELS, STAGE_ORDER, TEMPERATURE_LABELS } from "@/lib/format";
import type { Breakdown, Intent, Stage, Temperature } from "@/lib/types";

const tooltipStyle = {
  contentStyle: {
    borderRadius: 10,
    border: "1px solid var(--border)",
    background: "var(--card)",
    fontSize: 12,
    boxShadow: "0 4px 16px color-mix(in oklch, var(--primary) 10%, transparent)",
  },
  cursor: { fill: "color-mix(in oklch, var(--gold) 12%, transparent)" },
};

const STAGE_COLORS: Record<Stage, string> = {
  novo: "var(--chart-7)",
  em_qualificacao: "var(--chart-3)",
  qualificado: "var(--chart-4)",
  agendado: "var(--chart-5)",
  handoff: "var(--chart-1)",
  perdido: "var(--chart-7)",
  opt_out: "var(--chart-6)",
};

const TEMPERATURE_COLORS: Record<Temperature, string> = { quente: "var(--hot)", morno: "var(--warm)", frio: "var(--cold)" };

function lookup(data: Breakdown[], key: string) {
  return data.find((item) => item.key === key)?.count ?? 0;
}

function ChartCard({ title, description, children }: { title: string; description?: string; children: React.ReactNode }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        {description && <CardDescription>{description}</CardDescription>}
      </CardHeader>
      <CardContent className="h-64">{children}</CardContent>
    </Card>
  );
}

function Empty() {
  return <div className="flex h-full items-center justify-center text-sm text-muted-foreground">Sem dados ainda</div>;
}

export function FunnelChart({ data }: { data: Breakdown[] }) {
  const rows = STAGE_ORDER.map((stage) => ({ stage, label: STAGE_LABELS[stage], count: lookup(data, stage) }));
  const hasData = rows.some((row) => row.count > 0);
  return (
    <ChartCard title="Funil de leads" description="Quantidade de leads em cada estágio">
      {hasData ? (
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={rows} layout="vertical" margin={{ left: 8, right: 16 }}>
            <CartesianGrid horizontal={false} stroke="var(--border)" />
            <XAxis type="number" allowDecimals={false} tick={{ fontSize: 11, fill: "var(--muted-foreground)" }} axisLine={false} tickLine={false} />
            <YAxis type="category" dataKey="label" width={118} tick={{ fontSize: 12, fill: "var(--foreground)" }} axisLine={false} tickLine={false} />
            <Tooltip {...tooltipStyle} formatter={(value) => [value, "Leads"]} />
            <Bar dataKey="count" radius={[0, 6, 6, 0]} barSize={18}>
              {rows.map((row) => (
                <Cell key={row.stage} fill={STAGE_COLORS[row.stage]} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      ) : (
        <Empty />
      )}
    </ChartCard>
  );
}

export function TemperatureChart({ data }: { data: Breakdown[] }) {
  const rows = (["quente", "morno", "frio"] as Temperature[])
    .map((temperature) => ({ temperature, label: TEMPERATURE_LABELS[temperature], count: lookup(data, temperature) }))
    .filter((row) => row.count > 0);
  const total = rows.reduce((sum, row) => sum + row.count, 0);
  return (
    <ChartCard title="Temperatura" description="Score calculado a partir do perfil e engajamento">
      {total ? (
        <div className="relative h-full">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie data={rows} dataKey="count" nameKey="label" innerRadius="58%" outerRadius="85%" paddingAngle={3} strokeWidth={0}>
                {rows.map((row) => (
                  <Cell key={row.temperature} fill={TEMPERATURE_COLORS[row.temperature]} />
                ))}
              </Pie>
              <Tooltip {...tooltipStyle} />
            </PieChart>
          </ResponsiveContainer>
          <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
            <span className="text-2xl font-semibold tabular-nums">{total}</span>
            <span className="text-xs text-muted-foreground">leads</span>
          </div>
          <div className="absolute right-0 bottom-0 left-0 flex justify-center gap-3 text-xs">
            {rows.map((row) => (
              <span key={row.temperature} className="flex items-center gap-1">
                <span className="size-2.5 rounded-full" style={{ background: TEMPERATURE_COLORS[row.temperature] }} />
                {row.label} {row.count}
              </span>
            ))}
          </div>
        </div>
      ) : (
        <Empty />
      )}
    </ChartCard>
  );
}

export function IntentChart({ data }: { data: Breakdown[] }) {
  const rows = (["compra", "aluguel", "investimento", "indefinido"] as Intent[]).map((intent) => ({
    label: INTENT_LABELS[intent],
    count: lookup(data, intent),
  }));
  const hasData = rows.some((row) => row.count > 0);
  return (
    <ChartCard title="Intenção" description="Compra, aluguel ou investimento">
      {hasData ? (
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={rows} margin={{ top: 8 }}>
            <CartesianGrid vertical={false} stroke="var(--border)" />
            <XAxis dataKey="label" tick={{ fontSize: 12, fill: "var(--foreground)" }} axisLine={false} tickLine={false} />
            <YAxis allowDecimals={false} width={28} tick={{ fontSize: 11, fill: "var(--muted-foreground)" }} axisLine={false} tickLine={false} />
            <Tooltip {...tooltipStyle} formatter={(value) => [value, "Leads"]} />
            <Bar dataKey="count" fill="var(--chart-1)" radius={[6, 6, 0, 0]} barSize={36} />
          </BarChart>
        </ResponsiveContainer>
      ) : (
        <Empty />
      )}
    </ChartCard>
  );
}

export function LeadsPerDayChart({ data }: { data: { date: string; count: number }[] }) {
  const rows = data.map((row) => ({ ...row, label: shortDate(row.date) }));
  return (
    <ChartCard title="Novos leads por dia" description="Últimos 14 dias">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={rows} margin={{ top: 8, right: 8 }}>
          <defs>
            <linearGradient id="leadsGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--gold)" stopOpacity={0.45} />
              <stop offset="100%" stopColor="var(--gold)" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid vertical={false} stroke="var(--border)" />
          <XAxis dataKey="label" tick={{ fontSize: 11, fill: "var(--muted-foreground)" }} axisLine={false} tickLine={false} interval="preserveStartEnd" />
          <YAxis allowDecimals={false} width={28} tick={{ fontSize: 11, fill: "var(--muted-foreground)" }} axisLine={false} tickLine={false} />
          <Tooltip {...tooltipStyle} formatter={(value) => [value, "Leads"]} />
          <Area type="monotone" dataKey="count" stroke="var(--gold)" strokeWidth={2.5} fill="url(#leadsGradient)" />
        </AreaChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}
