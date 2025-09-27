"""
Raha MS AI Companion — reference implementation
------------------------------------------------
Single-file, framework-agnostic Python module you can drop into a FastAPI/Flask app.
Focus areas:
- Warm, human tone (Arabic or English) with minimal default verbosity
- GCC cultural context (fasting, prayer times, AC/home environment, heat, modesty considerations)
- Safety guardrails for general education only (not medical care), escalation rules
- Intent detection → style switching (chat vs plan vs checklists)
- Lightweight risk signals (heat, fatigue) you can wire to your telemetry
- Deterministic output shape for your UI (message + optional bullets + next_step)

Dependencies: openai>=1.40 (or compatible), pydantic
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional, Literal, Dict, Any
from pydantic import BaseModel, Field
import re
import datetime as dt

# ================== CONFIG ==================
OPENAI_MODEL = "gpt-4o-mini"
MAX_TOKENS = 350
DEFAULT_TEMPERATURE = 0.4

# ================== DATA SHAPES ==================
class CompanionOut(BaseModel):
    language: Literal["ar", "en"]
    role: Literal["companion"] = "companion"
    style: Literal["chat", "plan", "checklist"]
    message: str = Field(..., description="Primary conversational text")
    bullets: Optional[List[str]] = Field(None, description="Max 3 concise bullets when plan/checklist")
    next_step: Optional[str] = Field(None, description="One tiny suggestion or clarifying question")
    safety_note: Optional[str] = None

# ================== UTILITIES ==================
AR_ALIASES = {"ar", "arabic", "ar-sa", "ar-ae", "ar_ae", "ar_ksa", "ar-kw", "ar-bh", "ar-qa", "ar-om"}


def norm_lang(lang: str) -> str:
    return "ar" if str(lang).strip().lower() in AR_ALIASES else "en"


def clamp_bullets(items: List[str], k: int = 3) -> List[str]:
    return [s.strip() for s in items if s.strip()][:k]


# ================== PROMPT TEMPLATES ==================
SYSTEM_BASE = (
    "You are Raha MS AI Companion. Be warm, encouraging, and concise. "
    "Default to 2–3 short sentences. Only use bullets when asked for tips/plan or when intent is 'plan'. "
    "Keep max 3 bullets. Avoid long disclaimers. "
    "Provide culturally aware guidance for GCC users (fasting, prayer times, AC/home environment, cooling garments, pacing). "
    "Strictly educational — not medical care. No diagnosis. Encourage clinician follow-up for concerning symptoms."
)

SYSTEM_AR = "Respond only in Arabic. Use Gulf-friendly phrasing when relevant."
SYSTEM_EN = "Respond only in English."

# Few-shot style anchors for the model
FEW_SHOTS = [
    {"role": "user", "content": "I'm feeling tired after being outside—should I worry?"},
    {"role": "assistant", "content": (
        "It sounds like heat might have nudged your MS symptoms a bit. "
        "Rest in a cool room and sip water. If the tiredness doesn't settle after cooling and sleep, let your clinician know."
    )},
    {"role": "user", "content": "Give me a short plan for going to Friday prayer in the heat."},
    {"role": "assistant", "content": (
        "• Go during the coolest slot you can and pre‑cool at home.\n"
        "• Wear breathable layers or a cooling scarf/vest.\n"
        "• Park close, pace your steps, and hydrate before/after (if not fasting)."
    )},
]

# ================== INTENT & SAFETY ==================
INTENT_PATTERNS = {
    "plan": re.compile(r"\b(plan|tips|steps|how to|checklist|ماذا أفعل|خطة|نصائح)\b", re.I),
}

RED_FLAG_PATTERNS = [
    re.compile(r"(chest pain|trouble breathing|fainting|loss of vision|new weakness|can't walk|suicid|harm)", re.I),
    re.compile(r"(ألم صدر|صعوبة التنفس|إغماء|فقدان الرؤية|ضعف جديد|لا أستطيع المشي|انتحار|أؤذي نفسي)", re.I),
]


def detect_intent(text: str) -> Literal["chat", "plan"]:
    for pat in INTENT_PATTERNS.values():
        if pat.search(text or ""):
            return "plan"
    return "chat"


def detect_red_flags(text: str) -> bool:
    return any(p.search(text or "") for p in RED_FLAG_PATTERNS)

# ================== OPENAI CLIENT ==================
try:
    from openai import OpenAI
    client = OpenAI()
except Exception:  # library not present in some environments
    client = None


# ================== CORE ENGINE ==================
class RahaCompanion:
    def __init__(self, default_lang: str = "en"):
        self.default_lang = norm_lang(default_lang)

    def build_system(self, lang: str) -> str:
        return f"{SYSTEM_BASE} {(SYSTEM_AR if lang=='ar' else SYSTEM_EN)}"

    def make_messages(self, lang: str, user_text: str, intent: str) -> List[Dict[str, Any]]:
        sys_msg = {"role": "system", "content": self.build_system(lang)}
        style_hint = (
            "Write a brief chat-style reply (2–3 sentences)."
            if intent == "chat" else
            "Write a tiny action plan as 2–3 concise bullets."
        )
        style_msg = {"role": "system", "content": style_hint}
        msgs = [sys_msg, style_msg] + FEW_SHOTS + [{"role": "user", "content": user_text}]
        return msgs

    def _call_llm(self, messages: List[Dict[str, Any]]):
        if not client:
            raise RuntimeError("OpenAI client not configured")
        return client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            temperature=DEFAULT_TEMPERATURE,
            max_tokens=MAX_TOKENS,
            presence_penalty=0.0,
            frequency_penalty=0.2,
        )

    def _postprocess(self, text: str, intent: str, lang: str, red_flags: bool) -> CompanionOut:
        # Split potential bullets if the model returned them inline
        bullets = None
        msg = text.strip()
        lines = [l.strip("•-* \t") for l in msg.splitlines() if l.strip()]
        # Heuristic: if multiple short lines, treat as bullets
        if intent == "plan" or (len(lines) >= 2 and sum(len(l) for l in lines[:3]) < 300):
            bullets = clamp_bullets(lines, 3)
            # Keep a short lead line if present
            if bullets and (len(lines) > len(bullets)):
                msg = lines[0]
            else:
                # If all bullets, set a soft intro
                msg = "ها هي خطة قصيرة:" if lang == "ar" else "Here’s a short plan:"
        else:
            # Make sure it's not overly long
            if len(msg) > 450:
                msg = (msg[:447] + "…")

        safety_note = None
        if red_flags:
            safety_note = (
                "إذا كانت لديك أعراض خطيرة الآن (مثل ألم صدر أو صعوبة تنفس أو ضعف جديد شديد)، اتصل بالطوارئ فورًا أو راجع أقرب قسم طوارئ." if lang=="ar"
                else "If you have severe or new alarming symptoms (chest pain, trouble breathing, sudden weakness), call emergency services or go to the nearest ER now."
            )
        return CompanionOut(
            language=lang,
            style=("plan" if bullets else "chat"),
            message=msg,
            bullets=bullets,
            next_step=("هل تود خطة مختصرة؟" if lang=="ar" else "Would you like a short plan?") if bullets is None else None,
            safety_note=safety_note,
        )

    def respond(self, user_text: str, lang: Optional[str] = None) -> CompanionOut:
        lang = norm_lang(lang or self.default_lang)
        intent = detect_intent(user_text)
        red = detect_red_flags(user_text)
        messages = self.make_messages(lang, user_text, intent)
        try:
            resp = self._call_llm(messages)
            content = resp.choices[0].message.content
        except Exception as e:
            # graceful fallback text
            fallback = (
                "يبدو أن هناك مشكلة تقنية. جرّب مرة أخرى لاحقًا. في هذه الأثناء: اجلس في مكان مبرّد واشرب ماءً، وارتَح قليلاً." if lang=="ar"
                else "Looks like a technical hiccup. Try again shortly. Meanwhile: cool down, hydrate, and take a short rest."
            )
            return self._postprocess(fallback, intent, lang, red)
        return self._postprocess(content, intent, lang, red)


# ================== OPTIONAL: SIMPLE HEAT RISK HELPER ==================
@dataclass
class HeatInputs:
    feels_like_c: float
    humidity: float  # 0–1
    user_baseline_c: float = 36.8


def simple_heat_risk(inp: HeatInputs) -> Literal["low", "moderate", "high"]:
    # Lightweight proxy; replace with your telemetry model
    delta = inp.feels_like_c - 32  # indoor AC contrast heuristic
    humidity_penalty = 4 if inp.humidity > 0.6 else (2 if inp.humidity > 0.4 else 0)
    total = delta + humidity_penalty
    if total >= 12:
        return "high"
    if total >= 6:
        return "moderate"
    return "low"


# ================== EXAMPLE USAGE ==================
if __name__ == "__main__":
    bot = RahaCompanion(default_lang="ar")
    example = "مرهق بعد المشي وقت الظهر. هل هذا خطير؟"
    out = bot.respond(example, lang="ar-AE")
    print(out.model_dump())
