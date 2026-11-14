"""Definitions and ground truth for trial scenarios 7-20 (datasets in ``trials.py``).

Ground truth was written from the dataset design, before running the engine. Finding types used here in
addition to the original ones: ``classification`` (Naive Bayes label on a file), ``authenticity`` (verdict
of the message-authenticity agent), ``authenticity_indicator`` (one indicator it must raise), ``event``
(a timeline event type) and ``integrity_check`` (an integrity indicator on a file).
"""
from __future__ import annotations

NO_ATTRIBUTION = {"type": "text", "pattern": r"\b(?:is|was) the (?:attacker|hacker|perpetrator|culprit)\b",
                  "description": "No attribution of identity"}


def _gt(findings, expected="HOLD", forbidden=None, entities=None):
    return {"expected_outcome": expected, "findings": findings, "allowed_dependencies": [{"relation": "shared_source"},
            {"relation": "near_duplicate"}, {"relation": "derived"}], "allowed_contradictions": [], "forbidden": [NO_ATTRIBUTION] + (forbidden or []),
            "scored_entities": entities or {"types": [], "values": []}, "expected_events": [], "irrelevant_records": [],
            "ambiguous_records": [], "verification": {"max_unsupported_claim_rate": 0.0}, "timeline_sequence": [], "ocr_expect": {}, "asr_expect": {}}


def F(i, crit, t, desc, **match):
    return {"id": f"F{i}", "critical": crit, "type": t, "description": desc, "match": match}


TRIALS = {
    "s7-whatsapp-impersonation": {
        "number": 7, "title": "Impersonation: harassment sent from a hijacked WhatsApp", "difficulty": "Hard", "case_type": "harassment",
        "summary": "Threats appear to come from Rohan's WhatsApp, but a web session was linked 43 minutes earlier while he was at a hackathon.",
        "briefing": ("Sneha Kulkarni complains that her classmate Rohan Verma threatened her and demanded Rs 5000 on WhatsApp on 18 March "
                     "2026, and submits a screenshot. Rohan says someone else was using his account. Test whether the screenshot is "
                     "genuine, whether the messages were really sent from his account, and whether the records indicate someone else "
                     "was using it. Do not decide who typed the messages."),
        "questions": ["Is the screenshot consistent with both phones' chat exports?", "Was the account accessed from a new device before the messages?",
                      "Where was the account holder when they were sent?", "Do the messages read like his other messages?"],
        "planted_facts": ["WhatsApp Web linked at 21:58 from 103.211.54.90", "Messages at 22:41 and 22:42 logged as sent from WhatsApp Web",
                          "Rohan checked in at a hackathon at 22:05 with his phone in a locker", "Disputed messages are formal; Rohan writes 'bro', 'da', 'u'"],
        "planted_inconsistencies": ["Account holder's own phone did not send the disputed messages although they appear in his export"],
        "ground_truth": _gt([
            F(1, True, "authenticity", "Verdict: possible impersonation (account used by a linked device)", verdict="possible_impersonation", file="01_complaint_screenshot.png"),
            F(2, True, "authenticity_indicator", "New linked device shortly before the messages", key="device_link"),
            F(3, True, "authenticity_indicator", "Messages logged as sent from WhatsApp Web", key="sent_from_linked_device"),
            F(4, False, "authenticity_indicator", "Account holder recorded at the hackathon at that time", key="alibi"),
            F(5, False, "authenticity_indicator", "Writing style differs from the holder's known messages", key="style_mismatch"),
            F(6, True, "classification", "Naive Bayes flags the threat/extortion messages", file="01_complaint_screenshot.png", labels=["harassment", "extortion"]),
            F(7, False, "entity", "Linked-session IP extracted", type="ip_address", value="103.211.54.90"),
            F(8, False, "event", "Device-link event on the timeline", event_type="device_link"),
        ], forbidden=[{"type": "authenticity", "verdict": "consistent_with_account_holder", "description": "Must not attribute to the holder"}]),
    },
    "s8-fabricated-screenshot": {
        "number": 8, "title": "Fabricated chat screenshot used in a complaint", "difficulty": "Hard", "case_type": "harassment",
        "summary": "A 'threat' screenshot made with a chat generator: the message is in neither phone's export and the clock is wrong.",
        "briefing": ("Karan Malhotra complains that his former business partner Priya Nair threatened him on WhatsApp on 5 April 2026 and "
                     "attaches a screenshot. Both phones' chat exports and Priya's account log were later produced. Test whether the "
                     "screenshot is supported by the source records."),
        "questions": ["Does the threatening message exist in either export?", "Does the screenshot's metadata or layout show editing?",
                      "Is the screenshot internally consistent (clock, times)?"],
        "planted_facts": ["JPEG metadata names 'FakeChat Maker 3.2'", "Status-bar clock 18:05 but last message 19:20",
                          "Threat line pasted into a low-quality base image", "Exports show Priya's real 19:11 message 'Got it, thanks'"],
        "planted_inconsistencies": ["Screenshot message absent from both exports"],
        "ground_truth": _gt([
            F(1, True, "authenticity", "Verdict: screenshot likely fabricated", verdict="likely_fabricated", file="01_threat_screenshot.jpg"),
            F(2, True, "authenticity_indicator", "Message not found in either phone's export", key="not_in_exports"),
            F(3, True, "authenticity_indicator", "Chat-generator software named in metadata", key="generator_or_editor"),
            F(4, False, "authenticity_indicator", "Status-bar clock earlier than messages", key="clock_before_messages"),
            F(5, False, "authenticity_indicator", "Error-level analysis shows an edited region", key="ela_anomaly"),
            F(6, False, "classification", "Threat text classified as harassment", file="01_threat_screenshot.jpg", labels=["harassment"]),
        ], forbidden=[{"type": "authenticity", "verdict": "consistent_with_account_holder", "description": "Fabricated message must not be attributed"}]),
    },
    "s9-claimed-hack-control": {
        "number": 9, "title": "Control: accused claims 'my phone was hacked'", "difficulty": "Control", "case_type": "harassment",
        "summary": "Threats are in both exports, sent from the holder's own phone, match his style, and he apologised next morning.",
        "briefing": ("Ayesha Khan complains about threats from Vikram Singh on 22 March 2026. Vikram says his phone was hacked. "
                     "The engine must not accept the hacking claim without indicators, and must not overstate the conclusion either."),
        "questions": ["Are the messages in the sender's own export?", "Is there any sign of a new device, SIM change or reset?",
                      "Do the messages match the sender's writing?", "What did the sender say afterwards?"],
        "planted_facts": ["Messages present in both exports", "Account log: primary phone only", "Apology at 10:05 next day"],
        "planted_inconsistencies": ["Statement says he was asleep; account log shows his primary phone sending at 23:15"],
        "ground_truth": _gt([
            F(1, True, "authenticity", "Verdict: consistent with the account holder", verdict="consistent_with_account_holder", file="01_screenshot.png"),
            F(2, True, "authenticity_indicator", "Message found in the sender's own export", key="in_export"),
            F(3, False, "authenticity_indicator", "No security events although logs exist", key="no_security_events"),
            F(4, False, "authenticity_indicator", "Sender acknowledged the message later", key="acknowledged"),
            F(5, True, "classification", "Threat classified as harassment", file="01_screenshot.png", labels=["harassment"]),
        ], expected="PASS", forbidden=[{"type": "authenticity", "verdict": "possible_impersonation", "description": "Unsupported hacking claim must not be accepted"}]),
    },
    "s10-sim-swap": {
        "number": 10, "title": "SIM swap and net-banking takeover", "difficulty": "Hard", "case_type": "account_compromise",
        "summary": "A SIM is re-issued at 01:09, an OTP arrives at 01:25 and Rs 1.85 lakh leaves the account by 01:36.",
        "briefing": "Deepak Joshi's phone lost network at night; two IMPS transfers followed. Reconstruct the sequence and the records still needed.",
        "questions": ["In what order did SIM, OTP, login and transfers happen?", "Which accounts received the money?", "Which records are missing?"],
        "planted_facts": ["SIM replacement 00:55 request, 01:09 activation", "OTP for new beneficiary 01:25", "Transfers 609201325511 and 609201338842"],
        "planted_inconsistencies": [],
        "ground_truth": _gt([
            F(1, True, "event", "SIM change on the timeline", event_type="sim_change"),
            F(2, True, "entity", "First transfer reference", type="transaction", value="609201325511"),
            F(3, False, "entity", "Second transfer reference", type="transaction", value="609201338842"),
            F(4, False, "event", "OTP / verification event", event_type="mfa"),
            F(5, False, "entity", "Victim phone number", type="phone", value="9008055667"),
        ]),
    },
    "s11-sextortion-email": {
        "number": 11, "title": "Sextortion email with a leaked password", "difficulty": "Easy", "case_type": "extortion",
        "summary": "A spoofed email quotes an old breached password and demands bitcoin.",
        "briefing": "Nitin Rao received two emails claiming a webcam recording. Classify the messages and identify what can and cannot be verified.",
        "questions": ["What kind of message is it?", "Is the sender verifiable?", "Where could the password have come from?"],
        "planted_facts": ["Sender spoofs the recipient's own address", "Password appears in a 2021 breach"], "planted_inconsistencies": [],
        "ground_truth": _gt([
            F(1, True, "classification", "Email classified as extortion", file="01_extortion_email.eml", labels=["extortion"]),
            F(2, False, "classification", "Follow-up classified as extortion", file="02_followup_email.eml", labels=["extortion"]),
            F(3, True, "entity", "Spoofed address extracted", type="email", value="nitin.rao@inboxmail.com"),
        ]),
    },
    "s12-task-job-scam": {
        "number": 12, "title": "Task-based part-time job scam", "difficulty": "Medium", "case_type": "fraud",
        "summary": "Escalating deposits (1,000 -> 5,000 -> 25,000) to 'unlock' a fake earnings dashboard.",
        "briefing": "Pooja Shetty paid three times to withdraw 'commission'. Link the chat, payments and dashboard.",
        "questions": ["Which UPI IDs received money?", "How did the demands escalate?", "Is the dashboard site suspicious?"],
        "planted_facts": ["Three UPI payees", "Dashboard on taskearn-pro.top"], "planted_inconsistencies": [],
        "ground_truth": _gt([
            F(1, True, "classification", "Recruiter messages classified as financial fraud", file="01_job_chat.txt", labels=["financial_fraud"]),
            F(2, True, "suspicious_url", "Dashboard domain flagged", domain="taskearn-pro.top"),
            F(3, False, "entity", "Third UPI payee", type="upi_id", value="secure.withdraw@paytm"),
            F(4, False, "entity", "Payment reference", type="transaction", value="412055443322"),
        ]),
    },
    "s13-business-email-compromise": {
        "number": 13, "title": "Business email compromise: changed bank details", "difficulty": "Medium", "case_type": "fraud",
        "summary": "A lookalike vendor domain asks finance to pay invoice INV-2207 to a new account.",
        "briefing": "BrightBuild paid Rs 8.4 lakh to a 'new' vendor account. Compare the request, the invoice and the real vendor's reply.",
        "questions": ["Which domain sent the change request?", "Do the invoice and payment accounts match?", "What does the real vendor say?"],
        "planted_facts": ["acme-supp1y.com vs acmesupply.in", "Reply-To to a gmail address"], "planted_inconsistencies": ["Account on invoice differs from account paid"],
        "ground_truth": _gt([
            F(1, True, "entity", "Lookalike domain extracted", type="website", value="acme-supp1y.com"),
            F(2, True, "classification", "Change request classified as financial fraud", file="01_vendor_bank_change.eml", labels=["financial_fraud"]),
            F(3, False, "entity", "Reply-To address", type="email", value="acme.accounts.desk@gmail.com"),
        ]),
    },
    "s14-loan-app-harassment": {
        "number": 14, "title": "Instant loan app harassment of contacts", "difficulty": "Medium", "case_type": "harassment",
        "summary": "Recovery agents threaten a borrower's contacts after the loan was already repaid.",
        "briefing": "Manoj Pillai repaid a loan but the app's recovery team messages his contacts. Classify the messages and link repayment.",
        "questions": ["What kind of messages are these?", "Was the loan repaid?", "Which permissions enabled contact harassment?"],
        "planted_facts": ["Repayment 12 Apr UTR 412233445566", "App has contacts permission"], "planted_inconsistencies": [],
        "ground_truth": _gt([
            F(1, True, "classification", "Recovery messages classified as extortion", file="02_recovery_chat.txt", labels=["extortion"]),
            F(2, False, "classification", "Messages to contact flagged", file="01_message_to_contact.png", labels=["extortion", "harassment"]),
            F(3, True, "entity", "Repayment reference", type="transaction", value="412233445566"),
        ]),
    },
    "s15-romance-investment-scam": {
        "number": 15, "title": "Romance-led crypto investment scam", "difficulty": "Medium", "case_type": "fraud",
        "summary": "An online friend steers the victim to a fake trading site; withdrawals need 'tax'.",
        "briefing": "Arvind Nair transferred Rs 5.5 lakh to a 'trading' platform. Link chat, site and payments.",
        "questions": ["Which site was used?", "Which transfers went out?", "What pattern do the messages follow?"],
        "planted_facts": ["globalcoin-xtrade.top", "Two IMPS transfers"], "planted_inconsistencies": [],
        "ground_truth": _gt([
            F(1, True, "suspicious_url", "Trading site flagged", domain="globalcoin-xtrade.top"),
            F(2, True, "classification", "Investment pitch classified as financial fraud", file="01_chat.txt", labels=["financial_fraud"]),
            F(3, False, "entity", "Transfer reference", type="transaction", value="606422334455"),
        ]),
    },
    "s16-fake-profile-stalking": {
        "number": 16, "title": "Stalking through multiple fake profiles", "difficulty": "Medium", "case_type": "harassment",
        "summary": "Two new accounts harass the victim; the platform shows both use the same recovery phone.",
        "briefing": "Neha Gupta is targeted by two accounts. Find what links them.",
        "questions": ["What links the two accounts?", "What kind of messages are they?"],
        "planted_facts": ["Shared recovery phone +91 97400 88112"], "planted_inconsistencies": [],
        "ground_truth": _gt([
            F(1, True, "entity", "Shared recovery phone extracted", type="phone", value="9740088112"),
            F(2, True, "classification", "Messages classified as harassment", file="01_dm_account1.png", labels=["harassment"]),
            F(3, False, "classification", "Second account's messages flagged", file="02_dm_account2.png", labels=["harassment"]),
            F(4, False, "entity", "Recovery email", type="email", value="shadow.nk@mailbox.in"),
        ]),
    },
    "s17-insider-exfiltration": {
        "number": 17, "title": "Insider data exfiltration before resignation", "difficulty": "Medium", "case_type": "corporate",
        "summary": "Client files copied to USB and mailed to a personal address the day before resignation.",
        "briefing": "Reconstruct what left the company and when. Note what the logs cannot show (e.g., who sat at the laptop).",
        "questions": ["What was copied, where, when?", "Was data emailed outside?", "What is still unknown?"],
        "planted_facts": ["USB copy 18:46", "Mail to amitk.personal@gmail.com 19:05", "Resignation next day"], "planted_inconsistencies": [],
        "ground_truth": _gt([
            F(1, True, "entity", "Personal email extracted", type="email", value="amitk.personal@gmail.com"),
            F(2, False, "entity", "Work email extracted", type="email", value="amit.kapoor@finedge.in"),
        ]),
    },
    "s18-marketplace-qr-scam": {
        "number": 18, "title": "Marketplace 'scan to receive' QR scam", "difficulty": "Easy", "case_type": "fraud",
        "summary": "A fake buyer sends a QR code that debits the seller instead of paying her.",
        "briefing": "Lakshmi Rao scanned a QR to 'receive' Rs 15,000 and lost the amount. Link chat, QR and debit.",
        "questions": ["Which UPI ID received the money?", "What tactic was used?"],
        "planted_facts": ["armyhelp.desk@okhdfcbank"], "planted_inconsistencies": [],
        "ground_truth": _gt([
            F(1, True, "entity", "Receiving UPI ID", type="upi_id", value="armyhelp.desk@okhdfcbank"),
            F(2, True, "classification", "Buyer messages classified as financial fraud", file="01_buyer_chat.txt", labels=["financial_fraud"]),
            F(3, False, "extraction", "QR image text read by OCR", file="02_qr_code.png", contains=["receive", "15,000"]),
        ]),
    },
    "s19-ransomware": {
        "number": 19, "title": "Ransomware on a hospital file server", "difficulty": "Medium", "case_type": "extortion",
        "summary": "RDP sign-in from an anonymising IP, backups stopped, 18,442 files renamed, ransom demanded.",
        "briefing": "Reconstruct the intrusion sequence and classify the attacker's communication.",
        "questions": ["Where did the sign-in come from?", "In what order did the steps happen?", "What does the note demand?"],
        "planted_facts": ["185.220.101.45 RDP 02:10", "Backup service stopped 02:18"], "planted_inconsistencies": [],
        "ground_truth": _gt([
            F(1, True, "entity", "Source IP extracted", type="ip_address", value="185.220.101.45"),
            F(2, True, "classification", "Ransom note classified as extortion", file="01_ransom_note.txt", labels=["extortion"]),
            F(3, False, "classification", "Attacker email classified as extortion", file="03_attacker_email.eml", labels=["extortion"]),
        ]),
    },
    "s20-fake-payment-proof": {
        "number": 20, "title": "Edited payment screenshot used as proof", "difficulty": "Medium", "case_type": "fraud",
        "summary": "A buyer's 'payment successful' screenshot was edited in Snapseed and no credit reached the seller.",
        "briefing": "Imran Sheikh handed over a laptop after receiving a payment screenshot. Check the screenshot against his bank statement.",
        "questions": ["Is the screenshot's metadata clean?", "Does the bank statement show the credit?"],
        "planted_facts": ["EXIF Software: Snapseed", "No Rs 42,000 credit on 18-19 Apr"], "planted_inconsistencies": ["Screenshot says SUCCESS; statement has no credit"],
        "ground_truth": _gt([
            F(1, True, "integrity_check", "Editing software flagged on the screenshot", file="01_payment_screenshot.jpg", check="editing_software"),
            F(2, False, "extraction", "Screenshot OCR reads the claimed amount", file="01_payment_screenshot.jpg", contains=["42,000"]),
        ]),
    },
}
