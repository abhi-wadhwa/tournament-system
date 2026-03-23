"""End-to-end demo of the tournament management system.

Demonstrates:
1. Registration of teams, speakers, and judges
2. Swiss pairing with result recording
3. Round Robin schedule generation
4. Single Elimination bracket generation
5. BP tabulation with institutional cap
6. Judge allocation with conflict avoidance
"""

from __future__ import annotations

import random

from src.core.bp_tab import BPTabulator
from src.core.elimination import EliminationBracketGenerator
from src.core.judge import JudgeAllocator, RoomDebate
from src.core.models import (
    BPRoundResult,
    Room,
    RoundResult,
    Side,
)
from src.core.registration import RegistrationManager
from src.core.round_robin import RoundRobinScheduler
from src.core.swiss import SwissPairing


def demo_registration() -> RegistrationManager:
    """Register teams and judges for the demo."""
    reg = RegistrationManager()

    # Register institutions
    oxford = reg.add_institution("Oxford", "OXF")
    cambridge = reg.add_institution("Cambridge", "CAM")
    harvard = reg.add_institution("Harvard", "HAR")
    yale = reg.add_institution("Yale", "YAL")

    # Register 16 teams (4 per institution)
    for i in range(1, 5):
        reg.register_team(
            name=f"Oxford {i}",
            institution_name="Oxford",
            speaker_names=[f"OXF Speaker {i}A", f"OXF Speaker {i}B"],
            seed=i,
        )
        reg.register_team(
            name=f"Cambridge {i}",
            institution_name="Cambridge",
            speaker_names=[f"CAM Speaker {i}A", f"CAM Speaker {i}B"],
            seed=4 + i,
        )
        reg.register_team(
            name=f"Harvard {i}",
            institution_name="Harvard",
            speaker_names=[f"HAR Speaker {i}A", f"HAR Speaker {i}B"],
            seed=8 + i,
        )
        reg.register_team(
            name=f"Yale {i}",
            institution_name="Yale",
            speaker_names=[f"YAL Speaker {i}A", f"YAL Speaker {i}B"],
            seed=12 + i,
        )

    # Register judges
    for i in range(1, 9):
        inst_name = ["Oxford", "Cambridge", "Harvard", "Yale"][(i - 1) % 4]
        reg.register_judge(
            name=f"Judge {i}",
            institution_name=inst_name,
            experience_level=random.randint(3, 10),
        )

    stats = reg.get_statistics()
    print("=== Registration Complete ===")
    print(f"  Institutions: {stats['institutions']}")
    print(f"  Teams: {stats['teams']}")
    print(f"  Speakers: {stats['speakers']}")
    print(f"  Judges: {stats['judges']}")
    print()

    return reg


def demo_swiss(reg: RegistrationManager) -> None:
    """Run a 5-round Swiss tournament."""
    print("=== Swiss Tournament ===")
    engine = SwissPairing(teams=reg.teams)

    for rnd in range(1, 6):
        pairings = engine.generate_pairings()
        print(f"\n--- Round {rnd} ---")
        for i, (ta, tb, sa, sb) in enumerate(pairings):
            print(f"  Room {i+1}: {ta.name} ({sa.value}) vs {tb.name} ({sb.value})")

            # Simulate: random winner, random scores
            prop = ta if sa == Side.PROPOSITION else tb
            opp = tb if sa == Side.PROPOSITION else ta
            prop_score = random.uniform(230, 280)
            opp_score = random.uniform(230, 280)
            winner = prop if prop_score > opp_score else opp

            result = RoundResult(
                round_number=rnd,
                proposition_team_id=prop.id,
                opposition_team_id=opp.id,
                proposition_score=prop_score,
                opposition_score=opp_score,
                winner_id=winner.id,
            )
            engine.record_result(result)

    print("\n--- Final Swiss Standings ---")
    for rank, team in enumerate(engine.get_standings(), 1):
        print(f"  {rank:2d}. {team.name:15s}  W:{team.wins}  Pts:{team.points:.1f}  Spk:{team.total_speaker_score:.1f}")


def demo_round_robin(reg: RegistrationManager) -> None:
    """Generate a Round Robin schedule for a subset of teams."""
    print("\n=== Round Robin (4 teams) ===")
    rr_teams = reg.teams[:4]
    engine = RoundRobinScheduler(teams=rr_teams)
    schedule = engine.generate_schedule()

    for rnd in schedule:
        print(f"\n--- Round {rnd[0].round_number} ---")
        for match in rnd:
            if match.is_bye:
                continue
            print(f"  {match.team_a.name} vs {match.team_b.name}")

    print(f"\nSchedule valid: {engine.validate_schedule(schedule)}")


def demo_elimination(reg: RegistrationManager) -> None:
    """Generate a Single Elimination bracket."""
    print("\n=== Single Elimination (8 teams) ===")
    elim_teams = reg.teams[:8]
    gen = EliminationBracketGenerator(teams=elim_teams)
    bracket = gen.generate_single_elimination()

    team_map = {t.id: t.name for t in elim_teams}

    for rnd in range(1, bracket.num_rounds + 1):
        matches = gen.get_round_matches(bracket, rnd)
        labels = {1: "Quarterfinals", 2: "Semifinals", 3: "Final"}
        print(f"\n--- {labels.get(rnd, f'Round {rnd}')} ---")
        for match in matches:
            t1 = team_map.get(match.team1_id, "BYE") if match.team1_id else "BYE"
            t2 = team_map.get(match.team2_id, "BYE") if match.team2_id else "BYE"
            suffix = " [BYE]" if match.is_bye else ""
            print(f"  {t1} vs {t2}{suffix}")


def demo_bp(reg: RegistrationManager) -> None:
    """Run a 3-round BP tournament."""
    print("\n=== British Parliamentary (16 teams, 3 rounds) ===")
    engine = BPTabulator(teams=reg.teams)

    for rnd in range(1, 4):
        draw = engine.generate_draw()
        print(f"\n--- Round {rnd} Draw ---")
        for room in draw:
            og = room.og_team.name if room.og_team else "?"
            oo = room.oo_team.name if room.oo_team else "?"
            cg = room.cg_team.name if room.cg_team else "?"
            co = room.co_team.name if room.co_team else "?"
            print(f"  Room {room.room_number}: OG={og}, OO={oo}, CG={cg}, CO={co}")

            # Simulate results
            ranks = [1, 2, 3, 4]
            random.shuffle(ranks)

            speaker_scores = {}
            for team in [room.og_team, room.oo_team, room.cg_team, room.co_team]:
                if team:
                    for speaker in team.speakers:
                        speaker_scores[speaker.id] = random.uniform(65, 85)

            result = BPRoundResult(
                round_number=rnd,
                og_team_id=room.og_team.id if room.og_team else "",
                oo_team_id=room.oo_team.id if room.oo_team else "",
                cg_team_id=room.cg_team.id if room.cg_team else "",
                co_team_id=room.co_team.id if room.co_team else "",
                og_rank=ranks[0],
                oo_rank=ranks[1],
                cg_rank=ranks[2],
                co_rank=ranks[3],
                speaker_scores=speaker_scores,
            )
            engine.record_result(result)

    print("\n--- BP Tab ---")
    for rank, team in enumerate(engine.get_tab(), 1):
        inst = team.institution.name if team.institution else "N/A"
        print(f"  {rank:2d}. {team.name:15s}  Pts:{team.points}  Spk:{team.total_speaker_score:.1f}  ({inst})")

    print("\n--- Break (top 8, cap 2 per institution) ---")
    breaking = engine.calculate_break(break_size=8, institutional_cap=2)
    for rank, team in enumerate(breaking, 1):
        inst = team.institution.name if team.institution else "N/A"
        print(f"  {rank}. {team.name} ({inst})")

    print("\n--- Top 5 Speakers ---")
    for rank, (sid, name, score) in enumerate(engine.get_speaker_tab()[:5], 1):
        print(f"  {rank}. {name}: {score:.1f}")


def demo_judge_allocation(reg: RegistrationManager) -> None:
    """Demonstrate judge allocation with conflict avoidance."""
    print("\n=== Judge Allocation ===")
    allocator = JudgeAllocator(judges=reg.judges, panel_size=1)

    # Create 4 debates
    debates = []
    for i in range(4):
        ta = reg.teams[i * 2]
        tb = reg.teams[i * 2 + 1]
        room = Room(name=f"Room {i+1}", priority=4 - i)
        inst_ids = []
        if ta.institution:
            inst_ids.append(ta.institution.id)
        if tb.institution:
            inst_ids.append(tb.institution.id)

        debates.append(
            RoomDebate(
                room=room,
                team_ids=[ta.id, tb.id],
                institution_ids=inst_ids,
            )
        )

    assignments = allocator.allocate(debates)
    violations = allocator.validate_allocation(assignments, debates)

    for assignment in assignments:
        chair_inst = assignment.chair.institution.name if assignment.chair.institution else "N/A"
        print(
            f"  {assignment.room.name}: Chair = {assignment.chair.name} "
            f"(Exp: {assignment.chair.experience_level}, Inst: {chair_inst})"
        )

    if violations:
        print(f"\n  VIOLATIONS: {violations}")
    else:
        print("\n  No conflicts detected.")


def main() -> None:
    """Run all demos."""
    random.seed(42)  # For reproducibility

    reg = demo_registration()
    demo_swiss(reg)

    # Reset team stats for other demos
    for team in reg.teams:
        team.points = 0
        team.wins = 0
        team.losses = 0
        team.draws = 0
        team.speaker_scores.clear()
        team.opponent_history.clear()
        team.side_history.clear()
        team.bp_position_history.clear()

    demo_round_robin(reg)
    demo_elimination(reg)
    demo_bp(reg)
    demo_judge_allocation(reg)


if __name__ == "__main__":
    main()
