"""FinBERT sentiment with a confidence score for each announcement."""

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from .config import (
    CONFIDENCE_THRESHOLD,
    SENTIMENT_BATCH_SIZE,
    SENTIMENT_MAX_LENGTH,
    SENTIMENT_MODEL,
)


def build_text(event_type, content):
    """Announcement text to score; falls back to the event type when there is no body."""

    content = (content or "").strip()
    return content if content else (event_type or "").strip()


class FinBertScorer:
    def __init__(self, model_name=SENTIMENT_MODEL, device="cpu"):
        # CPU is as fast as MPS for short texts on Apple Silicon and is safer for background runs
        self.model_name = model_name
        self.device = device
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_name).to(device).eval()
        self.labels = {i: label.upper() for i, label in self.model.config.id2label.items()}

    @torch.no_grad()
    def predict(self, texts):
        """One prediction per text: sentiment, confidence (top probability), all scores."""

        predictions = []

        for start in range(0, len(texts), SENTIMENT_BATCH_SIZE):
            batch = texts[start:start + SENTIMENT_BATCH_SIZE]
            encoded = self.tokenizer(
                batch,
                padding=True,
                truncation=True,
                max_length=SENTIMENT_MAX_LENGTH,
                return_tensors="pt",
            ).to(self.device)

            probs = torch.softmax(self.model(**encoded).logits, dim=-1).cpu()

            for row in probs:
                top = int(row.argmax())
                confidence = float(row[top])
                predictions.append({
                    "sentiment": self.labels[top],
                    "confidence": confidence,
                    "scores": {self.labels[i]: float(p) for i, p in enumerate(row)},
                    "confident": confidence >= CONFIDENCE_THRESHOLD,
                })

        return predictions
