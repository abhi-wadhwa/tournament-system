"""Tests for Single and Double Elimination bracket generation."""

from __future__ import annotations

import math

import pytest

from src.core.elimination import EliminationBracketGenerator
from src.core.models import EliminationBracket, Team, TournamentFormat


def _make_teams(n: int) -> list[Team]:
    """Create n seeded teams."""
    return [
        Team(name=f"Seed {i}", seed=i)
        for i in range(1, n + 1)
    ]


class TestSingleElimination:
    """Test single elimination bracket generation."""

    def test_power_of_2_teams(self) -> None:
        teams = _make_teams(8)
        gen = EliminationBracketGenerator(teams=teams)
        bracket = gen.generate_single_elimination()

        assert bracket.num_teams == 8
        assert bracket.num_rounds == 3
        assert bracket.format == TournamentFormat.SINGLE_ELIMINATION

    def test_non_power_of_2_has_byes(self) -> None:
        teams = _make_teams(6)
        gen = EliminationBracketGenerator(teams=teams)
        bracket = gen.generate_single_elimination()

        assert bracket.num_teams == 6
        assert bracket.num_rounds == 3  # ceil(log2(6)) = 3

        # Should have 2 byes (8 - 6 = 2)
        bye_matches = [m for m in bracket.matches if m.is_bye]
        assert len(bye_matches) == 2

    def test_four_teams_two_rounds(self) -> None:
        teams = _make_teams(4)
        gen = EliminationBracketGenerator(teams=teams)
        bracket = gen.generate_single_elimination()

        assert bracket.num_rounds == 2
        round1 = [m for m in bracket.matches if m.round_number == 1]
        assert len(round1) == 2

    def test_two_teams_one_round(self) -> None:
        teams = _make_teams(2)
        gen = EliminationBracketGenerator(teams=teams)
        bracket = gen.generate_single_elimination()

        assert bracket.num_rounds == 1
        assert len(bracket.matches) == 1

    def test_bye_teams_auto_advance(self) -> None:
        teams = _make_teams(5)
        gen = EliminationBracketGenerator(teams=teams)
        bracket = gen.generate_single_elimination()

        bye_matches = [m for m in bracket.matches if m.is_bye]
        for match in bye_matches:
            assert match.winner_id is not None

    def test_seeding_1_vs_last(self) -> None:
        """Seed 1 should be on opposite side of bracket from Seed 2."""
        teams = _make_teams(8)
        gen = EliminationBracketGenerator(teams=teams)
        bracket = gen.generate_single_elimination()

        round1 = [m for m in bracket.matches if m.round_number == 1]

        # Find which round 1 match has seed 1
        seed1_team = teams[0]
        seed2_team = teams[1]

        seed1_match = None
        seed2_match = None
        for match in round1:
            if match.team1_id == seed1_team.id or match.team2_id == seed1_team.id:
                seed1_match = match
            if match.team1_id == seed2_team.id or match.team2_id == seed2_team.id:
                seed2_match = match

        assert seed1_match is not None
        assert seed2_match is not None
        # Seeds 1 and 2 should be in different matches (different halves of bracket)
        assert seed1_match.id != seed2_match.id

    def test_single_team_raises(self) -> None:
        teams = _make_teams(1)
        gen = EliminationBracketGenerator(teams=teams)
        with pytest.raises(ValueError):
            gen.generate_single_elimination()


class TestDoubleElimination:
    """Test double elimination bracket generation."""

    def test_double_elimination_has_losers_bracket(self) -> None:
        teams = _make_teams(8)
        gen = EliminationBracketGenerator(teams=teams)
        bracket = gen.generate_double_elimination()

        assert bracket.format == TournamentFormat.DOUBLE_ELIMINATION
        assert len(bracket.losers_matches) > 0

    def test_double_elimination_has_grand_final(self) -> None:
        teams = _make_teams(8)
        gen = EliminationBracketGenerator(teams=teams)
        bracket = gen.generate_double_elimination()

        # Grand final is the last round
        max_round = max(m.round_number for m in bracket.matches)
        grand_final = [m for m in bracket.matches if m.round_number == max_round]
        assert len(grand_final) == 1

    def test_losers_receive_match_links(self) -> None:
        teams = _make_teams(8)
        gen = EliminationBracketGenerator(teams=teams)
        bracket = gen.generate_double_elimination()

        # At least some first-round matches should link losers to losers bracket
        round1 = [m for m in bracket.matches if m.round_number == 1]
        loser_links = [m for m in round1 if m.loser_match_id is not None]
        assert len(loser_links) > 0


class TestMatchProgression:
    """Test recording results and advancing winners."""

    def test_winner_advances(self) -> None:
        teams = _make_teams(4)
        gen = EliminationBracketGenerator(teams=teams)
        bracket = gen.generate_single_elimination()

        round1 = [m for m in bracket.matches if m.round_number == 1]

        # Record result for first match
        match = round1[0]
        winner_id = match.team1_id
        gen.record_match_result(bracket, match.id, winner_id)

        assert match.winner_id == winner_id

        # Winner should appear in round 2
        if match.next_match_id:
            next_match = None
            for m in bracket.matches:
                if m.id == match.next_match_id:
                    next_match = m
                    break
            assert next_match is not None
            assert winner_id in (next_match.team1_id, next_match.team2_id)

    def test_invalid_winner_raises(self) -> None:
        teams = _make_teams(4)
        gen = EliminationBracketGenerator(teams=teams)
        bracket = gen.generate_single_elimination()

        round1 = [m for m in bracket.matches if m.round_number == 1]
        match = round1[0]

        with pytest.raises(ValueError):
            gen.record_match_result(bracket, match.id, "nonexistent_id")

    def test_invalid_match_raises(self) -> None:
        teams = _make_teams(4)
        gen = EliminationBracketGenerator(teams=teams)
        bracket = gen.generate_single_elimination()

        with pytest.raises(ValueError):
            gen.record_match_result(bracket, "bad_match_id", teams[0].id)

    def test_get_round_matches(self) -> None:
        teams = _make_teams(8)
        gen = EliminationBracketGenerator(teams=teams)
        bracket = gen.generate_single_elimination()

        r1 = gen.get_round_matches(bracket, 1)
        assert len(r1) == 4

        r2 = gen.get_round_matches(bracket, 2)
        assert len(r2) == 2

        r3 = gen.get_round_matches(bracket, 3)
        assert len(r3) == 1


class TestSeedPositions:
    """Test seeding algorithm."""

    def test_seed_positions_power_of_2(self) -> None:
        gen = EliminationBracketGenerator(teams=[])
        positions = gen._generate_seed_positions(8)
        assert len(positions) == 8
        # Seed 1 at position 0, seed 2 at position 7
        assert positions[0] == 0
        assert positions[1] == 7

    def test_seed_positions_all_unique(self) -> None:
        gen = EliminationBracketGenerator(teams=[])
        for size in [2, 4, 8, 16, 32]:
            positions = gen._generate_seed_positions(size)
            assert len(set(positions)) == size, f"Duplicate positions for size {size}"
