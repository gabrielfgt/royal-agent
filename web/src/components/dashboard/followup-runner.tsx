import { useMutation, useQueryClient } from "@tanstack/react-query";
import { LoaderCircle, Timer } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { dashboardApi } from "@/lib/api";

export function FollowupRunner() {
  const [force, setForce] = useState(true);
  const queryClient = useQueryClient();
  const mutation = useMutation({
    mutationFn: () => dashboardApi.runFollowups(force),
    onSuccess: (result) => {
      const sent = result.sent.length;
      const lost = result.lost.length;
      if (!sent && !lost) toast.info("Nenhum lead elegível para follow-up agora.");
      else
        toast.success(
          `${sent} follow-up${sent === 1 ? "" : "s"} enviado${sent === 1 ? "" : "s"}` +
            (lost ? ` · ${lost} lead${lost === 1 ? "" : "s"} marcado${lost === 1 ? "" : "s"} como perdido` : ""),
        );
      void queryClient.invalidateQueries();
    },
    onError: (error) => toast.error(error.message),
  });

  return (
    <div className="flex flex-wrap items-center gap-3 rounded-xl border bg-card px-3 py-2 shadow-xs">
      <div className="flex items-center gap-2">
        <Checkbox id="force-followup" checked={force} onCheckedChange={(value) => setForce(value === true)} />
        <Label htmlFor="force-followup" className="text-xs font-normal text-muted-foreground">
          forçar (ignorar intervalo — demo)
        </Label>
      </div>
      <Button size="sm" variant="gold" onClick={() => mutation.mutate()} disabled={mutation.isPending}>
        {mutation.isPending ? <LoaderCircle className="animate-spin" /> : <Timer />}
        Rodar follow-ups
      </Button>
    </div>
  );
}
