"""Data models for the tournament management system."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class TournamentFormat(str, Enum):
    """Supported tournament formats."""

    SWISS = "swiss"
    ROUND_ROBIN = "round_robin"
    SINGLE_ELIMINATION = "single_elimination"
    DOUBLE_ELIMINATION = "double_elimination"
    BRITISH_PARLIAMENTARY = "british_parliamentary"


class BPPosition(str, Enum):
    """British Parliamentary debate positions."""

    OG = "Opening Government"
    OO = "Opening Opposition"
    CG = "Closing Government"
    CO = "Closing Opposition"


class Side(str, Enum):
    """Sides in a two-team debate/match."""

    PROPOSITION = "proposition"
    OPPOSITION = "opposition"


@dataclass
class Institution:
    """An institution (school, university, club)."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    code: str = ""

    def __hash__(self) -> int:
        return hash(self.id)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Institution):
            return NotImplemented
        return self.id == other.id


@dataclass
class Speaker:
    """An individual speaker/competitor."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    institution: Optional[Institution] = None
    team_id: Optional[str] = None

    def __hash__(self) -> int:
        return hash(self.id)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Speaker):
            return NotImplemented
        return self.id == other.id


@dataclass
class Team:
    """A team in the tournament."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    institution: Optional[Institution] = None
    speakers: list[Speaker] = field(default_factory=list)
    seed: int = 0
    points: float = 0.0
    speaker_scores: list[float] = field(default_factory=list)
    wins: int = 0
    losses: int = 0
    draws: int = 0
    side_history: list[Side] = field(default_factory=list)
    opponent_history: list[str] = field(default_factory=list)
    bp_position_history: list[BPPosition] = field(default_factory=list)
    active: bool = True

    @property
    def total_speaker_score(self) -> float:
        """Sum of all speaker scores across rounds."""
        return sum(self.speaker_scores)

    @property
    def average_speaker_score(self) -> float:
        """Average speaker score."""
        if not self.speaker_scores:
            return 0.0
        return self.total_speaker_score / len(self.speaker_scores)

    def __hash__(self) -> int:
        return hash(self.id)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Team):
            return NotImplemented
        return self.id == other.id


@dataclass
class Judge:
    """A judge/adjudicator."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    institution: Optional[Institution] = None
    experience_level: int = 5  # 1-10 scale
    conflicts: list[str] = field(default_factory=list)  # team IDs
    avoidances: list[str] = field(default_factory=list)  # team IDs (soft constraint)
    active: bool = True

    def __hash__(self) -> int:
        return hash(self.id)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Judge):
            return NotImplemented
        return self.id == other.id


@dataclass
class Room:
    """A physical/virtual room for a debate/match."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    priority: int = 0  # Higher priority rooms get more experienced judges

    def __hash__(self) -> int:
        return hash(self.id)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Room):
            return NotImplemented
        return self.id == other.id


@dataclass
class RoundResult:
    """Result of a standard two-team match."""

    round_number: int = 0
    room: Optional[Room] = None
    proposition_team_id: str = ""
    opposition_team_id: str = ""
    proposition_score: float = 0.0
    opposition_score: float = 0.0
    winner_id: str = ""
    judge_ids: list[str] = field(default_factory=list)
    speaker_scores: dict[str, float] = field(default_factory=dict)  # speaker_id -> score


@dataclass
class BPRoundResult:
    """Result of a British Parliamentary debate round."""

    round_number: int = 0
    room: Optional[Room] = None
    og_team_id: str = ""
    oo_team_id: str = ""
    cg_team_id: str = ""
    co_team_id: str = ""
    # Ranks: 1st=3pts, 2nd=2pts, 3rd=1pt, 4th=0pts
    og_rank: int = 0  # 1-4
    oo_rank: int = 0
    cg_rank: int = 0
    co_rank: int = 0
    speaker_scores: dict[str, float] = field(default_factory=dict)  # speaker_id -> score
    judge_ids: list[str] = field(default_factory=list)


@dataclass
class EliminationMatch:
    """A match in an elimination bracket."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    round_number: int = 0
    position: int = 0  # Position within the round (0-indexed)
    team1_id: Optional[str] = None
    team2_id: Optional[str] = None
    winner_id: Optional[str] = None
    loser_id: Optional[str] = None
    is_bye: bool = False
    next_match_id: Optional[str] = None  # Winner advances to this match
    loser_match_id: Optional[str] = None  # For double elimination, loser goes here


@dataclass
class EliminationBracket:
    """Full bracket for single or double elimination."""

    format: TournamentFormat = TournamentFormat.SINGLE_ELIMINATION
    matches: list[EliminationMatch] = field(default_factory=list)
    num_teams: int = 0
    num_rounds: int = 0
    losers_matches: list[EliminationMatch] = field(default_factory=list)  # Double elim only


@dataclass
class Tournament:
    """Top-level tournament container."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    format: TournamentFormat = TournamentFormat.SWISS
    teams: list[Team] = field(default_factory=list)
    judges: list[Judge] = field(default_factory=list)
    institutions: list[Institution] = field(default_factory=list)
    rooms: list[Room] = field(default_factory=list)
    current_round: int = 0
    total_rounds: int = 0
    round_results: list[RoundResult] = field(default_factory=list)
    bp_round_results: list[BPRoundResult] = field(default_factory=list)
    elimination_bracket: Optional[EliminationBracket] = None
    break_size: int = 0  # Number of teams that break
    institutional_cap: int = 0  # Max teams per institution in the break (0 = no cap)
