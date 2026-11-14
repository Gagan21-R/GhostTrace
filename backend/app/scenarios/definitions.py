"""Scenario definitions and deterministic ground truth.

Ground truth is written independently of the engine: it lists what a competent investigator
should find in each synthetic dataset (planted facts, planted inconsistencies, expected gaps),
which findings are critical, what must NOT be reported (negative controls), and the expected
PASS/HOLD outcome. The evaluator compares engine output against this - no LLM is involved.
"""
from __future__ import annotations

S = {}

S["s1-phishing"] = {
    "number": 1, "title": "Phishing and Online Fraud", "difficulty": "Medium", "case_type": "fraud",
    "summary": "A KYC-themed phishing email leads a victim to a WhatsApp 'KYC desk' and a UPI payment of Rs 24,999.",
    "briefing": ("On 10 March 2026 Ananya Rao received an email claiming to be from her bank, warning that NetBanking would be "
                 "blocked unless KYC was completed. She followed the link, contacted a WhatsApp number shown on the page and paid a "
                 "'refundable verification fee'. A refund was promised but never arrived. Reconstruct what happened, link the "
                 "email, website, chat and payment, and identify inconsistencies and missing records."),
    "questions": ["Who sent the email and is the sender verifiable?", "Which URL and phone number connect the email, site and chat?",
                  "Do the receipt and the bank records describe the same transaction?", "When exactly was the payment made?",
                  "What evidence is still needed to trace the money?"],
    "planted_facts": ["Sender alerts@hdfc-secure-kyc.xyz with mismatched Reply-To/Return-Path and no SPF/DKIM results",
                      "Lookalike domain hdfc-secure-kyc.xyz", "WhatsApp number +91 98765 43210 in email, site and chat",
                      "UPI payment Rs 24,999 to kycdesk.verify@okaxis", "Voicemail from the 'KYC desk'"],
    "planted_inconsistencies": ["Receipt UPI Ref 407215583921 vs bank UTR 407215538921 (transposed digits)",
                                "Statement says payment on 11 March; bank records say 10 March"],
    "ground_truth": {
        "expected_outcome": "PASS",
        "findings": [
            {"id": "F1", "critical": True, "type": "entity", "description": "Sender address alerts@hdfc-secure-kyc.xyz extracted",
             "match": {"type": "email", "value": "alerts@hdfc-secure-kyc.xyz"}},
            {"id": "F2", "critical": True, "type": "suspicious_url", "description": "Lookalike domain hdfc-secure-kyc.xyz flagged with phishing indicators",
             "match": {"domain": "hdfc-secure-kyc.xyz"}},
            {"id": "F3", "critical": True, "type": "entity", "description": "Scammer phone number extracted", "match": {"type": "phone", "value": "9876543210"}},
            {"id": "F4", "critical": True, "type": "contradiction", "description": "Mismatched transaction reference between receipt and bank records",
             "match": {"category": "transaction_reference_mismatch", "values": ["407215583921", "407215538921"]}},
            {"id": "F5", "critical": False, "type": "contradiction", "description": "Payment date conflict (statement 11 Mar vs bank 10 Mar)",
             "match": {"category": "date_conflict", "contains": "dates for the payment"}},
            {"id": "F6", "critical": True, "type": "gap", "description": "Phishing email sender cannot be verified",
             "match": {"category": "unverified_sender", "file": "01_kyc_email.eml"}},
            {"id": "F7", "critical": True, "type": "gap", "description": "Promised refund is not evidenced", "match": {"category": "refund_unconfirmed"}},
            {"id": "F8", "critical": False, "type": "gap", "description": "Attachment referenced but missing (email KYC form or chat media)",
             "match": {"category": "missing_attachment"}},
            {"id": "F9", "critical": False, "type": "relationship", "description": "Phone number linked to the phishing domain by an observed record",
             "match": {"a": "9876543210", "b": "hdfc-secure-kyc.xyz"}},
            {"id": "F10", "critical": True, "type": "hypothesis", "description": "Hypothesis: phishing-led payment fraud", "match": {"pattern": "phishing_payment_fraud"}},
            {"id": "F11", "critical": False, "type": "extraction", "description": "Voicemail transcribed and mentions KYC",
             "match": {"file": "10_voicemail.wav", "contains": ["kyc", "blocked"]}},
            {"id": "F12", "critical": False, "type": "extraction", "description": "Receipt screenshot OCR recovers the UPI reference",
             "match": {"file": "04_payment_receipt.png", "contains": ["407215583921"]}},
            {"id": "F13", "critical": False, "type": "dependency", "description": "Receipt copy recognised as a duplicate, not independent corroboration",
             "match": {"files": ["04_payment_receipt.png", "04b_receipt_copy.png"], "relations": ["duplicate"]}},
            {"id": "F14", "critical": False, "type": "dependency", "description": "Forwarded email recognised as derived from the phishing email",
             "match": {"files": ["01_kyc_email.eml", "11_forward_to_bank.eml"], "relations": ["derived"]}},
        ],
        "allowed_dependencies": [{"relation": "shared_source"}, {"relation": "near_duplicate"}],
        "allowed_contradictions": [{"category": "identifier_mismatch"}, {"category": "date_conflict"}],
        "forbidden": [{"type": "gap", "category": "unverified_sender", "file": "09_flipkart_newsletter.eml",
                       "description": "Authenticated newsletter must not be flagged as unverified"},
                      {"type": "suspicious_url", "domain": "flipkart.com", "description": "Legitimate domain must not be flagged"}],
        "scored_entities": {"types": ["email", "upi_id", "phone", "website", "transaction"],
                            "values": ["alerts@hdfc-secure-kyc.xyz", "ananya.rao@mailbox.in", "support@kyc-update-help.top",
                                       "bounce@mailer-kyc.top", "kycdesk.verify@okaxis", "refunds@kyc-update-help.top",
                                       "noreply@flipkart.com", "9876543210", "8002586161",
                                       "hdfc-secure-kyc.xyz", "flipkart.com", "406812339011", "406903211874", "407215538921",
                                       "407320116522", "407500772014", "407215583921"]},
        "expected_events": [
            {"file": "01_kyc_email.eml", "contains": "KYC", "local_time": "2026-03-10 09:12"},
            {"file": "05_bank_statement.csv", "contains": "KYC DESK", "local_time": "2026-03-10 09:47"},
            {"file": "03_whatsapp_chat.txt", "contains": "Paid", "local_time": "2026-03-10 09:48"},
            {"file": "08_followup_email.eml", "contains": "Refund", "local_time": "2026-03-12 16:40"}],
        "irrelevant_records": ["09_flipkart_newsletter.eml"],
        "ambiguous_records": [{"file": "03_whatsapp_chat.txt", "note": "dd/mm/yyyy dates where day and month are both <= 12"}],
        "verification": {"max_unsupported_claim_rate": 0.0},
        "timeline_sequence": [{"file": "01_kyc_email.eml", "contains": "KYC"},
                              {"file": "03_whatsapp_chat.txt", "contains": "Is this the HDFC KYC desk"},
                              {"file": "05_bank_statement.csv", "contains": "KYC DESK"},
                              {"file": "08_followup_email.eml", "contains": "Refund"}],
        "ocr_expect": {"04_payment_receipt.png": ["Amount Paid: Rs 24,999.00", "UPI Ref No: 407215583921", "UPI ID: kycdesk.verify@okaxis"],
                       "02_phishing_site.png": ["Helpline: +91 98765 43210", "Pay to UPI ID: kycdesk.verify@okaxis"]},
        "asr_expect": {"10_voicemail.wav": "hello madam this is the kyc desk from hdfc bank your net banking will be blocked today please call back immediately on 98765 43210"},
    },
}

S["s2-account-compromise"] = {
    "number": 2, "title": "Account Compromise and Identity Misuse", "difficulty": "Hard", "case_type": "account_compromise",
    "summary": "Overnight sign-in, password change and recovery-email change on a cloud account after an OTP request on WhatsApp.",
    "briefing": ("Rahul Mehta reports that his CloudVault account was taken over during the night of 13-14 March 2026. He received "
                 "security emails about a new sign-in, a password change and a recovery-email change. Reconstruct the account "
                 "activity, compare session details, and test his statement against the records. Do not attribute the activity "
                 "to any individual on the basis of IP or device."),
    "questions": ["In what order did the account events occur?", "Do the alert and the session log agree on the session details?",
                  "Is the account holder's statement consistent with the other records?", "Which logs are missing?"],
    "planted_facts": ["Sign-in from 102.89.34.17 (Lagos) at 02:14", "Password changed 02:20", "Recovery email changed 02:25 to r.mehta.secure@protonmail-mail.net",
                      "OTP request from +44 7700 900123 at 01:58 answered at 02:03"],
    "planted_inconsistencies": ["Alert says Windows 11 Chrome; session log says Linux Firefox for the same sign-in",
                                "Statement denies sharing a code; chat shows Rahul Mehta sending a verification code",
                                "Session log export truncated before the recovery-email change"],
    "ground_truth": {
        "expected_outcome": "PASS",
        "findings": [
            {"id": "F1", "critical": True, "type": "entity", "description": "Suspicious IP 102.89.34.17 extracted", "match": {"type": "ip_address", "value": "102.89.34.17"}},
            {"id": "F2", "critical": True, "type": "entity", "description": "New recovery email extracted", "match": {"type": "email", "value": "r.mehta.secure@protonmail-mail.net"}},
            {"id": "F3", "critical": True, "type": "contradiction", "description": "Device conflict between alert and session log",
             "match": {"category": "attribute_conflict", "field": "device"}},
            {"id": "F4", "critical": True, "type": "contradiction", "description": "Statement denial vs the holder's own chat message",
             "match": {"category": "statement_vs_record"}},
            {"id": "F5", "critical": True, "type": "gap", "description": "Session log does not cover all account events", "match": {"category": "incomplete_login_records"}},
            {"id": "F6", "critical": False, "type": "entity", "description": "Lagos location extracted", "match": {"type": "location", "value": "lagos"}},
            {"id": "F7", "critical": True, "type": "hypothesis", "description": "Hypothesis: account compromise", "match": {"pattern": "account_compromise"}},
            {"id": "F8", "critical": False, "type": "counter", "description": "Counter-agent raises credential/OTP disclosure as an alternative",
             "match": {"contains": "disclosed a code"}},
            {"id": "F9", "critical": False, "type": "dependency", "description": "Alert email and session log come from the same provider (shared source, not independent)",
             "match": {"files": ["01_new_signin_alert.eml", "04_session_log.csv"], "relations": ["shared_source"]}},
        ],
        "allowed_dependencies": [{"relation": "shared_source"}],
        "allowed_contradictions": [{"category": "attribute_conflict"}, {"category": "date_conflict", "contains": "password"}],
        "forbidden": [{"type": "text", "pattern": r"\b(?:is|was) the (?:attacker|hacker|perpetrator)\b", "description": "No attribution of identity"}],
        "scored_entities": {"types": ["ip_address", "email"],
                            "values": ["102.89.34.17", "49.36.12.88", "security@cloudvault.io", "rahul.mehta@inboxmail.com",
                                       "r.mehta.secure@protonmail-mail.net", "news@cloudvault.io"]},
        "expected_events": [
            {"file": "04_session_log.csv", "contains": "102.89.34.17", "local_time": "2026-03-14 02:14"},
            {"file": "04_session_log.csv", "contains": "password changed", "local_time": "2026-03-14 02:20"},
            {"file": "03_recovery_email_changed.eml", "contains": "Recovery", "local_time": "2026-03-14 02:26"}],
        "irrelevant_records": ["08_product_update.eml"],
        "ambiguous_records": [{"file": "05_otp_chat.txt", "note": "chat export states no timezone; case default applied"}],
        "verification": {"max_unsupported_claim_rate": 0.0},
        "timeline_sequence": [{"file": "05_otp_chat.txt", "contains": "verification code sent"},
                              {"file": "05_otp_chat.txt", "contains": "Here is the verification code"},
                              {"file": "04_session_log.csv", "contains": "102.89.34.17"},
                              {"file": "02_password_changed.eml", "contains": "password"},
                              {"file": "03_recovery_email_changed.eml", "contains": "Recovery"}],
        "ocr_expect": {"07_device_list.png": ["Unknown device - Linux - Lagos, NG - 14 Mar 2026 02:14", "Pixel 7 - Android 14 - Mumbai, IN - Active now"]},
    },
}

S["s3-evidence-preservation"] = {
    "number": 3, "title": "Disappearing Digital Evidence Preservation", "difficulty": "Medium", "case_type": "harassment",
    "summary": "Harassing posts and DMs from @void_whisper; some content was unsent or deleted before capture.",
    "briefing": ("Meera Iyer is being harassed by the SocialHub account @void_whisper. Some posts and messages have already been "
                 "deleted or unsent. Build a verified evidence inventory, check integrity against the collection log, find "
                 "incomplete conversations and missing attachments, and list preservation actions. Do not attempt to recover "
                 "deleted content or access accounts without authorisation."),
    "questions": ["Is every item hashed and its collection documented?", "Does the collection log match the files received?",
                  "Which conversations are incomplete?", "What online content is at risk and not yet preserved?"],
    "planted_facts": ["Two post screenshots, one DM export, one downloaded image", "Collection log with hashes"],
    "planted_inconsistencies": ["Collection log hash for 02_post_screenshot_2.png does not match the file",
                                "DM export declares 14 messages, contains 10, IDs 5-6, 9, 13 missing",
                                "Attachment photo_0306.jpg not included", "Post 88245 deleted, never captured",
                                "08_comment_screenshot.png has no collection information"],
    "ground_truth": {
        "expected_outcome": "PASS",
        "findings": [
            {"id": "F1", "critical": True, "type": "contradiction", "description": "Integrity mismatch for 02_post_screenshot_2.png",
             "match": {"category": "integrity_mismatch", "contains": "02_post_screenshot_2.png"}},
            {"id": "F2", "critical": True, "type": "gap", "description": "DM export is incomplete", "match": {"category": "incomplete_conversation", "file": "03_dm_export.json"}},
            {"id": "F3", "critical": True, "type": "gap", "description": "Missing DM attachment photo_0306.jpg", "match": {"category": "missing_attachment", "contains": "photo_0306.jpg"}},
            {"id": "F4", "critical": True, "type": "gap", "description": "Deleted post 88245 not preserved", "match": {"category": "content_not_preserved", "contains": "88245"}},
            {"id": "F5", "critical": False, "type": "gap", "description": "Item without collection information", "match": {"category": "collection_info_missing", "file": "08_comment_screenshot.png"}},
            {"id": "F6", "critical": True, "type": "integrity", "description": "Every evidence item hashed at intake and re-verified", "match": {"all_hashed": True}},
            {"id": "F7", "critical": False, "type": "entity", "description": "Harassing account handle extracted", "match": {"type": "username", "value": "void_whisper"}},
            {"id": "F8", "critical": True, "type": "hypothesis", "description": "Hypothesis: harassment with preservation gaps", "match": {"pattern": "online_harassment_preservation"}},
            {"id": "F9", "critical": True, "type": "dependency", "description": "Exact duplicate screenshot identified",
             "match": {"files": ["01_post_screenshot_1.png", "01b_post_screenshot_1_copy.png"], "relations": ["duplicate"]}},
            {"id": "F10", "critical": False, "type": "dependency", "description": "Re-compressed copy identified as near-duplicate",
             "match": {"files": ["02_post_screenshot_2.png", "02b_post_screenshot_2_resaved.jpg"], "relations": ["near_duplicate"]}},
        ],
        "allowed_dependencies": [{"relation": "shared_source"}],
        "allowed_contradictions": [{"category": "date_conflict"}],
        "forbidden": [{"type": "gap", "category": "incomplete_conversation", "file": "06_urls.txt", "description": "Non-chat items are not conversations"},
                      {"type": "text", "pattern": r"recovered (?:the )?deleted", "description": "No claim of recovering deleted content"}],
        "scored_entities": {"types": ["username", "website"], "values": ["void_whisper", "meera.iyer", "socialhub.app"]},
        "expected_events": [
            {"file": "03_dm_export.json", "contains": "I will leak", "local_time": "2026-03-06 22:10"},
            {"file": "03_dm_export.json", "contains": "Watch your back", "local_time": "2026-03-07 09:05"}],
        "irrelevant_records": [],
        "ambiguous_records": [{"file": "08_comment_screenshot.png", "note": "no collection information"}],
        "verification": {"max_unsupported_claim_rate": 0.0},
        "timeline_sequence": [{"file": "03_dm_export.json", "contains": "Why are you ignoring"},
                              {"file": "03_dm_export.json", "contains": "I will leak"},
                              {"file": "03_dm_export.json", "contains": "Watch your back"}],
        "ocr_expect": {"01_post_screenshot_1.png": ["Everyone should know what Meera Iyer really is.", "Posted 5 Mar 2026 21:40"],
                       "02_post_screenshot_2.png": ["You will regret ignoring me @meera.iyer"]},
    },
}

S["s4-whistleblower-retaliation"] = {
    "number": 4, "title": "Whistleblower Retaliation and Corporate Misconduct", "difficulty": "Hard", "case_type": "corporate",
    "summary": "After a 6 March ethics complaint, the employee loses SharePoint access and steering-meeting invitations.",
    "briefing": ("Priya Nair reported suspected irregular vendor payments approved by her manager on 6 March 2026. Afterwards her "
                 "access to finance systems changed and she stopped being invited to steering meetings. HR says the access change "
                 "was a scheduled review that happened before the complaint. Reconstruct events before and after the complaint, "
                 "test each party's account against the records and identify what is missing. Timing alone does not prove retaliation."),
    "questions": ["What changed for the employee before and after 6 March?", "Does HR's explanation match the access log?",
                  "Are the changes documented with tickets and reasons?", "What alternative explanations exist?"],
    "planted_facts": ["Complaint email 6 Mar 18:42", "Access revoked 11 Mar by arjun.sethi with no ticket", "Removed from meeting invites from 13 Mar",
                      "Manager chat: 'keep Priya off the Atlas steering calls'"],
    "planted_inconsistencies": ["HR says access changed on 3 March; access log says 11 March",
                                "HR acknowledgement says complaint received 9 March; complaint email sent 6 March",
                                "Policy schedules reviews in the first week of each quarter"],
    "ground_truth": {
        "expected_outcome": "HOLD",
        "findings": [
            {"id": "F1", "critical": True, "type": "contradiction", "description": "Access-change date conflict (HR 3 Mar vs log 11 Mar)",
             "match": {"category": "date_conflict", "contains": "dates for the access change"}},
            {"id": "F2", "critical": False, "type": "contradiction", "description": "Complaint date conflict (6 Mar vs 9 Mar)",
             "match": {"category": "date_conflict", "contains": "dates for the complaint"}},
            {"id": "F3", "critical": True, "type": "gap", "description": "Access revocation lacks ticket/approver/reason", "match": {"category": "undocumented_access_change"}},
            {"id": "F4", "critical": True, "type": "hypothesis", "description": "Hypothesis: possible retaliation (timing)", "match": {"pattern": "workplace_retaliation"}},
            {"id": "F5", "critical": True, "type": "counter", "description": "Counter-agent raises the scheduled access review as an alternative",
             "match": {"contains": "scheduled access review"}},
            {"id": "F6", "critical": True, "type": "verdict", "description": "Reviewer does not conclude retaliation (contested/insufficient)",
             "match": {"verdicts": ["contested", "insufficient_evidence"]}},
            {"id": "F7", "critical": False, "type": "dependency", "description": "Forwarded HR reply recognised as derived, not a second HR account",
             "match": {"files": ["03_hr_access_reply.eml", "11_fwd_access_reply.eml"], "relations": ["derived"]}},
            {"id": "F8", "critical": False, "type": "extraction", "description": "Meeting recording: keyframe OCR and speech transcribed",
             "match": {"file": "12_steering_meeting_recording.mp4", "contains": ["attendees", "leads only"]}},
        ],
        "allowed_dependencies": [{"relation": "shared_source"}],
        "allowed_contradictions": [{"category": "date_conflict"}, {"category": "statement_vs_record"}],
        "forbidden": [{"type": "text", "pattern": r"\bretaliation (?:is|was) (?:proven|established|confirmed)\b", "description": "No unsupported misconduct finding"}],
        "scored_entities": {"types": ["email"], "values": ["priya.nair@northwind-analytics.com", "ethics@northwind-analytics.com",
                                                           "kavita.menon@northwind-analytics.com"]},
        "expected_events": [
            {"file": "01_complaint_email.eml", "contains": "complaint", "local_time": "2026-03-06 18:42"},
            {"file": "04_access_log.csv", "contains": "Finance-SharePoint; Action: Access revoked; Changed By: arjun", "local_time": "2026-03-11 09:42"}],
        "irrelevant_records": [],
        "ambiguous_records": [{"file": "09_statement_arjun.txt", "note": "undated assertions"}],
        "verification": {"max_unsupported_claim_rate": 0.0},
        "timeline_sequence": [{"file": "01_complaint_email.eml", "contains": "complaint"},
                              {"file": "06_team_chat.json", "contains": "keep Priya off"},
                              {"file": "04_access_log.csv", "contains": "Finance-SharePoint; Action: Access revoked; Changed By: arjun"},
                              {"file": "07_meeting_records.xlsx", "contains": "removed from invite"}],
    },
}

S["s5-marketplace-dispute"] = {
    "number": 5, "title": "Marketplace and Delivery Dispute Reconstruction", "difficulty": "Medium", "case_type": "commercial_dispute",
    "summary": "50 bottles ordered and invoiced, 40 delivered, Rs 65,200 paid against a Rs 62,500 invoice, refund promised but not paid.",
    "briefing": ("Karthik Bhat ordered 50 water bottles from Sunrise Kitchenware Traders on BazaarHub. He says he received only 40, "
                 "paid more than the invoice, and never received the refund the seller promised. Reconstruct the transaction, compare "
                 "quantities and amounts, connect seller messages with courier records and identify missing confirmations."),
    "questions": ["Do ordered, invoiced and delivered quantities match?", "Does the payment match the invoice?",
                  "When was the order delivered?", "Do all messages refer to the same order?", "Is the refund evidenced?"],
    "planted_facts": ["Order OD-48213 qty 50 Rs 62,500", "Payment Rs 65,200 incl. express shipping Rs 2,700", "Courier: 5 pieces picked up, 4 delivered on 18 Mar"],
    "planted_inconsistencies": ["Invoice qty 50 vs delivered qty 40", "Invoice Rs 62,500 vs payment Rs 65,200",
                                "Seller says delivered 16 Mar; courier says 18 Mar", "Refund message cites OD-48231 instead of OD-48213"],
    "ground_truth": {
        "expected_outcome": "PASS",
        "findings": [
            {"id": "F1", "critical": True, "type": "contradiction", "description": "Quantity conflict 50 vs 40", "match": {"category": "quantity_conflict", "values": ["50", "40"]}},
            {"id": "F2", "critical": True, "type": "contradiction", "description": "Invoice vs payment amount conflict", "match": {"category": "amount_conflict", "contains": "65,200"}},
            {"id": "F3", "critical": True, "type": "contradiction", "description": "Mismatched order ID OD-48213 / OD-48231",
             "match": {"category": "identifier_mismatch", "values": ["OD-48213", "OD-48231"]}},
            {"id": "F4", "critical": False, "type": "contradiction", "description": "Delivery date conflict 16 vs 18 Mar", "match": {"category": "date_conflict", "contains": "dates for the delivery"}},
            {"id": "F5", "critical": True, "type": "gap", "description": "Refund promised but not evidenced", "match": {"category": "refund_unconfirmed"}},
            {"id": "F6", "critical": True, "type": "entity", "description": "Order ID extracted", "match": {"type": "order", "value": "OD-48213"}},
            {"id": "F7", "critical": False, "type": "counter", "description": "Counter-agent explains Rs 2,700 difference by express shipping charge",
             "match": {"contains": "difference between the two amounts equals"}},
            {"id": "F8", "critical": True, "type": "hypothesis", "description": "Hypothesis: delivery dispute", "match": {"pattern": "delivery_dispute"}},
            {"id": "F9", "critical": False, "type": "dependency", "description": "Delivery screenshot depends on the delivery confirmation (not independent)",
             "match": {"files": ["06_delivery_confirmation.pdf", "10_delivery_screenshot.png"], "relations": ["near_duplicate", "derived"]}},
        ],
        "allowed_dependencies": [{"relation": "shared_source"}],
        "allowed_contradictions": [{"category": "date_conflict"}, {"category": "amount_conflict"}],
        "forbidden": [{"type": "contradiction_value", "value": "OD-51120", "description": "Unrelated order must not be linked"}],
        "scored_entities": {"types": ["order", "shipment", "transaction"], "values": ["OD-48213", "OD-48231", "OD-51120", "7781234590", "BHP8820193344"]},
        "expected_events": [
            {"file": "01_order_confirmation.eml", "contains": "OD-48213", "local_time": "2026-03-02 11:20"},
            {"file": "05_courier_tracking.csv", "contains": "Delivered", "local_time": "2026-03-18 14:35"}],
        "irrelevant_records": ["09_other_order.eml"],
        "ambiguous_records": [{"file": "04_seller_chat.json", "note": "refund message cites a different order ID"}],
        "verification": {"max_unsupported_claim_rate": 0.0},
        "timeline_sequence": [{"file": "01_order_confirmation.eml", "contains": "OD-48213"},
                              {"file": "04_seller_chat.json", "contains": "dispatched"},
                              {"file": "05_courier_tracking.csv", "contains": "Delivered"},
                              {"file": "04_seller_chat.json", "contains": "refund"}],
        "ocr_expect": {"03_payment_receipt.png": ["Amount Paid: Rs 65,200.00", "Transaction ID: BHP8820193344", "Order ID: OD-48213"],
                       "07_product_photo.jpg": ["CARTON 4 of 5 - 10 units - OD-48213"]},
    },
}

S["s2h-sparse-account-records"] = {
    "number": 6, "title": "Negative control: Account compromise with sparse records", "difficulty": "Control", "case_type": "account_compromise",
    "variant_of": "s2-account-compromise",
    "summary": "Only a statement and a device screenshot - the engine must return HOLD rather than a conclusion.",
    "briefing": ("Same incident as Scenario 2, but the investigator only has the account holder's statement and a screenshot of the "
                 "device list. The correct result is to request more records rather than to reach a conclusion."),
    "questions": ["Is there enough evidence to establish the sequence of account events?"],
    "planted_facts": ["Statement denying activity", "Device list showing a Linux/Lagos session"],
    "planted_inconsistencies": [],
    "ground_truth": {
        "expected_outcome": "HOLD",
        "findings": [
            {"id": "F1", "critical": True, "type": "verdict", "description": "Engine returns insufficient evidence", "match": {"verdicts": ["insufficient_evidence"]}},
            {"id": "F2", "critical": False, "type": "gap", "description": "Undated events flagged", "match": {"category": "missing_timestamps"}},
        ],
        "allowed_contradictions": [],
        "forbidden": [{"type": "text", "pattern": r"\b(?:is|was) the (?:attacker|hacker)\b", "description": "No attribution"}],
        "scored_entities": {"types": [], "values": []},
        "timeline_sequence": [],
        "ocr_expect": {"07_device_list.png": ["Unknown device - Linux - Lagos, NG - 14 Mar 2026 02:14"]},
    },
}


from .trial_defs import TRIALS  # noqa: E402

S.update(TRIALS)
from .marketplace import MARKET_DEFS  # noqa: E402

S.update(MARKET_DEFS)
