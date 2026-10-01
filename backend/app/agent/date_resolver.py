"""
date_resolver.py — Deterministic Hinglish / relative date & time resolver.

CRITICAL RULE: All resolution is done against a `today` string passed in the
request. datetime.now() is NEVER called here.

Handles:
  Relative days: aaj, kal, parso, tarson
  Day names (Hindi): somwar, mangalwar, budhwar, guruwar/veervar,
                     shukrawar, shanivaar, ravivar
  Date references: "3 tareekh", "8 taarikh", "8 ko"
  Clock times: "9 baje", "subah 9", "shaam 5 baje", "gyarah baje",
               "sawa 9" (+15), "sadhe 9" (+30), "paune 10" (-15),
               "half past 9" (09:30)
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Optional


# ------------------------------------------------------------------ #
# Day-name mapping                                                   #
# ------------------------------------------------------------------ #

_DAY_NAMES: dict[str, int] = {
    "somwar": 0, "monday": 0,
    "mangalwar": 1, "tuesday": 1,
    "budhwar": 2, "wednesday": 2,
    "guruwar": 3, "veervar": 3, "thursday": 3,
    "shukrawar": 4, "shukravar": 4, "friday": 4,
    "shanivaar": 5, "shanivar": 5, "saturday": 5,
    "ravivar": 6, "sunday": 6,
}

# ------------------------------------------------------------------ #
# Time helpers                                                        #
# ------------------------------------------------------------------ #

def _parse_clock_time(text: str) -> Optional[str]:
    """
    Extract HH:MM from a string fragment.
    Returns None if no time is found.

    Patterns handled:
      "9 baje"           -> 09:00 (if no am/pm/session, treat as-is but >=6 -> HH)
      "subah 9 baje"     -> 09:00
      "dopahar 12 baje"  -> 12:00
      "shaam 5 baje"     -> 17:00
      "raat 9 baje"      -> 21:00
      "gyarah baje"      -> 11:00  (gyarah = 11)
      "9:30"             -> 09:30
      "9.30"             -> 09:30
      "sawa 9"           -> 09:15  (sawa = +15 min)
      "sadhe 9"          -> 09:30  (sadhe / saadhe = +30 min)
      "paune 10"         -> 09:45  (paune = -15 min)
    """
    text = text.lower().strip()

    # Hindi number words for hours
    _HINDI_NUMS: dict[str, int] = {
        "ek": 1, "do": 2, "teen": 3, "char": 4,
        "paanch": 5, "cheh": 6, "saat": 7, "aath": 8,
        "nau": 9, "das": 10, "gyarah": 11, "barah": 12,
    }

    # Session modifiers
    is_morning = bool(re.search(r"\b(subah|morning|am)\b", text))
    is_afternoon = bool(re.search(r"\b(dopahar|afternoon)\b", text))
    is_evening = bool(re.search(r"\b(shaam|evening)\b", text))
    is_night = bool(re.search(r"\b(raat|night)\b", text))

    minute_offset = 0  # From quarter-hour modifiers
    prefix_modifier = None  # sawa / sadhe / paune
    if re.search(r"\bsawa\b", text):
        prefix_modifier = "sawa"
    elif re.search(r"\b(sadhe|saadhe)\b", text):
        prefix_modifier = "sadhe"
    elif re.search(r"\bpaune\b", text):
        prefix_modifier = "paune"

    hour: Optional[int] = None
    minute: int = 0

    # Try HH:MM or HH.MM pattern first
    m = re.search(r"\b(\d{1,2})[:\.](\d{2})\b", text)
    if m:
        hour = int(m.group(1))
        minute = int(m.group(2))
    else:
        # Try Hindi number words
        for word, val in _HINDI_NUMS.items():
            if re.search(rf"\b{word}\b", text):
                hour = val
                break
        # Try bare digit hour
        if hour is None:
            m2 = re.search(r"\b(\d{1,2})\s*baje\b", text)
            if m2:
                hour = int(m2.group(1))
            else:
                m3 = re.search(r"\b(\d{1,2})\b", text)
                if m3:
                    hour = int(m3.group(1))

    if hour is None:
        return None

    # Apply quarter-hour prefix
    if prefix_modifier == "sawa":
        minute = 15
    elif prefix_modifier == "sadhe":
        minute = 30
    elif prefix_modifier == "paune":
        # paune 10 = 9:45
        hour = hour - 1
        minute = 45

    # Apply session offset (24-hour)
    if is_night and hour < 12:
        hour += 12
    elif is_evening and hour < 12:
        hour += 12
    elif is_afternoon and hour < 12:
        hour += 12 if hour != 12 else 0
    elif is_morning:
        if hour == 12:
            hour = 0
    else:
        # No session hint: treat 1–5 as PM (13–17) in a clinic context
        if 1 <= hour <= 5:
            hour += 12

    return f"{hour:02d}:{minute:02d}"


# ------------------------------------------------------------------ #
# Date resolver                                                       #
# ------------------------------------------------------------------ #

def resolve_date(text: str, today: str) -> Optional[str]:
    """
    Resolve a date reference in `text` relative to `today` (YYYY-MM-DD).
    Returns YYYY-MM-DD or None if no date detected.
    """
    today_dt = datetime.strptime(today, "%Y-%m-%d").date()
    text_lower = text.lower()

    # Explicit date number: "3 tareekh", "3 taarikh", "3 ko", "3rd"
    m = re.search(r"\b(\d{1,2})\s*(tareekh|taarikh|tarikh|ko\b|th\b|rd\b|nd\b|st\b)", text_lower)
    if m:
        day_num = int(m.group(1))
        # Determine month (default current, roll over if day < today)
        candidate = today_dt.replace(day=day_num)
        if candidate < today_dt:
            # Next month
            if today_dt.month == 12:
                candidate = candidate.replace(year=today_dt.year + 1, month=1)
            else:
                candidate = candidate.replace(month=today_dt.month + 1)
        return candidate.strftime("%Y-%m-%d")

    # Relative keywords
    if re.search(r"\baaj\b", text_lower) or re.search(r"\btoday\b", text_lower):
        return today
    if re.search(r"\bkal\b", text_lower) or re.search(r"\btomorrow\b", text_lower):
        return (today_dt + timedelta(days=1)).strftime("%Y-%m-%d")
    if re.search(r"\bparso\b", text_lower) or re.search(r"\bday after tomorrow\b", text_lower):
        return (today_dt + timedelta(days=2)).strftime("%Y-%m-%d")
    if re.search(r"\btarson\b", text_lower):
        return (today_dt + timedelta(days=3)).strftime("%Y-%m-%d")

    # Day-name lookup: find next occurrence of that weekday
    for day_name, weekday in _DAY_NAMES.items():
        if re.search(rf"\b{day_name}\b", text_lower):
            days_ahead = (weekday - today_dt.weekday()) % 7
            if days_ahead == 0:
                days_ahead = 7  # "next Monday" means next week
            return (today_dt + timedelta(days=days_ahead)).strftime("%Y-%m-%d")

    return None


def resolve_time(text: str) -> Optional[str]:
    """
    Extract a clock time from `text`. Returns HH:MM (24-hour) or None.
    """
    return _parse_clock_time(text)


def resolve_date_from_turns(turns: list[str], today: str) -> Optional[str]:
    """
    Scan all turns (later turns override earlier) and return the last resolved date.
    This handles mid-turn corrections like "Mangalwar 6 tareekh... nahi nahi, budhwar 7 tareekh."
    """
    last_date: Optional[str] = None
    for turn in turns:
        # Handle mid-turn correction: split on "nahi nahi" and take the last segment
        segments = re.split(r"nahi[\s,]+nahi", turn, flags=re.IGNORECASE)
        for seg in segments:
            d = resolve_date(seg, today)
            if d:
                last_date = d
    return last_date


def resolve_time_from_turns(turns: list[str]) -> Optional[str]:
    """Scan turns and return the last resolved time."""
    last_time: Optional[str] = None
    for turn in turns:
        t = resolve_time(turn)
        if t:
            last_time = t
    return last_time
