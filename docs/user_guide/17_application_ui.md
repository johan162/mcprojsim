# Desktop Application UI

The `mcprojsim` desktop application lets you create, edit, validate, and simulate project files through a graphical interface. No knowledge of YAML is required — you fill in forms, the application generates the project file for you, and you can run a full Monte Carlo simulation without opening a terminal.

This chapter covers the purpose of the tool, how to install and launch it, and how to use every part of the interface.

---

## Purpose and scope

The CLI is the primary interface for `mcprojsim`, and it works well for users who are comfortable writing YAML and running commands in a terminal. The desktop UI is designed for a different situation: when you want to explore the tool interactively, onboard a colleague who is not comfortable with YAML, or build a project incrementally and immediately see the YAML taking shape.

| Feature | CLI | Desktop UI |
|---------|-----|------------|
| Create a project from YAML | ✓ | ✓ |
| Create a project from natural language | ✓ (`generate`) | ✗ (open the generated YAML) |
| Edit tasks through a form | ✗ | ✓ |
| Inline field validation | ✗ | ✓ |
| Run a simulation | ✓ | ✓ |
| View results summary | ✓ (terminal output) | ✓ (results pane) |
| Open the HTML report | ✓ (open manually) | ✓ (one-click from results) |
| Work on multiple projects | ✓ | ✓ (file menu, recent files) |

The YAML preview pane is always visible so you can see exactly what the application is generating. Experienced users can copy that YAML and work with it directly in the CLI.

---

## Installation

The desktop UI requires `PySide6`, which is declared as an optional dependency group so it does not affect users who only need the CLI.

### From a Poetry checkout

If you have the project checked out and use Poetry, install the `ui` group:

```bash
poetry install --with ui
```

### With pip

```bash
pip install "mcprojsim[ui]"
```

!!! note "PySide6 is a large download"
    PySide6 ships the full Qt runtime and is approximately 150 MB. The download and install step takes a minute or two on a typical connection. This only happens once.

---

## Starting the application

After installation, run:

```bash
mcprojsim-ui
```

A window titled **mcprojsim** opens. If you have used the application before, it restores the window size and position from the last session.

---

## Window layout

The window is divided into three areas.

```
┌─────────────────────────────────────────────────────────────────┐
│  Toolbar: [New] [Open] [Save] [Validate] [▶ Run Simulation]      │
├──────────────┬──────────────────────────────────────────────────┤
│              │                                                   │
│  Navigator   │   Form area (changes with navigator selection)   │
│              │                                                   │
│  Project     │                                                   │
│  Details     │                                                   │
│  Tasks       │                                                   │
│  Risks       │                                                   │
│  Resources   │                                                   │
│  Results     │                                                   │
│              │                                                   │
├──────────────┴──────────────────────────────────────────────────┤
│  YAML Preview (syntax-highlighted, read-only)                    │
├─────────────────────────────────────────────────────────────────┤
│  Status bar                                                      │
└─────────────────────────────────────────────────────────────────┘
```

**Toolbar** — houses the most common actions. The **▶ Run Simulation** button opens the run configuration dialog.

**Navigator** — a vertical list of sections. Click a section to switch the form area to it.

**Form area** — shows the editor for the selected section. Edits are reflected immediately in the YAML preview.

**YAML preview** — always shows the current state of the project as valid YAML. It updates in real time as you type. You can copy its content at any time to work with the CLI.

**Status bar** — shows the last action taken (saved, validated, simulation complete, etc.).

The splitter between the form area and the YAML preview is draggable. Drag it down to give more room to the form, or up to see more of the YAML.

---

## Project Details

The **Project Details** section captures the top-level settings for the project.

| Field | Description | Default |
|-------|-------------|---------|
| Name | Short project name (required) | — |
| Start Date | Calendar start date for the project | Today |
| Description | Optional summary | — |
| Hours / Day | Working hours per calendar day | 8 h |
| Working Days / Week | Working days per week | 5 d |

All fields validate inline. The **Name** field turns red and shows an error message if it is blank; the **Save** button and toolbar actions continue to work — validation errors only block the engine validation step, not file saves.

---

## Tasks

The **Tasks** section contains a table of all tasks in the project. Each row shows the task ID, name, estimate, dependencies, and priority.

### Adding a task

Click **+ Add Task**. A dialog opens with a **Basics** tab.

| Field | Description |
|-------|-------------|
| ID | Unique identifier, e.g. `task_1`. Must start with a letter or underscore. |
| Name | Human-readable name. |
| Estimate | Duration in days. |
| Dependencies | Comma-separated list of task IDs that must complete first. |
| Priority | `low`, `medium`, `high`, or `critical`. |
| Fixed Cost | Optional one-time cost for this task (currency units). |
| Notes | Optional free-text notes. |

Fields validate as you type. The **Save** button is disabled until the ID and Name are both valid. IDs must be unique across all tasks.

### Editing a task

Double-click any row, or select it and click **Edit**. The same dialog opens pre-filled with the existing values.

### Deleting a task

Select a row and click **Delete**. The task is removed immediately from the table and from the YAML preview.

### Reordering tasks

Select a row and use **↑** and **↓** to move it. Task order in the file affects display in the results report.

### Dependencies

Enter other task IDs in the **Dependencies** field, separated by commas. The engine validates dependency integrity at simulation time; the UI does not pre-validate referenced IDs so you can enter them before the target tasks exist.

---

## Risks

The **Risks** section shows a placeholder and a prompt to use the YAML preview. Full risk editing forms are planned for a future release.

To add risks now, copy the YAML from the preview pane, add a `risks:` block following the schema in [Project Risks](06_risks.md), and load the file back via **File → Open**.

---

## Resources

The **Resources** section shows a placeholder in the same way as Risks. To add resource definitions and calendar constraints, edit the YAML directly and reload. See [Constrained Scheduling](10_constrained.md) for the full resource/calendar syntax.

---

## YAML preview

The YAML preview at the bottom of the window reflects the entire current project as valid YAML. It is read-only in the UI — edits must go through the forms or through an external text editor and **File → Open**.

The preview is syntax-highlighted: keys appear in sage green, string values in amber, numbers in steel blue, and booleans in muted purple.

!!! tip "Learning the format"
    If you want to understand the YAML schema, build a project through the forms and study the preview. Each form field maps directly to a YAML key. Once you are comfortable you can write project files by hand and use the UI purely for validation and simulation.

---

## Validating the project

Click **Validate** in the toolbar (or press `Ctrl+K`). The application passes the current project through the same parser and model validation that the CLI uses. If validation passes, a green success dialog appears. If it fails, the dialog lists every error with field-level context.

Fix any errors shown, then validate again before running a simulation. The **▶ Run Simulation** dialog has a **Validate project before simulating** checkbox that is checked by default — it runs validation automatically and blocks the simulation if there are errors.

---

## Running a simulation

Click **▶ Run Simulation** in the toolbar. A dialog opens:

| Setting | Description | Default |
|---------|-------------|---------|
| Iterations | Number of Monte Carlo samples | 10 000 |
| Random Seed | Seed for reproducibility. Set to 0 for a random run. | 42 |
| JSON | Export results as JSON | Off |
| CSV | Export results as CSV | Off |
| HTML report | Generate the HTML simulation report | On |
| Output folder | Where to write export files | Project file's folder, or current dir |
| Validate before simulating | Run validation before starting | On |

Click **Run Simulation**. A progress bar appears at the bottom of the window while the simulation runs. You can click **Cancel** in the toolbar to stop it mid-run.

When the simulation completes the navigator switches to the **Results** section automatically.

---

## Results

The **Results** section displays a summary of the last simulation run.

### Calendar Duration

Shows the P10, P50, P90, and mean project duration in days.

| Percentile | Meaning |
|------------|---------|
| P10 | 10 % of simulated runs finished by this date — an optimistic estimate |
| P50 | Half of runs finished by this date — the median |
| P90 | 90 % of runs finished by this date — the conservative buffer date |

See [Interpreting Results](13_interpreting_results.md) for a full explanation of how to use percentile outputs in planning.

### Estimated Cost

Shown only when the project file defines hourly rates or fixed costs. Displays P10, P50, and P90 cost values in the project currency.

### Most Critical Tasks

Lists the tasks that appeared on the critical path most often across all simulation iterations, with their criticality frequency as a percentage. A task at 85 % means the simulation found it on the longest path in 85 out of 100 runs — it is the primary schedule risk driver.

See [Interpreting Results — Critical Path](13_interpreting_results.md#critical-path-analysis) for how to act on this information.

### Opening the HTML report

If you enabled **HTML report** in the run dialog, an **Open HTML Report** button appears in the results pane. Click it to open the full report in your default browser. The report includes histograms, percentile tables, sensitivity analysis, and the complete critical-path breakdown.

---

## File operations

### New project

**File → New** (or `Ctrl+N`) resets the project to an empty skeleton. If there are unsaved changes, the application asks whether to save first.

### Opening a file

**File → Open** (or `Ctrl+O`) opens a file chooser. Select any `.yaml` or `.yml` file that follows the mcprojsim project schema. The forms populate from the file contents immediately.

!!! tip "Opening a generated file"
    Use `mcprojsim generate description.txt -o project.yaml` in a terminal to convert a natural-language description to YAML, then open the resulting file in the desktop UI to review and edit it through the forms before simulating.

### Saving a file

**File → Save** (`Ctrl+S`) saves to the current file. **File → Save As** (`Ctrl+Shift+S`) lets you choose a new location or name. Unsaved changes are indicated by an asterisk in the window title bar.

### Recent files

**File → Recent Files** lists the last ten files you opened. Click any entry to open it directly.

---

## Auto-save and crash recovery

The application automatically saves a recovery copy of the current project every 60 seconds to `~/.mcprojsim/autosave.yaml`. This file is separate from your project file and exists only as a crash recovery measure.

If the application exits without saving (crash or forced quit) and you relaunch it, a dialog asks whether to restore the auto-saved project. Click **Yes** to load it, or **No** to start fresh. The recovery file is deleted as soon as the application starts regardless of your choice.

!!! note "Auto-save is not a substitute for saving your file"
    The recovery file is overwritten every minute. Use **File → Save** regularly to write your project to a permanent location under the name and path you choose.

---

## Keyboard shortcuts

| Action | Shortcut |
|--------|----------|
| New project | `Ctrl+N` |
| Open file | `Ctrl+O` |
| Save | `Ctrl+S` |
| Save As | `Ctrl+Shift+S` |
| Validate | `Ctrl+K` |
| Quit | `Ctrl+Q` |
