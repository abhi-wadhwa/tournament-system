"""British Parliamentary (BP) tabulation engine.

Implements WUDC-style BP tabulation:
- 4 teams per room: OG, OO, CG, CO
- Ranking: 1st=3pts, 2nd=2pts, 3rd=1pt, 4th=0pts
- Speaker scores: 50-100 range
- Standings: sort by team points, then total speaker score
- Break calculation with institutional caps
- Power-pairing for subsequent rounds (bracket by team points)
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from itertools import combinations

from src.core.models import BPPosition, BPRoundResult, Team


# Points awarded for each rank position
BP_RANK_POINTS = {1: 3, 2: 2, 3: 1, 4: 0}

# Valid speaker score range
MIN_SPEAKER_SCORE = 50
MAX_SPEAKER_SCORE = 100


@dataclass
class BPRoom:
    """A room draw for a single BP round."""

    room_number: int = 0
    og_team: Team | None = None
    oo_team: Team | None = None
    cg_team: Team | None = None
    co_team: Team | None = None


@dataclass
class BPTabulator:
    """British Parliamentary tabulation engine.

    Usage:
    1. Add teams via the teams list.
    2. Call generate_draw() to get a round draw.
    3. Record results with record_result().
    4. Call get_tab() for standings at any time.
    5. Call calculate_break() to determine which teams advance.
    """

    teams: list[Team] = field(default_factory=list)
    results: list[BPRoundResult] = field(default_factory=list)
    current_round: int = 0

    def generate_draw(self) -> list[BPRoom]:
        """Generate a draw for the next round.

        Round 1: Random draw.
        Subsequent rounds: Power-paired (teams grouped by points,
        then shuffled within brackets and assigned positions).
        """
        active_teams = [t for t in self.teams if t.active]
        n = len(active_teams)

        if n < 4:
            raise ValueError("Need at least 4 teams for BP format")

        # Trim to multiple of 4 (teams not drawn get a swing/sit-out)
        usable = (n // 4) * 4
        if usable < 4:
            raise ValueError("Need at least 4 active teams for BP format")

        self.current_round += 1

        if self.current_round == 1:
            # Random draw for round 1
            draw_teams = list(active_teams[:usable])
            random.shuffle(draw_teams)
        else:
            # Power-pair: sort by points, then speaker score
            sorted_teams = sorted(
                active_teams[:usable],
                key=lambda t: (t.points, t.total_speaker_score),
                reverse=True,
            )
            draw_teams = self._power_pair_bp(sorted_teams)

        rooms: list[BPRoom] = []
        for i in range(0, len(draw_teams), 4):
            room_teams = draw_teams[i : i + 4]
            # Assign positions, trying to balance position history
            assigned = self._assign_positions(room_teams)
            room = BPRoom(
                room_number=i // 4 + 1,
                og_team=assigned[BPPosition.OG],
                oo_team=assigned[BPPosition.OO],
                cg_team=assigned[BPPosition.CG],
                co_team=assigned[BPPosition.CO],
            )
            rooms.append(room)

        return rooms

    def _power_pair_bp(self, sorted_teams: list[Team]) -> list[Team]:
        """Power-pair teams for BP.

        Groups teams into brackets of 4 by their points, then shuffles
        within each bracket to create rooms.
        """
        result: list[Team] = []
        for i in range(0, len(sorted_teams), 4):
            bracket = sorted_teams[i : i + 4]
            random.shuffle(bracket)
            result.extend(bracket)
        return result

    def _assign_positions(
        self, room_teams: list[Team]
    ) -> dict[BPPosition, Team]:
        """Assign BP positions to 4 teams, balancing position history.

        Tries to give each team the position they have had the fewest times.
        Uses a simple greedy assignment.
        """
        positions = [BPPosition.OG, BPPosition.OO, BPPosition.CG, BPPosition.CO]

        # Score each team-position pair by how many times they've had that position
        # Lower count = preferred
        best_assignment: dict[BPPosition, Team] = {}
        remaining_teams = list(room_teams)
        remaining_positions = list(positions)

        for _ in range(4):
            best_score = float("inf")
            best_team = remaining_teams[0]
            best_pos = remaining_positions[0]

            for team in remaining_teams:
                for pos in remaining_positions:
                    count = sum(
                        1 for h in team.bp_position_history if h == pos
                    )
                    if count < best_score:
                        best_score = count
                        best_team = team
                        best_pos = pos

            best_assignment[best_pos] = best_team
            remaining_teams.remove(best_team)
            remaining_positions.remove(best_pos)

        return best_assignment

    def record_result(self, result: BPRoundResult) -> None:
        """Record a BP round result and update team scores.

        Validates ranks (each of 1-4 must appear exactly once) and
        speaker scores (must be in valid range).
        """
        ranks = [result.og_rank, result.oo_rank, result.cg_rank, result.co_rank]
        if sorted(ranks) != [1, 2, 3, 4]:
            raise ValueError(
                f"Invalid ranks: {ranks}. Must be a permutation of [1, 2, 3, 4]"
            )

        # Validate speaker scores
        for speaker_id, score in result.speaker_scores.items():
            if score < MIN_SPEAKER_SCORE or score > MAX_SPEAKER_SCORE:
                raise ValueError(
                    f"Speaker score {score} for {speaker_id} outside valid range "
                    f"[{MIN_SPEAKER_SCORE}, {MAX_SPEAKER_SCORE}]"
                )

        self.results.append(result)

        # Update teams
        team_rank_map = {
            result.og_team_id: (result.og_rank, BPPosition.OG),
            result.oo_team_id: (result.oo_rank, BPPosition.OO),
            result.cg_team_id: (result.cg_rank, BPPosition.CG),
            result.co_team_id: (result.co_rank, BPPosition.CO),
        }

        for team in self.teams:
            if team.id in team_rank_map:
                rank, position = team_rank_map[team.id]
                team.points += BP_RANK_POINTS[rank]
                team.bp_position_history.append(position)

                # Aggregate speaker scores for this team
                team_speaker_total = 0.0
                speaker_count = 0
                for speaker in team.speakers:
                    if speaker.id in result.speaker_scores:
                        team_speaker_total += result.speaker_scores[speaker.id]
                        speaker_count += 1

                if speaker_count > 0:
                    team.speaker_scores.append(team_speaker_total)

    def get_tab(self) -> list[Team]:
        """Get current standings sorted by team points, then total speaker score."""
        return sorted(
            self.teams,
            key=lambda t: (t.points, t.total_speaker_score),
            reverse=True,
        )

    def calculate_break(
        self,
        break_size: int,
        institutional_cap: int = 0,
    ) -> list[Team]:
        """Calculate which teams break (advance to elimination rounds).

        Args:
            break_size: Number of teams to break.
            institutional_cap: Maximum teams from any single institution
                that can break. 0 means no cap.

        Returns:
            List of breaking teams in order.
        """
        standings = self.get_tab()
        breaking: list[Team] = []
        institution_counts: dict[str, int] = {}

        for team in standings:
            if len(breaking) >= break_size:
                break

            if institutional_cap > 0 and team.institution is not None:
                inst_id = team.institution.id
                current_count = institution_counts.get(inst_id, 0)
                if current_count >= institutional_cap:
                    continue  # Skip this team; institution already at cap
                institution_counts[inst_id] = current_count + 1

            breaking.append(team)

        return breaking

    def get_speaker_tab(self) -> list[tuple[str, str, float]]:
        """Get individual speaker standings.

        Returns list of (speaker_id, speaker_name, total_score) sorted descending.
        """
        speaker_totals: dict[str, tuple[str, float]] = {}

        for result in self.results:
            for speaker_id, score in result.speaker_scores.items():
                if speaker_id in speaker_totals:
                    name, total = speaker_totals[speaker_id]
                    speaker_totals[speaker_id] = (name, total + score)
                else:
                    # Find speaker name
                    name = speaker_id
                    for team in self.teams:
                        for speaker in team.speakers:
                            if speaker.id == speaker_id:
                                name = speaker.name
                                break
                    speaker_totals[speaker_id] = (name, score)

        result_list = [
            (sid, name, total) for sid, (name, total) in speaker_totals.items()
        ]
        return sorted(result_list, key=lambda x: x[2], reverse=True)

    def validate_draw(self, rooms: list[BPRoom]) -> list[str]:
        """Validate a draw for obvious issues.

        Returns a list of warning messages (empty if no issues).
        """
        warnings: list[str] = []
        seen_teams: set[str] = set()

        for room in rooms:
            room_team_ids = []
            for team in [room.og_team, room.oo_team, room.cg_team, room.co_team]:
                if team is None:
                    warnings.append(f"Room {room.room_number} has an empty position")
                    continue
                if team.id in seen_teams:
                    warnings.append(
                        f"Team {team.name} appears in multiple rooms"
                    )
                seen_teams.add(team.id)
                room_team_ids.append(team.id)

            # Check for institutional clashes in room
            institutions = []
            for team in [room.og_team, room.oo_team, room.cg_team, room.co_team]:
                if team and team.institution:
                    institutions.append(team.institution.id)
            if len(institutions) != len(set(institutions)):
                warnings.append(
                    f"Room {room.room_number} has teams from the same institution"
                )

        return warnings
