from app import create_app
from app.extensions import db
from app.models.team import TeamMember

app = create_app("development")

NAMES_TO_MOVE = ["Giddo Tolasa", "Temesgen", "Diribsa Dinka", "Gosa", "Leta Alemu"]

with app.app_context():
    moved = 0
    for name in NAMES_TO_MOVE:
        member = (
            TeamMember.query
            .filter(TeamMember.parent_id.is_(None))
            .filter(TeamMember.member_name.ilike(f"%{name}%"))
            .first()
        )
        if member:
            member.section = "Registration"
            moved += 1
            print(f"Moved: {member.member_name} -> Registration")
        else:
            print(f"Not found, skipped: {name}")
    db.session.commit()
    print(f"Done. Moved {moved} leader(s) to Registration.")