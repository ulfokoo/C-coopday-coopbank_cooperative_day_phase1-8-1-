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
    names = TextAreaField(
        "Member names (one name per line)",
        validators=[DataRequired(message="Please write at least one name.")],
    )
    submit = SubmitField("Add Members")



class WindowForm(FlaskForm):
    window_label = StringField("Window", validators=[Optional(), Length(max=255)])


class DistrictForm(FlaskForm):
    district = StringField("District", validators=[Optional(), Length(max=120)])


class ActionForm(FlaskForm):
    action_note = StringField("Action", validators=[Optional(), Length(max=255)])
