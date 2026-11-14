"""Generate five NEW manual-test cases (stories the engine was never tuned on) into EVIDENCE-X/test_cases/.

Each folder holds real evidence files plus CASE_FORM.txt with the values to type into "New case" and the upload form.
All people, numbers, accounts and companies are fictional.

Usage:  python scripts/make_test_cases.py
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.scenarios.builder import AUTH_PASS, csv_file, eml, pdf, screenshot, tts_wav  # noqa: E402
from app.scenarios.trials import chat_shot, wa_export  # noqa: E402

OUT = Path(__file__).resolve().parent.parent.parent / "test_cases"


def form(d: Path, title, ctype, prio, desc, objective, upload, expect):
    (d.parent / f"{d.name} - CASE_FORM.txt").write_text(
        f"NEW CASE FORM\n=============\nCase title:          {title}\nCase type:           {ctype}\nPriority:            {prio}\n"
        f"Default timezone:    +05:30\n\nIncident description:\n{desc}\n\nInvestigation objective:\n{objective}\n\n"
        f"UPLOAD FORM (Evidence tab)\n==========================\n" + "\n".join(f"{k + ':':21}{v}" for k, v in upload.items()) +
        f"\n\nUpload the whole folder '{d.name}' (drop it on the upload box or use 'Choose a folder').\n\nWHAT YOU SHOULD SEE\n===================\n" +
        "\n".join(f"- {x}" for x in expect) + "\n", encoding="utf-8")


# 1 ------------------------------------------------------------------ fake job offer, advance fee
def case1(d: Path):
    eml(d / "01_offer_email.eml", '"HR Team - Nexora Global" <careers@nexora-global-hr.site>', '"Kiran Shetty" <kiran.shetty@mailbox.in>',
        "Offer letter - Data Analyst (Work from home)", "Mon, 06 Apr 2026 10:15:00 +0530",
        "Dear Kiran,\nCongratulations! You are selected as Data Analyst at Rs 65,000 per month.\n"
        "To activate your employee ID, pay a refundable onboarding and laptop security deposit of Rs 18,500 to UPI nexora.onboard@ybl within 24 hours.\n"
        "Upload your documents at https://nexora-global-hr.site/onboard and complete the payment today or the offer will be cancelled.\n"
        "HR Team, Nexora Global", received=False)
    pdf(d / "02_offer_letter.pdf", "Nexora Global Solutions - Offer of Employment", [
        "Candidate: Kiran Shetty", "Position: Data Analyst (Remote)", "Salary: Rs 65,000 per month", "Joining date: 13 April 2026",
        "Onboarding deposit: Rs 18,500 (refundable with first salary)", "Pay to UPI: nexora.onboard@ybl", "Signed: HR Manager, Nexora Global"])
    wa_export(d / "03_hr_chat.txt", [
        ("06/04/2026", "11:00", "Nexora HR Priya", "Hi Kiran, did you receive the offer letter? Pay the deposit today to block your seat."),
        ("06/04/2026", "11:20", "Kiran Shetty", "Is it refundable?"),
        ("06/04/2026", "11:22", "Nexora HR Priya", "Yes 100% refundable with first salary. Send screenshot after payment."),
        ("06/04/2026", "12:05", "Kiran Shetty", "Paid 18,500. Screenshot sent."),
        ("07/04/2026", "10:00", "Nexora HR Priya", "One more step: pay Rs 9,999 for background verification to receive your laptop."),
        ("08/04/2026", "09:30", "Kiran Shetty", "I want my deposit back, this looks wrong."),
        ("08/04/2026", "09:45", "Nexora HR Priya", "No refund before joining. Pay the verification fee or the offer is cancelled.")])
    csv_file(d / "04_bank_statement.csv", [["Date", "Description", "Debit", "Credit", "UTR"],
              ["2026-04-06 12:03 +05:30", "UPI/nexora.onboard@ybl/deposit", "18,500.00", "", "609612223411"]])
    (d / "05_complaint.txt").write_text("Statement of: Kiran Shetty\n\nI applied on a job portal and got an offer from Nexora Global. "
                                        "I paid Rs 18,500 as a refundable deposit on 6 April 2026. They now ask for Rs 9,999 more and refuse to refund. "
                                        "I believe this is a fake job scam.\n", encoding="utf-8")
    form(d, "Fake work-from-home job offer - complainant K. Shetty", "Fraud / phishing", "high",
         "The complainant received a job offer by email from 'Nexora Global', paid a 'refundable' onboarding deposit of Rs 18,500 by UPI, "
         "and was then asked for Rs 9,999 more. The 'HR' contact refuses to refund.",
         "Establish whether the offer is genuine, link the email, letter, chat and payment, and identify where the money went.",
         {"Category": "complaint evidence", "Tags": "job scam, upi, advance fee", "Collection source": "Files shared by the complainant from her phone and mailbox",
          "Collected by": "HC Ramesh Gowda, Cyber Cell", "Collected at": "2026-04-09 11:00"},
         ['Processing page opens by itself and shows Evidence processing -> Challenge engine -> Hypothesis engine, then a Final output panel.',
          "Hypothesis Lab: 'Deliberate scam' strongly supported; 'Genuine transaction or service dispute' weakened.",
          'Entities: UPI ID nexora.onboard@ybl, website nexora-global-hr.site (flagged as suspicious), UTR 609612223411.',
          'Message labels (Naive Bayes): the HR chat and the offer letter flagged as financial fraud.',
          "Gaps: the offer email's sender cannot be verified; no payment confirmation from the receiving side.",
          'Challenge tab: a phishing / payment-fraud hypothesis, decision SUPPORTED.'])


# 2 ------------------------------------------------------------------ hacked Instagram asking friends for money
def case2(d: Path):
    chat_shot(d / "01_friend_screenshot.png", "Aditi Rao", "21 April 2026", "23:58", [
        ("in", "hey are u awake? need urgent help", "23:40"), ("out", "Yes what happened?", "23:42"),
        ("in", "Please send 8000 to this upi, I will return tomorrow. My card is blocked", "23:44"),
        ("in", "Send me the OTP that came on your phone, sent by mistake", "23:47")])
    wa_export(d / "02_friend_chat_export.txt", [
        ("19/04/2026", "18:00", "Aditi Rao", "hiii are we meeting sat?? 😄"), ("19/04/2026", "18:02", "Neha Pai", "Yes! 5 pm at the cafe"),
        ("19/04/2026", "18:03", "Aditi Rao", "yayy ok see u 😄"), ("20/04/2026", "21:10", "Aditi Rao", "omg did u see the match"),
        ("20/04/2026", "21:12", "Neha Pai", "Haha yes"), ("20/04/2026", "21:15", "Aditi Rao", "lol ok gn 😴"),
        ("21/04/2026", "23:40", "Aditi Rao", "hey are u awake? need urgent help"), ("21/04/2026", "23:42", "Neha Pai", "Yes what happened?"),
        ("21/04/2026", "23:44", "Aditi Rao", "Please send 8000 to this upi, I will return tomorrow. My card is blocked"),
        ("21/04/2026", "23:47", "Aditi Rao", "Send me the OTP that came on your phone, sent by mistake"),
        ("22/04/2026", "08:10", "Aditi Rao", "neha dont send anything!! my account got hacked last night 😭")])
    csv_file(d / "03_account_login_log.csv", [["Time", "Account", "Event", "Device", "IP address", "Location"],
              ["2026-04-21 19:05 +05:30", "Aditi Rao +91 99001 23456", "Message sent", "Primary phone (iPhone)", "49.207.11.30", "Bengaluru"],
              ["2026-04-21 23:31 +05:30", "Aditi Rao +91 99001 23456", "Linked device added", "WhatsApp Web (Firefox on Linux)", "45.144.22.9", "Unknown"],
              ["2026-04-21 23:44 +05:30", "Aditi Rao +91 99001 23456", "Message sent", "WhatsApp Web (Firefox on Linux)", "45.144.22.9", "Unknown"],
              ["2026-04-21 23:47 +05:30", "Aditi Rao +91 99001 23456", "Message sent", "WhatsApp Web (Firefox on Linux)", "45.144.22.9", "Unknown"],
              ["2026-04-22 08:05 +05:30", "Aditi Rao +91 99001 23456", "Linked device removed", "Primary phone (iPhone)", "49.207.11.30", "Bengaluru"]])
    csv_file(d / "04_hospital_visitor_register.csv", [["Name", "Ward", "Check-in", "Check-out", "Purpose"],
              ["Aditi Rao", "ICU attendant", "2026-04-21 22:30 +05:30", "2026-04-22 06:00 +05:30", "Attending father (phone kept in locker)"]])
    (d / "05_account_holder_statement.txt").write_text(
        "Statement of: Aditi Rao\n\nOn the night of 21 April 2026 I was at the hospital with my father in the ICU and my phone was in a locker. "
        "In the morning I saw that a WhatsApp Web session had been added. I did not ask anyone for money or an OTP.\n", encoding="utf-8")
    form(d, "Money request sent from a friend's WhatsApp - complainant N. Pai", "Account compromise", "high",
         "The complainant received late-night messages from her friend Aditi Rao's WhatsApp asking for Rs 8,000 and an OTP. "
         "Aditi says her account was hacked while she was at a hospital.",
         "Test whether the messages were sent by the account holder or by someone using her account, and identify the records needed to confirm it.",
         {"Category": "complaint evidence", "Tags": "whatsapp, impersonation, otp", "Collection source": "Screenshot and export from complainant's phone; account log from provider",
          "Collected by": "SI Farhan Ali, Cyber Crime PS", "Collected at": "2026-04-22 14:00"},
         ["Message Check: 'Sent from the account, but indicators point to someone else using it' - a WhatsApp Web session was linked 13 minutes before, the messages were logged from it, and Aditi was in the hospital ICU at the time.",
          "Hypothesis Lab: 'Sent by someone else using the account' strongly supported; 'Sent by the account holder' contradicted.",
          "Message labels: the OTP message labelled 'OTP / password request'.",
          "Entities: the linked session's IP 45.144.22.9 and the holder's usual IP 49.207.11.30."])


# 3 ------------------------------------------------------------------ phone bought online, money to a mistyped UPI
def case3(d: Path):
    screenshot(d / "01_seller_listing.png", "QuickBuy - Seller profile", [("PhoneHub Electronics (verified)", 26, True, "#0f172a"),
               "Contact: +91 98450 77001", "Payout UPI: phonehub.store@okhdfcbank", "Listing: Pixel 8 (128 GB) - Rs 38,000"],
               bar="https://quickbuy.in/seller/phonehub", width=900)
    wa_export(d / "02_chat.txt", [
        ("10/05/2026", "17:00", "Rahul Nair", "Hi, Pixel 8 available?"),
        ("10/05/2026", "17:05", "PhoneHub Electronics", "Yes sir, Rs 38,000. Pay to phonehub.store@okhdfcbank and we ship today."),
        ("10/05/2026", "17:30", "Rahul Nair", "Paid Rs 38,000, ref 613044551290."),
        ("11/05/2026", "10:00", "PhoneHub Electronics", "Sir, not received any payment at our end. Please check the UPI you used."),
        ("12/05/2026", "11:00", "Rahul Nair", "This is fraud, you took my money.")])
    screenshot(d / "03_payment_screenshot.png", "Payment successful", ["Paid to: PhoneHub", "UPI ID: phonehub.stores@okhdfcbank",
               "Amount: Rs 38,000.00", "UPI Ref No: 613044551290", "Date: 10 May 2026, 17:28"], width=800, bg="#f0fdf4")
    csv_file(d / "04_bank_statement.csv", [["Date", "Description", "Debit", "Credit", "UTR"],
              ["2026-05-10 17:28 +05:30", "UPI/phonehub.stores@okhdfcbank/pixel", "38,000.00", "", "613044551290"]])
    eml(d / "05_seller_email.eml", '"PhoneHub Electronics" <support@phonehub-electronics.in>', '"Rahul Nair" <rahul.nair@inboxmail.com>',
        "Order - Pixel 8", "Tue, 12 May 2026 12:00:00 +0530",
        "Dear Rahul,\nWe have not received any payment. Our only UPI ID is phonehub.store@okhdfcbank. "
        "Your receipt shows phonehub.stores@okhdfcbank, which is not ours.\nPhoneHub Electronics", auth=AUTH_PASS.format(d="phonehub-electronics.in"))
    (d / "06_complaint.txt").write_text("Statement of: Rahul Nair\n\nI paid Rs 38,000 for a Pixel 8 to PhoneHub on 10 May 2026 and never got the phone. "
                                        "I think the seller cheated me.\n", encoding="utf-8")
    form(d, "Phone paid for, never received - complainant R. Nair", "Commercial / delivery dispute", "medium",
         "The buyer paid Rs 38,000 by UPI for a phone listed on QuickBuy. The seller says no payment arrived. The buyer alleges fraud.",
         "Test competing explanations (fraud, delay, wrong payment destination, failed payment, impersonation) and find where the money went.",
         {"Category": "complaint evidence", "Tags": "marketplace, upi, dispute", "Collection source": "Files provided by the buyer",
          "Collected by": "ASI Lakshmi Devi", "Collected at": "2026-05-13 10:30"},
         ["Hypothesis Lab: 'Incorrect payment destination' strongly supported - the receipt and bank show phonehub.STORES@okhdfcbank while the listing says phonehub.STORE@okhdfcbank (one letter different).",
          "'Seller impersonation' is also strongly supported, because the same UPI mismatch fits both; the first recommended step (KYC holder of the receiving UPI ID) is what separates them.",
          "'Payment processing issue' contradicted (the bank shows a completed debit); 'Deliberate fraud' weakened, because the money went to a different UPI ID than the seller's.",
          'Both UPI IDs appear as separate entities in Entities / Relationships.'])


# 4 ------------------------------------------------------------------ workplace harassment by a manager
def case4(d: Path):
    eml(d / "01_email_1.eml", '"Vikas Menon" <vikas.menon@orbitsoft.in>', '"Shruti Kamath" <shruti.kamath@orbitsoft.in>',
        "Your attitude", "Mon, 02 Mar 2026 21:40:00 +0530",
        "Shruti,\nIf you complain to HR again I will make your life hell. You are worthless and everyone in the team knows it.\nVikas",
        auth=AUTH_PASS.format(d="orbitsoft.in"))
    eml(d / "02_email_2.eml", '"Vikas Menon" <vikas.menon@orbitsoft.in>', '"Shruti Kamath" <shruti.kamath@orbitsoft.in>',
        "Last warning", "Thu, 05 Mar 2026 22:10:00 +0530",
        "Keep quiet or you will lose your job. I know where you live, don't test me.\nVikas", auth=AUTH_PASS.format(d="orbitsoft.in"))
    eml(d / "03_hr_complaint.eml", '"Shruti Kamath" <shruti.kamath@orbitsoft.in>', '"HR" <hr@orbitsoft.in>',
        "Complaint against my manager", "Fri, 06 Mar 2026 09:00:00 +0530",
        "Dear HR,\nI am reporting misconduct and harassment by my manager Vikas Menon. His emails of 2 and 5 March are attached.\nShruti Kamath",
        auth=AUTH_PASS.format(d="orbitsoft.in"))
    csv_file(d / "04_access_log.csv", [["Time", "User", "Event", "Changed by"],
              ["2026-03-09 10:00 +05:30", "shruti.kamath", "Access revoked: project repository", "vikas.menon"],
              ["2026-03-09 10:05 +05:30", "shruti.kamath", "Role downgraded to Contributor", "vikas.menon"]])
    pdf(d / "05_warning_letter.pdf", "OrbitSoft - Written warning", ["Employee: Shruti Kamath", "Date: 10 March 2026", "Issued by: Vikas Menon",
                                                                      "Reason: performance concerns", "This is a written warning."])
    form(d, "Manager harassment and retaliation - complainant S. Kamath", "Harassment / preservation", "high",
         "An employee received threatening emails from her manager, complained to HR on 6 March 2026, and within four days lost "
         "repository access, was downgraded and received a written warning.",
         "Establish the sequence of complaint and adverse actions, classify the messages, and identify missing records (HR investigation file).",
         {"Category": "workplace records", "Tags": "harassment, retaliation, email", "Collection source": "Mailbox export and IT access log provided by the company",
          "Collected by": "Internal Complaints Committee", "Collected at": "2026-03-12 15:00"},
         ["Message labels (Naive Bayes): both manager emails labelled 'Harassment / threat'.",
          'Timeline: HR complaint on 6 March, then repository access revoked and role downgraded on 9 March, warning letter on 10 March.',
          'Challenge tab: a workplace-retaliation hypothesis, decision SUPPORTED.',
          'Gaps: the access changes have no documented reason; the complaint mentions attachments that were not provided.',
          "Hypothesis Lab: the allegation partially supported; 'innocent explanation' contradicted."])


# 5 ------------------------------------------------------------------ electricity-bill SMS scam with screen-sharing app + voice note
def case5(d: Path):
    (d / "01_sms_export.txt").write_text(
        "SMS export - phone of Govind Rao (+91 94480 33221)\n\n"
        "[15/06/2026 19:02] VM-BESCOM: Dear consumer, your electricity will be disconnected tonight at 9.30 pm as your previous month bill was not updated. "
        "Please call our officer 8509912345 immediately.\n"
        "[15/06/2026 19:25] AX-SBIOTP: 774512 is the OTP to add a new device to SBI YONO. Do not share it with anyone.\n"
        "[15/06/2026 19:31] AX-SBIINB: Rs 49,000.00 debited from A/c XX7781 by IMPS to A/c XX2290. Not you? Call 1800 1234.\n", encoding="utf-8")
    csv_file(d / "02_call_log.csv", [["Time", "Number", "Direction", "Duration"],
              ["2026-06-15 19:05 +05:30", "8509912345", "Outgoing", "00:21:40"]])
    screenshot(d / "03_app_install.png", "Recently installed apps", ["AnyDesk - installed 15 Jun 2026, 19:12", "Permissions: Display over other apps, Accessibility",
               "Remote session started 19:14"], width=800)
    csv_file(d / "04_bank_statement.csv", [["Date", "Description", "Debit", "Credit", "UTR"],
              ["2026-06-15 19:31 +05:30", "IMPS TO A/C XX2290 SURESH TRADERS", "49,000.00", "", "616619445501"]])
    ok = tts_wav(d / "05_victim_voice_note.wav",
                 "My name is Govind Rao. On the fifteenth of June at around seven in the evening I got a message that my electricity "
                 "would be cut. I called the number. The man asked me to install AnyDesk to update my bill, and then forty nine "
                 "thousand rupees was taken from my account.")
    if not ok:
        (d / "05_victim_statement.txt").write_text("Statement of: Govind Rao\n\nOn 15 June 2026 at about 7 pm I got an SMS that my power would be cut. "
                                                   "I called the number; the man asked me to install AnyDesk to update my bill. Rs 49,000 was then taken.\n",
                                                   encoding="utf-8")
    form(d, "Electricity-bill SMS scam with remote-access app - complainant G. Rao", "Fraud / phishing", "critical",
         "A fake 'electricity disconnection' SMS led the complainant to call a number, install AnyDesk, and lose Rs 49,000 by IMPS minutes later.",
         "Reconstruct SMS -> call -> app install -> OTP -> debit, identify the receiving account, and list the records to request.",
         {"Category": "complaint evidence", "Tags": "sms scam, anydesk, imps", "Collection source": "Phone backup and bank statement provided by the complainant",
          "Collected by": "PC Anil Kumar, Cyber Cell", "Collected at": "2026-06-16 12:00"},
         ['Evidence tab: the voice note is transcribed and its language shown as English (100%).',
          "Timeline: SMS 19:02 -> call 19:05 -> AnyDesk 19:12 -> OTP 19:25 -> debit 19:31, plus the spoken date '15 June' from the voice note marked as estimated.",
          "Entities: the scammer's number 8509912345 and the UTR 616619445501.",
          "Hypothesis Lab: 'Deliberate scam' strongly supported; 'Genuine transaction' weakened.",
          'Message Check stays empty here on purpose: there is no chat screenshot to check.',
          'You can also record your own voice statement in this case to test Kannada / Hindi detection.'])


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    for i, (name, fn) in enumerate([("1_fake_job_offer", case1), ("2_hacked_whatsapp_money_request", case2), ("3_phone_wrong_upi", case3),
                                    ("4_workplace_harassment", case4), ("5_electricity_sms_scam", case5)], 1):
        d = OUT / name
        d.mkdir(parents=True)
        fn(d)
        print(name, sorted(p.name for p in d.iterdir()))


if __name__ == "__main__":
    main()
