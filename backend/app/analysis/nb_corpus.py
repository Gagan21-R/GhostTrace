"""Labelled training messages for the Naive Bayes message classifier.

Synthetic, written for this project (no real people). Mixed English / Hinglish because the
target users handle Indian cyber-crime complaints. Each class is deliberately varied in tone
and length so the model learns vocabulary, not one template.
"""
from __future__ import annotations

LABELS = {
    "harassment": "Harassment / threat",
    "extortion": "Extortion / blackmail",
    "financial_fraud": "Financial fraud / payment scam",
    "phishing": "Phishing / fake verification",
    "credential_request": "OTP / password request",
    "benign": "Ordinary conversation",
}

CORPUS: dict[str, list[str]] = {
    "harassment": [
        "I know where you live, you better watch your back",
        "you are worthless nobody wants you around here",
        "if you complain again I will make your life hell",
        "I will come to your house tonight and you will regret it",
        "stop ignoring me or I will hurt you",
        "everyone will know what a disgusting person you are",
        "you will pay for insulting me in front of everyone",
        "delete your account or I will keep posting about you",
        "tu bahut pachtayegi dekh lena, I will ruin you",
        "I am watching you every day outside your office",
        "you stupid idiot, block me and see what happens",
        "I will find you and break your face",
        "keep quiet or something bad will happen to your family",
        "nobody will save you, I promise you will suffer",
        "you are a liar and a cheat, I will destroy your reputation",
        "go die, the world is better without you",
        "I will send your photos to everyone in your college",
        "dont act smart with me, you have been warned",
        "I will make sure you lose your job you pathetic loser",
        "watch what happens when you step out tomorrow",
        "you ugly fool, I will humiliate you in front of the whole group",
        "maar dunga tujhe agar phir se message kiya",
    ],
    "extortion": [
        "pay 50000 rupees by tonight or I will leak your private photos",
        "I have your video, send bitcoin to this wallet or it goes viral",
        "transfer the money in 24 hours or your family sees everything",
        "we recorded your screen, pay 1500 dollars in btc to stay quiet",
        "if you do not pay I will upload your chats to every group",
        "send 20000 on this upi id otherwise I will share your pictures",
        "your data is encrypted, pay the ransom to get the decryption key",
        "last warning, pay now or I publish the documents",
        "I have hacked your account, pay me or I post everything",
        "send money quietly and nobody needs to know your secret",
        "paise bhej warna tera video sabko bhej dunga",
        "pay the amount before midnight or your boss gets the files",
        "deposit 0.05 btc to the address below to delete the recording",
        "you have 48 hours to pay, after that the leak starts",
        "your loan is overdue, pay today or we message all your contacts with your photo",
        "send the payment or I will tell your wife everything",
        "your files are locked, contact us on tor to pay the ransom",
        "pay me 10 lakh or the video goes to the media",
    ],
    "financial_fraud": [
        "send a refundable verification fee of 24999 to activate the refund",
        "invest 10000 today and get double returns in one week guaranteed",
        "complete simple tasks and earn 5000 daily, deposit to unlock withdrawal",
        "your lottery prize of 25 lakh is ready, pay processing charge first",
        "scan this qr code to receive the payment for your item",
        "please change the beneficiary bank account for all future invoices",
        "urgent wire transfer needed, keep it confidential, I am in a meeting",
        "pay the customs clearance fee to release your parcel",
        "your loan is approved, pay the insurance fee to disburse",
        "trading platform shows profit, add more funds to withdraw",
        "buy gift cards worth 20000 and send me the codes urgently",
        "advance payment required to book the flat viewing",
        "deposit security amount to confirm your work from home job",
        "pay the gst charge to receive your cashback",
        "electricity will be disconnected tonight, pay the pending bill on this number",
        "transfer money to this new account, the old one is under audit",
        "send 2000 as token amount and I will courier the phone",
        "crypto mining plan gives 3 percent daily, minimum deposit 50000",
        "your refund failed, pay one rupee to this upi to re-initiate",
        "please pay registration fee for the government scheme benefit",
    ],
    "phishing": [
        "your kyc is pending, click the link to update or your account will be blocked",
        "dear customer your netbanking will be suspended today, verify now",
        "unusual sign in detected, confirm your identity at the link below",
        "your parcel is on hold, update your address at this link",
        "your pan card is not linked, click here to avoid penalty",
        "verify your email account within 24 hours to avoid deactivation",
        "your credit card reward points expire today, redeem at the link",
        "income tax refund approved, submit bank details on the portal",
        "your apple id has been locked, sign in to unlock",
        "update your whatsapp now or your chats will be deleted, tap the link",
        "your electricity kyc is incomplete, download the app from this link",
        "security alert from your bank, login here to secure your account",
        "your sim will be deactivated, complete e-kyc using this link",
        "click to claim your free recharge offer before it expires",
        "we could not deliver your package, pay small fee at the link",
        "account verification required, enter your card details to continue",
        "hdfc kyc update required, visit the secure portal immediately",
        "your mailbox is full, login to increase storage",
    ],
    "credential_request": [
        "please share the otp you just received, I sent it by mistake",
        "send me the 6 digit code that came on your phone",
        "tell me the verification code, it is for the kyc process",
        "what is your password, I need to check something urgently",
        "forward me the code you got from whatsapp",
        "bhai ek otp aaya hoga, jaldi bhej de",
        "share your upi pin so I can send the refund",
        "read out the one time password from the sms",
        "I accidentally used your number, please send the login code",
        "give me your netbanking user id and password to fix the issue",
        "send your card cvv and expiry to verify the account",
        "the code expires in 5 minutes, send it fast please",
        "I am from support, tell me the otp to cancel the transaction",
        "share the screen code so I can help you install",
        "send me the link code that just came, I need to log in on laptop",
        "what is the pin you set, the bank officer needs it",
        "your friend needs the verification code, please share",
        "send the reset code from the email I need to recover my account",
    ],
    "benign": [
        "are we still meeting for lunch tomorrow at one",
        "thanks for the notes, see you in class",
        "happy birthday, have a great day",
        "can you send me the report by evening please",
        "reached home safely, talk later",
        "the meeting is moved to 4 pm",
        "did you watch the match yesterday, what a finish",
        "mom is asking if you will come for dinner on sunday",
        "please review the slides before the presentation",
        "ok noted, will do",
        "the delivery came today, the box was a bit damaged",
        "let us split the cab fare",
        "call me when you are free",
        "good morning, have a nice day",
        "i will be late, traffic is very bad",
        "send me the photos from the trip",
        "congrats on the new job",
        "kal milte hain office mein",
        "can you pick up milk on the way",
        "the invoice for march is attached, please check",
        "thank you for your help yesterday",
        "where are you, the movie starts in ten minutes",
        "please call the plumber, the tap is leaking",
        "lets go for a walk in the evening",
    ],
}

# Second batch: more variety so leave-one-out estimates are less noisy.
CORPUS["harassment"] += [
    "you better not show your face in college again", "I will tell everyone your secrets, just wait",
    "you are a characterless woman, shame on you", "one more word and I will slap you",
    "I have your address and I am coming", "you are dead to me and soon to everyone",
    "keep posting and see what I do to you", "i will burn your scooty outside your house",
    "chup reh warna bura hoga", "you disgusting creep, everyone hates you",
]
CORPUS["extortion"] += [
    "pay up or the pictures go online tomorrow", "send 5000 now or I share the screenshots with your parents",
    "unless you pay, your nude video will be on every site", "give me money or I report fake things about you",
    "wire the amount or the database gets published", "pay within one hour or your account details get sold",
    "I will delete everything once you send the bitcoin", "payment first, then I destroy the copies",
    "your contacts will receive the morphed photo unless you pay", "abhi paise do warna photo viral",
]
CORPUS["financial_fraud"] += [
    "pay a small deposit to start earning from youtube likes", "guaranteed 40 percent monthly profit, send funds to my account",
    "your parcel from abroad needs a clearance payment today", "the new vendor bank details are below, please update before paying",
    "pay the booking amount to reserve the car, I am in the army so cannot meet",
    "send 999 to unlock your prize money", "your account was credited by mistake, please return the amount to this upi",
    "recharge the wallet to withdraw your task commission", "kindly remit the invoice to our new account at a different bank",
    "pay token advance and the job offer letter will be sent",
]
CORPUS["phishing"] += [
    "dear user your account will be closed, verify at the url", "click this link to reactivate your blocked card",
    "you have a pending refund, login at the portal to claim", "confirm your details to avoid suspension of service",
    "your password expires today, reset it using this link", "important: validate your aadhaar to continue banking",
    "tap here to see who viewed your profile", "your instagram will be deleted for copyright, appeal at the link",
    "fastag kyc expired, update now at the link", "netflix payment failed, update card details here",
]
CORPUS["credential_request"] += [
    "please tell me the code from the sms, it is urgent", "send the otp quickly I am at the bank counter",
    "share your login password so I can fix the app", "can you forward the verification message you just got",
    "the six digit pin please, my phone is not getting it", "send me your whatsapp code, I am stuck",
    "give the otp to the executive to complete delivery", "what number came in the message just now, send it",
    "tell me your atm pin for the refund", "I need your email password to recover the files",
]
CORPUS["benign"] += [
    "the train is delayed by half an hour", "please bring the charger when you come",
    "nice photo, where was this taken", "I paid the rent for this month",
    "sorry I missed your call, was driving", "the doctor appointment is at 11 tomorrow",
    "do you have the notes for chapter five", "team dinner on friday, are you in",
    "my laptop is slow, can you look at it", "okay sounds good, see you then",
    "the shop is closed today, let us go tomorrow", "send me the address of the venue",
]

# Texting style (short forms are common in real complaints).
CORPUS["harassment"] += ["u will regret this watch ur back", "i know where u live dont forget", "u think u can ignore me",
                         "ur dead if u tell anyone", "wait n watch wat i do to u"]
CORPUS["benign"] += ["u coming to class tmrw?", "ok cya at 5", "thx bro ur the best", "wat time is the movie"]

# ---------------------------------------------------------------------------------------------------------------
# Hindi (Devanagari) and Kannada examples. Same six classes; the character n-gram features let one model handle
# all three scripts plus romanised Hinglish, so a mixed-language chat needs no separate model.
CORPUS["harassment"] += [
    "मुझे पता है तुम कहाँ रहती हो, तुम पछताओगी", "तुम्हें छोड़ूँगा नहीं, देख लेना", "कल घर से बाहर निकली तो बुरा होगा",
    "तुम बेकार हो, कोई तुम्हें पसंद नहीं करता", "शिकायत की तो तुम्हारी ज़िंदगी बर्बाद कर दूँगा", "अपनी औकात में रहो वरना मार खाओगे",
    "ನೀನು ಎಲ್ಲಿ ಇರ್ತೀಯ ಅಂತ ನನಗೆ ಗೊತ್ತು, ಪಶ್ಚಾತ್ತಾಪ ಪಡ್ತೀಯ", "ನಿನ್ನನ್ನು ಬಿಡಲ್ಲ, ನೋಡ್ತಾ ಇರು", "ನಾಳೆ ಮನೆಯಿಂದ ಹೊರಗೆ ಬಂದ್ರೆ ಕೆಟ್ಟದಾಗುತ್ತೆ",
    "ನೀನು ನಿಷ್ಪ್ರಯೋಜಕ, ಯಾರಿಗೂ ನೀನು ಇಷ್ಟ ಇಲ್ಲ", "ದೂರು ಕೊಟ್ರೆ ನಿನ್ನ ಜೀವನ ಹಾಳು ಮಾಡ್ತೀನಿ", "ಬಾಯಿ ಮುಚ್ಕೊಂಡು ಇರು ಇಲ್ಲಾಂದ್ರೆ ಹೊಡೀತೀನಿ",
]
CORPUS["extortion"] += [
    "आज रात तक 50000 भेजो वरना तुम्हारी फोटो सबको भेज दूँगा", "पैसे नहीं दिए तो वीडियो वायरल कर दूँगा", "24 घंटे में पैसे ट्रांसफर करो वरना परिवार सब देखेगा",
    "बिटकॉइन भेजो वरना रिकॉर्डिंग सबके पास जाएगी", "लोन चुकाओ वरना तुम्हारे सारे कॉन्टैक्ट्स को मैसेज करेंगे",
    "ಇವತ್ತು ರಾತ್ರಿ 50000 ಕಳಿಸು ಇಲ್ಲಾಂದ್ರೆ ನಿನ್ನ ಫೋಟೋ ಎಲ್ಲರಿಗೂ ಕಳಿಸ್ತೀನಿ", "ಹಣ ಕೊಡದಿದ್ರೆ ವಿಡಿಯೋ ವೈರಲ್ ಮಾಡ್ತೀನಿ", "24 ಗಂಟೆಯಲ್ಲಿ ಹಣ ಕಳಿಸು ಇಲ್ಲಾಂದ್ರೆ ನಿನ್ನ ಮನೆಯವರಿಗೆ ಎಲ್ಲಾ ಗೊತ್ತಾಗುತ್ತೆ",
    "ಬಿಟ್‌ಕಾಯಿನ್ ಕಳಿಸು ಇಲ್ಲಾಂದ್ರೆ ರೆಕಾರ್ಡಿಂಗ್ ಎಲ್ಲರಿಗೂ ಹೋಗುತ್ತೆ", "ಸಾಲ ಕಟ್ಟು ಇಲ್ಲಾಂದ್ರೆ ನಿನ್ನ ಎಲ್ಲಾ ಕಾಂಟ್ಯಾಕ್ಟ್‌ಗಳಿಗೆ ಮೆಸೇಜ್ ಮಾಡ್ತೀವಿ",
]
CORPUS["financial_fraud"] += [
    "रिफंड के लिए 24999 वेरिफिकेशन फीस भेजें", "रोज़ 5000 कमाइए, बस टास्क पूरे करें और पहले 1000 जमा करें", "आपकी लॉटरी लगी है, प्रोसेसिंग चार्ज पहले भरें",
    "पेमेंट पाने के लिए यह क्यूआर कोड स्कैन करें", "एक हफ्ते में पैसा दोगुना, गारंटी के साथ निवेश करें",
    "ರಿಫಂಡ್‌ಗಾಗಿ 24999 ವೆರಿಫಿಕೇಶನ್ ಶುಲ್ಕ ಕಳಿಸಿ", "ದಿನಕ್ಕೆ 5000 ಗಳಿಸಿ, ಟಾಸ್ಕ್ ಮುಗಿಸಿ ಮೊದಲು 1000 ಠೇವಣಿ ಇಡಿ", "ನಿಮಗೆ ಲಾಟರಿ ಬಂದಿದೆ, ಮೊದಲು ಪ್ರೊಸೆಸಿಂಗ್ ಶುಲ್ಕ ಕಟ್ಟಿ",
    "ಹಣ ಪಡೆಯಲು ಈ ಕ್ಯೂಆರ್ ಕೋಡ್ ಸ್ಕ್ಯಾನ್ ಮಾಡಿ", "ಒಂದು ವಾರದಲ್ಲಿ ಹಣ ಡಬಲ್, ಗ್ಯಾರಂಟಿ ಹೂಡಿಕೆ ಮಾಡಿ",
]
CORPUS["phishing"] += [
    "आपका केवाईसी लंबित है, लिंक पर क्लिक करें वरना खाता बंद हो जाएगा", "आपकी नेटबैंकिंग आज बंद होगी, अभी सत्यापित करें", "आपका पार्सल रुका है, इस लिंक पर पता अपडेट करें",
    "पैन कार्ड लिंक नहीं है, जुर्माने से बचने के लिए यहाँ क्लिक करें", "बिजली कनेक्शन कटेगा, लिंक से केवाईसी अपडेट करें",
    "ನಿಮ್ಮ ಕೆವೈಸಿ ಬಾಕಿ ಇದೆ, ಲಿಂಕ್ ಕ್ಲಿಕ್ ಮಾಡಿ ಇಲ್ಲದಿದ್ರೆ ಖಾತೆ ಬ್ಲಾಕ್ ಆಗುತ್ತೆ", "ನಿಮ್ಮ ನೆಟ್‌ಬ್ಯಾಂಕಿಂಗ್ ಇಂದು ಸ್ಥಗಿತವಾಗುತ್ತೆ, ಈಗಲೇ ಪರಿಶೀಲಿಸಿ",
    "ನಿಮ್ಮ ಪಾರ್ಸೆಲ್ ತಡೆಹಿಡಿಯಲಾಗಿದೆ, ಈ ಲಿಂಕ್‌ನಲ್ಲಿ ವಿಳಾಸ ಅಪ್‌ಡೇಟ್ ಮಾಡಿ", "ಪ್ಯಾನ್ ಕಾರ್ಡ್ ಲಿಂಕ್ ಆಗಿಲ್ಲ, ದಂಡ ತಪ್ಪಿಸಲು ಇಲ್ಲಿ ಕ್ಲಿಕ್ ಮಾಡಿ", "ವಿದ್ಯುತ್ ಸಂಪರ್ಕ ಕಡಿತವಾಗುತ್ತೆ, ಲಿಂಕ್ ಮೂಲಕ ಕೆವೈಸಿ ಅಪ್‌ಡೇಟ್ ಮಾಡಿ",
]
CORPUS["credential_request"] += [
    "जो ओटीपी आया है वो मुझे भेज दो, गलती से आपके नंबर पर गया", "अपना पासवर्ड बताओ, कुछ चेक करना है", "फोन पर आया 6 अंकों का कोड भेजो",
    "रिफंड के लिए अपना यूपीआई पिन बताइए", "वेरिफिकेशन कोड जल्दी भेजो, 5 मिनट में खत्म हो जाएगा",
    "ನಿಮಗೆ ಬಂದ ಓಟಿಪಿ ನನಗೆ ಕಳಿಸಿ, ತಪ್ಪಾಗಿ ನಿಮ್ಮ ನಂಬರ್‌ಗೆ ಬಂತು", "ನಿಮ್ಮ ಪಾಸ್‌ವರ್ಡ್ ಹೇಳಿ, ಏನೋ ಚೆಕ್ ಮಾಡಬೇಕು", "ಫೋನ್‌ಗೆ ಬಂದ 6 ಅಂಕಿಯ ಕೋಡ್ ಕಳಿಸಿ",
    "ರಿಫಂಡ್‌ಗೆ ನಿಮ್ಮ ಯುಪಿಐ ಪಿನ್ ಹೇಳಿ", "ವೆರಿಫಿಕೇಶನ್ ಕೋಡ್ ಬೇಗ ಕಳಿಸಿ, 5 ನಿಮಿಷದಲ್ಲಿ ಮುಗಿಯುತ್ತೆ",
]
CORPUS["benign"] += [
    "कल दोपहर को लंच पर मिलते हैं", "नोट्स के लिए धन्यवाद, क्लास में मिलते हैं", "जन्मदिन की बहुत बधाई", "मैं घर पहुँच गया, बाद में बात करते हैं",
    "मीटिंग चार बजे हो गई है", "शाम को टहलने चलें?",
    "ನಾಳೆ ಮಧ್ಯಾಹ್ನ ಊಟಕ್ಕೆ ಸಿಗೋಣ", "ನೋಟ್ಸ್‌ಗೆ ಧನ್ಯವಾದ, ಕ್ಲಾಸ್‌ನಲ್ಲಿ ಸಿಗೋಣ", "ಹುಟ್ಟುಹಬ್ಬದ ಶುಭಾಶಯಗಳು", "ಮನೆ ತಲುಪಿದೆ, ಆಮೇಲೆ ಮಾತಾಡೋಣ",
    "ಮೀಟಿಂಗ್ ನಾಲ್ಕು ಗಂಟೆಗೆ ಬದಲಾಗಿದೆ", "ಸಂಜೆ ವಾಕಿಂಗ್ ಹೋಗೋಣವಾ?",
]
