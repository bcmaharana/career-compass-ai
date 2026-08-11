import { create } from "zustand";

/** Which of the mobile header's two hamburger dropdowns (see AppHeader.tsx
 * — MobileNavMenu on the left, MobileAccountMenu on the right) is
 * currently open, if either. */
export type MobileDropdownId = "nav" | "account";

/**
 * A single shared "which mobile dropdown is open" slot, rather than each
 * of MobileNavMenu.tsx/MobileAccountMenu.tsx owning its own independent
 * `useState` — with two independent booleans, opening one had no way to
 * know it should close the other, so tapping the left hamburger while the
 * right one was already open left both open and stacked on screen at
 * once. Modeling it as a single nullable slot instead makes "only one
 * open at a time" true by construction: calling `open()` for either one
 * implicitly closes the other, since there's only one value to hold.
 *
 * Also read by SettingsLandingPage.tsx, which hides its own content while
 * the account dropdown is open — that page and the dropdown are both
 * overlays on the same content, and the dropdown's opaque panel covers
 * most of a narrow viewport's width.
 */
interface MobileDropdownState {
  active: MobileDropdownId | null;
  open: (id: MobileDropdownId) => void;
  close: () => void;
}

export const useMobileDropdownStore = create<MobileDropdownState>((set) => ({
  active: null,
  open: (id) => set({ active: id }),
  close: () => set({ active: null }),
}));
