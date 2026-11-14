"""Fourteen additional trial datasets (scenarios 7-20). Fictional people, numbers and domains only.

Three of them test the impersonation question directly:
  s7  a harassing message really was sent from the accused's WhatsApp - by a linked web session while he was elsewhere
  s8  the "threat" screenshot was produced with a chat generator and never existed in either phone
  s9  control: the accused claims "I was hacked", but every record points to his own phone
"""
from __future__ import annotations

import io
from pathlib import Path

from PIL import Image, ImageDraw
from PIL.PngImagePlugin import PngInfo

from .builder import AUTH_PASS, csv_file, eml, pdf, screenshot, _font


# ----------------------------------------------------------------------------- helpers
def wa_export(path: Path, rows: list[tuple[str, str, str | None, str]]):
    """rows: (dd/mm/yyyy, HH:MM, sender or None for system line, text) -> WhatsApp 'Export chat' text."""
    out = [f"{d}, {t} - {(s + ': ') if s else ''}{x}" for d, t, s, x in rows]
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


def chat_shot(path: Path, contact: str, date_label: str, status_time: str, msgs: list[tuple[str, str, str]],
              fmt="PNG", software: str | None = None, watermark: str | None = None, paste: dict | None = None):
    """Phone-style chat screenshot. msgs: (side 'in'|'out', text, HH:MM). Each bubble is one OCR row: text + time."""
    W = 900
    H = 260 + 86 * len(msgs) + (60 if watermark else 0)
    img = Image.new("RGB", (W, H), "#ece5dd")
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 48], fill="#054d44")
    d.text((24, 12), status_time, font=_font(22, True), fill="#ffffff")
    d.text((W - 150, 12), "4G  78%", font=_font(20), fill="#ffffff")
    d.rectangle([0, 48, W, 128], fill="#075e54")
    d.ellipse([24, 60, 80, 116], fill="#cfd8dc")
    d.text((100, 64), contact, font=_font(30, True), fill="#ffffff")
    d.text((100, 100), "online", font=_font(16), fill="#d1fae5")
    d.rounded_rectangle([W // 2 - 120, 150, W // 2 + 120, 190], radius=10, fill="#d9f1fb")
    d.text((W // 2 - 95, 156), date_label, font=_font(22), fill="#334155")
    y = 220
    for side, text, t in msgs:
        f = _font(24)
        tw = d.textlength(text, font=f)
        x0 = 30 if side == "in" else W - 70 - tw - 90
        d.rounded_rectangle([x0, y, x0 + tw + 110, y + 62], radius=12, fill="#ffffff" if side == "in" else "#dcf8c6")
        d.text((x0 + 18, y + 16), text, font=f, fill="#111827")
        d.text((x0 + tw + 36, y + 22), t, font=_font(18), fill="#6b7280")
        y += 86
    if watermark:
        d.text((30, y + 10), watermark, font=_font(18), fill="#9ca3af")
    if fmt == "JPEG":
        exif = Image.Exif()
        if software:
            exif[0x0131] = software
        if paste:  # simulate an edited bubble: base saved at low quality, then a fresh region pasted in and saved again
            buf = io.BytesIO()
            img.save(buf, "JPEG", quality=40)
            base = Image.open(io.BytesIO(buf.getvalue())).convert("RGB")
            base.paste(img.crop(paste["box"]), paste["box"][:2])
            img = base
        img.save(path, "JPEG", quality=92, exif=exif)
    else:
        info = PngInfo()
        if software:
            info.add_text("Software", software)
        img.save(path, "PNG", pnginfo=info)


def csvrows(path, header, rows):
    csv_file(path, [header] + rows)


# ----------------------------------------------------------------------------- s7 hacked WhatsApp
def build_s7(d: Path):
    f = []
    chat_shot(d / "01_complaint_screenshot.png", "Rohan Verma", "18 March 2026", "22:58", [
        ("in", "bro did u submit the dbms record", "21:02"),
        ("out", "Yes, this afternoon", "21:05"),
        ("in", "I know where you live. You will regret this.", "22:41"),
        ("in", "Send 5000 tonight or I share your photos with everyone.", "22:42"),
        ("out", "Rohan what is wrong with you??", "22:50"),
    ])
    f.append(("01_complaint_screenshot.png", "screenshot", "Screenshot submitted by complainant Sneha Kulkarni with her complaint", ["complaint", "screenshot"]))
    hist = [
        ("16/03/2026", "19:10", "Rohan Verma", "da can u send the os notes"), ("16/03/2026", "19:12", "Sneha Kulkarni", "Sent on the group"),
        ("16/03/2026", "19:13", "Rohan Verma", "thanks da ur a lifesaver"), ("17/03/2026", "08:40", "Rohan Verma", "bro class cancelled today or what"),
        ("17/03/2026", "08:45", "Sneha Kulkarni", "Not sure, ask Kavya"), ("17/03/2026", "13:05", "Rohan Verma", "lol ok ill check with her"),
        ("17/03/2026", "20:30", "Rohan Verma", "hackathon tmrw night u coming?"), ("17/03/2026", "20:31", "Sneha Kulkarni", "No, I have to study"),
        ("17/03/2026", "20:33", "Rohan Verma", "ok np all the best da"),
        ("18/03/2026", "21:02", "Rohan Verma", "bro did u submit the dbms record"), ("18/03/2026", "21:05", "Sneha Kulkarni", "Yes, this afternoon"),
        ("18/03/2026", "22:41", "Rohan Verma", "I know where you live. You will regret this."),
        ("18/03/2026", "22:42", "Rohan Verma", "Send 5000 tonight or I share your photos with everyone."),
        ("18/03/2026", "22:50", "Sneha Kulkarni", "Rohan what is wrong with you??"),
    ]
    wa_export(d / "02_sneha_chat_export.txt", hist)
    f.append(("02_sneha_chat_export.txt", "chat", "WhatsApp 'Export chat' from Sneha Kulkarni's phone, 19 Mar 2026", ["chat", "complainant"]))
    wa_export(d / "03_rohan_chat_export.txt", hist + [
        ("18/03/2026", "23:31", "Rohan Verma", "sneha i did not send those msgs. someone logged into my whatsapp on a laptop, i was at the hackathon"),
        ("18/03/2026", "23:33", "Sneha Kulkarni", "I am going to the police."),
    ])
    f.append(("03_rohan_chat_export.txt", "chat", "WhatsApp export from Rohan Verma's phone, seized and exported by police 20 Mar 2026", ["chat", "accused"]))
    csvrows(d / "04_whatsapp_account_log.csv", ["Time", "Account", "Event", "Device", "IP address"], [
        ["2026-03-18 21:02:11 +05:30", "Rohan Verma +91 98450 11223", "Message sent", "Primary phone (Android)", "49.36.88.12"],
        ["2026-03-18 21:58:40 +05:30", "Rohan Verma +91 98450 11223", "Linked device added", "WhatsApp Web (Chrome on Windows)", "103.211.54.90"],
        ["2026-03-18 22:41:10 +05:30", "Rohan Verma +91 98450 11223", "Message sent", "WhatsApp Web (Chrome on Windows)", "103.211.54.90"],
        ["2026-03-18 22:42:05 +05:30", "Rohan Verma +91 98450 11223", "Message sent", "WhatsApp Web (Chrome on Windows)", "103.211.54.90"],
        ["2026-03-18 23:24:51 +05:30", "Rohan Verma +91 98450 11223", "Linked device removed", "Primary phone (Android)", "49.36.88.12"],
    ])
    f.append(("04_whatsapp_account_log.csv", "account log", "Account activity for Rohan Verma's number, provider response to police request", ["log", "account"]))
    csvrows(d / "05_hackathon_entry_log.csv", ["Name", "Team", "Check-in", "Check-out", "Phone deposited", "Desk"], [
        ["Ananya Iyer", "ByteForce", "2026-03-18 21:50 +05:30", "2026-03-19 06:00 +05:30", "Locker 12", "D4"],
        ["Rohan Verma", "NullPointers", "2026-03-18 22:05 +05:30", "2026-03-18 23:15 +05:30", "Locker 17", "B2"],
        ["Kavya Menon", "NullPointers", "2026-03-18 22:06 +05:30", "2026-03-19 06:00 +05:30", "Locker 18", "B2"],
    ])
    f.append(("05_hackathon_entry_log.csv", "attendance", "Venue entry register, college hackathon (phones deposited at entrance)", ["alibi", "attendance"]))
    (d / "06_complainant_statement.txt").write_text(
        "Statement of: Sneha Kulkarni\n\nOn 18 March 2026 at about 22:41 I received two messages from my classmate Rohan Verma's WhatsApp "
        "number threatening me and asking for Rs 5000. I took a screenshot and stopped replying. Rohan later wrote that he did not send them.\n",
        encoding="utf-8")
    f.append(("06_complainant_statement.txt", "statement", "Statement recorded by investigator 19 Mar 2026", ["statement"]))
    return f


# ----------------------------------------------------------------------------- s8 fabricated screenshot
def build_s8(d: Path):
    f = []
    msgs = [("in", "Did you send the April invoice?", "19:02"), ("out", "Yes, check your mail", "19:05"),
            ("in", "You will pay for this. I will ruin your business and your family.", "19:20")]
    H = 260 + 86 * len(msgs)
    chat_shot(d / "01_threat_screenshot.jpg", "Priya Nair", "5 April 2026", "18:05", msgs, fmt="JPEG",
              software="FakeChat Maker 3.2", paste={"box": (20, 220 + 86 * 2 - 4, 900, H - 20)})
    f.append(("01_threat_screenshot.jpg", "screenshot", "Screenshot attached to complaint by Karan Malhotra (sent via email)", ["complaint", "screenshot"]))
    rows = [("03/04/2026", "11:00", "Priya Nair", "Karan, the client wants the revised quote by Friday."),
            ("03/04/2026", "11:20", "Karan Malhotra", "Ok will send"), ("04/04/2026", "16:45", "Priya Nair", "Please also share the GST details."),
            ("04/04/2026", "17:02", "Karan Malhotra", "Done"), ("05/04/2026", "19:02", "Priya Nair", "Did you send the April invoice?"),
            ("05/04/2026", "19:05", "Karan Malhotra", "Yes, check your mail"), ("05/04/2026", "19:11", "Priya Nair", "Got it, thanks. Talk tomorrow."),
            ("06/04/2026", "10:15", "Priya Nair", "I have asked the lawyer to draft the exit agreement as discussed."),
            ("06/04/2026", "10:40", "Karan Malhotra", "Fine.")]
    wa_export(d / "02_karan_chat_export.txt", rows)
    f.append(("02_karan_chat_export.txt", "chat", "WhatsApp export from Karan Malhotra's phone, produced on notice 9 Apr 2026", ["chat", "complainant"]))
    wa_export(d / "03_priya_chat_export.txt", rows)
    f.append(("03_priya_chat_export.txt", "chat", "WhatsApp export from Priya Nair's phone, produced through her counsel 10 Apr 2026", ["chat", "accused"]))
    csvrows(d / "04_priya_account_log.csv", ["Time", "Account", "Event", "Device", "IP address"], [
        ["2026-04-05 19:02:03 +05:30", "Priya Nair +91 99000 44556", "Message sent", "Primary phone (iPhone)", "106.51.22.40"],
        ["2026-04-05 19:11:30 +05:30", "Priya Nair +91 99000 44556", "Message sent", "Primary phone (iPhone)", "106.51.22.40"],
    ])
    f.append(("04_priya_account_log.csv", "account log", "Account activity for Priya Nair's number, provider response", ["log", "account"]))
    pdf(d / "05_complaint_letter.pdf", "Complaint - criminal intimidation", [
        "Complainant: Karan Malhotra", "Against: Priya Nair (former business partner)", "Date: 7 April 2026",
        "On 5 April 2026 at 19:20 Priya Nair threatened me on WhatsApp that she would ruin my business and family.",
        "Screenshot attached."])
    f.append(("05_complaint_letter.pdf", "complaint", "Complaint received at police station 7 Apr 2026", ["complaint"]))
    return f


# ----------------------------------------------------------------------------- s9 control: "I was hacked" claim
def build_s9(d: Path):
    f = []
    chat_shot(d / "01_screenshot.png", "Vikram Singh", "22 March 2026", "23:40", [
        ("in", "why r u not picking my calls", "23:10"), ("out", "Please stop calling me", "23:12"),
        ("in", "u think u can ignore me?? u will regret this, watch ur back", "23:15"),
        ("in", "i know where u live dont forget", "23:16")])
    f.append(("01_screenshot.png", "screenshot", "Screenshot submitted by complainant Ayesha Khan", ["complaint", "screenshot"]))
    rows = [("20/03/2026", "21:00", "Vikram Singh", "why r u ignoring me again??"), ("20/03/2026", "21:02", "Ayesha Khan", "I am busy."),
            ("20/03/2026", "21:03", "Vikram Singh", "busy my foot. always busy for me"), ("21/03/2026", "22:30", "Vikram Singh", "pick up the phone ayesha!!"),
            ("21/03/2026", "22:31", "Vikram Singh", "dont act smart with me"), ("21/03/2026", "22:45", "Ayesha Khan", "We are done. Please respect that."),
            ("21/03/2026", "22:47", "Vikram Singh", "u will see what happens"), ("22/03/2026", "09:15", "Vikram Singh", "good morning?? no reply again"),
            ("22/03/2026", "23:10", "Vikram Singh", "why r u not picking my calls"), ("22/03/2026", "23:12", "Ayesha Khan", "Please stop calling me"),
            ("22/03/2026", "23:15", "Vikram Singh", "u think u can ignore me?? u will regret this, watch ur back"),
            ("22/03/2026", "23:16", "Vikram Singh", "i know where u live dont forget"),
            ("23/03/2026", "10:05", "Vikram Singh", "sorry i was angry last night didnt mean it")]
    wa_export(d / "02_ayesha_chat_export.txt", rows)
    f.append(("02_ayesha_chat_export.txt", "chat", "WhatsApp export from Ayesha Khan's phone, 24 Mar 2026", ["chat", "complainant"]))
    wa_export(d / "03_vikram_chat_export.txt", rows)
    f.append(("03_vikram_chat_export.txt", "chat", "WhatsApp export from Vikram Singh's phone, seized 25 Mar 2026", ["chat", "accused"]))
    csvrows(d / "04_vikram_account_log.csv", ["Time", "Account", "Event", "Device", "IP address"], [
        ["2026-03-22 23:10:02 +05:30", "Vikram Singh +91 98111 22334", "Message sent", "Primary phone (Android)", "49.205.10.77"],
        ["2026-03-22 23:15:20 +05:30", "Vikram Singh +91 98111 22334", "Message sent", "Primary phone (Android)", "49.205.10.77"],
        ["2026-03-22 23:16:01 +05:30", "Vikram Singh +91 98111 22334", "Message sent", "Primary phone (Android)", "49.205.10.77"],
    ])
    f.append(("04_vikram_account_log.csv", "account log", "Account activity for Vikram Singh's number, provider response", ["log", "account"]))
    (d / "05_accused_statement.txt").write_text(
        "Statement of: Vikram Singh\n\nI did not send any threatening messages. My phone must have been hacked. "
        "I was asleep at 11 pm on 22 March 2026.\n", encoding="utf-8")
    f.append(("05_accused_statement.txt", "statement", "Statement recorded by investigator 25 Mar 2026", ["statement"]))
    return f


# ----------------------------------------------------------------------------- s10 SIM swap
def build_s10(d: Path):
    f = []
    (d / "01_sms_inbox.txt").write_text(
        "SMS export - phone of Deepak Joshi (+91 90080 55667)\n\n"
        "[02/04/2026 01:10] JIONET: Your SIM card has been deactivated as a new SIM was issued on your request. Not you? Call 198.\n"
        "[02/04/2026 01:25] AX-SBIOTP: 482913 is the OTP for adding a new beneficiary. Do not share it with anyone.\n"
        "[02/04/2026 01:28] AX-SBIINB: New login to SBI Online from a new device at 01:28.\n", encoding="utf-8")
    f.append(("01_sms_inbox.txt", "sms", "SMS backup restored from Deepak Joshi's cloud backup", ["sms"]))
    csvrows(d / "02_bank_statement.csv", ["Date", "Description", "Debit", "Credit", "Balance", "UTR"], [
        ["2026-04-01 18:20 +05:30", "SALARY CREDIT", "", "92,000.00", "2,14,500.00", "N091260123456"],
        ["2026-04-02 01:32 +05:30", "IMPS TO RAJESH K A/C XX4471", "95,000.00", "", "1,19,500.00", "609201325511"],
        ["2026-04-02 01:36 +05:30", "IMPS TO RAJESH K A/C XX4471", "90,000.00", "", "29,500.00", "609201338842"],
    ])
    f.append(("02_bank_statement.csv", "bank statement", "Downloaded from SBI Online by Deepak Joshi 2 Apr 2026", ["bank"]))
    pdf(d / "03_carrier_sim_record.pdf", "SIM replacement record", [
        "Subscriber: Deepak Joshi", "Mobile number: +91 90080 55667", "SIM replacement requested: 2026-04-02 00:55",
        "Store: Retail outlet 2213, Lajpat Nagar", "ID submitted: photocopy of driving licence", "New SIM activated: 2026-04-02 01:09"])
    f.append(("03_carrier_sim_record.pdf", "carrier record", "Carrier response to police notice 5 Apr 2026", ["carrier"]))
    (d / "04_victim_statement.txt").write_text(
        "Statement of: Deepak Joshi\n\nMy phone lost network at around 1 am on 2 April 2026. In the morning I saw two transfers of "
        "Rs 95,000 and Rs 90,000 to an account I do not know. I never requested a new SIM.\n", encoding="utf-8")
    f.append(("04_victim_statement.txt", "statement", "Statement recorded 2 Apr 2026", ["statement"]))
    return f


# ----------------------------------------------------------------------------- s11 sextortion email
def build_s11(d: Path):
    f = []
    eml(d / "01_extortion_email.eml", '"Unknown" <nitin.rao@inboxmail.com>', '"Nitin Rao" <nitin.rao@inboxmail.com>',
        "I have your video - read carefully", "Mon, 06 Apr 2026 03:12:00 +0000",
        "I hacked your device months ago and recorded you through your webcam. I also know your password: tiger@1987.\n"
        "Pay 1500 dollars in bitcoin to the wallet below within 48 hours or I will send the video to all your contacts.\n"
        "Wallet: bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh\nDo not reply. Do not go to the police.",
        received=False)
    f.append(("01_extortion_email.eml", "email", "Exported from Nitin Rao's mailbox", ["email", "extortion"]))
    eml(d / "02_followup_email.eml", '"Unknown" <nitin.rao@inboxmail.com>', '"Nitin Rao" <nitin.rao@inboxmail.com>',
        "Last warning", "Wed, 08 Apr 2026 02:40:00 +0000",
        "24 hours left. Pay now or the video goes viral and your family sees everything.", received=False)
    f.append(("02_followup_email.eml", "email", "Exported from Nitin Rao's mailbox", ["email", "extortion"]))
    screenshot(d / "03_breach_check.png", "Breach notification service", [
        "Email: nitin.rao@inboxmail.com", "Found in 2 data breaches", "ShopSphere breach (2021): email, password",
        "FitTrack breach (2023): email, name"], bar="https://breachcheck.example/results")
    f.append(("03_breach_check.png", "screenshot", "Screenshot taken by investigator 8 Apr 2026", ["osint"]))
    (d / "04_victim_statement.txt").write_text(
        "Statement of: Nitin Rao\n\nThe password in the email is an old password I used years ago. My laptop has a webcam cover. "
        "I have not paid anything.\n", encoding="utf-8")
    f.append(("04_victim_statement.txt", "statement", "Statement recorded 8 Apr 2026", ["statement"]))
    return f


# ----------------------------------------------------------------------------- s12 task-based job scam
def build_s12(d: Path):
    f = []
    wa_export(d / "01_job_chat.txt", [
        ("10/04/2026", "10:02", "HR Riya", "Hello, part-time job available. Complete simple tasks and earn 5000 daily from home."),
        ("10/04/2026", "10:05", "Pooja Shetty", "What do I have to do?"),
        ("10/04/2026", "10:07", "HR Riya", "Like hotel reviews. First deposit 1000 to unlock the task panel, it is refundable."),
        ("10/04/2026", "10:20", "Pooja Shetty", "Paid 1000"),
        ("10/04/2026", "18:30", "HR Riya", "Great, your commission 1450 is in the dashboard. Deposit 5000 for VIP tasks to withdraw."),
        ("11/04/2026", "11:15", "Pooja Shetty", "Paid 5000. Please release my money."),
        ("11/04/2026", "19:40", "HR Riya", "System error. Deposit 25000 security amount to unlock withdrawal, then all is returned."),
        ("12/04/2026", "09:05", "Pooja Shetty", "Paid 25000. Now please process the withdrawal."),
        ("12/04/2026", "21:00", "HR Riya", "Pay 15000 tax to withdraw. Otherwise account frozen."),
    ])
    f.append(("01_job_chat.txt", "chat", "WhatsApp export from Pooja Shetty's phone", ["chat"]))
    csvrows(d / "02_bank_statement.csv", ["Date", "Description", "Debit", "Credit", "UTR"], [
        ["2026-04-10 10:19 +05:30", "UPI/taskpanel.pay@ybl", "1,000.00", "", "410012345678"],
        ["2026-04-11 11:14 +05:30", "UPI/vip.tasks88@okicici", "5,000.00", "", "411098765432"],
        ["2026-04-12 09:04 +05:30", "UPI/secure.withdraw@paytm", "25,000.00", "", "412055443322"],
    ])
    f.append(("02_bank_statement.csv", "bank statement", "Bank statement download", ["bank"]))
    screenshot(d / "03_dashboard.png", "TaskEarn Pro - My account", [
        "Balance: Rs 38,450.00", "Withdrawal status: FROZEN", "Reason: pay tax Rs 15,000 to unlock withdrawal",
        "Support: t.me/taskearn_support"], bar="https://taskearn-pro.top/dashboard")
    f.append(("03_dashboard.png", "screenshot", "Screenshot by Pooja Shetty 12 Apr 2026", ["screenshot"]))
    return f


# ----------------------------------------------------------------------------- s13 business email compromise
def build_s13(d: Path):
    f = []
    eml(d / "01_vendor_bank_change.eml", '"Accounts - Acme Supply" <accounts@acme-supp1y.com>', '"Finance" <finance@brightbuild.in>',
        "Updated bank details for invoice INV-2207", "Tue, 14 Apr 2026 10:12:00 +0530",
        "Dear Finance team,\nOur bank account is under audit. Please change the beneficiary bank account for all future invoices to:\n"
        "Account: 50200077881122, IFSC: HDFC0009921, Name: Acme Supply Trading.\nPlease process INV-2207 today, it is urgent and confidential.\n"
        "Regards, Accounts", extra_headers={"Reply-To": "acme.accounts.desk@gmail.com"})
    f.append(("01_vendor_bank_change.eml", "email", "Finance mailbox export, BrightBuild Pvt Ltd", ["email"]))
    pdf(d / "02_invoice.pdf", "Acme Supply Pvt Ltd - Invoice INV-2207", [
        "Invoice No: INV-2207", "Invoice Date: 2026-04-10", "Amount: Rs 8,40,000.00", "Bank: ICICI Bank, Account 001105009876",
        "Payable within 30 days"])
    f.append(("02_invoice.pdf", "invoice", "Original invoice received by post", ["invoice"]))
    csvrows(d / "03_payment_register.csv", ["Date", "Payee", "Invoice", "Amount", "Account", "UTR"], [
        ["2026-04-14 15:40 +05:30", "Acme Supply Trading", "INV-2207", "8,40,000.00", "50200077881122", "HDFCR52026041488"]])
    f.append(("03_payment_register.csv", "payment register", "Finance payment register export", ["payment"]))
    eml(d / "04_real_vendor_reply.eml", '"Acme Supply Accounts" <accounts@acmesupply.in>', '"Finance" <finance@brightbuild.in>',
        "RE: payment for INV-2207", "Mon, 20 Apr 2026 11:00:00 +0530",
        "We have not received payment for INV-2207. Our bank details have never changed. We did not send any email from acme-supp1y.com.",
        auth=AUTH_PASS.format(d="acmesupply.in"))
    f.append(("04_real_vendor_reply.eml", "email", "Finance mailbox export", ["email"]))
    return f


# ----------------------------------------------------------------------------- s14 loan app harassment
def build_s14(d: Path):
    f = []
    chat_shot(d / "01_message_to_contact.png", "QuickRupee Recovery", "15 April 2026", "11:20", [
        ("in", "Your friend Manoj Pillai took loan and is not paying.", "10:02"),
        ("in", "Pay today or we message all your contacts with his photo.", "10:03"),
        ("in", "He is a fraud and a cheat, everyone will know.", "10:05")])
    f.append(("01_message_to_contact.png", "screenshot", "Screenshot from contact Sunil Das, forwarded to Manoj Pillai", ["screenshot"]))
    wa_export(d / "02_recovery_chat.txt", [
        ("14/04/2026", "20:00", "QuickRupee Recovery", "Your loan is overdue, pay today or we message all your contacts with your photo"),
        ("14/04/2026", "20:05", "Manoj Pillai", "I repaid the full amount on 12 April. Check your records."),
        ("14/04/2026", "20:10", "QuickRupee Recovery", "Pay 4500 penalty now or your morphed photo goes to everyone"),
        ("15/04/2026", "09:30", "QuickRupee Recovery", "You stupid fraud, we will humiliate you in front of your family")])
    f.append(("02_recovery_chat.txt", "chat", "WhatsApp export from Manoj Pillai's phone", ["chat"]))
    csvrows(d / "03_repayment_proof.csv", ["Date", "Description", "Debit", "UTR"], [
        ["2026-04-12 12:10 +05:30", "UPI/quickrupee.collect@axl", "6,000.00", "412233445566"]])
    f.append(("03_repayment_proof.csv", "bank statement", "Bank statement extract", ["bank"]))
    screenshot(d / "04_app_permissions.png", "App info - QuickRupee", [
        "Permissions: Contacts, Photos and media, Camera, SMS, Location", "Installed: 2 April 2026", "Loan amount: Rs 6,000 (7 days)"])
    f.append(("04_app_permissions.png", "screenshot", "Screenshot of Android app permissions, Manoj Pillai's phone", ["screenshot"]))
    return f


# ----------------------------------------------------------------------------- s15 romance / investment scam
def build_s15(d: Path):
    f = []
    wa_export(d / "01_chat.txt", [
        ("01/04/2026", "21:00", "Emily Carter", "Good evening dear, how was your day?"),
        ("01/04/2026", "21:05", "Arvind Nair", "Good, long day at work"),
        ("03/04/2026", "22:10", "Emily Carter", "My uncle taught me crypto trading. Guaranteed 40 percent monthly profit, send funds to the platform."),
        ("05/04/2026", "20:00", "Emily Carter", "Trading platform shows profit, add more funds to withdraw."),
        ("09/04/2026", "19:30", "Emily Carter", "Withdrawal needs 20 percent tax first, deposit 1,50,000 to unlock.")])
    f.append(("01_chat.txt", "chat", "WhatsApp export from Arvind Nair's phone", ["chat"]))
    screenshot(d / "02_platform.png", "GlobalCoin XTrade - Portfolio", [
        "Account: arvind.n", "Total assets: USD 18,920.44", "Withdrawal: locked - tax payment pending",
        "Deposit address: TRC20 TQ7vHk3mR8sPq2Lx9Nd4Fb6Wc1Yz5Aa8Ue"], bar="https://globalcoin-xtrade.top/portfolio")
    f.append(("02_platform.png", "screenshot", "Screenshot by Arvind Nair 9 Apr 2026", ["screenshot"]))
    csvrows(d / "03_bank_statement.csv", ["Date", "Description", "Debit", "UTR"], [
        ["2026-04-04 11:00 +05:30", "IMPS TO CRYPTOEDGE SOLUTIONS", "2,00,000.00", "604411223344"],
        ["2026-04-06 12:30 +05:30", "IMPS TO CRYPTOEDGE SOLUTIONS", "3,50,000.00", "606422334455"]])
    f.append(("03_bank_statement.csv", "bank statement", "Bank statement download", ["bank"]))
    return f


# ----------------------------------------------------------------------------- s16 fake profiles / stalking
def build_s16(d: Path):
    f = []
    screenshot(d / "01_dm_account1.png", "InstaPic - Direct", [("@fan_of_neha_22", 26, True, "#0f172a"),
               "I am watching you every day outside your office.", "You better not show your face in college again."],
               bar="https://instapic.app/direct/t/551")
    f.append(("01_dm_account1.png", "screenshot", "Screenshot by Neha Gupta", ["screenshot"]))
    screenshot(d / "02_dm_account2.png", "InstaPic - Direct", [("@neha_truth_page", 26, True, "#0f172a"),
               "Everyone will know what a disgusting person you are.", "Delete your account or I will keep posting about you."],
               bar="https://instapic.app/direct/t/602")
    f.append(("02_dm_account2.png", "screenshot", "Screenshot by Neha Gupta", ["screenshot"]))
    pdf(d / "03_platform_response.pdf", "InstaPic - response to law-enforcement request", [
        "Account: @fan_of_neha_22   Created: 2026-03-02   Recovery phone: +91 97400 88112   Recovery email: shadow.nk@mailbox.in",
        "Account: @neha_truth_page   Created: 2026-03-09   Recovery phone: +91 97400 88112   Last login IP: 157.45.66.10",
        "Account: @neha_gupta_real   Owner of complaint"])
    f.append(("03_platform_response.pdf", "platform record", "Response to police request 15 Apr 2026", ["platform"]))
    (d / "04_statement.txt").write_text("Statement of: Neha Gupta\n\nTwo new accounts have been messaging and posting about me since March. "
                                         "I think they are the same person.\n", encoding="utf-8")
    f.append(("04_statement.txt", "statement", "Statement recorded 12 Apr 2026", ["statement"]))
    return f


# ----------------------------------------------------------------------------- s17 insider exfiltration
def build_s17(d: Path):
    f = []
    csvrows(d / "01_usb_log.csv", ["Time", "User", "Host", "Event", "Device", "Files"], [
        ["2026-04-20 18:40 +05:30", "amit.k", "FIN-LT-044", "USB storage connected", "SanDisk Ultra 64GB", ""],
        ["2026-04-20 18:46 +05:30", "amit.k", "FIN-LT-044", "Files copied", "SanDisk Ultra 64GB", "client_master_2026.xlsx; pricing_q2.xlsx"],
        ["2026-04-20 18:52 +05:30", "amit.k", "FIN-LT-044", "USB storage removed", "SanDisk Ultra 64GB", ""]])
    f.append(("01_usb_log.csv", "endpoint log", "Endpoint agent export by IT security", ["log"]))
    eml(d / "02_mail_to_personal.eml", '"Amit Kapoor" <amit.kapoor@finedge.in>', '"Amit" <amitk.personal@gmail.com>',
        "docs", "Mon, 20 Apr 2026 19:05:00 +0530", "for reference", attachments=[("client_master_2026.xlsx", b"PK\x03\x04 synthetic", "application/octet-stream")],
        auth=AUTH_PASS.format(d="finedge.in"))
    f.append(("02_mail_to_personal.eml", "email", "Mail gateway journal export", ["email"]))
    pdf(d / "03_resignation.pdf", "Resignation letter", ["From: Amit Kapoor", "Date: 21 April 2026", "Last working day: 5 May 2026",
                                                         "Joining: competitor firm (name withheld)"])
    f.append(("03_resignation.pdf", "hr record", "HR file", ["hr"]))
    csvrows(d / "04_dlp_alerts.csv", ["Time", "User", "Policy", "Action", "Destination"], [
        ["2026-04-20 19:05 +05:30", "amit.k", "Client data to personal email", "Logged (not blocked)", "amitk.personal@gmail.com"]])
    f.append(("04_dlp_alerts.csv", "dlp log", "DLP console export", ["log"]))
    return f


# ----------------------------------------------------------------------------- s18 marketplace QR scam
def build_s18(d: Path):
    f = []
    wa_export(d / "01_buyer_chat.txt", [
        ("16/04/2026", "14:00", "Buyer Army Officer", "I want your sofa, I am in the army so I cannot come. I will pay full 15000."),
        ("16/04/2026", "14:05", "Lakshmi Rao", "Ok, how will you pay?"),
        ("16/04/2026", "14:07", "Buyer Army Officer", "Scan this qr code to receive the payment for your item."),
        ("16/04/2026", "14:15", "Lakshmi Rao", "Money got debited instead of credited!"),
        ("16/04/2026", "14:16", "Buyer Army Officer", "Technical issue, scan again to get refund of both payments.")])
    f.append(("01_buyer_chat.txt", "chat", "WhatsApp export from Lakshmi Rao's phone", ["chat"]))
    screenshot(d / "02_qr_code.png", "Payment QR", ["Scan to receive Rs 15,000", "UPI ID: armyhelp.desk@okhdfcbank", "Valid for 10 minutes"])
    f.append(("02_qr_code.png", "screenshot", "Image received on WhatsApp", ["screenshot"]))
    csvrows(d / "03_bank_statement.csv", ["Date", "Description", "Debit", "UTR"], [
        ["2026-04-16 14:12 +05:30", "UPI/armyhelp.desk@okhdfcbank", "15,000.00", "416012121212"]])
    f.append(("03_bank_statement.csv", "bank statement", "Bank statement download", ["bank"]))
    return f


# ----------------------------------------------------------------------------- s19 ransomware
def build_s19(d: Path):
    f = []
    (d / "01_ransom_note.txt").write_text(
        "YOUR FILES ARE ENCRYPTED\n\nAll your files have been locked. Your files are locked, contact us on tor to pay the ransom.\n"
        "Pay 2 BTC within 72 hours or your data is published.\nContact: lockbitz_support@onionmail.org\n", encoding="utf-8")
    f.append(("01_ransom_note.txt", "ransom note", "Copied from file server desktop by IT", ["ransomware"]))
    csvrows(d / "02_server_events.csv", ["Time", "Host", "Event", "Account", "Source IP"], [
        ["2026-04-22 02:10 +05:30", "FS-01", "RDP sign-in", "administrator", "185.220.101.45"],
        ["2026-04-22 02:18 +05:30", "FS-01", "Backup service stopped", "administrator", "185.220.101.45"],
        ["2026-04-22 02:31 +05:30", "FS-01", "Mass file rename to .locked (18,442 files)", "administrator", "local"]])
    f.append(("02_server_events.csv", "server log", "Windows event log export by IT", ["log"]))
    eml(d / "03_attacker_email.eml", '"Support" <lockbitz_support@onionmail.org>', '"IT Head" <it.head@medicore.in>',
        "Your network", "Wed, 22 Apr 2026 09:00:00 +0530",
        "We have your data. Pay the ransom to get the decryption key. Last warning, pay now or I publish the documents.", received=False)
    f.append(("03_attacker_email.eml", "email", "IT mailbox export", ["email"]))
    return f


# ----------------------------------------------------------------------------- s20 fake payment proof
def build_s20(d: Path):
    f = []
    img_path = d / "01_payment_screenshot.jpg"
    screenshot(img_path, "Payment successful", ["Paid to: Imran Sheikh", "Amount: Rs 42,000.00", "UTR: 6123 0098 1177",
                                               "Date: 18 Apr 2026, 16:42", "Status: SUCCESS"], fmt="JPEG", width=800, bg="#f0fdf4")
    im = Image.open(img_path)
    exif = Image.Exif()
    exif[0x0131] = "Snapseed 2.21"
    im.save(img_path, "JPEG", quality=90, exif=exif)
    f.append(("01_payment_screenshot.jpg", "screenshot", "Sent by buyer on WhatsApp as proof of payment", ["payment", "screenshot"]))
    wa_export(d / "02_chat.txt", [
        ("18/04/2026", "16:30", "Buyer Sameer", "I am sending 42000 for the laptop now"),
        ("18/04/2026", "16:44", "Buyer Sameer", "Done, check screenshot. Please hand over the laptop to my driver."),
        ("18/04/2026", "16:50", "Imran Sheikh", "Not reflecting in my account yet"),
        ("18/04/2026", "16:52", "Buyer Sameer", "Bank server delay, it will come by night. Driver is waiting.")])
    f.append(("02_chat.txt", "chat", "WhatsApp export from Imran Sheikh's phone", ["chat"]))
    csvrows(d / "03_bank_statement.csv", ["Date", "Description", "Debit", "Credit", "UTR"], [
        ["2026-04-18 11:05 +05:30", "UPI/swiggy", "420.00", "", "410811223344"],
        ["2026-04-19 10:00 +05:30", "NEFT/SALARY", "", "55,000.00", "N109260001122"]])
    f.append(("03_bank_statement.csv", "bank statement", "Imran Sheikh's bank statement 18-19 Apr", ["bank"]))
    return f


TRIAL_BUILDERS = {"s7-whatsapp-impersonation": build_s7, "s8-fabricated-screenshot": build_s8, "s9-claimed-hack-control": build_s9,
                  "s10-sim-swap": build_s10, "s11-sextortion-email": build_s11, "s12-task-job-scam": build_s12,
                  "s13-business-email-compromise": build_s13, "s14-loan-app-harassment": build_s14,
                  "s15-romance-investment-scam": build_s15, "s16-fake-profile-stalking": build_s16,
                  "s17-insider-exfiltration": build_s17, "s18-marketplace-qr-scam": build_s18, "s19-ransomware": build_s19,
                  "s20-fake-payment-proof": build_s20}
