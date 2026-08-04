#!/usr/bin/env python3
"""
Mark class attendance, then rebuild the dashboard.

  python _dashboard/attend.py <course> <status> [date] [-- note...]
  python _dashboard/attend.py <course>            # show this course's log
  python _dashboard/attend.py                     # show every course
  python _dashboard/attend.py undo <course>       # remove the last entry
  python _dashboard/attend.py ... --push          # also commit and push

course   an id or short name, any case: lsm, pi, ss, eosd, daa
status   present | absent | cancelled   (also p / a / c)
date     YYYY-MM-DD, or a weekday name this week (mon..fri), or "today"
         (the default), "yesterday"

Examples
  python _dashboard/attend.py lsm present            # today, present
  python _dashboard/attend.py pi cancelled 2026-07-21
  python _dashboard/attend.py ss absent mon
  python _dashboard/attend.py daa present --push     # mark and publish
  python _dashboard/attend.py undo lsm

Attendance lives in _dashboard/plan.json under each course's
attendance.sessions. Cancelled classes are logged but never count toward the
percentage. You can also edit plan.json by hand; this script is just a
convenience wrapper that appends an entry and re-runs build.py.
"""

import datetime as dt
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLAN = HERE / "plan.json"
BUILD = HERE / "build.py"

# reuse the dashboard's weighted attendance logic so tallies always agree
_spec = importlib.util.spec_from_file_location("build", BUILD)
build = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build)

STATUS = {
    "present": "present", "p": "present", "yes": "present", "y": "present",
    "absent": "absent", "a": "absent", "no": "absent", "n": "absent",
    "cancelled": "cancelled", "canceled": "cancelled", "c": "cancelled", "off": "cancelled",
}
MARK = {"present": "[P]", "absent": "[A]", "cancelled": "[-]"}
WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def die(msg):
    print(f"error: {msg}\n", file=sys.stderr)
    print(__doc__.strip(), file=sys.stderr)
    sys.exit(1)


def load():
    return json.loads(PLAN.read_text(encoding="utf-8"))


def save(plan):
    PLAN.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def find_course(plan, key):
    key = key.lower()
    for c in plan["courses"]:
        if c["id"].lower() == key or c["short"].lower() == key:
            return c
    opts = ", ".join(f'{c["id"]} ({c["short"]})' for c in plan["courses"])
    die(f'unknown course "{key}". choose from: {opts}')


def parse_date(tok, start_iso):
    tok = (tok or "today").lower()
    today = dt.date.today()
    if tok == "today":
        return today.isoformat()
    if tok == "yesterday":
        return (today - dt.timedelta(days=1)).isoformat()
    for i, name in enumerate(WEEKDAYS):
        if name.startswith(tok) and len(tok) >= 3:      # mon, tue, wed...
            monday = today - dt.timedelta(days=today.weekday())
            return (monday + dt.timedelta(days=i)).isoformat()
    try:
        return dt.date.fromisoformat(tok).isoformat()
    except ValueError:
        die(f'cannot read date "{tok}" — use YYYY-MM-DD, a weekday, or today/yesterday')


def sessions_of(course):
    att = course.setdefault("attendance", {})
    att.pop("held", None)                # migrate away from the counter form
    att.pop("attended", None)
    return att.setdefault("sessions", [])


def tally(plan, course):
    """One-line weighted summary (a 2-hour class counts as 2), via build.py."""
    s = build.attendance_stat(plan, course)
    pct = f'{s["pct"]:.0f}%' if s["pct"] is not None else "-"
    flag = {"ok": "  OK", "warn": "  OK", "below": "  BELOW"}.get(s["state"], "")
    extra = f', {s["cancelled"]} cancelled' if s["cancelled"] else ""
    return f'{course["short"]:6} {s["attended"]}/{s["held"]} classes{extra:16} {pct:>5}{flag}'


def show(plan, course=None):
    courses = [course] if course else plan["courses"]
    for c in courses:
        print(tally(plan, c))
        if course:                       # detail for a single course
            for s in (c.get("attendance") or {}).get("sessions", []):
                m = MARK.get(s.get("status"), "?")
                w = build.session_weight(plan, c["short"], s.get("date", ""))
                wt = f' (x{w})' if s.get("status") != "cancelled" and w != 1 else ""
                note = f'  {s["note"]}' if s.get("note") else ""
                print(f'   {s.get("date","?")}  {m} {s.get("status","?")}{wt}{note}')


def rebuild():
    subprocess.run([sys.executable, str(BUILD)], check=True)


def git_push(msg):
    root = HERE.parent
    subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(root), "commit", "-q", "-m", msg], check=True)
    subprocess.run(["git", "-C", str(root), "push", "-q", "origin", "main"], check=True)
    print("pushed.")


def main(argv):
    push = False
    if "--push" in argv:
        push = True
        argv = [a for a in argv if a != "--push"]

    note = ""
    if "--" in argv:
        i = argv.index("--")
        note = " ".join(argv[i + 1:])
        argv = argv[:i]

    plan = load()

    if not argv:                                     # show all
        show(plan)
        return

    if argv[0].lower() == "undo":
        if len(argv) < 2:
            die("undo needs a course, e.g. `undo lsm`")
        c = find_course(plan, argv[1])
        ss = sessions_of(c)
        if not ss:
            die(f'{c["short"]} has no entries to undo')
        removed = ss.pop()
        save(plan)
        rebuild()
        print(f'removed {c["short"]} {removed.get("date")} {removed.get("status")}')
        if push:
            git_push(f'Attendance: undo {c["short"]} {removed.get("date")}')
        return

    c = find_course(plan, argv[0])

    if len(argv) == 1:                               # show one course
        show(plan, c)
        return

    status = STATUS.get(argv[1].lower())
    if not status:
        die(f'unknown status "{argv[1]}" — use present, absent or cancelled')
    date = parse_date(argv[2] if len(argv) > 2 else None, plan["semester"]["start"])

    ss = sessions_of(c)
    dup = next((s for s in ss if s.get("date") == date), None)
    if dup:
        print(f'note: {c["short"]} already has {date} as {dup["status"]}; updating it.')
        dup["status"] = status
        if note:
            dup["note"] = note
    else:
        entry = {"date": date, "status": status}
        if note:
            entry["note"] = note
        ss.append(entry)
    ss.sort(key=lambda s: s.get("date", ""))
    save(plan)
    rebuild()

    print(f'{c["short"]}: {date} -> {MARK[status]} {status}')
    print(tally(plan, c))
    if push:
        git_push(f'Attendance: {c["short"]} {date} {status}')
    else:
        print("\n(local only - run git add/commit/push, or re-run with --push, to publish)")


if __name__ == "__main__":
    main(sys.argv[1:])
