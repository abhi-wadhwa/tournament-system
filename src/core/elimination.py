"""Single and Double Elimination bracket generation.

Handles:
- Seeded bracket generation
- Byes for non-power-of-2 team counts
- Match progression (winners advance)
- Double elimination with losers bracket
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from src.core.models import EliminationBracket, EliminationMatch, Team, TournamentFormat


@dataclass
class EliminationBracketGenerator:
    """Generate and manage elimination brackets.

    Single elimination: standard seeded bracket with byes.
    Double elimination: includes a losers bracket; must lose twice to be eliminated.
    """

    teams: list[Team] = field(default_factory=list)

    def generate_single_elimination(self) -> EliminationBracket:
        """Generate a single elimination bracket with proper seeding and byes."""
        active_teams = sorted(
            [t for t in self.teams if t.active],
            key=lambda t: t.seed if t.seed > 0 else 9999,
        )
        n = len(active_teams)
        if n < 2:
            raise ValueError("Need at least 2 teams for elimination bracket")

        num_rounds = math.ceil(math.log2(n))
        bracket_size = 2**num_rounds
        num_byes = bracket_size - n

        # Create seeded positions using standard bracket seeding
        seed_positions = self._generate_seed_positions(bracket_size)

        # Place teams into seeded slots
        team_slots: list[Team | None] = [None] * bracket_size
        for i, pos in enumerate(seed_positions):
            if i < n:
                team_slots[pos] = active_teams[i]

        # Build first round matches
        matches: list[EliminationMatch] = []
        round1_matches: list[EliminationMatch] = []

        for i in range(0, bracket_size, 2):
            team1 = team_slots[i]
            team2 = team_slots[i + 1]

            is_bye = team1 is None or team2 is None
            match = EliminationMatch(
                round_number=1,
                position=i // 2,
                team1_id=team1.id if team1 else None,
                team2_id=team2.id if team2 else None,
                is_bye=is_bye,
            )

            # Auto-advance byes
            if is_bye:
                if team1 is not None:
                    match.winner_id = team1.id
                elif team2 is not None:
                    match.winner_id = team2.id

            round1_matches.append(match)
            matches.append(match)

        # Build subsequent rounds
        prev_round_matches = round1_matches
        for rnd in range(2, num_rounds + 1):
            current_round_matches: list[EliminationMatch] = []
            for i in range(0, len(prev_round_matches), 2):
                match = EliminationMatch(
                    round_number=rnd,
                    position=i // 2,
                )
                current_round_matches.append(match)
                matches.append(match)

                # Link previous matches to this one
                prev_round_matches[i].next_match_id = match.id
                prev_round_matches[i + 1].next_match_id = match.id

                # If previous matches have winners (byes), propagate
                if prev_round_matches[i].winner_id and prev_round_matches[i + 1].winner_id:
                    match.team1_id = prev_round_matches[i].winner_id
                    match.team2_id = prev_round_matches[i + 1].winner_id
                elif prev_round_matches[i].winner_id:
                    match.team1_id = prev_round_matches[i].winner_id
                elif prev_round_matches[i + 1].winner_id:
                    match.team2_id = prev_round_matches[i + 1].winner_id

            prev_round_matches = current_round_matches

        bracket = EliminationBracket(
            format=TournamentFormat.SINGLE_ELIMINATION,
            matches=matches,
            num_teams=n,
            num_rounds=num_rounds,
        )
        return bracket

    def generate_double_elimination(self) -> EliminationBracket:
        """Generate a double elimination bracket.

        Winners bracket + losers bracket. A team must lose twice to be eliminated.
        """
        active_teams = sorted(
            [t for t in self.teams if t.active],
            key=lambda t: t.seed if t.seed > 0 else 9999,
        )
        n = len(active_teams)
        if n < 2:
            raise ValueError("Need at least 2 teams for elimination bracket")

        num_rounds = math.ceil(math.log2(n))
        bracket_size = 2**num_rounds

        # Generate winners bracket (same as single elimination)
        seed_positions = self._generate_seed_positions(bracket_size)
        team_slots: list[Team | None] = [None] * bracket_size
        for i, pos in enumerate(seed_positions):
            if i < n:
                team_slots[pos] = active_teams[i]

        winners_matches: list[EliminationMatch] = []
        round1_matches: list[EliminationMatch] = []

        for i in range(0, bracket_size, 2):
            team1 = team_slots[i]
            team2 = team_slots[i + 1]
            is_bye = team1 is None or team2 is None

            match = EliminationMatch(
                round_number=1,
                position=i // 2,
                team1_id=team1.id if team1 else None,
                team2_id=team2.id if team2 else None,
                is_bye=is_bye,
            )
            if is_bye:
                if team1 is not None:
                    match.winner_id = team1.id
                elif team2 is not None:
                    match.winner_id = team2.id

            round1_matches.append(match)
            winners_matches.append(match)

        prev_round_matches = round1_matches
        for rnd in range(2, num_rounds + 1):
            current_round_matches: list[EliminationMatch] = []
            for i in range(0, len(prev_round_matches), 2):
                match = EliminationMatch(round_number=rnd, position=i // 2)
                current_round_matches.append(match)
                winners_matches.append(match)
                prev_round_matches[i].next_match_id = match.id
                prev_round_matches[i + 1].next_match_id = match.id

                if prev_round_matches[i].winner_id and prev_round_matches[i + 1].winner_id:
                    match.team1_id = prev_round_matches[i].winner_id
                    match.team2_id = prev_round_matches[i + 1].winner_id
                elif prev_round_matches[i].winner_id:
                    match.team1_id = prev_round_matches[i].winner_id
                elif prev_round_matches[i + 1].winner_id:
                    match.team2_id = prev_round_matches[i + 1].winner_id

            prev_round_matches = current_round_matches

        # Generate losers bracket
        losers_matches: list[EliminationMatch] = []
        num_losers_rounds = (num_rounds - 1) * 2  # Losers bracket has roughly 2x rounds
        if num_losers_rounds < 1:
            num_losers_rounds = 1

        for lr in range(1, num_losers_rounds + 1):
            num_matches_this_round = max(1, bracket_size // (2 ** ((lr + 2) // 2)))
            for pos in range(num_matches_this_round):
                loser_match = EliminationMatch(
                    round_number=lr,
                    position=pos,
                )
                losers_matches.append(loser_match)

        # Link losers from winners bracket round 1 to losers bracket round 1
        for i, w_match in enumerate(round1_matches):
            if i < len(losers_matches):
                w_match.loser_match_id = losers_matches[i].id

        # Grand final
        grand_final = EliminationMatch(
            round_number=num_rounds + 1,
            position=0,
        )
        winners_matches.append(grand_final)

        bracket = EliminationBracket(
            format=TournamentFormat.DOUBLE_ELIMINATION,
            matches=winners_matches,
            num_teams=n,
            num_rounds=num_rounds + 1,  # +1 for grand final
            losers_matches=losers_matches,
        )
        return bracket

    def _generate_seed_positions(self, bracket_size: int) -> list[int]:
        """Generate seeded bracket positions so that top seeds meet latest.

        Uses the standard tournament seeding algorithm:
        For a bracket of size N, seed 1 is at position 0, seed 2 at position N-1,
        seed 3 at position N/2, etc.
        """
        if bracket_size == 1:
            return [0]
        if bracket_size == 2:
            return [0, 1]

        # Recursive approach
        positions = [0, 1]
        while len(positions) < bracket_size:
            new_positions: list[int] = []
            size = len(positions) * 2
            for pos in positions:
                new_positions.append(pos)
                new_positions.append(size - 1 - pos)
            positions = new_positions

        return positions

    @staticmethod
    def record_match_result(
        bracket: EliminationBracket, match_id: str, winner_id: str
    ) -> None:
        """Record result for a match and advance the winner."""
        target_match = None
        for match in bracket.matches:
            if match.id == match_id:
                target_match = match
                break
        if target_match is None:
            for match in bracket.losers_matches:
                if match.id == match_id:
                    target_match = match
                    break

        if target_match is None:
            raise ValueError(f"Match {match_id} not found in bracket")

        if winner_id not in (target_match.team1_id, target_match.team2_id):
            raise ValueError(f"Winner {winner_id} is not a participant in match {match_id}")

        target_match.winner_id = winner_id
        loser_id = (
            target_match.team2_id
            if winner_id == target_match.team1_id
            else target_match.team1_id
        )
        target_match.loser_id = loser_id

        # Advance winner to next match
        if target_match.next_match_id:
            for match in bracket.matches + bracket.losers_matches:
                if match.id == target_match.next_match_id:
                    if match.team1_id is None:
                        match.team1_id = winner_id
                    else:
                        match.team2_id = winner_id
                    break

        # Send loser to losers bracket if applicable
        if target_match.loser_match_id and loser_id:
            for match in bracket.losers_matches:
                if match.id == target_match.loser_match_id:
                    if match.team1_id is None:
                        match.team1_id = loser_id
                    else:
                        match.team2_id = loser_id
                    break

    @staticmethod
    def get_round_matches(bracket: EliminationBracket, round_number: int) -> list[EliminationMatch]:
        """Get all matches for a specific round."""
        return [m for m in bracket.matches if m.round_number == round_number]
