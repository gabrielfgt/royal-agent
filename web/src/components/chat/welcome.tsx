import { Building2, Home, KeyRound, TrendingUp } from "lucide-react";

import { SofiaAvatar } from "@/components/chat/avatar";

const SUGGESTIONS = [
  { icon: Home, text: "Procuro casa em condomínio fechado em Tatuí." },
  { icon: TrendingUp, text: "Quero investir em imóveis para renda." },
  { icon: KeyRound, text: "Tem casa de 2 quartos até 300 mil? Vou financiar." },
  { icon: Building2, text: "Quais imóveis vocês têm no Centro?" },
];

export function Welcome({ onPick, disabled }: { onPick: (text: string) => void; disabled?: boolean }) {
  return (
    <div className="mx-auto flex max-w-md flex-col items-center gap-5 px-2 py-8 text-center">
      <SofiaAvatar className="size-14 text-lg" />
      <div className="space-y-1.5">
        <h2 className="text-lg font-semibold text-balance">Oi! Eu sou a Sofia, da Royal Imóveis.</h2>
        <p className="text-sm text-muted-foreground text-balance">
          Assistente virtual para compra, aluguel e investimento em Tatuí e região. Escreva ou mande um áudio — ou comece por
          um dos cenários abaixo.
        </p>
      </div>
      <div className="grid w-full gap-2">
        {SUGGESTIONS.map(({ icon: Icon, text }) => (
          <button
            key={text}
            type="button"
            disabled={disabled}
            onClick={() => onPick(text)}
            className="flex items-center gap-3 rounded-xl border bg-card px-3.5 py-2.5 text-left text-sm shadow-xs transition hover:border-gold hover:bg-gold-soft disabled:opacity-50"
          >
            <Icon className="size-4 shrink-0 text-gold" />
            {text}
          </button>
        ))}
      </div>
    </div>
  );
}
