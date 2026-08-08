import { AsYouType, isSupportedCountry, parsePhoneNumberFromString } from "libphonenumber-js";
import type { CountryCode } from "libphonenumber-js";

/** Live-formats a phone number as the user types, national-format rules
 * for the given country (e.g. a GB number needs its leading trunk "0").
 * Originally local to SettingsProfilePage.tsx; shared here so
 * PhoneLoginForm.tsx formats its input the same way. */
export function formatPhoneForCountry(value: string, country: string): string {
  if (!value.trim()) return value;
  const defaultCountry = isSupportedCountry(country) ? (country as CountryCode) : undefined;
  return new AsYouType(defaultCountry).input(value);
}

/** Parses a (possibly nationally-formatted) phone number into E.164
 * (e.g. "+14155552671") for the given country, or null if it doesn't
 * parse into a valid number for that country. Firebase's
 * signInWithPhoneNumber requires E.164 — this is the one place that
 * conversion happens for phone login. */
export function toE164(value: string, country: string): string | null {
  if (!value.trim()) return null;
  const defaultCountry = isSupportedCountry(country) ? (country as CountryCode) : undefined;
  const parsed = parsePhoneNumberFromString(value, defaultCountry);
  return parsed && parsed.isValid() ? parsed.number : null;
}
