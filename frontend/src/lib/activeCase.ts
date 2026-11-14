// The case the investigator is currently working on. Global navigation sections (Evidence Vault, DNA,
// Timeline, ...) open on this case so nothing global is shown as if it belonged to a case.
const KEY = "evx_active_case";

export interface ActiveCase { id: string; title: string; number: string }

export function getActiveCase(): ActiveCase | null {
  try { return JSON.parse(localStorage.getItem(KEY) || "null"); } catch { return null; }
}

export function setActiveCase(c: ActiveCase | null) {
  try { c ? localStorage.setItem(KEY, JSON.stringify(c)) : localStorage.removeItem(KEY); } catch { /* storage unavailable */ }
  window.dispatchEvent(new Event("evx-active-case"));
}
