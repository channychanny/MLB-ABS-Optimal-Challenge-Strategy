"""完整九局／延長賽的合成來源，只用於可攜式工程測試。"""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path

from abs_challenge.historical_sources import BUNDLE_VERSION
from abs_challenge.provenance import build_download_manifest
from abs_challenge.savant import build_called_pitches_csv_url


def contract():
    path = Path(__file__).resolve().parents[1] / "config" / "phase2_dataset.json"
    return json.loads(path.read_text(encoding="utf-8"))


def game_fixture(season=2019, game_pk=501, away_runs=1, *, extra=False, walkoff=False):
    game_date = f"{season}-06-01"
    scores = {"home": 0, "away": 0}
    plays, rows, innings = [], [], []
    for inning in range(1, 11 if extra else 10):
        line = {"num": inning, "home": {"runs": 0}, "away": {"runs": 0}}
        for half in ("top", "bottom"):
            batting = "away" if half == "top" else "home"
            runs = away_runs if inning == 1 and half == "top" and not extra and not walkoff else 0
            if extra and inning == 10 and half == "top":
                runs = 1
            is_walkoff = walkoff and inning == 9 and half == "bottom"
            if is_walkoff:
                runs = 1
            outs = 0
            for number in range(runs + (0 if is_walkoff else 3)):
                homer = number < runs
                index = len(plays)
                events = []
                for pitch in (1, 2):
                    row = {"game_pk": str(game_pk), "at_bat_number": str(index + 1),
                        "pitch_number": str(pitch), "game_date": game_date, "game_type": "R",
                        "inning": str(inning), "inning_topbot": "Top" if half == "top" else "Bot",
                        "balls": str(pitch - 1), "strikes": "0", "outs_when_up": str(outs),
                        "on_1b": "", "on_2b": "", "on_3b": "", "home_score": str(scores["home"]),
                        "away_score": str(scores["away"]), "description": "ball" if pitch == 1 else "hit_into_play"}
                    rows.append(row)
                    events.append({"isPitch": True, "pitchNumber": pitch, "index": pitch - 1})
                if homer:
                    scores[batting] += 1
                    line[batting]["runs"] += 1
                else:
                    outs += 1
                plays.append({"about": {"atBatIndex": index, "inning": inning, "halfInning": half,
                    "isComplete": True}, "count": {"outs": outs},
                    "result": {"homeScore": scores["home"], "awayScore": scores["away"]},
                    "playEvents": events})
        innings.append(line)
    feed = {"gamePk": game_pk, "gameData": {"status": {"abstractGameState": "Final"},
        "game": {"type": "R", "season": str(season)}, "datetime": {"officialDate": game_date},
        "teams": {side: {"sport": {"id": 1}} for side in ("home", "away")}},
        "liveData": {"boxscore": {"teams": {side: {"teamStats": {"pitching": {
            "numberOfPitches": sum(len(p["playEvents"]) for p in plays
                if p["about"]["halfInning"] == ("top" if side == "home" else "bottom"))}}}
            for side in ("home", "away")}},
            "linescore": {"scheduledInnings": 9, "currentInning": 10 if extra else 9,
            "teams": {side: {"runs": scores[side]} for side in ("home", "away")}, "innings": innings},
            "plays": {"allPlays": plays}}}
    return feed, rows


def bundle_fixture(feed, rows):
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    sources = {}
    for name, text, url, kind, count in (
        ("feed", json.dumps(feed), f"https://statsapi.mlb.com/api/v1.1/game/{feed['gamePk']}/feed/live",
         "mlb_stats_api_feed_json", 1),
        ("statcast", buffer.getvalue(), build_called_pitches_csv_url(feed["gameData"]["datetime"]["officialDate"], "mlb"),
         "baseball_savant_pitch_csv", len(rows)),
    ):
        sources[name] = {"text": text, "manifest": build_download_manifest(source_type=kind,
            source_url=url, content=text, row_count=count, retrieved_at_utc="2026-09-15T00:00:00Z")}
    return {"schema_version": BUNDLE_VERSION, **sources}
