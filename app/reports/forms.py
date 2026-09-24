from flask_wtf import FlaskForm
from wtforms import TextAreaField, SelectField, SubmitField
from wtforms.validators import Optional

from app.models.report import REPORT_STATUSES


class AnnualReportForm(FlaskForm):
    executive_summary = TextAreaField("Executive Summary", validators=[Optional()])
    key_achievements = TextAreaField("Key Achievements", validators=[Optional()])
    challenges = TextAreaField("Challenges", validators=[Optional()])
    lessons_learned = TextAreaField("Lessons Learned", validators=[Optional()])
    recommendations = TextAreaField("Recommendations", validators=[Optional()])
    status = SelectField("Report Status", choices=[(s, s) for s in REPORT_STATUSES])
    submit = SubmitField("Save Report")
