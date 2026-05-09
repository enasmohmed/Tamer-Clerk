"""
Demo seed for Transformation Workspace only:
ProjectTrackerItem (planned/actual hours, dates, phases) + PortfolioRaidItem.

Safe cleanup: rows are tagged with [TW_SEED] in remarks; use --clear to remove them.
"""

from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

TW_MARKER = "[TW_SEED]"


class Command(BaseCommand):
    help = (
        "Insert sample Project Tracker + Portfolio RAID rows for the Transformation Workspace tab. "
        "Does not touch other models. Use --clear to remove seed rows (remarks contain [TW_SEED])."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete seed rows only (ProjectTrackerItem where remarks contain [TW_SEED]).",
        )

    def handle(self, *args, **options):
        from dashboard.models import PortfolioRaidItem, ProjectTrackerItem

        if options["clear"]:
            deleted_p = ProjectTrackerItem.objects.filter(
                remarks__contains=TW_MARKER
            ).delete()
            # CASCADE removes PortfolioRaidItem for those projects
            self.stdout.write(
                self.style.WARNING(
                    f"Cleared seed Project Tracker rows ({deleted_p}). Related RAID rows removed by CASCADE."
                )
            )
            return

        if ProjectTrackerItem.objects.filter(remarks__contains=TW_MARKER).exists():
            self.stdout.write(
                self.style.ERROR(
                    "Seed data already exists (remarks contain [TW_SEED]). "
                    "Run: python manage.py seed_transformation_workspace --clear"
                )
            )
            return

        today = date.today()

        def td(days: int) -> date:
            return today + timedelta(days=days)

        # Seven projects: six active + one completed (register diversity)
        specs = [
            # 0 — on track SPI/CPI
            {
                "description": "North Region — Omnichannel rollout",
                "project_code": "LOG-001",
                "project_lead": "Sara Ahmed",
                "person_name": "Sara Ahmed",
                "register_status": "on_track",
                "company": "Retail Ops",
                "department": "PMO",
                "project_type": "idea",
                "start_date": td(-50),
                "end_date": td(100),
                "brainstorming_status": "done",
                "execution_status": "working_on_it",
                "test_deadline_status": "working_on_it",
                "launch_status": "",
                "planned_hours": Decimal("320.00"),
                "actual_hours": Decimal("285.00"),
                "last_status_update": td(-3),
                "remarks": f"Pilot stores; RAID tracked.\n{TW_MARKER}",
                "display_order": 10,
            },
            # 1 — delayed / past deadline
            {
                "description": "WMS Phase 2 — Inventory sync",
                "project_code": "LOG-002",
                "project_lead": "Omar Hassan",
                "person_name": "Omar Hassan",
                "register_status": "delayed",
                "company": "Supply Chain",
                "department": "IT",
                "project_type": "automation",
                "start_date": td(-120),
                "end_date": td(-12),
                "brainstorming_status": "done",
                "execution_status": "working_on_it",
                "test_deadline_status": "working_on_it",
                "launch_status": "",
                "planned_hours": Decimal("900.00"),
                "actual_hours": Decimal("1040.00"),
                "last_status_update": td(-18),
                "remarks": f"Deadline passed; recovery plan.\n{TW_MARKER}",
                "display_order": 20,
            },
            # 2 — low SPI vs timeline (behind planned %)
            {
                "description": "Customer Data Platform",
                "project_code": "LOG-003",
                "project_lead": "Layla Farid",
                "person_name": "Layla Farid",
                "register_status": "at_risk",
                "company": "Analytics",
                "department": "Data",
                "project_type": "idea",
                "start_date": td(-90),
                "end_date": td(30),
                "brainstorming_status": "done",
                "execution_status": "stuck",
                "test_deadline_status": "",
                "launch_status": "",
                "planned_hours": Decimal("500.00"),
                "actual_hours": Decimal("520.00"),
                "last_status_update": td(-25),
                "remarks": f"Ingestion blockers.\n{TW_MARKER}",
                "display_order": 30,
            },
            # 3 — CPI < 1 (actual effort >> planned)
            {
                "description": "Mobile crew app — field tasks",
                "project_code": "LOG-004",
                "project_lead": "Karim Nasser",
                "person_name": "Karim Nasser",
                "register_status": "blocked",
                "company": "Digital",
                "department": "Product",
                "project_type": "automation",
                "start_date": td(-35),
                "end_date": td(60),
                "brainstorming_status": "done",
                "execution_status": "done",
                "test_deadline_status": "working_on_it",
                "launch_status": "",
                "planned_hours": Decimal("160.00"),
                "actual_hours": Decimal("245.00"),
                "last_status_update": td(-5),
                "remarks": f"Scope creep on offline mode.\n{TW_MARKER}",
                "display_order": 40,
            },
            # 4 — healthy updates / medium risk
            {
                "description": "API Gateway hardening",
                "project_code": "LOG-005",
                "project_lead": "Mona Selim",
                "person_name": "Mona Selim",
                "register_status": "on_track",
                "company": "Infrastructure",
                "department": "Security",
                "project_type": "automation",
                "start_date": td(-24),
                "end_date": td(70),
                "brainstorming_status": "done",
                "execution_status": "working_on_it",
                "test_deadline_status": "",
                "launch_status": "",
                "planned_hours": Decimal("210.00"),
                "actual_hours": Decimal("195.00"),
                "last_status_update": td(-1),
                "remarks": f"Rate limits & auth.\n{TW_MARKER}",
                "display_order": 50,
            },
            # 5 — started this quarter (for footer hint)
            {
                "description": "HR self-service portal — MVP",
                "project_code": "LOG-006",
                "project_lead": "Youssef Ali",
                "person_name": "Youssef Ali",
                "register_status": "on_track",
                "company": "HR",
                "department": "People Tech",
                "project_type": "idea",
                "start_date": td(-21),
                "end_date": td(120),
                "brainstorming_status": "working_on_it",
                "execution_status": "",
                "test_deadline_status": "",
                "launch_status": "",
                "planned_hours": Decimal("400.00"),
                "actual_hours": Decimal("110.00"),
                "last_status_update": td(-2),
                "remarks": f"Kickoff this quarter.\n{TW_MARKER}",
                "display_order": 60,
            },
            # 6 — completed (not counted as active)
            {
                "description": "Legacy POS decommission",
                "project_code": "LOG-007",
                "project_lead": "Huda Kamal",
                "person_name": "Huda Kamal",
                "register_status": "approved",
                "company": "Retail Ops",
                "department": "PMO",
                "project_type": "idea",
                "start_date": td(-400),
                "end_date": td(-30),
                "brainstorming_status": "done",
                "execution_status": "done",
                "test_deadline_status": "done",
                "launch_status": "done",
                "planned_hours": Decimal("120.00"),
                "actual_hours": Decimal("118.00"),
                "last_status_update": td(-40),
                "remarks": f"Closed — archive.\n{TW_MARKER}",
                "display_order": 70,
            },
        ]

        # RAID rows: (index into specs before DB ids), payload
        raid_plan = [
            (0, "risk", "Carrier integration SLA slip", "open", "critical", 1),
            (0, "issue", "UAT environment instability", "mitigated", "high", 2),
            (1, "risk", "Warehouse cutover weekend freeze", "open", "critical", 1),
            (1, "dependency", "Waiting on vendor API keys", "mitigated", "medium", 2),
            (1, "issue", "Duplicate SKU mapping", "open", "medium", 3),
            (2, "assumption", "Source system refresh nightly", "open", "low", 1),
            (2, "risk", "PII classification delays", "open", "high", 2),
            (2, "dependency", "Marketing consent export API", "mitigated", "medium", 3),
            (3, "issue", "App store review backlog", "mitigated", "medium", 1),
            (3, "dependency", "Push notification cert renewal", "open", "low", 2),
            (4, "risk", "Pen-test findings backlog", "open", "critical", 1),
            (4, "issue", "JWT rotation playbook", "mitigated", "medium", 2),
            (4, "dependency", "OCSP stapling enablement", "open", "low", 3),
            (5, "assumption", "SSO scope for MVP", "open", "medium", 1),
            (5, "issue", "Arabic payroll labels review", "mitigated", "low", 2),
            # Closed — should not count as open RAID
            (5, "risk", "Budget approval (FY)", "closed", "low", 3),
            (6, "issue", "Final handset return", "closed", "low", 1),
        ]

        with transaction.atomic():
            projects = []
            for s in specs:
                projects.append(ProjectTrackerItem.objects.create(**s))

            raid_count = 0
            for proj_idx, category, title, status, severity, disp in raid_plan:
                PortfolioRaidItem.objects.create(
                    project=projects[proj_idx],
                    category=category,
                    title=title,
                    status=status,
                    severity=severity,
                    display_order=disp,
                )
                raid_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded Transformation Workspace demo: {len(projects)} projects, {raid_count} RAID rows "
                f"(marker {TW_MARKER} in remarks — manage.py seed_transformation_workspace --clear to remove)."
            )
        )
