"""Score the *document* behind an announcement, not just its one-line summary.

`sentiment.py` feeds FinBERT the templated `news.content` line. This module feeds
it the attachment text cached by `attachment_text.py`, which is far longer than
FinBERT's 512-token window and mostly covering-letter boilerplate. It offers
three strategies so the trade-off can be measured rather than assumed:

    head    first 512 tokens. Cheapest, but an NSE filing opens with the
            address block and "Dear Sir/Madam, pursuant to Regulation 30..."
            -- often the least informative part of the whole document.

    mean    split into 480-token chunks, average the probability vectors.
            Stable, but boilerplate chunks outnumber the substantive ones and
            drag every document towards NEUTRAL.

    maxsal  split into chunks, keep the chunk with the strongest non-neutral
            signal, max(P_positive, P_negative). Finds the one paragraph that
            carries the news; the price is sensitivity to a single stray
            sentence, so it over-produces confident labels.

`strip_boilerplate` removes the standard covering-letter furniture first, which
helps all three. It is deliberately conservative: "Sub:" / "Subject:" lines are
kept, because that is where the actual news usually is.

This module never writes to the database; it is a pure scoring helper.
"""

import re

import torch

from .config import CONFIDENCE_THRESHOLD

CHUNK_TOKENS = 480      # leaves room for [CLS]/[SEP] inside FinBERT's 512
MAX_CHUNKS = 16         # ~7,700 tokens, roughly the first 10 pages
HEAD_TOKENS = 510

STRATEGIES = ("head", "mean", "maxsal")


# ---------------------------------------------------------
# Boilerplate removal
# ---------------------------------------------------------

# Matched case-insensitively against a whole line. "Sub:"/"Subject:" is NOT here:
# the subject line is usually the single most informative sentence in the filing.
_BOILERPLATE_PATTERNS = [
    r"^dear (sir|madam|sirs)", r"yours (faithfully|sincerely|truly)",
    r"^thanking you", r"^(with )?(warm )?regards",
    r"this is for your (information|record)", r"kindly take (the above )?on record",
    r"take the same on (your )?record", r"request you to take.{0,30}on record",
    r"national stock exchange of india", r"^bse limited", r"bombay stock exchange",
    r"exchange plaza", r"bandra[- ]kurla complex", r"dalal street",
    r"phiroze jeejeebhoy", r"^plot no", r"mumbai\s*[-–]?\s*400",
    r"scrip code", r"^symbol\s*[:\-]", r"^isin\s*[:\-]", r"trading symbol",
    r"^(company )?cin\s*[:\-]", r"^\(?cin\s*[:\-]", r"regd\.? ?office", r"registered office",
    r"^tel(ephone)?\s*[:\-\.]", r"^fax\s*[:\-]", r"^e-?mail\s*[:\-]", r"^website\s*[:\-]",
    r"www\.[a-z0-9\-]+\.(com|in|org|net)", r"^encl", r"enclosed herewith",
    r"regulation 30", r"regulation 3[0-9] of the sebi", r"listing obligations and disclosure",
    r"sebi \(listing obligations", r"lodr", r"as amended from time to time",
    r"pursuant to (the )?(provisions of )?regulation",
    r"^(company secretary|compliance officer)", r"company secretary (&|and) compliance officer",
    r"^(authorised|authorized) signatory", r"^membership no", r"^acs\b", r"^fcs\b",
    r"^page \d+ of \d+", r"^date\s*[:\-]", r"^place\s*[:\-]", r"^ref(erence)?( no)?\s*[:\-]",
    r"this (letter|disclosure) is (being )?(issued|made)",
    r"^for\s+[a-z0-9&.,' \-]{3,60}limited$",
]

_BOILERPLATE = re.compile("|".join(f"(?:{p})" for p in _BOILERPLATE_PATTERNS), re.I)
_MOSTLY_DIGITS = re.compile(r"^[\W\d]*$")


def strip_boilerplate(text, min_words=4):
    """Drop covering-letter furniture, address blocks and signature lines."""

    if not text:
        return ""

    kept = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if _MOSTLY_DIGITS.match(stripped):          # page numbers, rule lines, tables of figures
            continue
        if len(stripped.split()) < min_words:       # stray header fragments
            continue
        if _BOILERPLATE.search(stripped):
            continue
        kept.append(stripped)

    return "\n".join(kept)


# ---------------------------------------------------------
# Chunking
# ---------------------------------------------------------

def chunk_text(tokenizer, text, chunk_tokens=CHUNK_TOKENS, max_chunks=MAX_CHUNKS):
    """Split into FinBERT-sized pieces, decoded back to strings."""

    text = (text or "").strip()
    if not text:
        return []

    # verbose=False: we deliberately tokenize past 512 and then split, so the
    # tokenizer's "longer than maximum sequence length" warning is just noise.
    ids = tokenizer.encode(text, add_special_tokens=False, truncation=False, verbose=False)
    chunks = []
    for start in range(0, len(ids), chunk_tokens):
        chunks.append(tokenizer.decode(ids[start:start + chunk_tokens]))
        if len(chunks) >= max_chunks:
            break

    return chunks


# ---------------------------------------------------------
# Scoring
# ---------------------------------------------------------

@torch.no_grad()
def predict_probs(scorer, texts, max_length=512, batch_size=8):
    """Probability vectors for `texts`, using the FinBertScorer's tokenizer/model.

    `sentiment.py` truncates at 256 tokens, which is right for the one-line
    summary and wrong for a document chunk, so the forward pass is repeated here
    at the model's real limit instead of changing that module.
    """

    out = []
    for start in range(0, len(texts), batch_size):
        batch = texts[start:start + batch_size]
        encoded = scorer.tokenizer(
            batch, padding=True, truncation=True,
            max_length=max_length, return_tensors="pt",
        ).to(scorer.device)
        probs = torch.softmax(scorer.model(**encoded).logits, dim=-1).cpu()
        out.extend(probs)

    return out


def _prediction(scorer, probs, extra=None):
    top = int(probs.argmax())
    confidence = float(probs[top])
    result = {
        "sentiment": scorer.labels[top],
        "confidence": confidence,
        "scores": {scorer.labels[i]: float(p) for i, p in enumerate(probs)},
        "confident": confidence >= CONFIDENCE_THRESHOLD,
    }
    if extra:
        result.update(extra)
    return result


def score_documents_multi(scorer, texts, strategies=STRATEGIES, chunk_tokens=CHUNK_TOKENS,
                          max_chunks=MAX_CHUNKS, batch_size=8):
    """{strategy: [prediction | None, ...]} for several strategies at once.

    `mean` and `maxsal` are derived from a single chunk forward pass, so asking
    for both costs no more than asking for one -- which matters on CPU, where
    each 512-token pass is the expensive part.

    Empty documents yield None so the caller can keep its rows aligned.
    """

    strategies = list(strategies)
    unknown = set(strategies) - set(STRATEGIES)
    if unknown:
        raise ValueError(f"unknown strategies {sorted(unknown)}; expected {STRATEGIES}")

    results = {name: [None] * len(texts) for name in strategies}

    if "head" in strategies:
        usable = [(i, t) for i, t in enumerate(texts) if (t or "").strip()]
        if usable:
            probs = predict_probs(scorer, [t for _, t in usable], HEAD_TOKENS + 2, batch_size)
            for (i, _), prob in zip(usable, probs):
                results["head"][i] = _prediction(scorer, prob, {"chunks": 1})

    chunked = [name for name in strategies if name in ("mean", "maxsal")]
    if not chunked:
        return results

    # Flatten every document's chunks into one batched pass
    all_chunks, owners = [], []
    for i, text in enumerate(texts):
        for chunk in chunk_text(scorer.tokenizer, text, chunk_tokens, max_chunks):
            all_chunks.append(chunk)
            owners.append(i)

    if not all_chunks:
        return results

    probs = predict_probs(scorer, all_chunks, 512, batch_size)

    per_doc = {}
    for owner, prob, chunk in zip(owners, probs, all_chunks):
        per_doc.setdefault(owner, []).append((prob, chunk))

    neutral_index = next(i for i, label in scorer.labels.items() if label == "NEUTRAL")

    def salience(item):
        return float(max(p for j, p in enumerate(item[0]) if j != neutral_index))

    for i, items in per_doc.items():
        if "mean" in results:
            stacked = torch.stack([p for p, _ in items])
            results["mean"][i] = _prediction(scorer, stacked.mean(dim=0), {"chunks": len(items)})
        if "maxsal" in results:
            prob, chunk = max(items, key=salience)
            results["maxsal"][i] = _prediction(scorer, prob, {
                "chunks": len(items),
                "evidence": chunk[:400],
            })

    return results


def score_documents(scorer, texts, strategy="maxsal", chunk_tokens=CHUNK_TOKENS,
                    max_chunks=MAX_CHUNKS, batch_size=8):
    """One prediction (or None) per document for a single strategy."""

    return score_documents_multi(
        scorer, texts, [strategy], chunk_tokens, max_chunks, batch_size)[strategy]
