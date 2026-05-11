import { useQuery } from "@tanstack/react-query";
import { api } from "@/api/client";

/** Polls the health endpoint so the UI can show a live "reachable" indicator. */
export function useHealth() {
  return useQuery({
    queryKey: ["health"],
    queryFn: api.health,
    refetchInterval: 30_000,
    refetchOnWindowFocus: true,
    retry: 1,
  });
}
