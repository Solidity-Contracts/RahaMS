# companion.py
from __future__ import annotations
from typing import List, Optional, Literal, Dict, Any
from pydantic import BaseModel
import re

# ===== Shapes =====
class CompanionOut(BaseModel):
    language: Literal["ar", "en"]
    role: Literal["companion"] = "companion"
    style: Literal["chat", "plan", "checklist"]
    message: str
    bullets: Optional[List[str]] = None
    next_step: Optional[str] = None
    safety_note: Optional[str] = None

# ===== Utils =====
_ARABIC_RE = re.compile(r"[\u0600-\u06FF]")

def detect_arabic_in_text(text: str) -> bool:
    return bool(_ARABIC_RE.search(text or ""))

def clamp_bullets(items: List[str], k: int = 3) -> List[str]:
    return [s.strip() for s in items if s.strip()][:k]

# ===== Prompts (strict, language-specific) =====
SYSTEM_AR = (
    "You are Raha MS AI Companion. Be warm, encouraging, and concise. "
    "Default to 2–3 short sentences; only use bullets when the user asks for tips/plan (max 3). "
    "GCC context (fasting, prayer times, AC/home, cooling garments, pacing). "
    "Educational only, not medical care. "
    "**Respond ONLY in Arabic. Never use English.**"
)

SYSTEM_EN = (
    "You are Raha MS AI Companion. Be warm, encouraging, and concise. "
    "Default to 2–3 short sentences; only use bullets when the user asks for tips/plan (max 3). "
    "GCC context (fasting, prayer times, AC/home, cooling garments, pacing). "
    "Educational only, not medical care. "
    "**Respond ONLY in English. Never use Arabic.**"
)

FEW_SHOTS_AR = [
    {"role": "user", "content": "أشعر بإرهاق بعد المشي وقت الظهر. هل هذا طبيعي؟"},
    {"role": "assistant", "content": "الحر قد يرفع الأعراض مؤقتًا. اجلس في مكان مبرّد واشرب ماءً، ثم ارتَح قليلًا."},
]

FEW_SHOTS_EN = [
    {"role": "user", "content": "I'm feeling tired after being outside—should I worry?"},
    {"role": "assistant", "content": "Heat may have nudged your MS symptoms. Rest in a cool room and sip water."},
]

_INTENT_PLAN = re.compile(r"\b(plan|tips|steps|how to|checklist)\b|ماذا أفعل|خطة|نصائح", re.I)
_RED_FLAGS = [
    re.compile(r"(chest pain|trouble breathing|fainting|loss of vision|new weakness|can't walk|suicid|harm)", re.I),
    re.compile(r"(ألم صدر|صعوبة التنفس|إغماء|فقدان الرؤية|ضعف جديد|لا أستطيع المشي|انتحار|أؤذي نفسي)", re.I),
]

def detect_intent(text: str) -> Literal["chat", "plan"]:
    return "plan" if _INTENT_PLAN.search(text or "") else "chat"

def detect_red_flags(text: str) -> bool:
    return any(p.search(text or "") for p in _RED_FLAGS)

# ===== Core =====
class RahaCompanion:
    def __init__(self, openai_client, model: str = "gpt-4o-mini", temperature: float = 0.4, max_tokens: int = 350):
        self.client = openai_client
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

    def _system(self, lang: str) -> str:
        return SYSTEM_AR if lang == "ar" else SYSTEM_EN

    def _messages(self, lang: str, user_text: str, intent: str) -> List[Dict[str, Any]]:
        style_hint = "Write a brief chat-style reply (2–3 sentences)." if intent == "chat" \
                     else "Write a tiny action plan as 2–3 concise bullets."
        shots = FEW_SHOTS_AR if lang == "ar" else FEW_SHOTS_EN
        return [
            {"role": "system", "content": self._system(lang)},
            {"role": "system", "content": style_hint},
            *shots,
            {"role": "user", "content": user_text},
        ]

    def _call_llm(self, messages):
        return self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            presence_penalty=0.0,
            frequency_penalty=0.2,
        )

    def _post(self, text: str, intent: str, lang: str, red: bool) -> CompanionOut:
        msg = text.strip()
        lines = [l.strip("•-* \t") for l in msg.splitlines() if l.strip()]
        bullets = None
        if intent == "plan" or (len(lines) >= 2 and sum(len(l) for l in lines[:3]) < 300):
            bullets = clamp_bullets(lines, 3)
            if bullets and len(lines) > len(bullets):
                msg = lines[0]
            else:
                msg = "ها هي خطة قصيرة:" if lang == "ar" else "Here is a short plan:"
        else:
            if len(msg) > 450:
                msg = msg[:447] + "…"

        safety_note = None
        if red:
            safety_note = ("إذا كانت لديك أعراض خطيرة الآن (مثل ألم صدر أو صعوبة تنفس أو ضعف جديد شديد)، اتصل بالطوارئ فورًا."
                           if lang == "ar" else
                           "If you have severe or new alarming symptoms (chest pain, trouble breathing, sudden weakness), call emergency services now.")

        return CompanionOut(
            language=lang,
            style=("plan" if bullets else "chat"),
            message=msg,
            bullets=bullets,
            next_step=None if bullets else ("هل تود خطة مختصرة؟" if lang == "ar" else "Would you like a short plan?"),
            safety_note=safety_note,
        )

    def respond(self, user_text: str, lang: Optional[str] = None) -> CompanionOut:
        # Language = based purely on user text
        lang_final = "ar" if detect_arabic_in_text(user_text) else "en"
        intent = detect_intent(user_text)
        red = detect_red_flags(user_text)
        try:
            resp = self._call_llm(self._messages(lang_final, user_text, intent))
            content = resp.choices[0].message.content or ""
        except Exception:
            content = ("يبدو أن هناك مشكلة تقنية. حاول لاحقًا."
                       if lang_final == "ar" else
                       "Sorry—something went wrong. Please try again later.")
        return self._post(content, intent, lang_final, red)
