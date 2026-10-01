"""終局三振的事件 count 可能延遲，必須以明確證據核對。"""

from copy import deepcopy
import unittest

from abs_challenge.phase1 import call_only_limitation
from abs_challenge.state_value import GameState


class TerminalOutEvidenceTests(unittest.TestCase):
    def test_stale_pitch_outs_with_explicit_batter_out(self):
        state = GameState(8, "bottom", 1, 0, 0, 2, 0, 3)
        row = {"at_bat_index": 0, "play_event_index": 0, "pitch_number": 1,
               "abs_call": "strike", "batter_id": 100}
        play = {"atBatIndex": 0, "count": {"outs": 2},
                "result": {"eventType": "strikeout"},
                "playEvents": [{"index": 0, "pitchNumber": 1, "isPitch": True,
                                "details": {"description": "Called Strike", "isOut": True},
                                "count": {"outs": 1}}],
                "runners": [{"details": {"playIndex": 0, "eventType": "strikeout", "runner": {"id": 100}},
                             "movement": {"isOut": True, "outNumber": 2}}]}
        feed = {"liveData": {"plays": {"allPlays": [play]}}}
        self.assertIsNone(call_only_limitation(feed, row, state))
        for missing in ("runners", "count"):
            altered = deepcopy(feed)
            altered["liveData"]["plays"]["allPlays"][0].pop(missing)
            with self.subTest(missing=missing):
                self.assertIsNotNone(call_only_limitation(altered, row, state))
        extra_runner = deepcopy(feed)
        extra_runner["liveData"]["plays"]["allPlays"][0]["runners"].append({
            "details": {"playIndex": 0, "eventType": "stolen_base_2b", "runner": {"id": 200}},
            "movement": {"start": "1B", "end": "2B", "isOut": False}})
        self.assertIsNotNone(call_only_limitation(extra_runner, row, state))
        play["runners"][0]["movement"]["outNumber"] = 3
        self.assertIsNotNone(call_only_limitation(feed, row, state))
