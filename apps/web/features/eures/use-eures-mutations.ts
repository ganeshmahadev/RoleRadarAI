"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";

import { runEuresAction, updateEuresNotes, type EuresAction } from "@/lib/api/eures";

/** Every workflow change refreshes company lists, queue stats and the current company. */
export function useEuresMutations() {
  const client = useQueryClient();
  const invalidate = () =>
    Promise.all([
      client.invalidateQueries({ queryKey: ["companies"] }),
      client.invalidateQueries({ queryKey: ["eures"] }),
    ]);

  const action = useMutation({
    mutationFn: ({ companyId, action }: { companyId: string; action: EuresAction }) =>
      runEuresAction(companyId, action),
    onSettled: invalidate,
  });
  const notes = useMutation({
    mutationFn: ({ companyId, notes }: { companyId: string; notes: string }) =>
      updateEuresNotes(companyId, notes),
    onSettled: invalidate,
  });
  return { action, notes };
}
