// S8b.4b: dark for everyone by default; light only when the visitor chooses it.
// Storage can be missing or throw (private window, blocked site data): that means dark.
export const KEY = "gg-theme";

export function readTheme(storage) {
  try {
    return storage?.getItem(KEY) === "light" ? "light" : "dark";
  } catch {
    return "dark";
  }
}

export function saveTheme(storage, theme) {
  try {
    storage?.setItem(KEY, theme);
  } catch {
    /* not saved: the switch still works for this page */
  }
}

export const nextTheme = (t) => (t === "light" ? "dark" : "light");
export const label = (t) => (t === "light" ? "Switch to dark mode" : "Switch to light mode");
