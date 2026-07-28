import { getCountries } from "libphonenumber-js";

export interface LocaleOption {
  code: string;
  label: string;
}

// A curated set rather than the full BCP-47 registry — Intl.DisplayNames
// can name any tag, but the dropdown should stay a manageable, common-cases
// list rather than hundreds of regional variants.
const LANGUAGE_CODES = [
  "en",
  "es",
  "fr",
  "de",
  "it",
  "pt",
  "nl",
  "sv",
  "da",
  "no",
  "fi",
  "pl",
  "cs",
  "el",
  "tr",
  "ru",
  "uk",
  "ar",
  "he",
  "hi",
  "bn",
  "ur",
  "th",
  "vi",
  "id",
  "ms",
  "zh",
  "ja",
  "ko",
] as const;

export function getCountryOptions(): LocaleOption[] {
  const displayNames = new Intl.DisplayNames(["en"], { type: "region" });
  return getCountries()
    .map((code) => ({ code, label: displayNames.of(code) ?? code }))
    .sort((a, b) => a.label.localeCompare(b.label));
}

export function getLanguageOptions(): LocaleOption[] {
  const displayNames = new Intl.DisplayNames(["en"], { type: "language" });
  return LANGUAGE_CODES.map((code) => ({ code, label: displayNames.of(code) ?? code })).sort(
    (a, b) => a.label.localeCompare(b.label),
  );
}
