"""kpi_extractor.py – full functionality + fixes
-----------------------------------------------------------------
* Supports Claude, OpenAI **and DeepSeek** (cheap tier)
* Crash‑proof `_to_int()`; placeholders never raise `ValueError`
* Keeps all original KPI keys & logic
* Drops `bcdf_vdp` / `bcdf_conv` when they're placeholders
* Removes the whole video block if it's just placeholders
* Retains Palmer‑specific PMAX VLA fix
"""

from __future__ import annotations

import json
import re
import time
from typing import Any, Dict, Optional

import requests
import anthropic
import openai

# ---------------------------------------------------------------------------
#  PROMPT & PLACEHOLDERS
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """
You are an expert at extracting specific metrics from dealership marketing
reports. Return ONLY a JSON object with these keys (use placeholders when the
metric truly is missing):

- store_name, date_range
- rsa_impr, rsa_clicks, rsa_cpc, rsa_conv, rsa_cost_conv
- pmax_impr, pmax_clicks, pmax_cpc, pmax_conv, pmax_cost_conv
- pmax_vla_impr, pmax_vla_clicks, pmax_vla_cpc, pmax_vla_conv,
  pmax_vla_cost_conv
- dg_impr, dg_clicks, dg_cpm, dg_conv               # <-- CPM only
- dv_views, dv_viewrate, dv_cpc, dv_cpm  (include only if actual numbers
  appear in the report)
- social_reach, social_impr, social_clicks, social_cpc, social_vdp
- has_bcdf (true/false) and, if true:
  - bcdf_tactics, bcdf_impr, bcdf_clicks, bcdf_cpc,
  - bcdf_conv  (omit if not present)
  - bcdf_vdp   (omit if not present)
"""

# placeholder tokens that appear in the reports or AI output
PLACEHOLDER_NUM   = "[x,xxx]"
PLACEHOLDER_CLICK = "[xxx]"
PLACEHOLDER_COST  = "$x.xx"
PLACEHOLDER_CONV  = "[xx]"
PLACEHOLDER_RATE  = "[xx.xx%]"

# ---------------------------------------------------------------------------
#  HELPER FUNCTIONS
# ---------------------------------------------------------------------------

def _json_from_text(text: str) -> Dict[str, Any]:
    """Extract JSON object from text that may contain markdown or other content."""
    # Try to find JSON object within markdown code blocks
    json_match = re.search(r'```(?:json)?\s*({.*?})\s*```', text, re.DOTALL)
    if json_match:
        json_str = json_match.group(1)
    else:
        # Fall back to finding anything that looks like a JSON object
        json_match = re.search(r'({[\s\S]*})', text)
        json_str = json_match.group(1) if json_match else text
    
    try:
        return json.loads(json_str)
    except (json.JSONDecodeError, TypeError):
        # If we failed to parse JSON, return empty dict
        print(f"Failed to parse JSON from: {text[:200]}...")
        return {}

def _to_int(val: str | int | None) -> Optional[int]:
    if val is None:
        return None
    if isinstance(val, int):
        return val
    cleaned = str(val).replace(",", "").strip()
    return int(cleaned) if cleaned.isdigit() else None


def _is_placeholder(value: Any) -> bool:
    if value is None:
        return True
    s = str(value)
    return any(tok in s for tok in ("[x", "$x", "[xx"))


# ---------------------------------------------------------------------------
#  BCDF ORGANISATION & CLEANUP  (drop‑in replacement)
# ---------------------------------------------------------------------------

def organize_bcdf_tactics(kpis: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalises BCDF tactics coming out of the slide.

    • Any header that contains "GOOGLE" → we treat as Performance Max
      (Stellantis BCDF budgets are always PMAX on Google Ads).

    • Anything with "FACEBOOK", "META", "SOCIAL", or "AIA" → Paid Social.

    • If nothing matches the above, we simply join the raw list so the
      email never shows a blank line.
    """
    if isinstance(kpis.get("bcdf_tactics"), str) and "BCDF" not in kpis["bcdf_tactics"].upper():
        kpis["has_bcdf"] = False
        return kpis

    if not kpis.get("has_bcdf"):
        return kpis

    raw = kpis.get("bcdf_tactics", [])
    if isinstance(raw, str):
        # occasionally the LLM returns a stringified list
        raw = [s.strip(" \"'") for s in raw.strip("[]").split(",") if s.strip()]

    # ------------------------- broadened keyword nets ------------------------
    pmax_tokens   = ("GOOGLE", "PMAX", "SEARCH")   # BCDF 'Google Ads'
    social_tokens = ("FACEBOOK", "META", "SOCIAL", "AIA")

    pmax   = [t for t in raw if any(tok in t.upper() for tok in pmax_tokens)]
    social = [t for t in raw if any(tok in t.upper() for tok in social_tokens)]

    # Build the friendly list
    if pmax or social:
        tactics_list = ", ".join(
            filter(None, [
                "Performance Max" if pmax else "",
                "Paid Social"     if social else ""
            ])
        )
    else:
        # unknown headers—just echo whatever we got so the email isn't blank
        tactics_list = ", ".join(raw)

    kpis["bcdf_tactics_organized"] = {
        "pmax": bool(pmax),
        "paid_social": bool(social),
        "tactics_list": tactics_list
    }
    return kpis


def cleanup_placeholders(kpis: Dict[str, Any]) -> Dict[str, Any]:
    # Remove video keys if every metric is a placeholder/missing
    video_keys = ["dv_views", "dv_viewrate", "dv_cpc", "dv_cpm"]
    if not any(key in kpis and not _is_placeholder(kpis[key]) for key in video_keys):
        for key in video_keys:
            kpis.pop(key, None)

    # Remove BCDF conv / vdp if placeholders
    for key in ("bcdf_vdp", "bcdf_conv"):
        if _is_placeholder(kpis.get(key)):
            kpis.pop(key, None)

    return kpis


def validate_kpis(kpis: Dict[str, Any]) -> Dict[str, Any]:
    # strip commas in numeric strings
    for k, v in list(kpis.items()):
        if isinstance(v, str) and re.fullmatch(r"\d{1,3}(,\d{3})+", v):
            kpis[k] = v.replace(",", "")

    kpis = organize_bcdf_tactics(kpis)
    kpis = cleanup_placeholders(kpis)
    return kpis

# ---------------------------------------------------------------------------
#  PMAX / VLA EDGE‑CASE FIX (Palmer)
# ---------------------------------------------------------------------------

def fix_pmax_vla_inconsistency(kpis: Dict[str, Any]) -> Dict[str, Any]:
    has_pmax = any(k.startswith("pmax_") and not k.startswith("pmax_vla_") for k in kpis)
    has_vla  = any(k.startswith("pmax_vla_") for k in kpis)
    if not (has_pmax and has_vla):
        return kpis

    pmax_total = _to_int(kpis.get("pmax_impr"))
    vla_total  = _to_int(kpis.get("pmax_vla_impr"))
    if pmax_total is None or vla_total is None:
        return kpis

    if 0 < vla_total < pmax_total * 0.25 and "palmer" in kpis.get("store_name", "").lower():
        for metric in ("impr", "clicks", "cpc", "conv", "cost_conv"):
            kpis[f"pmax_vla_{metric}"] = kpis.get(f"pmax_{metric}")
            placeholder = (
                PLACEHOLDER_COST  if metric == "cpc"   else
                PLACEHOLDER_CLICK if metric == "clicks" else
                PLACEHOLDER_CONV  if metric == "conv"   else
                PLACEHOLDER_NUM
            )
            kpis[f"pmax_{metric}"] = placeholder
    return kpis

# ---------------------------------------------------------------------------
#  AI CLIENT WRAPPERS
# ---------------------------------------------------------------------------


def _query_claude(api_key: str, document: str) -> Dict[str, Any]:
    """
    Calls Anthropic Claude 3 using the correct message schema.
    """
    client = anthropic.Anthropic(api_key=api_key)

    resp = client.messages.create(
        model="claude-3-opus-20240229",
        max_tokens=4000,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": [  # ← must be a list of dicts
                    { "type": "text", "text": document }
                ]
            }
        ]
    )

    # Claude 3 returns content as a list as well
    reply = resp.content[0].text if isinstance(resp.content, list) else resp.content
    return _json_from_text(reply)



def _query_openai(api_key: str, document: str) -> Dict[str, Any]:
    client = openai.OpenAI(api_key=api_key)
    resp = client.chat.completions.create(
        model="gpt-4-turbo",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": document}
        ],
        response_format={"type": "json_object"}
    )
    return json.loads(resp.choices[0].message.content)


def _query_deepseek(api_key: str, document: str) -> Dict[str, Any]:
    """
    Call DeepSeek Chat API (OpenAI‑compatible) and return the JSON KPI object.
    Removes unsupported 'response_format' and handles long docs gracefully.
    """

    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY is missing or empty")

    url = "https://api.deepseek.com/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    # DeepSeek has a ~60 k token limit; hard‑truncate huge decks.
    if len(document) > 50_000:
        document = document[:50_000] + "\n[Truncated]"

    payload = {
        "model": "deepseek-chat",
        "messages": [
            { "role": "system", "content": SYSTEM_PROMPT },
            { "role": "user",   "content": document      }
        ],
        # No 'response_format' key – DeepSeek doesn't support it
        "temperature": 0.2,
    }

    for attempt in range(3):
        resp = requests.post(url, headers=headers, json=payload, timeout=60)
        if resp.status_code == 200:
            txt = resp.json()["choices"][0]["message"]["content"]
            return _json_from_text(txt)
        else:
            # Log first failure for easier debugging
            if attempt == 0:
                print("DeepSeek error:", resp.status_code, resp.text[:300])
        time.sleep((attempt + 1) * 2)   # back‑off 2s, 4s

    raise RuntimeError(f"DeepSeek API failed (last status {resp.status_code})")


# ---------------------------------------------------------------------------
#  PUBLIC ENTRY
# ---------------------------------------------------------------------------

def extract_kpis_with_ai(api_key: str, document_text: str, ai_provider: str = "deepseek") -> Dict[str, Any]:
    if ai_provider == "claude":
        kpis = _query_claude(api_key, document_text)
    elif ai_provider == "openai":
        kpis = _query_openai(api_key, document_text)
    elif ai_provider == "deepseek":
        kpis = _query_deepseek(api_key, document_text)
    else:
        raise ValueError(f"Unsupported AI provider: {ai_provider}")

    kpis = validate_kpis(kpis)
    kpis = fix_pmax_vla_inconsistency(kpis)
    return kpis
