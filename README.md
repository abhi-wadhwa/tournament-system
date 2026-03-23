# Tournament Management System

A comprehensive tournament management platform supporting Swiss pairing, Round Robin scheduling, Single/Double Elimination brackets, and British Parliamentary (BP) tabulation with institutional caps and automated judge allocation.

## Features

### Tournament Formats

| Format | Description |
|--------|-------------|
| **Swiss Pairing** | Power-paired rounds with rematch avoidance and side balancing |
| **Round Robin** | Complete schedule where every team meets every other team exactly once |
| **Single Elimination** | Seeded bracket with byes for non-power-of-2 team counts |
| **Double Elimination** | Winners and losers brackets; must lose twice to be eliminated |
| **British Parliamentary** | WUDC-style 4-team rooms with 3/2/1/0 point scoring |

### Core Capabilities

- **Registration management** with institutional affiliations, CSV import/export
- **Automated judge allocation** with institutional conflict avoidance, experience balancing, and soft avoidance constraints
- **Break calculation** with institutional caps (max N teams per institution)
- **Speaker tab** with individual score tracking
- **Interactive Streamlit UI** for tournament administration
- **CLI** for scripted/automated tournament operations

## Architecture

```
src/
├── core/
│   ├── models.py           # Data models (Team, Speaker, Judge, etc.)
│   ├── swiss.py             # Swiss pairing with backtracking
│   ├── round_robin.py       # Circle-method scheduling
│   ├── elimination.py       # Bracket generation and progression
│   ├── bp_tab.py            # BP tabulation engine
│   ├── judge.py             # Constraint-based judge allocation
│   └── registration.py      # Team/speaker/judge management
├── viz/
│   └── app.py               # Streamlit UI
└── cli.py                   # Command-line interface
```

## Installation

```bash
# Clone and install
git clone https://github.com/abhi-wadhwa/tournament-system.git
cd tournament-system
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Launch the UI
streamlit run src/viz/app.py

# Or use the CLI
python -m src.cli swiss --teams 16 --rounds 5
python -m src.cli bp --teams 24 --rounds 5
python -m src.cli round-robin --teams 8
python -m src.cli elimination --teams 16
```

## Quick Start

```python
from src.core.registration import RegistrationManager
from src.core.swiss import SwissPairing
from src.core.models import RoundResult, Side

# Register teams
reg = RegistrationManager()
for i in range(1, 9):
    reg.register_team(
        name=f"Team {i}",
        institution_name=f"School {(i-1) % 4 + 1}",
        speaker_names=[f"Speaker {i}A", f"Speaker {i}B"],
    )

# Generate Swiss pairings
engine = SwissPairing(teams=reg.teams)
pairings = engine.generate_pairings()

for team_a, team_b, side_a, side_b in pairings:
    print(f"{team_a.name} ({side_a.value}) vs {team_b.name} ({side_b.value})")
```

## Algorithms

### Swiss Pairing

1. **Sort** teams by cumulative points (descending), using total speaker score as tiebreaker.
2. **Pair** teams top-down within the sorted list (power pairing).
3. **Avoid rematches** by backtracking up to a configurable depth if a proposed pairing is a rematch.
4. **Balance sides** by assigning proposition/opposition based on each team's side history, preferring the side they have had fewer times.

For odd numbers of teams, the lowest-ranked unpaired team receives a bye (automatic win).

### Round Robin (Circle Method)

1. Fix one team in position 0.
2. Rotate the remaining teams through positions 1..N-1.
3. Each rotation produces one round; pair position `i` with position `N-1-i`.
4. For odd N, a dummy "BYE" team is added; any team paired with the dummy gets a bye.

This produces N-1 rounds for even N (or N rounds for odd N), each team playing every other team exactly once.

### Elimination Brackets

- **Seeding**: Standard bracket seeding ensures seed 1 and seed 2 are on opposite sides.
- **Byes**: For non-power-of-2 counts, top seeds receive first-round byes.
- **Double elimination**: Losers drop to a losers bracket. A team must lose twice to be eliminated. The winners bracket champion meets the losers bracket champion in a grand final.

### British Parliamentary Tabulation

Follows WUDC (World Universities Debating Championship) rules:

- **4 teams per room**: Opening Government (OG), Opening Opposition (OO), Closing Government (CG), Closing Opposition (CO).
- **Ranking**: Each room's four teams are ranked 1st through 4th.
- **Points**: 1st = 3 points, 2nd = 2 points, 3rd = 1 point, 4th = 0 points.
- **Speaker scores**: Individual scores in the range 50-100.
- **Standings**: Teams sorted by total team points, then total speaker score.
- **Break**: Top N teams advance; institutional cap limits how many teams from the same institution can break.
- **Power pairing**: After round 1, teams are grouped into brackets of 4 by points and shuffled within brackets.

### Judge Allocation

Constraint satisfaction approach:

- **Hard constraints**: A judge cannot adjudicate a room containing teams from their own institution or teams in their explicit conflicts list.
- **Soft constraints**: Judges prefer to avoid teams in their avoidance list (penalized score, but not excluded).
- **Experience matching**: Rooms are sorted by priority; the most experienced available judges are assigned to the highest-priority rooms first.
- **Panel composition**: The most experienced judge on each panel is designated chair.

## Testing

```bash
# All tests
pytest tests/ -v

# With coverage
pytest tests/ -v --cov=src --cov-report=term-missing

# Individual test files
pytest tests/test_swiss.py -v
pytest tests/test_bp_tab.py -v
pytest tests/test_judge.py -v
```

## Docker

```bash
docker build -t tournament-system .
docker run -p 8501:8501 tournament-system
# Visit http://localhost:8501
```

## License

MIT
