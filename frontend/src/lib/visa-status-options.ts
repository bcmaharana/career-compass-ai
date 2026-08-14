export interface VisaStatusOption {
  value: string;
  label: string;
}

/**
 * Standard US work-authorization values (per explicit user choice over a
 * fully free-text field) — stored on the backend as plain text
 * (User.visa_status), the same "frontend dropdown constrains the value,
 * backend just stores the string" convention already used for
 * country/language (see lib/locale-options.ts). Not sourced from
 * Intl.DisplayNames — there's no built-in registry for this, so it's a
 * plain curated list.
 */
export const VISA_STATUS_OPTIONS: VisaStatusOption[] = [
  { value: "U.S. Citizen", label: "U.S. Citizen" },
  { value: "Green Card/Permanent Resident", label: "Green Card / Permanent Resident" },
  { value: "H-1B", label: "H-1B" },
  { value: "L-1", label: "L-1" },
  { value: "TN", label: "TN" },
  { value: "F-1 (OPT/CPT)", label: "F-1 (OPT/CPT)" },
  { value: "O-1", label: "O-1" },
  { value: "Not Authorized to Work in the U.S.", label: "Not Authorized to Work in the U.S." },
  { value: "Other", label: "Other" },
];
