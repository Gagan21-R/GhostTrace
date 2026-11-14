"""Ten marketplace payment-dispute datasets (scenarios 21-30) for the Alternative Hypothesis Testing Engine.

The same story - Asha Menon pays Rs 50,000 for a laptop listed by "TechKart Deals" and the laptop does not arrive -
with one decisive difference per variant. Ground truth (written from the design, before running the engine) states
which hypothesis the evidence should favour, which must be contradicted, and which verification step must be proposed.
Scenario 30 also ships a stage-2 file (a bank confirmation) that is NOT in the manifest: uploading it later must make
the engine revise its leading explanation.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image

from .builder import AUTH_PASS, csv_file, eml, pdf, screenshot
from .trials import wa_export

SELLER_UPI, OTHER_UPI = "techkartdeals@okicici", "techkart.deals@okaxis"
LISTING_PHONE, OTHER_PHONE = "+91 98860 12345", "+91 70221 99876"


def _listing(d: Path):
    screenshot(d / "08_marketplace_listing.png", "BazaarHub - Seller profile", [
        ("TechKart Deals (verified seller)", 26, True, "#0f172a"), "Contact: " + LISTING_PHONE, "Payout UPI: " + SELLER_UPI,
        "Listing: Dell Inspiron 15 laptop - Rs 50,000"], bar="https://bazaarhub.in/seller/techkart-deals", width=900)
    return ("08_marketplace_listing.png", "marketplace listing", "Screenshot of the seller profile page taken by the buyer", ["listing"])


def _complaint(d: Path, extra=""):
    (d / "07_complaint.txt").write_text(
        "Statement of: Asha Menon\n\nI paid Rs 50,000 on 2 May 2026 for a laptop from TechKart Deals on BazaarHub. "
        "The laptop was never delivered. I believe the seller cheated me and this is a fraud." + (" " + extra if extra else "") + "\n",
        encoding="utf-8")
    return ("07_complaint.txt", "complaint", "Complaint statement recorded at the cyber cell on 9 May 2026", ["complaint"])


def _order(d: Path):
    pdf(d / "04_order_confirmation.pdf", "BazaarHub - Order confirmation", [
        "Order ID: BH-778120", "Order Date: 2026-05-02", "Item: Dell Inspiron 15 laptop", "Quantity: 1", "Amount: Rs 50,000.00",
        "Seller: TechKart Deals", "Payment mode: UPI (direct to seller)"])
    return ("04_order_confirmation.pdf", "order", "Downloaded from the buyer's BazaarHub account", ["order"])


def _receipt(d: Path, upi=SELLER_UPI, status="Payment successful", name="02_payment_screenshot.png", ref="612298845510"):
    screenshot(d / name, status, ["Paid to: TechKart Deals", f"UPI ID: {upi}", "Amount: Rs 50,000.00", f"UPI Ref No: {ref}",
                                  "Date: 02 May 2026, 11:42"], width=800, bg="#f0fdf4")
    return (name, "payment receipt", "Screenshot from the buyer's payment app", ["payment"])


def _bank(d: Path, rows):
    csv_file(d / "03_bank_statement.csv", [["Date", "Description", "Debit", "Credit", "UTR"]] + rows)
    return ("03_bank_statement.csv", "bank statement", "Statement downloaded from the buyer's bank", ["bank"])


DEBIT = ["2026-05-02 11:42 +05:30", f"UPI/{SELLER_UPI}/laptop", "50,000.00", "", "612298845510"]


def _chat(d: Path, rows):
    wa_export(d / "01_chat.txt", rows)
    return ("01_chat.txt", "chat", "WhatsApp export from the buyer's phone", ["chat"])


BASE_CHAT = [("01/05/2026", "18:00", "Asha Menon", "Hi, is the Dell Inspiron 15 still available?"),
             ("01/05/2026", "18:05", "TechKart Deals", "Yes madam, Rs 50,000, pay by UPI and we ship next day."),
             ("02/05/2026", "11:45", "Asha Menon", "Paid Rs 50,000 just now, ref 612298845510.")]


def build_s21(d):  # deliberate fraud
    return [_chat(d, BASE_CHAT + [("02/05/2026", "12:10", "TechKart Deals", "Ok received your payment, will ship tomorrow."),
                                  ("05/05/2026", "10:00", "Asha Menon", "No tracking yet? Please reply."),
                                  ("07/05/2026", "09:00", "Asha Menon", "Your number is switched off and you blocked me."),
                                  ("07/05/2026", "09:30", "TechKart Deals", "No refund. Pay extra Rs 5,000 courier charge if you want it.")]),
            _receipt(d), _bank(d, [DEBIT]), _order(d), _complaint(d), _listing(d)]


def build_s22(d):  # genuine delivery delay
    csv_file(d / "05_courier_tracking.csv", [["Date", "Status", "Location", "AWB", "Remarks"],
             ["2026-05-03 17:20 +05:30", "Picked up", "Pune", "SW77812045", "Shipper: TechKart Deals"],
             ["2026-05-04 09:10 +05:30", "In transit", "Pune hub", "SW77812045", ""],
             ["2026-05-06 15:00 +05:30", "Delayed", "Bengaluru hub", "SW77812045", "Held up due to weather; rescheduled"]])
    eml(d / "06_seller_email.eml", '"TechKart Deals" <support@techkartdeals.in>', '"Asha Menon" <asha.menon@inboxmail.com>',
        "Your order BH-778120", "Thu, 07 May 2026 10:00:00 +0530",
        "Dear Asha,\nWe received your payment. The courier reports a weather delay at the Bengaluru hub (AWB SW77812045). "
        "If it is not delivered by 12 May, a full refund will be processed.\nTechKart Deals", auth=AUTH_PASS.format(d="techkartdeals.in"))
    return [_chat(d, BASE_CHAT + [("02/05/2026", "12:10", "TechKart Deals", "Ok received your payment, shipping tomorrow."),
                                  ("03/05/2026", "18:00", "TechKart Deals", "Shipped, AWB SW77812045.")]),
            _receipt(d), _bank(d, [DEBIT]), _order(d),
            ("05_courier_tracking.csv", "courier tracking", "Courier website tracking export", ["courier"]),
            ("06_seller_email.eml", "email", "Buyer's mailbox export", ["email"]), _complaint(d), _listing(d)]


def build_s23(d):  # incorrect payment destination
    eml(d / "06_seller_email.eml", '"TechKart Deals" <support@techkartdeals.in>', '"Asha Menon" <asha.menon@inboxmail.com>',
        "Order BH-778120 payment", "Tue, 05 May 2026 10:00:00 +0530",
        f"Dear Asha,\nWe have not received any payment for this order. Our only UPI ID is {SELLER_UPI}. Your receipt shows {OTHER_UPI}, "
        "which is not ours. Please check with your bank.\nTechKart Deals", auth=AUTH_PASS.format(d="techkartdeals.in"))
    return [_chat(d, BASE_CHAT[:2] + [("01/05/2026", "18:06", "TechKart Deals", f"Our UPI: {SELLER_UPI}"),
                                      ("02/05/2026", "11:45", "Asha Menon", "Paid Rs 50,000 just now."),
                                      ("03/05/2026", "10:00", "TechKart Deals", "Madam, not received any payment yet, please check.")]),
            _receipt(d, upi=OTHER_UPI), _bank(d, [["2026-05-02 11:42 +05:30", f"UPI/{OTHER_UPI}/laptop", "50,000.00", "", "612298845510"]]),
            _order(d), ("06_seller_email.eml", "email", "Buyer's mailbox export", ["email"]), _complaint(d), _listing(d)]


def build_s24(d):  # failed / reversed payment
    return [_chat(d, BASE_CHAT + [("02/05/2026", "13:00", "TechKart Deals", "Madam, payment not received at our end, it shows pending."),
                                  ("04/05/2026", "10:00", "Asha Menon", "My app still says pending.")]),
            _receipt(d, status="Payment pending"),
            _bank(d, [DEBIT, ["2026-05-04 09:15 +05:30", f"REVERSAL UPI/{SELLER_UPI}/laptop", "", "50,000.00", "612298845510"]]),
            _order(d), _complaint(d), _listing(d)]


def build_s25(d):  # seller impersonation
    eml(d / "06_seller_email.eml", '"TechKart Deals" <support@techkartdeals.in>', '"Asha Menon" <asha.menon@inboxmail.com>',
        "Re: laptop order", "Wed, 06 May 2026 10:00:00 +0530",
        f"Dear Asha,\nWe did not talk to you on WhatsApp. {OTHER_PHONE} is not our number and {OTHER_UPI} is not our account. "
        "Someone is impersonating us. We never received your payment.\nTechKart Deals", auth=AUTH_PASS.format(d="techkartdeals.in"))
    wa_export(d / "01_chat.txt", [("01/05/2026", "18:00", "Asha Menon", "Hi, is the Dell Inspiron 15 still available?"),
                                  ("01/05/2026", "18:05", "TechKart Deals", f"Yes. This is our new number {OTHER_PHONE}. Use this UPI: {OTHER_UPI}"),
                                  ("02/05/2026", "11:45", "Asha Menon", "Paid Rs 50,000 just now.")])
    return [("01_chat.txt", "chat", "WhatsApp export from the buyer's phone", ["chat"]), _receipt(d, upi=OTHER_UPI),
            _bank(d, [["2026-05-02 11:42 +05:30", f"UPI/{OTHER_UPI}/laptop", "50,000.00", "", "612298845510"]]), _order(d),
            ("06_seller_email.eml", "email", "Buyer's mailbox export", ["email"]), _complaint(d), _listing(d)]


def build_s26(d):  # conflicting timestamps
    files = build_s21(d)
    screenshot(d / "02_payment_screenshot.png", "Payment successful", ["Paid to: TechKart Deals", f"UPI ID: {SELLER_UPI}", "Amount: Rs 50,000.00",
               "Paid on 03 May 2026, 19:05  UPI Ref No: 612298845510"], width=900, bg="#f0fdf4")
    return files


def build_s27(d):  # missing transaction evidence
    return [_chat(d, BASE_CHAT + [("02/05/2026", "12:10", "TechKart Deals", "Ok."), ("07/05/2026", "09:00", "Asha Menon", "You stopped replying.")]),
            _receipt(d), _complaint(d), _listing(d)]


def build_s28(d):  # duplicated / misleading screenshots
    files = build_s21(d)
    (d / "02b_payment_screenshot_copy.png").write_bytes((d / "02_payment_screenshot.png").read_bytes())
    Image.open(d / "02_payment_screenshot.png").convert("RGB").save(d / "02c_payment_forwarded.jpg", "JPEG", quality=75)
    files += [("02b_payment_screenshot_copy.png", "payment receipt", "Same screenshot re-sent by the buyer", ["payment", "copy"]),
              ("02c_payment_forwarded.jpg", "payment receipt", "Screenshot forwarded through a messaging app", ["payment", "copy"])]
    return files


def build_s29(d):  # insufficient evidence, several explanations plausible
    return [_chat(d, [("01/05/2026", "18:00", "Asha Menon", "Hi, is the laptop available?"), ("01/05/2026", "18:05", "TechKart Deals", "Yes, Rs 50,000."),
                      ("06/05/2026", "10:00", "Asha Menon", "Where is my laptop?")]), _complaint(d)]


def build_s30(d):  # stage 1 looks like fraud; stage-2 bank confirmation shows the payment was reversed
    files = [_chat(d, BASE_CHAT + [("04/05/2026", "10:00", "Asha Menon", "No reply from you for two days."),
                                   ("06/05/2026", "10:00", "Asha Menon", "You are not reachable, I will complain.")]),
             _receipt(d), _bank(d, [DEBIT]), _order(d), _complaint(d), _listing(d)]
    pdf(d / "stage2_bank_confirmation.pdf", "Bank of Deccan - Transaction status confirmation", [
        "Customer: Asha Menon", "UTR: 612298845510", "Amount: Rs 50,000.00", "Beneficiary: " + SELLER_UPI,
        "Status: FAILED at beneficiary bank - not credited to beneficiary", "Reversal: amount reversed and credited back to remitter on 2026-05-08",
        "This letter is issued at the customer's request."])
    return files


BUILDERS = {f"s{n}-{k}": fn for n, k, fn in [
    (21, "market-deliberate-fraud", build_s21), (22, "market-delivery-delay", build_s22), (23, "market-wrong-destination", build_s23),
    (24, "market-reversed-payment", build_s24), (25, "market-seller-impersonation", build_s25), (26, "market-conflicting-times", build_s26),
    (27, "market-missing-transaction", build_s27), (28, "market-duplicate-screenshots", build_s28), (29, "market-insufficient", build_s29),
    (30, "market-new-evidence", build_s30)]}


def F(i, crit, t, desc, **match):
    return {"id": f"F{i}", "critical": crit, "type": t, "description": desc, "match": match}


def _gt(findings, expected="HOLD"):
    from .trial_defs import _gt as base
    return base(findings, expected)


BRIEF = ("Asha Menon paid Rs 50,000 for a laptop listed by TechKart Deals on BazaarHub and did not receive it. She alleges fraud. "
         "Generate and test competing explanations; do not assume the allegation is correct.")
DEFS = {
    "s21-market-deliberate-fraud": ("Marketplace dispute: deliberate fraud", "Payment reached the seller's own UPI; seller acknowledged it, then blocked the buyer and refused a refund.", "Medium", [
        F(1, True, "leading_hypothesis", "Deliberate fraud fits the evidence best", hids=["H1"]),
        F(2, True, "hypothesis_label", "Payment-failure explanation contradicted by the bank debit", hid="H4", labels=["contradicted", "weakened"]),
        F(3, False, "hypothesis_label", "Delivery-delay explanation weakened (no shipment, seller unreachable)", hid="H2", labels=["weakened", "contradicted", "inconclusive"]),
        F(4, True, "review_passed", "Independent reviewer finds every citation grounded")]),
    "s22-market-delivery-delay": ("Marketplace dispute: genuine delivery delay", "Courier scans and a weather delay; the seller offers a refund.", "Medium", [
        F(1, True, "leading_hypothesis", "Delivery delay fits the evidence best", hids=["H2"]),
        F(2, True, "hypothesis_label", "Fraud explanation contradicted by courier records", hid="H1", labels=["contradicted", "weakened"]),
        F(3, True, "review_passed", "Independent reviewer finds every citation grounded")]),
    "s23-market-wrong-destination": ("Marketplace dispute: incorrect payment destination", "The buyer paid a UPI ID that is not the seller's.", "Hard", [
        F(1, True, "leading_hypothesis", "Wrong-destination explanation fits best", hids=["H3", "H5"]),
        F(2, True, "hypothesis_label", "Wrong destination supported", hid="H3", labels=["strongly_supported", "partially_supported"]),
        F(3, False, "next_evidence", "Planner asks for the beneficiary account's KYC", id="beneficiary_kyc")]),
    "s24-market-reversed-payment": ("Marketplace dispute: reversed payment", "The bank statement shows the debit reversed two days later.", "Medium", [
        F(1, True, "leading_hypothesis", "Payment-processing explanation fits best", hids=["H4"]),
        F(2, True, "hypothesis_label", "Fraud explanation contradicted by the reversal", hid="H1", labels=["contradicted", "weakened"])]),
    "s25-market-seller-impersonation": ("Marketplace dispute: seller impersonation", "A different number asked for payment to a different UPI; the real seller disowns it.", "Hard", [
        F(1, True, "leading_hypothesis", "Impersonation fits best", hids=["H5", "H3"]),
        F(2, True, "hypothesis_label", "Impersonation supported", hid="H5", labels=["strongly_supported", "partially_supported"]),
        F(3, True, "hypothesis_label", "Seller fraud contradicted by the genuine seller's records", hid="H1", labels=["contradicted", "weakened", "inconclusive"])]),
    "s26-market-conflicting-times": ("Marketplace dispute: conflicting timestamps", "The receipt shows a different payment date than the bank.", "Hard", [
        F(1, True, "contradiction", "Receipt and bank disagree on the payment date", category="date_conflict"),
        F(2, False, "leading_hypothesis", "Fraud still fits best on the remaining evidence", hids=["H1"])]),
    "s27-market-missing-transaction": ("Marketplace dispute: missing transaction evidence", "Only a chat, a receipt screenshot and a complaint; no bank record.", "Medium", [
        F(1, True, "hypothesis_not_strong", "No hypothesis is strongly supported without a bank record"),
        F(2, True, "next_evidence", "Planner asks for the bank's transaction status", id="bank_status")]),
    "s28-market-duplicate-screenshots": ("Marketplace dispute: duplicated screenshots", "Three copies of one receipt must count as one source.", "Medium", [
        F(1, True, "dependency", "Receipt copy recognised as a duplicate", files=["02_payment_screenshot.png", "02b_payment_screenshot_copy.png"], relations=["duplicate"]),
        F(2, True, "leading_hypothesis", "Fraud fits best", hids=["H1"])]),
    "s29-market-insufficient": ("Marketplace dispute: insufficient evidence", "A vague chat and a complaint; several explanations remain open.", "Control", [
        F(1, True, "hypothesis_not_strong", "No hypothesis is strongly supported"),
        F(2, True, "review_passed", "Reviewer flags no grounding problems")]),
    "s30-market-new-evidence": ("Marketplace dispute: new evidence changes the assessment", "Stage 1 looks like fraud; a later bank confirmation shows the payment was reversed.", "Hard", [
        F(1, True, "leading_hypothesis", "Stage 1: fraud fits the evidence best", hids=["H1"]),
        F(2, True, "next_evidence", "Planner asks for the bank's transaction status", id="bank_status")]),
}
MARKET_DEFS = {sid: {"number": 21 + i, "title": t, "difficulty": diff, "case_type": "commercial_dispute", "summary": summ, "briefing": BRIEF,
                     "questions": ["Where did the money go?", "Was anything shipped?", "Who was the buyer dealing with?", "Which record would settle it?"],
                     "planted_facts": [summ], "planted_inconsistencies": [], "ground_truth": _gt(f)}
               for i, (sid, (t, summ, diff, f)) in enumerate(DEFS.items())}
