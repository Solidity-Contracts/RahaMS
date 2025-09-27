# companion.py
from __future__ import annotations
from typing import List, Optional, Literal, Dict, Any
from pydantic import BaseModel, Field
import re

# ===== Shapes =====
class CompanionOut(BaseModel):
    language: Literal["ar", "en"]
    role: Literal["companion"] = "companion"
    style: Literal["chat", "plan", "checklist"]
    message: str
    bullets: Optional[List[str]] = None  # max 3 when present
    next_step: Optional[str] = None
    safety_note: Optional[str] = None

# ===== Utils =====
def norm_lang(lang: str) -> str:
    """
    Normalize language input.
    Any code starting with 'ar' (e.g. 'ar', 'ar-AE', 'Arabic') → 'ar'
    Everything else → 'en'
    """
    if not lang:
        return "en"
    lang = str(lang).strip().lower()
    return "ar" if lang.startswith("ar") or "arabic" in lang else "en"

def clamp_bullets(items: List[str], k: int = 3) -> List[str]:
    return [s.strip() for s in items if s.strip()][:k]

# ===== Prompts =====
SYSTEM_BASE = (
    "You are Raha MS AI Companion. Be warm, encouraging, and concise. "
    "Default to 2–3 short sentences. Only use bullets when asked for tips/plan or when intent is 'plan'. "
    "Keep max 3 bullets. Avoid long disclaimers. "
    "Provide culturally aware guidance for GCC users (fasting, prayer times, AC/home environment, cooling garments, pacing). "
    "Strictly educational — not medical care. No diagnosis. Encourage clinician follow-up for concerning symptoms."
)
SYSTEM_AR = "Respond only in Arabic. Use Gulf-friendly phrasing when relevant."
SYSTEM_EN = "Respond only in English."

FEW_SHOTS = [
    {"role": "user", "content": "I'm feeling tired after being outside—should I worry?"},
    {"role": "assistant", "content": (
        "It sounds like heat might have nudged your MS symptoms a bit. "
        "Rest in a cool room and sip water. If the tiredness doesn't settle after cooling and sleep, let your clinician know."
    )},
    {"role": "user", "content": "Give me a short plan for going to Friday prayer in the heat."},
    {"role": "assistant", "content": (
        "• Go during the coolest slot you can and pre-cool at home.\n"
        "• Wear breathable layers or a cooling scarf/vest.\n"
        "• Park close, pace your steps, and hydrate before/after (if not fasting)."
    )},
]

INTENT_PATTERNS = {
    "plan": re.compile(r"\b(plan|tips|steps|how to|checklist|ماذا أفعل|خطة|نصائح)\b", re.I),
}
RED_FLAG_PATTERNS = [
    re.compile(r"(chest pain|trouble breathing|fainting|loss of vision|new weakness|can't walk|suicid|harm)", re.I),
    re.compile(r"(ألم صدر|صعوبة التنفس|إغماء|فقدان الرؤية|ضعف جديد|لا أستطيع المشي|انتحار|أؤذي نفسي)", re.I),
]

def detect_intent(text: str) -> Literal["chat", "plan"]:
    return "plan" if any(p.search(text or "") for p in INTENT_PATTERNS.values()) else "chat"

def detect_red_flags(text: str) -> bool:
    return any(p.search(text or "") for p in RED_FLAG_PATTERNS)

# ===== Core =====
class RahaCompanion:
    def __init__(self, openai_client, default_lang: str = "en",
                 model: str = "gpt-4o-mini", temperature: float = 0.4, max_tokens: int = 350):
        self.client = openai_client
        self.default_lang = norm_lang(default_lang)
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

    def _system(self, lang: str) -> str:
        return f"{SYSTEM_BASE} {(SYSTEM_AR if lang=='ar' else SYSTEM_EN)}"

    def _messages(self, lang: str, user_text: str, intent: str) -> List[Dict[str, Any]]:
        style_hint = "Write a brief chat-style reply (2–3 sentences)." if intent == "chat" \
                     else "Write a tiny action plan as 2–3 concise bullets."
        return [
            {"role": "system", "content": self._system(lang)},
            {"role": "system", "content": style_hint},
            *FEW_SHOTS,
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

    def _post(self, text: str, intent: str, lang: str, red_flags: bool) -> CompanionOut:
        msg = text.strip()
        lines = [l.strip("•-* \t") for l in msg.splitlines() if l.strip()]
        bullets = None

        # prefer bullets if intent=plan OR reply looks like short lines
        if intent == "plan" or (len(lines) >= 2 and sum(len(l) for l in lines[:3]) < 300):
            bullets = clamp_bullets(lines, 3)
            if bullets and len(lines) > len(bullets):
                msg = lines[0]
            else:
                msg = "ها هي خطة قصيرة:" if lang == "ar" else "Here’s a short plan:"
        else:
            if len(msg) > 450:
                msg = msg[:447] + "…"

        safety_note = None
        if red_flags:
            safety_note = ("إذا كانت لديك أعراض خطيرة الآن (مثل ألم صدر أو صعوبة تنفس أو ضعف جديد شديد)، "
                           "اتصل بالطوارئ فورًا أو راجع أقرب قسم طوارئ.") if lang == "ar" else \
                          ("If you have severe or new alarming symptoms (chest pain, trouble breathing, sudden weakness), "
                           "call emergency services or go to the nearest ER now.")

        return CompanionOut(
            language=lang,
            style=("plan" if bullets else "chat"),
            message=msg,
            bullets=bullets,
            next_step=None if bullets else ("هل تود خطة مختصرة؟" if lang == "ar" else "Would you like a short plan?"),
            safety_note=safety_note,
        )

    def respond(self, user_text: str, lang: Optional[str] = None) -> CompanionOut:
        lang = norm_lang(lang or self.default_lang)
        intent = detect_intent(user_text)
        red = detect_red_flags(user_text)
        try:
            resp = self._call_llm(self._messages(lang, user_text, intent))
            content = resp.choices[0].message.content or ""
        except Exception:
            content = ("يبدو أن هناك مشكلة تقنية. جرّب مرة أخرى لاحقًا. في هذه الأثناء: اجلس في مكان مبرّد واشرب ماءً، وارتَح قليلاً."
                       if lang == "ar"
                       else "Looks like a technical hiccup. Try again shortly. Meanwhile: cool down, hydrate, and take a short rest.")
        return self._post(content, intent, lang, red)
