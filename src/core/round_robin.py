"""Round Robin scheduling using the circle (polygon) method.

Generates a complete schedule where every team plays every other team exactly once.
For N teams (even), there are N-1 rounds with N/2 matches per round.
If N is odd, a dummy team is added and any team paired with the dummy gets a bye.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.core.models import Side, Team


@dataclass
class RoundRobinMatch:
    """A single match in the round robin schedule."""

    round_number: int
    team_a: Team
    team_b: Team
    side_a: Side
    side_b: Side
    is_bye: bool = False


@dataclass
class RoundRobinScheduler:
    """Generate a full round robin schedule using the circle method.

    The circle method:
    1. Fix team 0 in position 0.
    2. Rotate teams 1..N-1 around the remaining positions.
    3. Each rotation produces one round of pairings.

    For N teams (even): N-1 rounds, N/2 matches each.
    For N teams (odd): a "BYE" placeholder is added; N rounds, (N-1)/2 real matches each.
    """

    teams: list[Team] = field(default_factory=list)

    def generate_schedule(self) -> list[list[RoundRobinMatch]]:
        """Generate the full round robin schedule.

        Returns a list of rounds, each containing a list of matches.
        """
        active_teams = [t for t in self.teams if t.active]
        n = len(active_teams)
        if n < 2:
            return []

        # If odd number, add a placeholder for byes
        use_bye = n % 2 == 1
        if use_bye:
            bye_placeholder = Team(id="__BYE__", name="BYE", active=False)
            team_list = active_teams + [bye_placeholder]
        else:
            team_list = list(active_teams)
            bye_placeholder = None

        total_teams = len(team_list)
        num_rounds = total_teams - 1
        schedule: list[list[RoundRobinMatch]] = []

        # Circle method: fix first team, rotate the rest
        fixed = team_list[0]
        rotating = team_list[1:]

        for round_num in range(num_rounds):
            round_matches: list[RoundRobinMatch] = []
            current = [fixed] + rotating

            # Pair teams: first with last, second with second-to-last, etc.
            half = total_teams // 2
            for i in range(half):
                team_a = current[i]
                team_b = current[total_teams - 1 - i]

                is_bye = (
                    bye_placeholder is not None
                    and (team_a.id == "__BYE__" or team_b.id == "__BYE__")
                )

                # Alternate sides based on round number
                if round_num % 2 == 0:
                    side_a, side_b = Side.PROPOSITION, Side.OPPOSITION
                else:
                    side_a, side_b = Side.OPPOSITION, Side.PROPOSITION

                match = RoundRobinMatch(
                    round_number=round_num + 1,
                    team_a=team_a,
                    team_b=team_b,
                    side_a=side_a,
                    side_b=side_b,
                    is_bye=is_bye,
                )
                round_matches.append(match)

            schedule.append(round_matches)

            # Rotate: move last element to the front of the rotating list
            rotating = [rotating[-1]] + rotating[:-1]

        return schedule

    def get_total_rounds(self) -> int:
        """Return the number of rounds needed."""
        n = len([t for t in self.teams if t.active])
        if n < 2:
            return 0
        if n % 2 == 1:
            return n
        return n - 1

    def get_matches_per_round(self) -> int:
        """Return the number of real matches per round."""
        n = len([t for t in self.teams if t.active])
        if n < 2:
            return 0
        return n // 2

    def validate_schedule(self, schedule: list[list[RoundRobinMatch]]) -> bool:
        """Validate that every pair of active teams meets exactly once."""
        active_ids = {t.id for t in self.teams if t.active}
        matchups: dict[tuple[str, str], int] = {}

        for rnd in schedule:
            for match in rnd:
                if match.is_bye:
                    continue
                pair = tuple(sorted([match.team_a.id, match.team_b.id]))
                matchups[pair] = matchups.get(pair, 0) + 1

        # Check completeness: every pair should appear exactly once
        expected_pairs = set()
        id_list = sorted(active_ids)
        for i in range(len(id_list)):
            for j in range(i + 1, len(id_list)):
                expected_pairs.add((id_list[i], id_list[j]))

        if set(matchups.keys()) != expected_pairs:
            return False

        return all(count == 1 for count in matchups.values())
