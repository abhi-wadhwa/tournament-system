"""Tests for judge allocation engine."""

from __future__ import annotations

import pytest

from src.core.judge import JudgeAllocator, RoomDebate
from src.core.models import Institution, Judge, Room


def _make_institutions(n: int) -> list[Institution]:
    """Create n institutions."""
    return [Institution(name=f"Inst {i}") for i in range(1, n + 1)]


def _make_judges(
    n: int, institutions: list[Institution] | None = None
) -> list[Judge]:
    """Create n judges with varied experience levels."""
    judges = []
    for i in range(1, n + 1):
        inst = institutions[(i - 1) % len(institutions)] if institutions else None
        judge = Judge(
            name=f"Judge {i}",
            institution=inst,
            experience_level=min(10, i),
        )
        judges.append(judge)
    return judges


def _make_debates(
    n: int, institutions: list[Institution] | None = None
) -> list[RoomDebate]:
    """Create n debates with 2 teams each."""
    debates = []
    for i in range(n):
        room = Room(name=f"Room {i + 1}", priority=n - i)
        team_ids = [f"team_{i * 2 + 1}", f"team_{i * 2 + 2}"]
        inst_ids = []
        if institutions and len(institutions) > i * 2 + 1:
            inst_ids = [
                institutions[i * 2].id,
                institutions[i * 2 + 1].id,
            ]
        debates.append(
            RoomDebate(room=room, team_ids=team_ids, institution_ids=inst_ids)
        )
    return debates


class TestJudgeAllocation:
    """Test basic judge allocation."""

    def test_all_rooms_get_judges(self) -> None:
        judges = _make_judges(4)
        allocator = JudgeAllocator(judges=judges, panel_size=1)
        debates = _make_debates(4)

        assignments = allocator.allocate(debates)
        assert len(assignments) == 4

        for assignment in assignments:
            assert assignment.chair.name != "UNASSIGNED"

    def test_panel_of_three(self) -> None:
        judges = _make_judges(9)
        allocator = JudgeAllocator(judges=judges, panel_size=3)
        debates = _make_debates(3)

        assignments = allocator.allocate(debates)
        for assignment in assignments:
            total = 1 + len(assignment.wings)
            assert total == 3

    def test_chair_is_most_experienced(self) -> None:
        judges = _make_judges(6)
        allocator = JudgeAllocator(judges=judges, panel_size=3)
        debates = _make_debates(2)

        assignments = allocator.allocate(debates)
        for assignment in assignments:
            for wing in assignment.wings:
                assert assignment.chair.experience_level >= wing.experience_level

    def test_no_judge_assigned_twice(self) -> None:
        judges = _make_judges(4)
        allocator = JudgeAllocator(judges=judges, panel_size=1)
        debates = _make_debates(4)

        assignments = allocator.allocate(debates)
        assigned_ids: set[str] = set()
        for assignment in assignments:
            all_judges = [assignment.chair] + assignment.wings
            for judge in all_judges:
                assert judge.id not in assigned_ids, f"{judge.name} assigned twice"
                assigned_ids.add(judge.id)


class TestJudgeConflicts:
    """Test that institutional and explicit conflicts are respected."""

    def test_no_institutional_conflicts(self) -> None:
        insts = _make_institutions(4)

        # Judge from Inst 1
        judge1 = Judge(name="Judge A", institution=insts[0], experience_level=8)
        # Judge from Inst 2
        judge2 = Judge(name="Judge B", institution=insts[1], experience_level=7)
        # Judge from Inst 3
        judge3 = Judge(name="Judge C", institution=insts[2], experience_level=6)
        # Judge from Inst 4
        judge4 = Judge(name="Judge D", institution=insts[3], experience_level=5)

        allocator = JudgeAllocator(
            judges=[judge1, judge2, judge3, judge4], panel_size=1
        )

        # Debate with teams from Inst 1 and Inst 2
        debate = RoomDebate(
            room=Room(name="Room 1", priority=1),
            team_ids=["team_1", "team_2"],
            institution_ids=[insts[0].id, insts[1].id],
        )

        assignments = allocator.allocate([debate])
        assert len(assignments) == 1

        chair = assignments[0].chair
        # Chair must NOT be from Inst 1 or Inst 2
        assert chair.institution is not None
        assert chair.institution.id not in (insts[0].id, insts[1].id)

    def test_explicit_conflicts_avoided(self) -> None:
        judge1 = Judge(
            name="Judge A",
            experience_level=10,
            conflicts=["team_1"],  # Hard conflict with team_1
        )
        judge2 = Judge(name="Judge B", experience_level=5)

        allocator = JudgeAllocator(judges=[judge1, judge2], panel_size=1)

        debate = RoomDebate(
            room=Room(name="Room 1", priority=1),
            team_ids=["team_1", "team_2"],
            institution_ids=[],
        )

        assignments = allocator.allocate([debate])
        # Judge A has conflict with team_1, so Judge B should be assigned
        assert assignments[0].chair.name == "Judge B"

    def test_no_conflicts_in_any_round(self) -> None:
        """End-to-end test: no conflicts in a multi-room allocation."""
        insts = _make_institutions(6)
        judges = []
        for i in range(6):
            judges.append(
                Judge(
                    name=f"Judge {i + 1}",
                    institution=insts[i],
                    experience_level=10 - i,
                )
            )

        allocator = JudgeAllocator(judges=judges, panel_size=1)

        debates = []
        for i in range(3):
            room = Room(name=f"Room {i + 1}", priority=3 - i)
            debates.append(
                RoomDebate(
                    room=room,
                    team_ids=[f"team_{2 * i + 1}", f"team_{2 * i + 2}"],
                    institution_ids=[insts[2 * i].id, insts[2 * i + 1].id],
                )
            )

        assignments = allocator.allocate(debates)
        violations = allocator.validate_allocation(assignments, debates)
        assert len(violations) == 0, f"Conflicts found: {violations}"


class TestJudgeExperienceBalancing:
    """Test that high-priority rooms get more experienced judges."""

    def test_highest_priority_room_gets_best_judge(self) -> None:
        judges = _make_judges(3)
        allocator = JudgeAllocator(judges=judges, panel_size=1)

        debates = [
            RoomDebate(
                room=Room(name="Low", priority=1),
                team_ids=["t1", "t2"],
                institution_ids=[],
            ),
            RoomDebate(
                room=Room(name="High", priority=10),
                team_ids=["t3", "t4"],
                institution_ids=[],
            ),
            RoomDebate(
                room=Room(name="Mid", priority=5),
                team_ids=["t5", "t6"],
                institution_ids=[],
            ),
        ]

        assignments = allocator.allocate(debates)
        # Find assignment for the high-priority room
        high_assignment = None
        for a in assignments:
            if a.room.name == "High":
                high_assignment = a
                break

        assert high_assignment is not None
        # The best judge (experience 3) should be in the high-priority room
        assert high_assignment.chair.experience_level == max(
            j.experience_level for j in judges
        )


class TestJudgeValidation:
    """Test allocation validation."""

    def test_valid_allocation_no_violations(self) -> None:
        judges = _make_judges(2)
        allocator = JudgeAllocator(judges=judges, panel_size=1)
        debates = _make_debates(2)

        assignments = allocator.allocate(debates)
        violations = allocator.validate_allocation(assignments, debates)
        assert len(violations) == 0

    def test_detect_institutional_violation(self) -> None:
        """Manually construct a violation to test detection."""
        from src.core.judge import JudgeAssignment

        inst = Institution(name="Conflict Inst")
        judge = Judge(name="Bad Judge", institution=inst)
        room = Room(name="Room 1")
        debate = RoomDebate(
            room=room,
            team_ids=["team_1"],
            institution_ids=[inst.id],
        )

        assignment = JudgeAssignment(
            room=room,
            chair=judge,
            wings=[],
            team_ids=["team_1"],
        )

        allocator = JudgeAllocator(judges=[judge])
        violations = allocator.validate_allocation([assignment], [debate])
        assert len(violations) > 0
        assert "institutional conflict" in violations[0]


class TestJudgeLoad:
    """Test judge workload tracking."""

    def test_load_counting(self) -> None:
        from src.core.judge import JudgeAssignment

        judge1 = Judge(name="J1")
        judge2 = Judge(name="J2")

        round1 = [
            JudgeAssignment(
                room=Room(name="R1"), chair=judge1, wings=[], team_ids=[]
            ),
            JudgeAssignment(
                room=Room(name="R2"), chair=judge2, wings=[], team_ids=[]
            ),
        ]
        round2 = [
            JudgeAssignment(
                room=Room(name="R1"), chair=judge1, wings=[], team_ids=[]
            ),
        ]

        allocator = JudgeAllocator(judges=[judge1, judge2])
        load = allocator.get_judge_load([round1, round2])

        assert load[judge1.id] == 2
        assert load[judge2.id] == 1


class TestJudgeEdgeCases:
    """Test edge cases."""

    def test_no_judges_raises(self) -> None:
        allocator = JudgeAllocator(judges=[], panel_size=1)
        debates = _make_debates(1)
        with pytest.raises(ValueError):
            allocator.allocate(debates)

    def test_inactive_judges_excluded(self) -> None:
        judges = _make_judges(3)
        judges[0].active = False
        judges[1].active = False
        allocator = JudgeAllocator(judges=judges, panel_size=1)
        debates = _make_debates(1)

        assignments = allocator.allocate(debates)
        assert assignments[0].chair.name == "Judge 3"

    def test_more_rooms_than_judges(self) -> None:
        judges = _make_judges(2)
        allocator = JudgeAllocator(judges=judges, panel_size=1)
        debates = _make_debates(4)

        assignments = allocator.allocate(debates)
        # 2 rooms get real judges, 2 get UNASSIGNED
        assigned_count = sum(
            1 for a in assignments if a.chair.name != "UNASSIGNED"
        )
        assert assigned_count == 2

    def test_avoidance_penalty_applied(self) -> None:
        """Judges with avoidances should be penalized but not excluded."""
        judge1 = Judge(
            name="Avoidant Judge",
            experience_level=10,
            avoidances=["team_1"],
        )
        judge2 = Judge(
            name="Clean Judge",
            experience_level=5,
        )

        allocator = JudgeAllocator(judges=[judge1, judge2], panel_size=1)

        debate = RoomDebate(
            room=Room(name="Room 1", priority=1),
            team_ids=["team_1", "team_2"],
            institution_ids=[],
        )

        assignments = allocator.allocate([debate])
        # The avoidant judge has score 10-3=7, clean judge has score 5
        # So avoidant judge should still be picked (7 > 5), but is penalized
        assert assignments[0].chair.name == "Avoidant Judge"
