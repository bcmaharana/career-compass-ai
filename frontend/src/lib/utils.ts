import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

/**
 * Merges Tailwind class names, resolving conflicts (e.g. `p-2 p-4` -> `p-4`)
 * the way the last one wins. Standard shadcn/ui convention — used by every
 * component in src/components/ui so conditional/override classes compose
 * predictably instead of both applying and fighting each other in the
 * cascade.
 */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
