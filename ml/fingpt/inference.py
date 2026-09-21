import re

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel

BASE_MODEL = "meta-llama/Llama-2-7b-hf"
LORA_ADAPTER = "FinGPT/fingpt-mt_llama2-7b_lora"

FIELD_PATTERNS = {
    "sentiment": r"1\.\s*Sentiment:\s*(.+)",
    "event": r"2\.\s*Event:\s*(.+)",
    "financial_impact": r"3\.\s*Financial Impact:\s*(.+)",
    "business_impact": r"4\.\s*Business Impact:\s*(.+)",
    "market_impact": r"5\.\s*Short-term Market Impact:\s*(.+)",
    "reason": r"6\.\s*Reason:\s*(.+)",
}


def _pick_device_and_dtype():
    if torch.cuda.is_available():
        return "cuda", torch.float16
    if torch.backends.mps.is_available():
        return "mps", torch.float16
    return "cpu", torch.float32


def load_model(base_model=BASE_MODEL, lora_adapter=LORA_ADAPTER):
    device, dtype = _pick_device_and_dtype()

    tokenizer = AutoTokenizer.from_pretrained(base_model)

    base = AutoModelForCausalLM.from_pretrained(base_model, torch_dtype=dtype)
    base.to(device)

    model = PeftModel.from_pretrained(base, lora_adapter)
    model.eval()

    return model, tokenizer


def analyze_news(model, tokenizer, prompt, max_new_tokens=256):
    device = next(model.parameters()).device

    inputs = tokenizer(prompt, return_tensors="pt").to(device)

    with torch.no_grad():
        output = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=False,
            temperature=1.0,
            pad_token_id=tokenizer.eos_token_id,
        )

    generated = tokenizer.decode(
        output[0][inputs["input_ids"].shape[1]:],
        skip_special_tokens=True,
    )

    return {
        "raw": generated.strip(),
        "parsed": _parse_response(generated),
    }


def _parse_response(text):
    parsed = {}

    for field, pattern in FIELD_PATTERNS.items():
        match = re.search(pattern, text)
        parsed[field] = match.group(1).strip() if match else None

    return parsed
