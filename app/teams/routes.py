import re
from io import BytesIO

from flask import Blueprint, render_template, redirect, url_for, flash, request, abort, send_file, jsonify
from flask_login import login_required, current_user

from app.extensions import db
from app.models.team import Team, TeamMember, WINDOW_SECTIONS
from app.models.document import Document
from app.models.event import CooperativeDay
from app.models.user import User
from app.teams.forms import TeamForm, TeamMemberForm, WindowForm, ActionForm, DistrictForm
from app.utils.decorators import permission_required
from app.utils.audit import log_action

teams_bp = Blueprint("teams", __name__)


def _uses_windows(team):
    """Only the Invitation / Registration / Per-diem team uses window leaders + staff."""
    return "invitation" in (team.name or "").lower()


def _section_query(team, section):
    """Top-level leaders of one section. Older leaders with no section count as the first one."""
    query = team.members.filter_by(parent_id=None)
    if section == WINDOW_SECTIONS[0]:
        return query.filter(db.or_(TeamMember.section == section, TeamMember.section.is_(None)))
    return query.filter(TeamMember.section == section)


def _window_sort_key(member):
    """Sort by the number in the window label (Window 2 before Window 10).
    Members with no window go last."""
    match = re.search(r"\d+", member.window_label or "")
    number = int(match.group()) if match else 10**9
    return (number, (member.window_label or "").lower(), member.id)


def _back(team_id, section=None):
    return redirect(url_for(
        "teams.team_detail", team_id=team_id, section=section,
        page=request.form.get("page", type=int),
    ))


def _export_context(team):
    """Resolve (use_windows, section, members) for the export routes,
    mirroring the logic in team_detail()."""
    use_windows = _uses_windows(team)
    section = None
    if use_windows:
        section = request.args.get("section")
        if section not in WINDOW_SECTIONS and section != "Participants":
            section = WINDOW_SECTIONS[0]
        members = _section_query(team, section).order_by(TeamMember.id).all()
        members.sort(key=_window_sort_key)
    else:
        members = team.members.filter_by(parent_id=None).order_by(TeamMember.id).all()
    return use_windows, section, members


def _safe_filename(*parts):
    name = "_".join(p for p in parts if p)
    name = re.sub(r"[^A-Za-z0-9_\-]+", "_", name).strip("_")
    return name or "export"


def _is_team_manager(team):
    """Admin (manage_teams permission) OR the leader of this very team."""
    return current_user.has_permission("manage_teams") or team.leader_id == current_user.id


def _is_team_viewer(team):
    """Managers plus ordinary members of the team can open it."""
    if _is_team_manager(team):
        return True
    return TeamMember.query.filter_by(team_id=team.id, user_id=current_user.id).first() is not None


# ---------- Invitation tab: Name / Phone / Account / Date / Sign / Day (+ any extra columns) ----------

INV_FIXED = ("Account", "Date", "Sign", "Day")
INV_PER_PAGE = 30


def _cell_text(val):
    if val in (None, ""):
        return ""
    if hasattr(val, "strftime"):
        return val.strftime("%Y-%m-%d")
    if isinstance(val, float) and val.is_integer():
        val = int(val)
    return str(val).strip()


def _tidy_phone(raw):
    """Light clean-up only, never rejects. Removes spaces/dashes, turns +251... into 0...,
    and puts back the leading 0 that Excel drops (911478198 -> 0911478198)."""
    raw = (raw or "").strip()
    if not raw:
        return ""
    d = re.sub(r"[\s\-().]", "", raw)
    if d.startswith("+"):
        d = d[1:]
    if d.isdigit():
        if d.startswith("251") and len(d) == 12:
            d = "0" + d[3:]
        elif len(d) == 9 and not d.startswith("0"):
            d = "0" + d
    return d[:15]


def _tidy_account(raw):
    """Light clean-up only, never rejects. Removes spaces and dashes."""
    return re.sub(r"[\s\-]", "", (raw or "").strip())[:20]


def _phone_bad(value):
    """True when a phone is filled in but is not exactly 10 digits."""
    return bool(value) and not (value.isdigit() and len(value) == 10)


def _account_bad(value):
    """True when an account is filled in but is not exactly 13 digits."""
    return bool(value) and not (value.isdigit() and len(value) == 13)


def _norm_name(name):
    """'  Abebe   KEBEDE ' -> 'abebe kebede' so first/middle/last names are compared as a whole."""
    return " ".join((name or "").lower().split())


def _norm_field(name):
    """Strip everything but letters and lowercase, so 'Acount', 'Account #', 'ACC. NO' all match."""
    return re.sub(r"[^a-z]", "", (name or "").lower())


def _looks_like_account_field(fname):
    """True for any extra column that is clearly meant to hold a bank account number,
    including common typos/abbreviations like 'Acount' or 'Acct No'."""
    n = _norm_field(fname)
    return n in ("account", "acount", "accountno", "accountnumber", "acctno", "bankaccount") or "acct" in n


def _extra_account_issues(all_members):
    """For every extra-field column that looks like an account number, work out which member
    ids have a value that is not exactly 13 digits, and which ids share a value with someone
    else (accounts must be unique per person)."""
    field_values = {}
    for m in all_members:
        ex = m.extra_fields or {}
        for fname, val in ex.items():
            val = (val or "").strip()
            if _looks_like_account_field(fname) and val:
                field_values.setdefault(fname, {})[m.id] = val

    bad_ids, dup_ids = {}, {}
    for fname, values in field_values.items():
        counts = {}
        for v in values.values():
            counts[v] = counts.get(v, 0) + 1
        bad_ids[fname] = {mid for mid, v in values.items() if _account_bad(v)}
        dup_ids[fname] = {mid for mid, v in values.items() if counts[v] > 1}
    return bad_ids, dup_ids


def _invitation_flags(all_members):
    """{member_id: {'name': dup?, 'phone': bad?, 'account': bad?, 'extra': {fname: bad_or_dup?},
    'extra_bad': any extra-field issue?}} for the WHOLE Invitation list."""
    counts = {}
    for m in all_members:
        key = _norm_name(m.display_name)
        counts[key] = counts.get(key, 0) + 1

    bad_ids, dup_ids = _extra_account_issues(all_members)
    extra_fields = set(bad_ids) | set(dup_ids)

    flags = {}
    for m in all_members:
        ex = m.extra_fields or {}
        extra = {
            fname: True
            for fname in extra_fields
            if m.id in bad_ids.get(fname, ()) or m.id in dup_ids.get(fname, ())
        }
        flags[m.id] = {
            "name": counts[_norm_name(m.display_name)] > 1,
            "phone": _phone_bad(m.phone or ""),
            "account": _account_bad(ex.get("Account", "")),
            "extra": extra,
            "extra_bad": bool(extra),
        }
    return flags


def _invitation_problem_count(flags):
    return sum(1 for f in flags.values() if any(f.values()))


def _invitation_visible_fixed(all_members):
    """Which of the built-in Account/Date/Sign/Day columns actually have data for at least
    one person — so a column that was never in the uploaded file (e.g. no 'Date' column)
    doesn't show up empty on the web page."""
    present = set()
    for m in all_members:
        ex = m.extra_fields or {}
        for key in INV_FIXED:
            if (ex.get(key) or "").strip():
                present.add(key)
    return present

def _invitation_extra_names(members):
    names = set()
    for m in members:
        names.update((m.extra_fields or {}).keys())
    return sorted(n for n in names if n not in INV_FIXED)


def _invitation_rows(members, extra_names, visible_fixed):
    rows = []
    for m in members:
        ex = m.extra_fields or {}
        row = [m.display_name]
        for key in ("Account", "Date", "Sign", "Day"):
            if key in visible_fixed:
                row.append(ex.get(key, ""))
        row += [ex.get(n, "") for n in extra_names]
        rows.append(row)
    return rows


def _invitation_excel(team, section, members):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Border, Side, Alignment
    from openpyxl.utils import get_column_letter

    extra_names = _invitation_extra_names(members)
    visible_fixed = _invitation_visible_fixed(members)
    fixed_headers = [h for h in ("Account", "Date", "Sign", "Day") if h in visible_fixed]
    fixed_widths = {"Account": 22, "Date": 14, "Sign": 18, "Day": 12}

    wb = Workbook()
    ws = wb.active
    ws.title = section[:31]

    body_font = Font(name="Arial Narrow", size=10)
    header_fill = PatternFill("solid", fgColor="4472C4")
    header_font = Font(name="Arial Narrow", size=10, bold=True, color="FFFFFF")
    thin = Side(style="thin", color="B7B7B7")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    center = Alignment(horizontal="center", vertical="center", wrap_text=True)
    left = Alignment(horizontal="left", vertical="center", wrap_text=True)

    headers = ["S/no", "Name"] + fixed_headers + extra_names
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(headers))
    ws.cell(row=1, column=1, value=f"{section} Team").font = Font(name="Arial Narrow", bold=True, size=14)
    ws.cell(row=1, column=1).alignment = center

    for col, h in enumerate(headers, start=1):
        c = ws.cell(row=3, column=col, value=h)
        c.font = header_font
        c.fill = header_fill
        c.border = border
        c.alignment = center

    for idx, row in enumerate(_invitation_rows(members, extra_names, visible_fixed), start=1):
        for col, val in enumerate([idx] + row, start=1):
            c = ws.cell(row=3 + idx, column=col, value=val)
            c.font = body_font
            c.border = border
            c.alignment = left

    widths = [6, 26, 16] + [fixed_widths[h] for h in fixed_headers] + [16] * len(extra_names)
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return send_file(
        buf, as_attachment=True,
        download_name=_safe_filename(team.name, section) + ".xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


def _invitation_pdf(team, section, members):
    from xml.sax.saxutils import escape
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

    extra_names = _invitation_extra_names(members)
    visible_fixed = _invitation_visible_fixed(members)
    fixed_headers = [h for h in ("Account", "Date", "Sign", "Day") if h in visible_fixed]
    fixed_widths_map = {"Account": 4.5, "Date": 3, "Sign": 4.5, "Day": 2.5}

    styles = getSampleStyleSheet()

    cell_style = styles["BodyText"]
    cell_style.fontSize = 8 if extra_names else 9
    cell_style.leading = 10 if extra_names else 11

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=landscape(A4),
        leftMargin=1.5 * cm, rightMargin=1.5 * cm, topMargin=1.2 * cm, bottomMargin=1.2 * cm,
    )
    story = [Paragraph(f"<b>{escape(section)} Team</b>", styles["Title"]), Spacer(1, 10)]

    data = [["#", "Name"] + fixed_headers + extra_names]
    for idx, row in enumerate(_invitation_rows(members, extra_names, visible_fixed), start=1):
        data.append([str(idx)] + [Paragraph(escape(str(x)), cell_style) for x in row])
    if len(data) == 1:
        data.append(["No records."] + [""] * (len(data[0]) - 1))

    widths = [1.2 * cm, 6 * cm, 3.5 * cm] + [fixed_widths_map[h] * cm for h in fixed_headers] + [2.8 * cm] * len(extra_names)
    max_w = 26.7 * cm
    total = sum(widths)
    if total > max_w:
        widths = [w * max_w / total for w in widths]

    table = Table(data, colWidths=widths, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E3D")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8 if extra_names else 9),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#B7B7B7")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (0, -1), "CENTER"),
        ("TOPPADDING", (0, 1), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 7),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F5F5")]),
    ]))
    story.append(table)
    doc.build(story)
    buf.seek(0)
    return send_file(
        buf, as_attachment=True,
        download_name=_safe_filename(team.name, section) + ".pdf",
        mimetype="application/pdf",
    )


def _invitation_import(team, section, ws):
    header_map = {
        "name": "name", "full name": "name",
        "phone": "phone", "phone number": "phone", "mobile": "phone",
        "account": "Account", "account number": "Account",
        "date": "Date",
        "sign": "Sign", "signature": "Sign",
        "day": "Day",
    }
    skip_headers = {"s/no", "#", "no", "sn", "s/n", "s.n"}

    col_map = {}
    header_row = None
    for r_idx, row in enumerate(ws.iter_rows(min_row=1, max_row=6), start=1):
        found = {}
        for cell in row:
            text_ = _cell_text(cell.value)
            key = text_.lower()
            if not text_ or key in skip_headers:
                continue
            found[cell.column] = header_map.get(key) or ("extra", text_[:60])
        if "name" in found.values():
            col_map, header_row = found, r_idx
            break

    if not header_row:
        flash("Could not find a 'Name' column in the first rows of that file.", "danger")
        return _back(team.id, section)

    people = []
    for row in ws.iter_rows(min_row=header_row + 1):
        vals, extra = {}, {}
        for cell in row:
            kind = col_map.get(cell.column)
            if not kind:
                continue
            v = _cell_text(cell.value)
            if isinstance(kind, tuple):
                if v:
                    extra[kind[1]] = v[:100]
            else:
                vals[kind] = v
        if not vals.get("name"):
            continue

        info = {k: vals[k][:100] for k in ("Date", "Sign", "Day") if vals.get(k)}
        account = _tidy_account(vals.get("Account"))
        if account:
            info["Account"] = account
        info.update(extra)
        people.append({
            "name": vals["name"][:150],
            "phone": _tidy_phone(vals.get("phone")),
            "extra": info,
        })

    if not people:
        flash("No rows with a name were found in that file.", "warning")
        return _back(team.id, section)

    for m in _section_query(team, section).all():
        db.session.delete(m)
    db.session.flush()

    for p in people:
        db.session.add(TeamMember(
            team_id=team.id,
            member_name=p["name"],
            phone=p["phone"] or None,
            section=section,
            extra_fields=p["extra"] or None,
        ))

    log_action("update", "Team", team.id, f"Imported {section} list from Excel ({len(people)} people)")
    db.session.commit()

    problems = _invitation_problem_count(
        _invitation_flags(_section_query(team, section).all())
    )
    if problems:
        flash(
            f"Imported {len(people)} people. {problems} row(s) need attention and are shown in red "
            f"(repeated name, phone not 10 digits, or account not 13 digits).",
            "warning",
        )
    else:
        flash(f"Imported {len(people)} people into {section}.", "success")
    return _back(team.id, section)


@teams_bp.route("/")
@login_required
def teams_list():
    event_id = request.args.get("event_id", type=int)
    query = Team.query
    # Admins see every team; everyone else sees only teams they lead or belong to.
    if not current_user.has_permission("manage_teams"):
        member_team_ids = db.session.query(TeamMember.team_id).filter_by(user_id=current_user.id)
        query = query.filter(
            db.or_(Team.leader_id == current_user.id, Team.id.in_(member_team_ids))
        )
    if event_id:
        query = query.filter_by(cooperative_day_id=event_id)
    teams = query.order_by(Team.cooperative_day_id.desc(), Team.name).all()
    events = CooperativeDay.query.order_by(CooperativeDay.year.desc()).all()
    return render_template("teams/list.html", teams=teams, events=events, selected_event_id=event_id)


@teams_bp.route("/new", methods=["GET", "POST"])
@login_required
@permission_required("manage_teams")
def team_new():
    form = TeamForm()
    _populate_choices(form)
    if form.validate_on_submit():
        team = Team(
            name=form.name.data,
            description=form.description.data,
            cooperative_day_id=form.cooperative_day_id.data,
            leader_id=form.leader_id.data or None,
            start_date=form.start_date.data,
            end_date=form.end_date.data,
            status=form.status.data,
        )
        db.session.add(team)
        db.session.flush()
        log_action("create", "Team", team.id, f"Created team {team.name}")
        db.session.commit()
        flash(f"Team '{team.name}' created.", "success")
        return redirect(url_for("teams.team_detail", team_id=team.id))
    return render_template("teams/form.html", form=form, is_new=True)


@teams_bp.route("/<int:team_id>")
@login_required
def team_detail(team_id):
    team = Team.query.get_or_404(team_id)
    if not _is_team_viewer(team):
        abort(403)
    member_form = TeamMemberForm()
    documents = Document.query.filter_by(team_id=team.id).order_by(Document.created_at.desc()).all()

    use_windows = _uses_windows(team)
    current_section = None
    if use_windows:
        current_section = request.args.get("section")
        if current_section not in WINDOW_SECTIONS and current_section != "Participants":
            current_section = WINDOW_SECTIONS[0]
        members = _section_query(team, current_section).order_by(TeamMember.id).all()
        members.sort(key=_window_sort_key)
    else:
        members = team.members.filter_by(parent_id=None).order_by(TeamMember.id).all()

    # Invitation tab: extra columns, red flags and paging (30 per page)
    inv_extra_names, inv_page, inv_pages, inv_offset, inv_total = [], 1, 1, 0, 0
    inv_flags, inv_problems = {}, 0
    inv_visible_fixed = set()
    inv_problem_ids = []
    if use_windows and current_section in ("Invitation", "Participants"):
        inv_total = len(members)
        inv_extra_names = _invitation_extra_names(members)
        inv_visible_fixed = _invitation_visible_fixed(members)
        inv_flags = _invitation_flags(members)          # checked across ALL pages
        inv_problems = _invitation_problem_count(inv_flags)
        inv_pages = max(1, -(-inv_total // INV_PER_PAGE))
        inv_page = min(max(request.args.get("page", 1, type=int), 1), inv_pages)
        inv_offset = (inv_page - 1) * INV_PER_PAGE
        inv_problem_ids = [
            {"id": m.id, "page": (idx // INV_PER_PAGE) + 1}
            for idx, m in enumerate(members)
            if any(inv_flags.get(m.id, {}).values())
        ]
        members = members[inv_offset:inv_offset + INV_PER_PAGE]

    extra_field_names = []
    if use_windows:
        names = set()
        for m in members:
            names.update((m.extra_fields or {}).keys())
        extra_field_names = sorted(names)

    return render_template(
        "teams/detail.html",
        team=team,
        members=members,
        use_windows=use_windows,
        sections=WINDOW_SECTIONS,
        current_section=current_section,
        extra_field_names=extra_field_names,
        inv_extra_names=inv_extra_names,
        inv_visible_fixed=inv_visible_fixed,
        inv_flags=inv_flags,
        inv_problem_ids=inv_problem_ids,
        inv_problems=inv_problems,
        inv_page=inv_page,
        inv_pages=inv_pages,
        inv_offset=inv_offset,
        inv_total=inv_total,
        documents=documents,
        member_form=member_form,
        can_manage_members=_is_team_manager(team),
        can_edit_team=current_user.has_permission("manage_teams"),
    )


@teams_bp.route("/<int:team_id>/export.xlsx")
@login_required
def team_export_excel(team_id):
    team = Team.query.get_or_404(team_id)
    if not _is_team_viewer(team):
        abort(403)
    use_windows, section, members = _export_context(team)

    if use_windows and section in ("Invitation", "Participants"):
        return _invitation_excel(team, section, members)

    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Border, Side, Alignment
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    ws = wb.active
    ws.title = (section or "Members")[:31]

    header_fill = PatternFill("solid", fgColor="1F4E3D")
    header_font = Font(bold=True, color="FFFFFF")
    title_font = Font(bold=True, size=14)
    thin = Side(style="thin", color="B7B7B7")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    center = Alignment(horizontal="center", vertical="center", wrap_text=True)
    left = Alignment(horizontal="left", vertical="center", wrap_text=True)

    extra_field_names = []
    if use_windows:
        names = set()
        for m in members:
            names.update((m.extra_fields or {}).keys())
        extra_field_names = sorted(names)

    title_text = f"{section} Team" if section else team.name
    base_cols = 6  # S/no, Leader, Window, District, Staff, Action
    n_cols = (base_cols + len(extra_field_names)) if use_windows else 3
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=n_cols)
    ws.cell(row=1, column=1, value=title_text).font = title_font
    ws.cell(row=1, column=1).alignment = center

    if use_windows:
        headers = ["S/no", "Leader", "Window", "District", "Staff", "Action"] + extra_field_names
    else:
        headers = ["#", "Name", "Added"]
    for col, h in enumerate(headers, start=1):
        c = ws.cell(row=3, column=col, value=h)
        c.font = header_font
        c.fill = header_fill
        c.border = border
        c.alignment = center

    row_ptr = 4
    if use_windows:
        staff_col = 5
        total_cols = base_cols + len(extra_field_names)
        merge_cols = [c for c in range(1, total_cols + 1) if c != staff_col]

        for idx, m in enumerate(members, start=1):
            staff = sorted(m.staff, key=lambda s: s.id)
            staff_names = [s.display_name for s in staff] or ["No staff yet"]
            span = len(staff_names)
            start_row, end_row = row_ptr, row_ptr + span - 1

            ws.cell(row=start_row, column=1, value=idx)
            ws.cell(row=start_row, column=2, value=m.display_name)
            ws.cell(row=start_row, column=3, value=m.window_label or "")
            ws.cell(row=start_row, column=4, value=m.district or "")
            ws.cell(row=start_row, column=6, value=m.action_note or "")
            for i, fname in enumerate(extra_field_names):
                ws.cell(row=start_row, column=7 + i, value=(m.extra_fields or {}).get(fname, ""))
            for i, name in enumerate(staff_names):
                ws.cell(row=row_ptr + i, column=staff_col, value=name)

            if span > 1:
                for col in merge_cols:
                    ws.merge_cells(start_row=start_row, end_row=end_row, start_column=col, end_column=col)

            for r in range(start_row, end_row + 1):
                for col in range(1, total_cols + 1):
                    cell = ws.cell(row=r, column=col)
                    cell.border = border
                    cell.alignment = left if col == staff_col else center
            row_ptr = end_row + 1

        widths = [6, 22, 14, 16, 26, 30] + [18] * len(extra_field_names)
    else:
        for idx, m in enumerate(members, start=1):
            ws.cell(row=row_ptr, column=1, value=idx)
            ws.cell(row=row_ptr, column=2, value=m.display_name)
            ws.cell(row=row_ptr, column=3, value=m.joined_at.strftime("%Y-%m-%d") if m.joined_at else "")
            for col in range(1, 4):
                cell = ws.cell(row=row_ptr, column=col)
                cell.border = border
                cell.alignment = center
            row_ptr += 1
        widths = [6, 30, 16]

    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    filename = _safe_filename(team.name, section) + ".xlsx"
    return send_file(
        buf,
        as_attachment=True,
        download_name=filename,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@teams_bp.route("/<int:team_id>/import.xlsx", methods=["POST"])
@login_required
def team_import_excel(team_id):
    team = Team.query.get_or_404(team_id)
    if not _is_team_manager(team):
        abort(403)

    use_windows = _uses_windows(team)
    if not use_windows:
        abort(404)

    section = request.form.get("section") or request.args.get("section")
    if section not in WINDOW_SECTIONS and section != "Participants":
        section = WINDOW_SECTIONS[0]

    file = request.files.get("excel_file")
    if not file or not file.filename:
        flash("Choose an Excel file to upload.", "danger")
        return _back(team.id, section)
    if not file.filename.lower().endswith(".xlsx"):
        flash("Please upload a .xlsx file.", "danger")
        return _back(team.id, section)

    from openpyxl import load_workbook
    try:
        wb = load_workbook(file, data_only=True)
        ws = wb.active
    except Exception:
        flash("Could not read that file. Make sure it's a valid .xlsx export.", "danger")
        return _back(team.id, section)

    if section in ("Invitation", "Participants"):
        return _invitation_import(team, section, ws)

    # Map each column to a known field, or treat it as a new custom field.
    col_map = {}
    header_row = next(ws.iter_rows(min_row=3, max_row=3), [])
    for cell in header_row:
        text = str(cell.value).strip() if cell.value not in (None, "") else ""
        if not text:
            continue
        key = text.lower()
        if key in ("s/no", "#", "no"):
            col_map[cell.column] = "sno"
        elif key == "leader":
            col_map[cell.column] = "leader"
        elif key == "window":
            col_map[cell.column] = "window"
        elif key == "district":
            col_map[cell.column] = "district"
        elif key == "staff":
            col_map[cell.column] = "staff"
        elif key == "action":
            col_map[cell.column] = "action"
        else:
            col_map[cell.column] = ("extra", text)

    groups = []
    current = None
    for row in ws.iter_rows(min_row=4):
        row_leader = row_window = row_district = row_action = row_staff = None
        row_extra = {}
        for cell in row:
            kind = col_map.get(cell.column)
            if not kind:
                continue
            val = cell.value
            val = str(val).strip() if val not in (None, "") else ""
            if kind == "leader":
                row_leader = val
            elif kind == "window":
                row_window = val
            elif kind == "district":
                row_district = val
            elif kind == "staff":
                row_staff = val
            elif kind == "action":
                row_action = val
            elif isinstance(kind, tuple) and kind[0] == "extra":
                row_extra[kind[1]] = val

        if row_leader:
            current = {
                "leader": row_leader,
                "window": row_window or "",
                "district": row_district or "",
                "action": row_action or "",
                "extra": {k: v for k, v in row_extra.items() if v},
                "staff": [],
            }
            groups.append(current)

        if current is None:
            continue

        for k, v in row_extra.items():
            if v:
                current["extra"][k] = v

        if row_staff and row_staff.lower() != "no staff yet":
            current["staff"].append(row_staff)

    if not groups:
        flash("No rows found in that file.", "warning")
        return _back(team.id, section)

    existing = _section_query(team, section).all()
    for m in existing:
        db.session.delete(m)
    db.session.flush()

    for g in groups:
        leader = TeamMember(
            team_id=team.id,
            member_name=g["leader"].rstrip(","),
            window_label=g["window"] or None,
            district=g["district"] or None,
            action_note=g["action"] or None,
            section=section,
            extra_fields=g["extra"] or None,
        )
        db.session.add(leader)
        db.session.flush()
        for name in g["staff"]:
            db.session.add(TeamMember(team_id=team.id, member_name=name, parent_id=leader.id))

    log_action("update", "Team", team.id, f"Imported {section} roster from Excel ({len(groups)} leaders)")
    db.session.commit()
    flash(f"Imported {len(groups)} leader(s) into {section}.", "success")
    return _back(team.id, section)


@teams_bp.route("/<int:team_id>/export.pdf")
@login_required
def team_export_pdf(team_id):
    team = Team.query.get_or_404(team_id)
    if not _is_team_viewer(team):
        abort(403)
    use_windows, section, members = _export_context(team)

    if use_windows and section == "Invitation":
        return _invitation_pdf(team, section, members)

    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

    styles = getSampleStyleSheet()
    cell_style = styles["BodyText"]
    cell_style.fontSize = 9
    cell_style.leading = 11

    extra_field_names = []
    if use_windows:
        names = set()
        for m in members:
            names.update((m.extra_fields or {}).keys())
        extra_field_names = sorted(names)

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=landscape(A4),
        leftMargin=1.5 * cm, rightMargin=1.5 * cm, topMargin=1.2 * cm, bottomMargin=1.2 * cm,
    )
    title_text = f"{section} Team" if section else team.name
    story = [Paragraph(f"<b>{title_text}</b>", styles["Title"]), Spacer(1, 10)]

    spans = []
    if use_windows:
        data = [["#", "Leader", "Window", "District", "Staff", "Action"] + extra_field_names]
        row_ptr = 1
        for idx, m in enumerate(members, start=1):
            staff = sorted(m.staff, key=lambda s: s.id)
            staff_names = [s.display_name for s in staff] or ["No staff yet"]
            span = len(staff_names)
            start_row, end_row = row_ptr, row_ptr + span - 1
            for i, name in enumerate(staff_names):
                row = [
                    str(idx) if i == 0 else "",
                    Paragraph(m.display_name, cell_style) if i == 0 else "",
                    (m.window_label or "") if i == 0 else "",
                    (m.district or "") if i == 0 else "",
                    Paragraph(name, cell_style),
                    Paragraph(m.action_note or "", cell_style) if i == 0 else "",
                ]
                for fname in extra_field_names:
                    row.append(Paragraph((m.extra_fields or {}).get(fname, ""), cell_style) if i == 0 else "")
                data.append(row)
            if span > 1:
                for col in [0, 1, 2, 3, 5] + list(range(6, 6 + len(extra_field_names))):
                    spans.append(("SPAN", (col, start_row), (col, end_row)))
            row_ptr = end_row + 1
        col_widths = [1.3 * cm, 3.5 * cm, 2.3 * cm, 2.3 * cm, 5 * cm, 6 * cm] + [3.5 * cm] * len(extra_field_names)
    else:
        data = [["#", "Name", "Added"]]
        for idx, m in enumerate(members, start=1):
            data.append([str(idx), Paragraph(m.display_name, cell_style),
                         m.joined_at.strftime("%Y-%m-%d") if m.joined_at else ""])
        col_widths = [1.5 * cm, 10 * cm, 4 * cm]

    if len(data) == 1:
        data.append(["No records." if use_windows else "No members."] + [""] * (len(data[0]) - 1))

    table = Table(data, colWidths=col_widths, repeatRows=1)
    style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E3D")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#B7B7B7")),
        ("ALIGN", (0, 0), (0, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F5F5")]),
    ] + spans
    table.setStyle(TableStyle(style_cmds))
    story.append(table)
    doc.build(story)
    buf.seek(0)
    filename = _safe_filename(team.name, section) + ".pdf"
    return send_file(buf, as_attachment=True, download_name=filename, mimetype="application/pdf")


@teams_bp.route("/<int:team_id>/edit", methods=["GET", "POST"])
@login_required
@permission_required("manage_teams")
def team_edit(team_id):
    team = Team.query.get_or_404(team_id)
    form = TeamForm(obj=team)
    _populate_choices(form)
    if request.method == "GET":
        form.leader_id.data = team.leader_id or 0

    if form.validate_on_submit():
        team.name = form.name.data
        team.description = form.description.data
        team.cooperative_day_id = form.cooperative_day_id.data
        team.leader_id = form.leader_id.data or None
        team.start_date = form.start_date.data
        team.end_date = form.end_date.data
        team.status = form.status.data
        log_action("update", "Team", team.id, f"Updated team {team.name}")
        db.session.commit()
        flash(f"Team '{team.name}' updated.", "success")
        return redirect(url_for("teams.team_detail", team_id=team.id))
    return render_template("teams/form.html", form=form, is_new=False, team=team)


@teams_bp.route("/<int:team_id>/members/add", methods=["POST"])
@login_required
def team_member_add(team_id):
    team = Team.query.get_or_404(team_id)
    if not _is_team_manager(team):
        abort(403)
    use_windows = _uses_windows(team)
    section = request.form.get("section")
    if not use_windows or (section not in WINDOW_SECTIONS and section != "Participants"):
        section = None
    form = TeamMemberForm()
    if form.validate_on_submit():
        pool = _section_query(team, section) if section else team.members
        existing = {(m.member_name or "").strip().lower() for m in pool}
        # Invitation: the same name may be added twice on purpose; it is then shown in red.
        allow_dupes = section in ("Invitation", "Participants")
        added = 0
        for line in form.names.data.splitlines():
            name = line.strip()
            if not name or (not allow_dupes and name.lower() in existing):
                continue
            db.session.add(TeamMember(
                team_id=team.id, member_name=name[:150],
                role_in_team="Member", section=section,
            ))
            existing.add(name.lower())
            added += 1
        log_action("create", "TeamMember", team.id, f"Added {added} member(s) to team {team.name}")
        db.session.commit()
        flash(f"{added} member(s) added to the team.", "success")
    else:
        flash("Please write at least one name.", "danger")
    return _back(team.id, section)


@teams_bp.route("/<int:team_id>/members/<int:member_id>/remove", methods=["POST"])
@login_required
def team_member_remove(team_id, member_id):
    team = Team.query.get_or_404(team_id)
    if not _is_team_manager(team):
        abort(403)
    member = TeamMember.query.filter_by(id=member_id, team_id=team_id).first_or_404()
    root = member.leader or member
    section = root.section if _uses_windows(team) else None
    log_action("delete", "TeamMember", member.id, f"Removed member {member.display_name} from team {team_id}")
    db.session.delete(member)
    db.session.commit()
    flash("Member removed from team.", "info")
    return _back(team_id, section)


@teams_bp.route("/<int:team_id>/members/<int:member_id>/window", methods=["POST"])
@login_required
def team_member_window(team_id, member_id):
    team = Team.query.get_or_404(team_id)
    if not _is_team_manager(team):
        abort(403)
    member = TeamMember.query.filter_by(id=member_id, team_id=team_id).first_or_404()
    form = WindowForm()
    if form.validate_on_submit():
        member.window_label = (form.window_label.data or "").strip() or None
        log_action("update", "TeamMember", member.id, f"Set window for {member.display_name}")
        db.session.commit()
        if request.headers.get("X-Requested-With") == "fetch":
            return "", 204
        flash("Window saved.", "success")
    return _back(team_id, member.section)


@teams_bp.route("/<int:team_id>/members/<int:member_id>/field", methods=["POST"])
@login_required
def team_member_field(team_id, member_id):
    team = Team.query.get_or_404(team_id)
    if not _is_team_manager(team):
        abort(403)
    member = TeamMember.query.filter_by(id=member_id, team_id=team_id).first_or_404()
    field_name = (request.form.get("field_name") or "").strip()
    field_value = (request.form.get("field_value") or "").strip()
    if field_name:
        data = dict(member.extra_fields or {})
        if field_value:
            data[field_name] = field_value
        else:
            data.pop(field_name, None)
        member.extra_fields = data
        log_action("update", "TeamMember", member.id, f"Set field '{field_name}' for {member.display_name}")
        db.session.commit()
        flash(f"'{field_name}' saved.", "success")
    return _back(team_id, member.section)


@teams_bp.route("/<int:team_id>/members/<int:member_id>/invite", methods=["POST"])
@login_required
def team_member_invite(team_id, member_id):
    """Save one Invitation row. Nothing is rejected: wrong phone/account values are saved
    as typed and simply shown in red (see _invitation_flags)."""
    team = Team.query.get_or_404(team_id)
    if not _is_team_manager(team):
        abort(403)
    member = TeamMember.query.filter_by(id=member_id, team_id=team_id).first_or_404()

    name = (request.form.get("member_name") or "").strip()
    if name:
        member.member_name = name[:150]

    if "phone" in request.form:
        member.phone = _tidy_phone(request.form.get("phone")) or None

    data = dict(member.extra_fields or {})

    for key in INV_FIXED:
        if key not in request.form:
            continue
        raw = request.form.get(key)
        val = _tidy_account(raw) if key == "Account" else (raw or "").strip()[:100]
        if val:
            data[key] = val
        else:
            data.pop(key, None)

    for form_key, raw in request.form.items():
        if form_key.startswith("x__"):
            fname = form_key[3:][:60]
            val = (raw or "").strip()[:100]
            if val:
                data[fname] = val
            else:
                data.pop(fname, None)

    member.extra_fields = data or None
    db.session.commit()

    everyone = _section_query(team, member.section or WINDOW_SECTIONS[0]).all()
    flags = _invitation_flags(everyone)
    mine = flags.get(member.id, {})
    extra_bad_ids = {}
    for i, f in flags.items():
        for fname in f.get("extra", {}):
            extra_bad_ids.setdefault(fname, []).append(i)

    return jsonify(
        phone=member.phone or "",
        account=data.get("Account", ""),
        bad={"phone": bool(mine.get("phone")), "account": bool(mine.get("account"))},
        dupe_ids=[i for i, f in flags.items() if f["name"]],
        extra_bad_ids=extra_bad_ids,
        problems=_invitation_problem_count(flags),
    )


@teams_bp.route("/<int:team_id>/members/<int:member_id>/district", methods=["POST"])
@login_required
def team_member_district(team_id, member_id):
    team = Team.query.get_or_404(team_id)
    if not _is_team_manager(team):
        abort(403)
    member = TeamMember.query.filter_by(id=member_id, team_id=team_id).first_or_404()
    form = DistrictForm()
    if form.validate_on_submit():
        member.district = (form.district.data or "").strip() or None
        log_action("update", "TeamMember", member.id, f"Set district for {member.display_name}")
        db.session.commit()
        if request.headers.get("X-Requested-With") == "fetch":
            return "", 204
        flash("District saved.", "success")
    return _back(team_id, member.section)


@teams_bp.route("/<int:team_id>/members/<int:member_id>/action", methods=["POST"])
@login_required
def team_member_action(team_id, member_id):
    team = Team.query.get_or_404(team_id)
    if not _is_team_manager(team):
        abort(403)
    member = TeamMember.query.filter_by(id=member_id, team_id=team_id).first_or_404()
    form = ActionForm()
    if form.validate_on_submit():
        member.action_note = (form.action_note.data or "").strip() or None
        log_action("update", "TeamMember", member.id, f"Set today's action for {member.display_name}")
        db.session.commit()
        flash("Action saved.", "success")
    return _back(team_id, member.section)


@teams_bp.route("/<int:team_id>/members/<int:member_id>/staff/add", methods=["POST"])
@login_required
def team_staff_add(team_id, member_id):
    team = Team.query.get_or_404(team_id)
    if not _is_team_manager(team):
        abort(403)
    leader = TeamMember.query.filter_by(id=member_id, team_id=team_id, parent_id=None).first_or_404()
    form = TeamMemberForm()
    if form.validate_on_submit():
        existing = {(m.member_name or "").strip().lower() for m in team.members}
        added = 0
        for line in form.names.data.splitlines():
            name = line.strip()
            if not name or name.lower() in existing:
                continue
            db.session.add(TeamMember(
                team_id=team.id, parent_id=leader.id,
                member_name=name[:150], role_in_team="Staff",
            ))
            existing.add(name.lower())
            added += 1
        log_action("create", "TeamMember", leader.id, f"Added {added} staff under {leader.display_name}")
        db.session.commit()
        flash(f"{added} staff added under {leader.display_name}.", "success")
    else:
        flash("Please write at least one name.", "danger")
    return _back(team_id, leader.section)


@teams_bp.route("/<int:team_id>/members/<int:staff_id>/staff/move", methods=["POST"])
@login_required
def team_staff_move(team_id, staff_id):
    """Drag-and-drop: reassign a staff member from one window leader to another."""
    team = Team.query.get_or_404(team_id)
    if not _is_team_manager(team):
        abort(403)
    staff = TeamMember.query.filter_by(id=staff_id, team_id=team_id).first_or_404()
    if staff.parent_id is None:
        return {"ok": False, "error": "Not a staff member."}, 400
    new_leader_id = request.form.get("new_leader_id", type=int)
    new_leader = TeamMember.query.filter_by(id=new_leader_id, team_id=team_id, parent_id=None).first_or_404()
    if new_leader.section != staff.leader.section:
        return {"ok": False, "error": "Leaders are in different sections."}, 400
    old_leader_name = staff.leader.display_name if staff.leader else "?"
    staff.parent_id = new_leader.id
    log_action(
        "update", "TeamMember", staff.id,
        f"Moved staff {staff.display_name} from {old_leader_name} to {new_leader.display_name}",
    )
    db.session.commit()
    return {"ok": True}


def _populate_choices(form):
    form.cooperative_day_id.choices = [
        (e.id, e.name) for e in CooperativeDay.query.order_by(CooperativeDay.year.desc())
    ]
    form.leader_id.choices = [(0, "— None —")] + [
        (u.id, u.full_name) for u in User.query.filter_by(status="Active").order_by(User.full_name)
    ]