"""Dependency-aware sprint planner for whole-item and spillover simulation."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from mcprojsim.models.project import (
    Project,
    RemovedWorkTreatment,
    SprintCapacityMode,
    SprintSpilloverModel,
    Task,
)
from mcprojsim.planning.sprint_capacity import SprintOutcomeSample


@dataclass(frozen=True)
class SprintBacklogLedgerEntry:
    """Auditable aggregate backlog adjustment for one sprint."""

    entry_type: str
    units: float
    affects_remaining_backlog: bool


@dataclass(frozen=True)
class SprintWorkItem:
    """One schedulable unit of work in a sprint iteration."""

    item_id: str
    task_id: str
    units: float
    dependencies: tuple[str, ...]
    priority: int | None
    planning_story_points: float | None
    is_remainder: bool = False


@dataclass(frozen=True)
class SprintCarryoverRecord:
    """Carryover produced by a spillover event in one sprint."""

    sprint_number: int
    task_id: str
    planned_points: float
    consumed_fraction: float
    remaining_points: float


@dataclass(frozen=True)
class SprintPlanResult:
    """Result of planning one sprint from the current ready queue."""

    completed_task_ids: list[str]
    completed_item_ids: list[str]
    deferred_task_ids: list[str]
    deferred_item_ids: list[str]
    delivered_units: float
    consumed_units: float
    remaining_capacity: float
    ledger_entries: list[SprintBacklogLedgerEntry]
    ready_task_ids: list[str]
    carryover_items: list[SprintWorkItem]
    carryover_records: list[SprintCarryoverRecord]
    spillover_item_ids: list[str]
    spillover_event_count: int
    pulled_item_count: int


class SprintPlanner:
    """Plan a single sprint using dependency-aware pull semantics."""

    def __init__(
        self,
        project: Project,
        random_state: np.random.RandomState | None = None,
    ):
        """Initialize the planner with project task metadata."""
        self.project = project
        self.task_map = {task.id: task for task in project.tasks}
        self.random_state = random_state or np.random.RandomState()
        self._remainder_counter = 0

        if project.sprint_planning is None:
            raise ValueError("SprintPlanner requires project.sprint_planning")

        self.sprint_planning = project.sprint_planning

    def build_initial_work_items(self) -> dict[str, SprintWorkItem]:
        """Create the starting set of work items from named tasks."""
        work_items: dict[str, SprintWorkItem] = {}
        for task in self.project.tasks:
            planning_story_points = task.get_planning_story_points()
            work_items[task.id] = SprintWorkItem(
                item_id=task.id,
                task_id=task.id,
                units=self._task_units(task),
                dependencies=tuple(task.dependencies),
                priority=task.priority,
                planning_story_points=(
                    float(planning_story_points)
                    if planning_story_points is not None
                    else None
                ),
                is_remainder=False,
            )
        return work_items

    def get_ready_tasks(self, completed_task_ids: set[str]) -> list[Task]:
        """Return dependency-ready tasks in deterministic sprint pull order."""
        ready_tasks = [
            task
            for task in self.project.tasks
            if task.id not in completed_task_ids
            and all(
                dependency in completed_task_ids for dependency in task.dependencies
            )
        ]
        return sorted(ready_tasks, key=self._task_sort_key)

    def get_ready_work_items(
        self,
        work_items: dict[str, SprintWorkItem],
        completed_task_ids: set[str],
    ) -> list[SprintWorkItem]:
        """Return all dependency-ready work items in pull order."""
        ready_items = [
            item
            for item in work_items.values()
            if all(dependency in completed_task_ids for dependency in item.dependencies)
        ]
        return sorted(ready_items, key=self._work_item_sort_key)

    def plan_sprint(
        self,
        completed_task_ids: set[str],
        sampled_outcome: SprintOutcomeSample,
        sprint_number: int = 1,
        work_items: dict[str, SprintWorkItem] | None = None,
    ) -> SprintPlanResult:
        """Plan one sprint using sampled completed-capacity and backlog churn."""
        if work_items is None:
            work_items = self.build_initial_work_items()
            for task_id in completed_task_ids:
                work_items.pop(task_id, None)

        ready_items = self.get_ready_work_items(work_items, completed_task_ids)
        remaining_capacity = float(sampled_outcome.completed_units)
        completed_task_ids_this_sprint: list[str] = []
        completed_item_ids: list[str] = []
        deferred_task_ids: list[str] = []
        deferred_item_ids: list[str] = []
        delivered_units = 0.0
        consumed_units = 0.0
        carryover_items: list[SprintWorkItem] = []
        carryover_records: list[SprintCarryoverRecord] = []
        spillover_item_ids: list[str] = []
        spillover_event_count = 0
        pulled_item_count = 0

        for item in ready_items:
            if item.units > remaining_capacity:
                deferred_task_ids.append(item.task_id)
                deferred_item_ids.append(item.item_id)
                continue

            pulled_item_count += 1
            spillover_record = self._maybe_spillover(item, sprint_number)
            if spillover_record is not None:
                carryover_item, record = spillover_record
                carryover_items.append(carryover_item)
                carryover_records.append(record)
                spillover_item_ids.append(item.item_id)
                consumed_units += item.units * record.consumed_fraction
                remaining_capacity -= item.units * record.consumed_fraction
                spillover_event_count += 1
                continue

            completed_task_ids_this_sprint.append(item.task_id)
            completed_item_ids.append(item.item_id)
            delivered_units += item.units
            consumed_units += item.units
            remaining_capacity -= item.units

        ledger_entries = self._build_ledger_entries(sampled_outcome)

        return SprintPlanResult(
            completed_task_ids=completed_task_ids_this_sprint,
            completed_item_ids=completed_item_ids,
            deferred_task_ids=deferred_task_ids,
            deferred_item_ids=deferred_item_ids,
            delivered_units=delivered_units,
            consumed_units=consumed_units,
            remaining_capacity=remaining_capacity,
            ledger_entries=ledger_entries,
            ready_task_ids=[item.task_id for item in ready_items],
            carryover_items=carryover_items,
            carryover_records=carryover_records,
            spillover_item_ids=spillover_item_ids,
            spillover_event_count=spillover_event_count,
            pulled_item_count=pulled_item_count,
        )

    def _maybe_spillover(
        self,
        item: SprintWorkItem,
        sprint_number: int,
    ) -> tuple[SprintWorkItem, SprintCarryoverRecord] | None:
        """Sample whether a pulled item spills over into a new remainder item."""
        spillover = self.sprint_planning.spillover
        if not spillover.enabled:
            return None

        planned_points = item.planning_story_points
        if planned_points is None or planned_points <= 0:
            return None

        probability = self._spillover_probability(item)
        if float(self.random_state.random_sample()) >= probability:
            return None

        consumed_fraction = float(
            self.random_state.beta(
                spillover.consumed_fraction_alpha,
                spillover.consumed_fraction_beta,
            )
        )
        consumed_fraction = min(max(consumed_fraction, 1e-6), 0.999999)
        remaining_units = item.units * (1 - consumed_fraction)
        if remaining_units <= 1e-9:
            return None

        remainder_item = SprintWorkItem(
            item_id=self._next_remainder_id(item.task_id),
            task_id=item.task_id,
            units=float(remaining_units),
            dependencies=(),
            priority=item.priority,
            planning_story_points=float(planned_points * (1 - consumed_fraction)),
            is_remainder=True,
        )
        record = SprintCarryoverRecord(
            sprint_number=sprint_number,
            task_id=item.task_id,
            planned_points=float(planned_points),
            consumed_fraction=consumed_fraction,
            remaining_points=float(planned_points * (1 - consumed_fraction)),
        )
        return remainder_item, record

    def _spillover_probability(self, item: SprintWorkItem) -> float:
        """Return the configured spillover probability for a pulled item."""
        task = self.task_map[item.task_id]
        if task.spillover_probability_override is not None:
            return float(task.spillover_probability_override)

        planning_points = item.planning_story_points
        if planning_points is None:
            return 0.0

        spillover = self.sprint_planning.spillover
        if spillover.model == SprintSpilloverModel.LOGISTIC:
            scaled_points = max(planning_points / spillover.size_reference_points, 1e-6)
            logit = (
                spillover.logistic_slope * math.log(scaled_points)
                + spillover.logistic_intercept
            )
            return float(1.0 / (1.0 + math.exp(-logit)))

        for bracket in spillover.size_brackets:
            if bracket.max_points is None or planning_points <= bracket.max_points:
                return float(bracket.probability)
        return 0.0

    def _build_ledger_entries(
        self,
        sampled_outcome: SprintOutcomeSample,
    ) -> list[SprintBacklogLedgerEntry]:
        """Build explicit auditable aggregate backlog adjustments."""
        ledger_entries: list[SprintBacklogLedgerEntry] = []

        if sampled_outcome.added_units > 0:
            ledger_entries.append(
                SprintBacklogLedgerEntry(
                    entry_type="added_scope",
                    units=float(sampled_outcome.added_units),
                    affects_remaining_backlog=True,
                )
            )

        if sampled_outcome.removed_units > 0:
            ledger_entries.append(
                SprintBacklogLedgerEntry(
                    entry_type="removed_scope",
                    units=float(sampled_outcome.removed_units),
                    affects_remaining_backlog=(
                        self.sprint_planning.removed_work_treatment
                        == RemovedWorkTreatment.REDUCE_BACKLOG
                    ),
                )
            )

        return ledger_entries

    def _task_sort_key(self, task: Task) -> tuple[float, str]:
        """Sort by priority first when present, otherwise by task ID."""
        priority = float(task.priority) if task.priority is not None else float("inf")
        return priority, task.id

    def _work_item_sort_key(self, item: SprintWorkItem) -> tuple[float, str]:
        """Sort work items using the same priority semantics as base tasks."""
        priority = float(item.priority) if item.priority is not None else float("inf")
        return priority, item.item_id

    def _task_units(self, task: Task) -> float:
        """Return the planner unit size for a task."""
        if self.sprint_planning.capacity_mode == SprintCapacityMode.TASKS:
            return 1.0

        planning_story_points = task.get_planning_story_points()
        if planning_story_points is None:
            raise ValueError(
                f"Task {task.id} is missing planning story points in story_points mode"
            )
        return float(planning_story_points)

    def _next_remainder_id(self, task_id: str) -> str:
        """Create a deterministic synthetic identifier for a carryover item."""
        self._remainder_counter += 1
        return f"{task_id}__carryover_{self._remainder_counter:04d}"
