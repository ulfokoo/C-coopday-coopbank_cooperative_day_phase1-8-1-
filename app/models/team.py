from datetime import datetime
from app.extensions import db

TEAM_STATUSES = ["Active", "Inactive", "Completed"]


class Team(db.Model):
    """A team/committee for one Cooperative Day year, e.g. 'Procurement Team'."""

    __tablename__ = "teams"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text)

    cooperative_day_id = db.Column(db.Integer, db.ForeignKey("cooperative_days.id"), nullable=False)
    leader_id = db.Column(db.Integer, db.ForeignKey("users.id"))

    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    status = db.Column(db.String(20), default="Active", nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    members = db.relationship(
        "TeamMember", backref="team", lazy="dynamic", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Team {self.name} ({self.cooperative_day_id})>"


class TeamMember(db.Model):
    """A staff member's membership in a team. A user can belong to several
    teams (across the same or different years) if authorized."""

    __tablename__ = "team_members"
    __table_args__ = (db.UniqueConstraint("team_id", "user_id", name="uq_team_user"),)

    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey("teams.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    role_in_team = db.Column(db.String(80), default="Member")  # e.g. Member, Deputy Leader
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<TeamMember team={self.team_id} user={self.user_id}>"
