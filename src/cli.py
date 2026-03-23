"""Command-line interface for the tournament management system.

Provides commands for running tournaments without the Streamlit UI.
"""

from __future__ import annotations

import argparse
import json
import sys

from src.core.bp_tab import BPTabulator
from src.core.elimination import EliminationBracketGenerator
from src.core.models import TournamentFormat
from src.core.registration import RegistrationManager
from src.core.round_robin import RoundRobinScheduler
from src.core.swiss import SwissPairing


def create_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="tournament",
        description="Tournament Management System CLI",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # --- register ---
    reg_parser = subparsers.add_parser("register", help="Register teams from CSV")
    reg_parser.add_argument("csv_file", help="Path to teams CSV file")
    reg_parser.add_argument(
        "--type",
        choices=["teams", "judges"],
        default="teams",
        help="Import type",
    )

    # --- swiss ---
    swiss_parser = subparsers.add_parser("swiss", help="Run Swiss pairing demo")
    swiss_parser.add_argument(
        "--teams", type=int, default=8, help="Number of demo teams"
    )
    swiss_parser.add_argument(
        "--rounds", type=int, default=3, help="Number of rounds"
    )

    # --- round-robin ---
    rr_parser = subparsers.add_parser("round-robin", help="Generate round robin schedule")
    rr_parser.add_argument(
        "--teams", type=int, default=6, help="Number of demo teams"
    )

    # --- elimination ---
    elim_parser = subparsers.add_parser("elimination", help="Generate elimination bracket")
    elim_parser.add_argument(
        "--teams", type=int, default=8, help="Number of demo teams"
    )
    elim_parser.add_argument(
        "--double", action="store_true", help="Use double elimination"
    )

    # --- bp ---
    bp_parser = subparsers.add_parser("bp", help="Run BP tabulation demo")
    bp_parser.add_argument(
        "--teams", type=int, default=16, help="Number of demo teams (multiple of 4)"
    )
    bp_parser.add_argument(
        "--rounds", type=int, default=3, help="Number of rounds"
    )

    # --- ui ---
    subparsers.add_parser("ui", help="Launch Streamlit UI")

    return parser


def cmd_swiss(args: argparse.Namespace) -> None:
    """Run a Swiss pairing demo."""
    reg = RegistrationManager()
    for i in range(1, args.teams + 1):
        reg.register_team(
            name=f"Team {i}",
            institution_name=f"Inst {(i - 1) % 4 + 1}",
            speaker_names=[f"Speaker {i}A", f"Speaker {i}B"],
            seed=i,
        )

    engine = SwissPairing(teams=reg.teams)

    print(f"Swiss Tournament: {args.teams} teams, {args.rounds} rounds\n")

    for rnd in range(1, args.rounds + 1):
        pairings = engine.generate_pairings()
        print(f"--- Round {rnd} ---")
        for i, (ta, tb, sa, sb) in enumerate(pairings):
            print(f"  Room {i+1}: {ta.name} ({sa.value}) vs {tb.name} ({sb.value})")

        # Simulate results (higher seed wins)
        import random

        for ta, tb, sa, sb in pairings:
            from src.core.models import RoundResult, Side

            prop = ta if sa == Side.PROPOSITION else tb
            opp = tb if sa == Side.PROPOSITION else ta
            winner = random.choice([prop, opp])
            result = RoundResult(
                round_number=rnd,
                proposition_team_id=prop.id,
                opposition_team_id=opp.id,
                proposition_score=random.uniform(200, 300),
                opposition_score=random.uniform(200, 300),
                winner_id=winner.id,
            )
            engine.record_result(result)

        print()

    print("--- Final Standings ---")
    for rank, team in enumerate(engine.get_standings(), 1):
        print(
            f"  {rank}. {team.name}: {team.points} pts, "
            f"{team.total_speaker_score:.1f} spk"
        )


def cmd_round_robin(args: argparse.Namespace) -> None:
    """Generate and display a round robin schedule."""
    reg = RegistrationManager()
    for i in range(1, args.teams + 1):
        reg.register_team(name=f"Team {i}")

    engine = RoundRobinScheduler(teams=reg.teams)
    schedule = engine.generate_schedule()

    print(f"Round Robin Schedule: {args.teams} teams\n")

    for rnd in schedule:
        print(f"--- Round {rnd[0].round_number} ---")
        for match in rnd:
            if match.is_bye:
                bye_team = (
                    match.team_a if match.team_b.id == "__BYE__" else match.team_b
                )
                print(f"  BYE: {bye_team.name}")
            else:
                print(f"  {match.team_a.name} vs {match.team_b.name}")
        print()

    valid = engine.validate_schedule(schedule)
    print(f"Schedule valid: {valid}")


def cmd_elimination(args: argparse.Namespace) -> None:
    """Generate and display an elimination bracket."""
    reg = RegistrationManager()
    for i in range(1, args.teams + 1):
        reg.register_team(name=f"Seed {i}", seed=i)

    engine = EliminationBracketGenerator(teams=reg.teams)

    if args.double:
        bracket = engine.generate_double_elimination()
        print(f"Double Elimination: {args.teams} teams\n")
    else:
        bracket = engine.generate_single_elimination()
        print(f"Single Elimination: {args.teams} teams\n")

    team_map = {t.id: t.name for t in reg.teams}

    for rnd in range(1, bracket.num_rounds + 1):
        matches = [m for m in bracket.matches if m.round_number == rnd]
        print(f"--- Round {rnd} ---")
        for match in matches:
            t1 = team_map.get(match.team1_id, "BYE") if match.team1_id else "BYE"
            t2 = team_map.get(match.team2_id, "BYE") if match.team2_id else "BYE"
            suffix = " (BYE)" if match.is_bye else ""
            print(f"  {t1} vs {t2}{suffix}")
        print()


def cmd_bp(args: argparse.Namespace) -> None:
    """Run a BP tabulation demo."""
    import random

    reg = RegistrationManager()
    n = (args.teams // 4) * 4
    for i in range(1, n + 1):
        reg.register_team(
            name=f"Team {i}",
            institution_name=f"Uni {(i - 1) % 5 + 1}",
            speaker_names=[f"Speaker {i}A", f"Speaker {i}B"],
        )

    engine = BPTabulator(teams=reg.teams)

    print(f"BP Tournament: {n} teams, {args.rounds} rounds\n")

    for rnd in range(1, args.rounds + 1):
        draw = engine.generate_draw()
        print(f"--- Round {rnd} Draw ---")
        for room in draw:
            print(
                f"  Room {room.room_number}: "
                f"OG={room.og_team.name if room.og_team else '?'}, "
                f"OO={room.oo_team.name if room.oo_team else '?'}, "
                f"CG={room.cg_team.name if room.cg_team else '?'}, "
                f"CO={room.co_team.name if room.co_team else '?'}"
            )

        # Simulate results
        from src.core.models import BPRoundResult

        for room in draw:
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

        print()

    print("--- Final Tab ---")
    for rank, team in enumerate(engine.get_tab(), 1):
        print(
            f"  {rank}. {team.name}: {team.points} pts, "
            f"{team.total_speaker_score:.1f} spk"
        )

    print("\n--- Break (top 8, cap 2 per institution) ---")
    breaking = engine.calculate_break(break_size=8, institutional_cap=2)
    for rank, team in enumerate(breaking, 1):
        print(
            f"  {rank}. {team.name} "
            f"({team.institution.name if team.institution else 'N/A'})"
        )


def cmd_ui(_args: argparse.Namespace) -> None:
    """Launch the Streamlit UI."""
    import subprocess

    subprocess.run(
        [sys.executable, "-m", "streamlit", "run", "src/viz/app.py"],
        check=True,
    )


def main() -> None:
    """CLI entry point."""
    parser = create_parser()
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return

    commands = {
        "swiss": cmd_swiss,
        "round-robin": cmd_round_robin,
        "elimination": cmd_elimination,
        "bp": cmd_bp,
        "ui": cmd_ui,
    }

    handler = commands.get(args.command)
    if handler:
        handler(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
