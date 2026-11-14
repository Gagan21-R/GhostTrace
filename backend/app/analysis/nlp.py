"""Deterministic language utilities: identifier patterns, date parsing, event classification
and claim detection. Rule-based so results are reproducible and auditable."""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation

from dateutil import parser as dparser

# ------------------------------------------------------------------ identifier patterns
EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
URL_RE = re.compile(r"\b(?:https?://|www\.)[^\s\"'<>()\]]+", re.I)
BARE_DOMAIN_RE = re.compile(r"\b(?:[a-z0-9-]+\.)+(?:com|net|org|in|io|co|info|xyz|top|site|online|support|live|app|biz|me|ru|cn)\b(?:/[^\s]*)?", re.I)
PHONE_RE = re.compile(r"(?<![\w/.-])(?:\+\d{1,3}[\s-]?)?(?:\(?\d{2,5}\)?[\s-]?)?\d{3,5}[\s-]?\d{4,5}(?![\w/-]|\.\d)")
IPV4_RE = re.compile(r"\b(?:25[0-5]|2[0-4]\d|1?\d?\d)(?:\.(?:25[0-5]|2[0-4]\d|1?\d?\d)){3}\b")
HANDLE_RE = re.compile(r"(?<![\w@.])@([A-Za-z0-9_.]{3,30})\b")
MONEY_RE = re.compile(
    r"(?P<cur>₹|Rs\.?|INR|USD|\$|EUR|€|GBP|£)\s?(?P<amt>\d{1,3}(?:,\d{2,3})*(?:\.\d{1,2})?|\d+(?:\.\d{1,2})?)"
    r"|(?P<amt2>\d{1,3}(?:,\d{2,3})*(?:\.\d{1,2})?|\d+(?:\.\d{1,2})?)\s?(?P<cur2>INR|USD|EUR|GBP|rupees)\b", re.I)
TXN_RE = re.compile(r"\b(?:UTR|RRN|TXN|Txn|Transaction\s*(?:ID|Ref(?:erence)?|No\.?)|Payment\s*(?:ID|Ref(?:erence)?)|"
                    r"Ref(?:erence)?\s*(?:No\.?|ID|#)|UPI\s*Ref(?:\.|erence)?\s*(?:No\.?)?)\s*[:#.\-]?\s*([A-Z0-9][A-Z0-9-]{5,23})\b", re.I)
ORDER_RE = re.compile(r"\bOrder\s*(?:ID|No\.?|Number|#|Ref)?\s*[:#\-]?\s*(#?[A-Z]{0,5}-?\d{4,}[A-Z0-9-]*)\b", re.I)
INVOICE_RE = re.compile(r"\bInvoice\s*(?:No\.?|Number|#|ID)\s*[:#\-]?\s*([A-Z0-9][A-Z0-9/-]{3,20})\b", re.I)
TRACKING_RE = re.compile(r"\b(?:AWB|Tracking\s*(?:No\.?|Number|ID|#)?|Consignment\s*(?:No\.?)?)\s*[:#\-]?\s*([A-Z0-9]{8,20})\b", re.I)
ACCOUNT_RE = re.compile(r"\b(?:A/c|Acct|Account)\s*(?:No\.?|Number|#|ending(?: in)?)?\s*[:#\-]?\s*([X*x]{0,12}\d{3,18})\b")
TICKET_RE = re.compile(r"\b(?:Ticket|Case|Complaint|Incident|Request)\s*(?:ID|No\.?|#|Ref)\s*[:#\-]?\s*([A-Z]{1,6}-?\d{3,10})\b", re.I)
QTY_RE = re.compile(r"\b(?:Qty|Quantity|Units?|Count)\s*(?:ordered|delivered|received|shipped)?\s*[:=\-]?\s*(\d{1,6})\b", re.I)
QTY_UNITS_RE = re.compile(r"\b(\d{1,6})\s*(?:units|pcs|pieces|items|nos|bottles)\b", re.I)
DEVICE_RE = re.compile(r"\b((?:Windows|Android|iPhone|iPad|iOS|macOS|Mac OS X|Linux|Ubuntu|ChromeOS)[^,;\n|]{0,40})", re.I)

DATE_PATTERNS = [
    r"\b\d{4}-\d{2}-\d{2}(?:[T ]\d{1,2}:\d{2}(?::\d{2})?(?:\.\d+)?)?(?:\s?(?:Z|[+-]\d{2}:?\d{2}|UTC|IST|GMT))?\b",
    r"\b\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}(?:,?\s+\d{1,2}:\d{2}(?::\d{2})?(?:\s?[APap][Mm])?)?(?:\s?(?:IST|UTC|GMT))?\b",
    r"\b\d{1,2}(?:st|nd|rd|th)?\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?,?\s+\d{4}"
    r"(?:,?\s+(?:at\s+)?\d{1,2}:\d{2}(?::\d{2})?(?:\s?[APap][Mm])?)?(?:\s?(?:IST|UTC|GMT|[+-]\d{4}))?",
    r"\b(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)[a-z]*,?\s+\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}\s+\d{1,2}:\d{2}(?::\d{2})?(?:\s?[+-]\d{4})?",
    r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4}"
    r"(?:,?\s+(?:at\s+)?\d{1,2}:\d{2}(?::\d{2})?(?:\s?[APap][Mm])?)?(?:\s?(?:IST|UTC|GMT))?",
]
DATE_RE = re.compile("|".join(f"(?:{p})" for p in DATE_PATTERNS), re.I)
TZINFOS = {"IST": 19800, "UTC": 0, "GMT": 0}

RELATIVE_RE = re.compile(r"\b(yesterday|today|tonight|last night|this morning|(\d+|two|three|four|five)\s+days?\s+(ago|later))\b", re.I)
_NUM = {"two": 2, "three": 3, "four": 4, "five": 5}


def normalize_phone(raw: str) -> str | None:
    digits = re.sub(r"\D", "", raw)
    if len(digits) < 8 or len(digits) > 15:
        return None
    if len(set(digits)) <= 2:
        return None
    return digits[-10:] if len(digits) >= 10 else digits


def normalize_amount(cur: str | None, amt: str) -> tuple[str, Decimal] | None:
    try:
        val = Decimal(amt.replace(",", ""))
    except InvalidOperation:
        return None
    c = (cur or "").upper().strip(". ")
    c = {"₹": "INR", "RS": "INR", "RUPEES": "INR", "$": "USD", "€": "EUR", "£": "GBP"}.get(c, c or "UNK")
    return c, val


def find_amounts(text: str) -> list[dict]:
    out = []
    for m in MONEY_RE.finditer(text):
        cur = m.group("cur") or m.group("cur2")
        amt = m.group("amt") or m.group("amt2")
        n = normalize_amount(cur, amt)
        if n and n[1] > 0:
            out.append({"raw": m.group(0).strip(), "currency": n[0], "value": str(n[1].quantize(Decimal("0.01"))),
                        "start": m.start()})
    return out


def domain_of(url: str) -> str:
    u = re.sub(r"^https?://", "", url.strip().lower())
    u = u.split("/")[0].split("?")[0].split(":")[0]
    return u[4:] if u.startswith("www.") else u


def tz_from_offset(spec: str | None):
    """'+05:30' / '+0530' / 'UTC' -> tzinfo (None if invalid)."""
    if not spec or spec.upper() in ("UTC", "Z", "GMT"):
        return timezone.utc
    m = re.fullmatch(r"([+-])(\d{2}):?(\d{2})", spec.strip())
    if not m:
        return None
    delta = timedelta(hours=int(m.group(2)), minutes=int(m.group(3)))
    return timezone(delta if m.group(1) == "+" else -delta)


def display_dt(dt: datetime | None, info: dict | None = None) -> str:
    """Render a stored (UTC) timestamp in the timezone the source reported, so investigators read
    the same clock time as the record."""
    if dt is None:
        return "unknown time"
    if (info or {}).get("display_offset") == "unknown":
        return dt.strftime("%d %b %Y %H:%M") + " (timezone unknown)"
    tz = tz_from_offset((info or {}).get("display_offset"))
    if tz is not None:
        return dt.astimezone(tz).strftime("%d %b %Y %H:%M ") + (info or {}).get("display_offset", "UTC")
    return dt.strftime("%d %b %Y %H:%M UTC")


def parse_datetime(raw: str, anchor: datetime | None = None, default_tz: str | None = None) -> tuple[datetime | None, dict]:
    """Parse a timestamp string. Returns (dt, info) where info notes precision/ambiguity/tz.

    Day-first is assumed for numeric dates (dd/mm/yyyy) and the ambiguity is recorded when
    both day and month are <= 12. Times without a timezone are kept as reported and flagged.
    """
    info: dict = {"raw": raw}
    s = raw.strip()
    if not s:
        return None, info
    m = re.match(r"^(\d{1,2})[/.-](\d{1,2})[/.-](\d{2,4})", s)
    if m and int(m.group(1)) <= 12 and int(m.group(2)) <= 12 and m.group(1) != m.group(2):
        info["ambiguous_day_month"] = True
    try:
        dt = dparser.parse(s, dayfirst=not re.match(r"^\d{4}-", s), fuzzy=True, tzinfos=TZINFOS,
                           default=datetime(1900, 1, 1, 0, 0, 0))
    except (ValueError, OverflowError):
        return None, info
    if dt.year == 1900:
        return None, info
    info["has_time"] = bool(re.search(r"\d{1,2}:\d{2}", s))
    info["precision"] = "minute" if info["has_time"] else "day"
    if dt.tzinfo is None and (default_tz or "").lower() == "unknown":
        info["timezone"] = "unknown - not stated in source and no case default; times compared as wall-clock"
        info["tz_assumed"] = True
        info["tz_unknown"] = True
        info["display_offset"] = "unknown"
        return dt.replace(tzinfo=timezone.utc), info
    if dt.tzinfo is None:
        tz = tz_from_offset(default_tz) or timezone.utc
        off = default_tz if tz_from_offset(default_tz) else "UTC"
        info["timezone"] = f"not stated in source - case default {off} applied"
        info["tz_assumed"] = True
        info["display_offset"] = off
        dt = dt.replace(tzinfo=tz).astimezone(timezone.utc)
    else:
        off = dt.strftime("%z")
        info["timezone"] = off
        info["display_offset"] = f"{off[:3]}:{off[3:]}" if len(off) == 5 else "UTC"
        dt = dt.astimezone(timezone.utc)
    return dt, info


def find_dates(text: str) -> list[tuple[str, int]]:
    return [(m.group(0), m.start()) for m in DATE_RE.finditer(text)]


def resolve_relative(text: str, anchor: datetime) -> tuple[datetime, str] | None:
    m = RELATIVE_RE.search(text)
    if not m:
        return None
    w = m.group(1).lower()
    if w in ("today", "tonight", "this morning"):
        return anchor, w
    if w in ("yesterday", "last night"):
        return anchor - timedelta(days=1), w
    n = m.group(2).lower()
    days = int(n) if n.isdigit() else _NUM.get(n, 0)
    return (anchor - timedelta(days=days)) if m.group(3).lower() == "ago" else (anchor + timedelta(days=days)), w


# ------------------------------------------------------------------ event classification
EVENT_LEXICON: list[tuple[str, re.Pattern]] = [
    ("password_reset", re.compile(r"password (?:reset|was reset|was changed|changed|change request)|reset (?:your|the|my) password|change (?:my|the|your) password", re.I)),
    ("recovery_change", re.compile(r"recovery (?:email|phone|address|number)|account recovery", re.I)),
    ("mfa", re.compile(r"\b(?:2fa|two-factor|otp|one-time (?:password|code)|verification code)\b", re.I)),
    ("login", re.compile(r"\b(?:new )?(?:login|log-in|log in|sign-in|sign in|signed in|logged in|session (?:started|created))\b", re.I)),
    ("security_alert", re.compile(r"security alert|suspicious (?:activity|sign|login)|unusual (?:activity|sign)", re.I)),
    ("complaint", re.compile(r"\b(?:complaint|grievance|whistleblow\w*|report(?:ed|ing)? (?:misconduct|concerns?|fraud|irregularit))", re.I)),
    ("refund", re.compile(r"\brefund", re.I)),
    ("payment", re.compile(r"\b(?:paid|payment|transferred|debited|credited|upi|remitted|sent (?:you )?(?:₹|rs|inr|\$))", re.I)),
    ("delivery", re.compile(r"\bdelivered\b|delivery (?:confirmed|completed|attempt)|proof of delivery", re.I)),
    ("shipment", re.compile(r"\b(?:shipped|dispatched|in transit|out for delivery|picked up|manifested)\b", re.I)),
    ("invoice", re.compile(r"\binvoice\b", re.I)),
    ("order", re.compile(r"\border (?:placed|confirmed|received)|\bpurchase order\b|order confirmation", re.I)),
    ("access_change", re.compile(r"\baccess (?:revoked|removed|downgraded|restricted|changed|granted|disabled)|"
                                 r"permission(?:s)? (?:revoked|removed|changed|downgraded)|role (?:changed|downgraded)|"
                                 r"(?:revoked|removed|disabled) .{0,30}access|"
                                 r"access .{0,40}(?:was|were|has been|had been) (?:changed|revoked|removed|downgraded|restricted)", re.I)),
    ("warning", re.compile(r"\b(?:written warning|performance improvement plan|\bpip\b|disciplinary|show[- ]cause)", re.I)),
    ("meeting", re.compile(r"\bmeeting\b|\binvite(?:d)?\b.{0,20}\bcall\b|calendar invite", re.I)),
    ("click", re.compile(r"\bclicked\b|\bopened the link\b|\bvisited\b", re.I)),
    ("post", re.compile(r"\b(?:posted|tweeted|commented|shared a post|published)\b", re.I)),
    ("deletion", re.compile(r"\b(?:deleted|removed the post|taken down|unsent)\b", re.I)),
    ("threat", re.compile(r"\b(?:you will regret|watch your back|i will (?:leak|expose|post)|or else)\b", re.I)),
    ("collection", re.compile(r"\b(?:screenshot (?:taken|captured)|captured|archived|downloaded|exported)\b", re.I)),
]


def classify_event(text: str) -> str | None:
    """Return the event type whose cue appears first in the text (the sentence's main act);
    lexicon order breaks ties. E.g. "access was changed ... before your complaint" -> access_change,
    "complaint - irregular vendor payments" -> complaint."""
    best = None
    for rank, (etype, rx) in enumerate(EVENT_LEXICON):
        m = rx.search(text)
        if m and (best is None or (m.start(), rank) < best[0]):
            best = ((m.start(), rank), etype)
    return best[1] if best else None


NEGATION_RE = re.compile(r"\b(?:never|did not|didn't|do not|don't|have not|haven't|was not|wasn't|no one|not)\b", re.I)
FIRST_PERSON_RE = re.compile(r"\b(?:I|we|my|me)\b")


def claims_in(text: str) -> list[dict]:
    """Detect first-person assertions about event types (e.g. "I never requested a password reset")."""
    out = []
    for sent in re.split(r"(?<=[.!?])\s+|\n", text):
        if not FIRST_PERSON_RE.search(sent):
            continue
        et = classify_event(sent)
        if not et:
            continue
        polarity = "negative" if NEGATION_RE.search(sent) else "positive"
        out.append({"sentence": sent.strip(), "event_type": et, "polarity": polarity})
    return out


SUSPICIOUS_TLDS = {"xyz", "top", "site", "online", "support", "live", "info", "biz", "ru", "cn", "click", "help"}
KNOWN_BRAND_DOMAINS = {"paypal.com", "amazon.com", "amazon.in", "netflix.com", "google.com", "microsoft.com",
                        "apple.com", "hdfcbank.com", "icicibank.com", "onlinesbi.sbi", "sbi.co.in", "axisbank.com",
                        "paytm.com", "phonepe.com", "flipkart.com", "accounts.google.com"}
BRAND_HINTS = ["paypal", "amazon", "netflix", "google", "microsoft", "apple", "hdfc", "icici", "sbi", "axis", "paytm",
               "phonepe", "flipkart", "secure", "verify", "account", "login", "update", "kyc", "bank", "support"]


def url_risk(url: str, trusted_domains: set[str] | None = None) -> dict:
    """Deterministic URL risk indicators. Indicators are signals, not proof of maliciousness."""
    d = domain_of(url)
    tld = d.rsplit(".", 1)[-1] if "." in d else ""
    reasons = []
    if tld in SUSPICIOUS_TLDS:
        reasons.append(f"uses a TLD frequently abused in phishing (.{tld})")
    if re.search(r"\d{1,3}(?:\.\d{1,3}){3}", d):
        reasons.append("host is a raw IP address")
    if d.count("-") >= 2:
        reasons.append("hyphen-heavy hostname")
    brands = [b for b in BRAND_HINTS if b in d]
    if brands and trusted_domains is not None and d not in trusted_domains:
        reasons.append(f"contains brand/lure keywords ({', '.join(brands[:3])}) but is not a known domain of that brand")
    if "@" in url:
        reasons.append("URL contains '@' (credential-style obfuscation)")
    if d in {"bit.ly", "tinyurl.com", "t.co", "rb.gy", "cutt.ly", "is.gd", "ow.ly"}:
        reasons.append("URL shortener hides destination")
    return {"domain": d, "indicators": reasons, "suspicious": len(reasons) >= 1}


def levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]
