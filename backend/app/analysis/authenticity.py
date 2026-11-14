"""Message Authenticity agent: was a disputed message really sent by the person it appears to come from?

The problem: someone gains access to A's phone or WhatsApp (linked device, SIM swap, stolen OTP), sends B an
abusive message "as A", and B files a harassment complaint with a screenshot. Or B fabricates/edits the
screenshot outright. A screenshot alone cannot tell these apart. This agent gathers the records that can,
by calling tools (see ``app/tools``), and weighs three kinds of indicator:

* Fabrication: the message is not in either phone's export, the wording/time differs from the export,
  editing or chat-generator software is named, the status-bar clock is earlier than the messages,
  error-level analysis shows pasted regions.
* Account compromise: a new linked device, SIM change, new sign-in or OTP/password reset shortly before;
  the account log shows the message was sent from a web/linked device; the holder is recorded elsewhere
  (exam hall, flight, hospital) at that minute; the text does not read like the holder's writing.
* Consistent with the account holder: the message is in the holder's own export, no security events in the
  window although logs exist, writing style matches, later messages acknowledge it.

The output is a set of indicators for a human reviewer, never a finding of who typed the message.
"""
from __future__ import annotations

import json
import logging

from sqlalchemy import delete
from sqlalchemy.orm import Session

from ..models import AuthenticityAssessment
from ..tools import case_tools  # noqa: F401  (registers the tools)
from ..tools.case_tools import CaseCtx
from ..tools.registry import REGISTRY, ToolSession

log = logging.getLogger("evidencex.authenticity")

VERDICTS = {
    "likely_fabricated": "Screenshot not supported by source records",
    "possible_impersonation": "Sent from the account, but indicators point to someone else using it",
    "consistent_with_account_holder": "Records are consistent with the account holder sending it",
    "insufficient_evidence": "Not enough records to tell",
}


def _ind(kind, key, weight, text, refs=None):
    return {"kind": kind, "key": key, "weight": weight, "text": text, "refs": [r for r in (refs or []) if r]}


def assess(session: ToolSession, d: dict) -> dict:
    """Deterministic planner: a fixed, explainable sequence of tool calls for one disputed message."""
    sender, text = d.get("claimed_sender") or "", d["text"]
    ind: list[dict] = []
    session.call("classify_message", {"text": text}, "What kind of message is it?")
    shot = session.call("inspect_screenshot", {"code": d["code"]}, "Is the screenshot itself trustworthy?")
    found = session.call("search_message_exports", {"text": text, "sender": sender},
                         f"Does the message exist in {sender or 'the sender'}'s chat history on either phone?")
    exports, matches = found.get("exports", []), found.get("matches", [])
    best = matches[0] if matches else None
    when = best["time"] if best and best["similarity"] >= 0.6 else None
    if not when and d.get("screenshot_date"):
        when = f"{d['screenshot_date']} {d['time_on_screen']}"

    # ---------------- fabrication
    if shot.get("editing_or_generator"):
        ind.append(_ind("fabrication", "generator_or_editor", 0.5, f"Screenshot names editing / chat-generator software or text "
                        f"({shot.get('software_tags') or 'visible on the image'}).", [d["code"]]))
    if shot.get("clock_before_messages"):
        ind.append(_ind("fabrication", "clock_before_messages", 0.4, f"Status-bar clock ({shot['status_bar_time']}) is earlier than the "
                        f"latest message on screen ({shot['last_message_time']}); a real screenshot is taken after its messages.", [d["code"]]))
    if shot.get("ela_anomaly"):
        ind.append(_ind("fabrication", "ela_anomaly", 0.25, f"Error-level analysis: {shot['ela']['outlier_blocks']} text regions were "
                        "compressed differently from the rest of the image (possible pasted or edited area).", [d["code"]]))
    covering = [x for x in exports if x["messages"] > 0]
    if best and best["similarity"] >= 0.9:
        ind.append(_ind("authentic", "in_export", 0.35 if best["from_sender_device"] else 0.25,
                        f"Same message found in chat export {best['code']} ({best['locator']}, {best['time']}), "
                        f"{'exported from the sender' + chr(39) + 's own phone' if best['from_sender_device'] else 'exported from the recipient' + chr(39) + 's phone'}.",
                        [best["code"]]))
        if d.get("time_on_screen") and best.get("time") and d["time_on_screen"].split()[0] not in best["time"]:
            ind.append(_ind("fabrication", "time_mismatch", 0.3, f"Time on screenshot ({d['time_on_screen']}) differs from the export "
                            f"({best['time']}) for the same message.", [d["code"], best["code"]]))
    elif best and best["similarity"] >= 0.6:
        ind.append(_ind("fabrication", "text_altered", 0.5, f"Closest message in export {best['code']} reads differently "
                        f"({best['similarity']:.0%} similar): \"{best['text'][:90]}\". The screenshot wording may have been edited.",
                        [d["code"], best["code"]]))
    elif covering:
        ind.append(_ind("fabrication", "not_in_exports", 0.6, f"Message not found in {len(covering)} chat export(s) "
                        f"({', '.join(x['code'] for x in covering)}) that cover this conversation.", [x["code"] for x in covering]))

    # ---------------- account compromise (only meaningful if the message was really sent)
    sec = session.call("account_security_events", {"around": when, "person": sender}, "Was the account accessed by a new device "
                       "or SIM shortly before?") if when else {}
    labels = {"device_link": ("A new device was linked to the account", 0.35), "sim_change": ("The SIM was changed / re-issued", 0.35),
              "login": ("A sign-in was recorded", 0.15), "password_reset": ("Password was reset", 0.15),
              "recovery_change": ("Recovery details were changed", 0.15), "mfa": ("An OTP / verification code was requested", 0.1),
              "security_alert": ("A security alert was raised", 0.1)}
    seen = set()
    for ev in sec.get("events", []):
        if not ev["concerns_person"] or ev["type"] in seen:
            continue
        seen.add(ev["type"])
        what, w = labels[ev["type"]]
        if ev["type"] == "login" and not __import__("re").search(r"new|unknown|unrecognised|unrecognized|web|linked", ev["what"], __import__("re").I):
            continue
        ind.append(_ind("compromise", ev["type"], w, f"{what} {ev['minutes_before']} min before the message: \"{ev['what'][:110]}\".", [ev["code"]]))
    for s in sec.get("message_sent_from_linked_or_web_device", [])[:1]:
        ind.append(_ind("compromise", "sent_from_linked_device", 0.4, f"Account log shows the message was sent from a web / linked device: "
                        f"\"{s['what'][:110]}\".", [s["code"]]))
    if when and sec.get("account_logs_available") and not seen:
        ind.append(_ind("authentic", "no_security_events", 0.25, f"Account logs ({', '.join(sec['account_logs_available'])}) show no new "
                        "device, SIM change or reset in the 48 hours before the message.", sec["account_logs_available"]))
    if when and sender:
        wb = session.call("person_whereabouts", {"person": sender, "around": when}, f"Where was {sender} at that minute?")
        for r in wb.get("records", [])[:1]:
            when_txt = ("for a period that includes the message time" if r.get("covers_message_time") else
                        f"{abs(r['minutes_from_message'])} min {'after' if r['minutes_from_message'] > 0 else 'before'} the message")
            ind.append(_ind("compromise", "alibi", 0.35, f"{sender} is recorded elsewhere {when_txt}: \"{r['record'][:110]}\" ({r['source']}).", [r["code"]]))
        style = session.call("compare_writing_style", {"text": text, "person": sender}, f"Does it read like {sender}'s own messages?")
        if style.get("usable"):
            p = style["p_same_author"]
            if p < 0.35:
                ind.append(_ind("compromise", "style_mismatch", 0.2, f"Writing style differs from {sender}'s {style['known_messages']} known "
                                f"messages (Naive Bayes authorship score {p:.0%}).", []))
            elif p > 0.65:
                ind.append(_ind("authentic", "style_match", 0.25, f"Writing style is similar to {sender}'s {style['known_messages']} known "
                                f"messages (Naive Bayes authorship score {p:.0%}).", []))
        after = session.call("messages_after", {"person": sender, "after": when}, f"What did {sender} say afterwards?")
        import re
        for m in after.get("messages", []):
            if re.search(r"hack|not me|wasn'?t me|someone (?:used|accessed|logged)|didn'?t send|linked device", m["text"], re.I):
                ind.append(_ind("compromise", "reported_compromise", 0.1, f"{sender} later wrote: \"{m['text'][:100]}\" (a claim, weak on its own).", [m["code"]]))
                break
            if re.search(r"\bsorry\b|didn'?t mean|i was angry|apolog", m["text"], re.I):
                ind.append(_ind("authentic", "acknowledged", 0.2, f"{sender} later wrote: \"{m['text'][:100]}\".", [m["code"]]))
                break

    fab = min(1.0, sum(i["weight"] for i in ind if i["kind"] == "fabrication"))
    comp = min(1.0, sum(i["weight"] for i in ind if i["kind"] == "compromise"))
    auth = min(1.0, sum(i["weight"] for i in ind if i["kind"] == "authentic"))
    if fab >= 0.6 and fab > auth:
        verdict = "likely_fabricated"
    elif comp >= 0.6 and comp > auth:
        verdict = "possible_impersonation"
    elif auth >= 0.5 and comp < 0.3 and fab < 0.3:
        verdict = "consistent_with_account_holder"
    else:
        verdict = "insufficient_evidence"
    recs = recommendations(verdict, ind, exports, sec)
    return {"verdict": verdict, "fabrication_score": round(fab, 2), "compromise_score": round(comp, 2), "authentic_score": round(auth, 2),
            "message_time": when, "indicators": ind, "recommendations": recs}


def recommendations(verdict, ind, exports, sec) -> list[str]:
    keys = {i["key"] for i in ind}
    r = []
    if not any(x["from_sender_device"] for x in exports):
        r.append("Obtain a forensic extraction (or at least a chat export) from the accused account holder's own phone.")
    if not exports:
        r.append("Obtain the chat export from the complainant's phone; a screenshot alone cannot be verified.")
    r.append("Collect the original screenshot file from the complainant's device (with its metadata), not a forwarded copy.")
    if not (sec or {}).get("account_logs_available"):
        r.append("Request the messaging account's linked-device / session log and IP records from the provider through legal process.")
    if keys & {"sim_change", "device_link", "sent_from_linked_device"} or verdict == "possible_impersonation":
        r.append("Request SIM change / port records from the mobile carrier and the IP subscriber for the linked session.")
    if "alibi" in keys:
        r.append("Verify the attendance / location record independently (CCTV, invigilator, second log).")
    r.append("Treat any conclusion as provisional: a human reviewer must confirm before it is used.")
    return r


def _summary(d, res) -> str:
    top = sorted(res["indicators"], key=lambda i: -i["weight"])[:3]
    why = "; ".join(i["text"].split(":")[0].rstrip(".") for i in top) or "no strong indicators either way"
    return f"\"{d['text'][:80]}\" shown as from {d.get('claimed_sender') or 'unknown'}: {VERDICTS[res['verdict']].lower()}. Main reasons: {why}."


def run_case(db: Session, case_id: str, run_id: str | None = None) -> dict:
    ctx = CaseCtx.load(db, case_id)
    db.execute(delete(AuthenticityAssessment).where(AuthenticityAssessment.case_id == case_id))
    finder = ToolSession(REGISTRY, ctx)
    disputed = finder.call("find_disputed_messages", {}, "Which screenshot messages could be disputed?")
    if isinstance(disputed, dict):
        disputed = []
    seen, out = set(), []
    for d in disputed:
        key = (d["code"], d["text"][:40])
        if key in seen:
            continue
        seen.add(key)
        session = ToolSession(REGISTRY, ctx)
        session.trace = list(finder.trace)
        res = assess(session, d)
        mode = "deterministic-planner"
        narrative = llm_review(ctx, d, res)
        if narrative:
            mode = "deterministic-planner+llm-tool-review"
        row = AuthenticityAssessment(case_id=case_id, run_id=run_id, evidence_id=ctx.by_code(d["code"]).id, disputed_text=d["text"],
                                     claimed_sender=d.get("claimed_sender"), message_time=res["message_time"], verdict=res["verdict"],
                                     fabrication_score=res["fabrication_score"], compromise_score=res["compromise_score"],
                                     indicators=res["indicators"] + [{"kind": "score", "key": "authentic_score", "weight": res["authentic_score"],
                                                                      "text": "", "refs": []}],
                                     tool_trace=session.trace, recommendations=res["recommendations"],
                                     summary=(narrative or _summary(d, res)), mode=mode)
        db.add(row)
        out.append({"code": d["code"], "sender": d.get("claimed_sender"), "verdict": res["verdict"],
                    "fabrication": res["fabrication_score"], "compromise": res["compromise_score"], "tool_calls": len(session.trace)})
    db.flush()
    return {"assessed": len(out), "results": out}


# ------------------------------------------------------------------------------------- optional LLM tool use
def llm_review(ctx: CaseCtx, d: dict, res: dict) -> str | None:
    """With the case's external-AI permission and a configured model, let the LLM drive the same tools (native tool
    use) to double-check the deterministic result and write a short narrative. It cannot change the verdict."""
    from ..agents.llm import SYSTEM_GUARD, AnthropicProvider
    if not ctx.case.allow_external_ai or not AnthropicProvider().available():
        return None
    try:
        import anthropic
        from ..config import get_settings
        s = get_settings()
        client = anthropic.Anthropic(api_key=s.anthropic_api_key, max_retries=1, timeout=90)
        session = ToolSession(REGISTRY, ctx, planner="llm")
        messages = [{"role": "user", "content": (
            f"<evidence>Disputed message (untrusted): {json.dumps(d)}</evidence>\nDeterministic result: {json.dumps(res)[:3000]}\n"
            "Use the tools to check anything that looks wrong, then write at most 120 words for the investigator. "
            "Do not name who typed the message; describe indicators only.")}]
        for _ in range(6):
            resp = client.messages.create(model=s.llm_model, max_tokens=1500, system=SYSTEM_GUARD,
                                          tools=REGISTRY.schemas("case"), messages=messages)
            if resp.stop_reason != "tool_use":
                return "".join(b.text for b in resp.content if b.type == "text").strip() or None
            messages.append({"role": "assistant", "content": resp.content})
            results = []
            for b in resp.content:
                if b.type == "tool_use":
                    out = session.call(b.name, dict(b.input), "chosen by LLM")
                    results.append({"type": "tool_result", "tool_use_id": b.id, "content": json.dumps(out, default=str)[:6000]})
            messages.append({"role": "user", "content": results})
    except Exception as e:  # never block the deterministic result
        log.warning("LLM tool review unavailable: %s", str(e)[:200])
    return None
