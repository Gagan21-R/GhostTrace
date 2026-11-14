"""Builds the five synthetic Scenario Lab datasets (plus one negative-control variant).

All people, companies, domains, phone numbers and accounts are fictional. Files are written
in their native formats (EML, PDF, DOCX, XLSX, CSV, JSON, WhatsApp TXT, PNG/JPG screenshots,
WAV audio) so the real extraction pipeline - including OCR and speech-to-text - is exercised.

Run:  python -m app.scenarios.builder   (idempotent; rebuilds every dataset)
"""
from __future__ import annotations

import csv
import hashlib
import json
import platform
import shutil
import subprocess
from email.message import EmailMessage
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "scenario_data"


# ----------------------------------------------------------------------------- file helpers
def _font(size, bold=False):
    for p in (["C:/Windows/Fonts/arialbd.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"] if bold else
              ["C:/Windows/Fonts/arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]):
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default(size)


def screenshot(path: Path, title: str, lines: list[str | tuple], width=1000, bar: str | None = None, fmt="PNG",
               bg="#ffffff", chrome="#e2e8f0"):
    """Render a clean UI-style screenshot. A line may be (text, size, bold, color)."""
    rows = [(l, 26, False, "#0f172a") if isinstance(l, str) else l for l in lines]
    h = 140 + sum(int(r[1] * 1.75) for r in rows) + 40
    img = Image.new("RGB", (width, h), bg)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, width, 64], fill=chrome)
    if bar:
        d.rounded_rectangle([110, 14, width - 30, 50], radius=16, fill="#ffffff")
        d.text((130, 20), bar, font=_font(22), fill="#334155")
    for i, c in enumerate(("#ef4444", "#f59e0b", "#22c55e")):
        d.ellipse([20 + i * 26, 24, 36 + i * 26, 40], fill=c)
    d.text((40, 84), title, font=_font(34, True), fill="#0f172a")
    y = 140
    for text, size, bold, color in rows:
        d.text((40, y), text, font=_font(size, bold), fill=color)
        y += int(size * 1.75)
    img.save(path, fmt, quality=92) if fmt == "JPEG" else img.save(path, fmt)


def eml(path: Path, frm, to, subject, date, body, extra_headers: dict | None = None, attachments=None, received=True, auth=None):
    m = EmailMessage()
    if received:
        m["Received"] = f"from mail-out.{frm.split('@')[-1].rstrip('>')} by mx.inbox.example; {date}"
    if auth:
        m["Authentication-Results"] = auth
    m["From"] = frm
    m["To"] = to
    m["Subject"] = subject
    m["Date"] = date
    m["Message-ID"] = "<" + hashlib.md5((subject + date).encode()).hexdigest()[:16] + "@" + frm.split("@")[-1].rstrip(">") + ">"
    for k, v in (extra_headers or {}).items():
        m[k] = v
    m.set_content(body)
    for name, data, mt in attachments or []:
        maintype, subtype = mt.split("/")
        m.add_attachment(data, maintype=maintype, subtype=subtype, filename=name)
    path.write_bytes(bytes(m))


def pdf(path: Path, title: str, lines: list[str], meta_date="D:20260302112000+05'30'"):
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    c = canvas.Canvas(str(path), pagesize=A4)
    c.setTitle(title)
    c.setCreator("GhostTrace synthetic dataset")
    w, h = A4
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, h - 60, title)
    c.setFont("Helvetica", 11)
    y = h - 95
    for l in lines:
        if y < 60:
            c.showPage(); c.setFont("Helvetica", 11); y = h - 60
        c.drawString(50, y, l)
        y -= 17
    c.save()


def docx_file(path: Path, title: str, paras: list[str]):
    import docx
    d = docx.Document()
    d.add_heading(title, level=1)
    for p in paras:
        d.add_paragraph(p)
    d.core_properties.author = "Synthetic dataset"
    d.save(str(path))


def csv_file(path: Path, rows: list[list]):
    with open(path, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows(rows)


def xlsx_file(path: Path, sheet: str, rows: list[list]):
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = sheet
    for r in rows:
        ws.append(r)
    wb.save(str(path))


def tts_wav(path: Path, text: str) -> bool:
    """Synthesise speech with the Windows SAPI voice (no network). Returns False elsewhere."""
    if platform.system() != "Windows":
        return False
    ps = ("Add-Type -AssemblyName System.Speech; $s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
          f"$s.Rate = -1; $s.SetOutputToWaveFile('{str(path)}'); $s.Speak(@'\n{text}\n'@); $s.Dispose()")
    try:
        subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=True, timeout=120, capture_output=True)
        return path.exists() and path.stat().st_size > 1000
    except Exception:
        return False


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


AUTH_PASS = "mx.inbox.example; spf=pass smtp.mailfrom={d}; dkim=pass header.d={d}; dmarc=pass"


def quote(path: Path) -> str:
    """Body of an existing EML, quoted as a mail client does when forwarding."""
    import email as _e
    import email.policy as _p
    m = _e.message_from_bytes(path.read_bytes(), policy=_p.default)
    body = m.get_body(preferencelist=("plain",)).get_content()
    head = f"---------- Forwarded message ---------\nFrom: {m['From']}\nDate: {m['Date']}\nSubject: {m['Subject']}\nTo: {m['To']}\n\n"
    return head + body


def make_video(path: Path, slides: list[tuple[float, list[str]]], speech: str | None, fps: int = 2) -> bool:
    """Synthetic screen recording: text slides (H.264) plus an optional synthesised speech track (AAC)."""
    import wave

    import av
    import numpy as np
    wav = path.with_suffix(".tmp.wav")
    has_audio = bool(speech) and tts_wav(wav, speech)
    try:
        out = av.open(str(path), "w")
        vs = out.add_stream("h264", rate=fps)
        vs.width, vs.height, vs.pix_fmt = 960, 540, "yuv420p"
        as_ = None
        if has_audio:
            with wave.open(str(wav)) as w:
                sr, ch, raw = w.getframerate(), w.getnchannels(), w.readframes(w.getnframes())
            pcm = np.frombuffer(raw, dtype=np.int16)
            if ch > 1:
                pcm = pcm.reshape(-1, ch)[:, 0]
            as_ = out.add_stream("aac", rate=sr)
            as_.layout = "mono"
        for dur, lines in slides:
            img = Image.new("RGB", (960, 540), "#0f172a")
            d = ImageDraw.Draw(img)
            y = 120
            for i, l in enumerate(lines):
                d.text((60, y), l, font=_font(40 if i == 0 else 32, i == 0), fill="#ffffff" if i == 0 else "#cbd5e1")
                y += 70
            frame = av.VideoFrame.from_image(img)
            for _ in range(int(dur * fps)):
                for p in vs.encode(frame):
                    out.mux(p)
        for p in vs.encode():
            out.mux(p)
        if as_ is not None:
            step = 1024
            for i in range(0, len(pcm), step):
                chunk = pcm[i:i + step]
                af = av.AudioFrame.from_ndarray(chunk.reshape(1, -1), format="s16", layout="mono")
                af.sample_rate = sr
                for p in as_.encode(af):
                    out.mux(p)
            for p in as_.encode():
                out.mux(p)
        out.close()
        return path.exists() and path.stat().st_size > 2000
    except Exception as e:
        print("video build failed:", e)
        return False
    finally:
        if wav.exists():
            wav.unlink()


# ============================================================================= S1 phishing
def build_s1(d: Path) -> list[dict]:
    files = []
    eml(d / "01_kyc_email.eml", '"HDFC Bank Alerts" <alerts@hdfc-secure-kyc.xyz>', '"Ananya Rao" <ananya.rao@mailbox.in>',
        "Urgent: Your NetBanking will be blocked - complete KYC today", "Tue, 10 Mar 2026 09:12:00 +0530",
        "Dear Customer,\n\nYour NetBanking access will be BLOCKED within 24 hours because your KYC is incomplete.\n"
        "Complete verification now: https://hdfc-secure-kyc.xyz/verify?id=88213\n\n"
        "For assistance call or WhatsApp our KYC desk on +91 98765 43210.\n"
        "Please find the KYC form attached and keep it ready.\n\nHDFC Bank KYC Team",
        extra_headers={"Reply-To": "support@kyc-update-help.top", "Return-Path": "<bounce@mailer-kyc.top>"}, auth=None)
    files.append(("01_kyc_email.eml", "email", "Victim's mailbox export (EML) by investigator", ["phishing", "email"]))

    screenshot(d / "02_phishing_site.png", "HDFC Bank - KYC Verification", [
        "Complete your KYC to avoid account suspension",
        "Customer ID: 4471 2290",
        "Verification fee: Rs 24,999.00 (fully refundable)",
        "Pay to UPI ID: kycdesk.verify@okaxis",
        "Helpline: +91 98765 43210",
        ("Session expires in 09:59", 22, False, "#b91c1c"),
    ], bar="https://hdfc-secure-kyc.xyz/verify?id=88213")
    files.append(("02_phishing_site.png", "screenshot", "Screenshot captured by victim on phone, shared via email", ["website"]))

    (d / "03_whatsapp_chat.txt").write_text(
        "10/03/2026, 09:31 - Ananya Rao: Hi, I got an email about KYC. Is this the HDFC KYC desk?\n"
        "10/03/2026, 09:33 - +91 98765 43210: Yes madam. Your account will be blocked today. Pay the refundable verification fee of ₹24,999 to UPI kycdesk.verify@okaxis\n"
        "10/03/2026, 09:34 - +91 98765 43210: <Media omitted>\n"
        "10/03/2026, 09:35 - +91 98765 43210: Scan this QR and send screenshot after payment\n"
        "10/03/2026, 09:48 - Ananya Rao: Paid ₹24,999. UPI Ref No: 407215583921\n"
        "10/03/2026, 09:52 - +91 98765 43210: Received. KYC will be updated in 2 hours\n"
        "11/03/2026, 18:05 - Ananya Rao: My account is still showing KYC pending. Please refund my money\n"
        "11/03/2026, 18:20 - +91 98765 43210: Madam we will refund ₹24,999 within 48 hours\n"
        "13/03/2026, 10:02 - Ananya Rao: No refund yet. Please call me\n", encoding="utf-8")
    files.append(("03_whatsapp_chat.txt", "chat", "WhatsApp 'Export chat' (without media) from victim's phone", ["chat"]))

    screenshot(d / "04_payment_receipt.png", "Payment Successful", [
        ("Amount Paid: Rs 24,999.00", 30, True, "#15803d"),
        "Paid to: KYC Desk Verify",
        "UPI ID: kycdesk.verify@okaxis",
        "UPI Ref No: 407215583921",
        "Date: 10 Mar 2026, 09:47 AM",
        "From: Ananya Rao (A/c XX4821)",
    ], width=900)
    files.append(("04_payment_receipt.png", "payment", "Screenshot from victim's UPI app", ["payment", "receipt"]))

    csv_file(d / "05_bank_statement.csv", [
        ["Transaction Date", "Description", "Debit", "Credit", "UTR", "Balance"],
        ["2026-03-08 14:02:10", "POS/ANNAPURNA STORES", "1240.00", "", "406812339011", "81210.55"],
        ["2026-03-09 10:15:44", "NEFT CR SALARY ACME", "", "64000.00", "406903211874", "145210.55"],
        ["2026-03-10 09:47:12", "UPI/DR/KYC DESK VERI/okaxis", "24999.00", "", "407215538921", "120211.55"],
        ["2026-03-11 20:30:02", "UPI/DR/ZOMATO", "389.00", "", "407320116522", "119822.55"],
        ["2026-03-14 09:00:00", "ATM WDL MG ROAD", "5000.00", "", "407500772014", "114822.55"],
    ])
    files.append(("05_bank_statement.csv", "bank", "Statement downloaded from NetBanking by investigator with victim", ["bank"]))

    (d / "06_bank_sms_alert.txt").write_text(
        "SMS from HDFCBK received 10-03-2026 09:47\n\n"
        "HDFC Bank: Rs.24999.00 debited from A/c XX4821 on 10-03-26 to VPA kycdesk.verify@okaxis. "
        "UTR 407215538921. Not you? Call 18002586161\n", encoding="utf-8")
    files.append(("06_bank_sms_alert.txt", "bank", "SMS transcribed from victim's phone by investigator", ["bank", "notification"]))

    docx_file(d / "07_victim_statement.docx", "Statement of complainant", [
        "Statement of: Ananya Rao",
        "On the morning of 10 March 2026 I received an email saying my NetBanking would be blocked because of KYC.",
        "I clicked the link in the email and it opened a page that looked like the HDFC Bank website.",
        "I contacted the number on the page on WhatsApp. The person asked me to pay a refundable verification fee.",
        "I paid Rs 24,999 on 11 March 2026 at about 9:45 AM using UPI.",
        "I did not share my OTP or PIN with anyone.",
        "The person promised a refund but I have not received any money back.",
    ])
    files.append(("07_victim_statement.docx", "statement", "Signed statement recorded at police station", ["statement"]))

    eml(d / "08_followup_email.eml", '"KYC Refund Desk" <refunds@kyc-update-help.top>', '"Ananya Rao" <ananya.rao@mailbox.in>',
        "Refund initiated - Ref RFD-20931", "Thu, 12 Mar 2026 16:40:00 +0530",
        "Dear Customer,\n\nYour refund of Rs 24,999 has been initiated and will be credited within 5 working days.\n"
        "See attached refund confirmation.\nRef: RFD-20931\n\nKYC Refund Desk", auth=None)
    files.append(("08_followup_email.eml", "email", "Victim's mailbox export (EML)", ["follow-up"]))

    eml(d / "09_flipkart_newsletter.eml", '"Flipkart" <noreply@flipkart.com>', '"Ananya Rao" <ananya.rao@mailbox.in>',
        "Big Saving Days start Friday", "Mon, 09 Mar 2026 08:00:00 +0530",
        "Hi Ananya,\n\nBig Saving Days start this Friday. Browse deals at https://www.flipkart.com/offers\n\nTeam Flipkart",
        auth=AUTH_PASS.format(d="flipkart.com"))
    files.append(("09_flipkart_newsletter.eml", "email", "Victim's mailbox export (EML) - unrelated control item", ["unrelated"]))

    (d / "04b_receipt_copy.png").write_bytes((d / "04_payment_receipt.png").read_bytes())
    files.append(("04b_receipt_copy.png", "payment", "Same screenshot sent again by victim via WhatsApp to investigator", ["payment", "copy"]))
    eml(d / "11_forward_to_bank.eml", '"Ananya Rao" <ananya.rao@mailbox.in>', '"Phishing Reports" <report-phishing@securebank.example>',
        "Fwd: Urgent: Your NetBanking will be blocked - complete KYC today", "Wed, 11 Mar 2026 19:05:00 +0530",
        "Is this email genuine? I paid them yesterday.\n\n" + quote(d / "01_kyc_email.eml"), auth=AUTH_PASS.format(d="mailbox.in"))
    files.append(("11_forward_to_bank.eml", "email", "Victim's sent-mail export", ["forward"]))
    if tts_wav(d / "10_voicemail.wav", "Hello madam, this is the K Y C desk from H D F C bank. Your net banking will be blocked "
                                       "today. Please call back immediately on nine eight seven six five, four three two one zero."):
        files.append(("10_voicemail.wav", "audio", "Voicemail exported from victim's phone", ["audio", "voicemail"]))
    return files


# ============================================================================= S2 account compromise
def build_s2(d: Path, sparse=False) -> list[dict]:
    files = []
    if not sparse:
        eml(d / "01_new_signin_alert.eml", '"CloudVault Security" <security@cloudvault.io>', '"Rahul Mehta" <rahul.mehta@inboxmail.com>',
            "New sign-in to your CloudVault account", "Sat, 14 Mar 2026 02:16:05 +0530",
            "We noticed a new sign-in to your CloudVault account.\n\nTime: 14 Mar 2026 02:14 IST\nDevice: Windows 11 Chrome 133\n"
            "Location: Lagos, Nigeria (approximate)\nIP address: 102.89.34.17\n\nIf this wasn't you, secure your account now.",
            auth=AUTH_PASS.format(d="cloudvault.io"))
        files.append(("01_new_signin_alert.eml", "email", "Exported from account holder's mailbox", ["security alert"]))
        eml(d / "02_password_changed.eml", '"CloudVault Security" <security@cloudvault.io>', '"Rahul Mehta" <rahul.mehta@inboxmail.com>',
            "Your CloudVault password was changed", "Sat, 14 Mar 2026 02:21:10 +0530",
            "The password for your CloudVault account was changed.\n\nTime: 14 Mar 2026 02:20 IST\nIP address: 102.89.34.17\n\n"
            "If you did not change your password, start account recovery.", auth=AUTH_PASS.format(d="cloudvault.io"))
        files.append(("02_password_changed.eml", "email", "Exported from account holder's mailbox", ["password reset"]))
        eml(d / "03_recovery_email_changed.eml", '"CloudVault Security" <security@cloudvault.io>', '"Rahul Mehta" <rahul.mehta@inboxmail.com>',
            "Recovery email changed", "Sat, 14 Mar 2026 02:26:40 +0530",
            "The recovery email for your account was changed to r.mehta.secure@protonmail-mail.net\n\nTime: 14 Mar 2026 02:25 IST\n"
            "IP address: 102.89.34.17", auth=AUTH_PASS.format(d="cloudvault.io"))
        files.append(("03_recovery_email_changed.eml", "email", "Exported from account holder's mailbox", ["recovery"]))
        csv_file(d / "04_session_log.csv", [
            ["Timestamp", "Event", "IP", "Device", "Location", "Session ID", "Result"],
            ["2026-03-12 19:02:11+05:30", "login", "49.36.12.88", "Android 14 CloudVault app", "Mumbai, IN", "s-90121", "success"],
            ["2026-03-13 08:15:40+05:30", "login", "49.36.12.88", "Android 14 CloudVault app", "Mumbai, IN", "s-90388", "success"],
            ["2026-03-14 02:14:51+05:30", "login", "102.89.34.17", "Linux x86_64 Firefox 136", "Lagos, NG", "s-90410", "success"],
            ["2026-03-14 02:20:30+05:30", "password changed", "102.89.34.17", "Linux x86_64 Firefox 136", "Lagos, NG", "s-90410", "success"],
            ["# export truncated: showing first 4 events of requested range", "", "", "", "", "", ""],
        ])
        files.append(("04_session_log.csv", "log", "CloudVault 'Download account activity' export requested 15 Mar", ["log"]))
        (d / "05_otp_chat.txt").write_text(
            "14/03/2026, 01:58 - +44 7700 900123: CloudVault Security: we detected unusual activity. Reply with the 6-digit verification code sent to you to keep your account active.\n"
            "14/03/2026, 02:03 - Rahul Mehta: Here is the verification code 482913\n"
            "14/03/2026, 02:04 - +44 7700 900123: Thank you, your account is now protected.\n"
            "14/03/2026, 02:30 - +44 7700 900123: This message was deleted\n"
            "14/03/2026, 07:12 - Rahul Mehta: Why did I get password change emails??\n", encoding="utf-8")
        files.append(("05_otp_chat.txt", "chat", "WhatsApp export from account holder's phone", ["chat", "otp"]))
    docx_file(d / "06_statement_rahul.docx", "Statement of account holder", [
        "Statement of: Rahul Mehta",
        "I was asleep between 11 PM on 13 March and 7 AM on 14 March 2026.",
        "I did not sign in to CloudVault during that time and I did not change my password.",
        "I never shared any verification code with anyone.",
        "I only use my Android phone for CloudVault.",
    ])
    files.append(("06_statement_rahul.docx", "statement", "Statement taken by investigator on 15 Mar", ["statement"]))
    screenshot(d / "07_device_list.png", "Devices signed in to your account", [
        "Pixel 7 - Android 14 - Mumbai, IN - Active now",
        "Unknown device - Linux - Lagos, NG - 14 Mar 2026 02:14",
        ("Sign out of all other sessions", 22, True, "#1d4ed8"),
    ], bar="https://account.cloudvault.io/security/devices")
    files.append(("07_device_list.png", "screenshot", "Screenshot by account holder on 15 Mar 08:10", ["devices"]))
    if not sparse:
        eml(d / "08_product_update.eml", '"CloudVault" <news@cloudvault.io>', '"Rahul Mehta" <rahul.mehta@inboxmail.com>',
            "What's new in CloudVault - March", "Tue, 03 Mar 2026 10:00:00 +0530",
            "New: shared folders and faster sync. Read more at https://cloudvault.io/blog/march", auth=AUTH_PASS.format(d="cloudvault.io"))
        files.append(("08_product_update.eml", "email", "Exported from account holder's mailbox - unrelated control", ["unrelated"]))
    return files


# ============================================================================= S3 harassment / preservation
def build_s3(d: Path) -> list[dict]:
    files = []
    screenshot(d / "01_post_screenshot_1.png", "SocialHub", [
        ("@void_whisper", 26, True, "#0f172a"),
        "Posted 5 Mar 2026 21:40",
        "Everyone should know what Meera Iyer really is.",
        "I will expose everything this week.",
        ("128 likes  -  41 replies", 20, False, "#64748b"),
    ], bar="https://socialhub.app/void_whisper/post/88123")
    files.append(("01_post_screenshot_1.png", "screenshot", "Captured by Meera Iyer on laptop (Firefox full-page)", ["post"]))
    screenshot(d / "02_post_screenshot_2.png", "SocialHub", [
        ("@void_whisper", 26, True, "#0f172a"),
        "Posted 6 Mar 2026 22:05",
        "You will regret ignoring me @meera.iyer",
        ("12 likes  -  3 replies", 20, False, "#64748b"),
    ], bar="https://socialhub.app/void_whisper/post/88190")
    files.append(("02_post_screenshot_2.png", "screenshot", "Captured by Meera Iyer on laptop (Firefox full-page)", ["post"]))
    msgs = []
    texts = {1: ("void_whisper", "2026-03-04T23:10:00+05:30", "Why are you ignoring my messages?"),
             2: ("meera.iyer", "2026-03-04T23:15:00+05:30", "Please stop contacting me."),
             3: ("void_whisper", "2026-03-05T00:02:00+05:30", "You don't get to decide that."),
             4: ("void_whisper", "2026-03-05T21:45:00+05:30", "Check my profile. Everyone will see soon."),
             7: ("void_whisper", "2026-03-06T22:10:00+05:30", "I have your photos. I will leak them."),
             8: ("void_whisper", "2026-03-06T22:11:00+05:30", ""),
             10: ("meera.iyer", "2026-03-07T09:00:00+05:30", "I am reporting this account."),
             11: ("void_whisper", "2026-03-07T09:05:00+05:30", "Watch your back."),
             12: ("void_whisper", "2026-03-07T09:06:00+05:30", "This message was deleted"),
             14: ("meera.iyer", "2026-03-08T11:30:00+05:30", "Saving everything for the police.")}
    for i, (s, t, x) in texts.items():
        m = {"id": i, "sender": s, "timestamp": t, "text": x}
        if i == 8:
            m["attachments"] = [{"name": "photo_0306.jpg", "type": "image/jpeg", "included": False}]
        if i == 12:
            m["deleted"] = True
        msgs.append(m)
    (d / "03_dm_export.json").write_text(json.dumps({
        "platform": "SocialHub Direct Messages", "conversation": "void_whisper <> meera.iyer",
        "participants": ["void_whisper", "meera.iyer"],
        "export_info": {"exported_by": "meera.iyer", "exported_at": "2026-03-08T12:00:00+05:30", "complete": False,
                        "total_messages": 14, "note": "Export generated after some messages were unsent by the other party"},
        "messages": msgs}, indent=2), encoding="utf-8")
    files.append(("03_dm_export.json", "chat", "SocialHub 'Download your data' DM export", ["dm", "chat"]))
    screenshot(d / "04_downloaded_media.jpg", "Image received via DM (downloaded)", [
        "[photo content withheld - personal image]", "Caption overlay: 'leaked soon'"], fmt="JPEG", width=800, bg="#f8fafc")
    files.append(("04_downloaded_media.jpg", "media", "Downloaded from SocialHub DM on 7 Mar by Meera Iyer", ["media"]))
    (d / "06_urls.txt").write_text(
        "Reported URLs (compiled by Meera Iyer, 8 Mar 2026)\n\n"
        "Profile: https://socialhub.app/void_whisper\n"
        "Post 1: https://socialhub.app/void_whisper/post/88123\n"
        "Post 2: https://socialhub.app/void_whisper/post/88190\n"
        "Post 3: https://socialhub.app/void_whisper/post/88245 (said 'watch your back' - deleted 8 Mar morning, not captured)\n",
        encoding="utf-8")
    files.append(("06_urls.txt", "urls", "List typed by complainant", ["urls"]))
    (d / "07_victim_statement.txt").write_text(
        "Statement of: Meera Iyer\n\n"
        "The posts about me started on 5 March 2026 from the account @void_whisper.\n\n"
        "A third post on 7 March 2026 said 'watch your back'. It was deleted the next morning before I could screenshot it.\n\n"
        "The account also sent me a photo by direct message and threatened to leak more. I downloaded the photo.\n\n"
        "Some of the messages were unsent by the sender before I exported the conversation.\n", encoding="utf-8")
    files.append(("07_victim_statement.txt", "statement", "Statement recorded by investigator 9 Mar", ["statement"]))
    (d / "01b_post_screenshot_1_copy.png").write_bytes((d / "01_post_screenshot_1.png").read_bytes())
    files.append(("01b_post_screenshot_1_copy.png", "screenshot", "Copy found in complainant's cloud backup", ["post", "copy"]))
    Image.open(d / "02_post_screenshot_2.png").convert("RGB").save(d / "02b_post_screenshot_2_resaved.jpg", "JPEG", quality=80)
    files.append(("02b_post_screenshot_2_resaved.jpg", "screenshot", "Version forwarded by a friend (re-compressed by messaging app)", ["post", "copy"]))
    screenshot(d / "08_comment_screenshot.png", "SocialHub - replies", [
        ("@void_whisper replied", 24, True, "#0f172a"), "Nobody will believe her anyway.",
        ("6 Mar 2026 22:40", 20, False, "#64748b")], bar="https://socialhub.app/void_whisper/post/88190#replies")
    files.append(("08_comment_screenshot.png", "screenshot", None, ["comment"]))
    return files


def build_s3_log(d: Path):
    """Collection log written after the screenshots exist - one hash is deliberately wrong."""
    h1 = sha(d / "01_post_screenshot_1.png")
    wrong = hashlib.sha256(b"different-version-of-screenshot-2").hexdigest()
    h3 = sha(d / "03_dm_export.json")
    csv_file(d / "05_collection_log.csv", [
        ["Item", "URL", "Collected At", "Collected By", "Method", "SHA256"],
        ["01_post_screenshot_1.png", "https://socialhub.app/void_whisper/post/88123", "2026-03-05 22:05", "Meera Iyer", "Firefox full-page screenshot", h1],
        ["02_post_screenshot_2.png", "https://socialhub.app/void_whisper/post/88190", "2026-03-06 22:30", "Meera Iyer", "Firefox full-page screenshot", wrong],
        ["03_dm_export.json", "SocialHub data download", "2026-03-08 12:00", "Meera Iyer", "Platform export", h3],
        ["(post 88245)", "https://socialhub.app/void_whisper/post/88245", "", "", "NOT CAPTURED - deleted before capture", ""],
    ])


# ============================================================================= S4 whistleblower retaliation
def build_s4(d: Path) -> list[dict]:
    files = []
    dom = "northwind-analytics.com"
    eml(d / "01_complaint_email.eml", f'"Priya Nair" <priya.nair@{dom}>', f'"Ethics Office" <ethics@{dom}>',
        "Confidential complaint - irregular vendor payments", "Fri, 06 Mar 2026 18:42:00 +0530",
        "Dear Ethics Office,\n\nI am reporting concerns about vendor invoices approved by Arjun Sethi in February 2026. "
        "Several invoices from Brightline Supplies appear to be duplicated.\n\nI request that this complaint be treated confidentially.\n\nPriya Nair",
        auth=AUTH_PASS.format(d=dom))
    files.append(("01_complaint_email.eml", "email", "Exported from Ethics Office mailbox by investigator", ["complaint"]))
    eml(d / "02_hr_acknowledgement.eml", f'"Kavita Menon" <kavita.menon@{dom}>', f'"Priya Nair" <priya.nair@{dom}>',
        "Re: Confidential complaint", "Mon, 09 Mar 2026 10:05:00 +0530",
        "Dear Priya,\n\nWe received your complaint on 9 March 2026 and it has been assigned to the investigations team.\n\nKavita Menon\nHR Business Partner",
        auth=AUTH_PASS.format(d=dom))
    files.append(("02_hr_acknowledgement.eml", "email", "Exported from Priya Nair's mailbox", ["hr"]))
    eml(d / "03_hr_access_reply.eml", f'"Kavita Menon" <kavita.menon@{dom}>', f'"Priya Nair" <priya.nair@{dom}>',
        "Re: Finance SharePoint access", "Mon, 16 Mar 2026 15:20:00 +0530",
        "Dear Priya,\n\nRegarding your query, your access to the Finance SharePoint was changed on 3 March 2026 as part of the "
        "scheduled quarterly access review, before your complaint was raised.\n\nKavita Menon", auth=AUTH_PASS.format(d=dom))
    files.append(("03_hr_access_reply.eml", "email", "Exported from Priya Nair's mailbox", ["hr", "access"]))
    csv_file(d / "04_access_log.csv", [
        ["Timestamp", "User", "Resource", "Action", "Changed By", "Ticket", "Reason"],
        ["2026-02-02 10:00", "Priya Nair", "Finance-SharePoint", "Access granted (Editor)", "it.admin", "CHG-1102", "Onboarding to finance analytics"],
        ["2026-03-02 11:30", "Rohan Das", "Finance-SharePoint", "Access revoked", "it.admin", "CHG-1180", "Quarterly access review"],
        ["2026-03-11 09:42", "Priya Nair", "Finance-SharePoint", "Access revoked", "arjun.sethi", "", ""],
        ["2026-03-11 09:44", "Priya Nair", "Project-Atlas", "Role downgraded Editor to Viewer", "arjun.sethi", "", ""],
    ])
    files.append(("04_access_log.csv", "log", "IAM audit export provided by IT on 17 Mar", ["access log"]))
    pdf(d / "05_access_review_policy.pdf", "Access Review Policy v3.2", [
        "Northwind Analytics Pvt Ltd - Information Security",
        "Policy owner: IT Security   Effective: 01 Jan 2026",
        "",
        "1. Access to finance systems is recertified in a quarterly access review.",
        "2. The quarterly review is scheduled in the first week of each quarter (January, April, July, October).",
        "3. Every revocation must reference an approved change ticket and a documented reason.",
        "4. Out-of-cycle revocations require approval from the system owner.",
    ], meta_date=None)
    files.append(("05_access_review_policy.pdf", "policy", "Intranet policy library download", ["policy"]))
    (d / "06_team_chat.json").write_text(json.dumps({
        "platform": "Northwind Teams export", "conversation": "Atlas leads", "participants": ["Arjun Sethi", "Neha Kapoor"],
        "export_info": {"complete": True, "exported_by": "IT eDiscovery"},
        "messages": [
            {"id": 1, "sender": "Arjun Sethi", "timestamp": "2026-03-07T09:12:00+05:30", "text": "Let's keep Priya off the Atlas steering calls for now."},
            {"id": 2, "sender": "Neha Kapoor", "timestamp": "2026-03-07T09:20:00+05:30", "text": "Ok. Any reason I should give her?"},
            {"id": 3, "sender": "Arjun Sethi", "timestamp": "2026-03-07T09:21:00+05:30", "text": "Just say the meeting is leads-only now."},
            {"id": 4, "sender": "Arjun Sethi", "timestamp": "2026-03-10T17:45:00+05:30", "text": "Also remove her from the finance sharepoint group."},
        ]}, indent=2), encoding="utf-8")
    files.append(("06_team_chat.json", "chat", "eDiscovery export of Teams channel", ["chat"]))
    xlsx_file(d / "07_meeting_records.xlsx", "Meetings", [
        ["Date", "Meeting", "Organiser", "Invitees", "Notes"],
        ["2026-02-27 11:00", "Atlas steering", "Arjun Sethi", "Arjun Sethi, Neha Kapoor, Priya Nair, Rohan Das", "Regular meeting"],
        ["2026-03-06 11:00", "Atlas steering", "Arjun Sethi", "Arjun Sethi, Neha Kapoor, Priya Nair, Rohan Das", "Regular meeting"],
        ["2026-03-13 11:00", "Atlas steering", "Arjun Sethi", "Arjun Sethi, Neha Kapoor, Rohan Das", "Priya Nair removed from invite list"],
        ["2026-03-20 11:00", "Atlas steering", "Arjun Sethi", "Arjun Sethi, Neha Kapoor, Rohan Das", "Leads-only meeting"],
    ])
    files.append(("07_meeting_records.xlsx", "meetings", "Calendar export by IT on 17 Mar", ["meetings"]))
    docx_file(d / "08_statement_priya.docx", "Statement of complainant", [
        "Statement of: Priya Nair",
        "I submitted my complaint to the Ethics Office on 6 March 2026.",
        "On 11 March 2026 I found my Finance SharePoint access revoked. I was not given any reason.",
        "From 13 March I stopped receiving invitations to the Atlas steering meetings.",
    ])
    files.append(("08_statement_priya.docx", "statement", "Interview on 18 Mar", ["statement"]))
    (d / "09_statement_arjun.txt").write_text(
        "Statement of: Arjun Sethi\n\nI was not aware of any complaint when the access changes were made.\n\n"
        "The change was requested by IT as part of the review. Meetings became leads-only for all members.\n", encoding="utf-8")
    files.append(("09_statement_arjun.txt", "statement", "Interview on 19 Mar", ["statement"]))
    eml(d / "11_fwd_access_reply.eml", f'"Priya Nair" <priya.nair@{dom}>', '"R. Iyer (Counsel)" <r.iyer@lawchambers.example>',
        "Fwd: Re: Finance SharePoint access", "Tue, 17 Mar 2026 09:10:00 +0530",
        "Please see HR's explanation below.\n\n" + quote(d / "03_hr_access_reply.eml"), auth=AUTH_PASS.format(d=dom))
    files.append(("11_fwd_access_reply.eml", "email", "Priya Nair's sent-mail export", ["forward"]))
    if make_video(d / "12_steering_meeting_recording.mp4", [
            (4, ["Atlas steering - 13 Mar 2026 11:00", "Organiser: Arjun Sethi"]),
            (4, ["Attendees", "Arjun Sethi, Neha Kapoor, Rohan Das"]),
            (4, ["Agenda", "Vendor payment review postponed", "Meeting is leads-only from today"])],
            "Welcome to the Atlas steering meeting. From today this meeting is leads only. The vendor payment review is postponed."):
        files.append(("12_steering_meeting_recording.mp4", "meeting", "Teams recording exported by IT on 17 Mar", ["meeting", "video"]))
    csv_file(d / "10_document_history.csv", [
        ["Timestamp", "Document", "User", "Action", "Details"],
        ["2026-02-20 16:10", "Vendor_Payments_Q1.xlsx", "priya.nair", "edited", "Added Brightline invoice reconciliation"],
        ["2026-03-07 23:10", "Vendor_Payments_Q1.xlsx", "arjun.sethi", "edited", "Deleted rows 14-22"],
    ])
    files.append(("10_document_history.csv", "log", "SharePoint version history export", ["document history"]))
    return files


# ============================================================================= S5 marketplace dispute
def build_s5(d: Path) -> list[dict]:
    files = []
    eml(d / "01_order_confirmation.eml", '"BazaarHub Orders" <orders@bazaarhub.in>', '"Karthik Bhat" <karthik.bhat@shopmail.in>',
        "Order OD-48213 confirmed", "Mon, 02 Mar 2026 11:20:00 +0530",
        "Hi Karthik,\n\nYour order has been confirmed.\n\nOrder ID: OD-48213\nItem: Stainless steel water bottle 1L\nQty: 50\n"
        "Order Total: Rs 62,500.00\nSeller: Sunrise Kitchenware Traders\n\nBazaarHub", auth=AUTH_PASS.format(d="bazaarhub.in"))
    files.append(("01_order_confirmation.eml", "order", "Buyer's mailbox export", ["order"]))
    pdf(d / "02_invoice.pdf", "TAX INVOICE - Sunrise Kitchenware Traders", [
        "Invoice No: SKT/2026/0412", "Invoice Date: 02 Mar 2026", "Order ID: OD-48213", "Buyer: Karthik Bhat",
        "Item: Stainless steel water bottle 1L", "Qty: 50", "Unit Price: Rs 1,250.00", "Grand Total: Rs 62,500.00",
        "Shipping: Standard (free)"])
    files.append(("02_invoice.pdf", "invoice", "Downloaded from BazaarHub order page", ["invoice"]))
    screenshot(d / "03_payment_receipt.png", "BazaarHub Pay - Payment successful", [
        "Order ID: OD-48213",
        ("Amount Paid: Rs 65,200.00", 30, True, "#15803d"),
        "Express shipping: Rs 2,700.00",
        "Transaction ID: BHP8820193344",
        "Date: 2 Mar 2026, 11:24 AM",
    ], width=900)
    files.append(("03_payment_receipt.png", "payment", "Screenshot from buyer's phone", ["payment"]))
    (d / "04_seller_chat.json").write_text(json.dumps({
        "platform": "BazaarHub buyer-seller chat", "conversation": "Order OD-48213",
        "participants": ["Karthik Bhat", "Sunrise Kitchenware Traders"], "export_info": {"complete": True},
        "messages": [
            {"id": 1, "sender": "Sunrise Kitchenware Traders", "timestamp": "2026-03-05T18:30:00+05:30", "text": "Your order OD-48213 has been dispatched. 50 units packed in 5 cartons. AWB 7781234590."},
            {"id": 2, "sender": "Karthik Bhat", "timestamp": "2026-03-16T10:00:00+05:30", "text": "Tracking still shows in transit. When will it arrive?"},
            {"id": 3, "sender": "Sunrise Kitchenware Traders", "timestamp": "2026-03-16T12:10:00+05:30", "text": "As per our records order OD-48213 was delivered on 16 March 2026."},
            {"id": 4, "sender": "Karthik Bhat", "timestamp": "2026-03-18T16:05:00+05:30", "text": "Received today but only 40 units in 4 cartons. Unboxing video attached.", "attachments": [{"name": "unboxing.mp4", "included": False}]},
            {"id": 5, "sender": "Sunrise Kitchenware Traders", "timestamp": "2026-03-19T11:00:00+05:30", "text": "Sorry for this. We will refund Rs 12,500 for the 10 missing units within 5 days for order OD-48231."},
        ]}, indent=2), encoding="utf-8")
    files.append(("04_seller_chat.json", "chat", "BazaarHub chat export from buyer account", ["chat"]))
    csv_file(d / "05_courier_tracking.csv", [
        ["Date", "Status", "Location", "AWB", "Order ID", "Pieces", "Weight", "Remarks"],
        ["2026-03-05 18:10", "Picked up", "Pune", "7781234590", "OD-48213", "5", "25.0 kg", "Shipper: Sunrise Kitchenware"],
        ["2026-03-07 06:40", "In transit", "Bengaluru hub", "7781234590", "OD-48213", "5", "25.0 kg", ""],
        ["2026-03-18 14:35", "Delivered", "Bengaluru", "7781234590", "OD-48213", "4", "20.0 kg", "Received by: Security desk"],
    ])
    files.append(("05_courier_tracking.csv", "courier", "Courier website tracking export", ["courier"]))
    pdf(d / "06_delivery_confirmation.pdf", "BazaarHub - Delivery confirmation", [
        "Order ID: OD-48213", "Delivered On: 18 Mar 2026 14:35", "Quantity Delivered: 40", "Received By: Security desk",
        "Delivery partner: SwiftShip Couriers"])
    files.append(("06_delivery_confirmation.pdf", "delivery", "Downloaded from BazaarHub order page", ["delivery"]))
    screenshot(d / "07_product_photo.jpg", "Received cartons (photo)", [
        "CARTON 1 of 5 - 10 units - OD-48213", "CARTON 2 of 5 - 10 units - OD-48213",
        "CARTON 3 of 5 - 10 units - OD-48213", "CARTON 4 of 5 - 10 units - OD-48213"], fmt="JPEG", width=900, bg="#fdf6e3")
    files.append(("07_product_photo.jpg", "photo", "Photo taken by buyer 18 Mar", ["photo"]))
    screenshot(d / "10_delivery_screenshot.png", "BazaarHub - Delivery confirmation", [
        "Order ID: OD-48213", "Delivered On: 18 Mar 2026 14:35", "Quantity Delivered: 40", "Received By: Security desk",
        "Delivery partner: SwiftShip Couriers"], width=900)
    files.append(("10_delivery_screenshot.png", "delivery", "Screenshot of the BazaarHub delivery page sent by seller", ["delivery", "screenshot"]))
    eml(d / "08_refund_followup.eml", '"Karthik Bhat" <karthik.bhat@shopmail.in>', '"Seller Support" <support@sunrisekitchenware.in>',
        "Refund still pending - order OD-48213", "Thu, 26 Mar 2026 09:30:00 +0530",
        "Hello,\n\nThe refund of Rs 12,500 promised on 19 March has not been received in my account.\n\nKarthik Bhat",
        auth=AUTH_PASS.format(d="shopmail.in"))
    files.append(("08_refund_followup.eml", "email", "Buyer's sent-mail export", ["refund"]))
    eml(d / "09_other_order.eml", '"BazaarHub Orders" <orders@bazaarhub.in>', '"Karthik Bhat" <karthik.bhat@shopmail.in>',
        "Order OD-51120 delivered", "Wed, 11 Mar 2026 17:00:00 +0530",
        "Your order OD-51120 (Cotton kitchen towels, Qty: 6) was delivered on 11 Mar 2026.", auth=AUTH_PASS.format(d="bazaarhub.in"))
    files.append(("09_other_order.eml", "order", "Buyer's mailbox export - unrelated control item", ["unrelated"]))
    return files


BUILDERS = {"s1-phishing": build_s1, "s2-account-compromise": build_s2, "s3-evidence-preservation": build_s3,
            "s4-whistleblower-retaliation": build_s4, "s5-marketplace-dispute": build_s5,
            "s2h-sparse-account-records": lambda d: build_s2(d, sparse=True)}


from .trials import TRIAL_BUILDERS  # noqa: E402  (trials reuses the helpers above)

BUILDERS.update(TRIAL_BUILDERS)
from .marketplace import BUILDERS as MARKET_BUILDERS  # noqa: E402

BUILDERS.update(MARKET_BUILDERS)


def build_all(force: bool = False) -> dict:
    out = {}
    for sid, fn in BUILDERS.items():
        d = DATA_DIR / sid
        if d.exists() and (d / "manifest.json").exists() and not force:
            out[sid] = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
            continue
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True)
        files = fn(d)
        if sid == "s3-evidence-preservation":
            build_s3_log(d)
            files.insert(4, ("05_collection_log.csv", "collection log", "Collection log kept by complainant", ["log"]))
        manifest = []
        for name, cat, coll, tags in files:
            manifest.append({"file": name, "category": cat, "collection_source": coll, "tags": tags,
                             "collected_by": None if coll is None else "Scenario dataset collector",
                             "sha256": sha(d / name), "size": (d / name).stat().st_size})
        (d / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        out[sid] = manifest
    return out


if __name__ == "__main__":
    import sys
    res = build_all(force="--force" in sys.argv)
    for k, v in res.items():
        print(k, len(v), "files")
