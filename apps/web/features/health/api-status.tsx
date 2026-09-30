"use client";

import { useQuery } from "@tanstack/react-query";

import { getHealth } from "@/lib/api/health";

export function ApiStatus() {
  const { data, isPending, isError, error } = useQuery({
    queryKey: ["health"],
    queryFn: getHealth,
  });

  let label = "Checking API…";
  let tone = "text-muted";
  if (isError) {
    label = `API unavailable: ${error.message}`;
    tone = "text-danger";
  } else if (!isPending) {
    label = data.status === "ok" ? "API connected" : `API status: ${data.status}`;
    tone = data.status === "ok" ? "text-success" : "text-warning";
  }

  return (
    <p role="status" className={`text-sm ${tone}`}>
      {label}
    </p>
  );
}
