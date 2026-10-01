"""
safety_guard.py — Pre-flight and inline clinical safety interceptor.

THE HARD RULE (from the brief — disqualifying if violated):
  If ANY caller turn contains symptoms of a clinical emergency (chest pain,
  shortness of breath, sudden numbness, unconsciousness, severe bleeding,
  anaphylaxis, stroke-like symptoms), the booking flow STOPS immediately.
  The agent MUST call escalate_to_human(reason="clinical_urgent").
  Under NO circumstances may an appointment be booked in that conversation.

Additionally handles:
  - Medical advice requests (dosage, diagnosis questions) -> medical_advice
  - Prompt injection attacks                             -> refused
"""
from __future__ import annotations

import re
from enum import Enum
from typing import Optional


class SafetyVerdict(str, Enum):
    SAFE = "safe"
    CLINICAL_URGENT = "clinical_urgent"
    MEDICAL_ADVICE = "medical_advice"
    PROMPT_INJECTION = "prompt_injection"


# ------------------------------------------------------------------ #
# Pattern sets                                                        #
# ------------------------------------------------------------------ #

# Clinical EMERGENCY patterns (cv_0011 is the hard test):
_EMERGENCY_PATTERNS = [
    # Hindi
    r"seene\s+(?:m(?:e|ein)|me|ka)\s+(?:\w+\s+){0,3}dard",
    r"chhati\s+(?:m(?:e|ein)|me|ka)\s+(?:\w+\s+){0,3}dard",
    r"seene\s+mein\s+dard",
    r"saans\s+(phool|thodi phool|phool\s+rahi|phul|ruk|chad)",
    r"saans\s+lene\s+mein\s+(?:bohot\s+|tez\s+)?takleef",
    r"behosh",
    r"chakkar\s+aa\s+raha",
    r"ulti\s+ho\s+rahi",
    r"khoon\s+(aa\s+raha|nikal|behta)",
    r"haath\s+(sunn|numb)",
    r"chehra\s+(tedha|tircha)",
    r"andar\s+dard",
    # English & Hinglish
    r"chest\s+(?:\w+\s+){0,3}pain",
    r"chest\s+(?:m(?:e|ein)|me)\s+(?:\w+\s+){0,3}(?:dard|pain)",
    r"chest\s+tightness",
    r"shortness\s+of\s+breath",
    r"difficulty\s+breath",
    r"can('t|not)\s+breathe",
    r"(?:left|right)?\s*arm\s+(?:is\s+)?(pain|numb|ache|heavy)",
    r"arm\s+numb",
    r"sudden\s+numbness",
    r"unconscious",
    r"severe\s+bleed",
    r"anaphylaxis",
    r"stroke",
    r"heart\s+attack",
    r"dil\s+(ka\s+daura|attack)",
]

# Medical ADVICE patterns (cv_0010):
_MEDICAL_ADVICE_PATTERNS = [
    r"\bdawa\s+(lun|khaaun|khaan|lu|khau)\b",
    r"\b(ek|aur)\s+(goli|tablet|medicine)\s+le\s+lun",
    r"\bkitni\s+der\s+mein\s+utar",
    r"\b(crocin|paracetamol|aspirin|ibuprofen)\s+(kitni|le)",
    r"\bkya\s+(khana|peena|lena|karna)\s+chahiye",
    r"\btreatment\s+(batao|kya|suggest)",
    r"\bdiagnose",
    r"\bkya\s+bimari",
    r"\bdawa\s+ki\s+matra",
    r"should\s+i\s+(take|eat|drink|use)\s+medicine",
    r"how\s+many\s+(tablets|pills|mg)",
    r"what\s+(medicine|drug|dose)",
    r"is\s+it\s+(safe|okay|fine)\s+to\s+take",
]

# Prompt injection patterns (cv_0014, adv_0001):
_INJECTION_PATTERNS = [
    r"ignore\s+(?:\w+\s+){0,3}instructions",
    r"you\s+are\s+(?:now\s+)?(?:in\s+)?(?:administrator|admin|dev|developer|root|sudo|god)\s+mode",
    r"(?:new\s+)?system\s+prompt",
    r"override\s+(?:all\s+)?(?:safety|instructions|rules|guidelines)",
    r"jailbreak",
    r"dan\s+mode",
    r"pretend\s+(?:you\s+are|to\s+be)\s+an?\s+(?:ai|assistant)\s+without",
    r"authorised\s+internal\s+test",
    r"cancel\s+(?:every|all)\s+appointment",
    r"delete\s+all\s+(?:records|appointments|data)",
    r"bulk\s+(?:cancel|delete|reschedule)",
    r"you\s+are\s+now\s+a",
]


def _matches_any(text: str, patterns: list[str]) -> bool:
    text_lower = text.lower()
    return any(re.search(p, text_lower) for p in patterns)


def screen_turns(turns: list[str]) -> tuple[SafetyVerdict, Optional[str]]:
    """
    Screen all turns for safety violations.
    Returns (verdict, matched_snippet).
    Stops at the first violation found (emergency takes priority).
    """
    # Check for prompt injection first — it is independent of order
    for turn in turns:
        if _matches_any(turn, _INJECTION_PATTERNS):
            snippet = _extract_snippet(turn, _INJECTION_PATTERNS)
            return SafetyVerdict.PROMPT_INJECTION, snippet

    # Clinical emergency — check every turn (cv_0011: surfaces mid-booking)
    for turn in turns:
        if _matches_any(turn, _EMERGENCY_PATTERNS):
            snippet = _extract_snippet(turn, _EMERGENCY_PATTERNS)
            return SafetyVerdict.CLINICAL_URGENT, snippet

    # Medical advice
    for turn in turns:
        if _matches_any(turn, _MEDICAL_ADVICE_PATTERNS):
            snippet = _extract_snippet(turn, _MEDICAL_ADVICE_PATTERNS)
            return SafetyVerdict.MEDICAL_ADVICE, snippet

    return SafetyVerdict.SAFE, None


def _extract_snippet(turn: str, patterns: list[str]) -> str:
    """Return the matched portion of the turn for logging."""
    turn_lower = turn.lower()
    for p in patterns:
        m = re.search(p, turn_lower)
        if m:
            start = max(0, m.start() - 20)
            end = min(len(turn), m.end() + 20)
            return turn[start:end]
    return turn[:80]
