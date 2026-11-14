// Interface languages: English, Hindi (हिन्दी), Kannada (ಕನ್ನಡ).
// Strings are keyed by their English text, so `t("Cases")` works anywhere and untranslated text falls back to English.
// Evidence content is never translated: it is shown exactly as it was collected.
import { createContext, ReactNode, useContext, useEffect, useState } from "react";

export type Lang = "en" | "hi" | "kn";
export const LANGS: { id: Lang; label: string; short: string }[] = [
  { id: "en", label: "English", short: "EN" }, { id: "hi", label: "हिन्दी", short: "हि" }, { id: "kn", label: "ಕನ್ನಡ", short: "ಕ" },
];

// [English, Hindi, Kannada]
const ROWS: [string, string, string][] = [
  // navigation
  ["Workspace", "कार्यक्षेत्र", "ಕಾರ್ಯಕ್ಷೇತ್ರ"], ["Overview", "अवलोकन", "ಅವಲೋಕನ"], ["Cases", "मामले", "ಪ್ರಕರಣಗಳು"],
  ["Active case", "चालू मामला", "ಸಕ್ರಿಯ ಪ್ರಕರಣ"], ["Evidence", "साक्ष्य", "ಸಾಕ್ಷ್ಯ"], ["Timeline", "समयरेखा", "ಕಾಲರೇಖೆ"],
  ["Relationships", "संबंध", "ಸಂಬಂಧಗಳು"], ["Message Check", "संदेश जाँच", "ಸಂದೇಶ ಪರಿಶೀಲನೆ"], ["Challenge", "चुनौती", "ಸವಾಲು"],
  ["Platform", "प्लेटफ़ॉर्म", "ವೇದಿಕೆ"], ["Scenario Lab", "परिदृश्य लैब", "ಸನ್ನಿವೇಶ ಪ್ರಯೋಗಾಲಯ"], ["AI Lab", "एआई लैब", "ಎಐ ಪ್ರಯೋಗಾಲಯ"],
  ["Evaluation", "मूल्यांकन", "ಮೌಲ್ಯಮಾಪನ"], ["Reports", "रिपोर्ट", "ವರದಿಗಳು"], ["Audit Log", "ऑडिट लॉग", "ಲೆಕ್ಕಪರಿಶೋಧನಾ ದಾಖಲೆ"],
  ["Settings & Admin", "सेटिंग्स और प्रशासन", "ಸೆಟ್ಟಿಂಗ್ಸ್ ಮತ್ತು ಆಡಳಿತ"],
  ["Findings assist investigators. They are not determinations of guilt or identity.",
    "निष्कर्ष जाँचकर्ताओं की सहायता करते हैं। ये अपराध या पहचान का निर्णय नहीं हैं।",
    "ಫಲಿತಾಂಶಗಳು ತನಿಖಾಧಿಕಾರಿಗಳಿಗೆ ಸಹಾಯ ಮಾಡುತ್ತವೆ. ಇವು ಅಪರಾಧ ಅಥವಾ ಗುರುತಿನ ತೀರ್ಮಾನವಲ್ಲ."],
  ["Every clue connected", "हर सुराग जुड़ा हुआ", "ಪ್ರತಿ ಸುಳಿವು ಜೋಡಿಸಲಾಗಿದೆ"], ["Language", "भाषा", "ಭಾಷೆ"], ["Sign out", "साइन आउट", "ಸೈನ್ ಔಟ್"],
  // case tabs
  ["Summary", "सारांश", "ಸಾರಾಂಶ"], ["Contradictions", "विरोधाभास", "ವಿರೋಧಾಭಾಸಗಳು"], ["Gaps", "कमियाँ", "ಕೊರತೆಗಳು"],
  ["Processing", "प्रोसेसिंग", "ಸಂಸ್ಕರಣೆ"], ["Entities", "इकाइयाँ", "ಘಟಕಗಳು"], ["Evidence DNA", "साक्ष्य डीएनए", "ಸಾಕ್ಷ್ಯ ಡಿಎನ್‌ಎ"],
  ["Missing Evidence", "गायब साक्ष्य", "ಕಾಣೆಯಾದ ಸಾಕ್ಷ್ಯ"], ["What-If Lab", "क्या-अगर लैब", "ಹೀಗಾದರೆ ಪ್ರಯೋಗಾಲಯ"], ["Replay", "रीप्ले", "ಮರುಪ್ರದರ್ಶನ"],
  ["Integrity & Audit", "अखंडता और ऑडिट", "ಸಮಗ್ರತೆ ಮತ್ತು ಲೆಕ್ಕಪರಿಶೋಧನೆ"], ["More", "और", "ಇನ್ನಷ್ಟು"],
  ["You are in:", "आप यहाँ हैं:", "ನೀವು ಇಲ್ಲಿದ್ದೀರಿ:"], ["Explain", "समझाएँ", "ವಿವರಿಸಿ"], ["Explain this tab", "यह टैब समझाएँ", "ಈ ಟ್ಯಾಬ್ ವಿವರಿಸಿ"],
  ["All cases", "सभी मामले", "ಎಲ್ಲಾ ಪ್ರಕರಣಗಳು"], ["Scenario runs", "परिदृश्य रन", "ಸನ್ನಿವೇಶ ರನ್‌ಗಳು"], ["Archive", "संग्रहित करें", "ಆರ್ಕೈವ್"],
  // page headers & sections
  ["Investigation workspace", "जाँच कार्यक्षेत्र", "ತನಿಖಾ ಕಾರ್ಯಕ್ಷೇತ್ರ"], ["Live figures from your cases.", "आपके मामलों के ताज़ा आँकड़े।", "ನಿಮ್ಮ ಪ್ರಕರಣಗಳ ಇತ್ತೀಚಿನ ಅಂಕಿಅಂಶಗಳು."],
  ["Investigations", "जाँच", "ತನಿಖೆಗಳು"], ["Each case keeps its own evidence, findings and access list.", "हर मामले के अपने साक्ष्य, निष्कर्ष और पहुँच सूची होती है।", "ಪ್ರತಿ ಪ್ರಕರಣಕ್ಕೂ ತನ್ನದೇ ಸಾಕ್ಷ್ಯ, ಫಲಿತಾಂಶ ಮತ್ತು ಪ್ರವೇಶ ಪಟ್ಟಿ ಇದೆ."],
  ["Open a new case", "नया मामला खोलें", "ಹೊಸ ಪ್ರಕರಣ ತೆರೆಯಿರಿ"], ["Recent cases", "हाल के मामले", "ಇತ್ತೀಚಿನ ಪ್ರಕರಣಗಳು"],
  ["Recent activity", "हाल की गतिविधि", "ಇತ್ತೀಚಿನ ಚಟುವಟಿಕೆ"], ["Needs attention", "ध्यान दें", "ಗಮನ ಬೇಕು"], ["Integrity verification", "अखंडता सत्यापन", "ಸಮಗ್ರತೆ ಪರಿಶೀಲನೆ"],
  ["Evidence by type", "प्रकार के अनुसार साक्ष्य", "ಪ್ರಕಾರದ ಪ್ರಕಾರ ಸಾಕ್ಷ್ಯ"], ["Investigation workflow", "जाँच प्रक्रिया", "ತನಿಖಾ ಪ್ರಕ್ರಿಯೆ"],
  ["Recent reports", "हाल की रिपोर्ट", "ಇತ್ತೀಚಿನ ವರದಿಗಳು"], ["Recent reviewer decisions", "समीक्षक के हाल के निर्णय", "ಪರಿಶೀಲಕರ ಇತ್ತೀಚಿನ ನಿರ್ಧಾರಗಳು"],
  ["Evidence intake · last 14 days", "साक्ष्य प्राप्ति · पिछले 14 दिन", "ಸಾಕ್ಷ್ಯ ಸ್ವೀಕಾರ · ಕಳೆದ 14 ದಿನ"], ["Contradictions by category", "श्रेणी अनुसार विरोधाभास", "ವರ್ಗದ ಪ್ರಕಾರ ವಿರೋಧಾಭಾಸಗಳು"],
  ["Evidence items", "साक्ष्य आइटम", "ಸಾಕ್ಷ್ಯ ವಸ್ತುಗಳು"], ["Open gaps", "खुली कमियाँ", "ತೆರೆದ ಕೊರತೆಗಳು"], ["Pending reviews", "लंबित समीक्षाएँ", "ಬಾಕಿ ಪರಿಶೀಲನೆಗಳು"],
  ["Running jobs", "चल रहे कार्य", "ನಡೆಯುತ್ತಿರುವ ಕೆಲಸಗಳು"], ["Timeline events", "समयरेखा घटनाएँ", "ಕಾಲರೇಖೆ ಘಟನೆಗಳು"], ["Active", "सक्रिय", "ಸಕ್ರಿಯ"],
  ["Completed", "पूर्ण", "ಪೂರ್ಣ"], ["Ground-truth evaluation", "ग्राउंड-ट्रुथ मूल्यांकन", "ನೈಜ-ಸತ್ಯ ಮೌಲ್ಯಮಾಪನ"], ["Investigation reports", "जाँच रिपोर्ट", "ತನಿಖಾ ವರದಿಗಳು"],
  ["System configuration", "सिस्टम कॉन्फ़िगरेशन", "ವ್ಯವಸ್ಥೆ ಸಂರಚನೆ"], ["Users & access", "उपयोगकर्ता और पहुँच", "ಬಳಕೆದಾರರು ಮತ್ತು ಪ್ರವೇಶ"],
  ["Choose a case", "मामला चुनें", "ಪ್ರಕರಣ ಆಯ್ಕೆಮಾಡಿ"], ["Scenario test results", "परिदृश्य परीक्षण परिणाम", "ಸನ್ನಿವೇಶ ಪರೀಕ್ಷಾ ಫಲಿತಾಂಶಗಳು"],
  ["Your profile", "आपकी प्रोफ़ाइल", "ನಿಮ್ಮ ಪ್ರೊಫೈಲ್"], ["Change password", "पासवर्ड बदलें", "ಪಾಸ್‌ವರ್ಡ್ ಬದಲಾಯಿಸಿ"],
  ["Case history", "मामले का इतिहास", "ಪ್ರಕರಣದ ಇತಿಹಾಸ"], ["Incident & objective", "घटना और उद्देश्य", "ಘಟನೆ ಮತ್ತು ಉದ್ದೇಶ"], ["Current assessment", "वर्तमान आकलन", "ಪ್ರಸ್ತುತ ಮೌಲ್ಯಮಾಪನ"],
  ["Recommended next steps", "अगले सुझाए गए कदम", "ಶಿಫಾರಸು ಮಾಡಿದ ಮುಂದಿನ ಹೆಜ್ಜೆಗಳು"], ["Access & assignments", "पहुँच और ज़िम्मेदारियाँ", "ಪ್ರವೇಶ ಮತ್ತು ಹೊಣೆಗಳು"],
  ["Evidence processing pipeline", "साक्ष्य प्रोसेसिंग पाइपलाइन", "ಸಾಕ್ಷ್ಯ ಸಂಸ್ಕರಣಾ ಪೈಪ್‌ಲೈನ್"], ["Generate evidence-linked report", "साक्ष्य-आधारित रिपोर्ट बनाएँ", "ಸಾಕ್ಷ್ಯ-ಆಧಾರಿತ ವರದಿ ರಚಿಸಿ"],
  ["Evidence dependencies", "साक्ष्य निर्भरताएँ", "ಸಾಕ್ಷ್ಯ ಅವಲಂಬನೆಗಳು"], ["Independent source groups", "स्वतंत्र स्रोत समूह", "ಸ್ವತಂತ್ರ ಮೂಲ ಗುಂಪುಗಳು"],
  ["Shared identifiers (fingerprint)", "साझा पहचानकर्ता (फ़िंगरप्रिंट)", "ಹಂಚಿಕೊಂಡ ಗುರುತುಗಳು (ಬೆರಳಚ್ಚು)"],
  // AI lab / message check
  ["Models & tools", "मॉडल और टूल", "ಮಾದರಿಗಳು ಮತ್ತು ಉಪಕರಣಗಳು"], ["OCR reads the words. Naive Bayes decides what they mean.",
    "OCR शब्द पढ़ता है। नेव बेज़ तय करता है कि उनका मतलब क्या है।", "OCR ಪದಗಳನ್ನು ಓದುತ್ತದೆ. ನೇವ್ ಬೇಸ್ ಅವುಗಳ ಅರ್ಥ ನಿರ್ಧರಿಸುತ್ತದೆ."],
  ["Try the classifier", "क्लासिफ़ायर आज़माएँ", "ವರ್ಗೀಕರಣಕಾರ ಪ್ರಯತ್ನಿಸಿ"], ["Classify", "वर्गीकृत करें", "ವರ್ಗೀಕರಿಸಿ"], ["Model card", "मॉडल कार्ड", "ಮಾದರಿ ಕಾರ್ಡ್"],
  ["Tools agents can call", "एजेंट जिन टूल्स को कॉल कर सकते हैं", "ಏಜೆಂಟ್‌ಗಳು ಕರೆಯಬಹುದಾದ ಉಪಕರಣಗಳು"], ["Because of", "इन शब्दों के कारण", "ಈ ಪದಗಳಿಂದ"],
  ["uncertain", "अनिश्चित", "ಅನಿಶ್ಚಿತ"], ["leave-one-out accuracy", "लीव-वन-आउट सटीकता", "ಲೀವ್-ಒನ್-ಔಟ್ ನಿಖರತೆ"], ["training messages", "प्रशिक्षण संदेश", "ತರಬೇತಿ ಸಂದೇಶಗಳು"],
  ["Accuracy by language", "भाषा अनुसार सटीकता", "ಭಾಷೆಯ ಪ್ರಕಾರ ನಿಖರತೆ"], ["Detected language", "पहचानी गई भाषा", "ಪತ್ತೆಯಾದ ಭಾಷೆ"],
  ["Message labels (Naive Bayes)", "संदेश लेबल (नेव बेज़)", "ಸಂದೇಶ ಲೇಬಲ್‌ಗಳು (ನೇವ್ ಬೇಸ್)"], ["Tool console", "टूल कंसोल", "ಉಪಕರಣ ಕನ್ಸೋಲ್"],
  ["Call", "कॉल करें", "ಕರೆ ಮಾಡಿ"], ["Next steps", "अगले कदम", "ಮುಂದಿನ ಹೆಜ್ಜೆಗಳು"], ["Shown as from", "इनके नाम से दिखाया गया", "ಇವರಿಂದ ಎಂದು ತೋರಿಸಲಾಗಿದೆ"],
  ["Fake screenshot signs", "नकली स्क्रीनशॉट के संकेत", "ನಕಲಿ ಸ್ಕ್ರೀನ್‌ಶಾಟ್ ಸೂಚನೆಗಳು"], ["Someone else used the account", "किसी और ने खाता इस्तेमाल किया", "ಬೇರೆ ಯಾರೋ ಖಾತೆ ಬಳಸಿದ್ದಾರೆ"],
  ["Account holder sent it", "खाताधारक ने भेजा", "ಖಾತೆದಾರರೇ ಕಳುಹಿಸಿದ್ದಾರೆ"], ["Agent called", "एजेंट ने कॉल किए", "ಏಜೆಂಟ್ ಕರೆದದ್ದು"], ["tools", "टूल", "ಉಪಕರಣಗಳು"],
  ["show whole files", "पूरी फ़ाइलें दिखाएँ", "ಪೂರ್ಣ ಫೈಲ್‌ಗಳನ್ನು ತೋರಿಸಿ"], ["No message was flagged.", "कोई संदेश चिह्नित नहीं हुआ।", "ಯಾವುದೇ ಸಂದೇಶ ಗುರುತಿಸಲಾಗಿಲ್ಲ."],
  ["No disputed chat screenshots", "कोई विवादित चैट स्क्रीनशॉट नहीं", "ವಿವಾದಿತ ಚಾಟ್ ಸ್ಕ್ರೀನ್‌ಶಾಟ್‌ಗಳಿಲ್ಲ"],
  ["Screenshot not supported by source records", "स्क्रीनशॉट मूल रिकॉर्ड से मेल नहीं खाता", "ಸ್ಕ್ರೀನ್‌ಶಾಟ್ ಮೂಲ ದಾಖಲೆಗಳಿಗೆ ಹೊಂದಿಕೆಯಾಗುತ್ತಿಲ್ಲ"],
  ["Sent from the account, but indicators point to someone else using it", "खाते से भेजा गया, पर संकेत बताते हैं कि कोई और इसे इस्तेमाल कर रहा था",
    "ಖಾತೆಯಿಂದ ಕಳುಹಿಸಲಾಗಿದೆ, ಆದರೆ ಬೇರೆ ಯಾರೋ ಬಳಸುತ್ತಿದ್ದರು ಎಂಬ ಸೂಚನೆಗಳಿವೆ"],
  ["Records are consistent with the account holder sending it", "रिकॉर्ड बताते हैं कि खाताधारक ने ही भेजा", "ಖಾತೆದಾರರೇ ಕಳುಹಿಸಿದ್ದಾರೆ ಎಂದು ದಾಖಲೆಗಳು ತೋರಿಸುತ್ತವೆ"],
  ["Not enough records to tell", "तय करने के लिए पर्याप्त रिकॉर्ड नहीं", "ನಿರ್ಧರಿಸಲು ಸಾಕಷ್ಟು ದಾಖಲೆಗಳಿಲ್ಲ"],
  ["Harassment / threat", "उत्पीड़न / धमकी", "ಕಿರುಕುಳ / ಬೆದರಿಕೆ"], ["Extortion / blackmail", "जबरन वसूली / ब्लैकमेल", "ಸುಲಿಗೆ / ಬ್ಲ್ಯಾಕ್‌ಮೇಲ್"],
  ["Financial fraud / payment scam", "वित्तीय धोखाधड़ी / भुगतान घोटाला", "ಹಣಕಾಸು ವಂಚನೆ / ಪಾವತಿ ಮೋಸ"], ["Phishing / fake verification", "फ़िशिंग / नकली सत्यापन", "ಫಿಶಿಂಗ್ / ನಕಲಿ ಪರಿಶೀಲನೆ"],
  ["OTP / password request", "ओटीपी / पासवर्ड माँग", "ಓಟಿಪಿ / ಪಾಸ್‌ವರ್ಡ್ ಬೇಡಿಕೆ"], ["Ordinary conversation", "सामान्य बातचीत", "ಸಾಮಾನ್ಯ ಸಂಭಾಷಣೆ"],
  // graph
  ["Path finder", "रास्ता खोजें", "ಮಾರ್ಗ ಹುಡುಕಿ"], ["Key connectors", "मुख्य कड़ियाँ", "ಮುಖ್ಯ ಸಂಪರ್ಕಗಳು"], ["entities", "इकाइयाँ", "ಘಟಕಗಳು"], ["links", "कड़ियाँ", "ಸಂಪರ್ಕಗಳು"],
  ["Isolate", "अलग करें", "ಪ್ರತ್ಯೇಕಿಸಿ"], ["Show all", "सब दिखाएँ", "ಎಲ್ಲಾ ತೋರಿಸಿ"], ["Path from here", "यहाँ से रास्ता", "ಇಲ್ಲಿಂದ ಮಾರ್ಗ"],
  ["Connected to", "इनसे जुड़ा", "ಇವುಗಳಿಗೆ ಸಂಪರ್ಕಿತ"], ["Seen in", "इसमें दिखा", "ಇಲ್ಲಿ ಕಂಡಿದೆ"], ["Find…", "खोजें…", "ಹುಡುಕಿ…"],
  ["Click a start node, then an end node", "पहले शुरुआती, फिर अंतिम नोड चुनें", "ಮೊದಲು ಆರಂಭದ, ನಂತರ ಕೊನೆಯ ನೋಡ್ ಆಯ್ಕೆಮಾಡಿ"],
  ["Hover to spotlight · click to inspect · double-click to isolate · dashed orange = inferred lead.",
    "होवर: उजागर · क्लिक: जाँचें · डबल-क्लिक: अलग करें · नारंगी डैश = अनुमानित सुराग।", "ಹೋವರ್: ಎದ್ದು ತೋರಿಸು · ಕ್ಲಿಕ್: ಪರಿಶೀಲಿಸು · ಡಬಲ್-ಕ್ಲಿಕ್: ಪ್ರತ್ಯೇಕಿಸು · ಕಿತ್ತಳೆ ಗೆರೆ = ಊಹಿತ ಸುಳಿವು."],
  // assistant
  ["Ask GhostTrace", "GhostTrace से पूछें", "GhostTrace ಅನ್ನು ಕೇಳಿ"], ["Ask anything about this screen…", "इस स्क्रीन के बारे में कुछ भी पूछें…", "ಈ ಪರದೆಯ ಬಗ್ಗೆ ಏನಾದರೂ ಕೇಳಿ…"],
  ["Send", "भेजें", "ಕಳುಹಿಸಿ"], ["Clear conversation", "बातचीत साफ़ करें", "ಸಂಭಾಷಣೆ ಅಳಿಸಿ"], ["Close assistant", "सहायक बंद करें", "ಸಹಾಯಕ ಮುಚ್ಚಿ"],
  ["Hi! I explain everything on screen in plain words. Press any **Explain** button next to a section, or ask me a question.",
    "नमस्ते! मैं स्क्रीन पर सब कुछ आसान शब्दों में समझाता हूँ। किसी भी सेक्शन के पास **समझाएँ** बटन दबाएँ या मुझसे सवाल पूछें।",
    "ನಮಸ್ಕಾರ! ಪರದೆಯಲ್ಲಿರುವ ಎಲ್ಲವನ್ನೂ ಸರಳ ಪದಗಳಲ್ಲಿ ವಿವರಿಸುತ್ತೇನೆ. ಯಾವುದೇ ವಿಭಾಗದ ಪಕ್ಕದ **ವಿವರಿಸಿ** ಬಟನ್ ಒತ್ತಿ ಅಥವಾ ಪ್ರಶ್ನೆ ಕೇಳಿ."],
  ["Record a voice statement", "आवाज़ में बयान रिकॉर्ड करें", "ಧ್ವನಿ ಹೇಳಿಕೆ ರೆಕಾರ್ಡ್ ಮಾಡಿ"],
  ["Speaker name (optional)", "बोलने वाले का नाम (वैकल्पिक)", "ಮಾತನಾಡುವವರ ಹೆಸರು (ಐಚ್ಛಿಕ)"],
  ["Start recording", "रिकॉर्डिंग शुरू करें", "ರೆಕಾರ್ಡಿಂಗ್ ಪ್ರಾರಂಭಿಸಿ"], ["Stop", "रोकें", "ನಿಲ್ಲಿಸಿ"], ["Record again", "फिर से रिकॉर्ड करें", "ಮತ್ತೆ ರೆಕಾರ್ಡ್ ಮಾಡಿ"],
  ["Record another", "एक और रिकॉर्ड करें", "ಇನ್ನೊಂದು ರೆಕಾರ್ಡ್ ಮಾಡಿ"],
  ["The person agreed to be recorded and to the recording being stored as evidence.", "व्यक्ति ने रिकॉर्ड होने और रिकॉर्डिंग को साक्ष्य के रूप में रखने की सहमति दी है।", "ವ್ಯಕ್ತಿ ರೆಕಾರ್ಡ್ ಆಗಲು ಮತ್ತು ರೆಕಾರ್ಡಿಂಗ್ ಅನ್ನು ಸಾಕ್ಷ್ಯವಾಗಿ ಇಡಲು ಒಪ್ಪಿದ್ದಾರೆ."],
  ["Saving and detecting language…", "सहेज रहे हैं और भाषा पहचान रहे हैं…", "ಉಳಿಸಲಾಗುತ್ತಿದೆ ಮತ್ತು ಭಾಷೆ ಪತ್ತೆ ಮಾಡಲಾಗುತ್ತಿದೆ…"],
  ["Save as evidence and re-analyse", "साक्ष्य के रूप में सहेजें और दोबारा विश्लेषण करें", "ಸಾಕ್ಷ್ಯವಾಗಿ ಉಳಿಸಿ ಮತ್ತು ಮರು-ವಿಶ್ಲೇಷಿಸಿ"],
  ["Stored. The full analysis is running again with this recording.", "सहेज लिया गया। इस रिकॉर्डिंग के साथ पूरा विश्लेषण फिर से चल रहा है।", "ಉಳಿಸಲಾಗಿದೆ. ಈ ರೆಕಾರ್ಡಿಂಗ್ ಜೊತೆ ಸಂಪೂರ್ಣ ವಿಶ್ಲೇಷಣೆ ಮತ್ತೆ ನಡೆಯುತ್ತಿದೆ."],
  ["Stored as evidence.", "साक्ष्य के रूप में सहेजा गया।", "ಸಾಕ್ಷ್ಯವಾಗಿ ಉಳಿಸಲಾಗಿದೆ."],
  ["Confidence", "विश्वास", "ವಿಶ್ವಾಸ"], ["Model confidence report", "मॉडल विश्वास रिपोर्ट", "ಮಾದರಿ ವಿಶ್ವಾಸ ವರದಿ"],
  ["How far the model's output for this case can be trusted.", "इस मामले में मॉडल के आउटपुट पर कितना भरोसा किया जा सकता है।", "ಈ ಪ್ರಕರಣದಲ್ಲಿ ಮಾದರಿಯ ಫಲಿತಾಂಶವನ್ನು ಎಷ್ಟು ನಂಬಬಹುದು."],
  ["Overall confidence", "कुल विश्वास", "ಒಟ್ಟು ವಿಶ್ವಾಸ"], ["High", "उच्च", "ಹೆಚ್ಚು"], ["Moderate", "मध्यम", "ಮಧ್ಯಮ"], ["Low", "कम", "ಕಡಿಮೆ"],
  ["Check these first", "पहले इन्हें जाँचें", "ಮೊದಲು ಇವುಗಳನ್ನು ಪರಿಶೀಲಿಸಿ"], ["Not measured in this case", "इस मामले में नहीं मापा गया", "ಈ ಪ್ರಕರಣದಲ್ಲಿ ಅಳೆಯಲಾಗಿಲ್ಲ"],
  ["Download report (PDF)", "रिपोर्ट डाउनलोड करें (PDF)", "ವರದಿ ಡೌನ್‌ಲೋಡ್ ಮಾಡಿ (PDF)"], ["weight", "भार", "ತೂಕ"],
  ["File integrity (SHA-256)", "फ़ाइल अखंडता (SHA-256)", "ಫೈಲ್ ಸಮಗ್ರತೆ (SHA-256)"], ["Reading quality (OCR / speech / parsing)", "पढ़ने की गुणवत्ता (OCR / आवाज़ / पार्सिंग)", "ಓದುವ ಗುಣಮಟ್ಟ (OCR / ಧ್ವನಿ / ಪಾರ್ಸಿಂಗ್)"],
  ["Timestamp reliability", "समय की विश्वसनीयता", "ಸಮಯದ ವಿಶ್ವಾಸಾರ್ಹತೆ"], ["Source traceability", "स्रोत से जुड़ाव", "ಮೂಲಕ್ಕೆ ಜೋಡಣೆ"],
  ["Claim verification", "दावों का सत्यापन", "ಹೇಳಿಕೆಗಳ ಪರಿಶೀಲನೆ"], ["Naive Bayes label confidence", "नेव बेज़ लेबल विश्वास", "ನೇವ್ ಬೇಸ್ ಲೇಬಲ್ ವಿಶ್ವಾಸ"],
  ["Measured accuracy (Scenario Lab)", "मापी गई सटीकता (परिदृश्य लैब)", "ಅಳೆದ ನಿಖರತೆ (ಸನ್ನಿವೇಶ ಪ್ರಯೋಗಾಲಯ)"],
  ["Hypothesis Lab", "हाइपोथिसिस लैब", "ಹೈಪೋಥೆಸಿಸ್ ಲ್ಯಾಬ್"], ["Only", "केवल", "ಕೇವಲ"],
  ["evidence file(s) in this case.", "साक्ष्य फ़ाइल(ें) इस मामले में हैं।", "ಸಾಕ್ಷ್ಯ ಫೈಲ್(ಗಳು) ಈ ಪ್ರಕರಣದಲ್ಲಿವೆ."],
  ["Timeline, relationships and contradictions need several related files (chats, statements, bank or account records).",
   "समयरेखा, संबंध और विरोधाभास के लिए कई जुड़ी हुई फ़ाइलें चाहिए (चैट, बयान, बैंक या खाते के रिकॉर्ड)।",
   "ಕಾಲರೇಖೆ, ಸಂಬಂಧ ಮತ್ತು ವಿರೋಧಾಭಾಸಗಳಿಗೆ ಹಲವು ಸಂಬಂಧಿತ ಫೈಲ್‌ಗಳು ಬೇಕು (ಚಾಟ್, ಹೇಳಿಕೆ, ಬ್ಯಾಂಕ್ ಅಥವಾ ಖಾತೆ ದಾಖಲೆಗಳು)."],
  ["Add evidence", "साक्ष्य जोड़ें", "ಸಾಕ್ಷ್ಯ ಸೇರಿಸಿ"],
  ["Watch live", "लाइव देखें", "ನೇರವಾಗಿ ನೋಡಿ"], ["Evidence processing", "साक्ष्य प्रोसेसिंग", "ಸಾಕ್ಷ್ಯ ಸಂಸ್ಕರಣೆ"],
  ["Challenge engine", "चुनौती इंजन", "ಸವಾಲು ಇಂಜಿನ್"], ["Hypothesis engine", "हाइपोथिसिस इंजन", "ಹೈಪೋಥೆಸಿಸ್ ಇಂಜಿನ್"],
  // case vocabulary
  ["Fraud / phishing", "धोखाधड़ी / फ़िशिंग", "ವಂಚನೆ / ಫಿಶಿಂಗ್"], ["Account compromise", "खाता हैक", "ಖಾತೆ ಹ್ಯಾಕ್"],
  ["Harassment / preservation", "उत्पीड़न / संरक्षण", "ಕಿರುಕುಳ / ಸಂರಕ್ಷಣೆ"], ["Corporate misconduct", "कॉर्पोरेट दुराचार", "ಕಾರ್ಪೊರೇಟ್ ದುರ್ನಡತೆ"],
  ["Commercial / delivery dispute", "व्यापार / डिलीवरी विवाद", "ವಾಣಿಜ್ಯ / ವಿತರಣೆ ವಿವಾದ"], ["General", "सामान्य", "ಸಾಮಾನ್ಯ"],
  ["Fraud", "धोखाधड़ी", "ವಂಚನೆ"], ["Harassment", "उत्पीड़न", "ಕಿರುಕುಳ"], ["Commercial Dispute", "व्यापार विवाद", "ವಾಣಿಜ್ಯ ವಿವಾದ"],
  ["Corporate", "कॉर्पोरेट", "ಕಾರ್ಪೊರೇಟ್"], ["Extortion", "जबरन वसूली", "ಸುಲಿಗೆ"], ["Account Compromise", "खाता हैक", "ಖಾತೆ ಹ್ಯಾಕ್"],
  ["active", "सक्रिय", "ಸಕ್ರಿಯ"], ["completed", "पूर्ण", "ಪೂರ್ಣ"], ["archived", "संग्रहित", "ಆರ್ಕೈವ್"],
  ["critical", "अति गंभीर", "ಅತಿ ಗಂಭೀರ"], ["high", "उच्च", "ಹೆಚ್ಚು"], ["medium", "मध्यम", "ಮಧ್ಯಮ"], ["low", "कम", "ಕಡಿಮೆ"],
  ["priority", "प्राथमिकता", "ಆದ್ಯತೆ"], ["Description", "विवरण", "ವಿವರಣೆ"], ["Objective", "उद्देश्य", "ಉದ್ದೇಶ"],
  ["Case title", "मामले का शीर्षक", "ಪ್ರಕರಣದ ಶೀರ್ಷಿಕೆ"], ["Case type", "मामले का प्रकार", "ಪ್ರಕರಣದ ಪ್ರಕಾರ"], ["Priority", "प्राथमिकता", "ಆದ್ಯತೆ"],
  ["Incident description", "घटना का विवरण", "ಘಟನೆಯ ವಿವರಣೆ"], ["Investigation objective", "जाँच का उद्देश्य", "ತನಿಖೆಯ ಉದ್ದೇಶ"],
  ["Hindi and Kannada versions (optional)", "हिन्दी और कन्नड़ संस्करण (वैकल्पिक)", "ಹಿಂದಿ ಮತ್ತು ಕನ್ನಡ ಆವೃತ್ತಿಗಳು (ಐಚ್ಛಿಕ)"],
  ["Shown instead of the English text when that language is selected. Evidence itself is never translated.",
   "वह भाषा चुनने पर अंग्रेज़ी की जगह यह दिखेगा। साक्ष्य का कभी अनुवाद नहीं होता।",
   "ಆ ಭಾಷೆ ಆಯ್ಕೆ ಮಾಡಿದಾಗ ಇಂಗ್ಲಿಷ್ ಬದಲು ಇದು ಕಾಣುತ್ತದೆ. ಸಾಕ್ಷ್ಯವನ್ನು ಎಂದಿಗೂ ಅನುವಾದಿಸುವುದಿಲ್ಲ."],
  ["Title", "शीर्षक", "ಶೀರ್ಷಿಕೆ"], ["English original", "मूल अंग्रेज़ी", "ಮೂಲ ಇಂಗ್ಲಿಷ್"],
  // hypothesis lab vocabulary
  ["Fits best", "सबसे उपयुक्त", "ಹೆಚ್ಚು ಹೊಂದಿಕೆ"], ["Re-evaluate", "फिर से आकलन करें", "ಮರು-ಮೌಲ್ಯಮಾಪನ"], ["Export report", "रिपोर्ट निर्यात करें", "ವರದಿ ರಫ್ತು ಮಾಡಿ"],
  ["Strongly supported by available evidence", "उपलब्ध साक्ष्य से मज़बूत समर्थन", "ಲಭ್ಯ ಸಾಕ್ಷ್ಯದಿಂದ ಬಲವಾದ ಬೆಂಬಲ"],
  ["Partially supported", "आंशिक समर्थन", "ಭಾಗಶಃ ಬೆಂಬಲ"], ["Inconclusive", "अनिर्णीत", "ಅನಿರ್ಣೀತ"],
  ["Weakened by available evidence", "उपलब्ध साक्ष्य से कमज़ोर", "ಲಭ್ಯ ಸಾಕ್ಷ್ಯದಿಂದ ದುರ್ಬಲ"], ["Contradicted by verified evidence", "सत्यापित साक्ष्य से खंडित", "ಪರಿಶೀಲಿತ ಸಾಕ್ಷ್ಯದಿಂದ ವಿರೋಧಿತ"],
  ["Rejected by investigator", "जाँचकर्ता ने अस्वीकार किया", "ತನಿಖಾಧಿಕಾರಿ ತಿರಸ್ಕರಿಸಿದ್ದಾರೆ"],
  ["Deliberate fraud", "जानबूझकर धोखाधड़ी", "ಉದ್ದೇಶಪೂರ್ವಕ ವಂಚನೆ"],
  ["The seller collected the payment with no intention of delivering.", "विक्रेता ने डिलीवरी के इरादे के बिना भुगतान लिया।", "ವಿತರಿಸುವ ಉದ್ದೇಶವಿಲ್ಲದೆ ಮಾರಾಟಗಾರ ಹಣ ಪಡೆದರು."],
  ["Genuine delivery delay", "वास्तविक डिलीवरी देरी", "ನಿಜವಾದ ವಿತರಣೆ ವಿಳಂಬ"],
  ["The seller accepted payment in good faith; shipping or logistics problems delayed delivery.", "विक्रेता ने ईमानदारी से भुगतान लिया; शिपिंग की समस्या से देरी हुई।", "ಮಾರಾಟಗಾರ ಪ್ರಾಮಾಣಿಕವಾಗಿ ಹಣ ಪಡೆದರು; ಸಾಗಣೆ ಸಮಸ್ಯೆಯಿಂದ ವಿಳಂಬವಾಯಿತು."],
  ["Incorrect payment destination", "गलत खाते में भुगतान", "ತಪ್ಪು ಖಾತೆಗೆ ಪಾವತಿ"],
  ["The buyer paid a wrong account or UPI ID; the intended seller never received the funds.", "खरीदार ने गलत खाते या यूपीआई आईडी पर भुगतान किया; असली विक्रेता को पैसा नहीं मिला।", "ಖರೀದಿದಾರ ತಪ್ಪು ಖಾತೆ ಅಥವಾ ಯುಪಿಐ ಐಡಿಗೆ ಪಾವತಿಸಿದರು; ನಿಜವಾದ ಮಾರಾಟಗಾರನಿಗೆ ಹಣ ತಲುಪಲಿಲ್ಲ."],
  ["Payment processing issue", "भुगतान प्रक्रिया की समस्या", "ಪಾವತಿ ಪ್ರಕ್ರಿಯೆ ಸಮಸ್ಯೆ"],
  ["The payment was initiated but failed, stayed pending, or was reversed.", "भुगतान शुरू हुआ पर असफल हुआ, लंबित रहा या वापस हुआ।", "ಪಾವತಿ ಆರಂಭವಾಯಿತು ಆದರೆ ವಿಫಲವಾಯಿತು, ಬಾಕಿ ಉಳಿಯಿತು ಅಥವಾ ಹಿಂತಿರುಗಿತು."],
  ["Seller impersonation", "विक्रेता का रूप धरकर ठगी", "ಮಾರಾಟಗಾರನ ಸೋಗು"],
  ["A third party posed as the legitimate seller and redirected the payment.", "किसी तीसरे व्यक्ति ने असली विक्रेता बनकर भुगतान अपनी ओर मोड़ लिया।", "ಮೂರನೇ ವ್ಯಕ್ತಿ ನಿಜವಾದ ಮಾರಾಟಗಾರನಂತೆ ನಟಿಸಿ ಪಾವತಿಯನ್ನು ತಿರುಗಿಸಿದರು."],
  ["Sent by the account holder", "खाताधारक ने भेजा", "ಖಾತೆದಾರರೇ ಕಳುಹಿಸಿದರು"],
  ["The account holder personally wrote and sent the disputed message.", "खाताधारक ने खुद विवादित संदेश लिखा और भेजा।", "ಖಾತೆದಾರರೇ ವಿವಾದಿತ ಸಂದೇಶ ಬರೆದು ಕಳುಹಿಸಿದರು."],
  ["Sent by someone else using the account", "खाते का इस्तेमाल कर किसी और ने भेजा", "ಖಾತೆ ಬಳಸಿ ಬೇರೆಯವರು ಕಳುಹಿಸಿದರು"],
  ["Another person used the holder's account (linked device, SIM swap, shared phone).", "किसी और ने खाताधारक का खाता इस्तेमाल किया (लिंक्ड डिवाइस, सिम स्वैप, साझा फ़ोन)।", "ಬೇರೆಯವರು ಖಾತೆದಾರರ ಖಾತೆ ಬಳಸಿದರು (ಲಿಂಕ್ಡ್ ಡಿವೈಸ್, ಸಿಮ್ ಸ್ವಾಪ್, ಹಂಚಿದ ಫೋನ್)."],
  ["Screenshot fabricated or edited", "स्क्रीनशॉट नकली या बदला हुआ", "ಸ್ಕ್ರೀನ್‌ಶಾಟ್ ನಕಲಿ ಅಥವಾ ತಿದ್ದಿದ್ದು"],
  ["The message never existed in this form; the screenshot was made or altered.", "यह संदेश इस रूप में कभी था ही नहीं; स्क्रीनशॉट बनाया या बदला गया।", "ಈ ರೂಪದಲ್ಲಿ ಸಂದೇಶ ಇರಲೇ ಇಲ್ಲ; ಸ್ಕ್ರೀನ್‌ಶಾಟ್ ತಯಾರಿಸಲಾಗಿದೆ ಅಥವಾ ತಿದ್ದಲಾಗಿದೆ."],
  ["The allegation is accurate as described", "आरोप जैसा बताया गया वैसा ही सही है", "ಆರೋಪ ಹೇಳಿದಂತೆಯೇ ಸರಿ"],
  ["Events happened the way the complaint says.", "घटनाएँ वैसे ही हुईं जैसे शिकायत में लिखा है।", "ದೂರಿನಲ್ಲಿ ಹೇಳಿದಂತೆಯೇ ಘಟನೆಗಳು ನಡೆದವು."],
  ["An innocent or alternative explanation", "निर्दोष या वैकल्पिक व्याख्या", "ನಿರಪರಾಧಿ ಅಥವಾ ಪರ್ಯಾಯ ವಿವರಣೆ"],
  ["The records are explained by ordinary events rather than wrongdoing.", "रिकॉर्ड गलत काम नहीं, सामान्य घटनाओं से समझ आते हैं।", "ದಾಖಲೆಗಳು ತಪ್ಪು ಕೆಲಸವಲ್ಲ, ಸಾಮಾನ್ಯ ಘಟನೆಗಳಿಂದ ವಿವರಿಸಲ್ಪಡುತ್ತವೆ."],
  ["Records are incomplete or unreliable", "रिकॉर्ड अधूरे या अविश्वसनीय हैं", "ದಾಖಲೆಗಳು ಅಪೂರ್ಣ ಅಥವಾ ಅವಿಶ್ವಸನೀಯ"],
  ["Gaps, conflicts or integrity problems mean no explanation can yet be relied on.", "कमियों, विरोधाभासों या अखंडता की समस्या के कारण अभी किसी व्याख्या पर भरोसा नहीं किया जा सकता।", "ಕೊರತೆ, ವಿರೋಧಾಭಾಸ ಅಥವಾ ಸಮಗ್ರತೆ ಸಮಸ್ಯೆಗಳಿಂದ ಇನ್ನೂ ಯಾವ ವಿವರಣೆಯನ್ನೂ ನಂಬಲಾಗದು."],
  ["Deliberate scam", "जानबूझकर ठगी", "ಉದ್ದೇಶಪೂರ್ವಕ ಮೋಸ"],
  ["The other party obtained the money by deception (fake offer, fake bill, fake verification).", "दूसरे पक्ष ने धोखे से पैसा लिया (नकली ऑफ़र, नकली बिल, नकली सत्यापन)।", "ಇನ್ನೊಂದು ಪಕ್ಷ ಮೋಸದಿಂದ ಹಣ ಪಡೆಯಿತು (ನಕಲಿ ಆಫರ್, ನಕಲಿ ಬಿಲ್, ನಕಲಿ ಪರಿಶೀಲನೆ)."],
  ["Genuine transaction or service dispute", "वास्तविक लेन-देन या सेवा विवाद", "ನಿಜವಾದ ವ್ಯವಹಾರ ಅಥವಾ ಸೇವಾ ವಿವಾದ"],
  ["The other party is legitimate; this is a disagreement over a real service, fee or refund.", "दूसरा पक्ष असली है; यह किसी वास्तविक सेवा, शुल्क या रिफ़ंड पर असहमति है।", "ಇನ್ನೊಂದು ಪಕ್ಷ ನಿಜವಾದದ್ದು; ಇದು ನಿಜವಾದ ಸೇವೆ, ಶುಲ್ಕ ಅಥವಾ ರಿಫಂಡ್ ಬಗ್ಗೆ ಭಿನ್ನಾಭಿಪ್ರಾಯ."],
  ["Victim's own account was taken over", "पीड़ित का अपना खाता हैक हुआ", "ಸಂತ್ರಸ್ತರ ಸ್ವಂತ ಖಾತೆ ಹ್ಯಾಕ್ ಆಯಿತು"],
  ["The victim did not make the payment; someone with access to the account or phone did.", "भुगतान पीड़ित ने नहीं, खाते या फ़ोन तक पहुँच रखने वाले किसी और ने किया।", "ಪಾವತಿ ಸಂತ್ರಸ್ತರು ಮಾಡಿಲ್ಲ; ಖಾತೆ ಅಥವಾ ಫೋನ್ ಪ್ರವೇಶ ಹೊಂದಿದ ಬೇರೆಯವರು ಮಾಡಿದರು."],
  ["Records incomplete or misread", "रिकॉर्ड अधूरे या गलत पढ़े गए", "ದಾಖಲೆಗಳು ಅಪೂರ್ಣ ಅಥವಾ ತಪ್ಪಾಗಿ ಓದಲಾಗಿದೆ"],
  ["Key records are missing, conflicting or misread, so no explanation can yet be relied on.", "मुख्य रिकॉर्ड गायब, परस्पर विरोधी या गलत पढ़े गए हैं, इसलिए अभी किसी व्याख्या पर भरोसा नहीं।", "ಮುಖ್ಯ ದಾಖಲೆಗಳು ಕಾಣೆ, ವಿರೋಧಾಭಾಸ ಅಥವಾ ತಪ್ಪಾಗಿ ಓದಲಾಗಿದೆ, ಆದ್ದರಿಂದ ಇನ್ನೂ ಯಾವ ವಿವರಣೆಯನ್ನೂ ನಂಬಲಾಗದು."],
  // hypothesis-lab change notes
  ["Assessment revised in version", "संस्करण में आकलन संशोधित", "ಆವೃತ್ತಿಯಲ್ಲಿ ಮೌಲ್ಯಮಾಪನ ಪರಿಷ್ಕೃತ"], ["after new evidence", "नए साक्ष्य के बाद", "ಹೊಸ ಸಾಕ್ಷ್ಯದ ನಂತರ"],
  ["Leading explanation", "मुख्य व्याख्या", "ಮುಖ್ಯ ವಿವರಣೆ"], ["New evidence", "नया साक्ष्य", "ಹೊಸ ಸಾಕ್ಷ್ಯ"],
  ["Later versions re-checked the evidence without changing these results.", "बाद के संस्करणों ने साक्ष्य दोबारा जाँचा पर ये नतीजे नहीं बदले।", "ನಂತರದ ಆವೃತ್ತಿಗಳು ಸಾಕ್ಷ್ಯವನ್ನು ಮರುಪರಿಶೀಲಿಸಿದವು, ಆದರೆ ಈ ಫಲಿತಾಂಶಗಳು ಬದಲಾಗಲಿಲ್ಲ."],
  ["Re-evaluation with updated findings or investigator feedback.", "अद्यतन निष्कर्षों या जाँचकर्ता की प्रतिक्रिया के साथ पुनर्मूल्यांकन।", "ನವೀಕರಿಸಿದ ಫಲಿತಾಂಶ ಅಥವಾ ತನಿಖಾಧಿಕಾರಿಯ ಪ್ರತಿಕ್ರಿಯೆಯೊಂದಿಗೆ ಮರುಮೌಲ್ಯಮಾಪನ."],
  ["strongly supported", "मज़बूत समर्थन", "ಬಲವಾದ ಬೆಂಬಲ"], ["partially supported", "आंशिक समर्थन", "ಭಾಗಶಃ ಬೆಂಬಲ"], ["inconclusive", "अनिर्णीत", "ಅನಿರ್ಣೀತ"],
  ["weakened", "कमज़ोर", "ದುರ್ಬಲ"], ["contradicted", "खंडित", "ವಿರೋಧಿತ"], ["rejected", "अस्वीकृत", "ತಿರಸ್ಕೃತ"],
  ["Payment recorded as made", "भुगतान किया गया दर्ज है", "ಪಾವತಿ ಮಾಡಲಾಗಿದೆ ಎಂದು ದಾಖಲಾಗಿದೆ"], ["Payment app shows success", "भुगतान ऐप सफलता दिखाता है", "ಪಾವತಿ ಆ್ಯಪ್ ಯಶಸ್ಸು ತೋರಿಸುತ್ತದೆ"],
  ["Payment failed, pending or reversed", "भुगतान असफल, लंबित या वापस", "ಪಾವತಿ ವಿಫಲ, ಬಾಕಿ ಅಥವಾ ಹಿಂತಿರುಗಿದೆ"], ["Money credited back", "पैसा वापस जमा हुआ", "ಹಣ ಹಿಂತಿರುಗಿ ಜಮೆಯಾಗಿದೆ"],
  ["Shipment recorded", "शिपमेंट दर्ज", "ಸರಕು ರವಾನೆ ದಾಖಲಾಗಿದೆ"], ["Delivery recorded", "डिलीवरी दर्ज", "ವಿತರಣೆ ದಾಖಲಾಗಿದೆ"], ["A delay is reported", "देरी की सूचना है", "ವಿಳಂಬ ವರದಿಯಾಗಿದೆ"],
  ["Seller could not be reached", "विक्रेता से संपर्क नहीं हो सका", "ಮಾರಾಟಗಾರರನ್ನು ಸಂಪರ್ಕಿಸಲಾಗಲಿಲ್ಲ"],
  ["Seller acknowledges receiving payment", "विक्रेता भुगतान मिलने की बात मानता है", "ಮಾರಾಟಗಾರ ಪಾವತಿ ಸ್ವೀಕರಿಸಿದ್ದನ್ನು ಒಪ್ಪುತ್ತಾರೆ"],
  ["Seller says no payment arrived", "विक्रेता कहता है कोई भुगतान नहीं आया", "ಯಾವುದೇ ಪಾವತಿ ಬಂದಿಲ್ಲ ಎಂದು ಮಾರಾಟಗಾರ ಹೇಳುತ್ತಾರೆ"],
  ["Refund refused or more money demanded", "रिफ़ंड से इनकार या और पैसे की माँग", "ರಿಫಂಡ್ ನಿರಾಕರಣೆ ಅಥವಾ ಹೆಚ್ಚು ಹಣದ ಬೇಡಿಕೆ"],
  ["Refund offered or made", "रिफ़ंड की पेशकश या दिया गया", "ರಿಫಂಡ್ ನೀಡುವ ಭರವಸೆ ಅಥವಾ ನೀಡಲಾಗಿದೆ"],
  ["Payment details changed during the deal", "सौदे के बीच भुगतान विवरण बदला", "ವ್ಯವಹಾರದ ಮಧ್ಯೆ ಪಾವತಿ ವಿವರ ಬದಲಾಯಿತು"],
  ["The real seller disowns the contact", "असली विक्रेता उस संपर्क से इनकार करता है", "ನಿಜವಾದ ಮಾರಾಟಗಾರ ಆ ಸಂಪರ್ಕವನ್ನು ನಿರಾಕರಿಸುತ್ತಾರೆ"],
  ["Allegation in a complaint or statement", "शिकायत या बयान में आरोप", "ದೂರು ಅಥವಾ ಹೇಳಿಕೆಯಲ್ಲಿನ ಆರೋಪ"],
  ["Paid identifier differs from the one the seller gave", "भुगतान किया गया पहचानकर्ता विक्रेता के दिए से अलग है", "ಪಾವತಿಸಿದ ಗುರುತು ಮಾರಾಟಗಾರ ನೀಡಿದ್ದಕ್ಕಿಂತ ಭಿನ್ನ"],
  ["Paid identifier matches the one the seller gave", "भुगतान किया गया पहचानकर्ता विक्रेता के दिए से मेल खाता है", "ಪಾವತಿಸಿದ ಗುರುತು ಮಾರಾಟಗಾರ ನೀಡಿದ್ದಕ್ಕೆ ಹೊಂದಿಕೆಯಾಗುತ್ತದೆ"],
  ["Documented alternative explanation", "दर्ज वैकल्पिक व्याख्या", "ದಾಖಲಿತ ಪರ್ಯಾಯ ವಿವರಣೆ"], ["High-severity evidence gap", "गंभीर साक्ष्य कमी", "ಗಂಭೀರ ಸಾಕ್ಷ್ಯ ಕೊರತೆ"],
  ["Sender authenticated (SPF and DKIM pass)", "प्रेषक सत्यापित (SPF और DKIM पास)", "ಕಳುಹಿಸಿದವರು ದೃಢೀಕೃತ (SPF ಮತ್ತು DKIM ಪಾಸ್)"],
  ["Sender cannot be verified (no SPF/DKIM pass)", "प्रेषक सत्यापित नहीं (SPF/DKIM पास नहीं)", "ಕಳುಹಿಸಿದವರನ್ನು ಪರಿಶೀಲಿಸಲಾಗದು (SPF/DKIM ಪಾಸ್ ಇಲ್ಲ)"],
  ["The victim says they made the payment themselves", "पीड़ित कहता है भुगतान उसने खुद किया", "ಪಾವತಿಯನ್ನು ತಾವೇ ಮಾಡಿದ್ದೇವೆ ಎಂದು ಸಂತ್ರಸ್ತರು ಹೇಳುತ್ತಾರೆ"],
  // common
  ["Loading", "लोड हो रहा है", "ಲೋಡ್ ಆಗುತ್ತಿದೆ"], ["Retry", "फिर से कोशिश करें", "ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ"], ["Close", "बंद करें", "ಮುಚ್ಚಿ"],
  ["Download PDF", "पीडीएफ़ डाउनलोड करें", "ಪಿಡಿಎಫ್ ಡೌನ್‌ಲೋಡ್ ಮಾಡಿ"], ["New case", "नया मामला", "ಹೊಸ ಪ್ರಕರಣ"], ["Run scenario", "परिदृश्य चलाएँ", "ಸನ್ನಿವೇಶ ನಡೆಸಿ"],
];

const DICT: Record<Lang, Map<string, string>> = { en: new Map(), hi: new Map(ROWS.map((r) => [r[0], r[1]])), kn: new Map(ROWS.map((r) => [r[0], r[2]])) };
const KEY = "evx_lang";
let current: Lang = (() => { try { const v = localStorage.getItem(KEY) as Lang; return v && v in DICT ? v : "en"; } catch { return "en"; } })();

/** Translate an English UI string into the current language (falls back to English). */
export function t(s: string): string {
  if (current === "en" || !s) return s;
  return DICT[current].get(s) ?? DICT[current].get(s.trim()) ?? s;
}
/** Translate when the value is a plain string; leave React nodes untouched. */
export const tn = <T,>(v: T): T => (typeof v === "string" ? (t(v) as unknown as T) : v);
export const getLang = () => current;

/** A case's title / description / objective in the selected language, falling back to the English original. */
export function ct(c: any, field: "title" | "description" | "objective"): string {
  if (!c) return "";
  return (current !== "en" && c.translations?.[current]?.[field]) || c[field] || "";
}

const Ctx = createContext<{ lang: Lang; setLang: (l: Lang) => void }>({ lang: current, setLang: () => {} });
export const useLang = () => useContext(Ctx);

export function LangProvider({ children }: { children: ReactNode }) {
  const [lang, set] = useState<Lang>(current);
  useEffect(() => { document.documentElement.lang = lang; }, [lang]);
  const setLang = (l: Lang) => { current = l; try { localStorage.setItem(KEY, l); } catch { /* storage blocked */ } set(l); };
  // Re-mount the tree on change so every t() call re-renders in the new language.
  return <Ctx.Provider value={{ lang, setLang }}><div key={lang} className="contents">{children}</div></Ctx.Provider>;
}

export function LangSwitch({ className = "" }: { className?: string }) {
  const { lang, setLang } = useLang();
  return (
    <div className={`flex border-2 border-ink-900 ${className}`} role="group" aria-label="Language">
      {LANGS.map((l) => (
        <button key={l.id} onClick={() => setLang(l.id)} title={l.label} aria-pressed={lang === l.id}
          className={`flex-1 px-2 py-1 text-xs font-bold ${lang === l.id ? "bg-acid text-ink-900" : "bg-surface text-ink-900 hover:bg-acid/40"}`}>{l.label}</button>))}
    </div>
  );
}
