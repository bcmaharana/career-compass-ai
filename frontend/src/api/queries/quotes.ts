import { apiClient } from "@/api/client";
import type { components } from "@/api/schema.gen";
import { useQuery } from "@tanstack/react-query";

type QuoteOfTheDayResponse = components["schemas"]["QuoteOfTheDayResponse"];

// The backend itself caches the day's quote (see
// ZenQuotesProvider.get_quote_of_the_day) and the value is identical for
// everyone all day — staleTime just avoids an extra round-trip per
// navigation on top of that, not a correctness requirement.
const TWELVE_HOURS_MS = 12 * 60 * 60 * 1000;

export function useQuoteOfTheDay() {
  return useQuery({
    queryKey: ["quote-of-the-day"],
    queryFn: () => apiClient.get<QuoteOfTheDayResponse>("/api/v1/quote-of-the-day"),
    staleTime: TWELVE_HOURS_MS,
  });
}
