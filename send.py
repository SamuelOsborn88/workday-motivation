#!/usr/bin/env python3
"""Send a motivational message to a phone via ntfy.

Usage:
    NTFY_TOPIC=<topic> python3 send.py                     # send if it's a scheduled time
    NTFY_TOPIC=<topic> python3 send.py --force midday      # send a slot's message now

Messages come from messages.txt, grouped by [morning] / [midday] / [afternoon].
Each group cycles in a shuffled order, so every message in it is used once
before any repeats.
"""
import datetime
import json
import os
import random
import sys
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

TIMEZONE = ZoneInfo("America/Chicago")
WORKDAYS = {0, 1, 2, 3, 4}          # Monday=0 … Friday=4
# Local send times. A run sends for a slot if it lands up to WINDOW after the slot time.
SLOTS = {
    "morning": datetime.time(9, 0),
    "midday": datetime.time(12, 0),
    "afternoon": datetime.time(15, 30),
}
WINDOW = datetime.timedelta(minutes=55)
NTFY_SERVER = os.environ.get("NTFY_SERVER", "https://ntfy.sh")

TITLES = {
    "morning": ["Good morning", "Rise and grind (gently)", "Morning boost", "Start of the day"],
    "midday": ["Midday check-in", "Halfway there", "Lunchtime boost", "Quick reminder"],
    "afternoon": ["Home stretch", "Afternoon boost", "Almost there", "Hang in there"],
}
TAGS = {
    "morning": ["sunrise", "coffee", "seedling", "star2"],
    "midday": ["sunny", "sparkles", "tea", "muscle"],
    "afternoon": ["rainbow", "fire", "checkered_flag", "house"],
}


def load_messages():
    groups, current = {}, None
    lines = (Path(__file__).parent / "messages.txt").read_text(encoding="utf-8").splitlines()
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            current = line[1:-1].strip().lower()
            groups.setdefault(current, [])
        elif current:
            groups[current].append(line)
    return groups


def pick_message(messages, today, slot):
    # Shuffle each full cycle with a fixed seed so the order is stable but mixed,
    # then walk through it one message per workday (weekends don't use one up).
    week, weekday = divmod(today.toordinal() - 1, 7)   # ordinal 1 is a Monday
    day_number = week * 5 + min(weekday, 4)
    cycle, position = divmod(day_number, len(messages))
    order = list(range(len(messages)))
    random.Random(f"{slot}-{cycle}").shuffle(order)
    return messages[order[position]]


def current_slot(now):
    if now.weekday() not in WORKDAYS:
        return None
    for slot, t in SLOTS.items():
        start = now.replace(hour=t.hour, minute=t.minute, second=0, microsecond=0)
        if start <= now < start + WINDOW:
            return slot
    return None


def main():
    topic = os.environ.get("NTFY_TOPIC")
    if not topic:
        sys.exit("NTFY_TOPIC is not set")

    now = datetime.datetime.now(TIMEZONE)
    args = sys.argv[1:]
    if "--force" in args:
        rest = [a for a in args if a != "--force"]
        slot = rest[0] if rest else "midday"
        if slot not in SLOTS:
            sys.exit(f"Unknown slot {slot!r}; choose from {', '.join(SLOTS)}")
    else:
        # The scheduler fires at two UTC times per slot to cover daylight saving;
        # only the one that lands in the slot's local window actually sends.
        slot = current_slot(now)
        if slot is None:
            print(f"Not a send time ({now:%a %H:%M %Z}); skipping.")
            return

    message = pick_message(load_messages()[slot], now.date(), slot)
    rng = random.Random(f"{slot}-{now.date().toordinal()}")
    payload = {
        "topic": topic,
        "title": rng.choice(TITLES[slot]),
        "message": message,
        "tags": [rng.choice(TAGS[slot])],
    }
    req = urllib.request.Request(
        NTFY_SERVER,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        print(f"Sent {slot} ({resp.status}): {message}")


if __name__ == "__main__":
    main()
