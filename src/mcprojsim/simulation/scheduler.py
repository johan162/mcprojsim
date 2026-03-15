"""Task scheduler with dependency and optional resource constraints."""

import math
from datetime import date, timedelta
from typing import Dict, List, Set

import numpy as np

from mcprojsim.models.project import CalendarSpec, Project, ResourceSpec


class TaskScheduler:
    """Scheduler for tasks with dependencies."""

    def __init__(self, project: Project):
        """Initialize scheduler with project.

        Args:
            project: Project with tasks and dependencies
        """
        self.project = project
        self.task_map = {task.id: task for task in project.tasks}

    def schedule_tasks(
        self,
        task_durations: Dict[str, float],
        *,
        use_resource_constraints: bool = False,
        return_diagnostics: bool = False,
        start_date: date | None = None,
        hours_per_day: float = 8.0,
    ) -> (
        Dict[str, Dict[str, float]]
        | tuple[Dict[str, Dict[str, float]], Dict[str, float]]
    ):
        """Schedule tasks respecting dependencies.

        Args:
            task_durations: Dictionary mapping task IDs to their durations
            use_resource_constraints: Whether to enforce resource assignment
                constraints when scheduling. Defaults to False.
            return_diagnostics: Whether to return constrained-mode diagnostics.
            start_date: Project start date used for calendar-aware scheduling.
                Defaults to project metadata start date when omitted.
            hours_per_day: Working hours per day fallback when calendar does not
                define explicit daily work hours.

        Returns:
            Dictionary mapping task IDs to their schedule info:
            {'start': start_time, 'end': end_time, 'duration': duration}
        """
        if use_resource_constraints and self.project.resources:
            effective_start_date = start_date or self.project.project.start_date
            schedule, diagnostics = self._schedule_tasks_with_resources(
                task_durations,
                start_date=effective_start_date,
                hours_per_day=hours_per_day,
            )
            if return_diagnostics:
                return schedule, diagnostics
            return schedule

        schedule = self._schedule_tasks_dependency_only(task_durations)
        if return_diagnostics:
            return schedule, {
                "resource_wait_time_hours": 0.0,
                "resource_utilization": 0.0,
                "calendar_delay_time_hours": 0.0,
            }
        return schedule

    def _schedule_tasks_dependency_only(
        self, task_durations: Dict[str, float]
    ) -> Dict[str, Dict[str, float]]:
        """Schedule tasks using dependency-only earliest-start logic."""
        schedule: Dict[str, Dict[str, float]] = {}
        sorted_tasks = self._topological_sort()

        for task_id in sorted_tasks:
            duration = task_durations[task_id]
            task = self.task_map[task_id]

            # Find earliest start time based on dependencies
            start_time = 0.0
            for dep_id in task.dependencies:
                if dep_id in schedule:
                    dep_end = schedule[dep_id]["end"]
                    start_time = max(start_time, dep_end)

            schedule[task_id] = {
                "start": start_time,
                "end": start_time + duration,
                "duration": duration,
            }

        return schedule

    def _schedule_tasks_with_resources(
        self,
        task_durations: Dict[str, float],
        *,
        start_date: date,
        hours_per_day: float,
    ) -> tuple[Dict[str, Dict[str, float]], Dict[str, float]]:
        """Schedule tasks with dependency and resource constraints.

        This first implementation is deterministic and non-preemptive. It
        enforces:
        - dependency precedence
        - per-task ``max_resources``
        - per-task ``min_experience_level``
        - exclusive resource assignment (one task at a time)
        """
        schedule: Dict[str, Dict[str, float]] = {}
        sorted_tasks = self._topological_sort()

        remaining = set(sorted_tasks)
        active: list[tuple[float, str, list[str]]] = []
        current_time = 0.0
        resource_wait_time_hours = 0.0
        calendar_delay_time_hours = 0.0

        resource_map = {
            resource.name: resource
            for resource in self.project.resources
            if resource.name is not None
        }
        free_resources = set(resource_map.keys())

        calendar_map = {calendar.id: calendar for calendar in self.project.calendars}
        default_calendar = calendar_map.get("default")
        horizon_days = self._estimate_sickness_horizon_days(
            task_durations,
            resource_map,
            hours_per_day,
        )
        sickness_absence = self._generate_sickness_absence(
            resource_map,
            start_date,
            horizon_days,
            calendar_map,
            default_calendar,
        )

        while remaining:
            # Release completed tasks at current time
            finished = [entry for entry in active if entry[0] <= current_time + 1e-9]
            for _, _, assigned in finished:
                for resource_name in assigned:
                    free_resources.add(resource_name)
            active = [entry for entry in active if entry[0] > current_time + 1e-9]

            # Find tasks ready by dependency constraints
            ready = [
                task_id
                for task_id in sorted(remaining)
                if all(
                    dep_id in schedule
                    and schedule[dep_id]["end"] <= current_time + 1e-9
                    for dep_id in self.task_map[task_id].dependencies
                )
            ]

            started_any = False
            for task_id in ready:
                task = self.task_map[task_id]
                eligible_pool = (
                    [r for r in task.resources if r in resource_map]
                    if task.resources
                    else sorted(resource_map.keys())
                )

                eligible_free = [
                    name
                    for name in sorted(eligible_pool)
                    if name in free_resources
                    and resource_map[name].experience_level >= task.min_experience_level
                ]

                if not eligible_free:
                    continue

                assigned = eligible_free[: task.max_resources]
                if not assigned:
                    continue

                dependency_ready_time = max(
                    (
                        schedule[dep_id]["end"]
                        for dep_id in task.dependencies
                        if dep_id in schedule
                    ),
                    default=0.0,
                )
                if current_time > dependency_ready_time:
                    resource_wait_time_hours += current_time - dependency_ready_time

                actual_start = self._find_next_time_with_capacity(
                    current_time,
                    assigned,
                    resource_map,
                    calendar_map,
                    default_calendar,
                    sickness_absence,
                    start_date,
                    hours_per_day,
                )

                if actual_start is None:
                    continue

                if actual_start > current_time:
                    calendar_delay_time_hours += actual_start - current_time

                end_time, execution_calendar_delay = (
                    self._compute_task_end_with_calendars(
                        actual_start,
                        task_durations[task_id],
                        assigned,
                        resource_map,
                        calendar_map,
                        default_calendar,
                        sickness_absence,
                        start_date,
                        hours_per_day,
                    )
                )
                calendar_delay_time_hours += execution_calendar_delay
                elapsed_duration = end_time - actual_start

                for resource_name in assigned:
                    free_resources.remove(resource_name)

                schedule[task_id] = {
                    "start": actual_start,
                    "end": end_time,
                    "duration": elapsed_duration,
                }
                active.append((end_time, task_id, assigned))
                remaining.remove(task_id)
                started_any = True

            if started_any:
                continue

            if active:
                current_time = min(end_time for end_time, _, _ in active)
            else:
                # Fallback safety (should not happen for valid inputs)
                # Use dependency-only schedule for any unscheduled tasks.
                fallback = self._schedule_tasks_dependency_only(task_durations)
                for task_id in remaining:
                    schedule[task_id] = fallback[task_id]
                break

        project_end = max((info["end"] for info in schedule.values()), default=0.0)
        total_effort = float(sum(task_durations.values()))
        total_available_capacity = self._integrate_available_capacity(
            0.0,
            project_end,
            sorted(resource_map.keys()),
            resource_map,
            calendar_map,
            default_calendar,
            sickness_absence,
            start_date,
            hours_per_day,
        )
        utilization = (
            min(1.0, total_effort / total_available_capacity)
            if total_available_capacity > 0
            else 0.0
        )

        return schedule, {
            "resource_wait_time_hours": resource_wait_time_hours,
            "resource_utilization": utilization,
            "calendar_delay_time_hours": calendar_delay_time_hours,
        }

    @staticmethod
    def _estimate_sickness_horizon_days(
        task_durations: Dict[str, float],
        resource_map: Dict[str, ResourceSpec],
        hours_per_day: float,
    ) -> int:
        """Estimate sickness simulation horizon in days for one iteration."""
        total_effort = sum(task_durations.values())
        total_capacity = sum(
            resource.productivity_level * resource.availability
            for resource in resource_map.values()
        )
        if total_capacity <= 0:
            total_capacity = 0.1

        effort_days = total_effort / (hours_per_day * total_capacity)
        return max(30, int(math.ceil(effort_days)) + 60)

    def _generate_sickness_absence(
        self,
        resource_map: Dict[str, ResourceSpec],
        start_date: date,
        horizon_days: int,
        calendar_map: Dict[str, CalendarSpec],
        default_calendar: CalendarSpec | None,
    ) -> Dict[str, Set[date]]:
        """Generate sickness absence days per resource for an iteration."""
        sickness_by_resource: Dict[str, Set[date]] = {
            name: set() for name in resource_map.keys()
        }

        sigma = 0.5
        mode_days = 2.0
        mu = math.log(mode_days) + sigma * sigma

        for resource_name, resource in resource_map.items():
            current_day = 0
            while current_day < horizon_days:
                d = start_date + timedelta(days=current_day)
                if self._is_resource_working_day(
                    resource,
                    d,
                    calendar_map,
                    default_calendar,
                    preplanned_absence_only=True,
                ):
                    if np.random.random() < resource.sickness_prob:
                        sickness_len = max(
                            1, int(round(np.random.lognormal(mu, sigma)))
                        )
                        for offset in range(sickness_len):
                            sickness_by_resource[resource_name].add(
                                d + timedelta(days=offset)
                            )
                        current_day += sickness_len
                        continue
                current_day += 1

        return sickness_by_resource

    def _resolve_calendar(
        self,
        resource: ResourceSpec,
        calendar_map: Dict[str, CalendarSpec],
        default_calendar: CalendarSpec | None,
        hours_per_day: float,
    ) -> CalendarSpec:
        """Resolve resource calendar with sensible defaults."""
        calendar = calendar_map.get(resource.calendar) or default_calendar
        if calendar is None:
            return CalendarSpec(
                id="default",
                work_hours_per_day=hours_per_day,
                work_days=[1, 2, 3, 4, 5],
                holidays=[],
            )
        return calendar

    def _is_resource_working_day(
        self,
        resource: ResourceSpec,
        d: date,
        calendar_map: Dict[str, CalendarSpec],
        default_calendar: CalendarSpec | None,
        *,
        preplanned_absence_only: bool = False,
        sickness_absence: Dict[str, Set[date]] | None = None,
    ) -> bool:
        """Check whether a date is a working day for a resource."""
        calendar = self._resolve_calendar(
            resource, calendar_map, default_calendar, self.project.project.hours_per_day
        )
        weekday = d.weekday() + 1  # Monday=1

        if weekday not in calendar.work_days:
            return False
        if d in calendar.holidays:
            return False
        if d in resource.planned_absence:
            return False
        if not preplanned_absence_only and sickness_absence is not None:
            if (
                resource.name in sickness_absence
                and d in sickness_absence[resource.name]
            ):
                return False
        return True

    def _capacity_at_time(
        self,
        t: float,
        assigned: list[str],
        resource_map: Dict[str, ResourceSpec],
        calendar_map: Dict[str, CalendarSpec],
        default_calendar: CalendarSpec | None,
        sickness_absence: Dict[str, Set[date]],
        start_date: date,
        hours_per_day: float,
    ) -> float:
        """Compute effective capacity (person-hours/clock-hour) at time t."""
        day_index = int(math.floor(t / 24.0))
        d = start_date + timedelta(days=day_index)
        hour_of_day = t - day_index * 24.0

        capacity = 0.0
        for resource_name in assigned:
            resource = resource_map[resource_name]
            calendar = self._resolve_calendar(
                resource, calendar_map, default_calendar, hours_per_day
            )
            if hour_of_day < 0 or hour_of_day >= calendar.work_hours_per_day:
                continue
            if not self._is_resource_working_day(
                resource,
                d,
                calendar_map,
                default_calendar,
                sickness_absence=sickness_absence,
            ):
                continue
            capacity += resource.productivity_level * resource.availability

        return capacity

    @staticmethod
    def _next_day_start(t: float) -> float:
        """Return next day boundary in clock hours."""
        day_index = int(math.floor(t / 24.0))
        return (day_index + 1) * 24.0

    def _next_capacity_change(
        self,
        t: float,
        assigned: list[str],
        resource_map: Dict[str, ResourceSpec],
        calendar_map: Dict[str, CalendarSpec],
        default_calendar: CalendarSpec | None,
        hours_per_day: float,
    ) -> float:
        """Find next time where capacity may change for assigned resources."""
        day_index = int(math.floor(t / 24.0))
        hour_of_day = t - day_index * 24.0

        candidates = [self._next_day_start(t)]
        for resource_name in assigned:
            resource = resource_map[resource_name]
            calendar = self._resolve_calendar(
                resource, calendar_map, default_calendar, hours_per_day
            )
            start_of_day = day_index * 24.0
            if hour_of_day < calendar.work_hours_per_day:
                candidates.append(start_of_day + calendar.work_hours_per_day)

        return min(c for c in candidates if c > t + 1e-9)

    def _find_next_time_with_capacity(
        self,
        start_t: float,
        assigned: list[str],
        resource_map: Dict[str, ResourceSpec],
        calendar_map: Dict[str, CalendarSpec],
        default_calendar: CalendarSpec | None,
        sickness_absence: Dict[str, Set[date]],
        start_date: date,
        hours_per_day: float,
    ) -> float | None:
        """Find next time point with non-zero available capacity."""
        t = start_t
        max_search_hours = 24.0 * 730.0  # Safety bound: ~2 years
        while t - start_t < max_search_hours:
            if (
                self._capacity_at_time(
                    t,
                    assigned,
                    resource_map,
                    calendar_map,
                    default_calendar,
                    sickness_absence,
                    start_date,
                    hours_per_day,
                )
                > 0
            ):
                return t
            t = self._next_capacity_change(
                t,
                assigned,
                resource_map,
                calendar_map,
                default_calendar,
                hours_per_day,
            )
        return None

    def _compute_task_end_with_calendars(
        self,
        start_t: float,
        effort_hours: float,
        assigned: list[str],
        resource_map: Dict[str, ResourceSpec],
        calendar_map: Dict[str, CalendarSpec],
        default_calendar: CalendarSpec | None,
        sickness_absence: Dict[str, Set[date]],
        start_date: date,
        hours_per_day: float,
    ) -> tuple[float, float]:
        """Integrate effort over time-varying resource capacity windows."""
        remaining_effort = effort_hours
        t = start_t
        calendar_delay_hours = 0.0

        while remaining_effort > 1e-9:
            cap = self._capacity_at_time(
                t,
                assigned,
                resource_map,
                calendar_map,
                default_calendar,
                sickness_absence,
                start_date,
                hours_per_day,
            )
            next_change = self._next_capacity_change(
                t,
                assigned,
                resource_map,
                calendar_map,
                default_calendar,
                hours_per_day,
            )

            if cap <= 0:
                calendar_delay_hours += max(0.0, next_change - t)
                t = next_change
                continue

            dt = next_change - t
            producible = cap * dt
            if producible >= remaining_effort:
                t += remaining_effort / cap
                remaining_effort = 0.0
            else:
                remaining_effort -= producible
                t = next_change

        return t, calendar_delay_hours

    def _integrate_available_capacity(
        self,
        start_t: float,
        end_t: float,
        resource_names: list[str],
        resource_map: Dict[str, ResourceSpec],
        calendar_map: Dict[str, CalendarSpec],
        default_calendar: CalendarSpec | None,
        sickness_absence: Dict[str, Set[date]],
        start_date: date,
        hours_per_day: float,
    ) -> float:
        """Integrate available capacity (person-hours) over a timeline."""
        if end_t <= start_t:
            return 0.0

        t = start_t
        total_capacity = 0.0
        while t < end_t - 1e-9:
            cap = self._capacity_at_time(
                t,
                resource_names,
                resource_map,
                calendar_map,
                default_calendar,
                sickness_absence,
                start_date,
                hours_per_day,
            )
            next_change = self._next_capacity_change(
                t,
                resource_names,
                resource_map,
                calendar_map,
                default_calendar,
                hours_per_day,
            )
            segment_end = min(end_t, next_change)
            dt = max(0.0, segment_end - t)
            total_capacity += cap * dt
            t = segment_end

        return total_capacity

    def _topological_sort(self) -> List[str]:
        """Perform topological sort using Kahn's algorithm.

        Returns:
            List of task IDs in topological order
        """
        # Calculate in-degree for each task
        in_degree: Dict[str, int] = {task.id: 0 for task in self.project.tasks}
        adjacency: Dict[str, List[str]] = {task.id: [] for task in self.project.tasks}

        for task in self.project.tasks:
            for dep_id in task.dependencies:
                adjacency[dep_id].append(task.id)
                in_degree[task.id] += 1

        # Queue of tasks with no dependencies
        queue: List[str] = [
            task_id for task_id, degree in in_degree.items() if degree == 0
        ]
        sorted_tasks: List[str] = []

        while queue:
            task_id = queue.pop(0)
            sorted_tasks.append(task_id)

            # Reduce in-degree for dependent tasks
            for dependent_id in adjacency[task_id]:
                in_degree[dependent_id] -= 1
                if in_degree[dependent_id] == 0:
                    queue.append(dependent_id)

        # Check if all tasks were sorted (no cycles)
        if len(sorted_tasks) != len(self.project.tasks):
            raise ValueError("Circular dependency detected in project tasks")

        return sorted_tasks

    def calculate_slack(
        self, schedule: Dict[str, Dict[str, float]]
    ) -> Dict[str, float]:
        """Calculate total float (slack) for each task.

        Total float is the amount of time a task can be delayed without
        delaying the project. Computed via a backward pass from the
        project end time.

        Args:
            schedule: Task schedule from schedule_tasks()

        Returns:
            Dictionary mapping task IDs to their total float in hours
        """
        if not schedule:
            return {}

        project_end = max(info["end"] for info in schedule.values())

        # Build successor map
        successors: Dict[str, List[str]] = {tid: [] for tid in schedule}
        for task in self.project.tasks:
            for dep_id in task.dependencies:
                if dep_id in successors:
                    successors[dep_id].append(task.id)

        # Backward pass: compute latest start
        latest_start: Dict[str, float] = {}
        for task_id in reversed(self._topological_sort()):
            if not successors[task_id]:
                # No successors: latest finish = project end
                latest_start[task_id] = project_end - schedule[task_id]["duration"]
            else:
                # Latest start = earliest latest-start of successors minus nothing
                # Actually: LF = min(LS of successors), LS = LF - duration
                min_succ_ls = min(latest_start[succ] for succ in successors[task_id])
                latest_start[task_id] = min_succ_ls - schedule[task_id]["duration"]

        slack: Dict[str, float] = {}
        for task_id, info in schedule.items():
            slack[task_id] = max(0.0, latest_start[task_id] - info["start"])

        return slack

    def max_parallel_tasks(self, schedule: Dict[str, Dict[str, float]]) -> int:
        """Compute the peak number of concurrently running tasks.

        Uses a sweep-line over task start/end events.  At a given point in
        time a task is considered active during the half-open interval
        ``[start, end)`` so that a task ending exactly when another begins
        does not count as concurrent.

        Args:
            schedule: Task schedule from schedule_tasks()

        Returns:
            Maximum number of tasks active at any single point in time
        """
        if not schedule:
            return 0

        # Build event list: +1 for a task starting, -1 for a task ending.
        events: list[tuple[float, int]] = []
        for info in schedule.values():
            events.append((info["start"], 1))
            events.append((info["end"], -1))

        # Sort by time; at equal times process end events before start
        # events so that back-to-back tasks are not counted as parallel.
        events.sort(key=lambda e: (e[0], e[1]))

        current = 0
        peak = 0
        for _, delta in events:
            current += delta
            if current > peak:
                peak = current

        return peak

    def get_critical_path(self, schedule: Dict[str, Dict[str, float]]) -> Set[str]:
        """Identify critical path tasks.

        Args:
            schedule: Task schedule from schedule_tasks()

        Returns:
            Set of task IDs on the critical path
        """
        critical_paths = self.get_critical_paths(schedule)
        return {task_id for path in critical_paths for task_id in path}

    def get_critical_paths(
        self, schedule: Dict[str, Dict[str, float]]
    ) -> list[tuple[str, ...]]:
        """Identify all full critical path sequences.

        Args:
            schedule: Task schedule from `schedule_tasks()`

        Returns:
            Sorted list of critical path sequences from start task to end task
        """
        if not schedule:
            return []

        project_end = max(info["end"] for info in schedule.values())
        critical_paths: set[tuple[str, ...]] = set()
        cache: Dict[str, set[tuple[str, ...]]] = {}

        for task_id, info in schedule.items():
            if abs(info["end"] - project_end) < 1e-9:  # Float comparison tolerance
                critical_paths.update(
                    self._trace_critical_paths(task_id, schedule, cache)
                )

        return sorted(critical_paths)

    def _trace_critical_paths(
        self,
        task_id: str,
        schedule: Dict[str, Dict[str, float]],
        cache: Dict[str, set[tuple[str, ...]]],
    ) -> set[tuple[str, ...]]:
        """Recursively trace all critical paths backwards.

        Args:
            task_id: Current task ID
            schedule: Task schedule
            cache: Memoized critical paths ending at each task

        Returns:
            Set of critical path sequences ending at `task_id`
        """
        if task_id in cache:
            return cache[task_id]

        task = self.task_map[task_id]
        task_start = schedule[task_id]["start"]
        matching_dependencies = [
            dep_id
            for dep_id in task.dependencies
            if abs(schedule[dep_id]["end"] - task_start) < 1e-9
        ]

        if not matching_dependencies:
            leaf_paths: set[tuple[str, ...]] = {(task_id,)}
            cache[task_id] = leaf_paths
            return leaf_paths

        paths: set[tuple[str, ...]] = set()
        for dep_id in sorted(matching_dependencies):
            for path in self._trace_critical_paths(dep_id, schedule, cache):
                paths.add(path + (task_id,))

        cache[task_id] = paths
        return paths
