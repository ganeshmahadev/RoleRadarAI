import { DashboardView } from "@/features/dashboard/dashboard-view";
import { ApiStatus } from "@/features/health/api-status";

export default function DashboardPage() {
  return (
    <section className="space-y-4">
      <header className="flex flex-wrap items-baseline justify-between gap-2">
        <h1 className="text-xl font-semibold tracking-tight">Dashboard</h1>
        <ApiStatus />
      </header>
      <DashboardView />
    </section>
  );
}
