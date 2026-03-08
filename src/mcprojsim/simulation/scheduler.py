"""Task scheduler with dependency resolution."""

from typing import Dict, List, Set
from mcprojsim.models.project import Project


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
        self, task_durations: Dict[str, float]
    ) -> Dict[str, Dict[str, float]]:
        """Schedule tasks respecting dependencies.

        Args:
            task_durations: Dictionary mapping task IDs to their durations

        Returns:
            Dictionary mapping task IDs to their schedule info:
            {'start': start_time, 'end': end_time, 'duration': duration}
        """
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
