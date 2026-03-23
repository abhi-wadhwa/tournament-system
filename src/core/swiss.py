"""Swiss pairing algorithm.

Implements power-paired Swiss with:
- Sort by points (descending), then speaker score tiebreak
- Top-down pairing within point brackets
- Rematch avoidance with backtracking
- Side balancing (alternate prop/opp)
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.core.models import RoundResult, Side, Team


@dataclass
class SwissPairing:
    """Generate Swiss-system pairings for a round.

    Swiss pairing works by:
    1. Sorting teams by cumulative points (power pairing).
    2. Pairing teams top-down within the sorted list.
    3. Avoiding rematches unless no valid alternative exists.
    4. Balancing proposition/opposition sides across rounds.
    """

    teams: list[Team] = field(default_factory=list)
    avoid_rematches: bool = True
    max_backtrack_depth: int = 50

    def generate_pairings(self) -> list[tuple[Team, Team, Side, Side]]:
        """Generate pairings for the next round.

        Returns a list of (team_a, team_b, side_a, side_b) tuples.
        team_a plays side_a, team_b plays side_b.
        """
        active_teams = [t for t in self.teams if t.active]
        if len(active_teams) < 2:
            return []

        # Sort by points descending, then total speaker score descending
        sorted_teams = sorted(
            active_teams,
            key=lambda t: (t.points, t.total_speaker_score),
            reverse=True,
        )

        # Handle odd number of teams: lowest-ranked team gets a bye
        bye_team = None
        if len(sorted_teams) % 2 == 1:
            bye_team = sorted_teams.pop()

        pairings = self._pair_with_backtracking(sorted_teams)

        if bye_team is not None:
            # Give the bye team a win with average score
            bye_team.wins += 1
            bye_team.points += 1

        return pairings

    def _pair_with_backtracking(
        self, teams: list[Team]
    ) -> list[tuple[Team, Team, Side, Side]]:
        """Pair teams using backtracking to avoid rematches."""
        n = len(teams)
        if n == 0:
            return []

        result: list[tuple[Team, Team, Side, Side]] = []
        used = [False] * n

        def _backtrack(depth: int) -> bool:
            # Find the first unused team
            first_unused = -1
            for i in range(n):
                if not used[i]:
                    first_unused = i
                    break
            if first_unused == -1:
                return True  # All teams paired

            used[first_unused] = True

            # Try pairing with the next available teams (prefer adjacent in ranking)
            for j in range(first_unused + 1, n):
                if used[j]:
                    continue

                team_a = teams[first_unused]
                team_b = teams[j]

                # Check rematch constraint
                if self.avoid_rematches and self._is_rematch(team_a, team_b):
                    if depth < self.max_backtrack_depth:
                        continue  # Try another opponent
                    # Past max backtrack depth, allow rematch

                used[j] = True
                side_a, side_b = self._assign_sides(team_a, team_b)
                result.append((team_a, team_b, side_a, side_b))

                if _backtrack(depth + 1):
                    return True

                # Undo
                result.pop()
                used[j] = False

            used[first_unused] = False
            return False

        success = _backtrack(0)

        if not success:
            # Fallback: pair without rematch avoidance
            result.clear()
            for i in range(0, n - 1, 2):
                team_a = teams[i]
                team_b = teams[i + 1]
                side_a, side_b = self._assign_sides(team_a, team_b)
                result.append((team_a, team_b, side_a, side_b))

        return result

    def _is_rematch(self, team_a: Team, team_b: Team) -> bool:
        """Check if two teams have already faced each other."""
        return team_b.id in team_a.opponent_history

    def _assign_sides(self, team_a: Team, team_b: Team) -> tuple[Side, Side]:
        """Assign proposition/opposition sides to balance history.

        Prefers to give each team the side they have had fewer times.
        """
        a_prop_count = sum(1 for s in team_a.side_history if s == Side.PROPOSITION)
        a_opp_count = sum(1 for s in team_a.side_history if s == Side.OPPOSITION)
        b_prop_count = sum(1 for s in team_b.side_history if s == Side.PROPOSITION)
        b_opp_count = sum(1 for s in team_b.side_history if s == Side.OPPOSITION)

        a_balance = a_prop_count - a_opp_count  # positive = more prop
        b_balance = b_prop_count - b_opp_count

        if a_balance < b_balance:
            # A has had fewer prop, give A prop
            return Side.PROPOSITION, Side.OPPOSITION
        elif a_balance > b_balance:
            # B has had fewer prop, give B prop
            return Side.OPPOSITION, Side.PROPOSITION
        else:
            # Equal balance: give the higher-ranked team prop
            return Side.PROPOSITION, Side.OPPOSITION

    def record_result(self, result: RoundResult) -> None:
        """Record a round result and update team records."""
        prop_team = None
        opp_team = None
        for team in self.teams:
            if team.id == result.proposition_team_id:
                prop_team = team
            elif team.id == result.opposition_team_id:
                opp_team = team

        if prop_team is None or opp_team is None:
            raise ValueError("Teams in result not found in tournament")

        # Update opponent history
        prop_team.opponent_history.append(opp_team.id)
        opp_team.opponent_history.append(prop_team.id)

        # Update side history
        prop_team.side_history.append(Side.PROPOSITION)
        opp_team.side_history.append(Side.OPPOSITION)

        # Update speaker scores
        prop_team.speaker_scores.append(result.proposition_score)
        opp_team.speaker_scores.append(result.opposition_score)

        # Update wins/losses/points
        if result.winner_id == prop_team.id:
            prop_team.wins += 1
            prop_team.points += 1
            opp_team.losses += 1
        elif result.winner_id == opp_team.id:
            opp_team.wins += 1
            opp_team.points += 1
            prop_team.losses += 1
        else:
            # Draw
            prop_team.draws += 1
            opp_team.draws += 1
            prop_team.points += 0.5
            opp_team.points += 0.5

    def get_standings(self) -> list[Team]:
        """Return teams sorted by points then total speaker score."""
        return sorted(
            self.teams,
            key=lambda t: (t.points, t.total_speaker_score),
            reverse=True,
        )
