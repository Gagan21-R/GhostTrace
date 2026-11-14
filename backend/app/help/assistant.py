"""The "Explain" assistant.

Default mode is fully offline: questions and section titles are matched against the plain-language
guide in ``knowledge.py``. If ``HELP_ASSISTANT_LLM=true`` and an Anthropic key is configured, chat
questions are answered by the configured LLM - which only ever receives the guide text and the user's
question, never case evidence.
"""
from __future__ import annotations

import logging
import re

from ..config import get_settings
from .knowledge import T

log = logging.getLogger("evidencex.help")
_WORD = re.compile(r"[a-z0-9][a-z0-9\-]*")
_STOP = {"the", "a", "an", "is", "are", "of", "and", "to", "in", "on", "for", "what", "does", "do", "this", "that", "me",
         "it", "how", "why", "i", "my", "you", "can", "with", "explain", "mean", "means", "about", "tell", "please", "page",
         "section", "by", "be", "or", "as", "at", "from", "your", "show", "shows", "which", "when", "where", "who"}


def _tokens(text: str) -> list[str]:
    return [w for w in _WORD.findall(text.lower()) if w not in _STOP]


def rank(query: str, page: str = "", topic_hint: str | None = None, limit: int = 3) -> list[tuple[float, dict]]:
    q = query.lower()
    toks = set(_tokens(query))
    page_toks = set(_tokens(page))
    scored = []
    for key, t in T.items():
        s = 0.0
        if topic_hint and key == topic_hint:
            s += 100
        for kw in t["keywords"]:
            if kw in q:
                s += 6 + len(kw) / 4  # whole-phrase hit; longer phrases are more specific
            elif kw in page.lower():
                s += 1.5
        title_toks = set(_tokens(t["title"]))
        s += 3 * len(toks & title_toks) + 1 * len(page_toks & title_toks)
        kw_toks = set(w for kw in t["keywords"] for w in _tokens(kw))
        s += 1.0 * len(toks & kw_toks)
        if s > 0:
            scored.append((s, t))
    scored.sort(key=lambda x: -x[0])
    return scored[:limit]


def render(t: dict, heading: str | None = None) -> str:
    head = f"**{heading}**" if heading and heading.lower() != t["title"].lower() else f"**{t['title']}**"
    if heading and heading.lower() != t["title"].lower():
        head += f" — part of *{t['title']}*"
    return (f"{head}\n\n{t['what']}\n\n**Example:** {t['example']}\n\n**Why it matters:** {t['why']}\n\n"
            f"**Tip:** {t['tip']}")


def related(t: dict) -> list[dict]:
    return [{"key": k, "title": T[k]["title"]} for k in t["related"] if k in T]


def explain(title: str, page: str = "", topic: str | None = None, context: str = "") -> dict:
    hits = rank(f"{title} {context}", page, topic)
    if not hits:
        hits = rank(page, page)
    if not hits:
        return {"answer": f"**{title}**\n\nThis part of EVIDENCE-X isn't in my guide yet. In general, every number and finding "
                          "on screen comes from your own case's evidence, and anything the engine suggests is waiting for a "
                          "person to confirm. Try asking me a question in your own words.",
                "topic": None, "related": [{"key": "evidence_x", "title": T["evidence_x"]["title"]}], "mode": "guide"}
    t = hits[0][1]
    return {"answer": render(t, title), "topic": t["key"], "related": related(t), "mode": "guide"}


GREETING = re.compile(r"^\s*(hi|hii+|hello|hey|yo|good (morning|afternoon|evening))\b", re.I)


def _guide_reply(question: str, page: str) -> dict:
    if GREETING.match(question) and len(question.split()) <= 4:
        return {"answer": "Hi! I'm the EVIDENCE-X guide. Press any **Explain** button on the screen, or ask me things like "
                          "*\"what is a contradiction?\"*, *\"what does HOLD mean?\"* or *\"how do I start a case?\"*.",
                "topic": None, "related": [{"key": k, "title": T[k]["title"]} for k in ("evidence_x", "challenge", "dna")],
                "mode": "guide"}
    hits = rank(question, page)
    if not hits or hits[0][0] < 2:
        return {"answer": "I'm not sure which part you mean. I can explain any screen, button or term in EVIDENCE-X - try "
                          "naming it (for example *timeline*, *Evidence DNA*, *What-If Lab*, *SHA-256*), or press an "
                          "**Explain** button next to the section you're looking at.",
                "topic": None, "related": [{"key": k, "title": T[k]["title"]} for k in ("evidence_x", "timeline", "contradictions", "reports")],
                "mode": "guide"}
    t = hits[0][1]
    answer = render(t)
    if len(hits) > 1 and hits[1][0] >= hits[0][0] * 0.7:
        answer += f"\n\n*You might also mean* **{hits[1][1]['title']}** — ask about it and I'll explain."
    return {"answer": answer, "topic": t["key"], "related": related(t), "mode": "guide"}


HELP_SYSTEM = (
    "You are the in-app guide for EVIDENCE-X, a digital-evidence investigation platform. Explain features in simple, "
    "friendly words for non-experts: short paragraphs, one concrete example, no jargon without a definition. Use ONLY "
    "the guide excerpts provided; if the answer isn't covered, say so and suggest the closest feature. You have no "
    "access to any case or evidence - never claim to know what is in the user's case. Never say anyone is guilty, "
    "never say a file is authentic because its hash matches, and never give legal advice. Keep answers under 180 words."
)


def _llm_enabled() -> bool:
    s = get_settings()
    return bool(s.help_assistant_llm and s.anthropic_api_key and s.llm_model)


def _llm_reply(messages: list[dict], page: str) -> dict | None:
    s = get_settings()
    last = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
    hits = rank(last, page, limit=4)
    ctx = "\n\n".join(f"## {t['title']}\n{t['what']}\nExample: {t['example']}\nWhy: {t['why']}\nTip: {t['tip']}"
                      for _, t in hits) or "\n\n".join(f"## {t['title']}\n{t['what']}" for t in list(T.values())[:12])
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=s.anthropic_api_key, max_retries=1, timeout=45)
        resp = client.messages.create(
            model=s.llm_model, max_tokens=700,
            system=f"{HELP_SYSTEM}\n\nUser is on page: {page or 'unknown'}\n\n<guide>\n{ctx}\n</guide>",
            messages=[{"role": m["role"], "content": m["content"][:2000]} for m in messages[-8:]],
        )
    except Exception as e:  # network, auth or rate limit - fall back to the offline guide
        log.warning("help assistant LLM unavailable: %s", str(e)[:200])
        return None
    if resp.stop_reason == "refusal":
        return None
    text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text").strip()
    if not text:
        return None
    t = hits[0][1] if hits else None
    return {"answer": text, "topic": t["key"] if t else None, "related": related(t) if t else [], "mode": "ai"}


def chat(messages: list[dict], page: str = "") -> dict:
    last = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
    if _llm_enabled():
        out = _llm_reply(messages, page)
        if out:
            return out
    return _guide_reply(last, page)


def mode() -> str:
    return "ai" if _llm_enabled() else "guide"
