"""Tests for Swiss pairing engine."""

from __future__ import annotations

import pytest

from src.core.models import Institution, RoundResult, Side, Speaker, Team
from src.core.swiss import SwissPairing


def _make_teams(n: int) -> list[Team]:
    """Create n teams with unique IDs."""
    teams = []
    for i in range(1, n + 1):
        inst = Institution(name=f"Inst {i}")
        team = Team(
            name=f"Team {i}",
            institution=inst,
            speakers=[
                Speaker(name=f"Speaker {i}A", institution=inst),
                Speaker(name=f"Speaker {i}B", institution=inst),
            ],
            seed=i,
        )
        teams.append(team)
    return teams


class TestSwissPairingGeneration:
    """Test basic pairing generation."""

    def test_generates_correct_number_of_pairings_even(self) -> None:
        teams = _make_teams(8)
        engine = SwissPairing(teams=teams)
        pairings = engine.generate_pairings()
        assert len(pairings) == 4

    def test_generates_correct_number_of_pairings_odd(self) -> None:
        teams = _make_teams(7)
        engine = SwissPairing(teams=teams)
        pairings = engine.generate_pairings()
        # 7 teams -> 3 pairings + 1 bye
        assert len(pairings) == 3

    def test_all_teams_paired_exactly_once(self) -> None:
        teams = _make_teams(8)
        engine = SwissPairing(teams=teams)
        pairings = engine.generate_pairings()

        paired_ids = set()
        for ta, tb, _, _ in pairings:
            assert ta.id not in paired_ids, f"{ta.name} paired twice"
            assert tb.id not in paired_ids, f"{tb.name} paired twice"
            paired_ids.add(ta.id)
            paired_ids.add(tb.id)

        assert len(paired_ids) == 8

    def test_sides_assigned(self) -> None:
        teams = _make_teams(4)
        engine = SwissPairing(teams=teams)
        pairings = engine.generate_pairings()

        for _, _, side_a, side_b in pairings:
            assert side_a in (Side.PROPOSITION, Side.OPPOSITION)
            assert side_b in (Side.PROPOSITION, Side.OPPOSITION)
            assert side_a != side_b

    def test_empty_teams_returns_empty(self) -> None:
        engine = SwissPairing(teams=[])
        pairings = engine.generate_pairings()
        assert pairings == []

    def test_single_team_returns_empty(self) -> None:
        teams = _make_teams(1)
        engine = SwissPairing(teams=teams)
        pairings = engine.generate_pairings()
        assert pairings == []

    def test_inactive_teams_excluded(self) -> None:
        teams = _make_teams(6)
        teams[0].active = False
        teams[1].active = False
        engine = SwissPairing(teams=teams)
        pairings = engine.generate_pairings()
        assert len(pairings) == 2

        paired_ids = set()
        for ta, tb, _, _ in pairings:
            paired_ids.add(ta.id)
            paired_ids.add(tb.id)
        assert teams[0].id not in paired_ids
        assert teams[1].id not in paired_ids


class TestSwissNoRematches:
    """Test that rematches are avoided."""

    def test_no_rematches_after_first_round(self) -> None:
        teams = _make_teams(8)
        engine = SwissPairing(teams=teams)

        # Round 1
        pairings_r1 = engine.generate_pairings()
        r1_matchups = set()
        for ta, tb, sa, sb in pairings_r1:
            r1_matchups.add(frozenset([ta.id, tb.id]))
            prop = ta if sa == Side.PROPOSITION else tb
            opp = tb if sa == Side.PROPOSITION else ta
            result = RoundResult(
                round_number=1,
                proposition_team_id=prop.id,
                opposition_team_id=opp.id,
                proposition_score=250.0,
                opposition_score=240.0,
                winner_id=prop.id,
            )
            engine.record_result(result)

        # Round 2
        pairings_r2 = engine.generate_pairings()
        for ta, tb, _, _ in pairings_r2:
            matchup = frozenset([ta.id, tb.id])
            assert matchup not in r1_matchups, (
                f"Rematch detected: {ta.name} vs {tb.name}"
            )

    def test_no_rematches_across_three_rounds(self) -> None:
        teams = _make_teams(8)
        engine = SwissPairing(teams=teams)
        all_matchups: set[frozenset[str]] = set()

        for rnd in range(1, 4):
            pairings = engine.generate_pairings()
            for ta, tb, sa, sb in pairings:
                matchup = frozenset([ta.id, tb.id])
                assert matchup not in all_matchups, (
                    f"Rematch in round {rnd}: {ta.name} vs {tb.name}"
                )
                all_matchups.add(matchup)

                prop = ta if sa == Side.PROPOSITION else tb
                opp = tb if sa == Side.PROPOSITION else ta
                result = RoundResult(
                    round_number=rnd,
                    proposition_team_id=prop.id,
                    opposition_team_id=opp.id,
                    proposition_score=250.0,
                    opposition_score=240.0,
                    winner_id=prop.id,
                )
                engine.record_result(result)


class TestSwissPowerPairing:
    """Test that teams are power-paired (sorted by points)."""

    def test_higher_ranked_teams_paired_together(self) -> None:
        teams = _make_teams(4)
        # Manually set points: Team1=3, Team2=2, Team3=1, Team4=0
        teams[0].points = 3
        teams[1].points = 2
        teams[2].points = 1
        teams[3].points = 0

        engine = SwissPairing(teams=teams)
        pairings = engine.generate_pairings()

        # Top two should play each other, bottom two should play each other
        pair1_ids = {pairings[0][0].id, pairings[0][1].id}
        pair2_ids = {pairings[1][0].id, pairings[1][1].id}

        top_two = {teams[0].id, teams[1].id}
        bottom_two = {teams[2].id, teams[3].id}

        assert pair1_ids == top_two or pair1_ids == bottom_two
        assert pair2_ids == top_two or pair2_ids == bottom_two
        assert pair1_ids != pair2_ids


class TestSwissResultRecording:
    """Test result recording and score tracking."""

    def test_record_result_updates_teams(self) -> None:
        teams = _make_teams(2)
        engine = SwissPairing(teams=teams)

        result = RoundResult(
            round_number=1,
            proposition_team_id=teams[0].id,
            opposition_team_id=teams[1].id,
            proposition_score=260.0,
            opposition_score=240.0,
            winner_id=teams[0].id,
        )
        engine.record_result(result)

        assert teams[0].wins == 1
        assert teams[0].points == 1
        assert teams[1].losses == 1
        assert teams[1].points == 0

        assert teams[0].opponent_history == [teams[1].id]
        assert teams[1].opponent_history == [teams[0].id]

        assert teams[0].side_history == [Side.PROPOSITION]
        assert teams[1].side_history == [Side.OPPOSITION]

    def test_record_draw(self) -> None:
        teams = _make_teams(2)
        engine = SwissPairing(teams=teams)

        result = RoundResult(
            round_number=1,
            proposition_team_id=teams[0].id,
            opposition_team_id=teams[1].id,
            proposition_score=250.0,
            opposition_score=250.0,
            winner_id="",  # Draw
        )
        engine.record_result(result)

        assert teams[0].draws == 1
        assert teams[0].points == 0.5
        assert teams[1].draws == 1
        assert teams[1].points == 0.5

    def test_invalid_team_raises(self) -> None:
        teams = _make_teams(2)
        engine = SwissPairing(teams=teams)

        result = RoundResult(
            round_number=1,
            proposition_team_id="nonexistent",
            opposition_team_id=teams[1].id,
            winner_id="nonexistent",
        )
        with pytest.raises(ValueError):
            engine.record_result(result)


class TestSwissStandings:
    """Test standings calculation."""

    def test_standings_sorted_by_points(self) -> None:
        teams = _make_teams(4)
        teams[0].points = 1
        teams[1].points = 3
        teams[2].points = 0
        teams[3].points = 2

        engine = SwissPairing(teams=teams)
        standings = engine.get_standings()

        assert standings[0].name == "Team 2"
        assert standings[1].name == "Team 4"
        assert standings[2].name == "Team 1"
        assert standings[3].name == "Team 3"

    def test_standings_tiebreak_by_speaker_score(self) -> None:
        teams = _make_teams(2)
        teams[0].points = 2
        teams[0].speaker_scores = [200, 210]
        teams[1].points = 2
        teams[1].speaker_scores = [220, 230]

        engine = SwissPairing(teams=teams)
        standings = engine.get_standings()

        # Team 2 has higher speaker scores (450 vs 410)
        assert standings[0].name == "Team 2"
        assert standings[1].name == "Team 1"
