import os
from flask import Flask, render_template

from config import config
from app.extensions import db, login_manager, migrate, csrf

def _sync_missing_columns():
    """Add columns defined in the models that are missing in the database."""
    from sqlalchemy import inspect, text

    # 1) add any missing columns
    try:
        insp = inspect(db.engine)
        existing_tables = set(insp.get_table_names())
        dialect = db.engine.dialect

        with db.engine.begin() as conn:
            for table in db.metadata.sorted_tables:
                if table.name not in existing_tables:
                    continue  # missing tables are handled by create_all / seed
                have = {c["name"] for c in insp.get_columns(table.name)}
                for col in table.columns:
                    if col.name in have:
                        continue
                    coltype = col.type.compile(dialect=dialect)
                    conn.execute(
                        text(f'ALTER TABLE "{table.name}" ADD COLUMN "{col.name}" {coltype}')
                    )
                    print(f"[db-sync] added {table.name}.{col.name}")
    except Exception as e:  # never stop the app from booting
        print(f"[db-sync] add columns skipped: {e}")

    # 2) widen window_label to 255 (Postgres only, safe to repeat)
    try:
        if db.engine.dialect.name == "postgresql":
            with db.engine.begin() as conn:
                conn.execute(
                    text("ALTER TABLE team_members ALTER COLUMN window_label TYPE VARCHAR(255)")
                )
    except Exception as e:
        print(f"[db-sync] widen window_label skipped: {e}")

def create_app(config_name=None):
    """Application factory."""
    config_name = config_name or os.environ.get("FLASK_ENV", "development")

    app = Flask(__name__)
    app.config.from_object(config[config_name])

    # --- extensions ---
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)

    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please log in to access this page."
    login_manager.login_message_category = "warning"

    # --- models (imported once, here, so every mapped class is registered
    # on the declarative base before Flask-Migrate/db.create_all() run) ---
    from app import models  # noqa: F401
    from app.models.user import User

     # --- auto-add any columns that exist in the models but not in the DB ---
    # (create_all() creates missing tables but never adds columns to existing ones)
    with app.app_context():
        _sync_missing_columns()

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    # --- blueprints ---
    from app.main.routes import main_bp
    from app.auth.routes import auth_bp
    from app.admin.routes import admin_bp
    from app.events.routes import events_bp
    from app.teams.routes import teams_bp
    from app.tasks.routes import tasks_bp
    from app.instructions.routes import instructions_bp
    from app.meetings.routes import meetings_bp
    from app.documents.routes import documents_bp
    from app.correspondence.routes import correspondence_bp
    from app.procurement.routes import procurement_bp
    from app.activities.routes import activities_bp
    from app.communication.routes import communication_bp
    from app.notifications.routes import notifications_bp
    from app.search.routes import search_bp
    from app.reports.routes import reports_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(events_bp, url_prefix="/events")
    app.register_blueprint(teams_bp, url_prefix="/teams")
    app.register_blueprint(tasks_bp, url_prefix="/tasks")
    app.register_blueprint(instructions_bp, url_prefix="/instructions")
    app.register_blueprint(meetings_bp, url_prefix="/meetings")
    app.register_blueprint(documents_bp, url_prefix="/documents")
    app.register_blueprint(correspondence_bp, url_prefix="/correspondence")
    app.register_blueprint(procurement_bp, url_prefix="/procurement")
    app.register_blueprint(activities_bp, url_prefix="/activities")
    app.register_blueprint(communication_bp, url_prefix="/communication")
    app.register_blueprint(notifications_bp, url_prefix="/notifications")
    app.register_blueprint(search_bp, url_prefix="/search")
    app.register_blueprint(reports_bp, url_prefix="/reports")

    # --- upload folder ---
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    # --- template helpers (permission checks etc. available in Jinja) ---
    from app.utils.decorators import user_has_permission
    from app.utils.notifications import unread_count
    from app.models.notification import Notification
    from flask_login import current_user

    @app.context_processor
    def inject_helpers():
        recent = []
        unread = 0
        if current_user.is_authenticated:
            unread = unread_count(current_user.id)
            recent = (
                Notification.query.filter_by(user_id=current_user.id)
                .order_by(Notification.created_at.desc()).limit(5).all()
            )
        return dict(
            user_has_permission=user_has_permission,
            unread_notifications_count=unread,
            recent_notifications=recent,
        )

    # --- error pages ---
    @app.errorhandler(403)
    def forbidden(e):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def server_error(e):
        db.session.rollback()
        return render_template("errors/500.html"), 500

    return app
