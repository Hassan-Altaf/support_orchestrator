import { useMutation } from "@tanstack/react-query";
import { api, ApiError } from "@/api/client";
import type { ProcessRequest, TicketProcessingResult } from "@/api/types";

/** Mutation hook wrapping POST /api/v1/support/process. */
export function useProcessSupport() {
  return useMutation<TicketProcessingResult, ApiError, ProcessRequest>({
    mutationFn: api.processSupport,
  });
}
