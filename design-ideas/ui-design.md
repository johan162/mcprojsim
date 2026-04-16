Version: 1.0.0

Date: 2026-04-16

Status: Design and Research Proposal

# mcprojsim Desktop UI — Design Document

**Scope:** A desktop GUI that lets a new user create, edit, validate, and simulate mcprojsim YAML project files without knowing the YAML format.

---

## 1. Goals

| Goal | Description |
|------|-------------|
| **Beginner-first** | A new user can create a basic project with 5 tasks and run a simulation in under 2 minutes, with zero knowledge of YAML. |
| **Full coverage** | Every field the YAML format supports is editable somewhere in the UI. Nothing is lost. |
| **Progressive disclosure** | Advanced options (cost, resources, sprint planning, calendars) are reachable but out of the way. |
| **Live YAML** | The generated YAML is always visible for users who want to learn or paste into a text editor. |
| **Run in-app** | The user can run a simulation and see results without leaving the application. |

---

## 2. Tech Stack Recommendation

### Chosen: **PySide6 (Qt for Python)**

```
Language:  Python 3.13+  (required by mcprojsim core)
Framework: PySide6 6.x   (official Qt binding by Qt Company, LGPL licence)
Packaging: PyInstaller   (single-folder app on Mac and Windows)
```

**Why PySide6:**

- Ships **native widgets** on both platforms: macOS uses Cocoa controls (aqua buttons, native menus); Windows uses the system theme.
- Already in the Python ecosystem; no separate language or compiler needed.
- Qt has a rich widget set that covers everything needed: form layouts, tree views, tab bars, drag handles, splitters, syntax-highlighted text areas.
- PyInstaller can produce a self-contained `.app` on macOS and an `.exe` on Windows, optionally installable via `brew` or a Windows installer (Inno Setup).
- The `mcprojsim` library can be imported directly — no subprocess calls needed to validate or simulate.

**Alternatives considered:**

| Stack | Pros | Cons |
|-------|------|------|
| Tkinter | Built into Python | Ugly, not native-looking |
| wxPython | Native on all platforms | Smaller community, dated API |
| Electron + React | Beautiful, web ecosystem | Heavy (200 MB), not native-looking |
| Tauri + React | Lighter than Electron | Requires Rust; two-language project |
| PyQt6 | Same as PySide6 | GPL licence; PySide6 is LGPL |

**Dependency additions (pyproject.toml optional group):**
```toml
[tool.poetry.group.ui]
optional = true

[tool.poetry.group.ui.dependencies]
PySide6 = ">=6.6"
```

> **Platform note**: PySide6 ships pre-built wheels for macOS (arm64 + x86_64) and Windows (x64). The app bundle produced by PyInstaller will be ~150–250 MB because it must include the Qt runtime and a bundled Python interpreter. This is comparable to other desktop apps and acceptable for a one-click install.

---

## 3. Design Principles

1. **One primary action per screen** — do not overwhelm with options.
2. **Smart defaults** — pre-fill start date to today, default estimate unit to `days`, default uncertainty level to `medium`.
3. **Inline validation** — show red borders and tooltips on bad values immediately; do not wait for a save action.
4. **YAML preview is read-write** — an advanced user can edit YAML directly and the form reflects the change.
5. **Section tabs are additive** — the user only needs the "Tasks" tab to get a working project; every other tab adds optional capability.
6. **No jargon until the user goes looking** — "Sprint Planning" is labelled "Sprint History (Optional)"; "Resources" is labelled "Team Members (Optional)"; "Constrained Scheduling" lives inside the Team Members tab.

---

## 4. Information Architecture

```
Main Window
├── Toolbar  [New] [Open] [Save] [Validate] [▶ Run Simulation]
├── Left Panel — Section Navigator
│   ├── 📋 Project Basics       ← always visible
│   ├── ✅ Tasks                ← always visible
│   ├── ⚠️  Risks               ← section (collapsed by default)
│   ├── 💰 Cost                 ← section (collapsed by default)
│   ├── 👥 Team Members         ← section (collapsed by default)
│   ├── 🗓️  Sprint History       ← section (collapsed by default)
│   └── ⚙️  Advanced            ← section (collapsed by default)
├── Right Panel — Context Form  (changes with section selection)
└── Bottom Panel (split view)
    ├── YAML Preview             (collapsible, syntax-highlighted)
    └── Simulation Results       (shown after ▶ Run)
```

The left panel acts as a single-column outline; clicking a section scrolls the right form to that section. On a wide display the right form is a flat single page; on a narrow display each section becomes a separate view.

---

## 5. Screen Sketches

### 5.1 — Main Window (Annotated)

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  mcprojsim                                                          [_ □ ×]  │
├──────────────────────────────────────────────────────────────────────────────┤
│  File  Edit  View  Help                                                       │
├──────────────────────────────────────────────────────────────────────────────┤
│ [+ New]  [Open]  [Save]  |  [✓ Validate]  [▶ Run Simulation]                 │
├────────────────┬─────────────────────────────────────────────────────────────┤
│  SECTIONS      │  PROJECT BASICS                                              │
│                │  ─────────────────────────────────────────────────────────  │
│ ▶ Project      │  Project Name *  [Customer Portal Redesign              ]   │
│   Basics       │  Start Date   *  [2026-05-01     ▼]                         │
│                │  Description     [                                       ]   │
│ ▶ Tasks (8)    │  Hours / Day     [8.0      ]   Working days per week [5  ]  │
│                │  ─────────────────────────────────────────────────────────  │
│ ▷ Risks (2)    │                                                              │
│                │  TASKS                                                       │
│ ▷ Cost         │  ─────────────────────────────────────────────────────────  │
│                │  [+ Add Task]                      [ ⇅ Reorder ]            │
│ ▷ Team Members │                                                              │
│                │  ┌──────┬──────────────────────────┬────────────┬────────┐ │
│ ▷ Sprint       │  │  ⠿   │ Task Name                │ Estimate   │ Deps   │ │
│   History      │  ├──────┼──────────────────────────┼────────────┼────────┤ │
│                │  │  ⠿   │ Database schema design   │ 3–5–10 d   │ —      │ │
│ ▷ Advanced     │  │  ⠿   │ API endpoint impl.       │ 5–8–15 d   │ #1     │ │
│                │  │  ⠿   │ Frontend components      │ 7–10–18 d  │ —      │ │
│                │  │  ⠿   │ Auth & Authorization     │ 4–6–12 d   │ #2     │ │
│                │  │  ⠿   │ Integration testing      │ 3–5–8 d    │ #2#3#4 │ │
│                │  │  ⠿   │ Performance optimization │ 2–4–7 d    │ #5     │ │
│                │  │  ⠿   │ Documentation            │ 2–3–5 d    │ #2#3   │ │
│                │  │  ⠿   │ Deployment & DevOps      │ 3–5–9 d    │ #6     │ │
│                │  └──────┴──────────────────────────┴────────────┴────────┘ │
│                │                                                              │
├────────────────┴─────────────────────────────────────────────────────────────┤
│  YAML PREVIEW  [▼ collapse]                    [Copy YAML]  [Open in Editor] │
│ ┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄ │
│  project:                                                                     │
│    name: "Customer Portal Redesign"                                           │
│    start_date: "2026-05-01"                                                   │
│    hours_per_day: 8.0                                                         │
│  tasks:                                                                       │
│    - id: "task_001"                ...                                        │
└──────────────────────────────────────────────────────────────────────────────┘
```

> **⠿** = drag handle for reordering rows.  
> The YAML preview pane at the bottom is resizable and is scrollable but defaults to ~6 lines visible.

---

### 5.2 — Task Editor (Flyout / Slide-in Panel)

Double-clicking a task row slides in a panel from the right. The panel has three tabs:

```
┌───────────────────────────────────────────────────────────┐
│  Edit Task: "API endpoint implementation"          [× Close]│
│  ─────────────────────────────────────────────────────────  │
│  [ Basics ] [ Uncertainty ] [ Risks ]                       │
│                                                             │
│  ┌─ Basics ───────────────────────────────────────────┐    │
│  │                                                     │    │
│  │  Task ID    [task_002                          ]   │    │
│  │  Name *     [API endpoint implementation       ]   │    │
│  │  Description[                                  ]   │    │
│  │                                                     │    │
│  │  Estimate Type  ○ Days (min/likely/max)             │    │
│  │                 ○ T-Shirt Size                      │    │
│  │                 ● Story Points                      │    │
│  │                                                     │    │
│  │  ┌─ Days Estimate ───────────────────────────────┐ │    │
│  │  │  Optimistic (min)  [5    ] days               │ │    │
│  │  │  Most Likely       [8    ] days    ──────────  │ │    │
│  │  │  Pessimistic (max) [15   ] days  ╔════════╗   │ │    │
│  │  │                    Unit  [days ▼]║ 5─8─15 ║   │ │    │
│  │  │                                  ╚════════╝   │ │    │
│  │  └───────────────────────────────────────────────┘ │    │
│  │                                                     │    │
│  │  Dependencies  (select tasks this task waits for)   │    │
│  │  ┌──────────────────────────────────────┐          │    │
│  │  │ [✓] Database schema design (#task_001)│          │    │
│  │  │ [ ] Frontend components (#task_003)   │          │    │
│  │  │ [ ] Auth & Auth (#task_004)           │          │    │
│  │  └──────────────────────────────────────┘          │    │
│  │                                                     │    │
│  │  Priority      [0     ]  (lower = higher priority)  │    │
│  │  Fixed Cost    [       ] USD  (optional)            │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
│                          [Cancel]  [Save Task]             │
└───────────────────────────────────────────────────────────┘
```

**Estimate input alternatives (shown when T-Shirt mode selected):**

```
│  ┌─ T-Shirt Estimate ─────────────────────────────────────┐
│  │                                                         │
│  │  Size   XS   S   M   L   XL  XXL                       │
│  │         ○    ○   ●   ○   ○   ○                         │
│  │                                                         │
│  │  Category  [story (default) ▼]                         │
│  │             story / bug / epic / business / initiative  │
│  └─────────────────────────────────────────────────────────┘
```

---

### 5.3 — Dependency Graph View

Accessible via a **[Graph View]** toggle button in the Tasks section toolbar. Replaces the table view with an interactive DAG diagram.

```
┌──────────────────────────────────────────────────────────┐
│  Tasks  [Table View]  [● Graph View]     [+ Add Task]    │
│  ─────────────────────────────────────────────────────── │
│                                                          │
│   ┌──────────────────┐                                   │
│   │ #1 DB Schema     │──────────────┐                    │
│   │ 3 – 5 – 10 d     │              │                    │
│   └──────────────────┘              ▼                    │
│                              ┌──────────────────┐        │
│   ┌──────────────────┐       │ #2 API Endpoints  │──┐   │
│   │ #3 Frontend      │──────▶│ 5 – 8 – 15 d     │  │   │
│   │ 7 – 10 – 18 d    │       └──────────────────┘  │   │
│   └──────────────────┘              │               │   │
│                                     ▼               │   │
│                              ┌──────────────────┐   │   │
│                         ┌───▶│ #4 Auth & Authz  │   │   │
│                         │    │ 4 – 6 – 12 d     │   │   │
│                         │    └──────────────────┘   │   │
│                         │           │               │   │
│                         │           ▼               ▼   │
│                         │    ┌──────────────────────┐   │
│                         │    │ #5 Integration Tests  │   │
│                         │    │ 3 – 5 – 8 d           │   │
│                         │    └──────────────────────┘   │
│                         │                               │
│  Drag arrow from one    │                               │
│  task to another to     │                               │
│  add a dependency.      └───────────────────────────────┘
└──────────────────────────────────────────────────────────┘
```

> Nodes are drag-repositionable. A new dependency is created by hovering the edge of a task node until an arrow cursor appears, then dragging to the target task.

---

### 5.4 — Uncertainty Tab (inside Task Editor)

```
│  [ Basics ] [● Uncertainty ] [ Risks ]
│
│  These factors adjust how uncertain the estimate is.
│  Leaving them all at "medium" means no adjustment.
│
│  ┌────────────────────────────────────────────────────────┐
│  │ Factor                      Level                      │
│  │ ──────────────────────────  ──────────────────────── │
│  │ Team Experience             [Very Low][Low][●Med][High][Very High]
│  │ Requirements Maturity       [Very Low][Low][Med][●High][Very High]
│  │ Technical Complexity        [Very Low][Low][●Med][High][Very High]
│  │ Team Distribution           [Colocated ●][Distributed]  │
│  │ Integration Complexity      [Very Low][Low][●Med][High][Very High]
│  └────────────────────────────────────────────────────────┘
│
│  Combined multiplier (estimated): ~1.05×
│  ℹ  "medium" on all factors = 1.00× (no adjustment)
```

The multiplier preview updates live as the user adjusts sliders, giving instant feedback.

---

### 5.5 — Risks Section

```
┌──────────────────────────────────────────────────────────────────────┐
│  RISKS                                                               │
│  ──────────────────────────────────────────────────────────────────  │
│  Project-wide risks (apply to entire project duration)               │
│                                                                      │
│  [+ Add Project Risk]                                                │
│  ┌────┬──────────────────────────────┬──────┬─────────────────────┐ │
│  │ ID │ Risk Name                    │ Prob │ Impact              │ │
│  ├────┼──────────────────────────────┼──────┼─────────────────────┤ │
│  │ R1 │ Key developer leaves         │ 15%  │ +20% duration       │ │
│  │ R2 │ Requirements change          │ 30%  │ +10 days (absolute) │ │
│  └────┴──────────────────────────────┴──────┴─────────────────────┘ │
│                                                                      │
│  ℹ  Task-level risks are added in the task editor (Risks tab).      │
└──────────────────────────────────────────────────────────────────────┘
```

**Risk Editor (inline expansion or small dialog):**

```
  ┌─ Add / Edit Risk ────────────────────────────────────────────┐
  │  Name *        [Key developer leaves                      ]  │
  │  Probability   [  15  ] %  ← type or use ← → keys           │
  │                ─────────────────────────────────────────     │
  │  Impact Type   ○ Hours (fixed)                               │
  │                ● Percentage  [20] %  of project duration     │
  │                ○ Absolute    [  ] days / hours               │
  │                                                              │
  │  Cost Impact   [ optional $ amount ]                        │
  │  Description   [                                          ]  │
  │                                                              │
  │                              [Cancel]  [Save Risk]          │
  └──────────────────────────────────────────────────────────────┘
```

---

### 5.6 — Cost Section

```
┌──────────────────────────────────────────────────────────────────────┐
│  COST                                                                │
│  ──────────────────────────────────────────────────────────────────  │
│  Enable cost tracking  [✓]                                           │
│                                                                      │
│  Currency           [USD ▼]                                          │
│  Default Hourly Rate  [$  125.00 / hour]  ← applied to all tasks    │
│  Overhead Rate        [  15 ] %           ← on top of hourly rate   │
│  Project Fixed Cost   [$       ]          ← one-time cost           │
│                                                                      │
│  ──────────────────────────────────────────────────────────────────  │
│  Budget Analysis (optional)                                          │
│  Target Budget     [$         ]           ← shows probability of    │
│                                            staying within budget     │
│                                                                      │
│  ┄ Secondary Currencies (Advanced) ──────────────────────────────── │
│  [+ Add Currency]                                                    │
│  ┌──────────────┬───────────────┬──────────────────┐                │
│  │ Currency     │ Rate to USD   │ FX Overhead      │                │
│  └──────────────┴───────────────┴──────────────────┘                │
│                                                                      │
│  ℹ  Per-task and per-resource hourly rates are set in the           │
│     task editor and team member settings respectively.               │
└──────────────────────────────────────────────────────────────────────┘
```

---

### 5.7 — Team Members Section (Constrained Scheduling)

```
┌──────────────────────────────────────────────────────────────────────┐
│  TEAM MEMBERS  (Optional — enables resource-constrained scheduling)  │
│  ──────────────────────────────────────────────────────────────────  │
│  [+ Add Team Member]                                                 │
│                                                                      │
│  ┌────────────────┬──────────────┬──────────────┬───────────────┐   │
│  │ Name           │ Experience   │ Availability │ Hourly Rate   │   │
│  ├────────────────┼──────────────┼──────────────┼───────────────┤   │
│  │ dev-senior     │ ★★★☆☆ (3)   │ 100%         │ $140 / hr     │   │
│  │ dev-junior     │ ★☆☆☆☆ (1)   │ 80%          │ $85 / hr      │   │
│  └────────────────┴──────────────┴──────────────┴───────────────┘   │
│                                                                      │
│  ┄ Scheduling Mode ───────────────────────────────────────────────  │
│  ○ Dependency only (ignore team member assignments)                  │
│  ● Resource-constrained (respect team member assignments)            │
│                                                                      │
│  Two-pass criticality ranking  [✓]   Improves schedule quality       │
│  Pass-1 iterations  [ 1000 ]                                         │
│                                                                      │
│  ┄ Calendars (Advanced) ─────────────────────────────────────────── │
│  [+ Add Calendar]  (define working hours, holidays per team member)  │
└──────────────────────────────────────────────────────────────────────┘
```

**Team Member Editor (dialog):**

```
  ┌─ Edit Team Member: dev-senior ─────────────────────────────────┐
  │  Name *            [dev-senior                              ]  │
  │  Experience Level  [★★★☆☆] 1 2 ●3 4 5                        │
  │  Productivity      [1.0  ]  (1.0 = baseline; 1.2 = 20% faster)│
  │  Availability      [100  ] %                                   │
  │  Calendar          [default ▼]                                 │
  │  Hourly Rate       [$  140.00]                                 │
  │                                                                │
  │  ┄ Absence ──────────────────────────────────────────────── │
  │  Sickness probability  [ 5 ] % per week                       │
  │  Planned absence dates  [+ Add date range]                    │
  │  ┌────────────────────┬──────────────────┐                   │
  │  │ From               │ To               │                   │
  │  │ 2026-08-01         │ 2026-08-14       │ [×]              │
  │  └────────────────────┴──────────────────┘                   │
  │                                [Cancel]  [Save]              │
  └────────────────────────────────────────────────────────────────┘
```

---

### 5.8 — Sprint History Section

```
┌──────────────────────────────────────────────────────────────────────┐
│  SPRINT HISTORY  (Optional — enables sprint-based planning)          │
│  ──────────────────────────────────────────────────────────────────  │
│  Enable sprint planning  [✓]                                         │
│                                                                      │
│  Sprint Length    [  2  ] weeks                                      │
│  Capacity Mode    ● Story Points   ○ Hours                           │
│  Velocity Model   ● Empirical (use history as-is)                    │
│                   ○ Neg-Binomial  (statistical fit)                  │
│                                                                      │
│  ──────────────────────────────────────────────────────────────────  │
│  Sprint History   [+ Add Sprint]                                     │
│                                                                      │
│  ┌──────────┬──────────────────┬──────────────────┬─────────────┐   │
│  │ Sprint   │ Completed Points │ Spillover Points │ Team Size   │   │
│  ├──────────┼──────────────────┼──────────────────┼─────────────┤   │
│  │ SPR-001  │  10              │  1               │             │   │
│  │ SPR-002  │   9              │  2               │             │   │
│  │ SPR-003  │  11              │  0               │             │   │
│  └──────────┴──────────────────┴──────────────────┴─────────────┘   │
│                                                                      │
│  ℹ  At least 2 usable sprint history rows are required.             │
│     Tasks must use story_points estimates when this is enabled.      │
└──────────────────────────────────────────────────────────────────────┘
```

---

### 5.9 — Advanced Section

```
┌──────────────────────────────────────────────────────────────────────┐
│  ADVANCED                                                            │
│  ──────────────────────────────────────────────────────────────────  │
│                                                                      │
│  ┄ Distribution ─────────────────────────────────────────────────── │
│  Task distribution     ● Triangular   ○ Log-normal                  │
│  Default T-shirt cat.  [story ▼]                                     │
│                                                                      │
│  ┄ Confidence Levels ────────────────────────────────────────────── │
│  Percentiles shown in output:                                        │
│  [✓] P50  [✓] P75  [✓] P80  [✓] P85  [✓] P90  [✓] P95  [✓] P99    │
│  [ ] P10  [ ] P25  [+ custom]                                        │
│                                                                      │
│  ┄ Probability Thresholds (thermometer chart colours) ─────────────  │
│  Red below    [ 50 ] %   Green above   [ 90 ] %                      │
│                                                                      │
│  ┄ Project-level Uncertainty Factors ───────────────────────────── │
│  (override defaults for all tasks unless overridden per task)        │
│  Team Experience          [medium ▼]                                 │
│  Requirements Maturity    [medium ▼]                                 │
│  Technical Complexity     [medium ▼]                                 │
│  Team Distribution        [colocated ▼]                              │
│  Integration Complexity   [medium ▼]                                 │
└──────────────────────────────────────────────────────────────────────┘
```

---

### 5.10 — Run Simulation Panel

Triggered by **▶ Run Simulation** in the toolbar. A sheet / modal appears:

```
┌──────────────────────────────────────────────────────────────┐
│  Run Simulation                                    [×]        │
│  ──────────────────────────────────────────────────────────  │
│  Iterations     [10000     ]                                 │
│  Random Seed    [          ]  (leave blank for random)       │
│  Output Format  [ ] JSON  [ ] CSV  [✓] HTML report           │
│  Output Folder  [~/Desktop/results              ] [Browse…]  │
│                                                              │
│  ─────────────────────────────────────────────────────────  │
│  ● Validate project first  (recommended)                     │
│                                                              │
│                         [Cancel]  [▶ Run]                   │
└──────────────────────────────────────────────────────────────┘
```

After pressing **▶ Run**, the bottom results pane expands and shows live output:

```
┌──────────────────────────────────────────────────────────────────────┐
│  SIMULATION RESULTS                                 [Save] [▲ Hide] │
│  ──────────────────────────────────────────────────────────────────  │
│  Progress: ████████████████████░░░░  73%  (7,312 / 10,000)         │
│                                                                      │
│  ┌──── Calendar Time ────────────────────────────────────────────┐  │
│  │  Mean:    578 h  (73 days)                                    │  │
│  │  Median:  571 h  (72 days)                                    │  │
│  │  P80:     642 h  (81 days)  ← 2026-07-30                      │  │
│  │  P90:     682 h  (86 days)  ← 2026-08-06                      │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  ┌──── Critical Path ────────────────────────────────────────────┐  │
│  │  #1 → #2 → #4 → #5 → #6 → #8  (100%)                        │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  [Open HTML Report]  [Show Full Output ▼]                           │
└──────────────────────────────────────────────────────────────────────┘
```

---

### 5.11 — New Project Wizard (First-Run Experience)

On first launch, or after clicking **[+ New]**, a minimal 3-step wizard appears:

```
Step 1 of 3: Project Basics
───────────────────────────────────────────────
 Project Name *    [My new project           ]
 Start Date   *    [2026-05-01               ]
 Currency          [USD ▼]   (optional)
 Hourly Rate       [         ]  $/hr  (optional)

                            [Skip]  [Next →]
```

```
Step 2 of 3: Add your first task
───────────────────────────────────────────────
 Task Name *       [                         ]
 How long might it take?
   Optimistic  [   ] days
   Most Likely [   ] days
   Pessimistic [   ] days

 ✓ You can add more tasks and set dependencies after the wizard.

                   [← Back]  [Add Task]  [Finish →]
```

```
Step 3 of 3: Ready to simulate
───────────────────────────────────────────────
 ✓  "My new project" has 1 task.

 You can add more tasks and then click ▶ Run Simulation,
 or save the project file and come back later.

                   [← Back]  [Open Project]
```

---

## 6. Progressive Disclosure Strategy

| User Type | What They See by Default | How to Reach More |
|-----------|--------------------------|-------------------|
| Total beginner | Wizard → Name + Start Date + 1 task | Click "Add Task", fill days |
| First-time planner | Task list table | Double-click row → Uncertainty / Risks tabs |
| Project manager | All main sections | Expand ▷ Cost, ▷ Team Members |
| Advanced user | All sections + YAML preview | Edit YAML directly; changes sync to form |
| Power user | YAML preview + CLI | Export YAML, run `mcprojsim simulate` in terminal |

Sections hidden by default (collapsed, shown as `▷`):
- Risks
- Cost
- Team Members
- Sprint History
- Advanced

Sections visible by default (shown as `▶`, expanded):
- Project Basics
- Tasks

---

## 7. YAML Sync Architecture

```
Form Fields  ──(on change)──▶  in-memory Project model
                                       │
                               (model → YAML serializer)
                                       │
                                       ▼
                               YAML Preview Pane
                               (syntax-highlighted,
                                read-write)

YAML Pane edit ──(on change)──▶  YAML parser
                                       │
                               (parsed model → form fields)
                                       │
                                       ▼
                               Form Updates
```

- Form changes immediately regenerate YAML; YAML pane is updated within ~50ms.
- YAML edits trigger a parse; if valid, the form fields update.
- If YAML is invalid, a warning badge appears on the YAML pane but the form does not clear.
- An undo/redo stack covers both form and YAML changes.

### 7.1 — mcprojsim API Integration Reference

The UI interacts with `mcprojsim` entirely through its Python API — no subprocess calls needed. The integration pattern is:

```python
from pathlib import Path
from mcprojsim.config import Config
from mcprojsim.parsers.yaml_parser import YAMLParser
from mcprojsim.simulation.engine import SimulationEngine
from mcprojsim.exporters import JSONExporter, CSVExporter, HTMLExporter

# 1. Load configuration (from file or built-in defaults)
config = Config.load_from_file("config.yaml")    # merges with defaults
config = Config.get_default()                      # pure defaults
config = Config.model_validate({"simulation": {"default_iterations": 5000}})  # from dict

# 2. Build project model (validation is automatic on construction)
parser = YAMLParser()
project = parser.parse_file("project.yaml")        # from file
project = parser.parse_dict(data_dict)              # from in-memory dict
# Raises ValueError with line/column context on invalid input.

# 3. Run simulation
engine = SimulationEngine(
    iterations=10000,
    random_seed=42,
    config=config,
    show_progress=False,    # disable stdout progress for GUI
    two_pass=True,
    pass1_iterations=1500,
)
results = engine.run(project)  # returns SimulationResults

# 4. Export results
JSONExporter.export(results, Path("out.json"), config=config, project=project)
CSVExporter.export(results, Path("out.csv"), config=config, project=project)
HTMLExporter.export(results, Path("out.html"), config=config, project=project)
```

**Key API facts for implementers:**

| Concern | Current API | Notes |
|---------|------------|-------|
| Config from dict | `Config.model_validate(dict)` | Merging with defaults happens inside `load_from_file`; for dict-based construction the UI must merge manually or use `load_from_file` with a temp file |
| Validation | Automatic on `YAMLParser.parse_dict()` / `parse_file()` | Raises `ValueError`; no separate validate function needed |
| Project from dict | `YAMLParser().parse_dict(data)` | Direct dict → `Project` model |
| TOML support | `TOMLParser().parse_file(path)` / `parse_dict(data)` | Same interface as YAML |
| Exporters | Static `export()` methods on `JSONExporter`, `CSVExporter`, `HTMLExporter` | Write to filesystem; return `None` |
| Reproducibility | `SimulationEngine(random_seed=N)` | Deterministic when seed is set |
| Two-pass scheduling | `SimulationEngine(two_pass=True, pass1_iterations=N)` | Only relevant when `resources` are defined |

---

## 8. Validation UX

- Red underline + tooltip on any invalid field (e.g., `min > expected`, unknown task ID in dependency).
- The **[✓ Validate]** toolbar button runs the full `mcprojsim validate` path and opens an inline problem list.
- The **[▶ Run Simulation]** button auto-runs validate first; if there are errors, simulation is blocked with a message listing them.

**Implementation note — inline vs full validation:**

The UI should implement two validation tiers:

1. **Inline (local)** — implemented in the UI layer. Check field-level constraints immediately (e.g., `low < expected < high`, probability between 0 and 1, non-empty names). These are fast and do not require calling the engine.
2. **Full (structural)** — build the dict from form state, call `YAMLParser().parse_dict(data)`, and catch `ValueError`. This validates cross-field constraints (circular dependencies, missing task IDs, symbolic estimate consistency). Run this on [✓ Validate] click and before simulation.

---

## 9. File Handling

- Saves and opens `.yaml` files in the standard `mcprojsim` format.
- Also accepts `.toml` files (read via `TOMLParser`).
- Recent files list in File menu.
- Auto-save to a temp file with recovery on crash.

### 9.1 — Import Tasks from CSV / External Sources

The UI should support **importing a task list from CSV** via `File → Import Tasks…`. This covers a common workflow where a project manager has an existing spreadsheet of work items.

**Expected CSV columns** (header row required, order-insensitive):

| Column | Required | Maps to |
|--------|----------|--------|
| `name` | Yes | `task.name` |
| `low` | Yes (if no `t_shirt_size`) | `estimate.low` |
| `expected` | Yes (if no `t_shirt_size`) | `estimate.expected` |
| `high` | Yes (if no `t_shirt_size`) | `estimate.high` |
| `unit` | No | `estimate.unit` (default: `days`) |
| `t_shirt_size` | No | `estimate.t_shirt_size` |
| `story_points` | No | `estimate.story_points` |
| `dependencies` | No | Comma-separated task names or IDs |
| `description` | No | `task.description` |

Behavior:
- IDs are auto-generated (`task_001`, `task_002`, …).
- If `dependencies` references task names, they are resolved to the generated IDs.
- After import, the user can edit tasks normally in the form.
- Import appends to existing tasks (with a confirmation dialog) or replaces all tasks.

This is a UI-layer feature; no engine change is needed since the UI constructs the project dict from the imported data.

---

## 10. Packaging & Distribution

### 10.1 — Distribution Channels

| Channel | Audience | Artefact | Tool |
|---------|----------|----------|------|
| **macOS installer (primary)** | Non-technical end-user | Signed, notarized `.dmg` containing `mcprojsim.app` | PyInstaller + `create-dmg` |
| **Windows installer** | Non-technical end-user | Signed `.exe` installer | PyInstaller + Inno Setup |
| **pip install** | Developer / power user | `pip install mcprojsim[ui]` (PySide6 added, no bundled runtime) | standard pip |

### 10.2 — macOS One-Click Install Details

For the target user (no Python, no terminal):

1. **PyInstaller** bundles the Python 3.13 interpreter, all dependencies (numpy, scipy, matplotlib, PySide6/Qt), and the `mcprojsim` library into a single `.app` bundle.
2. **Code signing** with an Apple Developer ID certificate (`codesign --deep --options runtime`).
3. **Notarization** via `notarytool` so Gatekeeper allows the app to run without security warnings.
4. **Staple** the notarization ticket to the `.dmg`.
5. User downloads `.dmg`, drags app to Applications, double-clicks. No terminal, no Python install, no Gatekeeper warning.

**Expected app size**: ~200–300 MB (Qt runtime ~120 MB, Python + numpy/scipy/matplotlib ~80 MB, mcprojsim ~2 MB). This is comparable to apps like VS Code or Slack.

### 10.3 — Windows One-Click Install Details

1. **PyInstaller** produces a directory bundle or single-file `.exe`.
2. **Inno Setup** wraps it in a standard Windows installer with Start Menu shortcuts.
3. **Code signing** with an Authenticode certificate (EV cert recommended to avoid SmartScreen warnings).
4. User downloads `.exe`, runs installer, launches from Start Menu.

### 10.4 — CI/CD Release Pipeline

Both platform builds should be automated in GitHub Actions:

```yaml
# Simplified workflow sketch
jobs:
  build-macos:
    runs-on: macos-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.13' }
      - run: pip install pyinstaller pyside6 .
      - run: pyinstaller mcprojsim-ui.spec
      - run: codesign --deep --options runtime dist/mcprojsim.app
      - run: xcrun notarytool submit dist/mcprojsim.dmg --wait
      - run: xcrun stapler staple dist/mcprojsim.dmg
      - uses: actions/upload-artifact@v4

  build-windows:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.13' }
      - run: pip install pyinstaller pyside6 .
      - run: pyinstaller mcprojsim-ui.spec
      - run: iscc mcprojsim-installer.iss
      - uses: actions/upload-artifact@v4
```

### 10.5 — Developer Install (pip)

For users with Python already installed:
```bash
pip install mcprojsim[ui]    # installs PySide6 + mcprojsim
mcprojsim-ui                  # launches the app
```

Entry point in `pyproject.toml`:
```toml
[tool.poetry.scripts]
mcprojsim-ui = "mcprojsim.ui.main:main"
```

---

## 11. Configuration Editor

The UI should allow creating and editing custom `mcprojsim` configuration files — not just project files. A **Preferences** or **Settings** dialog (accessible via the app menu or a gear icon) exposes the config sections:

```
┌──────────────────────────────────────────────────────────────────┐
│  Preferences                                           [×]       │
│  ────────────────────────────────────────────────────────────── │
│  [Simulation] [T-Shirt Sizes] [Story Points] [Uncertainty] [Output] │
│                                                                  │
│  ┌─ Simulation ───────────────────────────────────────────────┐ │
│  │  Default Iterations  [10000   ]                            │ │
│  │  Max Stored Paths    [20      ]                            │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ┌─ T-Shirt Sizes (story category) ──────────────────────────┐ │
│  │  Size │  Low  │ Expected │  High  │                       │ │
│  │  XS   │    3  │      5   │    15  │                       │ │
│  │  S    │    5  │     16   │    40  │                       │ │
│  │  M    │   40  │     60   │   120  │                       │ │
│  │  …    │       │          │        │                       │ │
│  │  Default Category  [story ▼]                              │ │
│  │  Unit              [hours ▼]                              │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  Config File  [~/mcprojsim-config.yaml]  [Browse…] [Save] [Reset]│
└──────────────────────────────────────────────────────────────────┘
```

**Implementation**: The UI builds a dict from the form, calls `Config.model_validate(merged_dict)` for validation, and serializes to YAML on save. Config overrides are loaded at startup and passed to `SimulationEngine(config=...)` on every run.

---

## 12. Implementation Phases

| Phase | Scope |
|-------|-------|
| **0 — Engine prep** | Add `progress_callback` parameter to `SimulationEngine` (see §A.1). This is a prerequisite for a responsive UI progress bar. |
| **1 — MVP** | Project Basics form, Task table + task editor (basics tab only), YAML preview, Run dialog with progress bar, Results pane (summary only), CSV task import |
| **2 — Core Features** | Dependency graph view, Uncertainty tab in task editor, Risks section, Cost section, Configuration editor |
| **3 — Advanced** | Team Members section (constrained scheduling), Sprint History section, Advanced section, calendar editor |
| **4 — Polish** | New Project Wizard, YAML ↔ Form two-way sync, HTML report viewer embedded in app, undo/redo |
| **5 — Distribution** | PyInstaller spec, macOS code signing + notarization, Windows installer, GitHub Actions release pipeline |

---

## Appendix A — Developer Review: API Gaps & Implementation Notes

This section documents gaps between the current `mcprojsim` API and what the UI requires, plus implementation guidance for non-obvious concerns.

### A.1 — Progress Callback (Required Engine Change)

**Current state**: `SimulationEngine` writes progress to `sys.stdout` via a hardcoded `self.progress_stream: TextIO = sys.stdout`. There is no callback mechanism. The `show_progress=False` flag suppresses output entirely.

**Problem for UI**: A Qt progress bar needs percentage updates delivered as callbacks or signals, not written to stdout. Redirecting stdout is fragile and not thread-safe.

**Required change** (small, non-breaking):

```python
# In SimulationEngine.__init__:
def __init__(
    self,
    ...,
    progress_callback: Optional[Callable[[int, int], None]] = None,
):
    self._progress_callback = progress_callback

# In SimulationEngine._report_progress:
def _report_progress(self, progress: int, completed_iterations: int) -> None:
    if self._progress_callback is not None:
        self._progress_callback(completed_iterations, self.iterations)
        return
    # ... existing stdout logic unchanged ...
```

UI usage:
```python
def on_progress(completed: int, total: int) -> None:
    pct = int(100 * completed / total)
    progress_signal.emit(pct)  # Qt signal to update progress bar

engine = SimulationEngine(
    iterations=10000,
    show_progress=False,
    progress_callback=on_progress,
)
```

This is backward-compatible: when `progress_callback` is `None` (default), behavior is identical to today.

### A.2 — Threading Model

Simulation must run in a **background thread** (or `QThread`) because `engine.run()` is synchronous and blocks until all iterations complete. The UI main thread must remain responsive for progress bar updates and cancel requests.

Recommended pattern:
```python
class SimulationWorker(QThread):
    progress = Signal(int)     # percentage
    finished = Signal(object)  # SimulationResults
    error = Signal(str)        # error message

    def run(self):
        try:
            engine = SimulationEngine(
                show_progress=False,
                progress_callback=lambda c, t: self.progress.emit(int(100*c/t)),
                ...
            )
            results = engine.run(self.project)
            self.finished.emit(results)
        except Exception as e:
            self.error.emit(str(e))
```

### A.3 — Cancellation Support (Nice-to-Have Engine Change)

Currently there is no way to cancel a running simulation. For the UI, a `cancel()` method or a check-flag in the iteration loop would allow the user to abort long runs.

**Suggested approach**: Add `self._cancelled = False` and `def cancel(self): self._cancelled = True` to the engine, with a check inside the main iteration loop that raises `SimulationCancelled` if set.

### A.4 — Large Project Scalability

The task table (§5.1) uses a `QTableWidget`/`QTableView`. For projects with 50–200 tasks:
- Use `QAbstractTableModel` (model/view pattern), not `QTableWidget`, for performance.
- The dependency graph view (§5.3) should use `QGraphicsScene` with layout computed by a graph library (e.g., `graphviz` via `pygraphviz`, or a simple Sugiyama algorithm). For >50 nodes, auto-layout is essential; manual positioning is not viable.
- Dependency checkboxes in the task editor (§5.2) should be replaced with a **searchable/filterable list** when task count exceeds ~20.

### A.5 — YAML Round-Trip Fidelity

The bidirectional YAML sync (§7) requires careful handling:

- **Form → YAML**: Straightforward. Build a dict from form state, serialize with `yaml.dump()`. Use `default_flow_style=False` for readable output.
- **YAML → Form**: Call `YAMLParser().parse_dict(yaml.safe_load(text))`. If it raises `ValueError`, show a warning badge but do **not** clear the form — let the user fix the YAML.
- **Preserving comments and ordering**: `yaml.safe_load` + `yaml.dump` will **not** preserve comments or key order from a hand-edited YAML file. If round-trip fidelity matters, use `ruamel.yaml` (YAML 1.2, comment-preserving) instead of `pyyaml`. This is a dependency trade-off to decide in Phase 4.

### A.6 — Config Model Construction

`Config.load_from_file()` merges user YAML with built-in defaults internally. But `Config.model_validate(dict)` does **not** merge — it constructs from the dict as-is. For the configuration editor (§11), the UI should:

1. Start from `Config.get_default().model_dump()` to get the full default dict.
2. Apply user edits on top.
3. Call `Config.model_validate(merged_dict)` to validate.
4. Serialize the merged dict to YAML for saving.

### A.7 — Native Look and Feel

PySide6/Qt renders native widgets on both platforms by default:
- **macOS**: Cocoa-style buttons, menus, scrollbars, file dialogs. Supports dark mode automatically.
- **Windows**: Win32 themed controls, native file dialogs, system tray integration.
- The app will look and feel native without custom styling. Avoid overriding the default Qt style unless a specific brand appearance is desired.
- macOS-specific: Set the `CFBundleName`, `CFBundleIdentifier`, and `LSMinimumSystemVersion` in the PyInstaller spec's `Info.plist` for proper Finder integration.

### A.8 — Sprint History: External CSV/JSON Import

The sprint planning model already supports external history files (CSV or JSON, referenced via `sprint_planning.history`). The UI sprint history table (§5.8) should offer an **[Import from CSV]** button that reads a CSV file and populates the sprint history rows. This is distinct from the task CSV import (§9.1).

### A.9 — What Is NOT Covered by This Design

For completeness, features **not** in scope for the desktop UI:

- MCP server management (this is an API/infrastructure concern, not a GUI task)
- Multi-user collaboration or project sharing
- Cloud storage integration
- Custom plugin/extension system
- Printing (users can print the HTML report from a browser)

---

## 13. Work Breakdown — Implementation Plan

This chapter breaks every feature from §1–§12 and Appendix A into concrete, ordered work items that a senior developer can follow sequentially. Each item specifies **what** to build, **where** it lives, and **how to verify** it works.

Convention: work items are numbered `P1-NN` (Phase 1) and `P2-NN` (Phase 2). Dependencies on earlier items are noted in parentheses.

---

### Phase 1 — MVP

**Goal:** A user can launch the app, create a project with tasks (triangular day estimates), see the generated YAML, run a simulation with a live progress bar, and view summary results. File open/save works. No advanced features yet.

---

#### P1-01 — Engine: Add `progress_callback` Parameter
**STATUS:** DONE. This is now implemented.

> Prerequisite for everything that follows. Ref: §A.1.

1. In `src/mcprojsim/simulation/engine.py`, add an optional `progress_callback: Optional[Callable[[int, int], None]] = None` parameter to `SimulationEngine.__init__()`.
2. Store it as `self._progress_callback`.
3. In `_report_progress()`, if `self._progress_callback is not None`, call `self._progress_callback(completed_iterations, self.iterations)` and return early — skip the existing `stdout` logic.
4. When `progress_callback` is `None` (default), behaviour is identical to today.
5. Add a unit test: create an engine with a mock callback, run a tiny project (3 tasks, 50 iterations), assert the callback was invoked at least once and the final call has `completed == iterations`.
6. Run the full test suite to confirm nothing regressed.

**Verify:** `poetry run pytest tests/test_simulation.py -k progress --no-cov -v` passes. Existing tests still pass.

---

#### P1-02 — Engine: Add Cancellation Flag
**STATUS:** DONE. This is now implemented.

> Ref: §A.3. Small change, best done alongside P1-01.

1. Add `self._cancelled: bool = False` in `SimulationEngine.__init__()`.
2. Add a public method `def cancel(self) -> None: self._cancelled = True`.
3. Inside the main iteration loop (the `for i in range(...)` in `run()`), check `if self._cancelled: raise SimulationCancelled()` at the top of each iteration.
4. Define `SimulationCancelled(Exception)` in `simulation/engine.py` (or a shared `exceptions.py` if one exists).
5. Add a unit test: start a simulation of 10 000 iterations, call `cancel()` from a thread after a short delay, assert `SimulationCancelled` is raised and the loop stopped early.

**Verify:** `poetry run pytest tests/test_simulation.py -k cancel --no-cov -v` passes.

---

#### P1-03 — Project Scaffolding: Directory Structure & Dependencies

1. Create the UI source directory: `src/mcprojsim/ui/`.
2. Create `src/mcprojsim/ui/__init__.py` (empty).
3. Create `src/mcprojsim/ui/main.py` with a minimal `main()` function that launches a `QApplication`, creates a `QMainWindow`, sets the window title to `"mcprojsim"`, and calls `app.exec()`.
4. In `pyproject.toml`:
   - Add the `[tool.poetry.group.ui]` optional group with `PySide6 = ">=6.6"` (ref: §2).
   - Add the entry point: `mcprojsim-ui = "mcprojsim.ui.main:main"` under `[tool.poetry.scripts]`.
5. Run `poetry install --with ui` to verify the dependency resolves and installs.
6. Run `mcprojsim-ui` from command line — an empty window appears with the correct title.

**Verify:** The app launches and closes cleanly. No import errors.

---

#### P1-04 — Main Window Shell: Menu Bar, Toolbar, Panels

> Ref: §4, §5.1.

1. Create `src/mcprojsim/ui/main_window.py` with class `MainWindow(QMainWindow)`.
2. **Menu bar** — `File` (New, Open, Save, Save As, Recent Files ▸, Quit), `Edit` (Undo, Redo), `View` (Toggle YAML Preview), `Help` (About).
   - Wire `Quit` to `QApplication.quit()`. Other actions stay as no-ops (stubs) for now.
3. **Toolbar** — Add `QToolBar` with icon-buttons: `[+ New]`, `[Open]`, `[Save]`, separator, `[✓ Validate]`, `[▶ Run Simulation]`. All stubbed.
4. **Central layout** — Use a `QSplitter` (horizontal):
   - Left: `QListWidget` for section navigator (items: "Project Basics", "Tasks"). Clicking an item will scroll the right panel (wired in P1-05).
   - Right: `QScrollArea` containing a `QVBoxLayout` that will host section widgets.
5. **Bottom panel** — A second `QSplitter` (vertical) splitting the central area from a bottom panel with two tabs: "YAML Preview" (a `QPlainTextEdit`, read-only for now) and "Simulation Results" (an empty `QWidget` placeholder).
6. Set minimum window size to 1024 × 700. Restore window geometry from `QSettings` on launch, save on close.
7. Update `main.py` to instantiate `MainWindow`.

**Verify:** App launches showing the skeleton: toolbar, section list on the left, empty form area on the right, YAML pane at the bottom. Resize and close — geometry is remembered next launch.

---

#### P1-05 — Project Basics Form

> Ref: §5.1 top section.

1. Create `src/mcprojsim/ui/widgets/project_basics.py` with class `ProjectBasicsWidget(QWidget)`.
2. Fields (use `QFormLayout`):
   - **Project Name** — `QLineEdit`, required (non-empty).
   - **Start Date** — `QDateEdit` with calendar popup. Default: today.
   - **Description** — `QTextEdit` (3 lines high), optional.
   - **Hours / Day** — `QDoubleSpinBox`, range 0.1–24.0, default 8.0.
   - **Working Days per Week** — `QSpinBox`, range 1–7, default 5.
3. Each field emits `dataChanged` signal (custom `Signal()`) whenever the user edits anything.
4. Provide `def to_dict(self) -> dict` that returns a dict matching the `project:` section of a YAML file.
5. Provide `def from_dict(self, data: dict) -> None` that populates the form from a loaded project dict.
6. Add the widget to `MainWindow`'s right-panel layout as the first section.
7. Wire the "Project Basics" entry in the section navigator to scroll to this widget.

**Verify:** Edit every field. Call `to_dict()` and confirm the dict is correct. Call `from_dict()` with sample data and confirm the form populates.

---

#### P1-06 — In-Memory Project Model & YAML Generation (Form → YAML)

> Ref: §7 (one-way only in Phase 1).

1. Create `src/mcprojsim/ui/project_model.py` with class `UIProjectModel(QObject)`.
   - Holds the complete project state as a Python dict (mirrors the YAML structure).
   - Exposes `project_changed = Signal()`.
   - Methods: `set_project_basics(dict)`, `set_tasks(list[dict])`, `to_dict() -> dict`, `to_yaml() -> str`.
2. `to_yaml()` calls `yaml.dump(self.to_dict(), default_flow_style=False, sort_keys=False)`.
3. In `MainWindow`, instantiate `UIProjectModel`. Connect `ProjectBasicsWidget.dataChanged` → update model → regenerate YAML → display in the YAML preview pane.
4. YAML preview pane becomes live: whenever the model changes, the YAML text is regenerated and displayed (< 50 ms for small projects).

**Verify:** Edit the project name → the YAML pane updates immediately with the new name.

---

#### P1-07 — Task Table

> Ref: §5.1 task table.

1. Create `src/mcprojsim/ui/widgets/task_table.py`.
2. Use `QTableView` backed by a custom `TaskTableModel(QAbstractTableModel)` — ref: §A.4 on scalability.
3. Columns: drag handle (icon), Task Name, Estimate (display as `low–expected–high unit`), Dependencies (display as comma-separated IDs or "—").
4. **[+ Add Task]** button above the table — inserts a new row with auto-generated ID (`task_001`, `task_002`, etc.), empty name, and placeholder estimate.
5. **Delete** — right-click context menu → "Delete Task" with confirmation. Also allow `Delete` key.
6. **Reorder** — drag handle column enables row drag-and-drop via `Qt::MoveAction`. Reorder changes the order in the model, not the IDs.
7. **Double-click** a row → opens the task editor (P1-08).
8. Connect model changes to `UIProjectModel.set_tasks(...)` → YAML regenerates.
9. Wire the section navigator "Tasks (N)" entry to scroll to this widget. The navigator text updates with the task count.

**Verify:** Add 5 tasks, reorder them via drag, delete one. YAML preview reflects each change. Double-click opens the editor (stubbed in P1-08).

---

#### P1-08 — Task Editor Panel (Basics Tab Only)

> Ref: §5.2, Basics tab only. Uncertainty and Risks tabs are Phase 2. Only triangular day estimates for now.

1. Create `src/mcprojsim/ui/widgets/task_editor.py` with class `TaskEditorPanel(QWidget)`.
2. The panel slides in from the right (or overlays the form area) when a task row is double-clicked. Has a `[× Close]` button.
3. Tab bar with three tabs: **Basics** (enabled), **Uncertainty** (disabled/greyed, "Coming soon"), **Risks** (disabled/greyed, "Coming soon").
4. **Basics tab** fields:
   - **Task ID** — `QLineEdit`, read-only (auto-generated).
   - **Name** — `QLineEdit`, required.
   - **Description** — `QTextEdit`, optional.
   - **Estimate Type** — radio buttons: `Days (min / likely / max)` (selected by default and the only enabled option in Phase 1), `T-Shirt Size` (disabled), `Story Points` (disabled).
   - **Optimistic (min)** — `QDoubleSpinBox`, range 0.01–9999.
   - **Most Likely** — `QDoubleSpinBox`, range 0.01–9999.
   - **Pessimistic (max)** — `QDoubleSpinBox`, range 0.01–9999.
   - **Unit** — `QComboBox` with `days` and `hours`. Default: `days`.
   - **Dependencies** — `QListWidget` with `QCheckBox` items listing all other tasks. Checked = this task depends on that task.
   - **Priority** — `QSpinBox`, default 0.
   - **Fixed Cost** — `QDoubleSpinBox`, optional, default empty/0.
5. Inline validation: red border if `min > expected` or `expected > max`. Tooltip explains the error.
6. **[Save Task]** applies changes back to the `TaskTableModel` and `UIProjectModel`. **[Cancel]** discards.
7. On save, close the panel and return to the table view.

**Verify:** Double-click a task, edit all fields, save. The table row and YAML update. Enter invalid estimates (min > max) — red border appears, save is blocked.

---

#### P1-09 — Inline Field Validation (Phase 1 Scope)

> Ref: §8, inline tier.

1. Create `src/mcprojsim/ui/validation.py` with reusable validation helpers.
2. Implement field-level validators:
   - **Non-empty name**: Project name, task name.
   - **Positive numeric**: hours_per_day > 0, spinbox values > 0.
   - **Estimate ordering**: `min <= expected <= max`.
   - **No self-dependency**: a task cannot depend on itself.
   - **Start date not empty**.
3. Each validator returns `(is_valid: bool, message: str)`.
4. Apply validators in `ProjectBasicsWidget` and `TaskEditorPanel`: on field change, run the validator. If invalid, set `QLineEdit.setStyleSheet("border: 2px solid red")` (or use `QPalette`) and set tooltip to the error message. If valid, reset style.
5. The **[Save Task]** button is disabled when any field in the editor is invalid.

**Verify:** Empty the project name → red border + tooltip. Set min > max in task editor → red border, Save disabled. Fix the value → border clears, Save enabled.

---

#### P1-10 — Full Validation via Engine

> Ref: §8, structural tier. Wire the [✓ Validate] toolbar button.

1. In `MainWindow`, connect `[✓ Validate]` action.
2. On click: call `UIProjectModel.to_dict()`, then call `YAMLParser().parse_dict(data)`.
3. If `ValueError` is raised, display the list of errors in a `QMessageBox` or a non-modal dockable panel below the form. Show file/field context from the error message.
4. If validation passes, show a brief green status bar message: "✓ Project is valid".

**Verify:** Create a project with a circular dependency (task A depends on B, B depends on A). Click Validate → error message names the cycle. Fix it → Validate passes.

---

#### P1-11 — File: New, Open, Save, Save As

> Ref: §9 (basic file handling only; CSV import is Phase 2).

1. **New** — reset `UIProjectModel` to defaults (empty project name, today's date, no tasks). If there are unsaved changes, prompt "Save changes?" (Yes / No / Cancel).
2. **Open** — `QFileDialog.getOpenFileName(filter="YAML (*.yaml *.yml);;TOML (*.toml)")`. Parse using the appropriate parser (`YAMLParser` for .yaml/.yml, `TOMLParser` for .toml). Populate the form via `UIProjectModel.from_dict()` and `ProjectBasicsWidget.from_dict()` / `TaskTableModel.from_list()`. Handle parse errors with a dialog.
3. **Save** — if the file has been opened or saved before, write `UIProjectModel.to_yaml()` to the same path. Otherwise, delegate to Save As.
4. **Save As** — `QFileDialog.getSaveFileName(filter="YAML (*.yaml)")`. Write YAML to the chosen path. Update the window title to include the filename.
5. **Dirty tracking** — maintain a `_dirty: bool` flag in `UIProjectModel`. Set to `True` on any change, `False` on save/open. Show `*` in the window title when dirty. Prompt on close if dirty.
6. **Recent Files** — store the last 10 file paths in `QSettings`. Populate the `File → Recent Files` submenu. Opening a recent file calls the Open logic.

**Verify:** Create a project with tasks → Save → close → reopen → all fields restored. Edit → title shows `*` → close → "Save changes?" prompt appears. Open a `.toml` file → loads correctly.

---

#### P1-12 — Run Simulation Dialog

> Ref: §5.10.

1. Create `src/mcprojsim/ui/dialogs/run_dialog.py` with class `RunSimulationDialog(QDialog)`.
2. Fields:
   - **Iterations** — `QSpinBox`, range 100–1 000 000, default 10 000.
   - **Random Seed** — `QLineEdit` (optional; leave blank for random). Validate: empty or positive integer.
   - **Output Format** — checkboxes: JSON, CSV, HTML. Default: HTML checked.
   - **Output Folder** — `QLineEdit` + `[Browse…]` button (`QFileDialog.getExistingDirectory`). Default: `~/Desktop/results`.
   - **"Validate project first"** — checkbox, checked by default.
3. **[Cancel]** closes the dialog. **[▶ Run]** triggers:
   a. If "validate first" is checked, run structural validation (P1-10 logic). If invalid, show errors and do not proceed.
   b. Call `dialog.accept()` returning `(iterations, seed, output_formats, output_folder)` to the caller.

**Verify:** Open dialog, change iterations to 500, set a seed, pick CSV + HTML, browse to a folder. Click Run. Values are returned correctly. With invalid project, errors are shown and dialog stays open.

---

#### P1-13 — Simulation Worker Thread

> Ref: §A.2.

1. Create `src/mcprojsim/ui/workers/simulation_worker.py` with class `SimulationWorker(QThread)`.
2. Signals: `progress = Signal(int, int)` (completed, total), `finished = Signal(object)` (`SimulationResults`), `error = Signal(str)`.
3. Constructor takes: `project_dict: dict`, `iterations: int`, `seed: Optional[int]`, `config: Config`.
4. `run()` method:
   a. Parse the project: `project = YAMLParser().parse_dict(self.project_dict)`.
   b. Build engine: `SimulationEngine(iterations=..., random_seed=..., config=config, show_progress=False, progress_callback=self._on_progress)`.
   c. Call `results = engine.run(project)`.
   d. Emit `self.finished.emit(results)`.
   e. On exception: `self.error.emit(str(e))`.
5. `_on_progress(completed, total)` → emits `self.progress.emit(completed, total)`.
6. Add `cancel()` method that calls `self.engine.cancel()` (ref: P1-02).

**Verify:** Unit test: create a `SimulationWorker` with a small project (3 tasks, 100 iterations), connect to signals, start thread, wait for `finished` signal, assert `SimulationResults` is returned. Test cancellation: start 100 000 iterations, call `cancel()`, assert worker finishes promptly without a result or with `SimulationCancelled`.

---

#### P1-14 — Wire Run Button → Worker → Progress → Results

> Connects P1-12 and P1-13 to the `MainWindow`.

1. In `MainWindow`, connect the `[▶ Run Simulation]` toolbar action:
   a. Open `RunSimulationDialog`. If user cancels, do nothing.
   b. Show the bottom "Simulation Results" pane (expand if collapsed).
   c. Show a `QProgressBar` in the results pane, set range 0–total.
   d. Instantiate `SimulationWorker` with model data and dialog settings.
   e. Connect `worker.progress → progress_bar.setValue`.
   f. Connect `worker.finished → self._on_simulation_finished`.
   g. Connect `worker.error → self._on_simulation_error`.
   h. Show a **[Cancel]** button next to the progress bar. Connect → `worker.cancel()`.
   i. Start the worker thread.
2. While simulation runs, disable [▶ Run Simulation] and [✓ Validate] buttons.
3. On error: show `QMessageBox.critical` with the error text. Re-enable buttons.
4. On finish:
   a. Re-enable buttons. Hide progress bar.
   b. Display results summary (P1-15).
   c. Export files to the chosen output folder in the selected formats.

**Verify:** Create a valid project → Run (10 000 iterations) → progress bar fills → results appear. Click Cancel mid-run → simulation stops, progress bar disappears, no crash.

---

#### P1-15 — Results Summary Pane

> Ref: §5.10 results section (summary only — no embedded HTML viewer yet).

1. Create `src/mcprojsim/ui/widgets/results_pane.py` with class `ResultsPane(QWidget)`.
2. Takes a `SimulationResults` object and displays:
   - **Calendar Time** box: Mean, Median, P80, P90 (from `results.statistics`). Show both hours and days (divide hours by `project.hours_per_day`).
   - **Effort** box (if `effort_durations` is populated): Mean effort hours.
   - **Critical Path** box: the most frequent path sequence, with percentage.
3. A **[Save]** button (saves results to the previously chosen output folder if not already exported).
4. An **[Open HTML Report]** button — if HTML export was selected, opens the HTML file in the system default browser via `QDesktopServices.openUrl()`.
5. A **[▲ Hide]** button collapses the results pane.
6. The pane replaces the progress bar in the bottom panel after simulation completes.

**Verify:** Run a simulation → results pane shows correct statistics (cross-check with CLI output for the same project/seed). Click [Open HTML Report] → browser opens the file.

---

#### P1-16 — Export Integration

> Ref: §7.1 export section.

1. After simulation completes, if the user selected output formats in the Run dialog:
   - Create the output folder if it doesn't exist.
   - For each selected format, call the corresponding exporter:
     - `JSONExporter.export(results, path / "results.json", config=config, project=project)`
     - `CSVExporter.export(results, path / "results.csv", config=config, project=project)`
     - `HTMLExporter.export(results, path / "results.html", config=config, project=project)`
2. Show a status bar message: "Results exported to ~/Desktop/results" with the path.
3. If export fails (e.g., permission error), show a warning dialog with the error.

**Verify:** Run simulation with all three formats checked → three files appear in the output folder. Open each and confirm content is valid.

---

#### P1-17 — YAML Syntax Highlighting

> Ref: §5.1 YAML preview pane.

1. Create `src/mcprojsim/ui/widgets/yaml_highlighter.py` with class `YAMLSyntaxHighlighter(QSyntaxHighlighter)`.
2. Highlight rules (via regex):
   - Keys (word followed by `:`) → bold, dark blue.
   - Strings (quoted) → dark green.
   - Numbers → dark cyan.
   - Comments (`#...`) → grey italic.
   - Booleans (`true`/`false`) → purple.
3. Attach the highlighter to the YAML preview `QPlainTextEdit` in `MainWindow`.

**Verify:** Open a project file → YAML preview is syntax-highlighted. Manually check a few colours are correct.

---

#### P1-18 — Auto-Save & Crash Recovery

> Ref: §9.

1. Start a `QTimer` in `MainWindow` that fires every 60 seconds.
2. On timer tick, if `_dirty` is `True`, write `UIProjectModel.to_yaml()` to a temp file at `~/.mcprojsim/autosave.yaml` (create directory if needed).
3. On clean exit (save or close without changes), delete the autosave file.
4. On launch, check if `~/.mcprojsim/autosave.yaml` exists. If so, prompt: "A previous session was not saved properly. Recover?" (Yes / No). If Yes, load the autosave file. If No, delete it.

**Verify:** Launch app → create a project → wait 60s → force-kill the process (kill -9). Relaunch → recovery prompt appears → recovered project matches what was in progress.

---

#### P1-19 — Application Icon & About Dialog

1. Source or create an application icon (`.icns` for macOS, `.ico` for Windows, `.png` for Linux). Place in `src/mcprojsim/ui/resources/`.
2. Set the icon on `QApplication` and `MainWindow`: `app.setWindowIcon(QIcon(...))`.
3. **About dialog** (`Help → About`): Show app name, version (from `mcprojsim.__version__`), "Built with PySide6 and mcprojsim", link to GitHub repo.
4. Use `QResource` or plain file path for icon loading.

**Verify:** Icon appears in the window title bar and dock/taskbar. About dialog shows correct version.

---

#### P1-20 — Smoke Test Script

1. Create `tests/test_ui_smoke.py`.
2. Use `pytest-qt` (add to `[tool.poetry.group.dev.dependencies]`) for Qt test infrastructure.
3. Tests:
   - `test_app_launches`: Instantiate `MainWindow`, assert window title contains "mcprojsim", close.
   - `test_project_basics_roundtrip`: Set project name and start date via the form, call `to_dict()`, assert values match.
   - `test_add_task_and_yaml`: Add a task via the [+ Add Task] button, assert the YAML preview contains the task name.
   - `test_save_and_open`: Save to a temp file, create new, open the saved file, assert form state matches.
   - `test_validate_invalid_project`: Create a task with min > max, click Validate, assert error appears.
4. Tests use `qtbot` fixture from `pytest-qt` for simulating clicks and waiting for signals.

**Verify:** `poetry run pytest tests/test_ui_smoke.py --no-cov -v` — all pass.

---

### Phase 2 — The Full Monty

**Goal:** Every feature described in §1–§12 is implemented. The app covers the full `mcprojsim` YAML schema, supports all estimate types, constrained scheduling, cost tracking, sprint planning, bidirectional YAML editing, CSV import, configuration editor, a new-project wizard, and polished production packaging for macOS and Windows.

---

#### P2-01 — T-Shirt Size & Story Point Estimate Modes

> Ref: §5.2 estimate alternatives. Prerequisite for projects using symbolic estimates.

1. In `TaskEditorPanel`, enable the `T-Shirt Size` and `Story Points` radio buttons.
2. **T-Shirt mode**: replace the numeric estimate fields with a radio-button row: `XS  S  M  L  XL  XXL`. Below it, a `QComboBox` for category (`story`, `bug`, `epic`, `business`, `initiative`) — populated from `Config.get_default()`.
3. **Story Points mode**: single `QSpinBox` for the point value (1–100).
4. When the estimate type changes, the corresponding input widget group is shown/hidden via `QStackedWidget` or show/hide logic.
5. `to_dict()` emits either `{low, expected, high, unit}`, `{t_shirt_size, category}`, or `{story_points}` depending on the selected mode.
6. `from_dict()` detects which keys are present and selects the correct radio button and populates the fields.
7. Update `TaskTableModel` display: for T-shirt, show `"M (story)"`; for story points, show `"5 SP"`.
8. Inline validation: if T-shirt or story points are selected, `unit` must NOT be present (enforced by model; UI simply omits it).

**Verify:** Create a task with T-shirt M, save. YAML shows `t_shirt_size: M`, no `unit` field. Reopen the task → T-shirt is selected, M is highlighted. Switch to Story Points → YAML updates. Run simulation → engine resolves symbolic estimates correctly.

---

#### P2-02 — Uncertainty Tab (Task Editor)

> Ref: §5.4.

1. In `TaskEditorPanel`, enable the **Uncertainty** tab.
2. Layout: a table/form with 5 factors:
   - Team Experience — 5 radio buttons: `Very Low`, `Low`, `Medium`, `High`, `Very High`. Default: `Medium`.
   - Requirements Maturity — same pattern.
   - Technical Complexity — same pattern.
   - Team Distribution — 2 radio buttons: `Colocated`, `Distributed`. Default: `Colocated`.
   - Integration Complexity — same 5 levels.
3. Below the factors, show **"Combined multiplier (estimated): ~X.XX×"** — calculate from the multiplier tables in `Config.get_default().uncertainty_multipliers`. Update live as the user changes any factor.
4. `to_dict()` emits `uncertainty_factors: {team_experience: "medium", ...}` only for factors that differ from the project-level defaults (§5.9). If all are default, omit the key.
5. `from_dict()` populates the radio buttons; missing factors show as medium.

**Verify:** Set team_experience to "low" and technical_complexity to "high" → multiplier shows ~1.15×. Save task → YAML includes only the two non-default factors. Clear them → key disappears from YAML.

---

#### P2-03 — Task-Level Risks (Risks Tab in Task Editor)

> Ref: §5.2 Risks tab, §5.5 risk editor dialog.

1. In `TaskEditorPanel`, enable the **Risks** tab.
2. The tab shows a mini risk table (same columns as the project-level risk table from P2-04) scoped to this task.
3. **[+ Add Risk]** opens the risk editor dialog (inline expansion or a small `QDialog`).
4. Risk editor fields:
   - **Name** — `QLineEdit`, required.
   - **Probability** — `QSpinBox` (0–100, suffix "%"). Also accept keyboard arrows.
   - **Impact Type** — radio buttons: `Hours (fixed)`, `Percentage`, `Absolute (days/hours)`.
   - Conditional fields based on impact type:
     - Percentage: `QSpinBox` (% of task duration).
     - Hours: `QDoubleSpinBox`.
     - Absolute: `QDoubleSpinBox` + unit combo (days/hours).
   - **Cost Impact** — `QDoubleSpinBox`, optional.
   - **Description** — `QTextEdit`, optional.
5. **[Save Risk]** / **[Cancel]** buttons.
6. Task-level risks are nested under the task in `to_dict()` as `risks: [...]`.

**Verify:** Add a risk "Server outage" with 10% probability and 20% impact. Save task. YAML shows the risk nested under the task. Remove the risk → it disappears from YAML.

---

#### P2-04 — Project-Level Risks Section

> Ref: §5.5.

1. Create `src/mcprojsim/ui/widgets/risks_section.py` with class `RisksSectionWidget(QWidget)`.
2. Section title: "RISKS". Add to `MainWindow`'s section layout.
3. Add to section navigator as "▷ Risks (N)" — collapsed by default.
4. **Project-wide risks table**: `QTableView` backed by `RiskTableModel(QAbstractTableModel)`.
   - Columns: ID (auto: `R1`, `R2`, …), Risk Name, Probability (%), Impact (formatted string).
5. **[+ Add Project Risk]** — opens the same risk editor dialog from P2-03 (reuse the widget).
6. Double-click a row → opens the editor to edit existing risk.
7. Right-click context menu → "Delete Risk" with confirmation.
8. Info label at bottom: "ℹ Task-level risks are added in the task editor (Risks tab)."
9. Connect data changes → `UIProjectModel` → YAML regeneration. Project-level risks go under `risks:` at project level.

**Verify:** Add two project risks. YAML shows a top-level `risks:` section. Delete one → YAML updates. The section navigator shows "Risks (1)".

---

#### P2-05 — Cost Section

> Ref: §5.6.

1. Create `src/mcprojsim/ui/widgets/cost_section.py` with class `CostSectionWidget(QWidget)`.
2. Add to section navigator as "▷ Cost" — collapsed by default.
3. Fields:
   - **Enable cost tracking** — `QCheckBox`. When unchecked, all other fields are disabled/greyed.
   - **Currency** — `QComboBox` (`USD`, `EUR`, `GBP`, `SEK`, etc.).
   - **Default Hourly Rate** — `QDoubleSpinBox` with currency prefix.
   - **Overhead Rate** — `QSpinBox` (0–100, suffix "%").
   - **Project Fixed Cost** — `QDoubleSpinBox`, optional.
   - **Target Budget** — `QDoubleSpinBox`, optional (for budget confidence analysis).
4. **Secondary Currencies** (collapsible "Advanced" sub-section):
   - **[+ Add Currency]** button.
   - Table: Currency, Rate to primary, FX Overhead (%).
   - Add/edit/delete rows.
5. Info label: "ℹ Per-task and per-resource hourly rates are set in the task editor and team member settings respectively."
6. Connect → `UIProjectModel` → YAML. The `cost:` section in YAML appears only when cost tracking is enabled.
7. Add `fixed_cost` field to the task editor Basics tab (already stubbed in P1-08 — ensure it connects).

**Verify:** Enable cost tracking, set rate to $125/hr, overhead 15%. YAML shows `cost:` section with correct values. Disable → `cost:` section disappears. Add a secondary currency → table row appears in YAML.

---

#### P2-06 — Team Members Section

> Ref: §5.7.

1. Create `src/mcprojsim/ui/widgets/team_section.py` with class `TeamSectionWidget(QWidget)`.
2. Add to section navigator as "▷ Team Members" — collapsed by default.
3. **Team member table**: `QTableView` — columns: Name, Experience (star rating), Availability (%), Hourly Rate.
4. **[+ Add Team Member]** button.
5. **Scheduling Mode** radio buttons:
   - `Dependency only (ignore team member assignments)`.
   - `Resource-constrained (respect team member assignments)`.
6. **Two-pass criticality ranking** — `QCheckBox`.
7. **Pass-1 iterations** — `QSpinBox`, shown only when two-pass is checked.
8. **Calendars** (collapsed sub-section): **[+ Add Calendar]** button — placeholder for calendar editor (P2-09).

**Verify:** Add two team members. YAML shows `resources:` section. Toggle scheduling mode → YAML includes/excludes resource-constrained config. Check two-pass → `two_pass: true` appears in YAML.

---

#### P2-07 — Team Member Editor Dialog

> Ref: §5.7 member editor dialog.

1. Create `src/mcprojsim/ui/dialogs/team_member_dialog.py` with class `TeamMemberDialog(QDialog)`.
2. Fields:
   - **Name** — `QLineEdit`, required.
   - **Experience Level** — 5 radio buttons (1–5) with star display.
   - **Productivity** — `QDoubleSpinBox`, default 1.0. Tooltip: "1.0 = baseline; 1.2 = 20% faster".
   - **Availability** — `QSpinBox` (0–100, suffix "%").
   - **Calendar** — `QComboBox` listing defined calendars (or "default").
   - **Hourly Rate** — `QDoubleSpinBox` with currency prefix.
   - **Absence** section:
     - **Sickness probability** — `QSpinBox` (0–100, suffix "% per week").
     - **Planned absence date ranges** — mini table with From/To columns (`QDateEdit`), [+ Add date range] button, [×] delete per row.
3. **[Save]** / **[Cancel]** buttons.
4. Update task editor to allow assigning a team member (add a `QComboBox` listing defined resources to the Basics tab, visible only when resources exist).

**Verify:** Add a team member with all fields populated. YAML shows the complete resource entry including absence dates. Edit → changes reflected. Add a task and assign the member → `assigned_to` appears in YAML.

---

#### P2-08 — Calendar Editor

> Ref: §5.7 calendars sub-section.

1. Create `src/mcprojsim/ui/dialogs/calendar_dialog.py` with class `CalendarDialog(QDialog)`.
2. Fields:
   - **Calendar Name** — `QLineEdit`, required.
   - **Working Hours** — `QTimeEdit` for start and end (e.g., 09:00–17:00).
   - **Working Days** — 7 checkboxes (Mon–Sun). Default: Mon–Fri checked.
   - **Holidays** — date list with [+ Add] and [×] delete per entry.
3. Calendars are listed in the Team Members section's "Calendars" sub-section and selectable in the Team Member Editor (P2-07).
4. Calendar data goes under `calendars:` in the YAML.

**Verify:** Create a calendar with custom hours and 2 holidays. Assign it to a team member. YAML shows `calendars:` section and the resource references the calendar by name.

---

#### P2-09 — Sprint History Section

> Ref: §5.8.

1. Create `src/mcprojsim/ui/widgets/sprint_section.py` with class `SprintSectionWidget(QWidget)`.
2. Add to section navigator as "▷ Sprint History" — collapsed by default.
3. Fields:
   - **Enable sprint planning** — `QCheckBox`. All other fields disabled when unchecked.
   - **Sprint Length** — `QSpinBox` (weeks).
   - **Capacity Mode** — radio: `Story Points` / `Hours`.
   - **Velocity Model** — radio: `Empirical` / `Neg-Binomial`.
4. **Sprint history table**: `QTableView` — columns: Sprint ID (auto), Completed Points, Spillover Points, Team Size (optional).
5. **[+ Add Sprint]** — adds a row.
6. **[Import from CSV]** button — reads a CSV file (ref: §A.8). Expected columns: `sprint_id`, `completed`, `spillover`, `team_size`. Populated rows replace or append to the table (with confirmation dialog).
7. Info label: "ℹ At least 2 usable sprint history rows are required. Tasks must use story_points estimates when this is enabled."
8. Validation: if enabled and < 2 rows → show warning. If capacity mode is "Story Points" but tasks don't use story point estimates → show warning.

**Verify:** Enable sprint planning, add 3 sprint rows. YAML shows `sprint_planning:` section. Import from a CSV file → table populates. Enable with only 1 row → warning shown.

---

#### P2-10 — Advanced Section

> Ref: §5.9.

1. Create `src/mcprojsim/ui/widgets/advanced_section.py` with class `AdvancedSectionWidget(QWidget)`.
2. Add to section navigator as "▷ Advanced" — collapsed by default.
3. **Distribution** sub-section:
   - **Task distribution** — radio: `Triangular` (default) / `Log-normal`.
   - **Default T-shirt category** — `QComboBox` (populated from config categories).
4. **Confidence Levels** sub-section:
   - Checkboxes for: P10, P25, P50, P75, P80, P85, P90, P95, P99. Default: P50, P75, P80, P85, P90, P95, P99 checked.
   - **[+ custom]** button to add an arbitrary percentile (spin box, 1–99).
5. **Probability Thresholds** sub-section:
   - **Red below** — `QSpinBox` (0–100, default 50).
   - **Green above** — `QSpinBox` (0–100, default 90).
   - Validation: red < green.
6. **Project-level Uncertainty Factors** sub-section:
   - Same 5-factor layout as the task-level Uncertainty tab (P2-02), but these are project defaults. Reuse the widget.
   - Caption: "Override defaults for all tasks unless overridden per task."
7. Connect → `UIProjectModel` → YAML. These values go into `simulation:` and `uncertainty:` config sections — or into the project-level YAML depending on the field.

**Verify:** Set distribution to Log-normal. YAML includes `distribution: lognormal`. Change thresholds → YAML updates. Set project-level experience to "high" → appears in YAML.

---

#### P2-11 — Dependency Graph View

> Ref: §5.3, §A.4.

1. Create `src/mcprojsim/ui/widgets/dependency_graph.py`.
2. Add a toggle in the Tasks section toolbar: **[Table View]** / **[Graph View]**.
3. Use `QGraphicsScene` and `QGraphicsView`.
4. **Node rendering**: each task is a rounded-rectangle `QGraphicsRectItem` with task ID, name, and estimate text. Colour-code by criticality (if results are available) or neutral.
5. **Edge rendering**: directed arrows (`QGraphicsLineItem` with arrowheads) for each dependency.
6. **Layout**: implement a layered (Sugiyama-style) layout algorithm, or use the `graphviz` Python bindings (`pygraphviz` or `graphviz` package) to compute positions. For up to ~100 tasks this is fast enough.
7. **Interaction**:
   - Click a node → highlight it and its edges, show task details in a tooltip.
   - Double-click a node → open the task editor (P1-08).
   - Drag a node → reposition it (manual layout override).
   - Drag from a node edge → create a new dependency arrow to the drop target.
   - Right-click an edge → "Remove dependency".
8. Zoom via scroll wheel. Pan via middle-click drag or Ctrl+scroll.
9. Data changes from graph interactions update `UIProjectModel` → YAML regenerates.
10. Add `graphviz` (or `pygraphviz`) as an optional dependency in `[tool.poetry.group.ui.dependencies]`.

**Verify:** Create 5 tasks with dependencies. Switch to Graph View → nodes arranged top-to-bottom by dependency depth. Drag arrow from task A to task B → YAML shows new dependency. Remove an edge → dependency removed. Double-click node → editor opens.

---

#### P2-12 — Bidirectional YAML ↔ Form Sync

> Ref: §7, §A.5.

1. Make the YAML preview pane **editable** (`QPlainTextEdit.setReadOnly(False)`).
2. On YAML text change (debounced by ~300 ms to avoid parsing on every keystroke):
   a. Call `yaml.safe_load(text)` — if it raises a YAML syntax error, show a warning badge on the YAML tab (yellow ⚠ icon) and do **not** update the form. Show the parse error in a tooltip on the badge.
   b. If YAML is valid, call `YAMLParser().parse_dict(data)`. If it raises `ValueError` (structural error), show a warning badge with the validation error. Do not update the form.
   c. If both pass, call `UIProjectModel.from_dict(data)` → update all form widgets. Suppress `dataChanged` signals during this update to prevent a feedback loop (YAML → form → YAML).
3. Form → YAML direction (existing from P1-06): when form changes, regenerate YAML and update the pane. Suppress YAML text change handler during this update.
4. Add an undo/redo stack: `QUndoStack`. Each form change or YAML edit pushes a `QUndoCommand`. Wire `Edit → Undo` and `Edit → Redo` menu actions. Also `Ctrl+Z` / `Ctrl+Shift+Z` shortcuts.
5. Consider switching from `pyyaml` to `ruamel.yaml` for comment-preserving round-trip — add as dependency. If comments are not a requirement, stick with `pyyaml`.

**Verify:** Edit the YAML to add a new task → form table shows the new task. Edit a task name in the form → YAML updates. Type invalid YAML → warning badge appears, form unchanged. Undo → previous state restored.

---

#### P2-13 — CSV Task Import

> Ref: §9.1.

1. Add `File → Import Tasks…` menu action.
2. Open `QFileDialog.getOpenFileName(filter="CSV (*.csv)")`.
3. Parse the CSV with Python's `csv.DictReader`. Validate:
   - `name` column is required.
   - Either (`low`, `expected`, `high`) or `t_shirt_size` or `story_points` must be present.
   - If `dependencies` column exists, resolve task name references against the imported task list.
4. Auto-generate IDs: `task_001`, `task_002`, etc.
5. Present a preview dialog showing the parsed tasks in a `QTableView`:
   - Title: "Import N tasks from file.csv".
   - Radio buttons: `Append to existing tasks` / `Replace all tasks`.
   - **[Cancel]** / **[Import]**.
6. On import, add/replace tasks in `UIProjectModel`, refresh the task table and YAML.

**Verify:** Create a CSV with 5 tasks (name, low, expected, high, dependencies). Import → 5 tasks appear in the table with correct estimates and dependency references. Import again with "replace" → old tasks are gone.

---

#### P2-14 — Sprint History CSV Import

> Ref: §A.8.

1. In the Sprint History section (P2-09), the **[Import from CSV]** button triggers `QFileDialog`.
2. Parse CSV columns: `sprint_id` (optional, auto-generated if missing), `completed`, `spillover`, `team_size` (optional).
3. Show a preview dialog (small `QTableView`) with radio: `Append` / `Replace`.
4. On import, populate the sprint history table and update `UIProjectModel`.

**Verify:** Create a CSV with 5 sprint rows. Import → table shows 5 rows. YAML includes all sprint data.

---

#### P2-15 — Configuration Editor (Preferences Dialog)

> Ref: §11, §A.6.

1. Create `src/mcprojsim/ui/dialogs/preferences_dialog.py` with class `PreferencesDialog(QDialog)`.
2. **Tab bar**: Simulation, T-Shirt Sizes, Story Points, Uncertainty, Output.
3. **Simulation tab**:
   - Default Iterations — `QSpinBox`.
   - Max Stored Paths — `QSpinBox`.
4. **T-Shirt Sizes tab**:
   - Table: Size (XS–XXL), Low, Expected, High. Editable cells.
   - Default Category — `QComboBox`.
   - Unit — `QComboBox` (hours/days).
   - One table per category (tabbed or selectable via combo).
5. **Story Points tab**:
   - Table: Points (1, 2, 3, 5, 8, 13, …), Low, Expected, High. Editable cells.
6. **Uncertainty tab**:
   - Table of multipliers per factor per level. Editable.
7. **Output tab**:
   - Number of histogram bins — `QSpinBox` (note: field is `number_bins` in code, not `histogram_bins`).
   - Default percentiles shown.
8. **Config File** row at the bottom: path display + **[Browse…]** + **[Save]** + **[Reset to Defaults]**.
9. **Implementation** (ref: §A.6):
   a. On dialog open: `defaults = Config.get_default().model_dump()` → populate form.
   b. If a config file is loaded, deep-merge its values over defaults → populate form.
   c. On Save: build dict from form, deep-merge over defaults, call `Config.model_validate(merged)` to validate, serialize to YAML, write to the chosen file path.
   d. On Reset: repopulate form from `Config.get_default()`.
10. Config is loaded at app startup (from `~/.mcprojsim/config.yaml` if it exists) and passed to `SimulationEngine` on every run.

**Verify:** Open Preferences → defaults displayed. Change iterations to 5000, save to a file. Close and reopen Preferences → shows 5000. Reset → back to 10 000. Run simulation → engine uses 5000 iterations (if file was saved before reset).

---

#### P2-16 — New Project Wizard

> Ref: §5.11.

1. Create `src/mcprojsim/ui/dialogs/wizard.py` with class `NewProjectWizard(QWizard)`.
2. **Step 1 — Project Basics**: Project Name (required), Start Date (required), Currency (optional), Hourly Rate (optional). [Skip] button sets sensible defaults and jumps to Step 3. [Next →] proceeds.
3. **Step 2 — Add Your First Task**: Task Name (required), Optimistic/Most Likely/Pessimistic in days. [← Back], [Add Task] (adds to internal list and clears fields for another), [Finish →] (proceeds even with just 1 task).
4. **Step 3 — Ready to Simulate**: Summary text: "✓ 'My Project' has N task(s)." Buttons: [← Back], [Open Project] — which closes the wizard and loads the data into `MainWindow`.
5. Show the wizard on first app launch (check `QSettings` for a "has_launched_before" flag) and when clicking **[+ New]** in the toolbar.
6. After wizard completes, the full project is loaded into `UIProjectModel` and displayed in the form + YAML preview.

**Verify:** First launch → wizard appears. Enter project name, add 2 tasks, finish → main window shows the project with 2 tasks and correct YAML. Click [+ New] → wizard appears again.

---

#### P2-17 — HTML Report Viewer (Embedded)

> Ref: §12 Phase 4 item.

1. Add `QWebEngineView` (from `PySide6.QtWebEngineWidgets`) as a tab in the bottom results panel, alongside the summary pane.
2. After simulation, if HTML export was produced, load the HTML file into the web view.
3. Tab label: "HTML Report". Visible only after a simulation with HTML output.
4. Add `PySide6-WebEngine` to the UI dependency group (note: this increases bundle size by ~50 MB).
5. Fallback: if WebEngine is not installed (e.g., pip install without it), the tab is hidden and the **[Open HTML Report]** button (P1-15) remains the only option.

**Verify:** Run simulation with HTML → "HTML Report" tab appears → full report rendered inside the app. Without WebEngine installed → tab is absent, [Open HTML Report] still works.

---

#### P2-18 — Progressive Disclosure Polish

> Ref: §6.

1. Ensure sections listed as "collapsed by default" in §6 (Risks, Cost, Team Members, Sprint History, Advanced) start collapsed in the section navigator and form layout.
2. The section navigator shows a collapsed indicator (`▷`) for hidden sections and an expanded indicator (`▶`) for visible sections.
3. Clicking a collapsed section expands it (scrolls to it, changes indicator to `▶`).
4. Sections with data show a count badge: "Risks (2)", "Team Members (3)".
5. Sections with no data show helper text when first expanded: e.g., "No risks defined yet. Click [+ Add Project Risk] to get started."
6. The first two sections (Project Basics, Tasks) are always expanded and cannot be collapsed.

**Verify:** Fresh project → only Project Basics and Tasks visible. Click "▷ Risks" → expands, shows empty state text. Add a risk → badge shows "Risks (1)".

---

#### P2-19 — Searchable Dependency List for Large Projects

> Ref: §A.4 last bullet.

1. When the project has > 20 tasks, replace the simple checkbox list in the task editor's dependency picker with a searchable list:
   - A `QLineEdit` filter field at the top.
   - A `QListView` backed by a `QSortFilterProxyModel` that filters by task name/ID as the user types.
   - Checkboxes remain for selection.
2. For ≤ 20 tasks, keep the simple checkbox list.

**Verify:** Create a project with 30 tasks. Open a task editor → dependency list has a search field. Type a task name → list filters to matches.

---

#### P2-20 — Undo / Redo System

> Ref: §7 (undo/redo), §12 Phase 4.

1. Implement a `QUndoStack` in `MainWindow`.
2. Wrap each user action as a `QUndoCommand` subclass:
   - `ChangeProjectBasicsCommand` — stores old and new basics dicts.
   - `AddTaskCommand` / `RemoveTaskCommand` / `EditTaskCommand` — stores task data.
   - `AddRiskCommand` / `RemoveRiskCommand` / `EditRiskCommand`.
   - `ChangeYAMLCommand` — for direct YAML edits (stores old and new text).
   - (Add commands for Cost, Team Members, Sprint, Advanced as needed.)
3. Wire `Edit → Undo` (`Ctrl+Z`) and `Edit → Redo` (`Ctrl+Shift+Z`) to `QUndoStack.undo()` / `redo()`.
4. The undo stack merges consecutive same-field edits within 500 ms (so typing "hello" in a name field becomes one undo step, not 5).

**Verify:** Add a task → undo → task disappears → redo → task reappears. Edit a task name letter by letter → undo once → whole name change reverts (not one letter).

---

#### P2-21 — PyInstaller Spec: macOS

> Ref: §10.1, §10.2, §A.7.

1. Create `packaging/mcprojsim-ui.spec` (PyInstaller spec file) for macOS.
2. Configure:
   - Entry point: `src/mcprojsim/ui/main.py`.
   - `onedir` mode (directory bundle, wrapped as `.app`).
   - Include all `mcprojsim` source, `PySide6` plugins, numpy, scipy, matplotlib, `pyyaml` (or `ruamel.yaml`).
   - Exclude test files, docs, dev dependencies.
   - Set `Info.plist` keys: `CFBundleName = "mcprojsim"`, `CFBundleIdentifier = "com.mcprojsim.app"`, `LSMinimumSystemVersion = "12.0"`, `CFBundleIconFile = "mcprojsim.icns"`.
   - Include the app icon.
3. Build locally: `pyinstaller packaging/mcprojsim-ui.spec` → produces `dist/mcprojsim.app`.
4. Test: double-click `.app` → launches correctly. All features work (create project, run simulation, view results).

**Verify:** `dist/mcprojsim.app` launches on macOS, runs simulation successfully, file open/save works.

---

#### P2-22 — macOS Code Signing & Notarization

> Ref: §10.2.

1. Obtain an Apple Developer ID Application certificate.
2. Code-sign the `.app` bundle: `codesign --deep --options runtime --sign "Developer ID Application: ..." dist/mcprojsim.app`.
3. Create a `.dmg` using `create-dmg` (or `hdiutil`): include `.app` and a symlink to `/Applications`.
4. Submit for notarization: `xcrun notarytool submit dist/mcprojsim.dmg --apple-id ... --password ... --team-id ... --wait`.
5. Staple the ticket: `xcrun stapler staple dist/mcprojsim.dmg`.
6. Test: download the `.dmg` on a clean Mac → double-click → no Gatekeeper warning → app runs.

**Verify:** `spctl --assess --type execute dist/mcprojsim.app` returns "accepted". Gatekeeper does not block the app.

---

#### P2-23 — PyInstaller Spec: Windows

> Ref: §10.1, §10.3.

1. Create `packaging/mcprojsim-ui-win.spec` (or extend the macOS spec with platform detection).
2. Configure for `onedir` mode on Windows.
3. Include same dependencies as macOS. Set app icon (`.ico` format).
4. Build on Windows: `pyinstaller packaging/mcprojsim-ui-win.spec`.
5. Create Inno Setup script `packaging/mcprojsim-installer.iss`:
   - Installer name: "mcprojsim Setup".
   - Start Menu shortcut.
   - Desktop shortcut (optional).
   - Uninstaller.
6. Build installer: `iscc packaging/mcprojsim-installer.iss` → produces `mcprojsim-setup.exe`.

**Verify:** Run `mcprojsim-setup.exe` on a clean Windows machine → installs → Start Menu shortcut works → app launches and runs a simulation.

---

#### P2-24 — Windows Code Signing

> Ref: §10.3.

1. Obtain an Authenticode code signing certificate (EV recommended for SmartScreen trust).
2. Sign the `.exe` files in the PyInstaller output: `signtool sign /f cert.pfx /p ... /tr http://timestamp.digicert.com /td sha256 dist/mcprojsim/*.exe`.
3. Sign the Inno Setup installer `.exe` as well.
4. Test: download and run on a machine without the cert → SmartScreen does not block.

**Verify:** `signtool verify /pa mcprojsim-setup.exe` returns "Successfully verified".

---

#### P2-25 — CI/CD Release Pipeline (GitHub Actions)

> Ref: §10.4.

1. Create `.github/workflows/release-ui.yml`.
2. Trigger: on push of a tag matching `v*` (or manual dispatch).
3. **macOS job** (`runs-on: macos-latest`):
   a. Checkout, setup Python 3.13.
   b. `pip install pyinstaller pyside6 .`
   c. `pyinstaller packaging/mcprojsim-ui.spec`
   d. Code sign (using secrets for certificate identity/password).
   e. Create `.dmg`.
   f. Notarize + staple.
   g. Upload `.dmg` as release artefact.
4. **Windows job** (`runs-on: windows-latest`):
   a. Checkout, setup Python 3.13.
   b. `pip install pyinstaller pyside6 .`
   c. `pyinstaller packaging/mcprojsim-ui-win.spec`
   d. Code sign (using secrets for Authenticode cert).
   e. Build Inno Setup installer.
   f. Sign installer.
   g. Upload `.exe` as release artefact.
5. **Release job** (after both platform jobs): create a GitHub Release, attach both artefacts and auto-generate release notes.

**Verify:** Push a test tag → workflow runs → both artefacts are uploaded to the GitHub Release page. Download each and confirm they install and run.

---

#### P2-26 — Developer Install (`pip install mcprojsim[ui]`)

> Ref: §10.5.

1. In `pyproject.toml`, add `ui` to the extras:
   ```toml
   [tool.poetry.extras]
   ui = ["PySide6"]
   ```
2. Ensure `mcprojsim-ui` script entry point is included.
3. Test: `pip install .[ui]` in a clean venv → `mcprojsim-ui` launches.
4. Test without `[ui]`: `pip install .` → `mcprojsim-ui` fails with a clear error message ("PySide6 is required. Install with: pip install mcprojsim[ui]").

**Verify:** Clean venv → `pip install .[ui]` → `mcprojsim-ui` runs. Without extras → helpful error on launch.

---

#### P2-27 — Comprehensive Test Suite

> Extends P1-20.

1. Add `pytest-qt` tests for every widget:
   - `test_cost_section.py` — enable cost, set fields, verify `to_dict()`.
   - `test_risk_section.py` — add/edit/delete risks, verify model.
   - `test_team_section.py` — add members, toggle scheduling mode, verify YAML.
   - `test_sprint_section.py` — add sprints, import CSV, verify data.
   - `test_advanced_section.py` — change distribution, thresholds, verify YAML.
   - `test_task_editor_full.py` — all three tabs (Basics, Uncertainty, Risks), all estimate modes.
   - `test_dependency_graph.py` — add/remove edges via the graph, verify model.
   - `test_yaml_sync.py` — edit YAML → form updates; edit form → YAML updates; invalid YAML → warning badge.
   - `test_csv_import.py` — import valid CSV, import with missing columns (error), append vs replace.
   - `test_preferences.py` — open config editor, change values, save, reload.
   - `test_wizard.py` — complete all 3 steps, verify project is loaded.
   - `test_undo_redo.py` — add task, undo, redo. Edit, undo.
2. Integration test:
   - `test_full_workflow.py` — create project via wizard, add 5 tasks with dependencies, enable cost and risks, run simulation (low iterations), verify results appear and export files are created.
3. Target: all UI tests pass with `poetry run pytest tests/test_ui_*.py --no-cov -v`.

**Verify:** Full test suite passes. No test touches the network or filesystem outside temp directories.

---

### Phase Summary

| Phase | Items | Core Deliverable |
|-------|-------|-----------------|
| **Phase 1 — MVP** | P1-01 through P1-20 | Functional app: create tasks (triangular estimates), YAML preview, run simulation with progress bar, view summary results, save/open files |
| **Phase 2 — Full Monty** | P2-01 through P2-27 | Complete feature set: all estimate types, risks, cost, team members, calendars, sprint planning, dependency graph, bidirectional YAML, CSV import, config editor, wizard, undo/redo, signed macOS + Windows distribution |
