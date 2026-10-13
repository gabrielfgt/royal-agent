import { useQuery } from "@tanstack/react-query";
import { BedDouble, Car, Images, MapPin, Maximize, TrendingUp } from "lucide-react";
import { useState } from "react";

import { PageHeader, PageShell } from "@/components/layout";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { NativeSelect } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { dashboardApi } from "@/lib/api";
import { brl, brlShort, percent, PROPERTY_KIND_LABELS } from "@/lib/format";
import type { Property, PropertyKind } from "@/lib/types";

function PropertyCard({ property }: { property: Property }) {
  const grossYield =
    property.purpose === "venda" && property.estimated_rent ? (property.estimated_rent * 12) / property.price : null;
  return (
    <Card className="flex flex-col gap-3 overflow-hidden p-0">
      {property.photos[0] && (
        <div className="relative aspect-[4/3] bg-muted">
          <img
            src={property.photos[0]}
            alt={property.title}
            loading="lazy"
            className="size-full object-cover"
            referrerPolicy="no-referrer"
          />
          <span className="absolute right-2 bottom-2 flex items-center gap-1 rounded-full bg-black/60 px-2 py-0.5 text-xs text-white">
            <Images className="size-3.5" /> {property.photos.length}
          </span>
        </div>
      )}
      <div className="flex flex-1 flex-col gap-3 px-4 pb-4">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-xs font-semibold tracking-wide text-gold uppercase">Ref. {property.code}</p>
          <h3 className="line-clamp-2 leading-snug font-semibold">{property.title}</h3>
          <p className="flex items-center gap-1 text-xs text-muted-foreground">
            <MapPin className="size-3.5 shrink-0" />
            {[property.neighborhood, property.condominium, property.city].filter(Boolean).join(" · ")}
          </p>
        </div>
        <Badge variant={property.purpose === "venda" ? "default" : "gold"}>
          {property.purpose === "venda" ? "Venda" : "Aluguel"}
        </Badge>
      </div>
      <div>
        <p className="text-xl font-semibold tabular-nums">
          {property.purpose === "venda" ? brlShort(property.price) : `${brl(property.price)}/mês`}
        </p>
        <p className="text-xs text-muted-foreground">
          {property.condo_fee ? `Condomínio ${brl(property.condo_fee)} · ` : ""}IPTU ~{brl(property.iptu_monthly)}/mês
        </p>
      </div>
      <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-muted-foreground">
        {property.bedrooms > 0 && (
          <span className="flex items-center gap-1">
            <BedDouble className="size-4" /> {property.bedrooms} dorm.
          </span>
        )}
        {property.area_m2 > 0 && (
          <span className="flex items-center gap-1">
            <Maximize className="size-4" /> {property.area_m2} m²
          </span>
        )}
        {property.parking > 0 && (
          <span className="flex items-center gap-1">
            <Car className="size-4" /> {property.parking}
          </span>
        )}
      </div>
      {grossYield && (
        <p className="flex items-center gap-1.5 rounded-lg bg-success-soft px-2.5 py-1.5 text-xs font-medium text-success">
          <TrendingUp className="size-3.5" /> Aluguel estimado {brl(property.estimated_rent)} · yield bruto{" "}
          {percent(grossYield)} a.a.
        </p>
      )}
      <div className="mt-auto flex flex-wrap gap-1.5">
        <Badge variant="muted">{PROPERTY_KIND_LABELS[property.kind] ?? property.kind}</Badge>
        {property.features.slice(0, 4).map((feature) => (
          <Badge key={feature} variant="outline">
            {feature}
          </Badge>
        ))}
      </div>
      </div>
    </Card>
  );
}

export default function PropertiesPage() {
  const [purpose, setPurpose] = useState("");
  const [kind, setKind] = useState("");
  const query = useQuery({
    queryKey: ["properties", purpose, kind],
    queryFn: () => dashboardApi.properties({ purpose, kind }),
  });

  return (
    <PageShell>
      <PageHeader
        title="Imóveis"
        description="Portfólio real importado do site da imobiliária parceira, usado pelo RAG do agente (filtros + busca semântica com pgvector)."
        actions={
          <>
            <NativeSelect value={purpose} onChange={(event) => setPurpose(event.target.value)} aria-label="Finalidade" className="w-40">
              <option value="">Venda e aluguel</option>
              <option value="venda">Venda</option>
              <option value="aluguel">Aluguel</option>
            </NativeSelect>
            <NativeSelect value={kind} onChange={(event) => setKind(event.target.value)} aria-label="Tipo" className="w-48">
              <option value="">Todos os tipos</option>
              {(Object.keys(PROPERTY_KIND_LABELS) as PropertyKind[]).map((value) => (
                <option key={value} value={value}>
                  {PROPERTY_KIND_LABELS[value]}
                </option>
              ))}
            </NativeSelect>
          </>
        }
      />
      {query.data && <p className="text-sm text-muted-foreground">{query.data.items.length} imóveis</p>}
      {query.isError && <p className="text-sm text-destructive">Erro ao carregar imóveis.</p>}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {query.data
          ? query.data.items.map((property) => <PropertyCard key={property.code} property={property} />)
          : !query.isError && Array.from({ length: 8 }, (_, index) => <Skeleton key={index} className="h-72 rounded-xl" />)}
      </div>
    </PageShell>
  );
}
