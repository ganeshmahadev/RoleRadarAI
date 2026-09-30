import { ApiStatus } from "@/features/health/api-status";

export default function DashboardPage() {
  return (
    <section className="space-y-4">
      <h1 className="text-xl font-semibold tracking-tight">Dashboard</h1>
      <ApiStatus />
    </section>
  );
}
