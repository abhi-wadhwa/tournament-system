"""Tests for Round Robin scheduling."""

from __future__ import annotations

import pytest

from src.core.models import Institution, Speaker, Team
from src.core.round_robin import RoundRobinScheduler


def _make_teams(n: int) -> list[Team]:
    """Create n teams."""
    return [
        Team(name=f"Team {i}", seed=i)
        for i in range(1, n + 1)
    ]


class TestRoundRobinSchedule:
    """Test schedule generation."""

    def test_even_teams_correct_rounds(self) -> None:
        teams = _make_teams(6)
        engine = RoundRobinScheduler(teams=teams)
        schedule = engine.generate_schedule()
        assert len(schedule) == 5  # N-1 rounds

    def test_odd_teams_correct_rounds(self) -> None:
        teams = _make_teams(5)
        engine = RoundRobinScheduler(teams=teams)
        schedule = engine.generate_schedule()
        assert len(schedule) == 5  # N rounds (with bye placeholder)

    def test_even_teams_correct_matches_per_round(self) -> None:
        teams = _make_teams(6)
        engine = RoundRobinScheduler(teams=teams)
        schedule = engine.generate_schedule()
        for rnd in schedule:
            assert len(rnd) == 3  # N/2 matches

    def test_every_pair_meets_exactly_once(self) -> None:
        teams = _make_teams(6)
        engine = RoundRobinScheduler(teams=teams)
        schedule = engine.generate_schedule()

        matchups: dict[tuple[str, str], int] = {}
        for rnd in schedule:
            for match in rnd:
                if match.is_bye:
                    continue
                pair = tuple(sorted([match.team_a.id, match.team_b.id]))
                matchups[pair] = matchups.get(pair, 0) + 1

        # C(6,2) = 15 unique matchups
        assert len(matchups) == 15
        for pair, count in matchups.items():
            assert count == 1, f"Pair {pair} met {count} times"

    def test_odd_teams_each_gets_one_bye(self) -> None:
        teams = _make_teams(5)
        engine = RoundRobinScheduler(teams=teams)
        schedule = engine.generate_schedule()

        bye_counts: dict[str, int] = {t.id: 0 for t in teams}
        for rnd in schedule:
            for match in rnd:
                if match.is_bye:
                    # Identify the real team getting the bye
                    if match.team_a.id != "__BYE__":
                        bye_counts[match.team_a.id] += 1
                    if match.team_b.id != "__BYE__":
                        bye_counts[match.team_b.id] += 1

        for team_id, count in bye_counts.items():
            assert count == 1, f"Team {team_id} had {count} byes, expected 1"

    def test_no_team_plays_twice_in_one_round(self) -> None:
        teams = _make_teams(8)
        engine = RoundRobinScheduler(teams=teams)
        schedule = engine.generate_schedule()

        for rnd_idx, rnd in enumerate(schedule):
            seen: set[str] = set()
            for match in rnd:
                for team in [match.team_a, match.team_b]:
                    if team.id == "__BYE__":
                        continue
                    assert team.id not in seen, (
                        f"Team {team.name} appears twice in round {rnd_idx + 1}"
                    )
                    seen.add(team.id)


class TestRoundRobinValidation:
    """Test schedule validation."""

    def test_valid_schedule_passes(self) -> None:
        teams = _make_teams(6)
        engine = RoundRobinScheduler(teams=teams)
        schedule = engine.generate_schedule()
        assert engine.validate_schedule(schedule) is True

    def test_valid_odd_schedule_passes(self) -> None:
        teams = _make_teams(7)
        engine = RoundRobinScheduler(teams=teams)
        schedule = engine.generate_schedule()
        assert engine.validate_schedule(schedule) is True


class TestRoundRobinEdgeCases:
    """Test edge cases."""

    def test_two_teams(self) -> None:
        teams = _make_teams(2)
        engine = RoundRobinScheduler(teams=teams)
        schedule = engine.generate_schedule()
        assert len(schedule) == 1
        assert len(schedule[0]) == 1

    def test_three_teams(self) -> None:
        teams = _make_teams(3)
        engine = RoundRobinScheduler(teams=teams)
        schedule = engine.generate_schedule()
        assert len(schedule) == 3

    def test_single_team_returns_empty(self) -> None:
        teams = _make_teams(1)
        engine = RoundRobinScheduler(teams=teams)
        schedule = engine.generate_schedule()
        assert schedule == []

    def test_no_teams_returns_empty(self) -> None:
        engine = RoundRobinScheduler(teams=[])
        schedule = engine.generate_schedule()
        assert schedule == []

    def test_large_tournament(self) -> None:
        teams = _make_teams(16)
        engine = RoundRobinScheduler(teams=teams)
        schedule = engine.generate_schedule()
        assert len(schedule) == 15
        assert engine.validate_schedule(schedule) is True

    def test_get_total_rounds(self) -> None:
        assert RoundRobinScheduler(teams=_make_teams(6)).get_total_rounds() == 5
        assert RoundRobinScheduler(teams=_make_teams(5)).get_total_rounds() == 5
        assert RoundRobinScheduler(teams=_make_teams(1)).get_total_rounds() == 0

    def test_get_matches_per_round(self) -> None:
        assert RoundRobinScheduler(teams=_make_teams(6)).get_matches_per_round() == 3
        assert RoundRobinScheduler(teams=_make_teams(5)).get_matches_per_round() == 2
