import { lazy, Suspense } from "react";
import { Link, Route, Routes } from "react-router";

import { Layout, PageShell } from "@/components/layout";
import { RequireAuth } from "@/components/require-auth";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ChatPage } from "@/pages/chat-page";

const DashboardPage = lazy(() => import("@/pages/dashboard-page"));
const LeadDetailPage = lazy(() => import("@/pages/lead-detail-page"));
const AgendaPage = lazy(() => import("@/pages/agenda-page"));
const PropertiesPage = lazy(() => import("@/pages/properties-page"));
const HowItWorksPage = lazy(() => import("@/pages/how-it-works-page"));

function PageFallback() {
  return (
    <PageShell>
      <Skeleton className="h-8 w-56" />
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }, (_, index) => (
          <Skeleton key={index} className="h-28" />
        ))}
      </div>
      <Skeleton className="h-72" />
    </PageShell>
  );
}

function NotFound() {
  return (
    <PageShell className="flex flex-col items-center gap-4 py-20 text-center">
      <h1 className="text-2xl font-semibold">Página não encontrada</h1>
      <Button asChild>
        <Link to="/">Voltar ao chat</Link>
      </Button>
    </PageShell>
  );
}

function protectedPage(element: React.ReactNode) {
  return (
    <RequireAuth>
      <Suspense fallback={<PageFallback />}>{element}</Suspense>
    </RequireAuth>
  );
}

export function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<ChatPage />} />
        <Route path="painel" element={protectedPage(<DashboardPage />)} />
        <Route path="painel/leads/:id" element={protectedPage(<LeadDetailPage />)} />
        <Route path="painel/agenda" element={protectedPage(<AgendaPage />)} />
        <Route path="painel/imoveis" element={protectedPage(<PropertiesPage />)} />
        <Route
          path="como-funciona"
          element={
            <Suspense fallback={<PageFallback />}>
              <HowItWorksPage />
            </Suspense>
          }
        />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
