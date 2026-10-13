import * as DialogPrimitive from "@radix-ui/react-dialog";
import { Building2, CalendarDays, LayoutDashboard, LogOut, Menu, MessageCircle, Workflow } from "lucide-react";
import { useState } from "react";
import { Link, NavLink, Outlet } from "react-router";

import { Brand } from "@/components/brand";
import { Button } from "@/components/ui/button";
import { Dialog, DialogDescription, DialogTitle, SheetContent } from "@/components/ui/dialog";
import { useAuth } from "@/hooks/use-auth";
import { cn } from "@/lib/utils";

const LINKS = [
  { to: "/", label: "Chat", icon: MessageCircle, end: true },
  { to: "/painel", label: "Painel", icon: LayoutDashboard, end: true },
  { to: "/painel/agenda", label: "Agenda", icon: CalendarDays, end: false },
  { to: "/painel/imoveis", label: "Imóveis", icon: Building2, end: false },
  { to: "/como-funciona", label: "Como funciona", icon: Workflow, end: false },
];

function NavItems({ onNavigate, vertical = false }: { onNavigate?: () => void; vertical?: boolean }) {
  return (
    <>
      {LINKS.map(({ to, label, icon: Icon, end }) => (
        <NavLink
          key={to}
          to={to}
          end={end}
          onClick={onNavigate}
          className={({ isActive }) =>
            cn(
              "flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground",
              isActive && "bg-gold-soft text-accent-foreground",
              vertical && "text-base",
            )
          }
        >
          <Icon className="size-4" />
          {label}
        </NavLink>
      ))}
    </>
  );
}

export function Layout() {
  const { token, logout } = useAuth();
  const [open, setOpen] = useState(false);
  return (
    <div className="min-h-dvh">
      <header className="sticky top-0 z-40 h-14 border-b bg-background/85 backdrop-blur supports-[backdrop-filter]:bg-background/70">
        <div className="mx-auto flex h-full max-w-7xl items-center gap-4 px-4">
          <Link to="/" className="shrink-0">
            <Brand />
          </Link>
          <nav className="hidden flex-1 items-center gap-1 md:flex">
            <NavItems />
          </nav>
          <div className="ml-auto flex items-center gap-2">
            {token && (
              <Button variant="ghost" size="sm" onClick={logout} className="hidden md:inline-flex">
                <LogOut /> Sair do painel
              </Button>
            )}
            <Button variant="ghost" size="icon" className="md:hidden" onClick={() => setOpen(true)} aria-label="Abrir menu">
              <Menu />
            </Button>
          </div>
        </div>
      </header>
      <main>
        <Outlet />
      </main>
      <Dialog open={open} onOpenChange={setOpen}>
        <SheetContent side="left">
          <DialogTitle asChild>
            <div>
              <Brand />
            </div>
          </DialogTitle>
          <DialogDescription className="sr-only">Navegação</DialogDescription>
          <nav className="flex flex-col gap-1">
            <NavItems vertical onNavigate={() => setOpen(false)} />
          </nav>
          {token && (
            <DialogPrimitive.Close asChild>
              <Button variant="outline" onClick={logout} className="mt-auto">
                <LogOut /> Sair do painel
              </Button>
            </DialogPrimitive.Close>
          )}
        </SheetContent>
      </Dialog>
    </div>
  );
}

export function PageShell({ children, className }: { children: React.ReactNode; className?: string }) {
  return <div className={cn("mx-auto w-full max-w-7xl space-y-6 px-4 py-6 sm:py-8", className)}>{children}</div>;
}

export function PageHeader({
  title,
  description,
  actions,
}: {
  title: string;
  description?: string;
  actions?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        {description && <p className="text-sm text-muted-foreground">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}
