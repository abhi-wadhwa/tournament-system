"""Judge allocation engine using constraint satisfaction.

Handles:
- Hard conflicts: judge must not see teams from their own institution
- Soft avoidances: judge prefers not to see certain teams
- Experience balancing: higher-priority rooms get more experienced judges
- Multi-judge panels: chair + wing judges
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from src.core.models import Judge, Room, Team


@dataclass
class JudgeAssignment:
    """Assignment of judges to a room for one round."""

    room: Room
    chair: Judge
    wings: list[Judge] = field(default_factory=list)
    team_ids: list[str] = field(default_factory=list)


@dataclass
class RoomDebate:
    """Describes a debate happening in a room (teams + room info)."""

    room: Room
    team_ids: list[str] = field(default_factory=list)
    institution_ids: list[str] = field(default_factory=list)


@dataclass
class JudgeAllocator:
    """Allocate judges to rooms while respecting conflicts and balancing experience.

    Algorithm:
    1. Score each judge-room pair based on conflicts and experience match.
    2. Sort rooms by priority (highest first).
    3. Assign best available judges to highest-priority rooms first.
    4. Chair is the most experienced judge assigned to each room.

    Constraints:
    - Hard: judge must not share institution with any team in room.
    - Hard: judge must not be in their explicit conflicts list for any team.
    - Soft: try to avoid teams in judge's avoidances list (penalized but allowed).
    """

    judges: list[Judge] = field(default_factory=list)
    panel_size: int = 1  # 1 = solo, 3 = chair + 2 wings, etc.

    def allocate(self, debates: list[RoomDebate]) -> list[JudgeAssignment]:
        """Allocate judges to debates for one round.

        Args:
            debates: list of RoomDebate describing each room's teams.

        Returns:
            List of JudgeAssignment objects.
        """
        available_judges = [j for j in self.judges if j.active]
        if not available_judges:
            raise ValueError("No active judges available")

        # Sort rooms by priority descending (high priority rooms first)
        sorted_debates = sorted(debates, key=lambda d: d.room.priority, reverse=True)

        # Sort judges by experience descending
        sorted_judges = sorted(
            available_judges, key=lambda j: j.experience_level, reverse=True
        )

        used_judge_ids: set[str] = set()
        assignments: list[JudgeAssignment] = []

        for debate in sorted_debates:
            # Score and rank available judges for this room
            candidates: list[tuple[float, Judge]] = []
            for judge in sorted_judges:
                if judge.id in used_judge_ids:
                    continue

                score = self._score_judge_for_room(judge, debate)
                if score is None:
                    continue  # Hard conflict, cannot assign

                candidates.append((score, judge))

            # Sort by score descending (higher = better fit)
            candidates.sort(key=lambda x: x[0], reverse=True)

            # Assign judges (up to panel_size)
            assigned_judges: list[Judge] = []
            for _score, judge in candidates:
                if len(assigned_judges) >= self.panel_size:
                    break
                assigned_judges.append(judge)
                used_judge_ids.add(judge.id)

            if not assigned_judges:
                # No valid judges available; create assignment with empty panel
                assignments.append(
                    JudgeAssignment(
                        room=debate.room,
                        chair=Judge(name="UNASSIGNED"),
                        wings=[],
                        team_ids=debate.team_ids,
                    )
                )
                continue

            # Chair is the most experienced
            assigned_judges.sort(key=lambda j: j.experience_level, reverse=True)
            chair = assigned_judges[0]
            wings = assigned_judges[1:]

            assignments.append(
                JudgeAssignment(
                    room=debate.room,
                    chair=chair,
                    wings=wings,
                    team_ids=debate.team_ids,
                )
            )

        return assignments

    def _score_judge_for_room(
        self, judge: Judge, debate: RoomDebate
    ) -> Optional[float]:
        """Score a judge for a room. Returns None if hard conflict exists.

        Scoring:
        - Base score = judge experience level (0-10)
        - Penalty for each soft avoidance in room (-3 each)
        - None (excluded) if hard conflict exists
        """
        # Check hard conflicts: institutional
        if judge.institution is not None:
            for inst_id in debate.institution_ids:
                if judge.institution.id == inst_id:
                    return None  # Hard conflict

        # Check hard conflicts: explicit conflict list
        for team_id in debate.team_ids:
            if team_id in judge.conflicts:
                return None  # Hard conflict

        # Base score from experience
        score = float(judge.experience_level)

        # Penalty for soft avoidances
        for team_id in debate.team_ids:
            if team_id in judge.avoidances:
                score -= 3.0

        return score

    def validate_allocation(
        self, assignments: list[JudgeAssignment], debates: list[RoomDebate]
    ) -> list[str]:
        """Validate that all allocations respect hard constraints.

        Returns a list of violation messages (empty = valid).
        """
        violations: list[str] = []

        # Build a map of debate team institutions
        debate_map: dict[str, RoomDebate] = {}
        for debate in debates:
            debate_map[debate.room.id] = debate

        for assignment in assignments:
            debate = debate_map.get(assignment.room.id)
            if debate is None:
                continue

            all_judges = [assignment.chair] + assignment.wings
            for judge in all_judges:
                if judge.name == "UNASSIGNED":
                    violations.append(
                        f"Room {assignment.room.name}: no judge assigned"
                    )
                    continue

                # Check institutional conflicts
                if judge.institution is not None:
                    for inst_id in debate.institution_ids:
                        if judge.institution.id == inst_id:
                            violations.append(
                                f"Judge {judge.name} has institutional conflict "
                                f"in room {assignment.room.name}"
                            )

                # Check explicit conflicts
                for team_id in debate.team_ids:
                    if team_id in judge.conflicts:
                        violations.append(
                            f"Judge {judge.name} has explicit conflict with "
                            f"team {team_id} in room {assignment.room.name}"
                        )

        return violations

    def get_judge_load(self, rounds_assignments: list[list[JudgeAssignment]]) -> dict[str, int]:
        """Get the number of rounds each judge has been assigned to.

        Useful for balancing workload across rounds.
        """
        load: dict[str, int] = {}
        for round_assignments in rounds_assignments:
            for assignment in round_assignments:
                all_judges = [assignment.chair] + assignment.wings
                for judge in all_judges:
                    load[judge.id] = load.get(judge.id, 0) + 1
        return load
