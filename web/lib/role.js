// "View as" (S7.15): one control, three choices -- a stand-in for logging in as a role in a
// bank's case tool. Remembered in the browser when storage works.
export const ROLES = [
  { key: "investigator", label: "Investigator", home: "/" },
  { key: "reviewer", label: "Reviewer", home: "/review/" },
  { key: "manager", label: "Manager", home: "/manager/" },
];
const KEY = "gg-role";

export function roleHome(key) {
  return (ROLES.find((r) => r.key === key) || ROLES[0]).home;
}

export function readRole() {
  try { return localStorage.getItem(KEY) || "investigator"; } catch { return "investigator"; }
}

export function saveRole(key) {
  try { localStorage.setItem(KEY, key); } catch { /* storage blocked: this page only */ }
}

/** The role a page belongs to (its path decides; the stored role is the fallback). */
export function roleForPath(path, stored) {
  if (path.startsWith("/review")) return "reviewer";
  if (path.startsWith("/manager")) return "manager";
  if (path === "/" || path === "") return "investigator";
  return stored;
}
