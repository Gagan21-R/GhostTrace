"""Unit tests for the deterministic primitives the investigation relies on."""
from datetime import timezone

from app.analysis import nlp
from app.services.intake import inspect_upload, sha256_bytes


def test_sha256_known_vector():
    assert sha256_bytes(b"abc") == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


def test_intake_rejects_mismatched_signature():
    assert not inspect_upload("x.png", b"not a png", 10_000).ok
    assert not inspect_upload("x.pdf", b"hello", 10_000).ok
    assert not inspect_upload("x.exe", b"MZ....", 10_000).ok
    assert inspect_upload("chat.json", b'{"messages": []}', 10_000).detected_type == "chat"
    assert not inspect_upload("big.txt", b"a" * 2000, 1000).ok


def test_whatsapp_detection():
    data = b"10/03/2026, 09:31 - A: hi\n10/03/2026, 09:32 - B: yo\n10/03/2026, 09:33 - A: ok\n"
    assert inspect_upload("c.txt", data, 10_000).detected_type == "chat"


def test_datetime_provenance_and_timezones():
    dt, info = nlp.parse_datetime("2026-03-14 02:14:51+05:30")
    assert dt.tzinfo == timezone.utc and dt.hour == 20 and info["display_offset"] == "+05:30"
    dt2, info2 = nlp.parse_datetime("10/03/2026, 09:31", default_tz="+05:30")
    assert info2["tz_assumed"] and info2["ambiguous_day_month"] and dt2.hour == 4
    _, info3 = nlp.parse_datetime("11 March 2026")
    assert info3["precision"] == "day"
    assert nlp.parse_datetime("no date here")[0] is None


def test_url_risk_indicators():
    assert nlp.url_risk("https://hdfc-secure-kyc.xyz/verify", nlp.KNOWN_BRAND_DOMAINS)["suspicious"]
    assert not nlp.url_risk("https://www.flipkart.com/offers", nlp.KNOWN_BRAND_DOMAINS)["suspicious"]
    assert nlp.url_risk("https://bit.ly/abc", nlp.KNOWN_BRAND_DOMAINS)["suspicious"]


def test_event_classification_prefers_first_cue():
    assert nlp.classify_event("your access was changed on 3 March before your complaint was raised") == "access_change"
    assert nlp.classify_event("Confidential complaint - irregular vendor payments") == "complaint"
    assert nlp.classify_event("Rs.24999.00 debited from A/c XX4821") == "payment"


def test_claims_and_negation():
    c = nlp.claims_in("I never shared any verification code with anyone.")
    assert c and c[0]["polarity"] == "negative" and c[0]["event_type"] == "mfa"


def test_phone_and_amount_extraction():
    phones = [m.group(0) for m in nlp.PHONE_RE.finditer("Call +91 98765 43210. Thanks")]
    assert phones == ["+91 98765 43210"]
    amts = nlp.find_amounts("Paid ₹24,999 and Rs 1,250.50")
    assert [a["value"] for a in amts] == ["24999.00", "1250.50"]
    assert nlp.levenshtein("407215583921", "407215538921") == 2
