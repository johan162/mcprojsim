"""One-shot script to generate examples/sprint_nb_sickness_large.yaml."""

import random
import yaml
from pathlib import Path

rng = random.Random(20260324)
story_point_sizes = [3, 5, 8, 12]
task_count = 60
independent_tasks = task_count // 2

tasks = []
for index in range(1, task_count + 1):
    task_id = f"task_{index:03d}"
    story_points = rng.choice(story_point_sizes)

    dependencies: list[str] = []
    if index > independent_tasks:
        candidate_ids = [f"task_{v:03d}" for v in range(1, index)]
        dependency_count = rng.randint(1, min(3, len(candidate_ids)))
        dependencies = sorted(rng.sample(candidate_ids, dependency_count))

    task: dict[str, object] = {
        "id": task_id,
        "name": f"Task {index:03d}",
        "estimate": {
            "distribution": "lognormal",
            "low": round(story_points * 0.55, 2),
            "expected": float(story_points),
            "high": round(story_points * 1.9, 2),
        },
        "planning_story_points": story_points,
    }
    if dependencies:
        task["dependencies"] = dependencies
    tasks.append(task)

data = {
    "project": {
        "name": "60-Task Sprint NB Sickness Example",
        "start_date": "2026-04-06",
        "team_size": 8,
        "confidence_levels": [50, 80, 90],
    },
    "tasks": tasks,
    "sprint_planning": {
        "enabled": True,
        "sprint_length_weeks": 2,
        "capacity_mode": "story_points",
        "velocity_model": "neg_binomial",
        "planning_confidence_level": 0.8,
        "history": {
            "format": "json",
            "path": "sprint_planning_history.json",
        },
        "sickness": {
            "enabled": True,
            "team_size": 8,
            "probability_per_person_per_week": 0.35,
            "duration_log_mu": 1.1,
            "duration_log_sigma": 0.9,
        },
    },
}

out = (
    Path(__file__).resolve().parent.parent
    / "examples"
    / "sprint_nb_sickness_large.yaml"
)
with open(out, "w") as f:
    yaml.dump(data, f, sort_keys=False, default_flow_style=False)

print(f"Written: {out}")
print(
    f"Tasks: {len(tasks)}, independent: {sum(1 for t in tasks if 'dependencies' not in t)}, with deps: {sum(1 for t in tasks if 'dependencies' in t)}"
)
