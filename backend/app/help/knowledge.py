"""Plain-language guide used by the "Explain" assistant.

Each topic explains one part of GhostTrace in simple words: what it is, a concrete example, why it
matters, and a practical tip. ``keywords`` let the assistant match section titles and free-text
questions to the right topic without any AI model.
"""
from __future__ import annotations

T: dict[str, dict] = {}


def topic(key, title, keywords, what, example, why, tip, related=()):
    T[key] = {"key": key, "title": title, "keywords": [k.lower() for k in keywords], "what": what, "example": example,
              "why": why, "tip": tip, "related": list(related)}


# ------------------------------------------------------------------ the product
topic("evidence_x", "What GhostTrace is", ["ghosttrace", "ghost trace", "evidence-x", "evidencex", "this app", "platform", "what is this", "overview of the app", "landing", "welcome"],
      "GhostTrace is a workspace for digital investigations. You put in files - emails, chats, screenshots, bank statements, recordings - and it reads them, lines up what happened, finds things that don't add up, and tells you what's still missing.",
      "A fraud victim gives you an email, a WhatsApp export and a bank statement. GhostTrace shows the email came first, the payment followed 35 minutes later, and the receipt's reference number doesn't match the bank's.",
      "Investigations are slow because the clues are spread across many files. Having them connected in one place, with every finding pointing back to its source, saves hours and reduces mistakes.",
      "Start with Cases → New case, upload files, press Start processing, then look at the Timeline and Contradictions.",
      ["cases", "evidence_vault", "processing", "challenge"])
topic("dashboard", "Overview dashboard", ["overview", "dashboard", "investigation workspace", "live figures", "needs attention"],
      "The dashboard is the home screen. It counts your cases, files, open problems and recent activity, using live data from your own cases.",
      "'Contradictions 4' means four places where two records disagree are waiting in your cases.",
      "It tells you at a glance where attention is needed, without opening every case.",
      "Click any recent case or decision to jump straight into it. Scenario Lab test cases are left out so the numbers reflect real work.",
      ["cases", "contradictions", "gaps"])
topic("stat_cards", "The number tiles", ["cases", "active", "completed", "evidence files", "pending reviews", "open gaps", "running jobs", "processed"],
      "Each tile is a live count. 'Evidence files' is how many files are stored, 'Pending reviews' is how many findings still need a person to confirm or dismiss them, 'Open gaps' is how many pieces of missing evidence are still unresolved, and 'Running jobs' is analysis happening right now.",
      "Pending reviews 7 = seven engine findings waiting for a human yes or no.",
      "The engine suggests; people decide. These counts show how much human checking is outstanding.",
      "Work the 'Pending reviews' number down before you generate a final report.",
      ["contradictions", "human_review"])
topic("charts", "Charts on the dashboard", ["evidence intake", "last 14 days", "evidence by type", "contradictions by category", "reviewer verdicts", "chart"],
      "The charts summarise your workload: how many files arrived each day, what kinds of files they are, which kinds of contradictions were found, and how the reviewer judged your cases.",
      "A spike in 'Evidence intake' on one day means a big batch of files was uploaded then.",
      "Patterns help you plan - for example, many 'amount conflicts' suggest asking banks for statements.",
      "Hover over bars to see exact numbers.", ["contradictions"])

# ------------------------------------------------------------------ cases
topic("cases", "Cases", ["cases", "case", "investigations", "case list", "open a new case", "new case", "recent cases"],
      "A case is a folder for one investigation. It holds that investigation's files, findings, people with access and reports - completely separate from other cases.",
      "'KYC phishing payment - A. Rao' is one case; a delivery dispute would be another.",
      "Keeping cases separate means people only see what they are allowed to see, and findings never mix between investigations.",
      "Give the case a clear title and objective - the objective appears in the report.",
      ["case_summary", "access"])
topic("case_summary", "Case summary", ["summary", "incident & objective", "incident", "objective", "investigation workflow", "current assessment"],
      "The summary page shows what the case is about, what you are trying to find out, how far the work has got, and the engine's current assessment.",
      "The checklist shows 'Upload evidence ✓, Run processing ✓, Review contradictions …' so you know the next step.",
      "It keeps the purpose of the investigation visible so the work stays focused.",
      "Use 'Edit case' to update the description or objective as you learn more.",
      ["cases", "challenge"])
topic("access", "Access, sharing and roles", ["access", "assignments", "share", "members", "roles", "users & access", "permissions", "your permissions", "user management"],
      "Every user has a role (admin, investigator, reviewer, viewer) that says what they can do. On top of that, each case has its own member list - you only see cases you've been added to.",
      "A reviewer added as 'viewer' to a case can read it but not upload files or change it.",
      "Evidence is sensitive. Two layers of permission stop people seeing cases they shouldn't.",
      "Only the case owner can share a case or allow external AI for it.",
      ["external_ai"])
topic("external_ai", "External AI provider", ["external ai", "ai provider", "authorise external ai", "llm", "language model"],
      "By default GhostTrace never sends evidence to an outside AI service. If the case owner switches this on, the counter-investigation step may send extracted text to the configured AI provider for extra ideas - and every idea it returns is still checked against the evidence.",
      "Left off, all analysis runs on this server with fixed rules.",
      "Evidence can be private. Sending it outside should be a deliberate, recorded decision.",
      "Leave it off unless your organisation has approved the provider.",
      ["challenge", "verification"])
topic("case_history", "Case history", ["case history", "recent activity", "activity"],
      "A running list of what happened in the case and who did it - uploads, processing, reviews, reports.",
      "'Evidence intake · admin · 10:42' shows when a file was added and by whom.",
      "It answers 'who did what, when' without digging through logs.",
      "For the full tamper-evident log, open Integrity & Audit.", ["audit"])

# ------------------------------------------------------------------ vault & integrity
topic("evidence_vault", "Evidence Vault", ["evidence vault", "evidence", "upload", "drop evidence", "files", "evidence item", "vault"],
      "The vault is where files are stored. Each upload gets a code like EV-003, its exact original is kept untouched, and anything the system produces from it (like OCR text) is stored separately.",
      "You upload a screenshot of a payment; it becomes EV-004, its fingerprint is recorded, and the text read from it is saved as a separate 'derivative'.",
      "Investigators must be able to show the original was never changed by the tool.",
      "Fill in 'Collection source' (where the file came from) - it strengthens the record of how it was obtained.",
      ["sha256", "derivatives", "collection"])
topic("sha256", "SHA-256 hash (file fingerprint)", ["sha-256", "sha256", "hash", "fingerprint", "verify hash", "re-verify", "integrity verification", "hash verification"],
      "A SHA-256 hash is a long code calculated from a file's exact bytes - like a fingerprint. If even one character in the file changes, the code changes completely.",
      "If EV-004's code today matches the code recorded at upload, the stored file is byte-for-byte the one received.",
      "It proves the file hasn't changed since it entered GhostTrace. It does NOT prove the file was genuine before it arrived.",
      "Press 'Verify hash' or 'Re-verify all' before producing a report.",
      ["evidence_vault", "integrity_inspection"])
topic("derivatives", "Derivatives", ["derivative", "derivatives", "ocr text", "transcript", "extracted text file"],
      "A derivative is something produced from an original file - for example the text read from a screenshot or the transcript of a recording. It's stored next to the original but never replaces it.",
      "EV-010 voicemail.wav (original) → transcript.txt (derivative, with its own fingerprint).",
      "You can always go back to the untouched original to check what the system extracted.",
      "Download a derivative from the evidence's 'Metadata & integrity' tab.", ["evidence_vault"])
topic("collection", "Collection & provenance", ["collection source", "collected by", "provenance", "collection information", "collection log"],
      "Provenance is the story of where a file came from: who collected it, from which device or account, when, and how.",
      "'Exported from the victim's phone via WhatsApp → Export chat, 12 Mar, by Officer K.'",
      "A file with no collection story is harder to rely on - you can't say where it came from.",
      "Record collection details at upload time while they're fresh.", ["sha256", "gaps"])
topic("integrity_inspection", "Integrity inspection", ["integrity inspection", "integrity checks", "anomal", "metadata", "missing email headers", "inconsistent copies", "what integrity verification shows", "evidence integrity"],
      "Integrity inspection looks for things worth a second look: a file's metadata dates that don't make sense, an email missing its routing headers, a file saying it's one type but being another, or two copies of the 'same' screenshot showing different amounts.",
      "'Email lacks Received and Authentication-Results headers' - so you can't tell which server really sent it.",
      "These are warning lights for a person to check, not proof that anything was tampered with.",
      "High and medium items are worth checking first; 'info' items are usually normal (e.g. screenshots have no camera data).",
      ["sha256", "dna"])
topic("audit", "Audit log", ["audit", "audit log", "audit trail", "hash-chained", "append-only", "audit chain verification", "per-case integrity"],
      "The audit log records every action - uploads, views, reviews, exports. Each entry is chained to the previous one with a hash, so if anyone edits or deletes an old entry, the chain visibly breaks.",
      "Pressing 'Verify chain' recomputes every link; 'Chain intact: 412 entries' means nothing was altered.",
      "It shows the investigation was handled properly and lets you prove it later.",
      "Verify the chain before sharing a final report.", ["sha256"])

# ------------------------------------------------------------------ processing & extraction
topic("processing", "Evidence processing", ["processing", "evidence processing pipeline", "start processing", "processing status", "run log", "agent outputs", "extraction results by file"],
      "Processing reads every file and turns it into structured information. A chain of steps (agents) runs in order: check files, extract text, find names and numbers, build the timeline, link things, compare files, spot conflicts and gaps.",
      "After processing a bank CSV, each row becomes a dated, searchable record linked to the account and amount it mentions.",
      "Without this step the system only has files; after it, it has facts it can connect and check.",
      "Re-run processing after uploading new files so everything is compared together.",
      ["extraction", "agents", "timeline"])
topic("extraction", "Extraction (reading files)", ["extraction", "ocr", "speech", "transcription", "extracted content", "segments", "extractor"],
      "Extraction pulls the content out of each file: text from PDFs and Word files, rows from spreadsheets, messages from chats, headers from emails, text from images (OCR) and speech from audio or video (transcription). Each piece keeps its exact location, like 'Page 3' or 'Row 4'.",
      "A screenshot's line 'UPI Ref No: 407215583921' is extracted as OCR line 5 of EV-004.",
      "Every later finding can point back to the precise spot it came from.",
      "OCR can misread characters - check important values against the original image.",
      ["evidence_vault", "citations"])
topic("agents", "The agents", ["agents", "agent", "pipeline", "langgraph", "execution trace", "intake", "entity intelligence", "relationship agent"],
      "Agents are specialised workers, each doing one job in order: Intake checks files, Extraction reads them, Entity Intelligence finds names and numbers, Timeline orders events, Relationship links things, Evidence DNA compares files, Integrity Inspection looks for anomalies, Contradiction and Gap agents find conflicts and missing pieces. Then the Challenge agents test the explanation.",
      "The green chips in the pipeline show each agent finished and how long it took.",
      "Splitting the work makes each step checkable - you can see exactly what each agent produced.",
      "Open 'Agent outputs (structured JSON)' to see exactly what each step produced.",
      ["challenge", "replay"])

# ------------------------------------------------------------------ intelligence
topic("timeline", "Timeline", ["timeline", "chronolog", "events", "timestamp", "silent period", "simultaneous", "reported vs header"],
      "The timeline puts every dated event from every file in order. Each time is labelled with where it came from: stated in the record, taken from file metadata, estimated from words like 'yesterday', or unknown.",
      "Email received 09:12 → chat starts 09:31 → bank debit 09:47, all on 10 March.",
      "Seeing the order of events reveals cause and effect - and conflicts when two records disagree about when something happened.",
      "Times marked 'date only' or with the ⓘ (assumed timezone) are less certain. Upload and file times are hidden by default because they are not event times.",
      ["timestamp_kinds", "contradictions"])
topic("timestamp_kinds", "Timestamp labels", ["source-reported", "source reported", "metadata", "estimated", "unknown", "timezone", "provenance of time", "date only", "system"],
      "Source-reported: the time is written in the record itself. Metadata: taken from the file's hidden properties (can be wrong). Estimated: worked out from phrases like 'yesterday'. Unknown: no time at all. System: when GhostTrace received the file - not when anything happened.",
      "A chat message's own time is source-reported; a PDF's 'created' date is metadata.",
      "Different sources of time are not equally reliable; the labels stop weak times being treated as facts.",
      "If a case's timezone is unknown, choose 'unknown' so times aren't silently converted.",
      ["timeline"])
topic("entities", "Entities", ["entities", "entity", "names", "identifiers", "phone", "email address", "extracted entities"],
      "Entities are the 'who and what' found in the evidence: people's names, phone numbers, email addresses, websites, account numbers, transaction and order references, IP addresses, devices, places.",
      "+91 98765 43210 appears in the email, the website screenshot and the chat - one entity, three mentions.",
      "Seeing where the same identifier shows up connects files that look unrelated.",
      "A shared phone number links records - it does not prove two names are the same person.",
      ["graph", "dna"])
topic("graph", "Relationship graph", ["relationship", "relationships", "entity graph", "graph", "network", "shortest path", "connections", "nodes"],
      "The graph draws entities as dots and their connections as lines. Solid lines are seen directly in a record (an email from A to B). Dashed amber lines are inferred leads (two names using the same phone) - not proof.",
      "Click the phishing website dot to see it is linked to the scam phone number in the email body.",
      "Pictures of connections make hidden links obvious.",
      "Shift-click two dots to highlight the shortest connecting path; double-click a dot to focus on its neighbours.",
      ["entities", "dna"])
topic("dna", "Evidence DNA", ["evidence dna", "dna", "dependencies", "duplicate", "near-duplicate", "derived", "shared source", "independent", "source groups", "shared identifiers", "fingerprint", "related evidence"],
      "Evidence DNA compares every file with every other file to see how they are related: exact copies, near-copies (e.g. a screenshot of a PDF), one derived from another (a forwarded email), from the same source (two records from the same bank), or truly independent.",
      "Two screenshots of the same receipt are one source, not two confirmations.",
      "Three copies of one record are not three witnesses. DNA stops copies being counted as independent corroboration.",
      "Look at 'Independent source groups' - that's how many truly separate sources you really have.",
      ["challenge", "integrity_inspection"])
topic("contradictions", "Contradictions", ["contradiction", "contradictions", "conflict", "discrepanc", "direct contradiction", "potential", "contextual", "priority"],
      "A contradiction is where two records about the same thing disagree - a different amount, date, quantity or reference number. Direct means the same record clearly disagrees; potential means they might describe different events; contextual means a statement conflicts with a record.",
      "The receipt says reference 407215583921 but the bank says 407215538921 - two digits swapped.",
      "Conflicts are where the truth is usually hiding; each one needs explaining.",
      "Confirm or dismiss each one after checking both sources - your decision is recorded and appears in the report.",
      ["human_review", "missing_evidence"])
topic("gaps", "Evidence gaps", ["gaps", "evidence gaps", "missing", "incomplete", "checklist", "missing information", "to resolve"],
      "A gap is something that should exist but hasn't been collected: a bank record for a payment, the rest of a chat, an attachment, an email's full headers, a courier's proof of delivery.",
      "'A refund is promised but no record shows a refund was made.'",
      "Gaps show what you can't yet prove. A missing record is NOT evidence that anyone did wrong.",
      "Tick off checklist items as you collect them, then mark the gap resolved.",
      ["missing_evidence"])

# ------------------------------------------------------------------ flagship
topic("challenge", "Challenge Centre", ["challenge", "challenge centre", "challenge engine", "adversarial", "hypothesis", "hypotheses", "candidate", "balanced assessment"],
      "The Challenge Centre is where GhostTrace tries to prove itself wrong. One agent proposes the best explanation, a second deliberately looks for evidence against it, a third checks every citation against the original files, and a skeptical reviewer weighs both sides.",
      "Explanation: 'phishing email led to the payment'. Challenge: 'the receipt and bank record have different references - maybe two different transfers'.",
      "Good investigations test their own theories. This catches overconfident conclusions before a person relies on them.",
      "Read the challenges before the conclusion. Your 'Accept / Needs more evidence / Reject' decision is recorded.",
      ["decisions", "verification", "counter"])
topic("decisions", "Decisions: SUPPORTED, CONTRADICTED, INCONCLUSIVE, HOLD", ["supported", "contradicted", "inconclusive", "hold", "decision", "verdict", "reviewer verdicts", "recent reviewer decisions"],
      "SUPPORTED: the checked evidence backs the explanation (often with reservations). CONTRADICTED: key evidence goes against it. INCONCLUSIVE: there's a serious alternative explanation. HOLD: not enough verified evidence to say anything yet.",
      "The workplace case is INCONCLUSIVE: access changed after the complaint, but a scheduled-review policy could also explain it.",
      "Saying 'we can't tell yet' is a valid and honest answer - better than a confident wrong one.",
      "A HOLD or INCONCLUSIVE comes with a list of what to collect next in Missing Evidence.",
      ["challenge", "missing_evidence"])
topic("counter", "Counter-investigation & alternatives", ["counter", "counter-investigation", "alternative", "alternatives", "challenges", "evidence challenging", "assumption", "assumptions"],
      "The counter-investigation agent's job is to argue the other side: find records that don't fit, other explanations, weak links and assumptions that haven't been proven.",
      "'The 2,700 difference equals the express shipping charge' - so the 'overpayment' may just be a fee.",
      "It stops the first plausible story being accepted without testing.",
      "Strong challenges (red) deserve attention before any conclusion.", ["challenge"])
topic("verification", "Verification", ["verification", "verify a claim", "verified", "rejected", "unsupported", "fabricated", "citation check", "rejected by the verification agent"],
      "Verification checks every claim against the original files: does the cited file and location exist in this case, does it really contain the quoted value, is the time reliable, and does the claim avoid accusing anyone?",
      "Claim 'UTR is 999999999999' citing the bank SMS → rejected, because that number isn't in the SMS.",
      "This is how AI-generated statements are stopped from silently becoming 'facts'.",
      "Use 'Verify a claim' to check any sentence before you put it in a report.",
      ["challenge", "citations"])
topic("missing_evidence", "Missing Evidence Predictor", ["missing evidence", "recommendation", "recommendations", "what to collect", "collect next", "score", "what would resolve"],
      "The predictor turns open questions into a ranked to-do list: which record to get next, why it matters, what it could confirm or disprove, and the lawful place to request it from.",
      "#1: 'Get the bank's transaction detail for both references' - it decides whether there were one or two payments.",
      "It focuses effort on the evidence that would settle the most important questions.",
      "The score is explained (importance, ability to tell explanations apart, relevance, information value, availability). It never assumes the record exists.",
      ["gaps", "decisions"])
topic("whatif", "What-If Lab", ["what-if", "what if", "whatif", "hypothetical", "scenario branches", "simulate", "sandbox", "branch"],
      "The What-If Lab lets you test 'what if...?' safely. It copies the case into a sandbox, applies your assumption there - for example 'this screenshot is unrelated' - re-runs the analysis and shows what would change. The real case is never touched.",
      "'What if the bank SMS is unreliable?' → the decision stays SUPPORTED but the number of independent sources drops from 3 to 2.",
      "It shows how much a conclusion depends on one piece of evidence.",
      "Everything here is labelled HYPOTHETICAL. Branch a scenario to stack assumptions, and tick two to compare.",
      ["challenge"])
topic("replay", "Investigation Replay", ["replay", "investigation replay", "play from start", "history of actions", "execution"],
      "Replay shows, step by step, what actually happened in the case: each upload, fingerprint, extraction, agent step, finding, decision, review and report, in the order they occurred.",
      "Press Play to watch: upload → hash → OCR → contradiction found → hypothesis → challenge → decision.",
      "It makes the investigation transparent and repeatable - you can explain exactly how a conclusion was reached.",
      "Every entry was saved at the moment it happened; nothing is reconstructed later.",
      ["audit", "agents"])
topic("human_review", "Human review", ["human review", "review", "confirm", "dismiss", "reviewer note", "accept assessment", "human review checkpoint"],
      "Human review is where a person accepts, rejects or annotates what the engine found. The engine never has the final say.",
      "You confirm a contradiction after phoning the bank and add the note 'bank confirmed one transfer'.",
      "Decisions about people must be made by people; your notes also appear in the report.",
      "Add a short reason when you confirm or dismiss - it helps anyone reading the report later.",
      ["contradictions", "challenge"])
topic("citations", "Citations and source links", ["citation", "citations", "ev-", "source reference", "evidence-linked", "source link"],
      "Every finding points to its exact source, written like [EV-004 | OCR line 5] or [EV-005 | Sheet csv | Row 4]. Clicking one opens that file at that spot.",
      "[EV-001 | Email header] opens the phishing email's header with the sender highlighted.",
      "Anyone can check a claim in seconds instead of trusting it blindly.",
      "If a location is unknown, it says so rather than inventing one.", ["reports", "verification"])

# ------------------------------------------------------------------ reports & lab
topic("reports", "Reports", ["report", "reports", "generate", "pdf", "docx", "html", "redact", "investigation reports", "report preview"],
      "A report is a 20-section document built from the case: evidence list with fingerprints, timeline, relationships, contradictions, gaps, the challenged explanation, recommendations and limitations - with a source link on every finding.",
      "Section 10 lists each contradiction with both sources quoted and linked.",
      "It's the shareable result of the investigation, and it keeps engine findings and human decisions clearly labelled.",
      "Tick 'Redact' to mask personal details before sharing. Download as PDF, Word or HTML.",
      ["citations"])
topic("scenario_lab", "Scenario Lab", ["scenario lab", "scenario", "scenarios", "simulation", "case study", "case studies", "ground truth", "planted", "briefing", "custom dataset", "previous runs"],
      "The Scenario Lab runs five realistic, made-up investigations through the real engine and checks the results against an answer key (the 'ground truth').",
      "Phishing scenario: the answer key says the receipt/bank reference mismatch must be found - the lab checks that it was.",
      "It proves the engine works end to end and catches regressions when the rules change.",
      "Reveal 'planted items' to see what the engine was supposed to find.", ["evaluation", "pass_fail_hold"])
topic("pass_fail_hold", "PASS / FAIL / HOLD", ["pass", "fail", "outcome", "expected outcome", "result", "expected vs actual"],
      "PASS: everything important was found and nothing forbidden appeared. FAIL: something important was missed or something wrong was claimed. HOLD: nothing was missed, but the evidence doesn't support a firm conclusion - which can be the correct answer.",
      "The whistleblower scenario is expected to HOLD, because timing alone can't prove retaliation.",
      "It tests the engine honestly, including whether it knows when to stop.",
      "Compare 'Expected' and 'Result' - a match is what you want, whatever the letters say.", ["scenario_lab"])
topic("evaluation", "Evaluation metrics", ["evaluation", "metric", "metrics", "precision", "recall", "f1", "accuracy", "benchmark", "not evaluated", "similarity", "coverage", "unsupported claim rate"],
      "Evaluation scores how well the engine did on each scenario. Precision: of what it reported, how much was right. Recall: of what it should find, how much it found. F1 combines both. 'NOT EVALUATED' means that metric wasn't measured - nothing is guessed.",
      "Contradiction recall 100% = every planted conflict was found.",
      "Measured numbers show where the engine is strong and where it needs work.",
      "These scenarios were used to build the rules, so scores show consistency rather than performance on brand-new evidence.",
      ["scenario_lab"])
topic("settings", "Settings", ["settings", "system configuration", "engines", "storage", "retention", "orchestration"],
      "Settings shows which engines are installed (OCR, speech-to-text, language), whether an AI provider is configured, where files and data are stored, and the retention policy.",
      "'Speech-to-text: installed, model base' means audio files will be transcribed.",
      "It tells you what the platform can and can't do on this installation.",
      "Admins can apply the retention policy here to clean up archived evidence.", ["external_ai"])
topic("profile", "Your profile", ["profile", "change password", "password", "account", "sign out"],
      "Your profile shows your name, role and permissions, and lets you change your password.",
      "Role 'investigator' can create cases, upload evidence and run analysis.",
      "Strong passwords protect sensitive evidence.",
      "Use at least 10 characters with an uppercase letter and a digit.", ["access"])
topic("contact", "Contact form", ["contact", "contact form", "get in touch", "message us"],
      "The contact form sends a message to the people who run this GhostTrace installation. Admins read it in Settings & Admin.",
      "'We'd like a demo for our fraud team' - sent with your name and email.",
      "It's the simplest way to reach the team without an account.",
      "Don't include case evidence in a contact message.", [])
topic("team", "The team (the agents)", ["team", "team showcase", "who works", "meet the team"],
      "The 'team' are the AI agents that do the work, each with one job: Investigator, Counter-Investigator, Verifier, Skeptical Reviewer, Evidence DNA analyst, Integrity inspector, Predictor and Replay recorder.",
      "The Counter-Investigator's whole job is to disagree with the Investigator.",
      "Separate roles mean conclusions are tested, not just produced.",
      "Open any case's Challenge Centre to see them work together.", ["agents", "challenge"])
topic("naive_bayes", "Naive Bayes message labels", ["naive bayes", "naive", "bayes", "classifier", "message labels", "label", "ai lab",
                                                     "model card", "classify", "harassment label", "extortion", "credential request"],
      "OCR reads the words in a screenshot. Naive Bayes then decides what the words mean: harassment, extortion, a payment scam, phishing, a request for an OTP, or an ordinary message. It counts how often each word appears in examples of each kind and picks the most likely kind. It also shows which words pushed it there.",
      "\"Send 5000 tonight or I share your photos\" is labelled Extortion, because 'share', 'photos' and 'send <amount>' are common in extortion examples.",
      "Investigators can find the threatening messages among hundreds quickly, and they can see why each message was flagged.",
      "Treat a label as a pointer for a person to read, not as proof of intent. The model card in the AI Lab shows how accurate it is.", ["authenticity", "extraction"])
topic("tool_calling", "Tool calling (how agents work)", ["tool", "tools", "tool calling", "tool call", "function calling", "tool console", "agent called"],
      "Agents don't read the database directly. They call small tools, such as 'search the chat exports', 'inspect this screenshot' or 'list security events around 22:41', and every call is recorded with its input, output and time. The same tools can be driven by fixed steps (offline) or by an AI model that chooses which tool to call next.",
      "To check a threat screenshot, the agent calls find_disputed_messages, then inspect_screenshot, then search_message_exports, then account_security_events, and so on.",
      "Every step can be replayed and audited, and an AI cannot reach anything a tool doesn't allow.",
      "Open 'Agent called N tools' under any Message Check result to see the trace, or call a tool yourself in the Tool console.", ["authenticity", "agents"])
topic("authenticity", "Message Check (fake screenshot or hacked account?)", ["message check", "authenticity", "impersonation", "hacked", "fake screenshot",
                                                                           "fabricated", "pretending", "linked device", "whatsapp web", "sim swap", "account holder"],
      "When a complaint rests on a chat screenshot, Message Check asks three questions. Is the screenshot fake? Was the message really sent from that account? Was someone else using the account at the time? It compares the screenshot with both phones' chat exports, looks for editing traces, checks account logs for new linked devices or SIM changes, checks where the account holder was, and compares the writing style with their other messages.",
      "A threat appears to come from Rohan. The account log shows a WhatsApp Web session was linked 43 minutes earlier and sent that exact message, while Rohan's phone was in a locker at a hackathon. Result: possible impersonation.",
      "Without this check, a hacked account or an edited screenshot can lead to an innocent person being accused.",
      "The result is a set of indicators for a human to confirm. It never decides who typed the message; it lists the records you still need, such as provider logs and carrier SIM records.", ["naive_bayes", "tool_calling"])

topic("confidence", "Confidence report", ["confidence", "confidence report", "confidence score", "how correct", "how accurate", "reliability", "trust score"],
      "At the end of processing, the confidence report gives a score from 0 to 100 for how reliable the model's output is in this case. It is built from parts you can check: file integrity, how clearly OCR and speech-to-text read the files, how sure the Naive Bayes labels are, how many findings point to a source, how many claims passed verification, and the accuracy measured in the Scenario Lab.",
      "A case of clean PDFs and CSVs might score 88; a case of blurry screenshots and a noisy voice note might score 61, with OCR and speech marked as the weak parts.",
      "You can see which parts of the output to trust and which to double-check. It measures the model, never a person's guilt.",
      "Open the Confidence tab after processing, or read the Confidence section in the PDF report.", ["evaluation", "verification"])
topic("voice", "Voice recording", ["voice", "record", "recording", "microphone", "speak", "language detection", "audio statement"],
      "You can record a person's voice straight from the browser. The recording is stored in the evidence vault with its SHA-256, the Whisper model detects whether it is Kannada, Hindi or English and transcribes it, and the whole analysis runs again with the new evidence.",
      "A witness gives a short statement in Kannada; it appears as a new evidence item marked 'Kannada (94%)' with its transcript, and the timeline and message labels update.",
      "Statements are captured at once and linked to the rest of the evidence.",
      "Ask for the person's consent before recording. The speech model is less accurate for Kannada than for English, so check the transcript.", ["extraction", "naive_bayes"])

topic("hypothesis_lab", "Hypothesis Lab (alternative explanations)", ["hypothesis lab", "hypotheses", "alternative explanation", "alternative hypothesis",
                                                                     "what else could have happened", "evidence matrix", "competing explanations", "fits best"],
      "The Hypothesis Lab never assumes the complaint is right. It writes three to five different explanations for what happened (for example deliberate fraud, a delivery delay, a payment sent to the wrong account, a failed payment, or someone impersonating the seller) and tests each one against every file. A matrix shows which records support or contradict each explanation, a counter-evidence agent attacks each one, and a reviewer checks every citation.",
      "A buyer says the seller cheated her. The bank statement later shows the payment was reversed, so 'payment failed' moves up and 'deliberate fraud' becomes contradicted. The lab shows exactly which record caused the change.",
      "It protects against confirmation bias: the first accusation is tested, not accepted. It also tells you which single record would settle the question.",
      "Labels such as 'partially supported' describe the evidence, not guilt. A person must approve the assessment before it is used.", ["challenge", "missing_evidence"])


GLOSSARY = {k: v for k, v in T.items()}
