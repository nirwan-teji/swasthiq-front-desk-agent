"""
test_date_resolver.py — Tests for the Hinglish / relative date-time resolver.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.agent.date_resolver import resolve_date, resolve_time, resolve_date_from_turns

TODAY = "2026-10-01"  # Thursday


def test_aaj():
    assert resolve_date("aaj ka appointment", TODAY) == "2026-10-01"


def test_kal():
    assert resolve_date("kal milna hai", TODAY) == "2026-10-02"


def test_parso():
    assert resolve_date("parso gyarah baje", TODAY) == "2026-10-03"


def test_tarson():
    assert resolve_date("tarson aana hai", TODAY) == "2026-10-04"


def test_shanivaar():
    # Today is Thu Oct 1; next Sat = Oct 3
    assert resolve_date("Shanivaar subah", TODAY) == "2026-10-03"


def test_somwar():
    # Next Monday after Thu Oct 1 = Oct 5
    assert resolve_date("somwar ko", TODAY) == "2026-10-05"


def test_budhwar():
    # Next Wednesday = Oct 7
    assert resolve_date("budhwar 7 tareekh", TODAY) == "2026-10-07"


def test_explicit_date():
    assert resolve_date("3 tareekh ko", TODAY) == "2026-10-03"


def test_explicit_date_8():
    assert resolve_date("8 tareekh subah", TODAY) == "2026-10-08"


def test_mid_turn_correction():
    """cv_0002: 'Mangalwar 6 tareekh... nahi nahi, budhwar kar dijiye, 7 tareekh'"""
    turns = [
        "Dr. Rao ke saath appointment karwana hai.",
        "Mangalwar 6 tareekh ko... nahi nahi, budhwar kar dijiye, 7 tareekh.",
        "Neha Bhatt, 9812200404. Subah ka time theek rahega.",
    ]
    result = resolve_date_from_turns(turns, TODAY)
    assert result == "2026-10-07"  # Must be Wed 7 Oct, not Tue 6 Oct


def test_time_subah_9():
    assert resolve_time("subah 9 baje") == "09:00"


def test_time_gyarah():
    assert resolve_time("gyarah baje") == "11:00"


def test_time_sawa_9():
    assert resolve_time("sawa nau baje") == "09:15"


def test_time_shaam_5():
    assert resolve_time("shaam 5 baje") == "17:00"


def test_time_hhmm():
    assert resolve_time("9:30 par aana") == "09:30"
