Version: 1.0.0

# Extending NL Parser and MCP Server

## Background and Motivation

The `mcprojsim` NL parser was designed to accept a *semi-structured* format that
looks like a simplified YAML written in plain text — section headers plus bullet
points. This made it easy to implement but hard to use, because nobody talks about
projects that way. Real project descriptions arrive as:

- Email threads: "Hi Alice, quick recap — the backend migration should take about
  two weeks once the DB schema is done, then API refactoring is another week…"
- Meeting notes with bullets that are not numbered
- Copy-paste from Jira/Trello/Notion boards with items like `[AUTH-12] Login page - 3 days`
- Slack summaries mixing who, what, and how long in a single sentence
- A Jira ticket description or a project brief document

The goal of this improvement plan is to make the NL parser and MCP server handle this
full class of real-world input while keeping the existing semi-structured format fully
working. The ideal end-state is:

> A PM or developer can paste anything — emails, meeting notes, a Jira backlog copy,
> a PowerPoint outline — and the MCP server will either produce a runnable simulation
> or ask exactly the right clarifying questions to complete one.

Each item below is ordered by impact vs. effort. Each section describes the feature,
its design, the exact code changes required, and acceptance criteria.



## Item 1 — Unnumbered / auto-numbered list → task auto-detection

### Problem

The parser only starts a task when it sees `Task N:` (with a number). Any numbered or
bulleted list that doesn't use that exact keyword is silently dropped to
project-level metadata processing where it either hits a project-name match or is
ignored. This breaks every workflow involving copy-paste from a planning tool.

Examples that currently produce no tasks:

```
1. Design database schema
2. Implement REST API
3. Frontend integration testing
4. Deployment and smoke tests
```

```
- Discovery and requirements
- Database design
- Backend implementation
- Frontend
- QA
- Deployment
```

```
[1] Authentication
[2] User management
[3] Reporting module
```

### Design

Add a two-phase line classification in `parse()`. Phase 1 (current behaviour) checks
for recognized section headers. If no section was matched and the line looks like a
numbered or bulleted list item that carries no other recognized keyword, classify it
as an **implicit task line** and auto-assign the next task number.

An implicit task line satisfies ALL of:
1. Is not already matched by a section header regex
2. Matches one of the auto-task patterns below
3. Is not inside an existing open section (flush first)

**Auto-task trigger patterns:**
```python
_PLAIN_NUMBERED_RE  = re.compile(
    r'^(\d+)\s*[.)\]]\s*(.+)', re.IGNORECASE)           # "1. foo", "2) bar", "[3] baz"
_PLAIN_BULLET_RE    = re.compile(
    r'^[-*•]\s+(.+)', re.IGNORECASE)                     # "- foo", "* bar", "• baz"
_HASH_NUMBERED_RE   = re.compile(
    r'^#\s*(\d+)\s+(.+)', re.IGNORECASE)                 # "# 1 foo" (rare but seen)
```

When `_PLAIN_NUMBERED_RE` matches, preserve the number from the source (group 1).
When `_PLAIN_BULLET_RE` or `_HASH_NUMBERED_RE` matches, use a monotonically
increasing counter.

**Trigger condition:** Only activate when no section is currently open AND no
`Task N:` headers have been seen yet. Once a real `Task N:` header appears, disable
auto-task mode to prevent collisions. This also means auto-task mode is "all or
nothing" per description — mixing explicit and auto-numbered tasks in the same
description is disallowed.

**After the task name is extracted**, subsequent indented lines (indented by at least
2 spaces or a tab) belonging to the same item are treated as task bullet lines,
exactly as today. Lines that are not indented and not themselves matching
an auto-task pattern close the previous task.

```python
# In parse(), after all section header checks fail:
if not current_task and not any_explicit_task_seen:
    m = self._PLAIN_NUMBERED_RE.match(line)
    if m:
        _flush_section()
        task_num = int(m.group(1))
        current_task = ParsedTask(number=task_num, name=m.group(2).strip())
        auto_task_mode = True
        continue
    m = self._PLAIN_BULLET_RE.match(line)
    if m:
        _flush_section()
        current_task = ParsedTask(number=auto_task_counter, name=m.group(1).strip())
        auto_task_counter += 1
        auto_task_mode = True
        continue
```

**Inline properties on the same line** — common in board exports:

```
- Backend API [XL] depends on DB schema
- Frontend (M, after task 2)
- QA: 3–5 days
```

After extracting the task name, scan the remainder of the line for:
- A bracketed or parenthesized size token: `\[?(XS|S|M|L|XL|XXL)\]?`
- A fuzzy t-Shirt size, `probably an M`, `probably M`, `likely an L`, `assume S` should be parsed correctly.
- An inline estimate range (see Item 2)
- A dependency phrase (see Item 3)

This inline scan reuses the same helper methods already used for bullet parsing.

### Files changed

- `nl_parser.py` — add `auto_task_mode: bool`, `auto_task_counter: int`,
  `any_explicit_task_seen: bool` to parse loop state; add the three new class-level
  compiled regexes; add inline-property extraction after name assignment
- `tests/test_nl_parser.py` — new `TestAutoTaskDetection` class

### Acceptance criteria

1. A plain numbered list with no other structure produces one `ParsedTask` per item.
2. Task numbers preserved from source `1. / 2.` lists; auto-assigned from counter for
   bullet lists.
3. `[M]`, `(XL)`, or inline size in parentheses after the task name is parsed as
   `t_shirt_size`.
4. A valid T-Shirt size token on the same line as the task name is parsed even in auto-task mode. 
   For example `probably an M` or `frontend (L)` should set the `t_shirt_size` field of the task.
5. Inline estimate ranges like `3–5 days` or `about 2 weeks` are parsed correctly
   even when on the same line as the task name.
6. When a description mixes `Task 1:` headers with plain bullets, the plain bullets
   are NOT treated as auto-tasks.
7. Indented continuation lines under a plain bullet are parsed as task bullet
   properties (size, estimate, dependency, resources).


## Item 2 — Natural duration phrases and inline estimate ranges

### Problem

Nobody says `Estimate: 3/5/10 days`. People say:

- "a couple of days"
- "about a week"  
- "2–4 days"
- "around 3 to 5 hours"
- "a few weeks"
- "a sprint" (two weeks by default)
- "a month or so"

None of these are currently parsed. Any line containing one of these phrases inside a
task section is silently treated as a task description string.

### Design

#### 2a — Phrase → T-shirt-size mapping

Add a pre-scan for fuzzy duration phrases before the existing size/estimate checks.
Map phrases to canonical T-shirt sizes. Because the sizes already map to calibrated
triangular distributions in `Config`, this is the right abstraction level.

```python
_FUZZY_DURATION_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r'\ba\s*few\s+hours?\b|\bcouple\s+of\s+hours?\b|\ban?\s+hour\s+or\s+two\b', re.I), 'XS'),
    (re.compile(r'\ba\s*day\s+or\s+two\b|\bcouple\s+of\s+days?\b|\ba?\s+few\s+hours?\b', re.I), 'XS'),
    (re.compile(r'\ba?\s*(?:half\s+a?\s*)?day\b|\bone\s+day\b|\ba\s+full\s+day\b', re.I), 'S'),
    (re.compile(r'\b(?:a?\s*few|several|[23])\s+days?\b|\bcouple\s+of\s+days?\b', re.I), 'S'),
    (re.compile(r'\ba?\s*(?:(?:half\s+a?\s*)?week|sprint)\b|\b[45]\s+days?\b', re.I), 'M'),
    (re.compile(r'\b(?:about\s+)?(?:a|one)\s+week\b|\b5\s+(?:working\s+)?days?\b', re.I), 'M'),
    (re.compile(r'\b(?:a?\s*couple\s+of\s+|two\s+|[23]\s*)weeks?\b', re.I), 'L'),
    (re.compile(r'\b(?:a?\s*few|several)\s+weeks?\b|\ba\s+month\s+or\s+(?:so|two)\b', re.I), 'L'),
    (re.compile(r'\b(?:a|one)\s+month\b|\bfour\s+weeks?\b|\ba\s+full\s+month\b', re.I), 'XL'),
    (re.compile(r'\b(?:a?\s*couple\s+of\s+|two\s+)months?\b|\bsix\s+weeks?\b', re.I), 'XL'),
    (re.compile(r'\b(?:a?\s*few|several|[3-6])\s+months?\b|\ba\s+quarter\b', re.I), 'XXL'),
    (re.compile(r'\b(?:half\s+a\s+year|six\s+months)\b', re.I), 'XXL'),
]
```

Add a new helper `_try_parse_fuzzy_duration(text, task) -> bool` that runs each
pattern in order and assigns `task.t_shirt_size` on the first match. Call this helper
inside the task bullet dispatch, before the `_try_parse_estimate` call.

#### 2b — Inline numeric range parse

Extend the existing `_ESTIMATE_RE` to fire **anywhere in the bullet text**, not just
when the line begins with `Estimate:`. The current regex:

```python
r"estimate\s*[:.=]\s*([\d.]+)\s*[-/,]\s*([\d.]+)\s*[-/,]\s*([\d.]+)"
```

Add a complementary pattern that does NOT require the `estimate` keyword:

```python
_INLINE_RANGE_RE = re.compile(
    r'(?:about\s+|around\s+|roughly\s+|~\s*)?'
    r'([\d.]+)\s*(?:[-–—]|to)\s*([\d.]+)'
    r'(?:\s+(hours?|days?|weeks?|h|d|w))?',
    re.IGNORECASE,
)

_INLINE_POINT_WITH_QUALIFIER_RE = re.compile(
    r'(?:about|around|roughly|~|approx(?:imately)?)\s+([\d.]+)'
    r'(?:\s+(hours?|days?|weeks?|h|d|w))?',
    re.IGNORECASE,
)
```

When `_INLINE_RANGE_RE` matches with two numbers (low, high), synthesize `expected`
as `(low + high) / 2`. When `_INLINE_POINT_WITH_QUALIFIER_RE` matches a single
number with a qualifier word, treat it as `expected` and synthesize
`low = expected * 0.7`, `high = expected * 1.5`.

These patterns are applied only inside task bullet/line context, never to
project-level metadata lines, to avoid false positives on version numbers or dates.

#### 2c — "about a sprint" → L (sprint-length aware)

If `sprint_planning` has been parsed and `sprint_length_weeks` is set, dynamically
map "a sprint" to the appropriate size instead of always mapping to M (2 weeks).
This requires the fuzzy duration helper to accept an optional `sprint_weeks` parameter.

#### 2d — Relative date phrases for `start_date`

Currently `Start date:` requires `YYYY-MM-DD`. Add a secondary pattern:

```python
_RELATIVE_DATE_RE = re.compile(
    r'start(?:ing|s)?\s+(?:date\s*[:.=]?\s*)?'
    r'(next\s+(?:monday|tuesday|wednesday|thursday|friday)|'
    r'in\s+(\d+)\s+(?:days?|weeks?)|'
    r'(?:beginning|start)\s+of\s+(?:next\s+)?(?:month|[A-Za-z]+)|'
    r'(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|'
    r'Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)'
    r'(?:\s+\d{1,2})?(?:\s+\d{4})?)',
    re.IGNORECASE,
)
```

Add a `_resolve_relative_date(phrase: str, today: date) -> str | None` helper that
converts the matched phrase to an ISO 8601 string. Handle:
- `next Monday` — find the next occurrence of that weekday from `today`
- `in 2 weeks` — `today + timedelta(weeks=2)`
- `in 5 days` — `today + timedelta(days=5)`
- `beginning of May` / `May 2026` — first day of that month


### Files changed

- `nl_parser.py` — `_FUZZY_DURATION_PATTERNS` list, `_INLINE_RANGE_RE`,
  `_INLINE_POINT_WITH_QUALIFIER_RE`, `_RELATIVE_DATE_RE`; new helpers
  `_try_parse_fuzzy_duration()`, `_try_parse_inline_range()`,
  `_resolve_relative_date()`; updated bullet dispatch in `parse()`
- `tests/test_nl_parser.py` — `TestFuzzyDurations`, `TestInlineRanges`,
  `TestRelativeDates`

### Acceptance criteria

1. `"takes a couple of days"` → `t_shirt_size = "S"`
2. `"about 2–4 days"` → `low=2, expected=3, high=4, unit="days"`
3. `"around 3 weeks"` → `t_shirt_size = "L"` (no number triggers fuzzy map)
4. `"about 10 hours"` (single approximate value) → `low=7, expected=10, high=15, unit="hours"`
5. `"Start date: next Monday"` resolves to the correct ISO date
6. `"starting in 2 weeks"` resolves relative to today
7. A bare number range `"3–5 days"` without qualifier still parses correctly
8. Version numbers like `"v2.4"` and date fragments like `"2026-04"` are NOT parsed
   as estimates.



## Item 3 — Prose-style dependency connectors

### Problem

The current depend pattern requires `Depends on Task 1` or `Depend on Task 2`.
People write dependencies as qualifiers on the task they're describing:

- "API implementation (builds on the DB schema)"
- "after the design phase"
- "once authentication is done"
- "blocked by task 2"
- "requires the data pipeline"
- "following task 3"

None of these are parsed as dependencies today.

### Design

Add a `_PROSE_DEPENDS_RE` that fires inside task bullet text and inline task names:

```python
_PROSE_DEPENDS_RE = re.compile(
    r'(?:'
    r'after\s+|'
    r'following\s+|'
    r'once\s+(?:\w+\s+)?(?:is\s+)?(?:done|complete|finished)\s*[,:]?\s*|'
    r'(?:blocked\s+by|requires?|needs?|depends?\s+on|builds?\s+on|based\s+on)\s+'
    r')(.+)',
    re.IGNORECASE,
)
```

After matching, extract referenced task identifiers from the captured group using the
existing `_TASK_REF_RE = re.compile(r"task\s*(\d+)", re.IGNORECASE)`. If no explicit
`Task N` reference is found, attempt a **name match**: compare the captured phrase
against known task names accumulated so far. Use a case-insensitive prefix or
token-overlap heuristic (≥ 2 tokens in common → match).

The name-matching lookup needs access to tasks already parsed. Since parsing is
sequential from top to bottom, only tasks defined *before* the current task are
searchable. This is a natural limitation that's consistent with how YAML dependency
resolution works downstream.

```python
def _resolve_task_ref_by_name(
    self, phrase: str, known_tasks: list[ParsedTask]
) -> list[str]:
    """Return task numbers (as strings) whose names overlap with phrase."""
    phrase_tokens = set(re.findall(r'\w+', phrase.lower()))
    results = []
    for t in known_tasks:
        name_tokens = set(re.findall(r'\w+', t.name.lower()))
        if len(phrase_tokens & name_tokens) >= 2:
            results.append(str(t.number))
    return results
```

This method is deliberately conservative (requires ≥ 2 matching tokens) to avoid
false-positive dependency injection. A single common word like "API" should not
create a dependency.

### Files changed

- `nl_parser.py` — `_PROSE_DEPENDS_RE`, `_resolve_task_ref_by_name()`, updated
  `_try_parse_depends()` and inline-scan in auto-task extraction
- `tests/test_nl_parser.py` — `TestProseDependencies`

### Acceptance criteria

1. `"- after task 1"` → `dependency_refs = ["1"]`
2. `"- blocked by task 3"` → `dependency_refs = ["3"]`
3. `"- once authentication is done"` with a task named "Authentication" already
   parsed → `dependency_refs` populated with that task's number
4. `"- requires the DB migration"` with a task named "Database migration" → matched
5. A phrase matching only one token (e.g. "- builds on the system") with no task
   named "the" → no dependency added (no false positive)
6. Self-referential text like "this task has dependencies" → no dependency added



## Item 4 — Inline team member extraction

### Problem

The `Resource N: Name` syntax requires explicitly numbered entries. Real input often
reads:

- `Team: Alice, Bob, Carol (part-time)`
- `Assigned to: Alice`
- `Developer: Bob`
- `Alice and Bob will work on this`
- `Engineers: Alice (senior), Bob, Carol`

### Design

Add a **team-block** parser that runs before the existing resource header check.

#### 4a — Team header line

```python
_TEAM_HEADER_RE = re.compile(
    r'(?:team|engineers?|developers?|people|members?|staff|assigned\s*to)\s*[:.=]\s*(.+)',
    re.IGNORECASE,
)
```

When this matches at project level (not inside a section), parse the value as a
comma-separated or `and`-separated list of names. For each name, auto-create a
`ParsedResource` with an auto-assigned number. Attribute modifiers in parentheses
after the name are parsed:
- `(part-time)` → `availability = 0.5`
- `(senior)` or `(lead)` → `experience_level = 3`
- `(junior)` or `(new)` → `experience_level = 1`
- `(0.75)` or `(75%)` → `availability = 0.75`
- `(0.8 FTE)` → `availability = 0.8`

```python
_TEAM_MEMBER_RE = re.compile(
    r'([A-Za-z][A-Za-z\s\-]+?)'                     # name
    r'(?:\s*\(([^)]+)\))?'                           # optional (modifier)
    r'(?:\s*,|\s+and\b|$)',
    re.IGNORECASE,
)

_TEAM_MODIFIER_MAP = {
    'part.time': ('availability', 0.5),
    'half.time': ('availability', 0.5),
    '0.75': ('availability', 0.75),
    'senior': ('experience_level', 3),
    'lead': ('experience_level', 3),
    'junior': ('experience_level', 1),
    'new': ('experience_level', 1),
}
```

#### 4b — `Developer:` / `Assigned to:` single-resource lines

```python
_ASSIGNED_TO_RE = re.compile(
    r'(?:assigned\s+to|developer|engineer|owner|responsible)\s*[:.=]\s*(.+)',
    re.IGNORECASE,
)
```

Inside a task bullet context, this creates a resource if not already known, and wires
`task.resources` to that name.

#### 4c — Name deduplication

Track a `_known_resource_names: dict[str, int]` in `parse()` loop state. When a name
already exists in this map, reuse its number rather than creating a duplicate. Name
comparison is case-insensitive and strips whitespace.

### Files changed

- `nl_parser.py` — `_TEAM_HEADER_RE`, `_TEAM_MEMBER_RE`, `_ASSIGNED_TO_RE`,
  `_TEAM_MODIFIER_MAP`; `_parse_team_line()` helper; updated `parse()` loop;
  `_known_resource_names` state variable
- `tests/test_nl_parser.py` — `TestInlineTeamExtraction`

### Acceptance criteria

1. `"Team: Alice, Bob, Carol (part-time)"` creates three `ParsedResource` entries;
   Carol has `availability = 0.5`
2. `"Engineers: Alice (senior), Bob"` → Alice has `experience_level = 3`
3. `"Assigned to: Alice"` inside a task bullet wires that task's `resources` field
   to Alice and creates a resource entry for Alice if not already present
4. The same name appearing twice (Team line + Assigned to) creates only ONE resource
5. Resource numbers auto-assigned sequentially starting from 1



## Item 5 — `ask_clarifying_questions` MCP tool

### Problem

When the NL parser receives insufficient input — no estimates, no start date, a vague
description — it either raises `ValueError` (no tasks) or produces a YAML with
warnings. The LLM calling the MCP tool has no structured way to ask the user follow-up
questions.

The current flow:
```
user input (vague) → generate_project_file → ValueError or broken YAML → LLM fabricates
```

The desired flow:
```
user input (vague) → ask_clarifying_questions → structured Q&A → generate_project_file → YAML
```

### Design

Add a new MCP tool `ask_clarifying_questions(description: str) -> str` that:
1. Runs `NLProjectParser().parse()` with a try/except
2. Inspects the resulting `ParsedProject` for mandatory and optional gaps
3. Returns a machine-readable JSON-ish block that an LLM can use to drive
   a conversational follow-up

```python
@mcp.tool()
def ask_clarifying_questions(description: str) -> str:
    """Analyse a project description and return structured clarifying questions.

    Use this tool BEFORE generate_project_file when the description is vague,
    has missing estimates, or has no tasks. Present the returned questions to
    the user, collect answers, incorporate them into the description, then
    call generate_project_file with the enriched description.

    Returns a JSON object with:
      - "parsed_summary": brief summary of what was successfully extracted
      - "questions": list of {field, question, why, example} objects
      - "ready_to_generate": bool — true if no blocking gaps remain
    """
```

The inspection logic walks over these checks in order:

| Check | Severity | Question template |
|-------|----------|-------------------|
| `len(project.tasks) == 0` | Blocking | "What are the main tasks or phases of this project? Please list them." |
| Any task with no estimate | Blocking | "How long do you expect [task name] to take? (e.g. 'about a week', '2–5 days', 'M')" |
| `project.start_date is None` | Recommended | "When do you plan to start this project?" |
| `project.name == "Untitled Project"` | Optional | "What is the name of this project?" |
| Tasks have names like "Task 1" (no real name) | Recommended | "Can you give more descriptive names to your tasks?" |
| `project.resources == []` and any task has `resources` referenced | Blocking | "Task X references [resource name] but no team members are defined. Who is on the team?" |
| Dependency ref points to non-existent task number | Blocking | "Task X depends on Task Y, but Task Y is not defined." |
| No sprint history but sprint planning is enabled | Recommended | "Do you have historical sprint data? If so, provide 3–5 past sprint outcomes (story points or tasks completed per sprint)." |

**Output format** is a plain text block that an LLM can parse:

```
PARSED SUMMARY:
3 tasks found. No estimates. No start date.

CLARIFYING QUESTIONS:
[BLOCKING] estimates_missing
  Q: How long do you expect "Design database schema" to take?
  Why: No estimate was found for this task. A simulation requires effort estimates.
  Example: "about a week", "3–5 days", "Size: M"

[BLOCKING] estimates_missing
  Q: How long do you expect "API implementation" to take?
  ...

[RECOMMENDED] start_date_missing
  Q: When do you plan to start this project?
  Why: Without a start date, the simulation cannot produce calendar delivery dates.
  Example: "2026-05-01", "next Monday", "beginning of June"

READY_TO_GENERATE: false
```

The plain text format (not JSON) is chosen because it is friendlier in LLM context
windows and easier for the model to parse and present to users conversationally.

### Files changed

- `mcp_server.py` — new `ask_clarifying_questions` tool function
- `tests/test_mcp_server.py` — `TestAskClarifyingQuestions`

### Acceptance criteria

1. Input with no tasks returns `READY_TO_GENERATE: false` and a blocking question
   about tasks
2. Input with tasks but no estimates returns one blocking question per missing estimate
3. Input with all mandatory fields filled returns `READY_TO_GENERATE: true`
4. Broken dependency references produce a blocking question naming the bad reference
5. The tool never raises an exception — all parse failures are caught and reported
   as questions



## Item 6 — Plain-English result narration

### Problem

The current simulation output from `simulate_from_description` is a block of raw
numbers. A PM asking "when will this project be done?" wants to hear:

> "Based on 10,000 simulations, your project is most likely to finish in about
> **8 weeks** (50% probability). You have a 90% chance of being done by **11 weeks**
> (by 1 July 2026). The database migration and API implementation tasks appear on the
> critical path in 82% of scenarios — delays there cascade directly to the end date."

Not:
```
Mean: 320.00 hours (40 working days)
P50: 305.20 hours
P90: 440.18 hours (55 working days)  (2026-07-01)
```

### Design

Add a `_narrate_results(results, project_name, hours_per_day) -> str` function in
`mcp_server.py` and a `narrative` section in `_format_simulation_output`. The narration
is assembled from template strings, not an LLM call — it must work offline and be
deterministic.

#### Narration components

**1. Opening sentence** — project name + p50

```python
p50_days = math.ceil(results.percentiles[50] / hours_per_day)
p50_weeks = round(p50_days / 5, 1)
opening = (
    f"Based on {results.iterations:,} simulations, "
    f"**{project_name}** is most likely to finish in about "
    f"**{p50_weeks:.0f} weeks** ({p50_days} working days, 50% probability)."
)
```

**2. Confidence corridor** — p80 and p90 with calendar dates

```python
for pct in [80, 90]:
    days = math.ceil(results.percentiles.get(pct, 0) / hours_per_day)
    delivery = results.delivery_date(results.percentiles[pct])
    date_str = f" (by {delivery.strftime('%d %B %Y')})" if delivery else ""
    lines.append(f"- {pct}% confidence: {days} working days{date_str}")
```

**3. Uncertainty characterisation** — coefficient of variation → adjective

```python
cv = results.std_dev / results.mean
if cv < 0.15:    uncertainty = "low"
elif cv < 0.30:  uncertainty = "moderate"
elif cv < 0.50:  uncertainty = "high"
else:            uncertainty = "very high"
```

Sentence: "Estimate uncertainty is **{uncertainty}** (CV={cv:.0%}). 
{If high/very high: 'Consider breaking large tasks into smaller pieces or reducing scope to tighten the range.'}"

**4. Critical path narrative** — top 1–2 critical paths in prose

```python
records = results.get_critical_path_sequences(2)
if records:
    top = records[0]
    pct = top.frequency * 100
    path_names = " → ".join(top.path)  # use task IDs; later map to names if available
    lines.append(
        f"The most common bottleneck sequence is **{path_names}**, "
        f"appearing on the critical path in {pct:.0f}% of simulations."
    )
```

**5. Skewness warning**

```python
if results.skewness > 1.5:
    lines.append(
        "⚠️  The distribution has a long right tail (skewness "
        f"{results.skewness:.1f}). A small number of scenarios run "
        "significantly longer than average — budget for this risk."
    )
```

The `simulate_from_description` tool should append the narration after the existing
structured output block, separated by a `=== Summary ===` header.

### Files changed

- `mcp_server.py` — `_narrate_results()` function, updated `_format_simulation_output()`
- `tests/test_mcp_server.py` — `TestResultNarration`

### Acceptance criteria

1. Output contains a plain-English opening sentence with project name, P50 in weeks
2. P80 and P90 lines include calendar dates when a start date was provided
3. CV < 0.15 → "low", CV > 0.50 → "very high"
4. Critical path appears in prose when simulation produces one
5. Skewness > 1.5 triggers the tail-risk warning
6. When no start date was given, date strings are omitted rather than showing None



## Item 7 — `what_if_scenario` MCP tool

### Problem

Stakeholders don't think in probability distributions. They think in scenarios:
- "What if we hire a second developer?"
- "What if the DB migration takes twice as long?"
- "What if we cut the testing phase?"
- "What happens if we slip the start date by two weeks?"

There is currently no way to invoke a comparison in one MCP call.

### Design

```python
@mcp.tool()
def what_if_scenario(
    base_description: str,
    scenario_description: str,
    iterations: int = 10000,
    config_yaml: str | None = None,
) -> str:
    """Run two simulations and compare the results:  baseline vs. a what-if.

    base_description: the original project description
    scenario_description: a natural language description of what changes
        in the scenario. Examples:
          - "Add a second developer with experience level 2"
          - "Double the estimate for the database migration task"
          - "Remove the performance testing task"
          - "Start date is 2 weeks later"

    The scenario description is applied as a PATCH on top of the base description.
    Changes are described in natural language; the tool interprets them.
    Returns a comparison of P50, P80, and P90 between the two runs,
    plus a plain-English summary of the impact.
    """
```

#### Scenario interpretation

The `scenario_description` is processed by a new `_apply_scenario_patch(base_yaml: str, scenario: str) -> str` function that:

1. Parses the scenario text for a small vocabulary of mutation keywords:

| Pattern | Action |
|---------|--------|
| `add a .* developer` / `add resource .* with ...` | Append a new resource entry |
| `remove task .*` / `drop the .* task` | Remove task from YAML |
| `double the estimate for .*` | Multiply low/expected/high by 2 for matched task |
| `halve the estimate for .*` | Multiply by 0.5 |
| `set estimate for .* to .*` | Replace estimate |
| `start date is .* later` / `delay start by .*` | Offset start_date |
| `push start by N weeks` | Offset start_date by N * 7 days |

2. The mutations operate on the parsed YAML dict (via `yaml.safe_load` →
   modify in Python → `yaml.dump`), not on raw text. This keeps the YAML valid.

3. If a mutation cannot be interpreted (none of the patterns match), the tool returns
   a `SCENARIO_PARSE_ERROR` message explaining what it could not understand, rather
   than silently using the unmodified baseline.

#### Output format

```
=== BASELINE ===
P50: 40 working days  (2026-07-15)
P80: 52 working days  (2026-08-01)
P90: 60 working days  (2026-08-15)

=== SCENARIO: "Add a second developer" ===
P50: 32 working days  (2026-07-05)
P80: 42 working days  (2026-07-18)
P90: 50 working days  (2026-08-01)

=== IMPACT ===
Adding a second developer reduces the median delivery by 8 working days (20%).
P90 improves by 10 days. The additional resource most benefits tasks on the
critical path: "API implementation" and "Frontend integration".
```

The impact section is generated from the delta values using the same narration
templates from Item 6.

### Files changed

- `mcp_server.py` — `what_if_scenario` tool, `_apply_scenario_patch()` helper,
  `_format_comparison_output()` helper
- `tests/test_mcp_server.py` — `TestWhatIfScenario`

### Acceptance criteria

1. `scenario_description = "double the estimate for task 1"` doubles that task's
   `low`/`expected`/`high` values and reruns the simulation
2. `scenario_description = "push start by 2 weeks"` offsets `start_date` by 14 days
3. Impact block always reports delta in working days and percentage
4. An unrecognised scenario returns `SCENARIO_PARSE_ERROR` rather than silently
   running the unmodified baseline
5. Both simulations use the same `random_seed` so results are reproducible



## Item 8 — `refine_project_file` MCP tool

### Problem

Once a YAML has been generated, users want to iterate on it without starting over.
Currently there is no way to say "add a QA task at the end" or "move task 3 to depend
on task 5" through the MCP interface. Users must manually edit the YAML, which defeats
the purpose.

### Design

```python
@mcp.tool()
def refine_project_file(
    project_yaml: str,
    instruction: str,
) -> str:
    """Apply a natural language modification instruction to an existing project YAML.

    instruction examples:
      - "Add a QA task at the end with size M, depends on task 3"
      - "Remove the deployment task"
      - "Make Alice available only 50% of the time"
      - "Add a 20% holiday factor to sprint 4"
      - "Rename task 2 to 'Backend API development'"
      - "Change the estimate for task 1 to 2–4 days"

    Returns the modified YAML, preserving all existing fields not mentioned
    in the instruction.
    """
```

#### Implementation

Load the YAML into a Python dict. Apply a `_refine_dict(data: dict, instruction: str) -> dict` function that dispatches to mutation handlers:

```python
_REFINE_PATTERNS: list[tuple[re.Pattern, Callable]] = [
    (re.compile(r'add\s+(?:a\s+)?(?:new\s+)?task', re.I),     _refine_add_task),
    (re.compile(r'remove\s+(?:the\s+)?task', re.I),           _refine_remove_task),
    (re.compile(r'rename\s+task', re.I),                       _refine_rename_task),
    (re.compile(r'change\s+(?:the\s+)?estimate', re.I),        _refine_change_estimate),
    (re.compile(r'move\s+task.*depends', re.I),                _refine_dependency),
    (re.compile(r'make\s+\w+\s+available', re.I),              _refine_availability),
    (re.compile(r'add\s+(?:a\s+)?(?:new\s+)?resource', re.I), _refine_add_resource),
    (re.compile(r'holiday\s+factor', re.I),                    _refine_sprint_override),
]
```

Each handler function takes `(data: dict, instruction: str) -> dict` and returns the
modified dict. Handler implementations use the same `NLProjectParser` regex helpers for
extracting names, sizes, and estimates from the instruction string.

The new task number for `_refine_add_task` is always `max_existing_task_number + 1`.

After all handlers run, the modified dict is round-tripped through
`yaml.safe_load` + `yaml.dump` with `default_flow_style=False` to normalise
formatting before returning.

If no handler matched the instruction, return an error string:
```
REFINE_ERROR: Could not interpret instruction: "..."
Supported operations: add task, remove task, rename task, change estimate,
  move task dependency, change availability, add resource, add sprint override
```

### Files changed

- `mcp_server.py` — `refine_project_file` tool, `_refine_dict()` dispatcher,
  individual `_refine_*` handler functions
- `tests/test_mcp_server.py` — `TestRefineProjectFile`

### Acceptance criteria

1. `"Add a QA task at the end with size M, depends on task 3"` → new task with
   correct size and dependency appended to the `tasks` list
2. `"Remove the deployment task"` → task with name matching "deployment" is deleted;
   any other task's dependency on that task is also removed
3. `"Make Alice available 50% of the time"` → Alice's `availability` field set to 0.5
4. `"Change the estimate for task 2 to 2–4 days"` → task 2 estimate `low=2, expected=3, high=4`
5. Unrecognised instruction → `REFINE_ERROR` message, original YAML unchanged
6. Output YAML passes `YAMLParser().parse_dict()` without validation errors



## Item 9 — Uncertainty factor inference from prose context signals

### Problem

`Config` has five global uncertainty factors (`team_experience`, `requirements_maturity`,
`technical_complexity`, `team_distribution`, `integration_complexity`) that significantly
affect simulation results but are never populated from NL input. The user must know they
exist and set them manually in a config YAML. Most NL descriptions contain signals that
map directly to these factors:

- "We've never done this kind of work before" → `technical_complexity: high`
- "The team is distributed across 3 time zones" → `team_distribution: distributed`
- "Requirements aren't finalized yet" → `requirements_maturity: low`
- "Our senior engineers have shipped similar systems before" → `team_experience: high`

### Design

Add a `_infer_uncertainty_factors(text: str) -> dict[str, str]` function in
`nl_parser.py` that scans the full input text (not per-line) for signals and returns
a dict of factor overrides.

```python
_UNCERTAINTY_SIGNALS: list[tuple[re.Pattern, str, str]] = [
    # (pattern, factor_name, level)
    (re.compile(r"new\s+to|never\s+done|no\s+experience|greenfield|first\s+time", re.I),
        "team_experience", "low"),
    (re.compile(r"experienced|senior\s+team|done\s+(?:this\s+)?before|familiar\s+with", re.I),
        "team_experience", "high"),
    (re.compile(r"requirements?\s+(?:aren'?t?|not\s+|un)(?:clear|finali[sz]ed|defined|stable)|"
                r"changing\s+requirements?|scope\s+(?:is\s+)?unclear", re.I),
        "requirements_maturity", "low"),
    (re.compile(r"requirements?\s+(?:are\s+)?(?:clear|finali[sz]ed|well.defined|stable|locked)", re.I),
        "requirements_maturity", "high"),
    (re.compile(r"complex\s+integrat|many\s+systems?|many\s+dependencies|"
                r"tightly\s+coupled|legacy\s+integrat", re.I),
        "integration_complexity", "high"),
    (re.compile(r"simple\s+integrat|standalone|no\s+(?:external\s+)?integrat|self.contained", re.I),
        "integration_complexity", "low"),
    (re.compile(r"distributed\s+team|across\s+time\s*zones?|remote\s+team|"
                r"offshore|multiple\s+(?:locations?|offices)", re.I),
        "team_distribution", "distributed"),
    (re.compile(r"same\s+(?:office|room|floor)|co.located|onsite\s+team", re.I),
        "team_distribution", "colocated"),
    (re.compile(r"new\s+tech|cutting.edge|never\s+used\s+before|experimental|"
                r"proof.of.concept|prototype", re.I),
        "technical_complexity", "high"),
    (re.compile(r"standard\s+(?:stack|tech)|proven\s+tech|well.understood|"
                r"existing\s+codebase|maintenance", re.I),
        "technical_complexity", "low"),
]
```

The function returns a dict only for factors where a signal was found. When
conflicting signals are found for the same factor (both "experienced" and "no
experience" in the same text), the last match wins — but a warning is added to
`ParsedProject.warnings` (a new optional field, see below).

**`ParsedProject` warnings field — new field:**

```python
@dataclass
class ParsedProject:
    ...
    warnings: list[str] = field(default_factory=list)  # non-blocking parse notices
    inferred_uncertainty_factors: dict[str, str] = field(default_factory=dict)
```

The inferred factors are not directly embedded in the YAML output (they belong in a
config, not a project file). Instead, `to_yaml()` emits them as a YAML comment block
at the top:

```yaml
# Inferred uncertainty factors (add to config YAML to apply):
#   team_experience: low
#   technical_complexity: high
#   team_distribution: distributed
project:
  name: "..."
  ...
```

The MCP `generate_project_file` tool appends a note to its output when factors were
inferred:

```
NOTE: The following uncertainty factors were inferred from your description.
To apply them, add this to your config YAML (or pass as config_yaml parameter):

uncertainty_factor_levels:
  team_experience: low
  technical_complexity: high
```

The `simulate_from_description` tool automatically applies inferred factors to the
`Config` object before running the simulation.

### Files changed

- `nl_parser.py` — `_UNCERTAINTY_SIGNALS` list, `_infer_uncertainty_factors()`,
  `warnings` and `inferred_uncertainty_factors` fields on `ParsedProject`,
  `to_yaml()` comment block, call site in `parse()`
- `mcp_server.py` — apply inferred factors in `_prepare_project_from_description()`
- `tests/test_nl_parser.py` — `TestUncertaintyInference`

### Acceptance criteria

1. `"We've never built microservices before"` → `technical_complexity: high`
2. `"The team is distributed across EU and US"` → `team_distribution: distributed`
3. `"Requirements aren't finalized"` → `requirements_maturity: low`
4. YAML output contains comment block with inferred factors
5. `simulate_from_description` uses inferred factors automatically
6. Conflicting signals add a warning to `ParsedProject.warnings`; no exception raised



## Item 10 — Two-tier LLM pre-processor architecture

### Problem

The current `generate_project_file` tool receives the raw user message and feeds it
directly to the regex-based parser. For truly messy input (email prose, meeting notes),
the parser misses almost everything.

The MCP server is called by an LLM (Claude, GPT). That LLM already has powerful
natural language understanding. The current architecture doesn't use it.

### Design

Add a `preprocess_description` MCP tool that acts as a normalisation step. Its job is
not to parse — it produces output that the existing parser can reliably handle. The
tool docstring serves as a prompt template for the calling LLM.

```python
@mcp.tool()
def preprocess_description(raw_text: str) -> str:
    """Normalize a messy project description into the semi-structured format
    expected by generate_project_file.

    Call this tool when raw_text is:
    - An email or Slack message
    - Meeting notes with mixed formatting
    - A copy-paste from a planning tool
    - Any text that mixes narrative prose with task descriptions

    This tool DOES NOT call the parser — it returns a normalized text string
    that you should then pass to generate_project_file or ask_clarifying_questions.

    The normalized format uses:
      Project name: <name>
      Start date: YYYY-MM-DD
      Task 1: <task name>
      - Size: XS/S/M/L/XL/XXL  OR  Estimate: low/expected/high days
      - Depends on Task N
      Resource 1: <name>
      - Experience: 1/2/3
      - Availability: 0.0-1.0

    If you cannot extract reliable task estimates from the text, omit the Size/
    Estimate line for that task — do not guess. Missing estimates will be
    flagged by ask_clarifying_questions.

    Args:
        raw_text: Any natural language project description.

    Returns:
        Normalized text ready for generate_project_file, or a note explaining
        what information could not be extracted.
    """
    # This tool is a pass-through: the value is entirely in the docstring
    # acting as a prompt that guides the LLM to produce normalized output.
    # The actual "preprocessing" is done by the LLM caller following this spec.
    # We validate the output is non-empty and return it directly.
    if not raw_text or not raw_text.strip():
        return "ERROR: Empty input"
    return raw_text.strip()
```

**Why this works:** In an MCP workflow, the tool's docstring is included verbatim
in the system context the LLM uses when deciding how to call tools. By making the
docstring an explicit normalization specification, the LLM will follow it when
constructing the argument to pass to `generate_project_file`. The tool itself is a
near-no-op; the value is entirely in the prompt contract.

The recommended two-step workflow to document in the MCP server instructions:

```
For messy input:
  1. preprocess_description(raw_text) → normalized_text
  2. ask_clarifying_questions(normalized_text) → questions (if not ready)
  3. generate_project_file(enriched_text) → YAML
  4. simulate_from_description(enriched_text) → results narrative
```

Update `mcp = FastMCP(...)` instructions to describe this pipeline.

### Files changed

- `mcp_server.py` — `preprocess_description` tool, updated `FastMCP` instructions

### Acceptance criteria

1. Tool is registered and visible in MCP tool list
2. Returns input unchanged (the LLM does the work through the docstring)
3. Returns `ERROR: Empty input` for blank/whitespace input
4. `FastMCP` instructions updated to describe the full pipeline
5. Tool docstring passes MCP schema validation (no required parameters without defaults)



## Item 11 — Phase-based task grouping

### Problem

Projects are often described in phases, not as flat numbered task lists:

```
Phase 1: Discovery
- Requirements gathering
- Stakeholder interviews
- Technical feasibility

Phase 2: Design
- Architecture
- UI/UX mockups

Phase 3: Implementation
...
```

`Sprint 1:` / `Sprint 2:` headers are similarly common in sprint-planning contexts.
Today these are all ignored.

### Design

Add `_PHASE_HEADER_RE` to detect phase and sprint section headers:

```python
_PHASE_HEADER_RE = re.compile(
    r'^(?:phase|stage|milestone|sprint|iteration|wave|release)\s*'
    r'(?:(\d+)\s*[:.]\s*(.*)|(.*))$',
    re.IGNORECASE,
)
```

When matched:
1. Record the current phase name and number in parser state
2. Tasks created while inside a phase inherit `task.description` as
   `"[Phase N: <phase_name>]"` prefix (or a new `phase` field on `ParsedTask`,
   depending on whether we want to expose this in the YAML)
3. Generate an **implicit sequential dependency** between the last task of phase N
   and the first task of phase N+1 — this captures the serial nature of phased delivery
   without requiring explicit `Depends on` entries

The phase name is preserved as a task group comment in the generated YAML:

```yaml
# Phase 1: Discovery
  - id: "task_001"
    name: "Requirements gathering"
    ...
```

If any task inside a phase already has an explicit dependency, the implicit
phase-chain dependency is NOT added for that task (explicit always wins).

The implicit dependency is from `last_task_in_prev_phase` to `first_task_in_this_phase`
only, not from every task in phase N to every task in phase N+1. This models the
handoff between phases while still allowing intra-phase parallelism.

### Files changed

- `nl_parser.py` — `_PHASE_HEADER_RE`, phase tracking state variables
  (`current_phase_name`, `current_phase_number`, `last_task_of_phase`),
  dependency injection logic in `_flush_section()`
- `nl_parser.py` → `to_yaml()` — phase group comments
- `tests/test_nl_parser.py` — `TestPhaseGrouping`

### Acceptance criteria

1. `"Phase 1: Discovery"` followed by task bullets creates tasks with "Discovery"
   in their description or task group comment
2. First task of Phase 2 automatically depends on last task of Phase 1 when no
   explicit dependency is set
3. When a Phase 2 task already has an explicit `Depends on`, the implicit phase-chain
   is NOT added
4. YAML output contains `# Phase N: <name>` comments before each phase's tasks
5. `Sprint 1:` / `Iteration 2:` / `Milestone 3:` all trigger phase grouping



## Item 12 — Tabular sprint history import

### Problem

Sprint velocity data almost always lives in a spreadsheet. When a user pastes it as
plain text, it arrives as a tab- or pipe-separated table that the parser ignores:

```
Sprint | Completed | Spillover
SPR-01 | 21        | 2
SPR-02 | 18        | 5
SPR-03 | 24        | 1
SPR-04 | 19        | 3
```

Or from CSV export:

```
sprint,completed,spillover
SPR-01,21,2
SPR-02,18,5
```

### Design

Add a `_detect_and_parse_table(text: str) -> list[ParsedSprintHistoryEntry] | None`
function that:

1. Detects a table via a header row heuristic: at least 2 columns, at least one column
   name matching a sprint history field keyword
2. Parses column names to field mappings using fuzzy keyword matching
3. Produces `ParsedSprintHistoryEntry` objects from each data row

**Header keyword mapping:**

```python
_TABLE_COLUMN_ALIASES = {
    'sprint': 'sprint_id',
    'sprint_id': 'sprint_id',
    'id': 'sprint_id',
    'completed': 'completed_story_points',
    'done': 'completed_story_points',
    'delivered': 'completed_story_points',
    'velocity': 'completed_story_points',
    'points': 'completed_story_points',
    'spillover': 'spillover_story_points',
    'carryover': 'spillover_story_points',
    'carry_over': 'spillover_story_points',
    'added': 'added_story_points',
    'scope_added': 'added_story_points',
    'removed': 'removed_story_points',
    'scope_removed': 'removed_story_points',
    'holiday': 'holiday_factor',
    'holiday_factor': 'holiday_factor',
    'capacity': 'holiday_factor',  # when value ≤ 1.0, treat as holiday_factor
}
```

The table detector fires when:
- A line in the input matches `^[\w\s|,\t]+$` characteristic of a header row
- The next 2+ lines have the same delimiter count as the header
- At least one column name is in `_TABLE_COLUMN_ALIASES`

If a table is detected, it is extracted from the text before line-by-line parsing,
converted to sprint history entries, and appended to `project.sprint_planning.history`.

**Delimiter detection** — support pipe (`|`), comma (`,`), and tab (`\t`) as
separators. Use the separator that produces the most consistent column count across
all rows.

### Files changed

- `nl_parser.py` — `_TABLE_COLUMN_ALIASES`, `_detect_and_parse_table()`,
  call site in `parse()` (runs on full text before line iteration)
- `tests/test_nl_parser.py` — `TestTabularSprintHistory`

### Acceptance criteria

1. Pipe-separated table with `Sprint | Completed | Spillover` header → list of
   `ParsedSprintHistoryEntry` with correct `sprint_id`, `completed_story_points`,
   `spillover_story_points`
2. CSV format (comma-separated with header row) parsed correctly
3. Tab-separated table parsed correctly
4. A table without any recognized column name is NOT parsed as sprint history
5. Table parsing does not affect other sections of the description
6. `ParsedProject.sprint_planning` is auto-created if not already set



## Implementation Order and Dependencies

```
1 (auto-numbered tasks)          ← no deps, highest standalone value
2 (fuzzy durations + ranges)     ← no deps, high standalone value
3 (prose dependencies)           ← benefits from 1 being done first
4 (inline team extraction)       ← no deps
5 (ask_clarifying_questions)     ← no deps; complements all parser work
6 (result narration)             ← no deps; pure MCP layer
7 (what_if_scenario)             ← needs simulate_from_description (exists)
8 (refine_project_file)          ← no parser deps; pure YAML manipulation
9 (uncertainty inference)        ← benefits from 1+2 being done
10 (two-tier pre-processor)      ← benefits from all parser items done
11 (phase grouping)              ← benefits from 1 being done
12 (tabular sprint history)      ← no deps; isolated feature
```

Items 1, 2, 5, 6 can be developed in parallel by two engineers. Items 7 and 8 can
be developed in parallel with any parser work since they operate at the YAML/MCP
level.



## Testing Strategy

All new parser features need entries in `tests/test_nl_parser.py`. The existing test
file already has class-based organisation; new features get new `Test*` classes.

For MCP tools, `tests/test_mcp_server.py` uses `pytest.importorskip("mcp")` and calls
tool functions directly. New tools follow the same pattern.

**Regression test**: after each item is implemented, run the existing example files
through `NLProjectParser().parse_and_generate()` and verify their output is unchanged.
The existing semi-structured format must continue to work exactly as before.

```bash
poetry run pytest tests/test_nl_parser.py tests/test_mcp_server.py -v --no-cov
```



## Non-Goals

The following are explicitly out of scope for this plan:

- **LLM API calls from within the parser** — the parser must remain a pure-Python,
  dependency-free component that works offline
- **Semantic similarity / vector embeddings** — name matching uses token overlap only,
  not embeddings
- **Speech-to-text** — not a parser responsibility
- **GUI** — the MCP server is the interaction layer; no UI work is planned
- **Automatic JIRA/Trello API integration** — import is by paste, not by API call
