"use client";

import { useEffect, useRef, useState } from "react";
import type { RecommendationRequest, RecommendationResult } from "@fieldshift/contracts";
import { getRecommendations } from "./api";

type PartResult = {
  request: RecommendationRequest;
  result?: RecommendationResult;
  error?: string;
  state: "waiting" | "loading" | "done" | "error";
};

export function usePartRecommendations() {
  const [parts, setParts] = useState<PartResult[]>([]);
  const [busy, setBusy] = useState(false);
  const controller = useRef<AbortController | null>(null);
  useEffect(() => () => controller.current?.abort(), []);

  function cancel() {
    controller.current?.abort();
    controller.current = null;
    setBusy(false);
    setParts((current) => current.map((part) =>
      part.state === "waiting" || part.state === "loading"
        ? { ...part, state: "error", error: "Calculation cancelled." }
        : part,
    ));
  }
  function clear() {
    cancel();
    setParts([]);
  }
  async function calculate(requests: RecommendationRequest[]) {
    cancel();
    const active = new AbortController();
    controller.current = active;
    setParts(requests.map((request) => ({ request, state: "waiting" })));
    setBusy(true);
    for (let index = 0; index < requests.length; index += 1) {
      if (active.signal.aborted) break;
      setParts((current) => current.map((part, i) =>
        i === index ? { ...part, state: "loading" } : part,
      ));
      try {
        const result = await getRecommendations(requests[index], active.signal);
        if (controller.current !== active || active.signal.aborted) break;
        setParts((current) => current.map((part, i) =>
          i === index ? { ...part, result, state: "done" } : part,
        ));
      } catch (cause) {
        if (controller.current !== active || active.signal.aborted) break;
        setParts((current) => current.map((part, i) =>
          i === index
            ? {
                ...part,
                state: "error",
                error: cause instanceof Error ? cause.message : "The calculation failed.",
              }
            : part,
        ));
      }
    }
    if (controller.current === active) {
      controller.current = null;
      setBusy(false);
    }
  }
  return { parts, busy, calculate, cancel, clear };
}
