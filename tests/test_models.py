"""Tests for data models."""

import pytest
from datetime import date

from mcprojsim.config import DEFAULT_CONFIDENCE_LEVELS
from mcprojsim.models.project import (
    Project,
    ProjectMetadata,
    Task,
    TaskEstimate,
    Risk,
    RiskImpact,
    UncertaintyFactors,
    DistributionType,
    ImpactType,
)


class TestTaskEstimate:
    """Tests for TaskEstimate model."""

    def test_triangular_distribution_valid(self):
        """Test valid triangular distribution."""
        estimate = TaskEstimate(
            distribution=DistributionType.TRIANGULAR,
            min=1.0,
            most_likely=2.0,
            max=5.0,
        )
        assert estimate.min == 1.0
        assert estimate.most_likely == 2.0
        assert estimate.max == 5.0

    def test_triangular_distribution_invalid_range(self):
        """Test invalid triangular distribution range."""
        with pytest.raises(ValueError, match="min <= most_likely <= max"):
            TaskEstimate(
                distribution=DistributionType.TRIANGULAR,
                min=5.0,
                most_likely=2.0,
                max=10.0,
            )

    def test_triangular_distribution_missing_params(self):
        """Test triangular distribution with missing parameters."""
        with pytest.raises(ValueError, match="requires min, most_likely, and max"):
            TaskEstimate(
                distribution=DistributionType.TRIANGULAR,
                most_likely=5.0,
            )

    def test_lognormal_distribution_valid(self):
        """Test valid lognormal distribution."""
        estimate = TaskEstimate(
            distribution=DistributionType.LOGNORMAL,
            most_likely=5.0,
            standard_deviation=2.0,
        )
        assert estimate.most_likely == 5.0
        assert estimate.standard_deviation == 2.0

    def test_lognormal_distribution_missing_params(self):
        """Test lognormal distribution with missing parameters."""
        with pytest.raises(
            ValueError, match="requires most_likely and standard_deviation"
        ):
            TaskEstimate(
                distribution=DistributionType.LOGNORMAL,
                most_likely=5.0,
            )

    def test_tshirt_size_valid(self):
        """Test T-shirt size specification."""
        estimate = TaskEstimate(
            t_shirt_size="M",
        )
        assert estimate.t_shirt_size == "M"
        assert estimate.min is None
        assert estimate.most_likely is None
        assert estimate.max is None

    def test_tshirt_size_with_unit(self):
        """Test T-shirt size with custom unit."""
        estimate = TaskEstimate(
            t_shirt_size="L",
            unit="weeks",
        )
        assert estimate.t_shirt_size == "L"
        assert estimate.unit == "weeks"

    def test_story_points_valid(self):
        """Test Story Point specification."""
        estimate = TaskEstimate(story_points=5)

        assert estimate.story_points == 5
        assert estimate.unit == "storypoint"
        assert estimate.min is None
        assert estimate.most_likely is None
        assert estimate.max is None

    def test_story_points_with_explicit_unit(self):
        """Test Story Points with explicit storypoint unit."""
        estimate = TaskEstimate(story_points=8, unit="storypoint")

        assert estimate.story_points == 8
        assert estimate.unit == "storypoint"

    def test_story_points_invalid_value(self):
        """Test Story Points must use supported agile sequence values."""
        with pytest.raises(ValueError, match="Story Points must be one of"):
            TaskEstimate(story_points=4)

    def test_story_points_invalid_unit(self):
        """Test Story Points reject non-storypoint units."""
        with pytest.raises(ValueError, match="must use unit 'storypoint'"):
            TaskEstimate(story_points=5, unit="days")

    def test_multiple_symbolic_estimates_invalid(self):
        """Test that only one symbolic estimate mode may be used."""
        with pytest.raises(ValueError, match="Only one symbolic estimate"):
            TaskEstimate(t_shirt_size="M", story_points=5)

    def test_missing_estimate_values(self):
        """Test that either T-shirt size or explicit estimate is required."""
        with pytest.raises(
            ValueError,
            match="Either 't_shirt_size', 'story_points', or 'most_likely' must be specified",
        ):
            TaskEstimate()


class TestRisk:
    """Tests for Risk model."""

    def test_risk_with_float_impact(self):
        """Test risk with simple float impact."""
        risk = Risk(
            id="risk_001",
            name="Test Risk",
            probability=0.3,
            impact=5.0,
        )
        assert risk.get_impact_value() == 5.0

    def test_risk_with_absolute_impact(self):
        """Test risk with absolute impact."""
        risk = Risk(
            id="risk_001",
            name="Test Risk",
            probability=0.3,
            impact=RiskImpact(type=ImpactType.ABSOLUTE, value=10.0),
        )
        assert risk.get_impact_value() == 10.0

    def test_risk_with_percentage_impact(self):
        """Test risk with percentage impact."""
        risk = Risk(
            id="risk_001",
            name="Test Risk",
            probability=0.3,
            impact=RiskImpact(type=ImpactType.PERCENTAGE, value=20.0),
        )
        assert risk.get_impact_value(base_duration=100.0) == 20.0

    def test_risk_probability_validation(self):
        """Test risk probability validation."""
        with pytest.raises(ValueError):
            Risk(
                id="risk_001",
                name="Test Risk",
                probability=1.5,  # Invalid
                impact=5.0,
            )


class TestTask:
    """Tests for Task model."""

    def test_task_creation(self):
        """Test basic task creation."""
        task = Task(
            id="task_001",
            name="Test Task",
            estimate=TaskEstimate(min=1, most_likely=2, max=5),
        )
        assert task.id == "task_001"
        assert task.name == "Test Task"
        assert len(task.dependencies) == 0

    def test_task_with_dependencies(self):
        """Test task with dependencies."""
        task = Task(
            id="task_001",
            name="Test Task",
            estimate=TaskEstimate(min=1, most_likely=2, max=5),
            dependencies=["task_000"],
        )
        assert task.has_dependency("task_000")
        assert not task.has_dependency("task_999")

    def test_task_with_uncertainty_factors(self):
        """Test task with uncertainty factors."""
        task = Task(
            id="task_001",
            name="Test Task",
            estimate=TaskEstimate(min=1, most_likely=2, max=5),
            uncertainty_factors=UncertaintyFactors(
                team_experience="high",
                technical_complexity="low",
            ),
        )
        assert task.uncertainty_factors is not None
        assert task.uncertainty_factors.team_experience == "high"


class TestProject:
    """Tests for Project model."""

    def test_project_metadata_uses_updated_default_confidence_levels(self):
        """Test project metadata defaults include the expanded percentile range."""
        metadata = ProjectMetadata(name="Test Project", start_date=date(2025, 1, 1))

        assert metadata.confidence_levels == DEFAULT_CONFIDENCE_LEVELS

    def test_project_creation(self):
        """Test basic project creation."""
        project = Project(
            project=ProjectMetadata(
                name="Test Project",
                start_date=date(2025, 1, 1),
            ),
            tasks=[
                Task(
                    id="task_001",
                    name="Task 1",
                    estimate=TaskEstimate(min=1, most_likely=2, max=5),
                )
            ],
        )
        assert project.project.name == "Test Project"
        assert len(project.tasks) == 1

    def test_project_duplicate_task_ids(self):
        """Test project with duplicate task IDs."""
        with pytest.raises(ValueError, match="Task IDs must be unique"):
            Project(
                project=ProjectMetadata(
                    name="Test Project",
                    start_date=date(2025, 1, 1),
                ),
                tasks=[
                    Task(
                        id="task_001",
                        name="Task 1",
                        estimate=TaskEstimate(min=1, most_likely=2, max=5),
                    ),
                    Task(
                        id="task_001",
                        name="Task 2",
                        estimate=TaskEstimate(min=1, most_likely=2, max=5),
                    ),
                ],
            )

    def test_project_no_tasks(self):
        """Test project with no tasks."""
        with pytest.raises(ValueError, match="at least one task"):
            Project(
                project=ProjectMetadata(
                    name="Test Project",
                    start_date=date(2025, 1, 1),
                ),
                tasks=[],
            )

    def test_project_invalid_dependency(self):
        """Test project with invalid dependency reference."""
        with pytest.raises(ValueError, match="non-existent task"):
            Project(
                project=ProjectMetadata(
                    name="Test Project",
                    start_date=date(2025, 1, 1),
                ),
                tasks=[
                    Task(
                        id="task_001",
                        name="Task 1",
                        estimate=TaskEstimate(min=1, most_likely=2, max=5),
                        dependencies=["task_999"],  # Doesn't exist
                    )
                ],
            )

    def test_project_circular_dependency(self):
        """Test project with circular dependencies."""
        with pytest.raises(ValueError, match="Circular dependency"):
            Project(
                project=ProjectMetadata(
                    name="Test Project",
                    start_date=date(2025, 1, 1),
                ),
                tasks=[
                    Task(
                        id="task_001",
                        name="Task 1",
                        estimate=TaskEstimate(min=1, most_likely=2, max=5),
                        dependencies=["task_002"],
                    ),
                    Task(
                        id="task_002",
                        name="Task 2",
                        estimate=TaskEstimate(min=1, most_likely=2, max=5),
                        dependencies=["task_001"],
                    ),
                ],
            )

    def test_project_get_task_by_id(self):
        """Test getting task by ID."""
        project = Project(
            project=ProjectMetadata(
                name="Test Project",
                start_date=date(2025, 1, 1),
            ),
            tasks=[
                Task(
                    id="task_001",
                    name="Task 1",
                    estimate=TaskEstimate(min=1, most_likely=2, max=5),
                )
            ],
        )
        task = project.get_task_by_id("task_001")
        assert task is not None
        assert task.id == "task_001"

        task = project.get_task_by_id("task_999")
        assert task is None

    def test_project_with_risks(self):
        """Test project with risks."""
        project = Project(
            project=ProjectMetadata(
                name="Test Project",
                start_date=date(2025, 1, 1),
            ),
            tasks=[
                Task(
                    id="task_001",
                    name="Task 1",
                    estimate=TaskEstimate(min=1, most_likely=2, max=5),
                    risks=[
                        Risk(
                            id="task_risk_001",
                            name="Task Risk",
                            probability=0.2,
                            impact=3.0,
                        )
                    ],
                )
            ],
            project_risks=[
                Risk(
                    id="proj_risk_001",
                    name="Project Risk",
                    probability=0.1,
                    impact=5.0,
                )
            ],
        )
        assert len(project.tasks[0].risks) == 1
        assert len(project.project_risks) == 1

    def test_project_probability_thresholds_valid(self):
        """Test valid probability thresholds."""
        project = Project(
            project=ProjectMetadata(
                name="Test Project",
                start_date=date(2025, 1, 1),
                probability_red_threshold=0.4,
                probability_green_threshold=0.85,
            ),
            tasks=[
                Task(
                    id="task_001",
                    name="Task 1",
                    estimate=TaskEstimate(min=1, most_likely=2, max=5),
                )
            ],
        )
        assert project.project.probability_red_threshold == 0.4
        assert project.project.probability_green_threshold == 0.85

    def test_project_probability_thresholds_invalid(self):
        """Test invalid probability thresholds (red >= green)."""
        with pytest.raises(ValueError, match="must be less than"):
            Project(
                project=ProjectMetadata(
                    name="Test Project",
                    start_date=date(2025, 1, 1),
                    probability_red_threshold=0.9,
                    probability_green_threshold=0.5,
                ),
                tasks=[
                    Task(
                        id="task_001",
                        name="Task 1",
                        estimate=TaskEstimate(min=1, most_likely=2, max=5),
                    )
                ],
            )
