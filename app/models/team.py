from datetime import datetime
from app.extensions import db


TEAM_STATUSES = ["Active", "Inactive", "Completed"]
WINDOW_SECTIONS = ["Invitation", "Registration", "Per-diem"]


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
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))  # optional: members need no account
    member_name = db.Column(db.String(150))                      # name typed in by the team leader
    phone = db.Column(db.String(30))
    role_in_team = db.Column(db.String(80), default="Member")
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Window leader / staff structure
    window_label = db.Column(db.String(80))  # e.g. "Window 1"
    district = db.Column(db.String(120))      # e.g. "East", "Adama"
    extra_fields = db.Column(db.JSON, default=dict)  # any custom columns the user adds
    section = db.Column(db.String(50))       # Invitation / Registration / Per-diem
    action_note = db.Column(db.String(255))  # what this leader needs to do that day
    parent_id = db.Column(db.Integer, db.ForeignKey("team_members.id"))  # set = this person is staff under a leader
    staff = db.relationship(
        "TeamMember",
        backref=db.backref("leader", remote_side=[id]),
        cascade="all, delete-orphan",
    )

    @property
    def display_name(self):
        if self.member_name:
            return self.member_name
        return self.user.full_name if self.user else "—"

    def __repr__(self):
        return f"<TeamMember team={self.team_id} user={self.user_id}>"
