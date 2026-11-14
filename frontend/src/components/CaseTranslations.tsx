import clsx from "clsx";
import { Languages } from "lucide-react";
import { useState } from "react";
import { t } from "../lib/i18n";

export type Translations = Record<string, Record<string, string>>;

const LANGS = [{ id: "hi", label: "हिन्दी" }, { id: "kn", label: "ಕನ್ನಡ" }];

/** Optional Hindi / Kannada versions of a case's title, description and objective. */
export default function CaseTranslations({ value, onChange }: { value: Translations; onChange: (v: Translations) => void }) {
  const filled = LANGS.some((l) => Object.values(value?.[l.id] || {}).some(Boolean));
  const [open, setOpen] = useState(filled);
  const [lang, setLang] = useState("hi");
  const cur = value?.[lang] || {};
  const set = (k: string, v: string) => onChange({ ...(value || {}), [lang]: { ...cur, [k]: v } });
  return (
    <div className="border-2 border-dashed border-ink-900/40 p-3">
      <button type="button" onClick={() => setOpen(!open)} className="flex w-full items-center gap-2 text-left text-sm font-bold">
        <Languages className="h-4 w-4" />{t("Hindi and Kannada versions (optional)")}<span className="ml-auto text-xs">{open ? "−" : "+"}</span></button>
      {open && (
        <div className="mt-3 space-y-2">
          <p className="text-xs text-slate-600">{t("Shown instead of the English text when that language is selected. Evidence itself is never translated.")}</p>
          <div className="flex gap-1">{LANGS.map((l) => (
            <button key={l.id} type="button" onClick={() => setLang(l.id)}
              className={clsx("border-2 border-ink-900 px-3 py-1 text-sm font-bold", lang === l.id ? "bg-acid" : "bg-surface")}>{l.label}</button>))}</div>
          <input className="input" placeholder={t("Title")} value={cur.title || ""} onChange={(e) => set("title", e.target.value)} maxLength={200} />
          <textarea className="input min-h-[70px]" placeholder={t("Description")} value={cur.description || ""} onChange={(e) => set("description", e.target.value)} maxLength={5000} />
          <textarea className="input min-h-[50px]" placeholder={t("Objective")} value={cur.objective || ""} onChange={(e) => set("objective", e.target.value)} maxLength={3000} />
        </div>)}
    </div>
  );
}
