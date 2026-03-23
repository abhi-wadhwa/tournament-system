"""Streamlit UI for interactive tournament management.

Run with: streamlit run src/viz/app.py

Features:
- Tournament setup wizard (format, teams, judges)
- Live standings and tabulation display
- Round results entry forms
- Bracket visualization for elimination formats
- Judge assignment view
"""

from __future__ import annotations

import streamlit as st

from src.core.models import (
    BPPosition,
    BPRoundResult,
    Institution,
    Room,
    RoundResult,
    Side,
    Speaker,
    Team,
    TournamentFormat,
)
from src.core.bp_tab import BPTabulator
from src.core.elimination import EliminationBracketGenerator
from src.core.judge import JudgeAllocator, RoomDebate
from src.core.registration import RegistrationManager
from src.core.round_robin import RoundRobinScheduler
from src.core.swiss import SwissPairing


def init_session_state() -> None:
    """Initialize Streamlit session state variables."""
    defaults = {
        "registration": RegistrationManager(),
        "tournament_format": TournamentFormat.SWISS,
        "current_round": 0,
        "total_rounds": 5,
        "swiss_engine": None,
        "rr_engine": None,
        "bp_engine": None,
        "elim_engine": None,
        "judge_allocator": None,
        "pairings": [],
        "rr_schedule": [],
        "bp_draw": [],
        "bracket": None,
        "round_results": [],
        "setup_complete": False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def main() -> None:
    """Main Streamlit application."""
    st.set_page_config(
        page_title="Tournament Manager",
        page_icon="🏆",
        layout="wide",
    )

    init_session_state()

    st.title("Tournament Management System")

    # Sidebar navigation
    page = st.sidebar.radio(
        "Navigation",
        [
            "Setup",
            "Registration",
            "Pairings / Draw",
            "Enter Results",
            "Standings",
            "Bracket",
            "Judge Allocation",
        ],
    )

    if page == "Setup":
        render_setup_page()
    elif page == "Registration":
        render_registration_page()
    elif page == "Pairings / Draw":
        render_pairings_page()
    elif page == "Enter Results":
        render_results_page()
    elif page == "Standings":
        render_standings_page()
    elif page == "Bracket":
        render_bracket_page()
    elif page == "Judge Allocation":
        render_judge_page()


def render_setup_page() -> None:
    """Tournament setup wizard."""
    st.header("Tournament Setup")

    fmt = st.selectbox(
        "Tournament Format",
        options=[f.value for f in TournamentFormat],
        format_func=lambda x: x.replace("_", " ").title(),
    )
    st.session_state.tournament_format = TournamentFormat(fmt)

    if fmt in ("swiss", "british_parliamentary"):
        st.session_state.total_rounds = st.number_input(
            "Number of Preliminary Rounds",
            min_value=1,
            max_value=20,
            value=st.session_state.total_rounds,
        )

    if fmt == "british_parliamentary":
        break_size = st.number_input("Break Size", min_value=4, value=8, step=4)
        inst_cap = st.number_input(
            "Institutional Cap (0 = no cap)", min_value=0, value=0
        )
        st.session_state["break_size"] = break_size
        st.session_state["inst_cap"] = inst_cap

    if st.button("Initialize Tournament"):
        reg = st.session_state.registration
        teams = reg.teams
        judges = reg.judges

        if fmt == "swiss":
            engine = SwissPairing(teams=teams)
            st.session_state.swiss_engine = engine
        elif fmt == "round_robin":
            engine = RoundRobinScheduler(teams=teams)
            schedule = engine.generate_schedule()
            st.session_state.rr_engine = engine
            st.session_state.rr_schedule = schedule
        elif fmt in ("single_elimination", "double_elimination"):
            engine = EliminationBracketGenerator(teams=teams)
            if fmt == "single_elimination":
                bracket = engine.generate_single_elimination()
            else:
                bracket = engine.generate_double_elimination()
            st.session_state.elim_engine = engine
            st.session_state.bracket = bracket
        elif fmt == "british_parliamentary":
            engine = BPTabulator(teams=teams)
            st.session_state.bp_engine = engine

        if judges:
            allocator = JudgeAllocator(judges=judges)
            st.session_state.judge_allocator = allocator

        st.session_state.setup_complete = True
        st.success("Tournament initialized successfully!")


def render_registration_page() -> None:
    """Team and judge registration."""
    st.header("Registration")
    reg: RegistrationManager = st.session_state.registration

    tab1, tab2, tab3, tab4 = st.tabs(
        ["Add Team", "Add Judge", "Bulk Import", "Current Registrations"]
    )

    with tab1:
        st.subheader("Register Team")
        team_name = st.text_input("Team Name", key="team_name")
        inst_name = st.text_input("Institution", key="team_inst")
        sp1 = st.text_input("Speaker 1", key="sp1")
        sp2 = st.text_input("Speaker 2", key="sp2")
        seed = st.number_input("Seed (0 = unseeded)", min_value=0, value=0, key="team_seed")

        if st.button("Register Team"):
            speakers = [s for s in [sp1, sp2] if s.strip()]
            try:
                team = reg.register_team(
                    name=team_name,
                    institution_name=inst_name if inst_name else None,
                    speaker_names=speakers if speakers else None,
                    seed=seed,
                )
                st.success(f"Registered team: {team.name}")
            except ValueError as e:
                st.error(str(e))

    with tab2:
        st.subheader("Register Judge")
        judge_name = st.text_input("Judge Name", key="judge_name")
        judge_inst = st.text_input("Institution", key="judge_inst")
        exp_level = st.slider("Experience Level", 1, 10, 5, key="judge_exp")

        if st.button("Register Judge"):
            try:
                judge = reg.register_judge(
                    name=judge_name,
                    institution_name=judge_inst if judge_inst else None,
                    experience_level=exp_level,
                )
                st.success(f"Registered judge: {judge.name}")
            except ValueError as e:
                st.error(str(e))

    with tab3:
        st.subheader("Bulk Import (CSV)")
        csv_type = st.selectbox("Import Type", ["Teams", "Judges"])
        csv_data = st.text_area(
            "Paste CSV",
            placeholder=(
                "team_name,institution,speaker1,speaker2"
                if csv_type == "Teams"
                else "name,institution,experience_level"
            ),
        )
        if st.button("Import"):
            if csv_type == "Teams":
                imported = reg.import_teams_csv(csv_data)
                st.success(f"Imported {len(imported)} teams")
            else:
                imported = reg.import_judges_csv(csv_data)
                st.success(f"Imported {len(imported)} judges")

    with tab4:
        st.subheader("Registered Teams")
        if reg.teams:
            for team in reg.teams:
                with st.expander(
                    f"{team.name} ({team.institution.name if team.institution else 'No institution'})"
                ):
                    st.write(f"Seed: {team.seed}")
                    st.write(f"Active: {team.active}")
                    st.write(f"Speakers: {', '.join(s.name for s in team.speakers)}")
        else:
            st.info("No teams registered yet.")

        st.subheader("Registered Judges")
        if reg.judges:
            for judge in reg.judges:
                st.write(
                    f"- {judge.name} (Exp: {judge.experience_level}, "
                    f"Inst: {judge.institution.name if judge.institution else 'N/A'})"
                )
        else:
            st.info("No judges registered yet.")

        stats = reg.get_statistics()
        st.metric("Total Teams", stats["teams"])
        st.metric("Total Judges", stats["judges"])


def render_pairings_page() -> None:
    """Display and generate pairings/draw."""
    st.header("Pairings / Draw")
    fmt = st.session_state.tournament_format

    if not st.session_state.setup_complete:
        st.warning("Please complete tournament setup first.")
        return

    if fmt == TournamentFormat.SWISS:
        engine: SwissPairing = st.session_state.swiss_engine
        if engine is None:
            st.error("Swiss engine not initialized.")
            return

        if st.button("Generate Next Round Pairings"):
            pairings = engine.generate_pairings()
            st.session_state.pairings = pairings
            st.session_state.current_round += 1

        if st.session_state.pairings:
            st.subheader(f"Round {st.session_state.current_round}")
            for i, (ta, tb, sa, sb) in enumerate(st.session_state.pairings):
                st.write(
                    f"**Room {i+1}:** {ta.name} ({sa.value}) vs {tb.name} ({sb.value})"
                )

    elif fmt == TournamentFormat.ROUND_ROBIN:
        schedule = st.session_state.rr_schedule
        if schedule:
            for rnd_idx, rnd in enumerate(schedule):
                with st.expander(f"Round {rnd_idx + 1}"):
                    for match in rnd:
                        if match.is_bye:
                            bye_team = (
                                match.team_a
                                if match.team_b.id == "__BYE__"
                                else match.team_b
                            )
                            st.write(f"BYE: {bye_team.name}")
                        else:
                            st.write(
                                f"{match.team_a.name} ({match.side_a.value}) vs "
                                f"{match.team_b.name} ({match.side_b.value})"
                            )

    elif fmt == TournamentFormat.BRITISH_PARLIAMENTARY:
        engine_bp: BPTabulator = st.session_state.bp_engine
        if engine_bp is None:
            st.error("BP engine not initialized.")
            return

        if st.button("Generate Next Round Draw"):
            try:
                draw = engine_bp.generate_draw()
                st.session_state.bp_draw = draw
            except ValueError as e:
                st.error(str(e))

        if st.session_state.bp_draw:
            st.subheader(f"Round {engine_bp.current_round}")
            for room in st.session_state.bp_draw:
                with st.expander(f"Room {room.room_number}"):
                    st.write(f"OG: {room.og_team.name if room.og_team else 'TBD'}")
                    st.write(f"OO: {room.oo_team.name if room.oo_team else 'TBD'}")
                    st.write(f"CG: {room.cg_team.name if room.cg_team else 'TBD'}")
                    st.write(f"CO: {room.co_team.name if room.co_team else 'TBD'}")


def render_results_page() -> None:
    """Enter round results."""
    st.header("Enter Results")
    fmt = st.session_state.tournament_format

    if fmt in (TournamentFormat.SWISS, TournamentFormat.ROUND_ROBIN):
        pairings = st.session_state.pairings
        if not pairings:
            st.info("No active pairings. Generate pairings first.")
            return

        st.subheader(f"Round {st.session_state.current_round} Results")
        for i, (ta, tb, sa, sb) in enumerate(pairings):
            with st.expander(f"Room {i+1}: {ta.name} vs {tb.name}"):
                col1, col2 = st.columns(2)
                with col1:
                    score_a = st.number_input(
                        f"{ta.name} score",
                        min_value=0.0,
                        value=0.0,
                        key=f"score_a_{i}",
                    )
                with col2:
                    score_b = st.number_input(
                        f"{tb.name} score",
                        min_value=0.0,
                        value=0.0,
                        key=f"score_b_{i}",
                    )

                winner = st.selectbox(
                    "Winner",
                    [ta.name, tb.name, "Draw"],
                    key=f"winner_{i}",
                )

                if st.button("Submit", key=f"submit_{i}"):
                    if winner == ta.name:
                        winner_id = ta.id
                    elif winner == tb.name:
                        winner_id = tb.id
                    else:
                        winner_id = ""

                    prop_team = ta if sa == Side.PROPOSITION else tb
                    opp_team = tb if sa == Side.PROPOSITION else ta
                    prop_score = score_a if sa == Side.PROPOSITION else score_b
                    opp_score = score_b if sa == Side.PROPOSITION else score_a

                    result = RoundResult(
                        round_number=st.session_state.current_round,
                        proposition_team_id=prop_team.id,
                        opposition_team_id=opp_team.id,
                        proposition_score=prop_score,
                        opposition_score=opp_score,
                        winner_id=winner_id,
                    )

                    if fmt == TournamentFormat.SWISS:
                        st.session_state.swiss_engine.record_result(result)
                    st.session_state.round_results.append(result)
                    st.success("Result recorded!")

    elif fmt == TournamentFormat.BRITISH_PARLIAMENTARY:
        draw = st.session_state.bp_draw
        if not draw:
            st.info("No active draw. Generate a draw first.")
            return

        engine_bp: BPTabulator = st.session_state.bp_engine
        st.subheader(f"Round {engine_bp.current_round} Results")

        for room in draw:
            with st.expander(f"Room {room.room_number}"):
                teams_in_room = {
                    "OG": room.og_team,
                    "OO": room.oo_team,
                    "CG": room.cg_team,
                    "CO": room.co_team,
                }

                ranks = {}
                for pos_label, team in teams_in_room.items():
                    if team:
                        ranks[pos_label] = st.selectbox(
                            f"{pos_label} ({team.name}) rank",
                            [1, 2, 3, 4],
                            key=f"rank_{room.room_number}_{pos_label}",
                        )

                if st.button("Submit Room", key=f"submit_room_{room.room_number}"):
                    try:
                        bp_result = BPRoundResult(
                            round_number=engine_bp.current_round,
                            og_team_id=room.og_team.id if room.og_team else "",
                            oo_team_id=room.oo_team.id if room.oo_team else "",
                            cg_team_id=room.cg_team.id if room.cg_team else "",
                            co_team_id=room.co_team.id if room.co_team else "",
                            og_rank=ranks.get("OG", 1),
                            oo_rank=ranks.get("OO", 2),
                            cg_rank=ranks.get("CG", 3),
                            co_rank=ranks.get("CO", 4),
                        )
                        engine_bp.record_result(bp_result)
                        st.success("Room result recorded!")
                    except ValueError as e:
                        st.error(str(e))


def render_standings_page() -> None:
    """Display current standings/tab."""
    st.header("Standings")
    fmt = st.session_state.tournament_format

    if fmt == TournamentFormat.SWISS:
        engine: SwissPairing = st.session_state.swiss_engine
        if engine is None:
            st.info("Tournament not started.")
            return
        standings = engine.get_standings()
        _display_standings_table(standings)

    elif fmt == TournamentFormat.BRITISH_PARLIAMENTARY:
        engine_bp: BPTabulator = st.session_state.bp_engine
        if engine_bp is None:
            st.info("Tournament not started.")
            return

        tab = engine_bp.get_tab()
        _display_standings_table(tab, bp_mode=True)

        st.subheader("Speaker Tab")
        speaker_tab = engine_bp.get_speaker_tab()
        if speaker_tab:
            for rank, (sid, name, score) in enumerate(speaker_tab, 1):
                st.write(f"{rank}. {name}: {score:.1f}")

    elif fmt == TournamentFormat.ROUND_ROBIN:
        reg: RegistrationManager = st.session_state.registration
        standings = sorted(
            reg.teams,
            key=lambda t: (t.points, t.total_speaker_score),
            reverse=True,
        )
        _display_standings_table(standings)


def _display_standings_table(teams: list[Team], bp_mode: bool = False) -> None:
    """Render a standings table."""
    if not teams:
        st.info("No standings data yet.")
        return

    header = ["Rank", "Team", "Institution", "Points", "Speaker Score"]
    if bp_mode:
        header.append("Avg Spk")

    rows = []
    for rank, team in enumerate(teams, 1):
        row = [
            rank,
            team.name,
            team.institution.name if team.institution else "-",
            team.points,
            f"{team.total_speaker_score:.1f}",
        ]
        if bp_mode:
            row.append(f"{team.average_speaker_score:.1f}")
        rows.append(row)

    import pandas as pd

    df = pd.DataFrame(rows, columns=header)
    st.dataframe(df, use_container_width=True, hide_index=True)


def render_bracket_page() -> None:
    """Display elimination bracket."""
    st.header("Bracket")

    bracket = st.session_state.bracket
    if bracket is None:
        st.info("No elimination bracket. Set up a Single or Double Elimination tournament.")
        return

    reg: RegistrationManager = st.session_state.registration
    team_map = {t.id: t.name for t in reg.teams}

    for rnd in range(1, bracket.num_rounds + 1):
        matches = [m for m in bracket.matches if m.round_number == rnd]
        if not matches:
            continue

        round_label = _get_round_label(rnd, bracket.num_rounds)
        st.subheader(round_label)

        for match in matches:
            t1_name = team_map.get(match.team1_id, "TBD") if match.team1_id else "BYE"
            t2_name = team_map.get(match.team2_id, "TBD") if match.team2_id else "BYE"
            winner_name = team_map.get(match.winner_id, "") if match.winner_id else ""

            if match.is_bye:
                st.write(f"  {t1_name if t1_name != 'BYE' else t2_name} (BYE)")
            elif winner_name:
                st.write(f"  {t1_name} vs {t2_name}  -->  Winner: **{winner_name}**")
            else:
                st.write(f"  {t1_name} vs {t2_name}")

    if bracket.losers_matches:
        st.subheader("Losers Bracket")
        for match in bracket.losers_matches:
            t1_name = team_map.get(match.team1_id, "TBD") if match.team1_id else "TBD"
            t2_name = team_map.get(match.team2_id, "TBD") if match.team2_id else "TBD"
            st.write(f"  L-R{match.round_number} M{match.position+1}: {t1_name} vs {t2_name}")


def _get_round_label(round_num: int, total_rounds: int) -> str:
    """Get a human-readable label for a bracket round."""
    remaining = total_rounds - round_num
    if remaining == 0:
        return "Final"
    elif remaining == 1:
        return "Semifinal"
    elif remaining == 2:
        return "Quarterfinal"
    else:
        return f"Round {round_num}"


def render_judge_page() -> None:
    """Judge allocation view."""
    st.header("Judge Allocation")

    allocator: JudgeAllocator | None = st.session_state.judge_allocator
    if allocator is None:
        st.info("No judges registered or tournament not initialized.")
        return

    st.write(f"Available judges: {len([j for j in allocator.judges if j.active])}")

    if st.button("Auto-allocate Judges for Current Round"):
        # Build debates from current pairings
        fmt = st.session_state.tournament_format
        debates: list[RoomDebate] = []

        if fmt == TournamentFormat.SWISS:
            pairings = st.session_state.pairings
            for i, (ta, tb, sa, sb) in enumerate(pairings):
                room = Room(name=f"Room {i+1}", priority=len(pairings) - i)
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

        elif fmt == TournamentFormat.BRITISH_PARLIAMENTARY:
            draw = st.session_state.bp_draw
            for room_draw in draw:
                room = Room(name=f"Room {room_draw.room_number}", priority=len(draw) - room_draw.room_number + 1)
                team_ids = []
                inst_ids = []
                for team in [room_draw.og_team, room_draw.oo_team, room_draw.cg_team, room_draw.co_team]:
                    if team:
                        team_ids.append(team.id)
                        if team.institution:
                            inst_ids.append(team.institution.id)
                debates.append(
                    RoomDebate(room=room, team_ids=team_ids, institution_ids=inst_ids)
                )

        if debates:
            assignments = allocator.allocate(debates)
            violations = allocator.validate_allocation(assignments, debates)

            if violations:
                for v in violations:
                    st.warning(v)

            for assignment in assignments:
                with st.expander(f"{assignment.room.name}"):
                    st.write(f"Chair: {assignment.chair.name} (Exp: {assignment.chair.experience_level})")
                    if assignment.wings:
                        for wing in assignment.wings:
                            st.write(f"Wing: {wing.name} (Exp: {wing.experience_level})")
                    st.write(f"Teams: {', '.join(assignment.team_ids)}")
        else:
            st.warning("No pairings/draw available. Generate pairings first.")


if __name__ == "__main__":
    main()
