"""Naive Bayes classifier, tool registry and message-authenticity scoring."""
from app.analysis import naive_bayes as nb
from app.analysis.authenticity import assess
from app.tools.registry import ToolRegistry, ToolSession


def test_naive_bayes_labels_and_explains():
    r = nb.classify("Send 20000 tonight or I share your photos with everyone")
    assert r["label"] == "extortion" and not r["uncertain"]
    assert r["top_terms"] and sum(r["probabilities"].values()) > 0.99
    assert nb.classify("Please share the OTP you just received")["label"] == "credential_request"
    assert nb.classify("ok")["uncertain"]  # too short to say anything


def test_model_card_is_honest():
    c = nb.model_card()
    assert c["training_examples"] > 150 and 0.6 < c["loo_accuracy"] <= 1.0
    assert set(c["per_class_recall"]) == set(nb.LABELS)


def test_authorship_model_separates_styles():
    known = ["bro did u finish", "da send notes", "lol ok np", "u coming tmrw?", "thanks da", "ok bro cya", "bro wat time"]
    m = nb.AuthorshipNB(known, ["Please send the report.", "Thank you for your help."])
    assert m.usable
    assert m.score("bro u coming da")["p_same_author"] > m.score("I know where you live. You will regret this.")["p_same_author"]


def test_tool_registry_validates_and_traces():
    reg = ToolRegistry()

    @reg.register("echo", "Echo", {"text": {"type": "string"}, "n": {"type": "integer", "minimum": 1, "maximum": 3}}, ["text"])
    def echo(ctx, text, n=1):
        return text * n

    s = ToolSession(reg, None)
    assert s.call("echo", {"text": "a", "n": 9}) == "aaa"  # clamped to maximum
    assert "error" in s.call("echo", {})  # missing required input
    assert "error" in s.call("echo", {"text": "a", "bad": 1})  # unknown input rejected
    assert "error" in s.call("nope", {})
    assert [t["status"] for t in s.trace] == ["ok", "error", "error", "error"]
    assert reg.schemas()[0]["input_schema"]["required"] == ["text"]


class _FakeSession:
    """Stands in for ToolSession with canned tool outputs."""
    def __init__(self, outputs):
        self.outputs, self.trace = outputs, []

    def call(self, name, args=None, why=""):
        self.trace.append(name)
        return self.outputs.get(name, {})


D = {"code": "EV-001", "claimed_sender": "Rohan Verma", "text": "I know where you live", "time_on_screen": "22:41", "screenshot_date": "18 March 2026"}


def test_verdict_fabricated_when_absent_from_exports():
    out = assess(_FakeSession({"inspect_screenshot": {"editing_or_generator": True, "software_tags": "FakeChat"},
                               "search_message_exports": {"exports": [{"code": "EV-002", "messages": 9, "from_sender_device": True}], "matches": []}}), D)
    assert out["verdict"] == "likely_fabricated"
    assert {i["key"] for i in out["indicators"]} >= {"not_in_exports", "generator_or_editor"}


def test_verdict_impersonation_with_linked_device_and_alibi():
    match = {"code": "EV-003", "locator": "msg 12", "time": "18/03/2026, 22:41", "similarity": 1.0, "from_sender_device": True, "text": D["text"]}
    out = assess(_FakeSession({
        "search_message_exports": {"exports": [{"code": "EV-003", "messages": 9, "from_sender_device": True}], "matches": [match]},
        "account_security_events": {"events": [{"type": "device_link", "minutes_before": 43, "what": "Linked device added", "code": "EV-004", "concerns_person": True}],
                                    "message_sent_from_linked_or_web_device": [{"what": "Message sent, WhatsApp Web", "code": "EV-004"}],
                                    "account_logs_available": ["EV-004"]},
        "person_whereabouts": {"records": [{"minutes_from_message": -36, "covers_message_time": True, "record": "Check-in 22:05", "code": "EV-005", "source": "log.csv"}]},
        "compare_writing_style": {"usable": True, "p_same_author": 0.05, "known_messages": 9}}), D)
    assert out["verdict"] == "possible_impersonation"
    assert out["compromise_score"] >= 0.6


def test_verdict_consistent_when_holder_sent_it():
    match = {"code": "EV-003", "locator": "msg 11", "time": "22/03/2026, 23:15", "similarity": 1.0, "from_sender_device": True, "text": D["text"]}
    out = assess(_FakeSession({
        "search_message_exports": {"exports": [{"code": "EV-003", "messages": 13, "from_sender_device": True}], "matches": [match]},
        "account_security_events": {"events": [], "message_sent_from_linked_or_web_device": [], "account_logs_available": ["EV-004"]},
        "compare_writing_style": {"usable": True, "p_same_author": 0.8, "known_messages": 10},
        "messages_after": {"messages": [{"text": "sorry i was angry", "code": "EV-003"}]}}), {**D, "time_on_screen": "23:15"})
    assert out["verdict"] == "consistent_with_account_holder"


def test_multilingual_classification_and_help():
    hi = nb.classify("आज रात तक पैसे भेजो वरना तुम्हारी फोटो सबको भेज दूँगा")
    kn = nb.classify("ನಿಮಗೆ ಬಂದ ಓಟಿಪಿ ನನಗೆ ಕಳಿಸಿ")
    assert hi["language"] == "hi" and hi["label"] == "extortion"
    assert kn["language"] == "kn" and kn["label"] == "credential_request"
    assert nb.detect_language("paise bhej warna video viral kar dunga") == "hinglish"
    assert {"Hindi", "Kannada"} <= set(nb.model_card()["per_language"])
    from app.help import assistant
    assert "विरोधाभास" in assistant.explain("Contradictions", lang="hi")["answer"]
    assert assistant.chat([{"role": "user", "content": "ಕಾಲರೇಖೆ ಎಂದರೇನು"}], lang="kn")["topic"] == "timeline"
