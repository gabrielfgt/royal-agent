import { KeyRound, LoaderCircle } from "lucide-react";
import { type FormEvent, type ReactNode, useState } from "react";

import { BrandMark } from "@/components/brand";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/hooks/use-auth";
import { ApiError } from "@/lib/api";

export function LoginCard({ title = "Painel comercial" }: { title?: string }) {
  const { login } = useAuth();
  const [value, setValue] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!value.trim()) return;
    setPending(true);
    setError(null);
    try {
      await login(value);
    } catch (caught) {
      setError(caught instanceof ApiError && caught.status === 401 ? "Token inválido." : "Não consegui falar com a API.");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="flex min-h-[calc(100dvh-3.5rem)] items-center justify-center p-4">
      <Card className="w-full max-w-sm">
        <CardHeader className="items-center text-center">
          <BrandMark className="mb-2 size-12" />
          <CardTitle className="text-lg">{title}</CardTitle>
          <CardDescription>Área dos corretores. Informe o token de acesso do painel.</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={submit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="token">Token de acesso</Label>
              <Input
                id="token"
                type="password"
                autoComplete="current-password"
                value={value}
                onChange={(event) => setValue(event.target.value)}
                placeholder={import.meta.env.DEV ? "ex.: royal-demo" : "Token do painel"}
                autoFocus
              />
              {error && <p className="text-sm text-destructive">{error}</p>}
              <p className="text-xs text-muted-foreground">
                {import.meta.env.DEV ? (
                  <>
                    Na demo local o token padrão é <code className="rounded bg-muted px-1">royal-demo</code> (variável
                    DASHBOARD_TOKEN).
                  </>
                ) : (
                  "Use o token configurado em DASHBOARD_TOKEN no ambiente publicado."
                )}
              </p>
            </div>
            <Button type="submit" className="w-full" disabled={pending}>
              {pending ? <LoaderCircle className="animate-spin" /> : <KeyRound />}
              Entrar
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}

export function RequireAuth({ children }: { children: ReactNode }) {
  const { token } = useAuth();
  return token ? <>{children}</> : <LoginCard />;
}
