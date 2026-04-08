# Natural Language Input

The `mcprojsim` natural language parser accepts a wide range of input formats — from structured `Task N:` headers to plain bullet lists copied from a planning tool. This page is the single reference for every input pattern the parser understands.

!!! tip "Quick rule of thumb"
    If it looks like a task list a human would write, the parser will probably understand it. When in doubt, run `mcprojsim generate` and inspect the output.

## Input modes

The parser supports two task-definition modes. They cannot be mixed in the same description.

| Mode | Trigger | Example |
|------|---------|---------|
| **Explicit headers** | `Task N:` followed by bullet properties | `Task 1:` / `- Size: M` |
| **Auto-detected lists** | Plain numbered or bullet lists with no `Task N:` headers | `1. Design phase` / `- Backend API` |

Auto-detected lists activate automatically when the parser sees numbered or bulleted items and no `Task N:` header has appeared. Once a `Task N:` header is encountered, auto-detection is disabled for the rest of the description.

---

## Project-level metadata

These lines can appear anywhere outside a task section:

```text
Project name: Website Redesign
Description: Q3 infrastructure work
Start date: 2026-06-01
Hours per day: 7.5
Confidence levels: 50, 80, 90, 95
```

All fields are optional. Defaults: name = "Untitled Project", hours = 8.0, confidence = [50, 80, 90, 95].

---

## Explicit task headers (`Task N:`)

The original structured format. Each task starts with a numbered header, followed by indented bullet properties:

```text
Task 1: Design the login flow
- Size: M

Task 2: Implement backend
- Depends on Task 1
- Estimate: 5/8/15 days

Task 3: QA and testing
- Depends on Task 2
- Story points: 8
```

### Bullet properties

| Property | Patterns | Example |
|----------|----------|---------|
| Task name | `Name:` or first unmatched bullet | `- Name: Backend API` |
| T-shirt size | `Size: M`, `Size XL`, `Size. XL` | `- Size: L` |
| Story points | `Story points: 5`, `Points: 8` | `- Story points: 13` |
| Explicit estimate | `Estimate: low/expected/high [unit]` | `- Estimate: 3/5/10 days` |
| Dependencies | `Depends on Task 1, Task 3` | `- Depends on Task 2` |
| Resources | `Resources: Alice, Bob` | `- Resources: Alice` |
| Max resources | `Max resources: 2` | `- Max resources: 2` |
| Min experience | `Min experience: 2` | `- Min experience: 3` |
| Description | Second unmatched bullet | `- Involves DB migration` |

**Separators** between keyword and value can be `:`, `.`, `=`, or a space. All are equivalent and case-insensitive.

---

## Auto-detected task lists

When no `Task N:` headers are present, the parser automatically detects tasks from plain lists. This is ideal for copy-paste from planning tools, meeting notes, or email threads.

### Supported list formats

**Plain numbered lists** — task numbers are preserved from the source:

```text
Project name: Backend Migration
Start date: 2026-05-01

1. Design database schema
2. Implement REST API
3. Write integration tests
4. Deploy to staging
```

**Parenthesis numbered lists:**

```text
1) Authentication module
2) User management
3) Reporting
```

**Bracket numbered lists:**

```text
[1] Authentication
[2] User management
[3] Reporting module
```

**Bullet lists** — task numbers are auto-assigned (1, 2, 3, …):

```text
- Discovery and requirements
- Database design
- Backend implementation
- Frontend
- QA
- Deployment
```

Bullets can use `-`, `*`, or `•`.

**Hash numbered lists** (rare but supported):

```text
# 1 First task
# 2 Second task
```

### Continuation lines

Indented lines under an auto-detected task are treated as bullet properties, exactly like the explicit-header format:

```text
1. Design database schema
  Size: M
2. Implement REST API
  Size: XL
  Depends on Task 1
3. Write integration tests
  Estimate: 3/5/10 days
```

---

## Inline properties on task lines

Both auto-detected and continuation lines can carry properties directly on the task name line. The parser extracts them and cleans the task name.

### Bracketed or parenthesized sizes

```text
- Backend API [XL]
- Frontend (M)
1. QA testing [S]
```

### Fuzzy size hints

Natural phrasing like "probably an M" or "assume S" is recognized:

```text
- Backend refactoring, probably an M
- Frontend overhaul, likely an L
- Quick patch, assume S
```

Supported qualifiers: `probably`, `likely`, `assume`, `estimated as`.

### Inline estimate ranges

Numeric ranges on the task line are parsed as explicit estimates:

```text
- QA: 3–5 days
- Quick fix 2-4 hours
- Backend migration 2–4 weeks
- Implementation 3 to 5 days
```

The parser calculates `expected = (low + high) / 2` automatically.

### Inline dependencies

```text
1. Design database schema
2. Implement REST API depends on Task 1
```

### Combined example

Multiple inline properties can appear on the same line:

```text
- Backend API [XL] 3–5 days
```

This sets both the T-shirt size and the estimate range.

---

## T-shirt size aliases

The parser normalizes many size labels to the six canonical sizes:

| Canonical | Accepted inputs |
|-----------|-----------------|
| `XS` | `XS`, `Extra Small`, `Extrasmall` |
| `S` | `S`, `Small` |
| `M` | `M`, `Medium`, `Med` |
| `L` | `L`, `Large` |
| `XL` | `XL`, `Extra Large`, `Extralarge` |
| `XXL` | `XXL`, `Extra Extra Large`, `2XL` |

Matching is case-insensitive.

---

## Complete examples

### Example 1: Numbered list with inline sizes

```text
Project name: Backend Migration
Start date: 2026-05-01

1. Design database schema [M]
2. Implement REST API [XL] depends on Task 1
3. Write integration tests [L] depends on Task 2
4. Deploy to staging [S] depends on Task 3
5. Production cutover [S] depends on Task 4
```

### Example 2: Bullet list with fuzzy sizes

```text
Project name: Mobile App MVP
Start date: 2026-06-01

- Discovery and requirements (S)
- UX wireframes (M)
  Depends on Task 1
- Backend API, probably an XL
  Depends on Task 2
- iOS frontend (XL)
  Depends on Task 3
- Android frontend (XL)
  Depends on Task 3
- QA and bug fixes, likely an L
  Depends on Task 4, Task 5
- App store submission (S)
  Depends on Task 6
```

### Example 3: Bracket list with inline ranges

```text
Project name: Data Pipeline Rebuild
Start date: 2026-07-01

[1] Audit existing ETL jobs [S]
[2] Design new pipeline architecture [M] depends on Task 1
[3] Implement ingestion layer 3–5 days depends on Task 2
[4] Build transformation engine [XL] depends on Task 3
[5] Set up monitoring and alerts [M] depends on Task 4
[6] Migration and cutover, assume S, depends on Task 5
```

### Example 4: Mixed inline properties

```text
Project name: Auth Service Rewrite
Description: Replace legacy auth with OAuth2/OIDC
Start date: 2026-08-01

1. Evaluate identity providers 2–4 days
2. Design token flow and session management [M]
  Depends on Task 1
3. Implement OAuth2 authorization server, probably an XL
  Depends on Task 2
4. Migrate user database (L)
  Depends on Task 2
5. Integration testing [L]
  Depends on Task 3, Task 4
6. Security audit, assume M
  Depends on Task 5
7. Staged rollout [S]
  Depends on Task 6
```

### Example 5: Traditional structured format (still fully supported)

```text
Project name: Website Redesign
Start date: 2026-04-15

Task 1: Gather requirements
- Size: S

Task 2: Create wireframes
- Depends on Task 1
- Size: M

Task 3: Build frontend
- Depends on Task 2
- Size: XL
```

---

## Resources, calendars, and sprint planning

These sections use the same structured format regardless of whether tasks use explicit headers or auto-detection. See the [MCP Server](mcp-server.md#natural-language-input-format) page and the [API reference](../api_reference/10_nl_parser.md) for full details on resource, calendar, and sprint planning input patterns.

---

## Mixing estimation methods

Different tasks can use different estimation methods within the same project:

```text
1. Well-understood work
  Estimate: 3/5/8 days
2. Vaguely scoped work [XL]
3. Agile team estimate
  Story points: 8
```

The parser handles this correctly, and `mcprojsim` resolves each estimate type using the appropriate configuration mapping at simulation time.

---

## What is NOT supported in NL input

- **Task-level risks** and **uncertainty factors** — add these to the YAML after generation
- **Project-level risks** — add manually to YAML
- **Circular dependency detection** — caught later by `mcprojsim validate`
- **Volatility-overlay and spillover calibration** — edit directly in YAML
- Mixing `Task N:` headers and auto-detected lists in the same description

\newpage
