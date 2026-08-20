/**
 * Prefixes a bare domain/path with "https://" if it doesn't already carry
 * a scheme — lets a user type "linkedin.com/in/name" instead of being
 * forced through "https://linkedin.com/in/name" (the fields that accept
 * these are plain `type="text"` inputs with no format validation, so a
 * bare domain is valid input; this is what makes it usable as a real
 * `href` when rendered as a clickable link).
 */
export function withHttps(url: string): string {
  const trimmed = url.trim();
  return /^[a-z][a-z0-9+.-]*:\/\//i.test(trimmed) ? trimmed : `https://${trimmed}`;
}
