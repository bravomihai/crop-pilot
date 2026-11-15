"use client";

import { useEffect, useRef, useState } from "react";
import {
  requestSchema,
  type RecommendationRequest,
  type RecommendationResult,
} from "@croppilot/contracts";
import { getRecommendations } from "./api";

export function useRecommendations() {
  const [result, setResult] = useState<RecommendationResult>();
  const [lastRequest, setLastRequest] = useState<RecommendationRequest>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const controller = useRef<AbortController | null>(null);
  useEffect(() => () => controller.current?.abort(), []);
  function cancel() {
    controller.current?.abort();
    controller.current = null;
    setBusy(false);
  }
  function clear() {
    cancel();
    setResult(undefined);
    setLastRequest(undefined);
    setError("");
  }
  async function calculate(
    input: RecommendationRequest,
    preserve = false,
    debounceMs = 0,
  ) {
    cancel();
    const active = new AbortController();
    controller.current = active;
    setBusy(true);
    setError("");
    if (!preserve) {
      setResult(undefined);
      setLastRequest(undefined);
    }
    try {
      const parsed = requestSchema.safeParse(input);
      if (!parsed.success)
        throw new Error(
          "Check the location, dates, and form values before trying again.",
        );
      if (!Object.values(parsed.data.priorities).some((value) => value > 0))
        throw new Error("Choose at least one positive priority.");
      if (debounceMs)
        await new Promise<void>((resolve, reject) => {
          const done = () => {
            active.signal.removeEventListener("abort", abort);
            resolve();
          };
          const timer = setTimeout(done, debounceMs);
          const abort = () => {
            clearTimeout(timer);
            reject(new DOMException("Cancelled", "AbortError"));
          };
          active.signal.addEventListener("abort", abort, { once: true });
        });
      const output = await getRecommendations(parsed.data, active.signal);
      if (controller.current === active && !active.signal.aborted) {
        setResult(output);
        setLastRequest(parsed.data);
      }
    } catch (cause) {
      if (controller.current === active && !active.signal.aborted)
        setError(
          cause instanceof Error
            ? cause.message
            : "The calculation could not be completed.",
        );
    } finally {
      if (controller.current === active) setBusy(false);
    }
  }
  function recalculate(scenario: RecommendationRequest["scenario"]) {
    if (lastRequest) void calculate({ ...lastRequest, scenario }, true, 300);
  }
  /** Recalculates the last request with the farmer's own prices and costs (or without them). */
  function recalculateMoney(money_inputs: RecommendationRequest["money_inputs"]) {
    if (lastRequest) void calculate({ ...lastRequest, money_inputs }, true, 300);
  }
  return {
    result,
    lastRequest,
    busy,
    error,
    calculate,
    recalculate,
    recalculateMoney,
    clear,
    cancel,
    reportError: setError,
  };
}
