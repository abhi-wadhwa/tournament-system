"""Tests for British Parliamentary tabulation.

Verifies correct WUDC-style scoring:
- 3/2/1/0 points for ranks 1-4
- Speaker score tracking
- Institutional cap in break calculation
"""

from __future__ import annotations

import pytest

from src.core.bp_tab import BP_RANK_POINTS, BPRoom, BPTabulator
from src.core.models import BPPosition, BPRoundResult, Institution, Speaker, Team


def _make_bp_teams(n: int, teams_per_inst: int = 4) -> list[Team]:
    """Create n teams suitable for BP (with institutions and speakers)."""
    teams = []
    institutions: dict[int, Institution] = {}

    for i in range(1, n + 1):
        inst_num = (i - 1) // teams_per_inst + 1
        if inst_num not in institutions:
            institutions[inst_num] = Institution(name=f"University {inst_num}")
        inst = institutions[inst_num]

        team = Team(
            name=f"Team {i}",
            institution=inst,
            speakers=[
                Speaker(name=f"Speaker {i}A", institution=inst),
                Speaker(name=f"Speaker {i}B", institution=inst),
            ],
        )
        teams.append(team)
    return teams


class TestBPRankPoints:
    """Test that rank-to-points mapping is correct per WUDC rules."""

    def test_first_place_gets_3_points(self) -> None:
        assert BP_RANK_POINTS[1] == 3

    def test_second_place_gets_2_points(self) -> None:
        assert BP_RANK_POINTS[2] == 2

    def test_third_place_gets_1_point(self) -> None:
        assert BP_RANK_POINTS[3] == 1

    def test_fourth_place_gets_0_points(self) -> None:
        assert BP_RANK_POINTS[4] == 0


class TestBPResultRecording:
    """Test recording BP results and updating team scores."""

    def test_record_result_updates_team_points(self) -> None:
        teams = _make_bp_teams(4)
        engine = BPTabulator(teams=teams)

        result = BPRoundResult(
            round_number=1,
            og_team_id=teams[0].id,
            oo_team_id=teams[1].id,
            cg_team_id=teams[2].id,
            co_team_id=teams[3].id,
            og_rank=1,
            oo_rank=2,
            cg_rank=3,
            co_rank=4,
        )
        engine.record_result(result)

        assert teams[0].points == 3  # 1st place
        assert teams[1].points == 2  # 2nd place
        assert teams[2].points == 1  # 3rd place
        assert teams[3].points == 0  # 4th place

    def test_cumulative_points_across_rounds(self) -> None:
        teams = _make_bp_teams(4)
        engine = BPTabulator(teams=teams)

        # Round 1: Team 1 first, Team 2 second
        r1 = BPRoundResult(
            round_number=1,
            og_team_id=teams[0].id,
            oo_team_id=teams[1].id,
            cg_team_id=teams[2].id,
            co_team_id=teams[3].id,
            og_rank=1, oo_rank=2, cg_rank=3, co_rank=4,
        )
        engine.record_result(r1)

        # Round 2: Team 1 fourth, Team 4 first
        r2 = BPRoundResult(
            round_number=2,
            og_team_id=teams[0].id,
            oo_team_id=teams[1].id,
            cg_team_id=teams[2].id,
            co_team_id=teams[3].id,
            og_rank=4, oo_rank=3, cg_rank=2, co_rank=1,
        )
        engine.record_result(r2)

        assert teams[0].points == 3 + 0  # 1st + 4th
        assert teams[1].points == 2 + 1  # 2nd + 3rd
        assert teams[2].points == 1 + 2  # 3rd + 2nd
        assert teams[3].points == 0 + 3  # 4th + 1st

    def test_invalid_ranks_raises(self) -> None:
        teams = _make_bp_teams(4)
        engine = BPTabulator(teams=teams)

        result = BPRoundResult(
            round_number=1,
            og_team_id=teams[0].id,
            oo_team_id=teams[1].id,
            cg_team_id=teams[2].id,
            co_team_id=teams[3].id,
            og_rank=1, oo_rank=1, cg_rank=3, co_rank=4,  # Invalid: two 1st places
        )
        with pytest.raises(ValueError, match="Invalid ranks"):
            engine.record_result(result)

    def test_speaker_scores_recorded(self) -> None:
        teams = _make_bp_teams(4)
        engine = BPTabulator(teams=teams)

        speaker_scores = {}
        for team in teams:
            for speaker in team.speakers:
                speaker_scores[speaker.id] = 75.0

        result = BPRoundResult(
            round_number=1,
            og_team_id=teams[0].id,
            oo_team_id=teams[1].id,
            cg_team_id=teams[2].id,
            co_team_id=teams[3].id,
            og_rank=1, oo_rank=2, cg_rank=3, co_rank=4,
            speaker_scores=speaker_scores,
        )
        engine.record_result(result)

        # Each team should have a speaker score entry (sum of 2 speakers = 150)
        for team in teams:
            assert len(team.speaker_scores) == 1
            assert team.speaker_scores[0] == 150.0

    def test_invalid_speaker_score_raises(self) -> None:
        teams = _make_bp_teams(4)
        engine = BPTabulator(teams=teams)

        result = BPRoundResult(
            round_number=1,
            og_team_id=teams[0].id,
            oo_team_id=teams[1].id,
            cg_team_id=teams[2].id,
            co_team_id=teams[3].id,
            og_rank=1, oo_rank=2, cg_rank=3, co_rank=4,
            speaker_scores={teams[0].speakers[0].id: 120.0},  # Over max 100
        )
        with pytest.raises(ValueError, match="outside valid range"):
            engine.record_result(result)

    def test_position_history_recorded(self) -> None:
        teams = _make_bp_teams(4)
        engine = BPTabulator(teams=teams)

        result = BPRoundResult(
            round_number=1,
            og_team_id=teams[0].id,
            oo_team_id=teams[1].id,
            cg_team_id=teams[2].id,
            co_team_id=teams[3].id,
            og_rank=1, oo_rank=2, cg_rank=3, co_rank=4,
        )
        engine.record_result(result)

        assert teams[0].bp_position_history == [BPPosition.OG]
        assert teams[1].bp_position_history == [BPPosition.OO]
        assert teams[2].bp_position_history == [BPPosition.CG]
        assert teams[3].bp_position_history == [BPPosition.CO]


class TestBPTab:
    """Test standings/tab calculation."""

    def test_tab_sorted_by_points(self) -> None:
        teams = _make_bp_teams(8)
        engine = BPTabulator(teams=teams)

        # Simulate: first 4 teams in room 1
        r1 = BPRoundResult(
            round_number=1,
            og_team_id=teams[0].id, oo_team_id=teams[1].id,
            cg_team_id=teams[2].id, co_team_id=teams[3].id,
            og_rank=1, oo_rank=4, cg_rank=2, co_rank=3,
        )
        engine.record_result(r1)

        # Next 4 teams in room 2
        r2 = BPRoundResult(
            round_number=1,
            og_team_id=teams[4].id, oo_team_id=teams[5].id,
            cg_team_id=teams[6].id, co_team_id=teams[7].id,
            og_rank=2, oo_rank=1, cg_rank=4, co_rank=3,
        )
        engine.record_result(r2)

        tab = engine.get_tab()

        # Teams with rank 1 (3 pts) should be at top
        assert tab[0].points == 3
        assert tab[1].points == 3

    def test_tab_tiebreak_by_speaker_score(self) -> None:
        teams = _make_bp_teams(4)
        engine = BPTabulator(teams=teams)

        # Both OG and OO get rank 1 (impossible in one room, but across rooms)
        # Set up two teams with same points but different speaker scores
        teams[0].points = 3
        teams[0].speaker_scores = [160.0]
        teams[1].points = 3
        teams[1].speaker_scores = [155.0]

        tab = engine.get_tab()
        assert tab[0].id == teams[0].id  # Higher speaker score


class TestBPBreak:
    """Test break calculation with institutional caps."""

    def test_basic_break(self) -> None:
        teams = _make_bp_teams(16, teams_per_inst=4)
        engine = BPTabulator(teams=teams)

        # Give teams descending points
        for i, team in enumerate(teams):
            team.points = 16 - i

        breaking = engine.calculate_break(break_size=8)
        assert len(breaking) == 8
        assert breaking[0].points == 16
        assert breaking[7].points == 9

    def test_institutional_cap(self) -> None:
        # 20 teams across 5 institutions (4 per inst) ensures enough
        # teams to fill an 8-slot break with cap of 2 per institution
        teams = _make_bp_teams(20, teams_per_inst=4)
        engine = BPTabulator(teams=teams)

        # Teams ranked by descending points
        for i, team in enumerate(teams):
            team.points = 20 - i

        breaking = engine.calculate_break(break_size=8, institutional_cap=2)
        assert len(breaking) == 8

        # Count how many from each institution
        inst_counts: dict[str, int] = {}
        for team in breaking:
            if team.institution:
                iid = team.institution.id
                inst_counts[iid] = inst_counts.get(iid, 0) + 1

        # No institution should have more than 2 teams
        for iid, count in inst_counts.items():
            assert count <= 2, f"Institution {iid} has {count} teams in break"

    def test_institutional_cap_zero_means_no_cap(self) -> None:
        teams = _make_bp_teams(8, teams_per_inst=8)  # All same institution
        engine = BPTabulator(teams=teams)

        for i, team in enumerate(teams):
            team.points = 8 - i

        breaking = engine.calculate_break(break_size=4, institutional_cap=0)
        assert len(breaking) == 4  # No cap, all from same institution

    def test_break_respects_ranking_order(self) -> None:
        teams = _make_bp_teams(8, teams_per_inst=8)
        engine = BPTabulator(teams=teams)

        for i, team in enumerate(teams):
            team.points = 8 - i

        breaking = engine.calculate_break(break_size=4)
        for i in range(len(breaking) - 1):
            assert breaking[i].points >= breaking[i + 1].points


class TestBPDraw:
    """Test draw generation."""

    def test_draw_generates_correct_number_of_rooms(self) -> None:
        teams = _make_bp_teams(16)
        engine = BPTabulator(teams=teams)
        draw = engine.generate_draw()
        assert len(draw) == 4  # 16 / 4

    def test_draw_all_positions_filled(self) -> None:
        teams = _make_bp_teams(8)
        engine = BPTabulator(teams=teams)
        draw = engine.generate_draw()

        for room in draw:
            assert room.og_team is not None
            assert room.oo_team is not None
            assert room.cg_team is not None
            assert room.co_team is not None

    def test_fewer_than_4_teams_raises(self) -> None:
        teams = _make_bp_teams(4)
        teams[0].active = False
        teams[1].active = False
        engine = BPTabulator(teams=teams)

        with pytest.raises(ValueError):
            engine.generate_draw()

    def test_no_team_in_two_rooms(self) -> None:
        teams = _make_bp_teams(16)
        engine = BPTabulator(teams=teams)
        draw = engine.generate_draw()

        seen: set[str] = set()
        for room in draw:
            for team in [room.og_team, room.oo_team, room.cg_team, room.co_team]:
                if team:
                    assert team.id not in seen, f"{team.name} in multiple rooms"
                    seen.add(team.id)


class TestBPSpeakerTab:
    """Test individual speaker standings."""

    def test_speaker_tab_returns_sorted(self) -> None:
        teams = _make_bp_teams(4)
        engine = BPTabulator(teams=teams)

        scores = {}
        scores[teams[0].speakers[0].id] = 80.0
        scores[teams[0].speakers[1].id] = 70.0
        scores[teams[1].speakers[0].id] = 90.0
        scores[teams[1].speakers[1].id] = 60.0
        scores[teams[2].speakers[0].id] = 75.0
        scores[teams[2].speakers[1].id] = 65.0
        scores[teams[3].speakers[0].id] = 85.0
        scores[teams[3].speakers[1].id] = 55.0

        result = BPRoundResult(
            round_number=1,
            og_team_id=teams[0].id, oo_team_id=teams[1].id,
            cg_team_id=teams[2].id, co_team_id=teams[3].id,
            og_rank=1, oo_rank=2, cg_rank=3, co_rank=4,
            speaker_scores=scores,
        )
        engine.record_result(result)

        speaker_tab = engine.get_speaker_tab()
        # Should be sorted by total score descending
        for i in range(len(speaker_tab) - 1):
            assert speaker_tab[i][2] >= speaker_tab[i + 1][2]


class TestBPDrawValidation:
    """Test draw validation."""

    def test_valid_draw_no_warnings(self) -> None:
        teams = _make_bp_teams(8, teams_per_inst=2)
        engine = BPTabulator(teams=teams)
        draw = engine.generate_draw()
        warnings = engine.validate_draw(draw)
        # May have institutional clashes due to random draw, but structure should be valid
        structural_warnings = [w for w in warnings if "empty position" in w or "multiple rooms" in w]
        assert len(structural_warnings) == 0
