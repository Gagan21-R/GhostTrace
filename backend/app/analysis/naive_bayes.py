"""Multinomial Naive Bayes, implemented from scratch so every prediction can be explained.

OCR turns pixels into text. Naive Bayes then decides what that text *is*: harassment, extortion,
a payment scam, phishing, a request for an OTP, or ordinary conversation. Two models live here:

* ``message_model()``: word unigram + bigram features trained on ``nb_corpus.CORPUS``.
* ``AuthorshipNB``: character n-gram features trained per case on one person's known messages vs
  everyone else's. It estimates whether a disputed message reads like that person's writing.

    P(class | words) is proportional to P(class) x product over words of P(word | class)

computed in log space with Laplace (add-alpha) smoothing. ``explain`` returns the words that pushed
the decision most, which is what an investigator or a court needs to see.
"""
from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from functools import lru_cache

from .nb_corpus import CORPUS, LABELS

_WORD = re.compile(r"[a-z0-9ऀ-ॿಀ-೿‌‍']+")  # Latin, Devanagari (Hindi), Kannada
LANG_NAMES = {"en": "English", "hi": "Hindi", "kn": "Kannada", "hinglish": "Hinglish (romanised Hindi)", "mixed": "Mixed script"}
_HINGLISH = re.compile(r"\b(?:hai|hain|nahi|nahin|kya|kar|karo|warna|bhej|bhejo|paise|tera|teri|tujhe|mujhe|dekh|bhai|yaar|abhi|kal|"
                       r"milte|dunga|dungi|hoga|chup|reh|bura)\b", re.I)


def detect_language(text: str) -> str:
    """Script-based: mostly Devanagari -> Hindi, mostly Kannada script -> Kannada, Latin with Hindi words -> Hinglish."""
    dev = len(re.findall(r"[ऀ-ॿ]", text))
    kan = len(re.findall(r"[ಀ-೿]", text))
    lat = len(re.findall(r"[A-Za-z]", text))
    total = (dev + kan + lat) or 1
    if dev / total > 0.6:
        return "hi"
    if kan / total > 0.6:
        return "kn"
    if (dev + kan) / total > 0.2:
        return "mixed"
    return "hinglish" if len(_HINGLISH.findall(text)) >= 2 else "en"
_STOP = {"the", "a", "an", "to", "of", "and", "is", "it", "in", "on", "for", "at", "be", "this", "that", "with", "as", "are", "was"}


def _word_ngrams(text: str) -> list[str]:
    toks = [t for t in _WORD.findall(text.lower()) if t not in _STOP]
    toks = ["<num>" if t.isdigit() and len(t) > 3 else t for t in toks]
    return toks + [f"{a}_{b}" for a, b in zip(toks, toks[1:])]


def word_features(text: str) -> list[str]:
    """Word 1-2 grams plus character 3-5 grams (robust to spelling variants and Hinglish)."""
    s = f" {' '.join(_WORD.findall(text.lower()))} "
    return _word_ngrams(text) + ["#" + s[i:i + k] for k in (3, 4, 5) for i in range(len(s) - k + 1)]


def char_features(text: str, n=(2, 3, 4)) -> list[str]:
    s = f" {re.sub(r'\s+', ' ', text.strip())} "
    out = [s[i:i + k] for k in n for i in range(len(s) - k + 1)]
    # style markers a char model alone under-weights
    out += ["<emoji>"] * len(re.findall(r"[\U0001F300-\U0001FAFF☀-➿]", text))
    out += ["<allcaps>"] * len(re.findall(r"\b[A-Z]{3,}\b", text))
    out += ["<multi!>"] * len(re.findall(r"[!?]{2,}", text))
    return out


class MultinomialNB:
    def __init__(self, alpha: float = 1.0, featurize=word_features):
        self.alpha, self.featurize = alpha, featurize
        self.class_count: Counter = Counter()
        self.feat_count: dict[str, Counter] = defaultdict(Counter)
        self.total: Counter = Counter()
        self.vocab: set[str] = set()

    def fit(self, docs: list[str], labels: list[str]) -> "MultinomialNB":
        for d, y in zip(docs, labels):
            f = self.featurize(d)
            self.class_count[y] += 1
            self.feat_count[y].update(f)
            self.total[y] += len(f)
            self.vocab.update(f)
        return self

    @property
    def classes(self) -> list[str]:
        return sorted(self.class_count)

    def _loglik(self, feat: str, c: str) -> float:
        return math.log((self.feat_count[c][feat] + self.alpha) / (self.total[c] + self.alpha * len(self.vocab)))

    def joint_log(self, text: str) -> dict[str, float]:
        n = sum(self.class_count.values())
        feats = [f for f in self.featurize(text) if f in self.vocab]
        return {c: math.log(self.class_count[c] / n) + sum(self._loglik(f, c) for f in feats) for c in self.classes}

    def predict_proba(self, text: str, temper: bool = False) -> dict[str, float]:
        """``temper`` divides log scores by a feature-count temperature: NB treats overlapping n-grams as
        independent, which makes raw posteriors overconfident. Tempering keeps the ranking, softens the numbers."""
        jl = self.joint_log(text)
        m = max(jl.values())
        t = max(1.0, len([f for f in self.featurize(text) if f in self.vocab]) / 4) if temper else 1.0
        ex = {c: math.exp((v - m) / t) for c, v in jl.items()}
        z = sum(ex.values())
        return {c: v / z for c, v in ex.items()}

    def explain(self, text: str, label: str, k: int = 6) -> list[dict]:
        """Features that most favour ``label`` over the strongest other class (log-likelihood ratio)."""
        others = [c for c in self.classes if c != label]
        out = []
        for f, cnt in Counter(f for f in self.featurize(text) if f in self.vocab).items():
            lr = self._loglik(f, label) - max(self._loglik(f, o) for o in others)
            if lr > 0:
                out.append({"term": f.lstrip("#").replace("_", " ").strip(), "weight": round(lr * cnt, 3), "char": f.startswith("#")})
        words = sorted((o for o in out if not o["char"]), key=lambda x: -x["weight"])
        return [{"term": o["term"], "weight": o["weight"]} for o in words[:k]]


@lru_cache
def message_model() -> MultinomialNB:
    docs, ys = zip(*[(d, y) for y, ds in CORPUS.items() for d in ds])
    return MultinomialNB(alpha=0.5).fit(list(docs), list(ys))


def classify(text: str) -> dict:
    """Classify one message. ``uncertain`` when the top class is not clearly ahead or no known words appear."""
    m = message_model()
    grams = [f for f in word_features(text) if f.startswith("#")]
    known = [f for f in grams if f in m.vocab]
    probs = m.predict_proba(text, temper=True)
    ranked = sorted(probs.items(), key=lambda x: -x[1])
    label, p = ranked[0]
    margin = p - ranked[1][1]
    coverage = len(known) / max(1, len(grams))  # share of character n-grams the model has seen (robust to OCR word merges)
    uncertain = p < 0.45 or margin < 0.2 or coverage < 0.4 or len("".join(_WORD.findall(text.lower()))) < 10
    lang = detect_language(text)
    return {"label": label, "label_name": LABELS[label], "confidence": round(p, 3), "uncertain": uncertain,
            "language": lang, "language_name": LANG_NAMES[lang],
            "probabilities": {c: round(v, 3) for c, v in ranked},
            "top_terms": m.explain(text, label), "known_term_coverage": round(coverage, 2),
            "model": "multinomial-naive-bayes (word 1-2 grams + char 3-5 grams, Laplace alpha=0.5)"}


@lru_cache
def model_card() -> dict:
    """Leave-one-out cross-validation over the training corpus (honest estimate; corpus is small and synthetic)."""
    data = [(d, y) for y, ds in CORPUS.items() for d in ds]
    correct, conf, by_lang = 0, defaultdict(Counter), defaultdict(lambda: [0, 0])
    for i, (d, y) in enumerate(data):
        rest = data[:i] + data[i + 1:]
        m = MultinomialNB(alpha=0.5).fit([x for x, _ in rest], [z for _, z in rest])
        pr = m.predict_proba(d)
        pred = max(pr, key=pr.get)
        conf[y][pred] += 1
        correct += pred == y
        lg = detect_language(d)
        by_lang[lg][0] += pred == y
        by_lang[lg][1] += 1
    per_class = {c: round(conf[c][c] / max(1, sum(conf[c].values())), 3) for c in CORPUS}
    per_language = {LANG_NAMES[k]: {"examples": n, "accuracy": round(ok / n, 3)} for k, (ok, n) in sorted(by_lang.items(), key=lambda x: -x[1][1])}
    return {"model": "Multinomial Naive Bayes (implemented from scratch)", "features": "word unigrams + bigrams + character 3-5 grams",
            "smoothing": "Laplace, alpha=0.5", "classes": LABELS, "training_examples": len(data),
            "loo_accuracy": round(correct / len(data), 3), "per_class_recall": per_class, "per_language": per_language,
            "languages": ["English", "Hindi", "Kannada", "Hinglish"],
            "confusion": {c: dict(conf[c]) for c in CORPUS},
            "limits": "Small synthetic training set; a label is a lead for a human reviewer, never a finding of intent or guilt."}


class AuthorshipNB:
    """Two-class character n-gram NB: 'does this read like <person>?' trained on that person's own messages."""

    MIN_KNOWN = 6

    def __init__(self, known: list[str], others: list[str]):
        self.n_known, self.n_other = len(known), len(others)
        background = [d for ds in CORPUS.values() for d in ds]
        self.model = MultinomialNB(alpha=0.3, featurize=char_features).fit(
            known + others + background, ["person"] * len(known) + ["other"] * (len(others) + len(background)))

    @property
    def usable(self) -> bool:
        return self.n_known >= self.MIN_KNOWN

    def score(self, text: str) -> dict:
        # Equal priors: the background corpus is large and must not decide the answer by itself.
        m = self.model
        feats = [f for f in m.featurize(text) if f in m.vocab]
        ll = {c: sum(m._loglik(f, c) for f in feats) for c in m.classes}
        diff = (ll["person"] - ll["other"]) / max(1, len(feats)) * 8  # per-feature, scaled
        p = min(0.98, max(0.02, 1 / (1 + math.exp(-max(-30, min(30, diff))))))  # never claim certainty about authorship
        return {"p_same_author": round(p, 3), "known_messages": self.n_known, "comparison_messages": self.n_other,
                "distinctive_terms": [t["term"].strip() for t in m.explain(text, "person", 5) if t["term"].strip()],
                "model": "character 2-4 gram naive bayes"}
