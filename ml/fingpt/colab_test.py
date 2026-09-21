# Run this in Google Colab (GPU runtime: Runtime > Change runtime type > T4/A100).
#
# !pip install -q transformers peft accelerate bitsandbytes
# !hf auth login    # paste your HF token (needs approved Llama-2 access)
#
# Then upload fingpt/prompt.py and fingpt/inference.py to Colab (or git clone the repo)
# and run this script.

from prompt import build_fingpt_prompt
from inference import load_model, analyze_news

sample_row = {
    "company_name": "Tata Motors Limited",
    "symbol": "TATAMOTORS",
    "event_type": "Award of Order / Receipt of Order",
    "published_at": "2026-09-18",
    "content": (
        "Tata Motors Limited has received an order worth Rs. 1,200 crore "
        "from the Ministry of Defence for supply of tactical vehicles, "
        "to be executed over the next 18 months."
    ),
}

prompt = build_fingpt_prompt(sample_row)
print("PROMPT:\n", prompt)

model, tokenizer = load_model()
result = analyze_news(model, tokenizer, prompt)

print("\nRAW OUTPUT:\n", result["raw"])
print("\nPARSED:\n", result["parsed"])
