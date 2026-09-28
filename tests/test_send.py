import datetime
import sys
import unittest
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import send  # noqa: E402

CHICAGO = send.TIMEZONE
UTC = ZoneInfo("UTC")
CRON_TIMES_UTC = [(14, 7), (15, 7), (17, 7), (18, 7), (20, 37), (21, 37)]


def local(y, m, d, hh, mm):
    return datetime.datetime(y, m, d, hh, mm, tzinfo=CHICAGO)


class CurrentSlotTests(unittest.TestCase):
    def test_each_slot_inside_its_window(self):
        self.assertEqual(send.current_slot(local(2026, 9, 28, 9, 7)), "morning")
        self.assertEqual(send.current_slot(local(2026, 9, 28, 12, 7)), "midday")
        self.assertEqual(send.current_slot(local(2026, 9, 28, 15, 37)), "afternoon")

    def test_late_run_within_window_still_sends(self):
        self.assertEqual(send.current_slot(local(2026, 9, 28, 9, 50)), "morning")

    def test_outside_windows_does_not_send(self):
        for hh, mm in [(8, 59), (9, 55), (13, 7), (16, 37), (22, 0)]:
            self.assertIsNone(send.current_slot(local(2026, 9, 28, hh, mm)), f"{hh}:{mm}")

    def test_weekends_never_send(self):
        self.assertIsNone(send.current_slot(local(2026, 10, 3, 12, 7)))   # Saturday
        self.assertIsNone(send.current_slot(local(2026, 10, 4, 9, 7)))    # Sunday

    def test_every_cron_run_sends_each_slot_exactly_once_in_summer_and_winter(self):
        for day in (datetime.date(2026, 7, 15), datetime.date(2026, 12, 9)):   # CDT and CST
            sent = []
            for hh, mm in CRON_TIMES_UTC:
                utc = datetime.datetime(day.year, day.month, day.day, hh, mm, tzinfo=UTC)
                slot = send.current_slot(utc.astimezone(CHICAGO))
                if slot:
                    sent.append(slot)
            self.assertEqual(sorted(sent), ["afternoon", "midday", "morning"], day)


class MessageTests(unittest.TestCase):
    def setUp(self):
        self.groups = send.load_messages()

    def test_every_slot_has_messages(self):
        for slot in send.SLOTS:
            self.assertGreater(len(self.groups.get(slot, [])), 5, slot)

    def test_full_cycle_uses_every_message_once(self):
        for slot, msgs in self.groups.items():
            # find the first workday that starts a cycle, then walk one full cycle
            day = datetime.date(2026, 1, 5)
            workdays = []
            while len(workdays) < len(msgs) * 3:
                if day.weekday() < 5:
                    workdays.append(day)
                day += datetime.timedelta(days=1)
            index = lambda d: ((d.toordinal() - 1) // 7) * 5 + min((d.toordinal() - 1) % 7, 4)
            start = next(i for i, d in enumerate(workdays) if index(d) % len(msgs) == 0)
            picks = [send.pick_message(msgs, d, slot) for d in workdays[start:start + len(msgs)]]
            self.assertEqual(len(set(picks)), len(msgs), slot)

    def test_same_day_gives_same_message(self):
        d = datetime.date(2026, 9, 28)
        msgs = self.groups["midday"]
        self.assertEqual(send.pick_message(msgs, d, "midday"), send.pick_message(msgs, d, "midday"))


if __name__ == "__main__":
    unittest.main()
