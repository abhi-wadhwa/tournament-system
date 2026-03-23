"""Registration manager for teams, speakers, judges, and institutions.

Handles:
- Creating and managing institutions
- Registering teams with speakers
- Registering judges with conflict declarations
- Bulk import/export
- Validation (unique names, proper affiliations, etc.)
"""

from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass, field

from src.core.models import Institution, Judge, Speaker, Team


@dataclass
class RegistrationManager:
    """Manage registrations for a tournament.

    Provides CRUD operations for institutions, teams, speakers, and judges.
    Enforces uniqueness and referential integrity.
    """

    institutions: list[Institution] = field(default_factory=list)
    teams: list[Team] = field(default_factory=list)
    speakers: list[Speaker] = field(default_factory=list)
    judges: list[Judge] = field(default_factory=list)

    # --- Institution management ---

    def add_institution(self, name: str, code: str = "") -> Institution:
        """Register a new institution."""
        if any(inst.name == name for inst in self.institutions):
            raise ValueError(f"Institution '{name}' already exists")

        if not code:
            # Auto-generate code from first 3 letters
            code = name[:3].upper()

        inst = Institution(name=name, code=code)
        self.institutions.append(inst)
        return inst

    def get_institution(self, institution_id: str) -> Institution | None:
        """Look up an institution by ID."""
        for inst in self.institutions:
            if inst.id == institution_id:
                return inst
        return None

    def get_institution_by_name(self, name: str) -> Institution | None:
        """Look up an institution by name."""
        for inst in self.institutions:
            if inst.name == name:
                return inst
        return None

    def remove_institution(self, institution_id: str) -> bool:
        """Remove an institution. Fails if teams or judges are affiliated."""
        affiliated_teams = [
            t for t in self.teams
            if t.institution and t.institution.id == institution_id
        ]
        affiliated_judges = [
            j for j in self.judges
            if j.institution and j.institution.id == institution_id
        ]

        if affiliated_teams or affiliated_judges:
            raise ValueError(
                f"Cannot remove institution: {len(affiliated_teams)} teams and "
                f"{len(affiliated_judges)} judges are affiliated"
            )

        before = len(self.institutions)
        self.institutions = [i for i in self.institutions if i.id != institution_id]
        return len(self.institutions) < before

    # --- Team management ---

    def register_team(
        self,
        name: str,
        institution_name: str | None = None,
        speaker_names: list[str] | None = None,
        seed: int = 0,
    ) -> Team:
        """Register a new team with optional speakers.

        Args:
            name: Team name (must be unique).
            institution_name: Name of affiliated institution (created if not found).
            speaker_names: Names of speakers on the team.
            seed: Seeding number (0 = unseeded).

        Returns:
            The registered Team object.
        """
        if any(t.name == name for t in self.teams):
            raise ValueError(f"Team '{name}' already exists")

        institution = None
        if institution_name:
            institution = self.get_institution_by_name(institution_name)
            if institution is None:
                institution = self.add_institution(institution_name)

        team = Team(name=name, institution=institution, seed=seed)

        if speaker_names:
            for speaker_name in speaker_names:
                speaker = Speaker(
                    name=speaker_name,
                    institution=institution,
                    team_id=team.id,
                )
                team.speakers.append(speaker)
                self.speakers.append(speaker)

        self.teams.append(team)
        return team

    def get_team(self, team_id: str) -> Team | None:
        """Look up a team by ID."""
        for team in self.teams:
            if team.id == team_id:
                return team
        return None

    def get_team_by_name(self, name: str) -> Team | None:
        """Look up a team by name."""
        for team in self.teams:
            if team.name == name:
                return team
        return None

    def deactivate_team(self, team_id: str) -> bool:
        """Mark a team as inactive (withdrawn)."""
        team = self.get_team(team_id)
        if team:
            team.active = False
            return True
        return False

    def remove_team(self, team_id: str) -> bool:
        """Remove a team entirely."""
        team = self.get_team(team_id)
        if team is None:
            return False

        # Remove associated speakers
        speaker_ids = {s.id for s in team.speakers}
        self.speakers = [s for s in self.speakers if s.id not in speaker_ids]

        self.teams = [t for t in self.teams if t.id != team_id]
        return True

    # --- Speaker management ---

    def add_speaker_to_team(
        self, team_id: str, speaker_name: str
    ) -> Speaker:
        """Add a speaker to an existing team."""
        team = self.get_team(team_id)
        if team is None:
            raise ValueError(f"Team {team_id} not found")

        speaker = Speaker(
            name=speaker_name,
            institution=team.institution,
            team_id=team.id,
        )
        team.speakers.append(speaker)
        self.speakers.append(speaker)
        return speaker

    def remove_speaker(self, speaker_id: str) -> bool:
        """Remove a speaker from their team and the registry."""
        speaker = None
        for s in self.speakers:
            if s.id == speaker_id:
                speaker = s
                break
        if speaker is None:
            return False

        # Remove from team
        if speaker.team_id:
            team = self.get_team(speaker.team_id)
            if team:
                team.speakers = [s for s in team.speakers if s.id != speaker_id]

        self.speakers = [s for s in self.speakers if s.id != speaker_id]
        return True

    # --- Judge management ---

    def register_judge(
        self,
        name: str,
        institution_name: str | None = None,
        experience_level: int = 5,
        conflict_team_names: list[str] | None = None,
        avoidance_team_names: list[str] | None = None,
    ) -> Judge:
        """Register a new judge.

        Args:
            name: Judge name.
            institution_name: Affiliated institution.
            experience_level: Experience score (1-10).
            conflict_team_names: Teams the judge has hard conflicts with.
            avoidance_team_names: Teams the judge prefers to avoid.
        """
        institution = None
        if institution_name:
            institution = self.get_institution_by_name(institution_name)
            if institution is None:
                institution = self.add_institution(institution_name)

        conflicts: list[str] = []
        if conflict_team_names:
            for tname in conflict_team_names:
                team = self.get_team_by_name(tname)
                if team:
                    conflicts.append(team.id)

        avoidances: list[str] = []
        if avoidance_team_names:
            for tname in avoidance_team_names:
                team = self.get_team_by_name(tname)
                if team:
                    avoidances.append(team.id)

        judge = Judge(
            name=name,
            institution=institution,
            experience_level=max(1, min(10, experience_level)),
            conflicts=conflicts,
            avoidances=avoidances,
        )
        self.judges.append(judge)
        return judge

    def remove_judge(self, judge_id: str) -> bool:
        """Remove a judge."""
        before = len(self.judges)
        self.judges = [j for j in self.judges if j.id != judge_id]
        return len(self.judges) < before

    # --- Bulk operations ---

    def import_teams_csv(self, csv_text: str) -> list[Team]:
        """Import teams from CSV text.

        Expected columns: team_name, institution, speaker1, speaker2, [speaker3, ...]
        """
        reader = csv.DictReader(io.StringIO(csv_text))
        imported: list[Team] = []

        for row in reader:
            team_name = row.get("team_name", "").strip()
            institution = row.get("institution", "").strip() or None

            speakers = []
            for key in sorted(row.keys()):
                if key.startswith("speaker") and row[key].strip():
                    speakers.append(row[key].strip())

            if team_name:
                try:
                    team = self.register_team(
                        name=team_name,
                        institution_name=institution,
                        speaker_names=speakers if speakers else None,
                    )
                    imported.append(team)
                except ValueError:
                    pass  # Skip duplicates

        return imported

    def import_judges_csv(self, csv_text: str) -> list[Judge]:
        """Import judges from CSV text.

        Expected columns: name, institution, experience_level
        """
        reader = csv.DictReader(io.StringIO(csv_text))
        imported: list[Judge] = []

        for row in reader:
            name = row.get("name", "").strip()
            institution = row.get("institution", "").strip() or None
            exp = int(row.get("experience_level", "5"))

            if name:
                try:
                    judge = self.register_judge(
                        name=name,
                        institution_name=institution,
                        experience_level=exp,
                    )
                    imported.append(judge)
                except ValueError:
                    pass

        return imported

    def export_teams_json(self) -> str:
        """Export all teams as JSON."""
        data = []
        for team in self.teams:
            data.append(
                {
                    "id": team.id,
                    "name": team.name,
                    "institution": team.institution.name if team.institution else None,
                    "speakers": [
                        {"id": s.id, "name": s.name} for s in team.speakers
                    ],
                    "seed": team.seed,
                    "active": team.active,
                }
            )
        return json.dumps(data, indent=2)

    def export_judges_json(self) -> str:
        """Export all judges as JSON."""
        data = []
        for judge in self.judges:
            data.append(
                {
                    "id": judge.id,
                    "name": judge.name,
                    "institution": judge.institution.name if judge.institution else None,
                    "experience_level": judge.experience_level,
                    "active": judge.active,
                }
            )
        return json.dumps(data, indent=2)

    def get_statistics(self) -> dict[str, int]:
        """Return registration statistics."""
        return {
            "institutions": len(self.institutions),
            "teams": len(self.teams),
            "active_teams": len([t for t in self.teams if t.active]),
            "speakers": len(self.speakers),
            "judges": len(self.judges),
            "active_judges": len([j for j in self.judges if j.active]),
        }

    def validate(self) -> list[str]:
        """Validate registrations for common issues.

        Returns a list of warning messages.
        """
        warnings: list[str] = []

        # Check for teams without speakers
        for team in self.teams:
            if not team.speakers:
                warnings.append(f"Team '{team.name}' has no speakers")

        # Check for teams without institution
        for team in self.teams:
            if team.institution is None:
                warnings.append(f"Team '{team.name}' has no institution")

        # Check for judges without institution
        for judge in self.judges:
            if judge.institution is None:
                warnings.append(f"Judge '{judge.name}' has no institution")

        # Check for duplicate speaker names
        speaker_names = [s.name for s in self.speakers]
        seen: set[str] = set()
        for name in speaker_names:
            if name in seen:
                warnings.append(f"Duplicate speaker name: '{name}'")
            seen.add(name)

        return warnings
