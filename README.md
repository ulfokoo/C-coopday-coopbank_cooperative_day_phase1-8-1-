# CoopBank Cooperative Day Management & Tracking System

A multi-year, role-based web application for planning and tracking CoopBank's
annual Cooperative Day — from idea/planning through procurement, teams,
documents, correspondence, meetings, activities, and final reporting.

This drop is **Phase 1 + Phase 2 + Phase 3 + Phase 4 + Phase 5 + Phase 6 + Phase 7** of the full build:

**Phase 1 — Foundation**
- Project structure (Flask application factory + blueprints)
- Configuration via environment variables (dev/prod/test)
- Database models (SQLAlchemy) + Flask-Migrate
- Authentication (Flask-Login, hashed passwords, active/inactive accounts)
- User management (CRUD, search, pagination)
- Role management with a configurable permission system (not hard-coded to role names)
- Department management
- Base audit log (`AuditLog` model + `log_action()` helper, used by every module)
- Professional Bootstrap 5 UI shell (sidebar, top nav, dashboard cards)

**Phase 2 — Cooperative Day & Teams**
- `CooperativeDay` model — one workspace per year (2026, 2027, 2028, ...),
  never deleted, always browsable as history
- Full CRUD for Cooperative Day events, with status workflow
  (Planning → Preparation → Procurement → Implementation → Completed / Cancelled)
- Teams/Committees module, scoped to a Cooperative Day year
- Team member assignment (a user can belong to multiple teams)
- Dashboard summarizing years, teams, and active staff

**Phase 3 — Tasks, Instructions, Meetings, Decisions, Action Points**
- `Task` module: title, description, year/department/team/assignee, priority
  (Low/Medium/High/Critical), status (Not Started/In Progress/Waiting/
  Completed/Cancelled), % complete, due dates, comments thread, quick-status
  buttons, overdue highlighting, filterable list (year/team/status/priority/
  assignee/keyword)
- `Instruction` module ("management gives an instruction..."): source
  person, responsible person/department/team, deadline, priority, status
  (New/Assigned/In Progress/Completed/Overdue/Closed), optional link to a Task
- `Decision` register: important decisions, optionally tied to a Meeting and
  a follow-up Task
- `Meeting` module: agenda, minutes, participants (with attendance toggle),
  and **Action Points** that can be **promoted into a real Task with one
  click**, preserving the link back to the originating meeting
- Dashboard indicators: total/completed/pending/overdue tasks, tasks due
  soon (7 days), open/overdue instructions

**Phase 4 — Documents, Document Versions, Correspondence**
- `Document` module with full metadata (type, year, department, team,
  confidentiality, tags, description) and cross-links to a Task, Meeting,
  Instruction and/or Correspondence record
- `DocumentVersion` model for true versioning (`v1`, `v2`, `Final`, ...)
  independent of the parent Document row; every version keeps its own
  uploader, size, MIME type, notes and download counter
- Secure upload/download: extension allow-list, random UUID stored
  filenames (originals are never used as the on-disk name or in the URL),
  files organized under `uploads/documents/<cooperative_day_id>/`,
  every download logged to the audit trail
- Approval workflow: Draft → Submitted → Under Review → Approved/Rejected →
  Archived, gated by the `approve_documents` permission
- Search/filter by year, type, department, team, status and keyword
  (title/description/tags)
- `Correspondence` module: incoming/outgoing letters, memos, email records,
  instructions, meeting decisions, requests and responses — each with a
  unique reference number, response deadline, overdue highlighting, and a
  lifecycle (Received → Assigned → In Progress → Responded → Closed);
  Documents can be attached to a Correspondence record
- Dashboard indicators: total documents, pending document approvals,
  upcoming meetings

**Phase 5 — Procurement, Suppliers, Materials, Purchase Workflow**
- `ProcurementRequest` model covering the full lifecycle from the spec:
  Request → Approval → Supplier quotation → Evaluation → Purchase Order →
  Delivery → Inspection → Payment → Completion, with dedicated fields for
  each stage (PO number/order date, expected/actual delivery date,
  inspector + inspection notes, payment status/amount/date) and statuses
  Draft/Submitted/Under Review/Approved/Rejected/Procurement/Ordered/
  Delivered/Completed/Cancelled
- `ProcurementItem` line items per request (e.g. "Event banners x20"),
  each with its own quantity, unit cost, status and responsible person, plus
  an auto-computed items total
- One-click workflow buttons on the request detail page (gated by the
  `approve_purchase` permission), with light automatic bookkeeping — e.g.
  marking "Delivered" stamps the actual delivery date and inspector if not
  already set
- `Supplier` module: contact info, service category, registration info,
  Active/Inactive status, and a live list of every purchase request linked
  to that supplier
- `Material` module for event material/asset tracking (chairs, tents,
  banners, sound systems, ...) — required vs. available vs. purchased
  quantities per Cooperative Day year, with an auto-computed shortfall and
  a Needed → Requested → Purchased → Available → Deployed → Returned status
- `Document.procurement_request_id` is now a real foreign key (was reserved
  as a plain column in Phase 4) — documents can be uploaded and linked
  directly to a purchase request, and the request detail page shows every
  linked document
- New permissions: `manage_suppliers`, `manage_materials` (existing
  `view_procurement`, `create_purchase_request`, `approve_purchase` from
  Phase 1 are now fully wired to routes)

**Phase 6 — Activities, Communication/Media, Event Management**
- `Activity` module (the event schedule from the spec — opening ceremony,
  exhibition, cooperative awards, farmer/cooperative visits, panel
  discussions, training, media events, community activities, closing
  ceremony, ...): date/time/location, responsible team + responsible
  person, requirements, a free-text budget reference, and a status
  workflow (Planned → Confirmed → In Progress → Completed / Cancelled)
- `ActivityParticipant`: expected participants per activity with an
  attendance toggle, mirroring the Phase 3 meeting-participants pattern
- `Communication` module (comms/media pipeline): press releases, social
  media posts, posters, invitations, videos, photos, media coverage,
  radio/TV and website communication — each with target audience,
  platform, planned/publication dates, a delivery status (Planned → In
  Progress → Published / Cancelled) **and** a separate approval workflow
  (Pending → Approved/Rejected) gated by its own `approve_communication`
  permission
- Each communication item can carry one optional attachment (the actual
  flyer/photo/video file), stored the same secure way as Documents —
  extension allow-list, random UUID on-disk filename, download logged to
  the audit trail
- **Event management**: the Cooperative Day detail page is now a real
  workspace hub — stat cards for tasks/activities/media items completed
  and total documents (each linking straight into that module, pre-filtered
  to the year), plus an "Upcoming Activities" panel, alongside the existing
  Teams & Committees panel
- New permissions: `view_activities`, `manage_activities`,
  `view_communication`, `manage_communication`, `approve_communication`

Everything from Phase 7 onward (dashboard indicators for the new modules,
notifications, global search, full audit UI, annual reports, year
comparison, PDF/Excel export) is intentionally **not** in this drop — we're
building in phases as requested.

**Phase 7 — Dashboard Upgrades, Notifications, Global Search, Audit Log UI**
- `Notification` model + service (`app/utils/notifications.py`): `notify()`
  and `notify_users_with_permission()` create in-app notifications; wired
  into task assignment (create/edit), instruction assignment, document
  submission (notifies everyone with `approve_documents`), purchase request
  submission/approval/rejection, and meeting action point assignment
- `scan_deadlines()` runs on every dashboard load and raises (once each,
  idempotently) "due soon" / "overdue" reminders for tasks, instructions,
  correspondence response deadlines, and purchase requests past their
  required date — spec section 22's full notification trigger list
- Notification Center (`/notifications`) — paginated, filterable by
  category and read/unread, mark-one/mark-all-read; a bell icon with an
  unread badge and a 5-item preview dropdown now lives in the top navbar
  on every page
- Global Search (`/search`) — one query box (also in the top navbar) that
  searches Documents, Tasks, Correspondence, Instructions, Procurement,
  Meetings, Activities, Users and Teams in a single pass, each section only
  shown if the logged-in user actually has permission to view that module
- Admin **Audit Trail** viewer (`/admin/audit-log`) — filterable by action,
  record type and user, reading the same `AuditLog` table every module has
  been writing to since Phase 1
- Executive Dashboard upgrade: new KPI cards (total/pending purchase
  requests, completed purchases, upcoming activities), a full filter bar
  (Cooperative Day year, department, team, task status, responsible
  person), Chart.js charts for task completion, procurement status,
  document status, activities by team, tasks by team, and year-over-year
  task-completion progress, plus an Upcoming Activities panel alongside the
  existing Upcoming Meetings panel

**Phase 8 — Annual Reports, PDF/Excel Export, Year Comparison**
- `AnnualReport` model: one living narrative record per Cooperative Day
  year (Executive Summary, Key Achievements, Challenges, Lessons Learned,
  Recommendations, Draft/Published status, prepared-by + published-at).
  Every *quantitative* figure on the report (tasks, documents, procurement,
  instructions, meetings, decisions, activities, communication, staff
  participation...) is deliberately **not** stored here — it is computed
  live every time the report is opened (`app/reports/services.py`), so a
  report always reflects the current state of the year's records even
  after it has been marked Published
- **View online** (`/reports/<event_id>`): full report page — event info,
  participation, task/document/procurement/instruction/meeting/activity/
  communication stat cards, Chart.js breakdowns, team & staff participation
  lists, a "Photos & Supporting Documents" panel (pulls in Document rows of
  type Photo/Video for that year), and the narrative sections
- **Edit narrative** (`/reports/<event_id>/edit`, gated by
  `generate_reports`) — write achievements/challenges/lessons
  learned/recommendations and mark the report Draft or Published
- **Download as PDF** (`/reports/<event_id>/pdf`) — built with ReportLab
  (`app/reports/exporters.py`): branded cover section, full stat tables,
  and the narrative report on its own page; every download is written to
  the audit trail
- **Export to Excel** (`/reports/<event_id>/excel`) — built with openpyxl:
  a Summary sheet (event info + every headline figure + narrative text)
  plus one breakdown sheet per module (Tasks/Documents/Procurement/
  Activities/Instructions by status, Communication by type, and a Staff
  Participation roster)
- **Year Comparison** (`/reports/compare`) — pick any set of Cooperative
  Day years with checkboxes; get a side-by-side metrics table (teams,
  staff, activities, tasks completed/overdue, documents, procurement,
  instructions, meetings, decisions, communication items), two Chart.js
  comparison charts, a per-year mini-card (challenges/lessons learned at a
  glance), and its own Excel export
  (`/reports/compare/excel?years=<id>,<id>,...`)
- A "Reporting & Analytics" section is now in the sidebar
  (`Annual Reports` / `Year Comparison`, shown only to users with
  `view_reports`), and the Cooperative Day detail page links straight into
  that year's report
- No new permissions were needed — `view_reports` and `generate_reports`
  (seeded since Phase 1) now gate real routes instead of being unused

This drop is the complete **Phase 1–8** build per the spec. What remains is
Phase 9 (security review / testing / performance / deployment hardening).

## Project structure

```
coopbank_cooperative_day/
├── app/
│   ├── __init__.py             # application factory
│   ├── extensions.py           # db, login_manager, migrate, csrf
│   ├── models/                 # User, Role, Permission, Department,
│   │                           # CooperativeDay, Team, TeamMember,
│   │                           # Task, TaskComment,
│   │                           # Instruction, Decision,
│   │                           # Meeting, MeetingParticipant, ActionPoint,
│   │                           # Document, DocumentVersion, Correspondence,
│   │                           # Supplier, ProcurementRequest, ProcurementItem,
│   │                           # Material, Activity, ActivityParticipant,
│   │                           # Communication, AuditLog, AnnualReport
│   ├── auth/                   # login/logout/profile/change-password
│   ├── admin/                  # users, roles & permissions, departments
│   ├── events/                 # Cooperative Day CRUD
│   ├── teams/                  # Teams & team members
│   ├── tasks/                  # Task CRUD, comments, quick status
│   ├── instructions/           # Instructions + Decision register
│   ├── meetings/                # Meetings, participants, action points
│   ├── documents/               # Document upload/versions/search/download
│   ├── correspondence/          # Incoming/outgoing correspondence log
│   ├── procurement/              # Purchase requests, items, suppliers, materials
│   ├── activities/                # Event activity schedule + participants
│   ├── communication/             # Comms/media items, approval workflow, attachment
│   ├── main/                     # dashboard
│   ├── utils/                     # decorators (permission_required, role_required),
│   │                               # audit helper, file-security helpers
│   ├── templates/
│   └── static/
├── migrations/                    # created by `flask db init`
├── tests/
├── uploads/                       # local file storage (configurable)
│   └── documents/<year_id>/       # per-year document storage, UUID filenames
├── config.py
├── run.py
├── seed.py                        # creates permissions, roles, departments, super admin
├── requirements.txt
├── .env.example
└── .gitignore
```

## Getting started (local, SQLite)

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env             # then edit SECRET_KEY etc.

# Initialize the database
flask --app run.py db init
flask --app run.py db migrate -m "Phases 1-7 schema"
flask --app run.py db upgrade

# Seed permissions, roles, departments, and the first SUPER ADMIN account
python seed.py

# Run
python run.py
```

> If you already ran a previous phase's migration, just generate a new
> migration for the new tables instead of re-running `db init`:
> `flask --app run.py db migrate -m "Add notifications table"`
> then `flask --app run.py db upgrade`.

Then open http://localhost:5000 and log in with the username/password set
in `.env` (`SEED_ADMIN_USERNAME` / `SEED_ADMIN_PASSWORD`, default
`superadmin` / `ChangeMe123!` — **change this immediately** in a real
deployment).

## Switching to PostgreSQL (production)

Set `DATABASE_URL` in `.env`, e.g.:

```
DATABASE_URL=postgresql://user:password@host:5432/coopbank_coopday
```

Then run the same `flask db upgrade` and `python seed.py` steps against
that database.

## Roles seeded out of the box

SUPER ADMIN (full access, bypasses all permission checks), ADMIN, EVENT
COORDINATOR, TEAM LEADER, TEAM MEMBER, FINANCE, PROCUREMENT, DOCUMENT
OFFICER, VIEWER. Administrators can create additional roles and assign any
combination of permissions from **Admin → Roles & Permissions** — role
behavior is driven entirely by attached permissions, not by role name.

New permissions added in this drop: `view_activities`, `manage_activities`,
`view_communication`, `manage_communication`, `approve_communication`
(Phase 5's `manage_suppliers`, `manage_materials` and the earlier phases'
permissions remain unchanged).

## Security notes already in place

- Passwords hashed with Werkzeug (`generate_password_hash`)
- CSRF protection on all forms (Flask-WTF)
- Every route is guarded by `@permission_required(...)`
- No secrets hard-coded — everything sensitive comes from `.env`
- File uploads validated against an extension allow-list
  (`app/utils/files.py`) and saved under a random UUID filename — the
  original filename and the on-disk path are never exposed in a URL
- Every document download is written to the audit log with who, what
  version, and when
- Historical `CooperativeDay` records are archived (status → Cancelled),
  never hard-deleted

## Testing this drop yourself

```bash
python seed.py
python run.py
```

Log in, create a Cooperative Day (if you don't already have one), then:
1. **Tasks** → New Task
2. **Meetings** → New Meeting → open it → add an Action Point → **Promote to Task**
   (confirms the action-point-to-task workflow)
3. **Documents** → Upload Document (pick any small file) → open it → Upload
   New Version → Approve (confirms versioning + approval + download logging)
4. **Correspondence** → Log Correspondence, then move it through its
   lifecycle buttons on the detail page
5. **Suppliers** → New Supplier
6. **Purchase Requests** → New Request → open it → add a line item → walk
   it through the workflow buttons (Draft → Submitted → Approved →
   Procurement → Ordered → Delivered → Completed) and confirm the delivery
   date/inspector auto-fill and the items total update
7. **Materials & Assets** → New Material → confirm the shortfall column and
   status buttons on the detail page
8. **Activities** → New Activity → open it → add a participant → mark
   attended → walk the status buttons (Planned → Confirmed → In Progress →
   Completed)
9. **Communication & Media** → New Item → attach a small file → confirm the
   download works → walk the status buttons → **Approve** it (confirms the
   separate delivery-status vs. approval-status workflow)
10. **Open a Cooperative Day** (Cooperative Days → pick a year) → confirm
    the new stat cards (Tasks/Activities/Media/Documents) and the
    "Upcoming Activities" panel reflect what you just created
11. **Dashboard** → confirm the task/instruction/document counters and the
   upcoming-meetings list reflect what you just created

## Next phases

Phase 8 (Annual Reports, PDF/Excel export, Year-over-year comparison
dashboard) is the natural next drop — say the word and we'll continue from
here.
