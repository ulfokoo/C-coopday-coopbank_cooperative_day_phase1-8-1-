from sqlalchemy import inspect, text
from app import create_app
from app.extensions import db

app = create_app("development")
with app.app_context():
    cols = {c["name"] for c in inspect(db.engine).get_columns("teams")}
    with db.engine.begin() as conn:
        if "zone_labels" not in cols:
            conn.execute(text("ALTER TABLE teams ADD COLUMN zone_labels TEXT"))
    print("Done")