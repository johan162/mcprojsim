Version: 0.1.0

Date: 2026-04-16

Status: Design and Research Proposal

# mcprojsim Web UI — Design Document

**Scope:** A browser-based GUI that lets a new user create, edit, validate, and simulate mcprojsim YAML project files without knowing the YAML format. Shares the same usability philosophy as the desktop design (`ui-design.md`) but is served over HTTP and accessible from any modern browser or a local Electron-free desktop shell.

---

## 1. Goals

Identical to the desktop design — the web medium changes the delivery mechanism, not the intent.

| Goal | Description |
|------|-------------|
| **Beginner-first** | A new user can create a basic project with 5 tasks and run a simulation in under 2 minutes, with zero knowledge of YAML. |
| **Full coverage** | Every field the YAML format supports is editable somewhere in the UI. Nothing is lost. |
| **Progressive disclosure** | Advanced options (cost, resources, sprint planning, calendars) are reachable but out of the way. |
| **Live YAML** | The generated YAML is always visible for users who want to learn or paste into a text editor. |
| **Run in-app** | The user can run a simulation and see results without leaving the application. |

**Additional web goals:**

| Goal | Description |
|------|-------------|
| **Zero install for end-users** | Self-hosted or cloud deployment: navigate to a URL, start working. |
| **Local-first when desired** | `pip install mcprojsim[web]` + `mcprojsim-web` starts a local server on `localhost:7860`; data never leaves the machine. |
| **Shareable projects** | Projects can optionally be saved server-side and shared via URL. |
| **Responsive** | Usable on a 1280 px desktop; gracefully degrades on a tablet. Not designed for mobile. |

---

## 2. Tech Stack Recommendation

### Chosen: **NiceGUI + FastAPI (same process)**

```
Language:   Python 3.13+   (required by mcprojsim core)
UI layer:   NiceGUI 2.x    (Python API → Vue 3 / Quasar components in browser)
Transport:  WebSocket      (built into NiceGUI via Starlette/uvicorn)
HTTP server: uvicorn       (ASGI, ships with NiceGUI)
Syntax HL:  CodeMirror 6   (injected via NiceGUI's `ui.element` escape hatch)
DAG view:   elkjs + svg.js (bundled JS, injected once into the page)
Charts:     Plotly.js      (via `ui.plotly`, already optional dep of NiceGUI)
```

**Why NiceGUI:**

- The entire UI is written in **pure Python** — no TypeScript, no JSX, no build step.
- NiceGUI is built on top of **FastAPI + Starlette**; the simulation API and UI share one uvicorn process, so the engine is imported directly (no subprocess calls, no HTTP round-trips for simulation).
- Component library is **Quasar (Vue 3)**, which ships a professional-looking design system: cards, tabs, drawers, dialogs, data tables, progress bars, tree views — everything needed here.
- **WebSocket push** lets the progress bar update in real time from a background thread with a single `ui.notify()` or by writing to a `ui.label` from the worker thread.
- Hot-reload during development: `nicegui --reload`.
- Ships as a standalone server: `python -m nicegui app.py` or via the `ui.run()` call.

**Alternatives considered:**

| Stack | Pros | Cons |
|-------|------|------|
| Streamlit | Very easy to get started | Re-runs full script on every interaction; poor for stateful forms with many fields |
| Reflex | Pure Python, React-backed | Large bundle, slower cold-start, opinionated state model conflicts with mcprojsim's Pydantic models |
| Dash | Good charts, stable | Callback pattern is verbose; not suited to complex nested forms |
| Gradio | Good for ML demos | Limited layout control; designed for simple input→output, not rich editors |
| FastAPI + React | Maximum control | Two languages; separate build pipeline; loses the "Python stack" property |
| FastAPI + HTMX | Lightweight, fast | Form-heavy UX requires significant templating; no reactive state |
| Panel | Data-centric | Bokeh dependency heavy; weaker form component set |

**Dependency additions (pyproject.toml optional group):**
```toml
[tool.poetry.group.web]
optional = true

[tool.poetry.group.web.dependencies]
nicegui = ">=2.0"
uvicorn = {extras = ["standard"], version = ">=0.30"}
```

**Entry point:**
```toml
[tool.poetry.scripts]
mcprojsim-web = "mcprojsim.web.main:main"
```

Launch locally:
```bash
pip install mcprojsim[web]
mcprojsim-web           # opens http://localhost:7860 in the default browser
mcprojsim-web --port 8080 --host 0.0.0.0   # team server
```

---

## 3. Design Principles

Identical to the desktop design — the web surface does not change the UX contract.

1. **One primary action per screen** — do not overwhelm with options.
2. **Smart defaults** — pre-fill start date to today, default estimate unit to `hours`, default uncertainty level to `medium`.
3. **Inline validation** — show error state and helper text on bad values immediately; do not wait for a save action.
4. **YAML preview is read-write** — an advanced user can edit YAML directly and the form reflects the change.
5. **Section tabs are additive** — the user only needs the "Tasks" section to get a working project; every other section adds optional capability.
6. **No jargon until the user goes looking** — "Sprint Planning" is labelled "Sprint History (Optional)"; "Resources" is labelled "Team Members (Optional)"; "Constrained Scheduling" lives inside the Team Members section.

**Web-specific additions:**

7. **No page reloads** — all navigation is in-page; the browser URL updates via the History API but the page never reloads.
8. **Keyboard-first** — every action is reachable by keyboard: `⌘S` saves, `⌘↵` runs simulation, `⌘K` opens command palette.
9. **Dark mode by default** — follows `prefers-color-scheme`; toggle available in the header.

---

## 4. Visual Language

### 4.1 — Colour Palette

```
Background (dark)   #0f1117    Deepest surface
Surface             #1a1d27    Card / panel background
Surface raised      #22263a    Input fields, hover states
Border              #2e3350    Subtle dividers
Accent blue         #4f8ef7    Primary action (Run, Save, links)
Accent green        #34c47b    Success, valid state
Accent amber        #f5a623    Warning
Accent red          #e05252    Error, danger
Text primary        #e8eaf0    Body text
Text muted          #7b82a0    Labels, placeholders
```

A single `prefers-color-scheme: light` override swaps the palette to a clean off-white surface (`#f4f5f9`) while keeping the accent colours.

### 4.2 — Typography

```
Font:        Inter (variable) — loaded from Google Fonts or bundled
Code/YAML:   JetBrains Mono or Fira Code
Base size:   14px
Line height: 1.6
Heading:     Inter 600, slightly tracked
```

### 4.3 — Component Tokens

| Element | Style |
|---------|-------|
| Cards | `border-radius: 10px`, `1px border`, `4px box-shadow` |
| Inputs | Filled style, `border-radius: 6px`, focus ring in accent blue |
| Buttons (primary) | Filled accent blue, `border-radius: 6px`, subtle scale on hover |
| Buttons (secondary) | Ghost / outlined |
| Tab bars | Pill-style active indicator, no underline |
| Tables | Zebra rows, sticky header, row highlight on hover |

---

## 5. Information Architecture

The layout is a three-zone shell that does not change as the user navigates sections:

```
┌─────────────────────────────────────────────────────────────┐
│  HEADER BAR                                                 │
│  logo  project-name  [breadcrumb]  [⌘K Command Palette]     │
│  [New] [Open] [Save]  ·  [✓ Validate] [▶ Run Simulation]    │
│                                             [🌙 Dark Mode]  │
├──────────────┬──────────────────────────────────────────────┤
│  LEFT NAV    │  MAIN EDITOR AREA                            │
│  (240 px)    │  (scrollable, sections stack vertically)     │
│              │                                              │
│  Section     │  PROJECT BASICS ───────────────────────────  │
│  Navigator   │                                              │
│              │  TASKS ────────────────────────────────────  │
│  ▶ Project   │                                              │
│    Basics    │  RISKS (collapsed) ───────────────────────   │
│              │                                              │
│  ▶ Tasks(8)  │  COST (collapsed) ────────────────────────   │
│              │                                              │
│  ▷ Risks(2)  │  ...                                         │
│              │                                              │
│  ▷ Cost      │                                              │
│              ├──────────────────────────────────────────────┤
│  ▷ Team      │  BOTTOM DRAWER (resizable, 30% default)      │
│              │  [YAML Preview]  [Simulation Results]        │
│  ▷ Sprint    │                                              │
│              │                                              │
│  ▷ Advanced  │                                              │
└──────────────┴──────────────────────────────────────────────┘
```

The left nav acts as a section outline with smooth-scroll anchors. Clicking a nav item scrolls the editor to that section and highlights it. The bottom drawer houses the YAML preview and simulation results in a tab strip; it can be dragged to any height or minimised to a thin strip.

On viewports narrower than 900 px the left nav becomes a top tab bar and the bottom drawer moves to a full-width panel below the editor.

---

## 6. Screen Sketches

### 6.1 — Full Layout (Dark Mode)

```
╔═════════════════════════════════════════════════════════════════════╗
║  ◆ mcprojsim   Customer Portal Redesign ▸ Tasks         [⌘K ...]    ║
║  [+ New]  [↑ Open]  [↓ Save]  ·  [✓ Validate]  [▶ Run Simulation]   ║
╠═══════════════╦═════════════════════════════════════════════════════╣
║  SECTIONS     ║  PROJECT BASICS                               ╌ ╌╌╌ ║
║               ║                                                     ║
║  ▶ Project    ║  Name *      ┌────────────────────────────────────┐ ║
║    Basics     ║              │ Customer Portal Redesign           │ ║
║               ║              └────────────────────────────────────┘ ║
║  ▶ Tasks(8)   ║  Start Date  ┌───────────┐  Hours/Day   ┌─────────┐ ║
║               ║              │ 2026-05-01│              │   8.0   │ ║
║  ▷ Risks(2)   ║              └───────────┘              └─────────┘ ║
║               ║  Working Days/Week ┌───┐  Distribution   ┌────────┐ ║
║  ▷ Cost       ║                    │ 5 │                 │Triangl.│ ║
║               ║                    └───┘                 └────────┘ ║
║  ▷ Team       ╠═════════════════════════════════════════════════════╣
║               ║  TASKS                                         ╌╌╌╌ ║
║  ▷ Sprint     ║                                                     ║
║               ║  [+ Add Task]  [⇄ Graph View]  [⤓ Import CSV]       ║
║  ▷ Advanced   ║                                                     ║
║               ║  ┌────┬───────────────────────────┬──────────┬────┐ ║
║               ║  │ ⠿  │ Task                      │ Estimate │Dep │ ║
║               ║  ├────┼───────────────────────────┼──────────┼────┤ ║
║               ║  │ ⠿  │ Database schema design    │ 3–5–10 d │ —  │ ║
║               ║  │ ⠿  │ API endpoint impl.        │ 5–8–15 d │ #1 │ ║
║               ║  │ ⠿  │ Frontend components       │ 7–10–18d │ —  │ ║
║               ║  └────┴───────────────────────────┴──────────┴────┘ ║
╠═══════════════╩═════════════════════════════════════════════════════╣
║  [YAML Preview ▼]  [Simulation Results]            [─ ─  □  ✕]      ║
║ ┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄    ║
║  project:                                                [Copy YAML]║
║    name: "Customer Portal Redesign"                                 ║
║    start_date: "2026-05-01"                                         ║
╚═════════════════════════════════════════════════════════════════════╝
```

> **⠿** = drag handle for row reordering (HTML5 drag-and-drop).  
> The bottom drawer defaults to ~30% height; can be dragged or double-clicked to toggle full/minimised.

---

### 6.2 — Task Editor (Slide-Over Panel)

Double-clicking a task row slides in a panel from the right (600 px wide, overlays the editor with a semi-transparent backdrop). Closing the panel restores full focus to the task table. The panel has three tabs:

```
╔════════════════════════════════════════════════════════╗
║  Edit Task: "API endpoint implementation"      [×]     ║
║  ────────────────────────────────────────────────────  ║
║  ● Basics   ○ Uncertainty   ○ Risks                    ║
║                                                        ║
║  Task ID       ┌─────────────────────────────────┐     ║
║                │ task_002                        │     ║
║                └─────────────────────────────────┘     ║
║  Name *        ┌─────────────────────────────────┐     ║
║                │ API endpoint implementation     │     ║
║                └─────────────────────────────────┘     ║
║  Description   ┌─────────────────────────────────┐     ║
║                │                                 │     ║
║                └─────────────────────────────────┘     ║
║                                                        ║
║  Estimate ───────────────────────────────────────────  ║
║  ○ Three-Point (days / hours)                          ║
║  ● Story Points                                        ║
║  ○ T-Shirt Size                                        ║
║                                                        ║
║  ┌─ Three-Point ─────────────────────────────────┐     ║
║  │ Optimistic   ┌────────┐  days                 │     ║
║  │              │   5    │                       │     ║
║  │ Most Likely  ┌────────┐                       │     ║
║  │              │   8    │   ╭────────╮          │     ║
║  │ Pessimistic  ┌────────┐   │ 5─8─15 │ (spark)  │     ║
║  │              │  15    │   ╰────────╯          │     ║
║  │ Unit         ┌────────┐                       │     ║
║  │              │ days ▼ │                       │     ║
║  └───────────────────────────────────────────────┘     ║
║                                                        ║
║  Dependencies ───────────────────────────────────────  ║
║  ┌────────────────────────────────────────────────┐    ║
║  │ [✓] Database schema design (task_001)          │    ║
║  │ [ ] Frontend components (task_003)             │    ║
║  │ [ ] Auth & Authorization (task_004)            │    ║
║  └────────────────────────────────────────────────┘    ║
║                                                        ║
║                         [Discard]  [Save Task ↵]       ║
╚════════════════════════════════════════════════════════╝
```

The small spark chart on the right of the Three-Point block updates live as the three values change, giving a visual sense of the distribution shape.

--- 

### 6.3 — Dependency Graph View

The **[⇄ Graph View]** toggle replaces the table with an interactive SVG DAG rendered by elkjs (layout) + svg.js (rendering). Both libraries are injected once as static assets and kept in a NiceGUI `ui.html` island.

```
╔═════════════════════════════════════════════════════════════════╗
║  TASKS   [○ Table]  [● Graph]     [+ Add Task]  [⤓ Import CSV]  ║
║ ─────────────────────────────────────────────────────────────   ║
║                                                                 ║
║   ┌────────────────────┐                                        ║
║   │ #1 DB Schema       │                                        ║
║   │ 3 – 5 – 10 d       │──────────────────────┐                 ║
║   └────────────────────┘                       │                ║
║                                                ▼                ║
║   ┌────────────────────┐           ┌────────────────────┐       ║
║   │ #3 Frontend         │─────────▶ #2 API Endpoints    │──┐    ║
║   │ 7 – 10 – 18 d       │          │ 5 – 8 – 15 d       │  │    ║
║   └────────────────────┘           └────────────────────┘  │    ║
║                                            │               │    ║
║                                            ▼               │    ║
║                                   ┌────────────────────┐   │    ║
║                              ┌───▶ #4 Auth & Authz     │   │    ║
║                              │    │ 4 – 6 – 12 d       │   │    ║
║                              │    └────────────────────┘   │    ║
║                              │             │               │    ║
║                              │             ▼               ▼    ║
║                              │    ┌──────────────────────────┐  ║
║                              │    │ #5 Integration Tests     │  ║
║                              │    │ 3 – 5 – 8 d              │  ║
║                              │    └──────────────────────────┘  ║
║                              └────────────────────────────┘.    ║
║                                                                 ║
║  Drag a node to reposition. Drag from a node's edge to another  ║
║  node to add a dependency.                                      ║
╚═════════════════════════════════════════════════════════════════╝
```

Nodes are repositioned by drag. A dependency edge is drawn by hovering a node's right edge until an arrow cursor appears, then dragging to the target. Clicking a node opens the task editor slide-over.

---

### 6.4 — Run Simulation Panel (Modal Dialog)

Clicking **▶ Run Simulation** opens a centred modal (max-width 520 px):

```
╔═════════════════════════════════════════════════════╗
║  Run Simulation                               [×]   ║
║  ─────────────────────────────────────────────────  ║
║  Iterations      ┌────────────────┐                 ║
║                  │   10 000       │                 ║
║                  └────────────────┘                 ║
║  Random Seed     ┌────────────────┐                 ║
║                  │  (leave blank) │ ← reproducible  ║
║                  └────────────────┘                 ║
║                                                     ║
║  Output Files                                       ║
║  ☐ JSON   ☐ CSV   ☑ HTML report                     ║
║  Save to  ┌──────────────────────────┐ [Browse…]    ║
║           │ ~/Desktop/results        │              ║
║           └──────────────────────────┘              ║
║                                                     ║
║  ─────────────────────────────────────────────────  ║
║  ☑ Validate project first (recommended)             ║
║                                                     ║
║                      [Cancel]  [▶ Run ↵]            ║
╚═════════════════════════════════════════════════════╝
```

After **▶ Run**, the modal closes and the bottom drawer switches to the **Simulation Results** tab, showing a live progress bar fed by WebSocket events:

```
╔══════════════════════════════════════════════════════════════════╗
║  [YAML Preview]  [● Simulation Results]                          ║
║ ───────────────────────────────────────────────────────────────  ║
║  Running…  ████████████████░░░░░░░░  68%  (6,800 / 10,000)       ║
║                                                                  ║
║  ┌─── Calendar Time ────────────────────────────────────────┐    ║
║  │  Mean    578 h  (72 days)                                │    ║
║  │  Median  571 h  (71 days)                                │    ║
║  │  P80     642 h  (80 days)   → 2026-07-30                 │    ║
║  │  P90     682 h  (86 days)   → 2026-08-06                 │    ║
║  └──────────────────────────────────────────────────────────┘    ║
║                                                                  ║
║  ┌─── Effort ───────────────────────────────────────────────┐    ║
║  │  Mean    1 240 person-h  (155 person-days)               │    ║
║  └──────────────────────────────────────────────────────────┘    ║
║                                                                  ║
║  ┌─── Critical Path (most frequent) ────────────────────────┐    ║
║  │  #1 → #2 → #4 → #5 → #6 → #8  (61%)                      │    ║
║  └──────────────────────────────────────────────────────────┘    ║
║                                                                  ║
║  [Open HTML Report ↗]   [Save JSON]   [Save CSV]                 ║
╚══════════════════════════════════════════════════════════════════╝
```

Results fill in as soon as the simulation completes (partial rows are not shown to avoid confusion). The **Open HTML Report ↗** link opens the generated report in a new browser tab.

---

### 6.5 — Risks Section

```
╔═══════════════════════════════════════════════════════════════════╗
║  RISKS                                                    ╌╌╌╌▲   ║
║  Project-wide risks (apply to entire project duration)            ║
║                                                                   ║
║  [+ Add Project Risk]                                             ║
║                                                                   ║
║  ┌────┬──────────────────────────────┬──────┬────────────────┐    ║
║  │ ID │ Risk Name                    │ Prob │ Impact         │    ║
║  ├────┼──────────────────────────────┼──────┼────────────────┤    ║
║  │ R1 │ Key developer leaves         │ 15%  │ +20% duration  │    ║
║  │ R2 │ Requirements change          │ 30%  │ +10 d (abs.)   │    ║
║  └────┴──────────────────────────────┴──────┴────────────────┘    ║
║                                                                   ║
║  ℹ  Task-level risks are added in the task editor (Risks tab).    ║
╚═══════════════════════════════════════════════════════════════════╝
```

Clicking **+ Add Project Risk** or a row expands an inline form immediately below the table header (no dialog):

```
  ┌─ Add Risk ───────────────────────────────────────────────────────┐
  │  Name *         ┌──────────────────────────────────────────┐     │
  │                 │ Key developer leaves                     │     │
  │                 └──────────────────────────────────────────┘     │
  │  Probability    ┌────┐ %                                         │
  │                 │ 15 │                                           │
  │                 └────┘                                           │
  │  Impact Type    ○ Raw hours  ● Percentage  ○ Absolute            │
  │  Impact Value   ┌────┐ % of project duration                     │
  │                 │ 20 │                                           │
  │                 └────┘                                           │
  │  Cost Impact    ┌───────────────────┐  (optional)                │
  │                 │                   │                            │
  │                 └───────────────────┘                            │
  │                               [Discard]  [Add Risk ↵]            │
  └──────────────────────────────────────────────────────────────────┘
```

---

### 6.6 — Uncertainty Tab (inside Task Editor)

```
║  ● Basics   ○ Uncertainty   ○ Risks
║
║  These factors adjust how uncertain this task is.
║  Leaving all at "medium" means no adjustment.
║
║  ┌─────────────────────────────────────────────────────────┐
║  │  Factor                  Level                          │
║  │  ─────────────────────── ─────────────────────────────  │
║  │  Team Experience          ○ Low  ● Medium  ○ High        │
║  │  Requirements Maturity    ○ Low  ○ Medium  ● High        │
║  │  Technical Complexity     ○ Low  ● Medium  ○ High        │
║  │  Team Distribution        ● Colocated  ○ Distributed    │
║  │  Integration Complexity   ○ Low  ● Medium  ○ High        │
║  └─────────────────────────────────────────────────────────┘
║
║  Combined multiplier: ~1.05×
║  ℹ  All "medium" = 1.00× (no adjustment)
```

The multiplier updates live as the user clicks the radio buttons. A subtle colour change (green → amber → red) tracks whether the multiplier is near 1, moderately above, or significantly above 1.

---

### 6.7 — New Project Wizard (First-Run and [+ New])

On first load (no project in URL), or after **[+ New]**, a 3-step wizard fills the full editor area:

```
Step 1 of 3 — Project Basics
─────────────────────────────────────────────────────────
  Project Name *  ┌────────────────────────────────────┐
                  │                                    │
                  └────────────────────────────────────┘
  Start Date *    ┌──────────────┐
                  │ 2026-04-16   │
                  └──────────────┘
  Currency        ┌───────┐  Hourly Rate  ┌───────────┐
                  │ USD ▼ │               │           │ $/hr
                  └───────┘               └───────────┘
  ✓ These settings can be changed later.

                                  [Skip wizard]  [Next →]
```

```
Step 2 of 3 — Add your first task
─────────────────────────────────────────────────────────
  Task Name *     ┌────────────────────────────────────┐
                  │                                    │
                  └────────────────────────────────────┘
  How long might it take?
    Optimistic    ┌────┐  days
                  │    │
                  └────┘
    Most Likely   ┌────┐  days
                  │    │
                  └────┘
    Pessimistic   ┌────┐  days
                  │    │
                  └────┘

  ✓ You can add more tasks and set dependencies after the wizard.

                            [← Back]  [Add Task]  [Finish →]
```

```
Step 3 of 3 — Ready to simulate
─────────────────────────────────────────────────────────
  ✓ "My new project" · 1 task

  Add more tasks in the Tasks section, then click
  ▶ Run Simulation in the toolbar.

                            [← Back]  [Open Project]
```

---

### 6.8 — Command Palette

Pressing `⌘K` (or `Ctrl+K`) opens a centred search-and-command overlay, matching the pattern users know from VS Code:

```
╔══════════════════════════════════════════════════════════╗
║  ┌────────────────────────────────────────────────────┐  ║
║  │ >  Type a command or section name…                 │  ║
║  └────────────────────────────────────────────────────┘  ║
║  ─────────────────────────────────────────────────────   ║
║  ▶ Run Simulation              ⌘↵                        ║
║    Save                        ⌘S                        ║
║    Validate project            ⌘⇧V                       ║
║  ─────────────────────────────────────────────────────   ║
║    Jump to: Tasks                                        ║
║    Jump to: Risks                                        ║
║    Jump to: Cost                                         ║
║    Jump to: Team Members                                 ║
║    Jump to: Advanced                                     ║
║  ─────────────────────────────────────────────────────   ║
║    New project                                           ║
║    Open project…               ⌘O                        ║
║    Import tasks from CSV…                                ║
╚══════════════════════════════════════════════════════════╝
```

---

## 7. Progressive Disclosure Strategy

Same taxonomy as the desktop design; the web version adds sharing URLs.

| User Type | What They See by Default | How to Reach More |
|-----------|--------------------------|-------------------|
| Total beginner | Wizard → Name + Start Date + 1 task | Click "Add Task", fill days |
| First-time planner | Task table | Double-click row → Uncertainty / Risks tabs |
| Project manager | All main sections | Expand ▷ Cost, ▷ Team Members |
| Advanced user | All sections + YAML preview | Edit YAML directly; changes sync to form |
| Power user | YAML preview, share URL, CLI | Export YAML, run `mcprojsim simulate` in terminal |
| Team (server mode) | Own project list on `/projects/` | Open/share project URL |

Sections collapsed by default: Risks, Cost, Team Members, Sprint History, Advanced.  
Sections expanded by default: Project Basics, Tasks.

---

## 8. YAML Sync Architecture

Identical flow to the desktop design. In NiceGUI the in-memory model lives in a Python `AppState` object scoped to the browser session (NiceGUI provides per-client state via `Client`):

```
Form fields  ──(on_change)──▶  AppState.project_dict
                                        │
                                (dict → YAMLDumper)
                                        │
                                        ▼
                               CodeMirror 6 pane
                               (YAML syntax HL,
                                read-write)

CodeMirror edit ──(debounced 400ms)──▶  YAMLParser().parse_dict()
                                                │
                                     (if valid) │
                                                ▼
                               Form fields updated
                               (invalid YAML → red banner,
                                form not cleared)
```

- Form → YAML latency target: ≤ 50 ms (in-process Python serialisation).
- YAML → Form latency target: ≤ 200 ms (parse + 1 round-trip WebSocket message per changed field).
- An undo/redo stack (`collections.deque`, max 50 entries) covers both directions.

---

## 9. Backend API Architecture

Because NiceGUI is built on FastAPI, the same process exposes a REST/WebSocket API alongside the UI. This allows:

- Programmatic access from the CLI, notebooks, or CI scripts.
- Future mobile or third-party clients.

```
mcprojsim-web (uvicorn process)
├── / (NiceGUI app)              ← browser UI
├── /api/v1/validate             POST: project dict → validation result
├── /api/v1/simulate             POST: {project, config, iterations, seed}
│                                WS:   progress events during simulation
├── /api/v1/projects/            GET: list saved projects (server mode only)
├── /api/v1/projects/{id}        GET/PUT/DELETE: CRUD (server mode only)
└── /api/v1/nl/generate          POST: natural-language text → YAML
                                 (wraps nl_parser + mcp_server logic)
```

**Simulation endpoint** uses a `BackgroundTask` (FastAPI) or `asyncio.to_thread` so the event loop is never blocked:

```python
@app.post("/api/v1/simulate")
async def simulate(payload: SimulateRequest) -> SimulateResponse:
    project = YAMLParser().parse_dict(payload.project)
    config  = Config.get_default()
    engine  = SimulationEngine(
        iterations=payload.iterations,
        random_seed=payload.seed,
        config=config,
        show_progress=False,
        progress_callback=payload.ws_callback,   # see §A.1 of ui-design.md
    )
    results = await asyncio.to_thread(engine.run, project)
    return SimulateResponse.from_results(results)
```

---

## 10. Real-Time Progress via WebSocket

NiceGUI's per-client WebSocket connection is used to push progress events without polling:

```python
# UI layer (NiceGUI component)
progress_bar = ui.linear_progress(value=0, show_value=True)
status_label  = ui.label("Starting…")

async def run_simulation():
    def on_progress(completed: int, total: int) -> None:
        pct = completed / total
        # NiceGUI allows cross-thread UI updates via ui.run_javascript or
        # by posting to the client's asyncio queue:
        progress_bar.set_value(pct)
        status_label.set_text(f"{completed:,} / {total:,}")

    engine = SimulationEngine(
        ...,
        progress_callback=on_progress,
        show_progress=False,
    )
    results = await asyncio.to_thread(engine.run, project)
    display_results(results)
```

This requires the `progress_callback` engine change documented in §A.1 of `ui-design.md`; the web and desktop designs share the same prerequisite.

---

## 11. File Handling

- **Download / Upload** replace the desktop "Open File" / "Save File" dialogs.
  - **Upload**: `ui.upload()` accepts `.yaml` and `.toml`; the file is parsed server-side and populates the form.
  - **Download**: a **[↓ Save]** button serialises the current project dict to YAML and streams it as a download with `Content-Disposition: attachment`.
- **Local mode** (`mcprojsim-web --storage-path ~/.mcprojsim`): projects are persisted as YAML files in a user-owned directory. The server exposes a simple file browser at `/projects/`.
- **Server mode**: projects stored in a SQLite database (via SQLAlchemy), one row per project. Sharing is a URL: `http://host/projects/<uuid>`.
- Recent projects list in the left nav footer.
- Auto-save to local storage (browser `IndexedDB`) every 30 seconds as a crash-recovery mechanism.

---

## 12. Natural-Language Input

The web UI adds a first-class **Natural Language** entry point not in the desktop design, powered by the existing `nl_parser.py`:

A button **[✨ Describe project…]** in the toolbar opens a full-width text area:

```
╔══════════════════════════════════════════════════════════════════╗
║  Describe your project in plain English                  [×]    ║
║  ──────────────────────────────────────────────────────────────  ║
║  ┌──────────────────────────────────────────────────────────┐  ║
║  │ We need to build an API for our new customer portal.     │  ║
║  │ The database schema will take 3 to 10 days, most likely  │  ║
║  │ 5. Once that's done, the API endpoints (5–15 days, most  │  ║
║  │ likely 8) and the frontend (7–18 days, likely 10) can    │  ║
║  │ start in parallel. Integration tests follow the API.     │  ║
║  │                                                          │  ║
║  └──────────────────────────────────────────────────────────┘  ║
║                                                                  ║
║                          [Cancel]  [✨ Generate Project ↵]     ║
╚══════════════════════════════════════════════════════════════════╝
```

After generation, the form and YAML preview populate normally. The user can review and edit before running a simulation. This calls `NLProjectParser().parse()` in-process — no LLM, no network call.

---

## 13. Configuration Editor

Accessible via the gear icon `⚙` in the header or via the command palette. Opens as a slide-over from the right, identical in structure to the desktop version's Preferences dialog but rendered as a NiceGUI slide-over panel with tab navigation:

```
[Simulation] [T-Shirt Sizes] [Story Points] [Uncertainty] [Output]
```

Config is serialised to YAML and saved to the storage path (`~/.mcprojsim/config.yaml`). On the next page load it is merged with defaults via `Config.load_from_file()`.

---

## 14. Deployment

### 14.1 — Local (single user)

```bash
pip install mcprojsim[web]
mcprojsim-web
# opens http://localhost:7860 in the default browser
```

Equivalent to the desktop app but running in the browser. Projects saved to `~/.mcprojsim/projects/`.

### 14.2 — Docker (team or cloud)

```dockerfile
# Dockerfile.web
FROM python:3.13-slim
WORKDIR /app
COPY pyproject.toml poetry.lock ./
RUN pip install poetry && poetry install --only main,web --no-root
COPY src/ src/
RUN poetry install --only-root
EXPOSE 7860
CMD ["mcprojsim-web", "--host", "0.0.0.0", "--port", "7860", \
     "--storage-path", "/data"]
VOLUME ["/data"]
```

```bash
docker run -p 7860:7860 -v mcprojsim_data:/data ghcr.io/org/mcprojsim-web
```

### 14.3 — Cloud (Fly.io / Railway / Render one-click)

A `fly.toml` or `render.yaml` can point at the Docker image. Multi-user project storage uses the SQLite backend or a Postgres URL passed via `DATABASE_URL` env var.

### 14.4 — pip dependency group

```toml
[tool.poetry.group.web]
optional = true

[tool.poetry.group.web.dependencies]
nicegui   = ">=2.0"
uvicorn   = {extras = ["standard"], version = ">=0.30"}
aiofiles  = ">=23.0"   # async file I/O for upload/download
```

---

## 15. Implementation Phases

| Phase | Scope |
|-------|-------|
| **0 — Engine prep** | `progress_callback` parameter in `SimulationEngine` (shared with desktop design, §A.1 of `ui-design.md`). |
| **1 — MVP** | NiceGUI app skeleton, header + nav shell, Project Basics form, Task table + task editor (basics tab only), YAML preview (CodeMirror read-only), Run dialog + WebSocket progress bar, Results pane (summary), Download YAML. |
| **2 — Core** | YAML preview read-write with form sync, Upload YAML/TOML, Uncertainty tab in task editor, Risks section, Cost section, CSV task import, Configuration editor. |
| **3 — Advanced** | Dependency graph view (elkjs), Team Members section, Sprint History section, Advanced section. |
| **4 — Polish** | New Project Wizard, Natural-language input, Command palette, Dark/light toggle, Undo/redo, Keyboard shortcuts. |
| **5 — Distribution** | Docker image, Dockerfile.web, `mcprojsim[web]` pip extra, REST API (`/api/v1/`), GitHub Actions image build + push to GHCR. |
| **6 — Server mode** | Multi-user project storage (SQLite → Postgres), shareable project URLs, simple auth (HTTP Basic or OAuth2 via `fastapi-users`). |

---

## Appendix A — NiceGUI Integration Patterns

### A.1 — Per-Client State

NiceGUI scopes all Python objects to the connected client when declared inside `@ui.page('/')`:

```python
from nicegui import ui, app

@ui.page('/')
def index():
    # Each browser tab gets its own AppState instance.
    state = AppState()
    build_ui(state)
```

`AppState` is a plain Python dataclass holding the current project dict, validation errors, and simulation results. No global mutable state is needed.

### A.2 — Cross-Thread UI Updates

The `progress_callback` runs in the simulation worker thread. NiceGUI provides `ui.run_coroutine()` and the `Client.connected` awaitable to push updates safely:

```python
import asyncio
from nicegui import ui

def make_progress_callback(label: ui.label, bar: ui.linear_progress):
    def callback(completed: int, total: int) -> None:
        # Schedule the UI update on the event loop from the worker thread.
        asyncio.get_event_loop().call_soon_threadsafe(
            lambda: (
                bar.set_value(completed / total),
                label.set_text(f"{completed:,} / {total:,}"),
            )
        )
    return callback
```

### A.3 — CodeMirror 6 YAML Editor

NiceGUI's `ui.codemirror` (added in NiceGUI 1.4) wraps CodeMirror 6 natively:

```python
editor = ui.codemirror(
    value=initial_yaml,
    language='yaml',
    theme='dracula',        # matches dark palette
    on_change=on_yaml_edit, # debounced in JS
)
```

`on_yaml_edit` calls `YAMLParser().parse_dict(...)` on a 400 ms debounce and updates the form fields if valid.

### A.4 — elkjs DAG View

elkjs is a pure-JS ELK layout engine. It is injected once as a static asset:

```python
app.add_static_files('/static', 'src/mcprojsim/web/static')
dag_element = ui.html('<div id="dag-container"></div>')
ui.add_head_html('<script src="/static/dag.bundle.js"></script>')
```

Python sends the task graph as JSON to the JS island via `ui.run_javascript()`:

```python
graph_json = json.dumps(build_elk_graph(state.project_dict))
ui.run_javascript(f'window.dagView.load({graph_json})')
```

The JS island emits `CustomEvent` messages back to Python for dependency edits and node repositioning, received via `ui.on('dag-edge-added', handler)`.

---

## Appendix B — Work Breakdown: Implementation Plan

This chapter breaks every feature from §1–§15 and Appendix A into concrete, ordered work items. Each item specifies **what** to build, **where** it lives, and **how to verify** it works.

Convention: work items are numbered `W1-NN` (Phase 1 — MVP) and `W2-NN` (Phase 2 — Full features). Dependencies on earlier items are noted in parentheses where not obvious.

---

### Phase 1 — MVP

**Goal:** A user can open a browser, create a project with tasks (triangular day/hour estimates only), see the generated YAML, run a simulation with a live progress bar, and download the results. No advanced features.

**Phase 1 success criteria:**

- `mcprojsim-web` starts a server, the browser opens automatically.
- A project can be created from scratch using only the form.
- The YAML pane reflects every form change in ≤ 50 ms.
- A simulation runs on a background thread; progress updates in real time via WebSocket.
- The HTML report can be opened in a new tab after the run.
- A `.yaml` file can be downloaded and re-uploaded.

---

#### W1-01 — Engine: Add `progress_callback` Parameter

> Shared prerequisite with the desktop UI. If already done (see `ui-design.md` §A.1 / P1-01), skip to W1-02.

1. In `src/mcprojsim/simulation/engine.py`, add `progress_callback: Optional[Callable[[int, int], None]] = None` to `SimulationEngine.__init__()`.
2. Store as `self._progress_callback`.
3. In `_report_progress()`: if `self._progress_callback is not None`, call `self._progress_callback(completed_iterations, self.iterations)` and return. Leave existing `stdout` logic unchanged for the `None` case.
4. Add a unit test in `tests/test_simulation.py`: construct an engine with a mock callback, run a tiny project (3 tasks, 50 iterations), assert the callback was invoked at least once and the final call has `completed == iterations`.
5. Run full test suite.

**Verify:** `poetry run pytest tests/test_simulation.py -k progress --no-cov -v` passes. All existing tests still pass.

---

#### W1-02 — Project Scaffolding: Directory, Dependencies, Entry Point

1. Create the web source directory: `src/mcprojsim/web/`.
2. Create `src/mcprojsim/web/__init__.py` (empty).
3. Create `src/mcprojsim/web/main.py` with a `main()` function:
   ```python
   import click
   from nicegui import ui

   @click.command()
   @click.option('--host', default='127.0.0.1')
   @click.option('--port', default=7860)
   @click.option('--storage-path', default='~/.mcprojsim', envvar='MCPROJSIM_STORAGE')
   def main(host: str, port: int, storage_path: str) -> None:
       from mcprojsim.web.app import build_app
       build_app(storage_path)
       ui.run(host=host, port=port, title='mcprojsim', reload=False)
   ```
4. Create a minimal `src/mcprojsim/web/app.py` that registers a single `@ui.page('/')` showing "mcprojsim is running".
5. In `pyproject.toml`:
   - Add `[tool.poetry.group.web]` optional group with `nicegui = ">=2.0"`, `uvicorn = {extras = ["standard"], version = ">=0.30"}`, `aiofiles = ">=23.0"`.
   - Add entry point: `mcprojsim-web = "mcprojsim.web.main:main"`.
6. Run `poetry install --with web`.
7. Run `mcprojsim-web` — browser opens at `http://127.0.0.1:7860` showing the placeholder page.

**Verify:** Server starts, browser opens, no import errors. `Ctrl+C` stops cleanly.

---

#### W1-03 — App Shell: Header, Left Nav, Main Area, Bottom Drawer

> Ref: §5 information architecture, §6.1.

1. In `src/mcprojsim/web/app.py`, define `build_app(storage_path: str)` that registers the `@ui.page('/')` route.
2. **AppState** (`src/mcprojsim/web/state.py`): a plain Python dataclass holding `project_dict: dict`, `validation_errors: list[str]`, `simulation_results: Optional[SimulationResults]`. Instantiate one per client inside the page function.
3. **Header row** (full-width, fixed top):
   - Left: logo text "◆ mcprojsim" + current project name label.
   - Centre: toolbar buttons — `[+ New]`, `[↑ Open]`, `[↓ Save]`, divider, `[✓ Validate]`, `[▶ Run Simulation]`. All stubbed.
   - Right: `[🌙]` dark-mode toggle (wires to `ui.dark_mode()` in NiceGUI 2.x).
4. **Body row** (fills remaining viewport height): two columns.
   - Left nav (240 px, fixed, non-scrolling): a `ui.list` with items for each section. Items: "▶ Project Basics", "▶ Tasks (0)", "▷ Risks", "▷ Cost", "▷ Team Members", "▷ Sprint History", "▷ Advanced". Clicking scrolls the right panel to the corresponding section anchor.
   - Right editor area (`flex: 1`, scrollable): empty `ui.column` with `id` anchors for each section.
5. **Bottom drawer** (resizable, defaults to ~30% viewport height):
   - A `ui.splitter` (vertical) between the editor area and the drawer.
   - Drawer contains a `ui.tabs` with two tabs: "YAML Preview" (empty CodeMirror placeholder) and "Simulation Results" (empty placeholder).
   - Small collapse/expand button on the drawer handle.
6. Apply the dark palette from §4.1 via `ui.add_css(...)`. Set `ui.dark_mode(True)` as default. Toggle button flips between dark and light.

**Verify:** Browser shows the shell: header with buttons, left nav with all 7 section entries, empty editor area, bottom drawer with two tabs. Dark/light toggle works. Resize the browser — layout stays coherent above 900 px.

---

#### W1-04 — Project Basics Form Section

> Ref: §6.1 project basics area.

1. Create `src/mcprojsim/web/sections/project_basics.py` with `build_project_basics(state: AppState)`.
2. Build a `ui.card` with a "PROJECT BASICS" label and a `ui.grid` (2-column) of fields:
   - **Project Name** — `ui.input(label='Name *', placeholder='My project')`. Required (validated on blur).
   - **Start Date** — `ui.input(label='Start Date *', placeholder='2026-05-01')` with date-picker popup (NiceGUI `ui.date`).
   - **Hours / Day** — `ui.number(label='Hours / Day', value=8.0, min=0.1, max=24.0, step=0.5)`.
   - **Working Days / Week** — `ui.number(label='Days / Week', value=5, min=1, max=7, step=1)`.
   - **Distribution** — `ui.select(['triangular', 'lognormal'], value='triangular', label='Distribution')`.
3. Each field calls `on_change` → updates `state.project_dict['project']` → calls `regenerate_yaml(state)` (see W1-06).
4. Inline validation: empty project name → red border via `ui.input`'s `:error` binding. Start date in invalid format → error hint.
5. `populate(state)` function: reads `state.project_dict['project']` and sets field values (used by Open/New).

**Verify:** Edit each field. Inspect `state.project_dict['project']` → values match. Empty the name → red border. Tab to next field → hint text shown. Call `populate()` with sample data → fields update.

---

#### W1-05 — Task Table Section

> Ref: §6.1 task table, §5.

1. Create `src/mcprojsim/web/sections/tasks_section.py` with `build_tasks_section(state: AppState)`.
2. Build a `ui.card` with a "TASKS" header row containing `[+ Add Task]`, `[⇄ Graph View]` (disabled in Phase 1), `[⤓ Import CSV]` (disabled in Phase 1) buttons.
3. Task table: `ui.table` with columns: `⠿` (drag handle, no-op in Phase 1), `Task`, `Estimate`, `Dep`.
   - Rows are generated from `state.project_dict.get('tasks', [])`.
   - Estimate cell displays `low–expected–high unit` for triangular estimates; `"M (story)"` for T-shirt (Phase 2); `"5 SP"` for story points (Phase 2).
   - Dep cell shows comma-separated dependency IDs or "—".
4. **[+ Add Task]** generates an auto-ID (`task_001`, `task_002`, …), appends a skeleton task to `state.project_dict['tasks']`, and refreshes the table. Auto-opens the task editor (W1-07) for the new task.
5. Double-clicking a row opens the task editor slide-over (W1-07).
6. Right-click (or a row-action menu) → "Delete Task" with a `ui.notify` confirmation.
7. After any mutation: call `regenerate_yaml(state)` and update the left nav "Tasks (N)" label.

**Verify:** Add 3 tasks with names and estimates. Table shows all 3. Delete one — it disappears and YAML updates. Double-click → task editor opens.

---

#### W1-06 — In-Memory Model & YAML Generation (Form → YAML)

> Ref: §8 (one-way form → YAML in Phase 1).

1. Create `src/mcprojsim/web/yaml_sync.py` with two functions:
   - `regenerate_yaml(state: AppState) -> str`: serialises `state.project_dict` with `yaml.dump(state.project_dict, default_flow_style=False, sort_keys=False, allow_unicode=True)`. Stores the result in `state.yaml_text` and calls `update_yaml_pane(state)`.
   - `update_yaml_pane(state: AppState)`: pushes the new YAML text to the CodeMirror editor element (Phase 1: via `state.yaml_editor.set_value(state.yaml_text)` once the pane exists).
2. Call `regenerate_yaml(state)` from every `on_change` in project basics (W1-04) and every mutation in the task section (W1-05).
3. Target latency: ≤ 50 ms for a 50-task project. (Test on the dev machine with a 50-task dict.)

**Verify:** Add a task named "Backend API". Within 100 ms the YAML pane shows `name: "Backend API"`. Edit the project name → YAML pane updates the `name:` field under `project:`.

---

#### W1-07 — Task Editor Slide-Over (Basics Tab Only)

> Ref: §6.2, basics tab only. Uncertainty and Risks tabs disabled in Phase 1.

1. Create `src/mcprojsim/web/components/task_editor.py` with `open_task_editor(state: AppState, task_index: int)`.
2. Use a NiceGUI `ui.right_drawer` (or `ui.dialog` positioned right) as the slide-over container (600 px wide).
3. **Header**: "Edit Task: {name}" + `[×]` close button.
4. **Tab bar**: three `ui.tabs` items — "Basics" (active), "Uncertainty" (disabled), "Risks" (disabled).
5. **Basics tab fields** (`ui.tab_panel`):
   - **Task ID** — `ui.input(readonly=True)`.
   - **Name** — `ui.input(label='Name *')`, required.
   - **Description** — `ui.textarea`, optional.
   - **Estimate type** — `ui.radio(['Three-Point', 'T-Shirt Size', 'Story Points'], value='Three-Point')`. T-Shirt and Story Points disabled with tooltip "Available in Phase 2".
   - **Three-Point fields** (shown when type = Three-Point): `ui.number` for Optimistic, Most Likely, Pessimistic; `ui.select(['days', 'hours', 'weeks'], value='days')` for unit.
   - Live spark chart: a small inline `ui.plotly` (or `ui.chart`) triangular shape with the three values marked. Updates on any numeric change.
   - **Dependencies** — `ui.list` of `ui.checkbox` items, one per other task (name + ID). Checked = this task depends on that task.
   - **Priority** — `ui.number(label='Priority', value=0, min=0)`.
6. **[Discard]** button: closes drawer without saving.
7. **[Save Task ↵]** button: validates fields (name non-empty, low ≤ expected ≤ high), updates `state.project_dict['tasks'][task_index]`, closes drawer, calls `regenerate_yaml(state)`, refreshes task table.
8. Inline validation: if low > expected or expected > high, show red hint text next to the affected field and disable **[Save Task]**.

**Verify:** Open editor for a task. Change the name and estimates. Save — table row and YAML update. Set low > high — red hints appear, Save is disabled. Discard — original values persist.

---

#### W1-08 — YAML Preview Pane (Read-Only)

> Ref: §8, Appendix A.3. Read-only in Phase 1; bidirectional sync is Phase 2.

1. In `build_app`, after the drawer tabs are created, wire the "YAML Preview" tab panel.
2. Use `ui.codemirror` (NiceGUI ≥ 1.4) configured with:
   - `language='yaml'`
   - `theme='dracula'` (dark) / `'default'` (light, toggled with dark mode)
   - `readonly=True` (Phase 1)
   - `on_change=None`
3. Store a reference in `state.yaml_editor`.
4. `update_yaml_pane` (W1-06) calls `state.yaml_editor.set_value(state.yaml_text)`.
5. Add a **[Copy YAML]** button above the pane (`ui.run_javascript("navigator.clipboard.writeText(...)")`).

**Verify:** Create a project with 2 tasks. YAML pane shows valid, syntax-highlighted YAML. Clicking Copy → clipboard holds the YAML text (verify by pasting).

---

#### W1-09 — Inline and Structural Validation

> Ref: §3 principle 3, §6.4 validate step.

1. Create `src/mcprojsim/web/validation.py` with:
   - `validate_inline(state: AppState) -> list[str]`: field-level checks (non-empty name, date format, low ≤ expected ≤ high on all tasks). Returns a list of human-readable error strings.
   - `validate_structural(state: AppState) -> list[str]`: calls `YAMLParser().parse_dict(state.project_dict)` inside a `try/except ValueError`, returns the error strings from the exception.
2. Wire the **[✓ Validate]** header button:
   - Run `validate_inline` first. If errors, show them in a `ui.notify` list (type "negative").
   - If inline clean, run `validate_structural`. If errors, show them in a slide-down banner at the top of the editor area.
   - If all clean: `ui.notify('✓ Project is valid', type='positive')`.
3. Run `validate_inline` on every form change and mark the Validate button with a subtle warning dot when inline errors exist.

**Verify:** Create a task with min > max. Click Validate → error message names the task. Fix the estimate → warning dot disappears. Create a circular dependency (A → B → A). Click Validate → structural error names the cycle.

---

#### W1-10 — Run Simulation Modal

> Ref: §6.4.

1. Create `src/mcprojsim/web/components/run_dialog.py` with `open_run_dialog(state: AppState)`.
2. `ui.dialog` (centred, max-width 520 px) with:
   - **Iterations** — `ui.number(value=10000, min=100, max=1_000_000)`.
   - **Random Seed** — `ui.input(label='Random Seed (optional)')`. Validated: empty string or positive integer.
   - **Output Files** — `ui.checkbox` for JSON, CSV, HTML. HTML checked by default.
   - **Save to** — `ui.input` for directory path (default `~/mcprojsim-results`). On a local server, this is a server-side path. In browser context, display a note: "Files will be available as downloads after the run."
   - **Validate first** — `ui.checkbox(value=True)`.
3. **[Cancel]** closes the dialog.
4. **[▶ Run ↵]** button:
   a. If "Validate first" is checked, run structural validation. If errors, show them inside the dialog and block.
   b. Close dialog, switch bottom drawer to "Simulation Results" tab, call `run_simulation(state, iterations, seed, formats)` (W1-11).

**Verify:** Open dialog. Change iterations to 500, set seed 42, select CSV only. Click Run → dialog closes, Results tab becomes active. With invalid project and "validate first" checked → errors shown inside dialog, it stays open.

---

#### W1-11 — Simulation Background Thread + WebSocket Progress

> Ref: §10, Appendix A.2.

1. Create `src/mcprojsim/web/simulation_runner.py` with `async def run_simulation(state, iterations, seed, formats)`.
2. Implementation:
   ```python
   async def run_simulation(state, iterations, seed, formats, progress_bar, status_label, results_container):
       project = YAMLParser().parse_dict(state.project_dict)
       config  = Config.get_default()

       def on_progress(completed: int, total: int) -> None:
           asyncio.get_event_loop().call_soon_threadsafe(
               lambda: (
                   progress_bar.set_value(completed / total),
                   status_label.set_text(f'{completed:,} / {total:,}'),
               )
           )

       engine = SimulationEngine(
           iterations=iterations,
           random_seed=seed if seed else None,
           config=config,
           show_progress=False,
           progress_callback=on_progress,
       )
       results = await asyncio.to_thread(engine.run, project)
       state.simulation_results = results
       display_results(state, results_container, formats)
   ```
3. Wire a **[Cancel]** button visible while running: `engine.cancel()` (requires W1-01 / P1-02 cancellation flag — see `ui-design.md` §A.3; if not implemented yet, the Cancel button is a no-op placeholder).
4. Disable the **[▶ Run Simulation]** and **[✓ Validate]** buttons while a simulation is running.

**Verify:** Run a simulation with 10 000 iterations. Progress bar fills from 0 to 100%. Results appear after completion. Run with an intentionally slow project (large iteration count), click Cancel — simulation stops within a few seconds.

---

#### W1-12 — Results Summary Pane

> Ref: §6.4 results section.

1. Create `src/mcprojsim/web/components/results_pane.py` with `display_results(state, container, formats)`.
2. Clears the container and builds:
   - **Calendar Time card**: Mean (hours + days), Median (hours + days), P80 (hours + days + calendar date), P90 (hours + days + calendar date). Days = hours / `state.project_dict['project'].get('hours_per_day', 8)`.
   - **Effort card**: Mean person-hours and person-days.
   - **Critical Path card**: most frequent path as `#id → #id → …  (N%)`.
3. After the cards: `[Open HTML Report ↗]`, `[Save JSON]`, `[Save CSV]` buttons.
   - **Open HTML Report ↗**: `ui.run_javascript(f"window.open('{html_url}', '_blank')")` — serve the HTML file as a static route (W1-13).
   - **Save JSON / CSV**: trigger browser download using `ui.download(path)`.

**Verify:** Run simulation → cards appear with correct values. Cross-check mean calendar time with `poetry run mcprojsim simulate` on the same YAML + seed. Click [Open HTML Report] → browser opens the report in a new tab.

---

#### W1-13 — Export Integration & File Downloads

> Ref: §11 file handling, §9 backend API.

1. After simulation completes, export to a temp directory under `storage_path/runs/<uuid>/`:
   - Call `HTMLExporter.export(results, run_dir / "results.html", config=config, project=project)` if HTML selected.
   - Call `JSONExporter.export(...)` and `CSVExporter.export(...)` for other selected formats.
2. Register a static route: `app.add_static_files('/runs', storage_path + '/runs')`.
3. **[Open HTML Report ↗]** opens `/runs/<uuid>/results.html` in a new tab.
4. **[Save JSON]** and **[Save CSV]** use `ui.download(storage_path + '/runs/<uuid>/results.json')` to stream the file as a browser download.
5. Log the run path to `state` so the results pane can reference it.

**Verify:** Run simulation with all three formats selected. Three files exist in `~/.mcprojsim/runs/<uuid>/`. HTML opens in browser. JSON and CSV trigger downloads. Verify file contents are valid.

---

#### W1-14 — File Upload (Open Project)

> Ref: §11 file handling.

1. Wire the **[↑ Open]** header button.
2. Use `ui.upload(on_upload=handle_upload, auto_upload=True, max_file_size=5*1024*1024)` in a `ui.dialog`. Accept `.yaml`, `.yml`, `.toml`.
3. `handle_upload(e: UploadEventArguments)`:
   a. Read file content from `e.content`.
   b. Detect format by extension.
   c. Call `YAMLParser().parse_file(path)` or `TOMLParser().parse_file(path)` (or `parse_dict()` on pre-loaded content).
   d. On success: set `state.project_dict = parsed.model_dump(...)`, call `populate_all_sections(state)` (repopulates every form widget), call `regenerate_yaml(state)`, close dialog.
   e. On error: `ui.notify(str(e), type='negative')` — dialog stays open.
4. `populate_all_sections(state)` calls the `populate()` function of each section (project basics, task table, and later risks/cost/etc.).

**Verify:** Download a YAML from the app, make a manual edit in a text editor, re-upload → form reflects the edited value. Upload a `.toml` file → loads correctly. Upload a malformed file → error notification appears.

---

#### W1-15 — File Download (Save Project)

> Ref: §11 file handling.

1. Wire the **[↓ Save]** header button.
2. `save_project(state: AppState)`:
   a. Serialise `state.project_dict` to YAML text (`state.yaml_text` or freshly generated).
   b. Write to a temp file `storage_path/tmp/<project_name>.yaml`.
   c. Call `ui.download(path)` to stream it as a browser download.
3. Add dirty tracking: a `state.dirty: bool` flag, set to `True` on any model mutation, `False` after download. Show a `*` indicator next to the project name in the header when dirty.
4. `[+ New]` resets `state.project_dict` to a blank template (project name "Untitled", today's date, no tasks), calls `populate_all_sections(state)` + `regenerate_yaml(state)`, and resets `state.dirty = False`.

**Verify:** Create a project → save → file downloads with correct name and valid YAML content. Edit after save → `*` appears in header. Download again → `*` clears. Click New → form resets, YAML shows minimal template.

---

#### W1-16 — New Project Wizard (Lightweight Version)

> Ref: §6.7. Full wizard (with back/forward step navigation) is Phase 2 (W2-13). This phase implements a simpler version: a modal dialog covering the first two wizard steps.

1. On first page load (check `app.storage.user` key `'has_visited'`), or when **[+ New]** is clicked, open a `ui.dialog` (full-width, no close on outside click).
2. **Step 1** (shown first): Project Name input + Start Date input. **[Skip]** fills defaults and jumps to Step 2. **[Next]** validates and proceeds.
3. **Step 2**: Task Name + Optimistic / Most Likely / Pessimistic fields in days. **[Add Task]** appends to an internal list and clears fields. **[Finish]** (enabled when ≥ 1 task exists): loads the collected data into `state`, closes dialog.
4. Set `app.storage.user['has_visited'] = True` after the wizard completes.

**Verify:** First load → wizard appears. Fill steps, finish → project with tasks is shown in the form and YAML pane. Click **[+ New]** → wizard appears again regardless of `has_visited`.

---

#### W1-17 — Dark / Light Mode Toggle

> Ref: §3 principle 9, §6.1.

1. In the header, wire the `[🌙]` toggle to `ui.dark_mode()`:
   ```python
   dark = ui.dark_mode()
   ui.button(icon='dark_mode', on_click=dark.toggle)
   ```
2. CodeMirror editor theme: switch between `'dracula'` (dark) and `'default'` (light) by updating the `theme` property on the editor element when dark mode changes.
3. Persist the choice in `app.storage.user['dark_mode']` (NiceGUI browser storage) and restore on load.

**Verify:** Toggle dark/light — the full page palette flips, including the CodeMirror pane. Refresh the browser — the preference is remembered.

---

#### W1-18 — Responsive Breakpoint (Narrow Viewport)

> Ref: §5 info architecture.

1. Detect viewport width with a CSS media query (`@media (max-width: 900px)`).
2. At ≤ 900 px:
   - Left nav becomes a horizontal `ui.tabs` bar at the top of the editor area.
   - Bottom drawer moves to a full-width panel below the editor area (not overlapping).
3. Implement using NiceGUI's `ui.add_css` with the breakpoint rules. No JavaScript detection needed.

**Verify:** Narrow the browser to 850 px → left nav collapses to a top tab bar. Widen to 1200 px → left nav reappears on the left.

---

#### W1-19 — Smoke Test Suite (Phase 1)

1. Create `tests/test_web_smoke.py`. Use `pytest` + `httpx` (async) to hit the running server:
   ```python
   import httpx, subprocess, time, pytest

   @pytest.fixture(scope='module')
   def server():
       proc = subprocess.Popen(['poetry', 'run', 'mcprojsim-web', '--port', '17860'])
       time.sleep(3)
       yield 'http://127.0.0.1:17860'
       proc.terminate()
   ```
2. Tests:
   - `test_homepage_loads`: GET `/` → 200 OK, response body contains "mcprojsim".
   - `test_api_validate_valid`: POST `/api/v1/validate` with a minimal valid project dict → 200, no errors.
   - `test_api_validate_invalid`: POST with circular dependencies → 422 or 200 with error list.
   - `test_api_simulate_small`: POST `/api/v1/simulate` with 3 tasks, 100 iterations, seed 42 → 200, `mean` > 0.
   - `test_yaml_round_trip`: serialise a sample project to YAML, POST to `/api/v1/validate` → no errors.
3. Add `httpx` to `[tool.poetry.group.dev.dependencies]`.

**Verify:** `poetry run pytest tests/test_web_smoke.py --no-cov -v` — all pass. Server starts and stops cleanly.

---

#### W1-20 — REST API Endpoints (Phase 1 Subset)

> Ref: §9. The NiceGUI process also exposes FastAPI routes.

1. In `src/mcprojsim/web/api.py`, create a `fastapi.APIRouter` and mount it on the NiceGUI app:
   ```python
   from nicegui import app as nicegui_app
   nicegui_app.include_router(router, prefix='/api/v1')
   ```
2. Implement endpoints:
   - `POST /api/v1/validate`: accepts `{"project": dict}`, returns `{"valid": bool, "errors": list[str]}`.
   - `POST /api/v1/simulate`: accepts `{"project": dict, "iterations": int, "seed": int | null}`, runs simulation synchronously (short iterations only — add a max of 5 000 for the API; GUI uses WebSocket for long runs), returns `{"mean": float, "median": float, "p80": float, "p90": float, "effort_mean": float}`.
   - `GET /api/v1/health`: returns `{"status": "ok", "version": mcprojsim.__version__}`.
3. All endpoints validate input via Pydantic models; return 422 with detail on schema violations.

**Verify:** `curl -X POST http://127.0.0.1:7860/api/v1/validate -H 'Content-Type: application/json' -d '{"project": {...}}' ` → valid JSON response. Health endpoint returns 200.

---

### Phase 2 — Full Features

**Goal:** All features described in §1–§15 are implemented. The app covers the full `mcprojsim` YAML schema: all estimate types, risks, cost, constrained scheduling, sprint planning, bidirectional YAML editing, CSV import, configuration editor, complete wizard, DAG view, command palette, and Docker packaging.

**Phase 2 success criteria:**

- Every YAML field supported by `mcprojsim` can be edited in the form.
- Editing YAML directly in the pane updates the form without a full refresh.
- The dependency graph view shows the project DAG interactively.
- All Phase 1 smoke tests still pass.
- `docker build` produces a working image.

---

#### W2-01 — T-Shirt Size & Story Point Estimate Modes

> Ref: §6.2 estimate alternatives.

1. In `task_editor.py`, enable the "T-Shirt Size" and "Story Points" radio options.
2. **T-Shirt mode**: show a `ui.radio` row: `XS S M L XL XXL`. Below it, a `ui.select` for category (populated from `Config.get_default()`). Hide the three-point numeric fields.
3. **Story Points mode**: show a single `ui.select` or `ui.number` for the point value (Fibonacci choices: 1, 2, 3, 5, 8, 13, 21). Hide the three-point fields.
4. When estimate type changes, swap the visible sub-panel (use `ui.conditional` or `show`/`hide` helpers).
5. `to_dict()` emits `{t_shirt_size, category}`, `{story_points}`, or `{low, expected, high, unit}` depending on the selected mode.
6. `populate()` detects which keys are present in the task dict and selects the correct mode.
7. Update the task table `Estimate` cell display: T-shirt → `"M (story)"`, story points → `"5 SP"`.
8. Inline validation: when T-shirt or story points are selected, ensure `unit` is NOT emitted.

**Verify:** Create a task with T-shirt M. YAML shows `t_shirt_size: "M"`, no `unit`. Reopen task → T-shirt selected, M highlighted. Run simulation → resolves correctly. Switch to story points → YAML updates.

---

#### W2-02 — Uncertainty Tab (Task Editor)

> Ref: §6.6.

1. In `task_editor.py`, enable the "Uncertainty" tab.
2. Build a table of 5 factor rows. Each row: factor label + 3 `ui.radio` buttons (Low / Medium / High), except Team Distribution (2 options: Colocated / Distributed).
3. Below the table: a `ui.label` showing "Combined multiplier: ~X.XX×". Compute from `Config.get_default().uncertainty_multipliers` on each change. Apply a colour: green (≤ 1.05), amber (1.05–1.3), red (> 1.3).
4. `to_dict()` emits `uncertainty_factors: {...}` only for factors that differ from medium/colocated defaults. If all default → key omitted.
5. `populate()` reads task dict factors and sets radio buttons; missing keys → default (medium/colocated).

**Verify:** Set experience "low" and complexity "high" → multiplier updates live to ~1.15×. Save → YAML shows only the two non-default factors. Reset all to defaults → key absent from YAML.

---

#### W2-03 — Task-Level Risks (Risks Tab in Task Editor)

> Ref: §6.2 Risks tab.

1. In `task_editor.py`, enable the "Risks" tab.
2. Show a mini risk table (same structure as project-level risks W2-04).
3. Inline risk editor (no dialog — expand a form row below the table header on `[+ Add Risk]`):
   - Name, Probability (%), Impact Type (radio), Impact Value, optional Cost Impact.
   - `[Discard]` / `[Add Risk ↵]` buttons.
4. Task risks are stored under `task['risks']` in the dict. `to_dict()` includes them only if non-empty.

**Verify:** Add a risk to a task. YAML shows `risks:` nested under the task. Remove it → key disappears. Verify risk fires during simulation (run with high probability risk, confirm mean is elevated).

---

#### W2-04 — Project-Level Risks Section

> Ref: §6.5.

1. Create `src/mcprojsim/web/sections/risks_section.py` with `build_risks_section(state)`.
2. Add to editor area below the Tasks section. Left nav entry "▷ Risks (N)" collapsed by default.
3. "PROJECT-WIDE RISKS" card with `[+ Add Project Risk]` and a `ui.table` (ID, Name, Probability, Impact).
4. Clicking `[+ Add Project Risk]` or a row expands an inline form immediately below the button (no separate dialog) using `ui.expansion` or `show`/`hide`:
   - Name, Probability (%), Impact Type (Raw hours / Percentage / Absolute), Impact Value, optional Cost Impact.
   - `[Discard]` / `[Add Risk ↵]` buttons.
5. Double-click a row → same inline form, pre-filled for editing.
6. Right-click or row action → "Delete" with `ui.notify` confirm.
7. Project risks serialise to a top-level `project_risks:` list in the project dict.
8. Left nav badge "Risks (N)" updates after every add/delete.

**Verify:** Add two risks. YAML shows top-level `project_risks:`. Delete one → YAML updates, badge shows "(1)". Inline form: submit without a name → field turns red, submit blocked.

---

#### W2-05 — Cost Section

> Ref: §5 goals, cost support.

1. Create `src/mcprojsim/web/sections/cost_section.py` with `build_cost_section(state)`.
2. Left nav "▷ Cost" collapsed by default.
3. Card fields:
   - **Enable cost tracking** — `ui.switch`. All other fields disabled when off.
   - **Currency** — `ui.select` (USD, EUR, GBP, SEK, …).
   - **Default Hourly Rate** — `ui.number` with currency prefix.
   - **Overhead Rate** — `ui.number` (0–100, suffix %).
   - **Project Fixed Cost** — `ui.number`, optional.
   - **Target Budget** — `ui.number`, optional.
4. **Secondary Currencies** `ui.expansion` (collapsed by default):
   - `[+ Add Currency]` → appends a row to a mini table: Currency, Rate to primary, FX Overhead %.
   - Rows deleteable.
5. Info note: "Per-task hourly rates are set in the task editor."
6. When enabled: `cost:` section appears in YAML. When disabled: entire `cost:` key absent.
7. Also wire `fixed_cost` field in the task editor Basics tab (show a `ui.number` field, initially hidden; show only when cost tracking is enabled in state).

**Verify:** Enable cost tracking, set $125/hr. YAML shows `cost:` section. Add secondary EUR currency → appears in YAML. Disable → `cost:` key absent. Task editor Basics tab shows cost field when cost enabled.

---

#### W2-06 — Team Members Section

> Ref: §5.7 of `ui-design.md`.

1. Create `src/mcprojsim/web/sections/team_section.py` with `build_team_section(state)`.
2. Left nav "▷ Team Members" collapsed by default.
3. Card contents:
   - `[+ Add Team Member]` button.
   - `ui.table`: Name, Experience (1–3 stars display), Availability (%), Hourly Rate.
   - **Scheduling Mode** — `ui.radio(['Dependency only', 'Resource-constrained'], value='Dependency only')`.
   - **Two-pass criticality** — `ui.checkbox`. When checked, show `ui.number` for pass-1 iterations.
4. Double-click a row → open team member editor slide-over (W2-07).
5. Right-click / row action → "Delete" with confirmation.
6. Team data serialises to `resources:` in the project dict.

**Verify:** Add two members. YAML shows `resources:`. Switch to resource-constrained → `constrained: true` appears. Enable two-pass → appears in config. Run simulation with members assigned → no crash.

---

#### W2-07 — Team Member Editor Slide-Over

> Ref: §5.7 member editor.

1. Create `src/mcprojsim/web/components/team_member_editor.py` with `open_team_member_editor(state, member_index)`.
2. Use a `ui.right_drawer` or `ui.dialog` with fields:
   - Name, Experience (1–3 `ui.radio`), Productivity (`ui.number`, default 1.0), Availability (%), Calendar (`ui.select` listing defined calendars + "default"), Hourly Rate.
   - **Absence** section (`ui.expansion`): Sickness probability (%), Planned absence date ranges (mini table with From/To date pickers + `[+ Add]` / `[×]` per row).
3. Assign to tasks: in the task editor Basics tab, add a `ui.select` listing defined resource names (shown only if `state.project_dict.get('resources')` is non-empty).
4. `[Save]` / `[Discard]` buttons.

**Verify:** Add a member with a sickness probability, absence date, and calendar. YAML shows full resource entry. Assign the member to a task → `resources: [member_name]` appears in that task's YAML.

---

#### W2-08 — Calendar Editor

> Ref: §5.7 calendars sub-section.

1. Create `src/mcprojsim/web/components/calendar_editor.py`.
2. In the Team Members section, a `ui.expansion` "Calendars" shows existing calendars and a `[+ Add Calendar]` button.
3. `[+ Add Calendar]` opens a `ui.dialog`:
   - Calendar Name, Working Hours (start/end `ui.time`), Working Days (7 `ui.checkbox`es Mon–Sun), Holidays (date list with `[+ Add]` / `[×]`).
4. Calendars serialise to `calendars:` in the project dict.

**Verify:** Create a calendar with Tue–Sat working days and one holiday. Assign to a team member → YAML shows `calendar: my_calendar` on the resource. The `calendars:` key exists at project level.

---

#### W2-09 — Sprint History Section

> Ref: §5.8 of `ui-design.md`.

1. Create `src/mcprojsim/web/sections/sprint_section.py` with `build_sprint_section(state)`.
2. Left nav "▷ Sprint History" collapsed by default.
3. Card fields:
   - **Enable sprint planning** — `ui.switch`.
   - **Sprint Length** — `ui.number` (weeks).
   - **Capacity Mode** — `ui.radio(['Story Points', 'Tasks'])`.
   - **Velocity Model** — `ui.radio(['Empirical', 'Neg-Binomial'])`.
   - Sprint history table: `ui.table` with Sprint ID (auto), Completed, Spillover, Team Size columns. Editable rows.
   - `[+ Add Sprint]` and `[⤓ Import from CSV]` (W2-10).
4. Info label with the 2-row minimum and story-points requirement.
5. Validation: if enabled with < 2 rows → inline warning. If capacity mode is "Story Points" but tasks lack resolvable planning story points → warning.

**Verify:** Enable, add 3 sprints. YAML shows `sprint_planning:` section. Disable → key absent. Import from CSV (W2-10) → table populates.

---

#### W2-10 — CSV Import: Tasks and Sprint History

> Ref: §12 in `ui-design.md`.

1. **Task CSV import**: wire the `[⤓ Import CSV]` button in the Tasks section toolbar.
   - `ui.upload(on_upload=handle_task_csv, accept='.csv')` inside a `ui.dialog`.
   - Parse with `csv.DictReader`. Validate required columns (`name` + estimates or `t_shirt_size`).
   - Show a preview table in the dialog: parsed tasks in a `ui.table`.
   - `ui.radio(['Append', 'Replace'])` choice.
   - `[Cancel]` / `[Import N tasks]` buttons.
   - On import: update `state.project_dict['tasks']`, refresh the task table, call `regenerate_yaml(state)`.
2. **Sprint CSV import** (W2-09): same pattern — `ui.upload` in the Sprint History section, columns `completed`, `spillover`, optional `sprint_id` / `team_size`.

**Verify:** Create a CSV with 5 task rows (name, low, expected, high). Upload → preview shows 5 rows. Import with "Append" → tasks added. Import with "Replace" → old tasks gone. Invalid CSV (missing `name`) → error notification.

---

#### W2-11 — Advanced Section

> Ref: §5.9 of `ui-design.md`.

1. Create `src/mcprojsim/web/sections/advanced_section.py` with `build_advanced_section(state)`.
2. Left nav "▷ Advanced" collapsed by default.
3. Four `ui.expansion` sub-sections inside the card:
   - **Distribution**: `ui.radio(['triangular', 'lognormal'])` + default T-shirt category `ui.select`.
   - **Confidence Levels**: `ui.checkbox` group for P10, P25, P50, P75, P80, P85, P90, P95, P99 + `[+ custom]` to add an arbitrary value.
   - **Probability Thresholds**: Red below `ui.number` + Green above `ui.number`. Validate: red < green.
   - **Project-level Uncertainty Factors**: same 5-factor radio grid as W2-02, but for project defaults.
4. These values serialise to the `simulation:` / `uncertainty:` section within the project dict if they differ from defaults. Otherwise omit.

**Verify:** Set distribution to lognormal → YAML shows `distribution: lognormal`. Add custom percentile 60 → appears in output config. Set thresholds to (40, 80) → YAML updated. Reset all → keys absent.

---

#### W2-12 — Bidirectional YAML ↔ Form Sync

> Ref: §8.

1. Switch `ui.codemirror` from `readonly=True` to `readonly=False`.
2. Wire `on_change=handle_yaml_edit` with a 400 ms debounce (implement via `asyncio.sleep(0.4)` in a task, cancelling the previous pending task on each keystroke).
3. `handle_yaml_edit(value: str)`:
   a. Try `yaml.safe_load(value)`. On `YAMLError`: show a red warning badge on the YAML tab label. Stop.
   b. Try `YAMLParser().parse_dict(data)`. On `ValueError`: show the warning badge with the structural error. Stop.
   c. Both pass: set a `_syncing_from_yaml = True` guard, call `populate_all_sections(state)` with the parsed dict, then clear the guard.
4. Form `on_change` handlers: if `_syncing_from_yaml` is `True`, skip calling `regenerate_yaml` to prevent the feedback loop.
5. Implement an undo/redo stack using a `collections.deque` (max 50 entries) of `(project_dict_snapshot, yaml_text)` tuples:
   - Push a snapshot before every user-initiated change (form or YAML).
   - `[Ctrl+Z]` / `[Ctrl+Shift+Z]` keyboard shortcuts (via `ui.keyboard`) pop the deque and restore state.

**Verify:** Type a new task directly in the YAML pane → form table shows the new task. Edit a task name in the form → YAML pane updates. Type invalid YAML → red badge appears, form unchanged. Undo → previous state restored.

---

#### W2-13 — Full New Project Wizard

> Ref: §6.7. Replaces the Phase 1 lightweight version (W1-16).

1. Replace the W1-16 two-step modal with a proper 3-step wizard:
   - **Step 1**: Project Name + Start Date + optional Currency + optional Hourly Rate. [Skip wizard] sets defaults and goes to Step 3. [Next →] validates and advances.
   - **Step 2**: Task Name + Optimistic/Most Likely/Pessimistic (days). [Add Task] appends to internal list. [← Back] / [Finish →] (enabled when ≥ 1 task added).
   - **Step 3**: Summary — "✓ 'Name' · N task(s)." + instructional text. [← Back] / [Open Project].
2. Implement the step progression with `ui.stepper` (NiceGUI built-in) inside a full-screen `ui.dialog`.
3. On "Open Project": loads collected data into `state`, closes wizard, shows project in main view.

**Verify:** Run through all 3 steps. Back navigation preserves entered values. Finish → project with correct name and tasks. Skip wizard → defaults applied.

---

#### W2-14 — Dependency Graph View (elkjs)

> Ref: §6.3, Appendix A.4.

1. Wire the `[⇄ Graph View]` toggle in the Tasks section toolbar.
2. When toggled on, hide the task table and show a `ui.html('<div id="dag-container" style="width:100%;height:500px;"></div>')` element.
3. Register static assets: `app.add_static_files('/static', 'src/mcprojsim/web/static')`. Place `dag.bundle.js` (pre-built with `esbuild` or included as a vendored file) in that directory. The bundle wraps elkjs + SVG rendering logic.
4. On toggle: call `ui.run_javascript(f'window.dagView.load({json.dumps(build_elk_graph(state.project_dict))})')`.
5. `build_elk_graph(project_dict)` converts the task list to an ELK JSON graph (nodes = tasks, edges = dependencies).
6. The JS island:
   - Renders nodes as rounded rects with task ID, name, estimate text.
   - Renders directed edges with arrowheads.
   - Emits `CustomEvent('dag-node-dblclick', {taskId})` on node double-click.
   - Emits `CustomEvent('dag-edge-added', {from, to})` when user drags a new edge.
   - Emits `CustomEvent('dag-edge-removed', {from, to})` on right-click → remove edge.
7. Python handlers:
   - `dag-node-dblclick` → `open_task_editor(state, index_of(task_id))`.
   - `dag-edge-added` → append dependency to `state.project_dict`, call `regenerate_yaml`.
   - `dag-edge-removed` → remove dependency, call `regenerate_yaml`.
8. On task table changes (add/remove/edit tasks), if graph view is active, push an updated graph JSON to the JS island.

**Verify:** Create 5 tasks with 3 dependencies. Toggle graph view → DAG renders with correct edges. Drag a new edge → YAML shows new dependency. Double-click a node → task editor opens. Toggle back to table view → all data intact.

---

#### W2-15 — Command Palette

> Ref: §6.8.

1. Register a global keyboard shortcut `⌘K` / `Ctrl+K` via `ui.keyboard(on_key=handle_key)`.
2. On trigger: open a centred `ui.dialog` styled as a command palette:
   - A `ui.input` search field (auto-focused, placeholder "Type a command…").
   - A `ui.list` below the field, initially showing all commands (see §6.8 for full list).
   - Filter the list in real time as the user types (substring match on command labels).
3. Commands:
   - **▶ Run Simulation** (⌘↵) — trigger run flow.
   - **Save** (⌘S) — trigger download.
   - **Validate project** (⌘⇧V) — trigger validation.
   - **Jump to: Tasks / Risks / Cost / Team Members / Advanced** — scroll + expand the target section.
   - **New project** — trigger new flow.
   - **Open project…** (⌘O) — open upload dialog.
   - **Import tasks from CSV…** — open CSV import dialog.
4. Clicking or pressing Enter on a command executes it and closes the palette.
5. Pressing Escape closes without executing.

**Verify:** Press ⌘K → palette opens. Type "run" → only Run Simulation visible. Press Enter → simulation modal opens. Press ⌘K → type "risk" → "Jump to: Risks" appears → select → risks section scrolls into view.

---

#### W2-16 — Configuration Editor (Preferences Slide-Over)

> Ref: §13.

1. Add a gear icon `⚙` in the header. Clicking opens a `ui.right_drawer` (full-height, 480 px wide) with a `ui.tabs` header:
   - **Simulation** tab: Default Iterations, Max Stored Paths.
   - **T-Shirt Sizes** tab: `ui.table` for each size (XS–XXL) with Low, Expected, High editable cells. Default Category select, Unit select.
   - **Story Points** tab: similar table for point values.
   - **Uncertainty** tab: multiplier matrix (factor × level). Editable cells.
   - **Output** tab: histogram bins, default percentiles.
2. Config file row at bottom: path display + `[Browse…]` (upload) + `[Save Config]` + `[Reset to Defaults]`.
3. On open: populate from `Config.get_default().model_dump()`, deep-merged with any loaded config file.
4. On Save: build dict from form → `Config.model_validate(merged)` for validation → serialise to YAML → download as `mcprojsim-config.yaml` + store in `app.storage.user['config']`.
5. On Reset: repopulate from `Config.get_default()`.
6. Pass the current config to `SimulationEngine` on every run.

**Verify:** Open Preferences → defaults shown. Change default iterations to 5 000, save. Close and reopen → shows 5 000. Run simulation → engine uses 5 000 iterations. Reset → shows 10 000 again.

---

#### W2-17 — Natural-Language Input

> Ref: §12.

1. Add a `[✨ Describe project…]` button in the header (between Validate and Run).
2. Clicking opens a full-width `ui.dialog` with a `ui.textarea` (10 rows, placeholder as shown in §12) and `[Cancel]` / `[✨ Generate Project ↵]` buttons.
3. On generate:
   a. Call `from mcprojsim.nl_parser import NLProjectParser; result = NLProjectParser().parse(text)` in `asyncio.to_thread`.
   b. On success: set `state.project_dict` from the parsed project, call `populate_all_sections`, `regenerate_yaml`, close dialog.
   c. On failure: `ui.notify(str(e), type='negative')`.
4. Show a spinner while processing.

**Verify:** Enter a plain-English description of a 4-task project with dependencies. Click Generate → form populates with the parsed tasks. YAML preview shows valid YAML. Run simulation → no errors.

---

#### W2-18 — Multi-User Project Storage (Server Mode)

> Ref: §11 server mode, §15 phase 6.

1. Add an optional `--storage-mode` flag: `local` (default, YAML files in `storage_path/projects/`) or `db` (SQLite via SQLAlchemy).
2. **Local mode**: projects are YAML files named `<uuid>.yaml`. The `/api/v1/projects/` endpoint lists, reads, and writes them.
3. **DB mode**: projects table: `id (UUID PK)`, `name`, `created_at`, `updated_at`, `yaml_text TEXT`.
4. Add `GET /api/v1/projects/` (list) and `GET/PUT/DELETE /api/v1/projects/{id}`.
5. In the UI, add a "My Projects" view at route `/projects/`:
   - `ui.table` listing project name, last modified.
   - `[Open]` navigates to `/?project_id=<uuid>` and loads the project.
   - `[Delete]` with confirmation.
6. Add `[Share]` button in the header that copies `http://host/projects/<uuid>` to clipboard (server mode only).
7. Add `sqlalchemy = ">=2.0"` and `aiosqlite = ">=0.19"` to the `web` dependency group.

**Verify:** With `--storage-mode db`, create and save two projects. List endpoint returns both. Navigate to `/projects/` → both shown. Open one → form loads. Share URL in another tab → same project loads.

---

#### W2-19 — Docker Image

> Ref: §14.2.

1. Create `Dockerfile.web` in the repo root:
   ```dockerfile
   FROM python:3.13-slim
   WORKDIR /app
   COPY pyproject.toml poetry.lock ./
   RUN pip install poetry && poetry install --only main,web --no-root
   COPY src/ src/
   RUN poetry install --only-root
   EXPOSE 7860
   CMD ["mcprojsim-web", "--host", "0.0.0.0", "--port", "7860", \
        "--storage-path", "/data"]
   VOLUME ["/data"]
   ```
2. Add a `.dockerignore` excluding `.venv`, `tests/`, `docs/`, `dist/`, `htmlcov/`, `.git/`.
3. Build locally: `docker build -f Dockerfile.web -t mcprojsim-web .`.
4. Run: `docker run -p 7860:7860 -v mcprojsim_data:/data mcprojsim-web`.
5. Add a GitHub Actions workflow `docker.yml`:
   - Trigger: `push` to `main` and on release tags.
   - Build and push to `ghcr.io/<org>/mcprojsim-web:<tag>`.
   - Tag both `latest` and the version tag.

**Verify:** `docker build` completes without errors. `docker run` starts the server. Open `http://localhost:7860` → app loads. Create a project, run simulation → works. Restart container with the same volume → project data persists.

---

#### W2-20 — Full Integration Test Suite (Phase 2)

1. Extend `tests/test_web_smoke.py` with Phase 2 coverage:
   - `test_api_simulate_with_tshirt`: POST a project with T-shirt estimates to `/api/v1/simulate` → 200, `mean` > 0.
   - `test_api_simulate_with_risks`: POST a project with a 100% probability risk → `mean` is elevated vs same project without risks.
   - `test_api_nl_generate`: POST natural-language text to `/api/v1/nl/generate` → 200, response contains `tasks` list.
   - `test_api_project_crud` (server mode): create, read, update, delete a project via `/api/v1/projects/`.
2. Run with coverage: `poetry run pytest tests/test_web_smoke.py --cov=src/mcprojsim/web --cov-report=term-missing`.
3. Aim for ≥ 80% coverage of `src/mcprojsim/web/`.

**Verify:** `poetry run pytest tests/test_web_smoke.py --no-cov -v` — all pass. Coverage report shows ≥ 80% on web source files.
