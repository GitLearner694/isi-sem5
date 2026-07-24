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
  <div class="tracks">{''.join(tracks_html)}</div>
  {proj}
</section>"""


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


def render_weeks(plan, cur_week):
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

        flags = []
        if state == "current":
            flags.append('<span class="flag now">this week</span>')
        if open_tasks:
            flags.append(f'<span class="flag task">{open_tasks} open</span>')
        if filled == 0:
            flags.append('<span class="flag empty-f">not logged</span>')

        note = f'<div class="wnote">{esc(w["note"])}</div>' if w.get("note") else ""
        out.append(f"""
<details class="week {state}"{" open" if state == "current" else ""} data-state="{state}">
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

    ms_html = "".join(
        f'<li class="stack"><span class="due-d">{esc(m["date"]) if m.get("date") else "TBD"}</span>'
        f'<span class="lab">{esc(m["label"])}'
        + (f'<em class="sub-note">{esc(m["note"])}</em>' if m.get("note") else "")
        + '</span></li>'
        for m in plan.get("milestones", [])
    ) or '<li class="empty">none set</li>'

    cards = "".join(render_course_card(plan, c, scans) for c in plan["courses"])
    weeks_html = render_weeks(plan, cur_week)
    syl_html = render_syllabus(plan, covered)
    sched_html = render_schedule(plan)

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
  font-size:12px; min-width:64px }}
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
  <span class="sub">{esc(sem['also_known_as']) + ' &middot; ' if sem.get('also_known_as') else ''}Week {cur_week} of {sem['num_weeks']} &middot; {today.strftime('%A, %d %B %Y')}</span>
  <nav>{nav}<a href="#schedule">Schedule</a><a href="#weekly">Weekly</a><a href="#syllabus">Syllabus</a></nav>
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

<div style="margin-top:14px">{info_html}</div>

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
  Official syllabus and reference texts as printed in the B.Stat (2016) brochure.
  A topic ticks off when its index is listed under a week&rsquo;s
  <code>syllabus</code> field in <code>_dashboard/plan.json</code>.</p>
{syl_html}

<footer>
  Generated {dt.datetime.now().strftime('%d %b %Y, %H:%M')} from
  <code>_dashboard/plan.json</code>. Edit that file, then run
  <code>python _dashboard/build.py</code> to refresh this page.
</footer>
</div>

<script>
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
