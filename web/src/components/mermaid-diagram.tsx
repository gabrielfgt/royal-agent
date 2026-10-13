import { useEffect, useId, useRef, useState } from "react";

import { Skeleton } from "@/components/ui/skeleton";

function cssColorToHex(variable: string) {
  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = 1;
  const context = canvas.getContext("2d");
  const value = getComputedStyle(document.documentElement).getPropertyValue(variable).trim();
  if (!context || !value) return undefined;
  context.fillStyle = value;
  context.fillRect(0, 0, 1, 1);
  const [red, green, blue] = context.getImageData(0, 0, 1, 1).data;
  return `#${[red, green, blue].map((channel) => channel.toString(16).padStart(2, "0")).join("")}`;
}

export function MermaidDiagram({ definition }: { definition: string }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [ready, setReady] = useState(false);
  const id = `mermaid-${useId().replace(/[^a-zA-Z0-9]/g, "")}`;

  useEffect(() => {
    let cancelled = false;
    setReady(false);
    setError(null);
    (async () => {
      try {
        const { default: mermaid } = await import("mermaid");
        const token = cssColorToHex;
        mermaid.initialize({
          startOnLoad: false,
          securityLevel: "strict",
          theme: "base",
          fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif",
          themeVariables: {
            primaryColor: token("--gold-soft"),
            primaryBorderColor: token("--gold"),
            primaryTextColor: token("--foreground"),
            lineColor: token("--muted-foreground"),
            secondaryColor: token("--secondary"),
            tertiaryColor: token("--card"),
          },
        });
        const { svg } = await mermaid.render(id, definition);
        if (!cancelled && containerRef.current) {
          containerRef.current.innerHTML = svg;
          setReady(true);
        }
      } catch (caught) {
        if (!cancelled) setError(caught instanceof Error ? caught.message : "Falha ao renderizar o diagrama");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [definition, id]);

  return (
    <div className="scrollbar-thin overflow-x-auto">
      {!ready && !error && <Skeleton className="h-96 w-full" />}
      {error && (
        <div className="space-y-2">
          <p className="text-xs text-destructive">Não foi possível desenhar o diagrama ({error}).</p>
          <pre className="overflow-x-auto rounded-lg bg-muted p-3 text-xs">{definition}</pre>
        </div>
      )}
      <div ref={containerRef} className="flex min-w-[520px] justify-center [&_svg]:h-auto [&_svg]:max-w-full" />
    </div>
  );
}
