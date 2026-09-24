"""Creates the 9 teams from the organisation chart under the latest
Cooperative Day event. Safe to re-run (existing teams are skipped).

Run with:  python seed_teams.py
"""
import os
from app import create_app
from app.extensions import db
from app.models.event import CooperativeDay
from app.models.team import Team

app = create_app(os.environ.get("FLASK_ENV", "development"))

TEAMS = [
    "Expo Team",
    "Cooperative Team",
    "Award Team",
    "Branding & Communication Team",
    "Welcome Protocol Team",
    "Facilitator Team",
    "Venue Team",
    "Food Service Team",
    "Security Team",
]

with app.app_context():
    event = CooperativeDay.query.order_by(CooperativeDay.year.desc()).first()
    if not event:
        raise SystemExit("Create a Cooperative Day event first (Cooperative Days > New).")
    created = 0
    for name in TEAMS:
        if not Team.query.filter_by(name=name, cooperative_day_id=event.id).first():
            db.session.add(Team(name=name, cooperative_day_id=event.id, status="Active"))
            created += 1
    db.session.commit()
    print(f"Done. {created} team(s) created under '{event.name}'.")