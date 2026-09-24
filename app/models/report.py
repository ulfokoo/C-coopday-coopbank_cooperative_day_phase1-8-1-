from datetime import datetime
from app.extensions import db

REPORT_STATUSES = ["Draft", "Published"]


class AnnualReport(db.Model):
    """The narrative half of a Cooperative Day year's Annual Report.

    All *quantitative* figures (task counts, document counts, procurement
    totals...) are always computed live from the operational data by
    app.reports.services.build_report_context() — they are never frozen
    into this table, so a report always reflects the current state of the
    year's records. This model only stores the write-up a human adds on
    top: achievements, challenges, lessons learned and recommendations,
    plus who prepared it and whether it has been published.

    One row per CooperativeDay (a year "has one or more annual reports" in
    spirit, but in practice a year keeps a single living report document
    that is refined over time and can be marked Published when final).
    """

    __tablename__ = "annual_reports"

    id = db.Column(db.Integer, primary_key=True)
    cooperative_day_id = db.Column(
        db.Integer, db.ForeignKey("cooperative_days.id"), unique=True, nullable=False, index=True
    )

    executive_summary = db.Column(db.Text)
    key_achievements = db.Column(db.Text)
    challenges = db.Column(db.Text)
    lessons_learned = db.Column(db.Text)
    recommendations = db.Column(db.Text)

    status = db.Column(db.String(20), default="Draft", nullable=False, index=True)

    prepared_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    published_at = db.Column(db.DateTime)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    cooperative_day = db.relationship(
        "CooperativeDay", backref=db.backref("annual_report", uselist=False, cascade="all, delete-orphan")
    )
    prepared_by = db.relationship("User")

    def __repr__(self):
        return f"<AnnualReport {self.cooperative_day_id}>"
