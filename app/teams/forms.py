from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, DateField, SubmitField
from wtforms.validators import DataRequired, Optional, Length

from app.models.team import TEAM_STATUSES


class TeamForm(FlaskForm):
    name = StringField("Team Name", validators=[DataRequired(), Length(max=150)])
    description = TextAreaField("Responsibilities / Description", validators=[Optional()])
    cooperative_day_id = SelectField("Cooperative Day", coerce=int, validators=[DataRequired()])
    leader_id = SelectField("Team Leader", coerce=int, validators=[Optional()])
    start_date = DateField("Start Date", validators=[Optional()])
    end_date = DateField("End Date", validators=[Optional()])
    status = SelectField("Status", choices=[(s, s) for s in TEAM_STATUSES])
    submit = SubmitField("Save Team")


class TeamMemberForm(FlaskForm):
    user_id = SelectField("Staff Member", coerce=int, validators=[DataRequired()])
    role_in_team = StringField("Role in Team", default="Member", validators=[Optional(), Length(max=80)])
    submit = SubmitField("Add Member")
