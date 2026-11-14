"""Evidence DNA: cross-file relationship fingerprinting and evidence-dependency analysis.

For every pair of evidence items we look for shared identifiers (transaction/order/shipment refs,
phones, emails, domains, IPs, accounts, usernames, amounts), overlapping text and visually similar
images, then classify how the two items depend on each other:

  duplicate      byte-identical (same SHA-256)
  near_duplicate visually identical images or near-identical text (e.g. a screenshot of a PDF)
  derived        one item contains the other's content (forwarded/quoted email, PDF embedding a screenshot)
  shared_source  both reproduce records from the same issuing source (e.g. alert email and log export
                 from the same provider) - corroboration, but not independent
  independent    different issuing sources agree on a shared identifier - independent corroboration
  uncertain      shared identifiers but the sources cannot be established

A shared identifier never establishes that two people are the same person.
"""
from __future__ import annotations

import re
from collections import defaultdict
from itertools import combinations

from sqlalchemy import delete
from sqlalchemy.orm import Session

from .. import replay
from ..models import EvidenceDependency
from .index import CaseIndex

STRONG = {"txn_ref": "transaction reference", "order_id": "order ID", "invoice_no": "invoice number", "tracking": "shipment/AWB",
          "email": "email address", "phone": "phone number", "url": "domain", "ip": "IP address", "username": "username",
          "account": "account number", "ticket": "ticket/complaint ID"}
WEAK = {"amount": "amount"}
FORWARD_RX = re.compile(r"forwarded message|original message|^>|wrote:\s*$|begin forwarded", re.I | re.M)
WORD_RX = re.compile(r"[a-z0-9]+")
DEPENDENT = {"duplicate", "near_duplicate", "derived", "shared_source"}
# For corroboration counting only copies collapse into one source. Records from the same issuer are
# flagged (shared_source) and shown, but distinct records (an invoice and a delivery record) still count.
COPY_LIKE = {"duplicate", "near_duplicate", "derived"}


def _shingles(text: str, k: int = 4) -> set[tuple]:
    w = WORD_RX.findall(text.lower())
    return {tuple(w[i:i + k]) for i in range(max(0, len(w) - k + 1))}


def _grams(text: str, n: int = 8) -> set[str]:
    """Character n-grams over text with whitespace and punctuation removed: robust to OCR spacing errors."""
    t = "".join(WORD_RX.findall(text.lower()))
    return {t[i:i + n] for i in range(max(0, len(t) - n + 1))}


def _hamming(a: str, b: str) -> int:
    return bin(int(a, 16) ^ int(b, 16)).count("1")


def _sld(domain: str) -> str:
    parts = [p for p in domain.lower().split(".") if p]
    return parts[-2] if len(parts) >= 2 else (parts[0] if parts else "")


def issuer_tokens(idx: CaseIndex, ev_id: str, known: set[str]) -> set[str]:
    """Who issued the record: sender domain for emails, platform for chats, otherwise known issuer
    names found in the document header or the collector's provenance note."""
    e = idx.ev(ev_id)
    segs = idx.segments_of(ev_id)
    toks: set[str] = set()
    if e.detected_type == "email":
        hdr = next((s for s in segs if s.kind == "email_header"), None)
        for p in (hdr.data.get("from") or []) if hdr else []:
            if p.get("address"):
                toks.add(_sld(p["address"].split("@")[-1]))
        return toks
    if e.detected_type == "chat":
        plat = str((e.file_metadata or {}).get("platform") or "").lower()
        if plat and plat != "unknown":
            toks.add("chat:" + plat.split()[0])
    hay = " ".join(s.text for s in segs[:4]).lower() + " " + (e.collection_source or "").lower()
    toks |= {k for k in known if k and len(k) > 3 and re.search(rf"\b{re.escape(k)}\b", hay)}
    return toks


def analyse(db: Session, idx: CaseIndex, run_id: str | None = None) -> dict:
    db.execute(delete(EvidenceDependency).where(EvidenceDependency.case_id == idx.case_id))
    evs = [e for e in idx.evidence.values()]
    # Fingerprints: identifiers per evidence with their first location.
    occ: dict[tuple, dict[str, object]] = defaultdict(dict)
    for f in idx.facts:
        if f.type in STRONG or f.type in WEAK:
            key = (f.type, f.extra.get("domain") if f.type == "url" else (f.extra.get("amount") if f.type == "amount" else f.norm))
            if key[1] and f.evidence_id not in occ[key]:
                occ[key][f.evidence_id] = f
    known = {_sld(f.extra.get("domain", "")) for f in idx.facts_of("url")} | {
        _sld(f.norm.split("@")[-1]) for f in idx.facts_of("email")}
    known |= {f.norm.split()[0] for f in idx.facts_of("organisation") if f.norm}
    texts = {e.id: " ".join(s.text for s in idx.segments_of(e.id)) for e in evs}
    sh = {eid: _grams(t) for eid, t in texts.items()}
    issuers = {e.id: issuer_tokens(idx, e.id, known) for e in evs}

    pair_matches: dict[tuple, list] = defaultdict(list)
    for key, where in occ.items():
        ids = sorted(where)
        for a, b in combinations(ids, 2):
            fa, fb = where[a], where[b]
            pair_matches[(a, b)].append({
                "attribute": (STRONG | WEAK)[key[0]], "type": key[0], "value": fa.value if key[0] != "url" else key[1],
                "strength": "strong" if key[0] in STRONG else "weak",
                "a": {"evidence_id": a, "segment_id": fa.segment_id, "locator": fa.locator, "excerpt": fa.excerpt},
                "b": {"evidence_id": b, "segment_id": fb.segment_id, "locator": fb.locator, "excerpt": fb.excerpt}})

    order = {e.id: e.evidence_code for e in evs}
    deps = []
    for a, b in combinations(sorted(order, key=order.get), 2):
        ea, eb = idx.ev(a), idx.ev(b)
        m = pair_matches.get((a, b)) or pair_matches.get((b, a)) or []
        strong = [x for x in m if x["strength"] == "strong"]
        sa, sb = sh[a], sh[b]
        inter = len(sa & sb)
        jac = inter / len(sa | sb) if (sa or sb) else 0.0
        cont_a = inter / len(sa) if sa else 0.0  # share of A found in B
        cont_b = inter / len(sb) if sb else 0.0
        rel, conf, direction, why = None, 0.0, "", ""
        if ea.sha256 == eb.sha256:
            rel, conf, why = "duplicate", 1.0, "Byte-identical files (same SHA-256)."
        elif ea.perceptual_hash and eb.perceptual_hash and _hamming(ea.perceptual_hash, eb.perceptual_hash) <= 6 and (jac >= 0.6 or (not sa and not sb)):
            rel, conf = "near_duplicate", 0.85
            why = f"Images are visually near-identical (perceptual-hash distance {_hamming(ea.perceptual_hash, eb.perceptual_hash)}/64)."
        elif jac >= 0.8 and min(len(sa), len(sb)) >= 20:
            rel, conf, why = "near_duplicate", round(min(0.95, jac), 2), f"Extracted text is {jac:.0%} identical (e.g. a screenshot or copy of the same record)."
        elif max(cont_a, cont_b) >= 0.6 and min(len(sa), len(sb)) >= 40:
            small, big = (a, b) if cont_a >= cont_b else (b, a)
            rel, conf = "derived", round(min(0.9, max(cont_a, cont_b)), 2)
            direction = f"{order[big]} contains {order[small]}"
            fwd = FORWARD_RX.search(texts[big])
            why = (f"{max(cont_a, cont_b):.0%} of {order[small]}'s text appears inside {order[big]}"
                   + (" (forwarded/quoted message)." if fwd else " (embedded or copied content)."))
        elif strong:
            common = issuers[a] & issuers[b]
            if common:
                rel, conf = "shared_source", 0.7
                why = f"Both records originate from the same issuer ({', '.join(sorted(common))}) and share {len(strong)} identifier(s); they corroborate each other but are not independent."
            elif issuers[a] and issuers[b]:
                rel, conf = "independent", 0.65
                why = f"Different issuing sources ({', '.join(sorted(issuers[a]))} vs {', '.join(sorted(issuers[b]))}) record the same identifier(s) - independent corroboration."
            else:
                rel, conf = "uncertain", 0.4
                why = "The records share identifier(s) but their issuing sources cannot be established from the evidence."
        if not rel:
            continue
        deps.append(EvidenceDependency(case_id=idx.case_id, evidence_a_id=a, evidence_b_id=b, relation=rel, direction=direction,
                                       matches=m[:15], text_similarity=round(jac, 3), confidence=conf, explanation=why))
    for d in deps:
        db.add(d)
    db.flush()
    for d in deps:
        if d.relation in DEPENDENT:
            replay.emit(db, idx.case_id, "dependency.detected", component="evidence_dna", actor="evidence_dna",
                        inputs=[replay.ref("evidence", d.evidence_a_id, order[d.evidence_a_id]), replay.ref("evidence", d.evidence_b_id, order[d.evidence_b_id])],
                        outputs=[replay.ref("dependency", d.id, d.relation)], summary=f"{order[d.evidence_a_id]} ↔ {order[d.evidence_b_id]}: {d.relation.replace('_', ' ')}. {d.explanation}",
                        run_id=run_id)
    counts = defaultdict(int)
    for d in deps:
        counts[d.relation] += 1
    return {"pairs": len(deps), "by_relation": dict(counts), "shared_identifiers": sum(1 for w in occ.values() if len(w) > 1)}


def clusters(deps: list[EvidenceDependency], evidence_ids: list[str], relations: set[str] | None = None) -> dict[str, int]:
    """Union-find over dependent pairs: evidence in the same cluster is one source for corroboration."""
    relations = relations or COPY_LIKE
    parent = {e: e for e in evidence_ids}

    def find(x):
        while parent.get(x, x) != x:
            parent[x] = parent.get(parent[x], parent[x])
            x = parent[x]
        return x
    for d in deps:
        if d.relation in relations and d.evidence_a_id in parent and d.evidence_b_id in parent:
            parent[find(d.evidence_a_id)] = find(d.evidence_b_id)
    roots = {}
    return {e: roots.setdefault(find(e), len(roots)) for e in evidence_ids}


def fingerprint(idx: CaseIndex, deps: list[EvidenceDependency]) -> list[dict]:
    """Shared identifiers across files, with how many INDEPENDENT sources report each one."""
    cl = clusters(deps, list(idx.evidence))
    occ: dict[tuple, dict[str, object]] = defaultdict(dict)
    for f in idx.facts:
        if f.type in STRONG or f.type in WEAK:
            key = (f.type, f.extra.get("domain") if f.type == "url" else (f.extra.get("amount") if f.type == "amount" else f.norm))
            if key[1]:
                occ[key].setdefault(f.evidence_id, f)
    out = []
    for (t, v), where in occ.items():
        if len(where) < 2:
            continue
        fs = list(where.values())
        out.append({"attribute": (STRONG | WEAK)[t], "type": t, "value": fs[0].value if t != "url" else v,
                    "strength": "strong" if t in STRONG else "weak", "files": len(where),
                    "independent_sources": len({cl[e] for e in where}),
                    "occurrences": [{"evidence_id": f.evidence_id, "evidence_code": idx.ev(f.evidence_id).evidence_code,
                                     "filename": idx.ev(f.evidence_id).original_filename, "segment_id": f.segment_id,
                                     "locator": f.locator, "excerpt": f.excerpt} for f in fs]})
    out.sort(key=lambda x: (x["strength"] != "strong", -x["files"]))
    return out
