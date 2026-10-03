import pandas as pd

from pipeline import match_names as mn


def test_read_lines_parses_minutes_over_60(tmp_path):
    f = tmp_path / "t.txt"
    f.write_text("[444:31] Hello there\n[03:30] A very good morning\nnoise line\n", encoding="utf-8")
    assert mn.read_lines(f) == [(26671, "Hello there"), (210, "A very good morning")]


def test_words_of_drops_short_and_stop_words():
    assert mn.words_of("Mr. A Rahul Kumar") == ["RAHUL", "KUMAR"]


def test_make_chunks_skips_speech_before_name_zone():
    lines = [(100, "Welcome everyone"), (mn.ZONE_START_MIN * 60 + 5, "Rahul Sharma, Priya Verma")]
    chunks = mn.make_chunks(lines)
    assert [c[1] for c in chunks] == ["Rahul Sharma", "Priya Verma"]


def test_fuzzy_match_finds_misspelled_names(tmp_path, monkeypatch):
    csv = tmp_path / "attendees.csv"
    pd.DataFrame({"Name": ["RAHUL KUMAR SHARMA", "PRIYA VERMA"]}).to_csv(csv, index=False)
    monkeypatch.setattr(mn, "ATTENDEES_CSV", csv)
    t0 = mn.ZONE_START_MIN * 60
    lines = [(t0 + 10, "Rahul Sharma"), (t0 + 20, "Priya Varma")]
    res = mn.match(lines, write=False)
    assert res["RAHUL KUMAR SHARMA"][1] == t0 + 10
    assert res["PRIYA VERMA"][1] == t0 + 20


def test_two_common_surnames_do_not_identify_a_student(tmp_path, monkeypatch):
    csv = tmp_path / "attendees.csv"
    names = ["SHASHANK KUMAR SINGH"] + [f"PERSON{i} KUMAR SINGH" for i in range(30)]
    pd.DataFrame({"Name": names}).to_csv(csv, index=False)
    monkeypatch.setattr(mn, "ATTENDEES_CSV", csv)
    t0 = mn.ZONE_START_MIN * 60
    res = mn.match([(t0 + 10, "Vikas Kumar Singh")])
    assert "SHASHANK KUMAR SINGH" not in res
