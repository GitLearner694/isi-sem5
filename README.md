# Semester 5 — B.Stat 3rd Year, ISI

Open **`index.html`** in a browser. That is the front page for the semester:
courses, grade weightings, the class schedule, every filed document, the
week-by-week plan, and a syllabus tracker with the official reference texts.

The same file is what gets published to GitHub Pages — see *Publishing* below.

## Folder layout

```
Sem 5/
├── index.html                           ← generated; open this
├── _dashboard/
│   ├── plan.json                        ← the only file you hand-edit
│   └── build.py                         ← regenerates index.html
│
├── 00 Course Information/               brochure, class schedule, notices
│
├── 01 Linear Statistical Models/        Debashis Paul · ASU
├── 02 Parametric Inference/             Probal Chaudhuri · SMU
├── 03 Sample Surveys/                   Ambarish Chattopadhyay · ASU
├── 04 Economic and Official Statistics and Demography/
│   ├── A Economic Statistics/                Kajori Banerjee · PSU
│   ├── B Official Statistics/                Sandip Mitra · SOSU
│   ├── C Demography/                         Kajori Banerjee · PSU
│   └── Project/
└── 05 Design and Analysis of Algorithms/  Sandip Das · ACMU
```

Course 04 is one combined course taught in three parts: Kajori Banerjee takes
Economic Statistics and Demography, Sandip Mitra takes Official Statistics.
Every course (and each part of course 04) has the same four sections:

| Section | What goes in it |
| --- | --- |
| `Notes/` | Lecture notes — class notes, scans, my own write-ups |
| `Study Material/` | Books, papers, problem sets, slides, reference handouts |
| `Assignments/` | Assignment questions and my submissions |
| `Weekly Review/` | My weekly consolidation of what was taught |

`Project/` sits at the course level for the three courses carrying project marks
(Sample Surveys, EOS&D, DAA).

## Grade weightings

| Course | Mid-Sem | Semester | Project | Assignments |
| --- | --- | --- | --- | --- |
| Linear Statistical Models | 40 | 50 | — | 10 |
| Parametric Inference | *not specified* | | | |
| Sample Surveys | 30 | 50 | 20 | — |
| Economic & Official Statistics and Demography | 30 | 50 | 20 | — |
| Design and Analysis of Algorithms | 30 | 50 | 20 | — |

Parametric Inference has no weighting on the course sheet — worth confirming with
the instructor and filling into `plan.json`.

## Marking attendance

Attendance shows on the dashboard as a meter per course, measured against ISI's
75% requirement. Mark a class with one command from the `Sem 5` folder:

```bash
python _dashboard/attend.py lsm present
```

- **course** — `lsm`, `pi`, `ss`, `eosd`, or `daa` (any case)
- **status** — `present`, `absent`, or `cancelled` (short forms `p` / `a` / `c`)
- **date** — optional; defaults to today. Also accepts `YYYY-MM-DD`, a weekday
  this week (`mon`…`fri`), or `yesterday`.

```bash
python _dashboard/attend.py pi cancelled 2026-07-21     # a specific date
python _dashboard/attend.py ss absent mon               # this Monday
python _dashboard/attend.py daa present --push          # mark AND publish
python _dashboard/attend.py                             # show every course
python _dashboard/attend.py lsm                         # show one course's log
python _dashboard/attend.py undo lsm                    # remove the last entry
```

The command rebuilds `index.html` for you. It does **not** push by default —
add `--push` to commit and publish in the same step, or push later with the
usual `git add/commit/push`. Add a reason with a trailing `-- note`:

```bash
python _dashboard/attend.py lsm absent -- travelling
```

**Class length matters.** A 2-hour class counts as 2, a 1-hour class as 1. The
weight is read automatically from the timetable by the day you mark, so you just
record present / absent / cancelled and the maths follows. (Only EOS&D mixes
lengths — Kajori Banerjee's Mon/Wed hours are single, Sandip Mitra's Tuesday is
a double.)

**Cancelled classes** are logged but never count toward the percentage — the
denominator only includes classes that actually met. Under the hood each class
is one entry in `attendance.sessions` in `plan.json`, so you can also edit that
by hand if you prefer.

## Weekly routine

1. Drop the week's files into the right subject folders. Subfolders inside a
   section are fine; the dashboard shows the path.
2. Log the week in `_dashboard/plan.json` under `weeks` (see below).
3. Run:

```bash
python _dashboard/build.py
```

The script also creates any missing folders and extends the week list, so it is
always safe to re-run.

## Logging a week in `plan.json`

Each week has one entry per taught unit, keyed by track id — `lsm`, `pi`, `ss`,
`eos`, `dem`, `daa`:

```json
{
  "n": 1,
  "start": "2026-07-20",
  "end": "2026-07-26",
  "note": "optional note for the whole week",
  "tracks": {
    "lsm": {
      "topics":   ["What was actually taught in class"],
      "syllabus": [0, 1],
      "study":    ["Rao, Linear Statistical Inference — Ch. 4"],
      "tasks":    [{ "t": "Assignment 1", "due": "2026-08-03", "done": false }]
    }
  }
}
```

- `topics` — free text; the real record of what was covered.
- `syllabus` — indices into that track's `syllabus` outline. Listing an index
  ticks the topic off in the syllabus tracker and tags it with the week number.
  Indices are 0-based and follow the order in `plan.json`.
- `study` — readings and material for the week.
- `tasks` — anything to do. Ones with a `due` date and `"done": false` surface in
  the **Next up** panel at the top of the dashboard.

Fill in `milestones` at the top of `plan.json` once exam and submission dates are
announced.

## Syllabus and reference texts

The topic lists and reference texts in `plan.json` are the official ones,
transcribed from `00 Course Information/Revised-Brochure-BStat(2016).pdf`. Where
an instructor hands out their own syllabus or reading list, add it to the
relevant track in `plan.json` and note the source in `syllabus_source`.

## Class schedule

Fill in `schedule.days` in `plan.json`:

```json
"schedule": {
  "note": "",
  "days": {
    "Monday": [{ "time": "10:15 – 11:45", "course": "Linear Statistical Models", "room": "G-24" }],
    "Tuesday": []
  }
}
```

## Publishing (GitHub Pages)

The repo is set up to deploy itself. `.github/workflows/pages.yml` runs
`build.py` on every push to `main` (and weekly, so the "this week" highlight
stays right) and publishes the result.

**Everything committed becomes public.** Do not commit scanned textbooks or
other copyrighted PDFs — `.gitignore` has a ready-made block to exclude
`Study Material/` PDFs; uncomment it if you keep books there. Files excluded
that way still show on the dashboard when you open `index.html` locally.

To publish after the first setup:

```bash
git add -A && git commit -m "Week N notes" && git push
```
