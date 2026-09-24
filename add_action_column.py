from sqlalchemy import inspect, text
from app import create_app
from app.extensions import db

app = create_app("development")
with app.app_context():
    cols = {c["name"] for c in inspect(db.engine).get_columns("team_members")}
    with db.engine.begin() as conn:
        if "action_note" not in cols:
            conn.execute(text("ALTER TABLE team_members ADD COLUMN action_note VARCHAR(255)"))
    print("Done")