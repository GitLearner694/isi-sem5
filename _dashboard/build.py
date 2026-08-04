#!/usr/bin/env python3
"""
Builds Dashboard.html for the Semester 5 folder.

  python _dashboard/build.py

What it does
  1. Creates any missing subject / section folders described in plan.json.
  2. Backfills the "weeks" array in plan.json up to semester.num_weeks.
  3. Scans every section folder for files.
  4. Writes Dashboard.html at the root of the semester folder.

plan.json is the only file meant to be hand-edited. Re-run this after
editing it, or after dropping new notes into the folders.
"""

import json
import os
import html
import math
import datetime as dt
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
PLAN = Path(__file__).resolve().parent / "plan.json"
OUT = ROOT / "index.html"

SECTIONS = ["Notes", "Study Material", "Assignments", "Weekly Review"]
SECTION_ICON = {
    "Notes": "&#9998;",
    "Study Material": "&#128218;",
    "Assignments": "&#9745;",
    "Weekly Review": "&#128260;",
    "Project": "&#128203;",
}
SKIP_FILES = {"desktop.ini", ".gitkeep", "Thumbs.db", ".DS_Store"}

TRACK_KEY = {"topics": list, "syllabus": list, "study": list, "tasks": list}


# ---------------------------------------------------------------- plan / dirs

def load_plan():
    with open(PLAN, encoding="utf-8") as f:
        return json.load(f)


def save_plan(plan):
    with open(PLAN, "w", encoding="utf-8") as f:
        json.dump(plan, f, indent=2, ensure_ascii=False)
        f.write("\n")


def all_tracks(plan):
    """Yield (course, track) for every track in the plan."""
    for c in plan["courses"]:
        for t in c["tracks"]:
            yield c, t


def track_dir(course, track):
    d = ROOT / course["folder"]
    if track.get("subfolder"):
        d = d / track["subfolder"]
    return d


def has_project(course):
    return bool((course.get("weights") or {}).get("Project"))


def ensure_dirs(plan):
    created = []
    info = plan["semester"].get("info_folder")
    if info and not (ROOT / info).exists():
        (ROOT / info).mkdir(parents=True, exist_ok=True)
        created.append(ROOT / info)
    for course, track in all_tracks(plan):
        base = track_dir(course, track)
        for s in SECTIONS:
            p = base / s
            if not p.exists():
                p.mkdir(parents=True, exist_ok=True)
                created.append(p)
    for c in plan["courses"]:
        if has_project(c):
            p = ROOT / c["folder"] / "Project"
            if not p.exists():
                p.mkdir(parents=True, exist_ok=True)
                created.append(p)
    return created


def ensure_weeks(plan):
    """Grow plan['weeks'] to num_weeks and make sure every track key exists."""
    start = dt.date.fromisoformat(plan["semester"]["start"])
    n_target = plan["semester"]["num_weeks"]
    weeks = plan.setdefault("weeks", [])
    track_ids = [t["id"] for _, t in all_tracks(plan)]

    for i in range(len(weeks), n_target):
        weeks.append({"n": i + 1, "note": "", "tracks": {}})

    for i, w in enumerate(weeks):
        ws = start + dt.timedelta(days=7 * i)
        w["n"] = i + 1
        w["start"] = ws.isoformat()
        w["end"] = (ws + dt.timedelta(days=6)).isoformat()
        w.setdefault("note", "")
        tr = w.setdefault("tracks", {})
        for tid in track_ids:
            e = tr.setdefault(tid, {})
            for k, kind in TRACK_KEY.items():
                e.setdefault(k, kind())
    return weeks


# ------------------------------------------------------------------ scanning

def scan(folder):
    """Files directly inside `folder` (recursing into subfolders), newest first."""
    out = []
    if not folder.is_dir():
        return out
    for p in folder.rglob("*"):
        if p.is_dir() or p.name in SKIP_FILES or p.name.startswith("~$"):
            continue
        st = p.stat()
        out.append({
            "name": p.name,
            "rel": p.relative_to(ROOT).as_posix(),
            "sub": p.parent.relative_to(folder).as_posix() if p.parent != folder else "",
            "size": st.st_size,
            "mtime": st.st_mtime,
        })
    out.sort(key=lambda f: -f["mtime"])
    return out


def human_size(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024


def href(rel):
    return quote(rel)


# ------------------------------------------------------------------ rendering

def esc(s):
    return html.escape(str(s), quote=True)


WEIGHT_CLS = {
    "Mid-Semester": "w-mid", "Mid-Semester Exam": "w-mid",
    "Semester": "w-sem", "Final Exam": "w-sem", "Semester Exam": "w-sem",
    "Project": "w-proj",
    "Assignments": "w-asg", "Homework Assignments": "w-asg",
}
FALLBACK_CLS = ["w-mid", "w-sem", "w-proj", "w-asg"]


def weight_bar(weights):
    """Renders whatever components a course actually has, in plan.json order."""
    items = [(k, v) for k, v in (weights or {}).items() if v]
    if not items:
        return '<div class="wbar unknown"><span>weighting not specified</span></div>'
    segs, keys = [], []
    for i, (k, v) in enumerate(items):
        c = WEIGHT_CLS.get(k, FALLBACK_CLS[i % len(FALLBACK_CLS)])
        segs.append(f'<div class="wseg {c}" style="flex:{v}" title="{esc(k)}: {v}%">{v}</div>')
        keys.append(f'<span class="wkey"><i class="dot {c}"></i>{esc(k)} {v}%</span>')
    total = sum(v for _, v in items)
    warn = ("" if total == 100 else
            f'<span class="wkey wtot">components sum to {total}%</span>')
    return (f'<div class="wbar">{"".join(segs)}</div>'
            f'<div class="wkeys">{"".join(keys)}{warn}</div>')


def file_list(files, empty_msg):
    if not files:
        return f'<p class="empty">{esc(empty_msg)}</p>'
    rows = []
    for f in files:
        sub = f'<span class="sub">{esc(f["sub"])}/</span>' if f["sub"] else ""
        when = dt.datetime.fromtimestamp(f["mtime"]).strftime("%d %b")
        rows.append(
            f'<li><a href="{href(f["rel"])}">{sub}{esc(f["name"])}</a>'
            f'<span class="meta">{human_size(f["size"])} &middot; {when}</span></li>'
        )
    return f'<ul class="files">{"".join(rows)}</ul>'


PRESENT = {"present", "p", "yes", "y"}
ABSENT = {"absent", "a", "no", "n"}
CANCELLED = {"cancelled", "canceled", "c", "off"}


def attendance_stat(course, default_threshold):
    """Percentage, threshold state and a concrete next-step hint for one course.

    Reads a session log — attendance.sessions = [{date, status}, ...] — where
    status is present / absent / cancelled. Cancelled sessions are excluded from
    the denominator entirely. Falls back to plain held/attended counters if no
    session list is present.
    """
    a = course.get("attendance") or {}
    thr = a.get("threshold", default_threshold)
    sessions = a.get("sessions")
    if sessions is not None:
        held = sum(1 for s in sessions if s.get("status") in PRESENT | ABSENT)
        att = sum(1 for s in sessions if s.get("status") in PRESENT)
        cancelled = sum(1 for s in sessions if s.get("status") in CANCELLED)
    else:
        held = int(a.get("held", 0) or 0)
        att = int(a.get("attended", 0) or 0)
        cancelled = 0

    if held <= 0:
        if cancelled:
            hint = f"{cancelled} cancelled &middot; none counted yet"
        else:
            hint = "no classes recorded yet"
        return {"held": 0, "attended": att, "cancelled": cancelled, "pct": None,
                "thr": thr, "state": "none", "hint": hint}

    pct = 100.0 * att / held
    t = thr / 100.0
    if pct + 1e-9 >= thr:
        buf = int(att / t - held + 1e-9) if t > 0 else 0     # classes still missable
        hint = f"can miss {buf} more and stay &ge;&thinsp;{thr:g}%" if buf > 0 else "right at the line"
        state = "ok" if pct >= thr + 7 else "warn"
    else:
        need = max(0, math.ceil((t * held - att) / (1 - t) - 1e-9)) if t < 1 else 0
        hint = f"attend the next {need} to reach {thr:g}%"
        state = "below"
    return {"held": held, "attended": att, "cancelled": cancelled, "pct": pct,
            "thr": thr, "state": state, "hint": hint}


def attendance_meter(short, s):
    """Full meter used in the overview section."""
    if s["state"] == "none":
        return (f'<div class="amtr none"><div class="amtr-h">'
                f'<span class="badge sm">{esc(short)}</span><b>&mdash;</b></div>'
                f'<div class="ameter"><i class="athr" style="left:{s["thr"]}%"></i></div>'
                f'<div class="amtr-f"><span class="ahint">{s["hint"]}</span></div></div>')
    canc = f' &middot; {s["cancelled"]} cancelled' if s.get("cancelled") else ""
    return (f'<div class="amtr {s["state"]}"><div class="amtr-h">'
            f'<span class="badge sm">{esc(short)}</span><b>{s["pct"]:.0f}%</b></div>'
            f'<div class="ameter"><span class="afill" style="width:{min(s["pct"],100):.1f}%"></span>'
            f'<i class="athr" style="left:{s["thr"]}%" title="{s["thr"]:g}% required"></i></div>'
            f'<div class="amtr-f"><span>{s["attended"]}/{s["held"]} classes{canc}</span>'
            f'<span class="ahint">{s["hint"]}</span></div></div>')


def render_attendance(plan):
    thr = plan["semester"].get("attendance_threshold", 75)
    stats = [attendance_stat(c, thr) for c in plan["courses"]]
    any_held = any(s["held"] for s in stats)
    meters = "".join(attendance_meter(c["short"], s)
                     for c, s in zip(plan["courses"], stats))
    src = plan["semester"].get("attendance_source")
    note = f'<p class="src">{esc(src)}</p>' if src else ""
    if not any_held:
        note += ('<p class="src">Mark a class from the course folder with, e.g., '
                 '<code>python _dashboard/attend.py lsm present</code> '
                 '(status: present / absent / cancelled). See the README.</p>')
    return f'{note}<div class="attgrid">{meters}</div>'


def render_course_card(plan, course, scans):
    tracks_html = []
    for t in course["tracks"]:
        s = scans[t["id"]]
        total = sum(len(v) for v in s.values())
        head = ""
        if t.get("name"):
            head = f'<div class="track-name">{esc(t["name"])}</div>'
        extra = []
        if t.get("class_times"):
            extra.append('<span class="ct">' +
                         " &middot; ".join(esc(x) for x in t["class_times"]) + "</span>")
        if t.get("room"):
            extra.append(f'<span class="rm">{esc(t["room"])}</span>')
        if t.get("email"):
            extra.append(f'<a class="em" href="mailto:{esc(t["email"])}">{esc(t["email"])}</a>')
        extra_html = f'<div class="track-extra">{"".join(extra)}</div>' if extra else ""
        secs = []
        for name in SECTIONS:
            files = s[name]
            secs.append(
                f'<details class="sec"{" open" if files else ""}>'
                f'<summary><span class="ico">{SECTION_ICON[name]}</span>{esc(name)}'
                f'<span class="count">{len(files)}</span></summary>'
                f'{file_list(files, "nothing here yet")}</details>'
            )
        tracks_html.append(
            f'<div class="track">{head}'
            f'<div class="track-meta"><span class="teacher">{esc(t["teacher"])}</span>'
            f'<span class="unit">{esc(t["unit"])}</span>'
            f'<span class="fcount">{total} file{"" if total == 1 else "s"}</span></div>'
            f'{extra_html}'
            f'<div class="secs">{"".join(secs)}</div>'
            f'</div>'
        )

    proj = ""
    if has_project(course):
        pf = scan(ROOT / course["folder"] / "Project")
        proj = (f'<details class="sec proj"{" open" if pf else ""}>'
                f'<summary><span class="ico">{SECTION_ICON["Project"]}</span>Project'
                f'<span class="count">{len(pf)}</span></summary>'
                f'{file_list(pf, "no project files yet")}</details>')

    note = ""
    if course.get("weights_note"):
        note = f'<p class="note">{esc(course["weights_note"])}</p>'

    a = attendance_stat(course, plan["semester"].get("attendance_threshold", 75))
    if a["state"] == "none":
        att_line = ""
    else:
        canc = f' &middot; {a["cancelled"]} canc.' if a.get("cancelled") else ""
        att_line = (f'<div class="att-line {a["state"]}">Attendance '
                    f'<b>{a["pct"]:.0f}%</b> <span>({a["attended"]}/{a["held"]}{canc})</span>'
                    f'<span class="ahint">{a["hint"]}</span></div>')

    return f"""
<section class="card" id="c-{esc(course['id'])}">
  <header class="card-head">
    <div>
      <h3>{esc(course['name'])}</h3>
      <a class="folder" href="{href(course['folder'])}">{esc(course['folder'])}/</a>
    </div>
    <span class="badge">{esc(course['short'])}</span>
  </header>
  {weight_bar(course.get('weights') or {})}
  {note}
  {att_line}
  <div class="tracks">{''.join(tracks_html)}</div>
  {proj}
</section>"""


def fmt_range(s, e=None):
    ds = dt.date.fromisoformat(s)
    if not e or e == s:
        return ds.strftime("%d %b %Y")
    de = dt.date.fromisoformat(e)
    if (ds.year, ds.month) == (de.year, de.month):
        return f'{ds.strftime("%d")} &ndash; {de.strftime("%d %b %Y")}'
    if ds.year == de.year:
        return f'{ds.strftime("%d %b")} &ndash; {de.strftime("%d %b %Y")}'
    return f'{ds.strftime("%d %b %Y")} &ndash; {de.strftime("%d %b %Y")}'


def render_term(plan):
    ph = []
    for p in plan.get("term", []):
        ph.append(f'<div class="phase" data-start="{p["start"]}" data-end="{p["end"]}">'
                  f'<div class="ph-lab">{esc(p["label"])}</div>'
                  f'<div class="ph-date">{fmt_range(p["start"], p.get("end"))}</div></div>')
    if not ph:
        return ""
    src = plan["semester"].get("calendar_source")
    note = f'<p class="src">{esc(src)}</p>' if src else ""
    return f'{note}<div class="phases">{"".join(ph)}</div>'


def week_overlays(plan, start, num_weeks):
    """Per week: holidays falling in it, and any exam/leave phase overlapping it."""
    hol, phase = {}, {}
    teaching = set((plan.get("schedule") or {}).get("days") or {})

    for h in plan.get("holidays", []):
        s = dt.date.fromisoformat(h["start"])
        e = dt.date.fromisoformat(h.get("end") or h["start"])
        d = s
        while d <= e:
            wk = (d - start).days // 7 + 1
            if 1 <= wk <= num_weeks:
                rec = hol.setdefault(wk, {}).setdefault(h["label"], [])
                rec.append((d, d.strftime("%A") in teaching))
            d += dt.timedelta(days=1)

    for p in plan.get("term", []):
        if p["label"] == "Classes":
            continue
        s = dt.date.fromisoformat(p["start"])
        e = dt.date.fromisoformat(p.get("end") or p["start"])
        for wk in range(1, num_weeks + 1):
            ws = start + dt.timedelta(days=7 * (wk - 1))
            we = ws + dt.timedelta(days=6)
            if s <= we and e >= ws:
                phase.setdefault(wk, []).append(p["label"])
    return hol, phase


def render_books(track):
    groups = track.get("books") or []
    if not groups:
        return ""
    out = []
    for g in groups:
        head = f'<div class="bk-group">{esc(g["group"])}</div>' if g.get("group") else ""
        out.append(head + "<ul class=\"bk-list\">" +
                   "".join(f"<li>{esc(b)}</li>" for b in g.get("items", [])) + "</ul>")
    return f'<div class="books"><div class="lbl">Reference texts</div>{"".join(out)}</div>'


def render_syllabus(plan, covered):
    """covered: {track_id: {idx: week_no}}"""
    blocks = []
    for course, track in all_tracks(plan):
        syl = track.get("syllabus") or []
        done = covered.get(track["id"], {})
        pct = round(100 * len(done) / len(syl)) if syl else 0
        label = course["name"] if not track.get("name") else f'{course["short"]} &middot; {esc(track["name"])}'
        items = []
        for i, topic in enumerate(syl):
            w = done.get(i)
            mark = f'<span class="wk">wk {w}</span>' if w else ""
            items.append(f'<li class="{"done" if w else ""}">{esc(topic)}{mark}</li>')
        src = (f'<p class="src">{esc(track["syllabus_source"])}</p>'
               if track.get("syllabus_source") else "")
        blocks.append(f"""
<details class="syl"{" open" if pct else ""}>
  <summary>
    <span class="syl-name">{label}</span>
    <span class="prog"><span class="prog-fill" style="width:{pct}%"></span></span>
    <span class="pct">{len(done)}/{len(syl)}</span>
  </summary>
  <div class="syl-body">
    {src}
    <ol class="syl-list">{''.join(items)}</ol>
    {render_books(track)}
  </div>
</details>""")
    return "".join(blocks)


def render_schedule(plan):
    sch = plan.get("schedule") or {}
    days = sch.get("days") or {}
    cols = []
    any_slot = False
    for day, slots in days.items():
        rows = []
        for s in slots:
            any_slot = True
            room = f'<span class="room">{esc(s["room"])}</span>' if s.get("room") else ""
            tag = f'<span class="badge sm">{esc(s["short"])}</span>' if s.get("short") else ""
            rows.append(f'<li><span class="time">{esc(s.get("time", ""))}</span>'
                        f'<span class="slot">{tag}<span class="lab">'
                        f'{esc(s.get("course", ""))}</span></span>{room}</li>')
        body = f'<ul>{"".join(rows)}</ul>' if rows else '<p class="empty">&mdash;</p>'
        cols.append(f'<div class="day"><div class="day-h">{esc(day)}</div>{body}</div>')
    msg = sch.get("note") if not any_slot else sch.get("source")
    note = f'<p class="src">{esc(msg)}</p>' if msg else ""
    return f'{note}<div class="timetable">{"".join(cols)}</div>' if cols else ""


def render_weeks(plan, cur_week, hol, phase):
    tmap = {t["id"]: (c, t) for c, t in all_tracks(plan)}
    out = []
    for w in plan["weeks"]:
        ws = dt.date.fromisoformat(w["start"])
        we = dt.date.fromisoformat(w["end"])
        rng = f'{ws.strftime("%d %b")} &ndash; {we.strftime("%d %b %Y")}'
        state = "past" if w["n"] < cur_week else ("current" if w["n"] == cur_week else "future")

        cols, filled, open_tasks = [], 0, 0
        for tid, (c, t) in tmap.items():
            e = w["tracks"].get(tid, {})
            topics, study, tasks = e.get("topics", []), e.get("study", []), e.get("tasks", [])
            if topics or study or tasks:
                filled += 1
            open_tasks += sum(1 for x in tasks if not x.get("done"))
            name = t["name"] or c["name"]

            body = []
            if topics:
                body.append('<div class="lbl">Covered</div><ul>' +
                            "".join(f"<li>{esc(x)}</li>" for x in topics) + "</ul>")
            if study:
                body.append('<div class="lbl">Study material</div><ul>' +
                            "".join(f"<li>{esc(x)}</li>" for x in study) + "</ul>")
            if tasks:
                rows = []
                for x in tasks:
                    d = f' <span class="due">due {esc(x["due"])}</span>' if x.get("due") else ""
                    rows.append(f'<li class="{"tdone" if x.get("done") else "todo"}">'
                                f'{"&#9745;" if x.get("done") else "&#9744;"} {esc(x.get("t", ""))}{d}</li>')
                body.append('<div class="lbl">To do</div><ul class="tasks">' + "".join(rows) + "</ul>")
            if not body:
                body.append('<p class="empty">not logged yet</p>')

            cols.append(f'<div class="wcol"><div class="wcol-h">'
                        f'<span class="badge sm">{esc(c["short"])}</span>{esc(name)}</div>'
                        f'{"".join(body)}</div>')

        flags = ['<span class="flag now">this week</span>']
        for label in phase.get(w["n"], []):
            flags.append(f'<span class="flag exam">{esc(label)}</span>')
        hits = hol.get(w["n"], {})
        if hits:
            lost = sum(1 for days in hits.values() for _, t in days if t)
            flags.append(f'<span class="flag hol">holiday'
                         f'{f" &middot; {lost} class day{'' if lost == 1 else 's'} off" if lost else ""}'
                         f'</span>')
        if open_tasks:
            flags.append(f'<span class="flag task">{open_tasks} open</span>')
        if filled == 0:
            flags.append('<span class="flag empty-f">not logged</span>')

        notes = []
        if w.get("note"):
            notes.append(esc(w["note"]))
        for label, days in hits.items():
            ds = ", ".join(d.strftime("%a %d %b") for d, _ in days)
            notes.append(f"{esc(label)}: {ds}")
        note = f'<div class="wnote">{" &middot; ".join(notes)}</div>' if notes else ""

        out.append(f"""
<details class="week {state}"{" open" if state == "current" else ""}
         data-state="{state}" data-n="{w['n']}">
  <summary><span class="wn">Week {w['n']}</span><span class="wr">{rng}</span>
  <span class="flags">{''.join(flags)}</span></summary>
  {note}
  <div class="wgrid">{''.join(cols)}</div>
</details>""")
    return "".join(out)


def render(plan, cur_week, scans):
    sem = plan["semester"]
    today = dt.date.today()

    # syllabus coverage from week entries
    covered = {}
    for w in plan["weeks"]:
        for tid, e in w["tracks"].items():
            for i in e.get("syllabus", []):
                covered.setdefault(tid, {}).setdefault(i, w["n"])

    # counters
    n_files = sum(len(v) for s in scans.values() for v in s.values())
    for c in plan["courses"]:
        if has_project(c):
            n_files += len(scan(ROOT / c["folder"] / "Project"))
    if plan["semester"].get("info_folder"):
        n_files += len(scan(ROOT / plan["semester"]["info_folder"]))
    n_open = sum(1 for w in plan["weeks"] for e in w["tracks"].values()
                 for t in e.get("tasks", []) if not t.get("done"))
    logged = sum(1 for w in plan["weeks"]
                 if any(e.get("topics") or e.get("study") or e.get("tasks")
                        for e in w["tracks"].values()))

    # upcoming tasks with due dates
    upcoming = []
    tmap = {t["id"]: (c, t) for c, t in all_tracks(plan)}
    for w in plan["weeks"]:
        for tid, e in w["tracks"].items():
            for t in e.get("tasks", []):
                if t.get("done") or not t.get("due"):
                    continue
                upcoming.append((t["due"], tmap[tid][0]["short"], t.get("t", ""), w["n"]))
    upcoming.sort()
    up_html = "".join(
        f'<li><span class="due-d">{esc(d)}</span><span class="badge sm">{esc(sh)}</span>'
        f'<span class="lab">{esc(txt)}</span><span class="meta">wk {wn}</span></li>'
        for d, sh, txt, wn in upcoming[:8]
    ) or '<li class="empty">nothing with a due date yet</li>'

    ms_rows = []
    for m in plan.get("milestones", []):
        s, e = m.get("start"), m.get("end")
        when = fmt_range(s, e) if s else "TBD"
        attrs = f' data-start="{s}" data-end="{e or s}"' if s else ""
        ms_rows.append(
            f'<li class="stack"{attrs}><span class="due-d">{when}</span>'
            f'<span class="lab">{esc(m["label"])}'
            + (f'<em class="sub-note">{esc(m["note"])}</em>' if m.get("note") else "")
            + '</span><span class="away"></span></li>')
    ms_html = "".join(ms_rows) or '<li class="empty">none set</li>'

    start_d = dt.date.fromisoformat(sem["start"])
    hol, phase = week_overlays(plan, start_d, sem["num_weeks"])

    cards = "".join(render_course_card(plan, c, scans) for c in plan["courses"])
    weeks_html = render_weeks(plan, cur_week, hol, phase)
    syl_html = render_syllabus(plan, covered)
    sched_html = render_schedule(plan)
    term_html = render_term(plan)
    att_html = render_attendance(plan)

    info_folder = plan["semester"].get("info_folder")
    info_files = scan(ROOT / info_folder) if info_folder else []
    info_html = (f'<div class="panel"><h4>Course information</h4>'
                 f'{file_list(info_files, "brochure, schedule and other semester-wide documents go in " + (info_folder or ""))}'
                 f'</div>') if info_folder else ""

    nav = "".join(f'<a href="#c-{esc(c["id"])}">{esc(c["short"])}</a>' for c in plan["courses"])

    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(sem['name'])} &middot; Dashboard</title>
<style>
:root {{
  --bg:#f7f7f5; --panel:#fff; --ink:#1a1a18; --dim:#6b6b66; --line:#e3e2dd;
  --accent:#8a5a2b; --ok:#3d7a4e; --warn:#a8622a;
  --mid:#c26a4a; --sem:#4a6fa5; --proj:#6b8e5a; --asg:#a58a4a;
}}
@media (prefers-color-scheme:dark) {{
  :root {{ --bg:#161614; --panel:#1e1e1c; --ink:#e8e7e2; --dim:#95948d; --line:#33322e;
    --accent:#d3a06a; --ok:#79b98c; --warn:#d9a05f;
    --mid:#d98a6a; --sem:#7a9fd5; --proj:#93b982; --asg:#c9ae6e; }}
}}
* {{ box-sizing:border-box }}
body {{ margin:0; background:var(--bg); color:var(--ink);
  font:15px/1.55 ui-sans-serif,-apple-system,"Segoe UI",system-ui,sans-serif; }}
a {{ color:inherit }}
.wrap {{ max-width:1180px; margin:0 auto; padding:0 20px 80px }}

header.top {{ position:sticky; top:0; z-index:20; background:var(--bg);
  border-bottom:1px solid var(--line); padding:14px 0 10px; margin-bottom:24px }}
header.top .wrap {{ padding-bottom:0; display:flex; align-items:baseline;
  gap:16px; flex-wrap:wrap }}
header.top h1 {{ font-size:17px; margin:0; letter-spacing:-.01em }}
header.top .sub {{ color:var(--dim); font-size:13px }}
nav {{ margin-left:auto; display:flex; gap:4px; flex-wrap:wrap }}
nav a {{ font-size:12px; padding:3px 9px; border:1px solid var(--line);
  border-radius:99px; text-decoration:none; color:var(--dim) }}
nav a:hover {{ color:var(--ink); border-color:var(--accent) }}

h2 {{ font-size:13px; text-transform:uppercase; letter-spacing:.09em;
  color:var(--dim); font-weight:600; margin:38px 0 14px }}
h2:first-of-type {{ margin-top:8px }}

.stats {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr));
  gap:12px; margin-bottom:8px }}
.stat {{ background:var(--panel); border:1px solid var(--line); border-radius:10px;
  padding:13px 15px }}
.stat b {{ display:block; font-size:24px; font-weight:600; letter-spacing:-.02em }}
.stat span {{ font-size:12px; color:var(--dim) }}

.two {{ display:grid; grid-template-columns:1fr 1fr; gap:14px }}
@media (max-width:760px) {{ .two {{ grid-template-columns:1fr }} }}
.panel {{ background:var(--panel); border:1px solid var(--line);
  border-radius:10px; padding:14px 16px }}
.panel h4 {{ margin:0 0 10px; font-size:12px; text-transform:uppercase;
  letter-spacing:.07em; color:var(--dim); font-weight:600 }}
.panel ul {{ list-style:none; margin:0; padding:0 }}
.panel li {{ display:flex; align-items:baseline; gap:9px; padding:5px 0;
  border-top:1px solid var(--line); font-size:13.5px }}
.panel li:first-child {{ border-top:0 }}
.panel li > .lab {{ flex:1; min-width:0 }}
.due-d {{ flex:0 0 auto; font-variant-numeric:tabular-nums; color:var(--warn);
  font-size:12px; min-width:104px }}
.panel .meta {{ flex:0 1 auto; color:var(--dim); font-size:11.5px;
  text-align:right }}
.sub-note {{ display:block; font-size:11.5px; color:var(--dim); font-style:normal }}

.cards {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(330px,1fr));
  gap:14px; align-items:start }}
.card {{ background:var(--panel); border:1px solid var(--line);
  border-radius:12px; padding:16px 17px; scroll-margin-top:74px }}
.card-head {{ display:flex; justify-content:space-between; align-items:flex-start;
  gap:10px; margin-bottom:12px }}
.card h3 {{ margin:0; font-size:16.5px; letter-spacing:-.01em; line-height:1.3 }}
.folder {{ font-size:11.5px; color:var(--dim); text-decoration:none;
  font-family:ui-monospace,Consolas,monospace }}
.folder:hover {{ color:var(--accent) }}
.badge {{ font-size:11px; font-weight:600; letter-spacing:.04em; padding:2px 8px;
  border-radius:5px; background:var(--bg); border:1px solid var(--line);
  color:var(--dim); white-space:nowrap }}
.badge.sm {{ font-size:10px; padding:1px 6px }}

.wbar {{ display:flex; height:20px; border-radius:5px; overflow:hidden;
  margin-bottom:7px }}
.wseg {{ display:flex; align-items:center; justify-content:center; color:#fff;
  font-size:10.5px; font-weight:600 }}
.w-mid {{ background:var(--mid) }} .w-sem {{ background:var(--sem) }}
.w-proj {{ background:var(--proj) }} .w-asg {{ background:var(--asg) }}
.wbar.unknown {{ background:repeating-linear-gradient(45deg,var(--bg),var(--bg) 6px,
  var(--line) 6px,var(--line) 12px); align-items:center; justify-content:center }}
.wbar.unknown span {{ font-size:11px; color:var(--dim) }}
.wkeys {{ display:flex; flex-wrap:wrap; gap:10px; font-size:11px; color:var(--dim) }}
.dot {{ display:inline-block; width:7px; height:7px; border-radius:2px;
  margin-right:4px }}
.wtot {{ color:var(--warn) }}
.note {{ font-size:11.5px; color:var(--warn); margin:8px 0 0 }}

.tracks {{ margin-top:14px; display:flex; flex-direction:column; gap:14px }}
.track + .track {{ border-top:1px dashed var(--line); padding-top:14px }}
.track-name {{ font-size:13.5px; font-weight:600; margin-bottom:3px }}
.track-meta {{ display:flex; gap:8px; align-items:center; flex-wrap:wrap;
  font-size:12px; color:var(--dim); margin-bottom:8px }}
.teacher {{ color:var(--ink) }}
.unit {{ border:1px solid var(--line); border-radius:4px; padding:0 5px;
  font-size:10.5px }}
.fcount {{ margin-left:auto }}
.track-extra {{ display:flex; flex-wrap:wrap; gap:5px 10px; margin:-3px 0 9px;
  font-size:11.5px; color:var(--dim) }}
.track-extra .ct {{ color:var(--warn) }}
.track-extra .em {{ text-decoration:none; border-bottom:1px solid transparent }}
.track-extra .em:hover {{ color:var(--accent); border-bottom-color:var(--accent) }}

details.sec {{ border-top:1px solid var(--line) }}
details.sec summary {{ cursor:pointer; padding:6px 0; font-size:13px;
  display:flex; align-items:center; gap:7px; list-style:none }}
details.sec summary::-webkit-details-marker {{ display:none }}
details.sec summary::before {{ content:"\\25B8"; color:var(--dim); font-size:10px;
  transition:transform .12s }}
details.sec[open] summary::before {{ transform:rotate(90deg) }}
.ico {{ opacity:.6 }}
.count {{ margin-left:auto; font-size:11px; color:var(--dim);
  background:var(--bg); border-radius:99px; padding:0 7px; min-width:20px;
  text-align:center }}
details.proj {{ margin-top:12px; border-top:1px solid var(--line) }}

ul.files {{ list-style:none; margin:0 0 8px; padding:0 0 0 17px }}
ul.files li {{ display:flex; gap:9px; align-items:baseline; padding:2.5px 0;
  font-size:13px }}
ul.files a {{ text-decoration:none; border-bottom:1px solid transparent;
  overflow-wrap:anywhere }}
ul.files a:hover {{ border-bottom-color:var(--accent); color:var(--accent) }}
ul.files .sub {{ color:var(--dim) }}
ul.files .meta {{ margin-left:auto; color:var(--dim); font-size:11px;
  white-space:nowrap }}
.empty {{ color:var(--dim); font-size:12.5px; font-style:italic;
  margin:2px 0 8px 17px }}

details.syl {{ background:var(--panel); border:1px solid var(--line);
  border-radius:10px; margin-bottom:9px }}
details.syl summary {{ cursor:pointer; padding:11px 15px; display:flex;
  align-items:center; gap:13px; list-style:none; font-size:14px }}
details.syl summary::-webkit-details-marker {{ display:none }}
.syl-name {{ font-weight:500; flex:0 0 auto }}
.prog {{ flex:1; height:5px; background:var(--bg); border-radius:99px;
  overflow:hidden; min-width:60px }}
.prog-fill {{ display:block; height:100%; background:var(--ok) }}
.pct {{ font-size:11.5px; color:var(--dim); font-variant-numeric:tabular-nums }}
.syl-body {{ padding:0 18px 14px }}
.src {{ margin:0 0 10px 20px; font-size:11.5px; color:var(--dim);
  font-style:italic }}
ol.syl-list {{ margin:0; padding:0 0 0 20px; font-size:13.5px;
  color:var(--dim) }}
ol.syl-list li {{ padding:3px 0 }}
.books {{ margin-top:14px; padding-top:12px; border-top:1px dashed var(--line) }}
.books .lbl {{ font-size:10.5px; text-transform:uppercase; letter-spacing:.06em;
  color:var(--dim); margin-bottom:6px }}
.bk-group {{ font-size:12px; font-weight:600; margin:9px 0 3px; color:var(--ink) }}
ul.bk-list {{ margin:0; padding-left:20px; font-size:13px; color:var(--dim) }}
ul.bk-list li {{ padding:2px 0 }}

.timetable {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr));
  gap:1px; background:var(--line); border:1px solid var(--line);
  border-radius:10px; overflow:hidden }}
.day {{ background:var(--panel); padding:11px 13px 13px; min-height:78px }}
.day-h {{ font-size:11px; text-transform:uppercase; letter-spacing:.06em;
  color:var(--dim); font-weight:600; margin-bottom:7px }}
.day ul {{ list-style:none; margin:0; padding:0 }}
.day li {{ display:flex; flex-direction:column; gap:2px; padding:7px 0;
  border-top:1px solid var(--line); font-size:13px }}
.day li:first-child {{ border-top:0 }}
.slot {{ display:flex; align-items:baseline; gap:6px }}
.slot .lab {{ line-height:1.3 }}
.time {{ font-size:11px; color:var(--warn); font-variant-numeric:tabular-nums }}
.room {{ font-size:11px; color:var(--dim) }}
.day .empty {{ margin:0 }}
ol.syl-list li.done {{ color:var(--ink) }}
ol.syl-list li.done::marker {{ color:var(--ok) }}
.wk {{ font-size:10.5px; color:var(--ok); border:1px solid var(--ok);
  border-radius:4px; padding:0 5px; margin-left:8px; white-space:nowrap }}

details.week {{ background:var(--panel); border:1px solid var(--line);
  border-radius:10px; margin-bottom:8px }}
details.week.current {{ border-color:var(--accent) }}
details.week.past {{ opacity:.82 }}
details.week summary {{ cursor:pointer; padding:11px 15px; display:flex;
  align-items:center; gap:13px; list-style:none; font-size:14px }}
details.week summary::-webkit-details-marker {{ display:none }}
.wn {{ font-weight:600; min-width:66px }}
.wr {{ color:var(--dim); font-size:12.5px; font-variant-numeric:tabular-nums }}
.flags {{ margin-left:auto; display:flex; gap:6px; flex-wrap:wrap }}
.flag {{ font-size:10.5px; padding:1px 7px; border-radius:99px;
  border:1px solid var(--line); color:var(--dim) }}
.flag.now {{ border-color:var(--accent); color:var(--accent) }}
.flag.task {{ border-color:var(--warn); color:var(--warn) }}
.flag.exam {{ border-color:var(--mid); color:var(--mid) }}
.flag.hol {{ border-color:var(--proj); color:var(--proj) }}
details.week:not(.current) .flag.now {{ display:none }}

.phases {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr));
  gap:1px; background:var(--line); border:1px solid var(--line);
  border-radius:10px; overflow:hidden }}
.phase {{ background:var(--panel); padding:11px 13px 12px }}
.phase.on {{ background:color-mix(in srgb, var(--accent) 12%, var(--panel)) }}
.phase.done {{ opacity:.55 }}
.ph-lab {{ font-size:12.5px; font-weight:600; line-height:1.3 }}
.phase.on .ph-lab {{ color:var(--accent) }}
.ph-date {{ font-size:11.5px; color:var(--dim); margin-top:3px;
  font-variant-numeric:tabular-nums }}
.away {{ flex:0 0 auto; font-size:11px; color:var(--dim); white-space:nowrap }}
.away.soon {{ color:var(--warn) }}
.away.now {{ color:var(--accent) }}

/* attendance: --ac is the state colour, set per meter */
.attgrid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(190px,1fr));
  gap:12px }}
.amtr {{ background:var(--panel); border:1px solid var(--line); border-radius:10px;
  padding:13px 15px 12px }}
.amtr.ok {{ --ac:var(--ok) }} .amtr.warn {{ --ac:var(--warn) }}
.amtr.below {{ --ac:#c0392b }} .amtr.none {{ --ac:var(--line) }}
.amtr-h {{ display:flex; align-items:center; gap:8px; margin-bottom:9px }}
.amtr-h b {{ margin-left:auto; font-size:22px; font-weight:600;
  letter-spacing:-.02em; color:var(--ac) }}
.amtr.none .amtr-h b {{ color:var(--dim) }}
.ameter {{ position:relative; height:8px; background:var(--bg);
  border-radius:99px; overflow:hidden }}
.afill {{ display:block; height:100%; background:var(--ac); border-radius:99px }}
.athr {{ position:absolute; top:-3px; width:2px; height:14px; background:var(--ink);
  opacity:.55; transform:translateX(-1px) }}
.amtr-f {{ display:flex; gap:10px; margin-top:8px; font-size:11.5px;
  color:var(--dim) }}
.amtr-f .ahint {{ margin-left:auto; text-align:right; color:var(--ac) }}
.amtr.warn .amtr-f .ahint, .amtr.ok .amtr-f .ahint {{ color:var(--dim) }}
.amtr.none .ahint {{ margin-left:0 }}

.att-line {{ display:flex; align-items:baseline; gap:7px; margin:9px 0 0;
  font-size:12.5px; color:var(--dim); --ac:var(--ok) }}
.att-line.warn {{ --ac:var(--warn) }} .att-line.below {{ --ac:#c0392b }}
.att-line b {{ font-size:14px; color:var(--ac) }}
.att-line .ahint {{ margin-left:auto; color:var(--ac) }}
.att-line.ok .ahint, .att-line.warn .ahint {{ color:var(--dim) }}
.wnote {{ padding:0 15px 10px; font-size:13px; color:var(--dim) }}
.wgrid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(215px,1fr));
  gap:1px; background:var(--line); border-top:1px solid var(--line) }}
.wcol {{ background:var(--panel); padding:12px 14px 14px }}
.wcol-h {{ display:flex; align-items:center; gap:7px; font-size:12.5px;
  font-weight:600; margin-bottom:8px; line-height:1.3 }}
.wcol .lbl {{ font-size:10.5px; text-transform:uppercase; letter-spacing:.06em;
  color:var(--dim); margin-top:9px }}
.wcol ul {{ margin:3px 0 0; padding-left:16px; font-size:13px }}
.wcol li {{ padding:1.5px 0 }}
.wcol .empty {{ margin-left:0 }}
ul.tasks {{ list-style:none; padding-left:0 }}
ul.tasks li.tdone {{ color:var(--dim); text-decoration:line-through }}
.due {{ font-size:10.5px; color:var(--warn) }}

.filters {{ display:flex; gap:6px; margin-bottom:12px }}
.filters button {{ font:inherit; font-size:12px; padding:3px 11px;
  border:1px solid var(--line); background:var(--panel); color:var(--dim);
  border-radius:99px; cursor:pointer }}
.filters button.on {{ border-color:var(--accent); color:var(--accent) }}
footer {{ margin-top:44px; padding-top:16px; border-top:1px solid var(--line);
  font-size:11.5px; color:var(--dim) }}
code {{ font-family:ui-monospace,Consolas,monospace; font-size:11.5px;
  background:var(--panel); border:1px solid var(--line); border-radius:4px;
  padding:1px 5px }}
</style>
</head><body>

<header class="top"><div class="wrap">
  <h1>{esc(sem['program'])} &middot; {esc(sem['name'])}</h1>
  <span class="sub">{esc(sem['also_known_as']) + ' &middot; ' if sem.get('also_known_as') else ''}<span id="sub-week">Week {cur_week} of {sem['num_weeks']}</span> &middot; <span id="sub-date">{today.strftime('%A, %d %B %Y')}</span></span>
  <nav>{nav}<a href="#attendance">Attendance</a><a href="#term">Term</a><a href="#schedule">Schedule</a><a href="#weekly">Weekly</a><a href="#syllabus">Syllabus</a></nav>
</div></header>

<div class="wrap">

<h2>At a glance</h2>
<div class="stats">
  <div class="stat"><b>{len(plan['courses'])}</b><span>courses &middot; {len(list(all_tracks(plan)))} taught units</span></div>
  <div class="stat"><b>{n_files}</b><span>files filed</span></div>
  <div class="stat"><b>{logged}</b><span>weeks logged</span></div>
  <div class="stat"><b>{n_open}</b><span>open tasks</span></div>
</div>

<div class="two" style="margin-top:14px">
  <div class="panel"><h4>Next up</h4><ul>{up_html}</ul></div>
  <div class="panel"><h4>Milestones</h4><ul>{ms_html}</ul></div>
</div>

<h2 id="attendance">Attendance</h2>
{att_html}

<div style="margin-top:14px">{info_html}</div>

<h2 id="term">Term dates</h2>
{term_html}

<h2 id="schedule">Class schedule</h2>
{sched_html}

<h2>Courses</h2>
<div class="cards">{cards}</div>

<h2 id="weekly">Weekly plan</h2>
<div class="filters">
  <button data-f="all" class="on">All</button>
  <button data-f="current">This week</button>
  <button data-f="past">Past</button>
  <button data-f="future">Upcoming</button>
</div>
{weeks_html}

<h2 id="syllabus">Syllabus &amp; reference texts</h2>
<p style="font-size:12.5px;color:var(--dim);margin:-6px 0 14px">
  Each track cites its own source &mdash; the instructor&rsquo;s handout where one has been
  given, otherwise the B.Stat (2016) brochure. A topic ticks off when its index is
  listed under a week&rsquo;s <code>syllabus</code> field in
  <code>_dashboard/plan.json</code>.</p>
{syl_html}

<footer>
  Generated {dt.datetime.now().strftime('%d %b %Y, %H:%M')} from
  <code>_dashboard/plan.json</code>. Edit that file, then run
  <code>python _dashboard/build.py</code> to refresh this page.
</footer>
</div>

<script>
// The page is regenerated on a schedule, so anything relative to "today" is
// recomputed here on load -- otherwise it would drift between rebuilds.
(function () {{
  var START = "{sem['start']}", NW = {sem['num_weeks']};
  var DAY = 864e5;
  var today = new Date(); today.setHours(0, 0, 0, 0);
  var start = new Date(START + "T00:00:00");

  var wk = Math.floor((today - start) / (7 * DAY)) + 1;
  wk = Math.max(1, Math.min(NW, wk));

  var sw = document.getElementById('sub-week');
  if (sw) sw.textContent = 'Week ' + wk + ' of ' + NW;
  var sd = document.getElementById('sub-date');
  if (sd) sd.textContent = today.toLocaleDateString(undefined,
    {{ weekday: 'long', day: '2-digit', month: 'long', year: 'numeric' }});

  document.querySelectorAll('details.week').forEach(function (w) {{
    var n = +w.dataset.n;
    var st = n < wk ? 'past' : (n === wk ? 'current' : 'future');
    w.dataset.state = st;
    w.classList.remove('past', 'current', 'future');
    w.classList.add(st);
    w.open = (st === 'current');
  }});

  document.querySelectorAll('.phase').forEach(function (p) {{
    var s = new Date(p.dataset.start + "T00:00:00");
    var e = new Date(p.dataset.end + "T00:00:00");
    if (today > e) p.classList.add('done');
    else if (today >= s) p.classList.add('on');
  }});

  document.querySelectorAll('li[data-start] .away').forEach(function (el) {{
    var li = el.closest('li');
    var s = new Date(li.dataset.start + "T00:00:00");
    var e = new Date(li.dataset.end + "T00:00:00");
    var d = Math.round((s - today) / DAY);
    if (today > e) {{ el.textContent = 'done'; li.style.opacity = .5; return; }}
    if (d <= 0) {{ el.textContent = 'now'; el.className = 'away now'; return; }}
    el.textContent = d === 1 ? 'tomorrow' : 'in ' + d + ' days';
    if (d <= 14) el.className = 'away soon';
  }});
}})();

document.querySelectorAll('.filters button').forEach(function (b) {{
  b.addEventListener('click', function () {{
    document.querySelectorAll('.filters button').forEach(x => x.classList.remove('on'));
    b.classList.add('on');
    var f = b.dataset.f;
    document.querySelectorAll('details.week').forEach(function (w) {{
      w.style.display = (f === 'all' || w.dataset.state === f) ? '' : 'none';
    }});
  }});
}});
</script>
</body></html>
"""


# ---------------------------------------------------------------------- main

def main():
    plan = load_plan()
    created = ensure_dirs(plan)
    ensure_weeks(plan)
    save_plan(plan)

    start = dt.date.fromisoformat(plan["semester"]["start"])
    cur_week = max(1, min(plan["semester"]["num_weeks"],
                          (dt.date.today() - start).days // 7 + 1))

    scans = {}
    for course, track in all_tracks(plan):
        base = track_dir(course, track)
        scans[track["id"]] = {s: scan(base / s) for s in SECTIONS}

    OUT.write_text(render(plan, cur_week, scans), encoding="utf-8")

    for p in created:
        print("created  ", p.relative_to(ROOT))
    print(f"\nWeek {cur_week} of {plan['semester']['num_weeks']}")
    print("written  ", OUT.relative_to(ROOT))


if __name__ == "__main__":
    main()
