/** "Ask GhostTrace" - the explain chatbot.
 *
 * Every section, page header and stat tile renders an <ExplainButton>. Clicking it opens this panel and
 * asks the backend guide to explain that part of the screen in plain words. Users can also type questions.
 * Works offline (built-in guide); the backend may use an LLM for typed questions when an admin enables it,
 * and even then only the guide text and the question are sent - never case evidence.
 */
import clsx from "clsx";
import { AnimatePresence, motion } from "framer-motion";
import { ArrowUpRight, HelpCircle, Loader2, MessageCircleQuestion, RotateCcw, Send, Sparkles, X } from "lucide-react";
import { getLang, t } from "../lib/i18n";
import { createContext, Fragment, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useLocation } from "react-router-dom";
import { api } from "../lib/api";

type Related = { key: string; title: string };
type Msg = { role: "user" | "assistant"; content: string; related?: Related[]; mode?: string };
type Reply = { answer: string; topic: string | null; related: Related[]; mode: string };

interface AssistantCtx {
  open: boolean;
  setOpen: (v: boolean) => void;
  explain: (title: string, opts?: { topic?: string; context?: string }) => void;
  ask: (q: string) => void;
}
const Ctx = createContext<AssistantCtx | null>(null);
export const useAssistant = () => useContext(Ctx);

type ChatLang = "en" | "hi" | "kn";
const SUGGESTIONS: Record<ChatLang, string[]> = {
  en: ["What is GhostTrace?", "What does HOLD mean?", "Is this screenshot fake?", "How correct is the model?"],
  hi: ["GhostTrace क्या है?", "विरोधाभास क्या है?", "नकली स्क्रीनशॉट कैसे पता चलता है?", "विश्वास अंक क्या है?"],
  kn: ["GhostTrace ಎಂದರೇನು?", "ವಿರೋಧಾಭಾಸ ಎಂದರೇನು?", "ನಕಲಿ ಸ್ಕ್ರೀನ್‌ಶಾಟ್ ಹೇಗೆ ಗೊತ್ತಾಗುತ್ತೆ?", "ವಿಶ್ವಾಸ ಅಂಕ ಎಂದರೇನು?"],
};
const CHAT_LANGS: { id: ChatLang; label: string }[] = [{ id: "en", label: "EN" }, { id: "hi", label: "हिन्दी" }, { id: "kn", label: "ಕನ್ನಡ" }];
const UI_TXT: Record<ChatLang, { related: string; thinking: string; fail: string; tell: string; answers: string }> = {
  en: { related: "Related", thinking: "Thinking it through…", fail: "I couldn't reach the guide just now. Please try again in a moment.", tell: "Tell me about", answers: "Answers in" },
  hi: { related: "संबंधित", thinking: "सोच रहा हूँ…", fail: "अभी गाइड से जुड़ नहीं पाया। थोड़ी देर बाद फिर कोशिश करें।", tell: "इसके बारे में बताइए:", answers: "उत्तर की भाषा" },
  kn: { related: "ಸಂಬಂಧಿತ", thinking: "ಯೋಚಿಸುತ್ತಿದ್ದೇನೆ…", fail: "ಈಗ ಮಾರ್ಗದರ್ಶಿಯನ್ನು ತಲುಪಲಾಗಲಿಲ್ಲ. ಸ್ವಲ್ಪ ಸಮಯದ ನಂತರ ಪ್ರಯತ್ನಿಸಿ.", tell: "ಇದರ ಬಗ್ಗೆ ಹೇಳಿ:", answers: "ಉತ್ತರದ ಭಾಷೆ" },
};
const GREET: Record<ChatLang, string> = {
  en: "Hi! I explain everything on screen in plain words. Press any **Explain** button next to a section, or ask me a question.",
  hi: "नमस्ते! मैं स्क्रीन पर सब कुछ आसान शब्दों में समझाता हूँ। किसी भी सेक्शन के पास **समझाएँ** बटन दबाएँ या मुझसे सवाल पूछें।",
  kn: "ನಮಸ್ಕಾರ! ಪರದೆಯಲ್ಲಿರುವ ಎಲ್ಲವನ್ನೂ ಸರಳ ಪದಗಳಲ್ಲಿ ವಿವರಿಸುತ್ತೇನೆ. ಯಾವುದೇ ವಿಭಾಗದ ಪಕ್ಕದ **ವಿವರಿಸಿ** ಬಟನ್ ಒತ್ತಿ ಅಥವಾ ಪ್ರಶ್ನೆ ಕೇಳಿ.",
};
const initialChatLang = (): ChatLang => {
  try { const v = localStorage.getItem("evx_chat_lang"); if (v === "en" || v === "hi" || v === "kn") return v; } catch { /* storage blocked */ }
  return getLang();
};


function pageName(pathname: string): string {
  const p = pathname.replace(/\/[0-9a-f]{32}/g, "").split("/").filter(Boolean);
  return p.length ? p.join(" ") : "overview";
}

export function AssistantProvider({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const [chatLang, setChatLangState] = useState<ChatLang>(initialChatLang);
  const greet = (l: ChatLang): Msg => ({ role: "assistant", content: GREET[l] });
  const [msgs, setMsgs] = useState<Msg[]>(() => [greet(initialChatLang())]);
  const setChatLang = (l: ChatLang) => {
    setChatLangState(l);
    try { localStorage.setItem("evx_chat_lang", l); } catch { /* storage blocked */ }
    setMsgs((xs) => (xs.length <= 1 ? [greet(l)] : [...xs, greet(l)]));
  };
  const [busy, setBusy] = useState(false);
  const loc = useLocation();
  const page = pageName(loc.pathname);

  const push = (m: Msg) => setMsgs((xs) => [...xs, m]);
  const fail = () => push({ role: "assistant", content: UI_TXT[chatLang].fail });

  const explain = useCallback(async (title: string, opts?: { topic?: string; context?: string }) => {
    setOpen(true);
    push({ role: "user", content: `${t("Explain")} “${title}”` });
    setBusy(true);
    try {
      const r = await api.post<Reply>("/api/help/explain", { title: title.slice(0, 200), page, topic: opts?.topic, context: (opts?.context || "").slice(0, 500), lang: chatLang });
      push({ role: "assistant", content: r.answer, related: r.related, mode: r.mode });
    } catch { fail(); } finally { setBusy(false); }
  }, [page, chatLang]);

  const ask = useCallback(async (q: string) => {
    const text = q.trim();
    if (!text) return;
    setOpen(true);
    const history = [...msgs.filter((m) => !Object.values(GREET).includes(m.content)), { role: "user" as const, content: text }];
    push({ role: "user", content: text });
    setBusy(true);
    try {
      const r = await api.post<Reply>("/api/help/chat", { messages: history.slice(-12).map(({ role, content }) => ({ role, content: content.slice(0, 4000) })), page, lang: chatLang });
      push({ role: "assistant", content: r.answer, related: r.related, mode: r.mode });
    } catch { fail(); } finally { setBusy(false); }
  }, [msgs, page, chatLang]);

  const topic = useCallback(async (key: string, title: string) => {
    push({ role: "user", content: `${UI_TXT[chatLang].tell} “${title}”` });
    setBusy(true);
    try {
      const r = await api.get<Reply>(`/api/help/topics/${key}?lang=${chatLang}`);
      push({ role: "assistant", content: r.answer, related: r.related, mode: r.mode });
    } catch { fail(); } finally { setBusy(false); }
  }, [chatLang]);

  const value = useMemo(() => ({ open, setOpen, explain, ask }), [open, explain, ask]);
  return (
    <Ctx.Provider value={value}>
      {children}
      <AssistantPanel open={open} setOpen={setOpen} msgs={msgs} busy={busy} onAsk={ask} onTopic={topic}
        onReset={() => setMsgs([greet(chatLang)])} chatLang={chatLang} setChatLang={setChatLang} />
    </Ctx.Provider>
  );
}

/** Tiny, safe markdown: **bold**, *italic*, paragraphs. Renders text nodes only (no HTML injection). */
export function Md({ text }: { text: string }) {
  return (
    <>{text.split(/\n{2,}/).map((para, i) => (
      <p key={i} className="mb-2 last:mb-0">
        {para.split(/(\*\*[^*]+\*\*|\*[^*]+\*)/g).map((part, j) => {
          if (part.startsWith("**") && part.endsWith("**")) return <strong key={j} className="font-bold">{part.slice(2, -2)}</strong>;
          if (part.startsWith("*") && part.endsWith("*") && part.length > 2) return <em key={j}>{part.slice(1, -1)}</em>;
          return <Fragment key={j}>{part}</Fragment>;
        })}
      </p>))}
    </>
  );
}

function AssistantPanel({ open, setOpen, msgs, busy, onAsk, onTopic, onReset, chatLang, setChatLang }: {
  open: boolean; setOpen: (v: boolean) => void; msgs: Msg[]; busy: boolean; onAsk: (q: string) => void;
  onTopic: (key: string, title: string) => void; onReset: () => void; chatLang: ChatLang; setChatLang: (l: ChatLang) => void;
}) {
  const U = UI_TXT[chatLang];
  const [draft, setDraft] = useState("");
  const end = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLInputElement>(null);
  useEffect(() => { end.current?.scrollIntoView?.({ behavior: "smooth", block: "end" }); }, [msgs, busy, open]);
  useEffect(() => { if (open) setTimeout(() => input.current?.focus(), 250); }, [open]);
  useEffect(() => {
    const h = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [setOpen]);
  const lastMode = [...msgs].reverse().find((m) => m.mode)?.mode;
  const send = () => { if (!busy && draft.trim()) { onAsk(draft); setDraft(""); } };

  return (
    <>
      <AnimatePresence>
        {!open && (
          <motion.button key="fab" onClick={() => setOpen(true)} aria-label="Open the Ask GhostTrace assistant"
            initial={{ scale: 0, rotate: -20 }} animate={{ scale: 1, rotate: 0 }} exit={{ scale: 0, rotate: 20 }}
            whileHover={{ y: -3, rotate: -2 }} whileTap={{ scale: 0.94 }}
            className="fixed bottom-5 right-5 z-[60] flex items-center gap-2 border-[3px] border-ink-900 bg-acid px-4 py-3 font-display text-sm uppercase tracking-wide text-ink-900 shadow-brutal-lg">
            <MessageCircleQuestion className="h-5 w-5" />{t("Ask GhostTrace")}
          </motion.button>)}
      </AnimatePresence>
      <AnimatePresence>
        {open && (
          <motion.aside key="panel" role="dialog" aria-label="Ask GhostTrace"
            initial={{ y: 40, opacity: 0, rotate: 1.5 }} animate={{ y: 0, opacity: 1, rotate: 0 }} exit={{ y: 40, opacity: 0, rotate: -1.5 }}
            transition={{ type: "spring", damping: 24, stiffness: 300 }}
            className="fixed bottom-0 right-0 z-[60] flex h-[min(640px,100dvh)] w-full flex-col border-[3px] border-ink-900 bg-paper shadow-brutal-lg sm:bottom-5 sm:right-5 sm:w-[420px]">
            <header className="flex items-center gap-3 border-b-[3px] border-ink-900 bg-ink-900 px-4 py-3 text-paper">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center border-2 border-paper bg-acid text-ink-900"><Sparkles className="h-4 w-4" /></div>
              <div className="min-w-0 flex-1">
                <div className="font-display text-base uppercase leading-none tracking-wide">{t("Ask GhostTrace")}</div>
                <div className="mt-1 text-[11px] text-paper/70">
                  {lastMode === "ai" ? "AI answers from the built-in guide" : "Plain-language guide · works offline"} · never sees your evidence
                </div>
              </div>
              <button className="p-1.5 hover:bg-paper/10" onClick={onReset} title="Start over" aria-label="Clear conversation"><RotateCcw className="h-4 w-4" /></button>
              <button className="p-1.5 hover:bg-paper/10" onClick={() => setOpen(false)} aria-label="Close assistant"><X className="h-5 w-5" /></button>
            </header>
            <div className="flex items-center gap-2 border-b-2 border-ink-900 bg-acid/40 px-3 py-1.5" role="group" aria-label="Answer language">
              <span className="text-[10px] font-bold uppercase tracking-wider">{U.answers}</span>
              {CHAT_LANGS.map((l) => (
                <button key={l.id} onClick={() => setChatLang(l.id)} aria-pressed={chatLang === l.id}
                  className={clsx("border-2 border-ink-900 px-2 py-0.5 text-xs font-bold", chatLang === l.id ? "bg-ink-900 text-acid" : "bg-surface hover:bg-acid")}>{l.label}</button>))}
            </div>
            <div className="flex-1 space-y-3 overflow-y-auto px-4 py-4 scrollbar-thin" aria-live="polite">
              {msgs.map((m, i) => (
                <motion.div key={i} initial={{ opacity: 0, x: m.role === "user" ? 16 : -16 }} animate={{ opacity: 1, x: 0 }}
                  className={clsx("flex", m.role === "user" ? "justify-end" : "justify-start")}>
                  <div className={clsx("max-w-[88%] border-2 border-ink-900 px-3.5 py-2.5 text-[13.5px] leading-relaxed",
                    m.role === "user" ? "bg-ink-900 text-paper shadow-[3px_3px_0_0_#ff4f1f]" : "bg-surface text-ink-900 shadow-brutal-sm")}>
                    {m.role === "assistant" ? <Md text={m.content} /> : m.content}
                    {m.mode === "ai" && <div className="mt-1 text-[10px] uppercase tracking-wider text-slate-500">AI-written from the guide</div>}
                    {m.related && m.related.length > 0 && (
                      <div className="mt-2 flex flex-wrap gap-1.5 border-t-2 border-dashed border-ink-900/20 pt-2">
                        <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500">{U.related}</span>
                        {m.related.map((r) => (
                          <button key={r.key} disabled={busy} onClick={() => onTopic(r.key, r.title)}
                            className="inline-flex items-center gap-0.5 border-[1.5px] border-ink-900 bg-paper px-1.5 py-0.5 text-[11px] font-semibold hover:bg-acid">
                            {r.title}<ArrowUpRight className="h-3 w-3" /></button>))}
                      </div>)}
                  </div>
                </motion.div>))}
              {busy && <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-slate-500"><Loader2 className="h-3.5 w-3.5 animate-spin" />{U.thinking}</div>}
              {msgs.length === 1 && (
                <div className="flex flex-wrap gap-2 pt-1">
                  {SUGGESTIONS[chatLang].map((s) => (
                    <button key={s} onClick={() => onAsk(s)} className="border-2 border-ink-900 bg-surface px-2.5 py-1 text-xs font-semibold shadow-brutal-sm transition hover:-translate-y-0.5 hover:bg-acid">{s}</button>))}
                </div>)}
              <div ref={end} />
            </div>
            <form className="flex gap-2 border-t-[3px] border-ink-900 bg-surface p-3" onSubmit={(e) => { e.preventDefault(); send(); }}>
              <input ref={input} className="input flex-1" placeholder={t("Ask anything about this screen…")} value={draft} maxLength={1000}
                onChange={(e) => setDraft(e.target.value)} aria-label="Your question" />
              <button className="btn-primary !px-3" disabled={busy || !draft.trim()} aria-label="Send"><Send className="h-4 w-4" /></button>
            </form>
          </motion.aside>)}
      </AnimatePresence>
    </>
  );
}

function textOf(node: ReactNode): string {
  if (node == null || typeof node === "boolean") return "";
  if (typeof node === "string" || typeof node === "number") return String(node);
  if (Array.isArray(node)) return node.map(textOf).join(" ");
  if (typeof node === "object" && "props" in (node as any)) return textOf((node as any).props.children);
  return "";
}

/** The "Explain" button. `title` may be any React node; its text is what gets explained. */
export function ExplainButton({ title, topic, context, size = "sm", className, label = "Explain" }: {
  title: ReactNode; topic?: string; context?: string; size?: "xs" | "sm"; className?: string; label?: string;
}) {
  const a = useAssistant();
  const text = textOf(title).replace(/\s+/g, " ").trim();
  if (!a || !text) return null;
  return (
    <button type="button" onClick={(e) => { e.stopPropagation(); e.preventDefault(); a.explain(text, { topic, context }); }}
      title={`Explain “${text}” in simple words`} aria-label={`Explain ${text}`} data-explain={text}
      className={clsx("explain-btn group inline-flex shrink-0 items-center gap-1 border-2 border-ink-900 bg-paper font-bold uppercase tracking-wider text-ink-900 transition",
        "hover:-translate-x-px hover:-translate-y-px hover:bg-acid hover:shadow-brutal-sm active:translate-x-0 active:translate-y-0 active:shadow-none",
        size === "xs" ? "px-1 py-0.5 text-[9px]" : "px-1.5 py-0.5 text-[10px]", className)}>
      <HelpCircle className={size === "xs" ? "h-2.5 w-2.5" : "h-3 w-3"} />{size === "sm" && t(label)}
    </button>
  );
}
