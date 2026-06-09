# context_helpers.py — Functions to merge model data (theme, regions, warehouses) into dashboard context


def get_dashboard_theme_dict():
    """Returns a key -> value dictionary from DashboardTheme for template use (dashboard colors)."""
    try:
        from .models import DashboardTheme, DEFAULT_THEME_COLORS

        qs = DashboardTheme.objects.all()
        theme_dict = {t.key: t.value or "" for t in qs}

        # Fill in defaults for any missing keys
        for key, value, description, category in DEFAULT_THEME_COLORS:
            if key not in theme_dict or not theme_dict[key]:
                theme_dict[key] = value

        return theme_dict
    except Exception:
        # Return defaults if database error
        from .models import DEFAULT_THEME_COLORS

        return {key: value for key, value, desc, cat in DEFAULT_THEME_COLORS}


def get_regions_table_from_db():
    """Returns a list of dictionaries from Region model for returns_region_table."""
    try:
        from .models import Region

        rows = Region.objects.all()
        return [
            {
                "region": r.name,
                "skus": r.skus,
                "available": r.available,
                "utilization_pct": r.utilization_pct,
            }
            for r in rows
        ]
    except Exception:
        return []


def get_warehouse_metrics_table_from_db():
    """Returns a list of dictionaries from WarehouseMetric model for inventory_warehouse_table."""
    try:
        from .models import WarehouseMetric

        rows = WarehouseMetric.objects.all()
        return [
            {
                "warehouse": r.name or (r.warehouse.name if r.warehouse else ""),
                "skus": r.skus,
                "available_space": r.available_space,
                "utilization_pct": r.utilization_pct,
            }
            for r in rows
        ]
    except Exception:
        return []


def get_phases_sections_list():
    """
    Returns a list of Phase sections for Plan (30/60/90 DAYS) ribbons.
    Uses days_number and days_label from the model when set; else falls back to parsing title.
    """
    try:
        from .models import PhaseSection

        sections = PhaseSection.objects.filter(is_active=True).prefetch_related(
            "points"
        )
        result = []
        for s in sections:
            if s.days_number is not None:
                display_number = str(s.days_number)
                display_label = (s.days_label or "DAYS").strip() or "DAYS"
            else:
                title = (s.title or "").strip()
                parts = title.split(None, 1)
                if parts and parts[0].isdigit():
                    display_number = parts[0]
                    display_label = parts[1].strip() if len(parts) > 1 else "DAYS"
                else:
                    display_number = ""
                    display_label = title or "DAYS"
            result.append({
                "id": s.id,
                "title": s.title,
                "display_number": display_number,
                "display_label": display_label,
                "points": [p.text for p in s.points.all()],
            })
        return result
    except Exception:
        return []


EO_KPI_CARD_ORDER = (
    "total_projects",
    "on_track",
    "at_risk",
    "spi",
)

HIDDEN_EO_KPI_KEYS = frozenset({"cpi", "open_risks", "time_saved"})


def get_executive_overview_kpi_cards(project_type=None, workspace_metrics=None):
    """
    Executive Overview KPI cards (top strip).
    If admin didn't add any rows yet, return a reasonable default set.
    """
    defaults = [
        {
            "key": "total_projects",
            "title": "TOTAL PROJECTS",
            "value_text": "—",
            "subtitle": "Across portfolio",
            "footer": "Connected from Admin / data model",
            "accent": "cyan",
        },
        {
            "key": "on_track",
            "title": "ON TRACK",
            "value_text": "—",
            "subtitle": "Projects healthy",
            "footer": "Improving vs last month",
            "accent": "green",
        },
        {
            "key": "at_risk",
            "title": "AT RISK",
            "value_text": "—",
            "subtitle": "Needs attention",
            "footer": "Review top drivers",
            "accent": "amber",
        },
        {
            "key": "spi",
            "title": "SPI",
            "value_text": "—",
            "subtitle": "Schedule performance",
            "footer": "6‑month view",
            "accent": "cyan",
        },
        {
            "key": "cpi",
            "title": "CPI",
            "value_text": "—",
            "subtitle": "Cost performance",
            "footer": "6‑month view",
            "accent": "purple",
        },
        {
            "key": "open_risks",
            "title": "OPEN RISKS",
            "value_text": "—",
            "subtitle": "Across portfolio",
            "footer": "Prioritize mitigations",
            "accent": "red",
        },
    ]

    def _apply_computed_to_card(card, computed_values):
        key = (card.get("key") or "").strip().lower()
        if key in computed_values and (card.get("value_text") in ("—", "", None)):
            card["value_text"] = computed_values[key]
        return card

    def _card_from_default(tpl, computed_values):
        return _apply_computed_to_card(dict(tpl), computed_values)

    def _merge_eo_kpi_cards(existing, computed_values):
        """Ensure all standard KPI cards appear in canonical order."""
        by_key = {
            (r.get("key") or "").strip().lower(): r
            for r in (existing or [])
            if (r.get("key") or "").strip().lower() not in HIDDEN_EO_KPI_KEYS
        }
        merged = []
        for key in EO_KPI_CARD_ORDER:
            if key in by_key:
                merged.append(by_key[key])
                continue
            tpl = next((d for d in defaults if d.get("key") == key), None)
            if tpl:
                merged.append(_card_from_default(tpl, computed_values))
        return merged

    def _compute_defaults():
        """
        Compute live values from Transformation Workspace data models.
        Uses workspace_metrics when provided to avoid double work.
        """
        try:
            from .models import PortfolioRaidItem, ProjectTrackerItem

            qs = ProjectTrackerItem.objects.all()
            if project_type and project_type in ("idea", "automation"):
                qs = qs.filter(project_type=project_type)
            total_projects = qs.count()
            on_track = qs.filter(register_status="on_track").count()
            at_risk = qs.filter(register_status="at_risk").count()
            # Keep "open risks" aligned with TW meaning (open RAID excluding completed projects)
            open_risks = PortfolioRaidItem.objects.filter(status="open").exclude(
                project__launch_status="done"
            ).count()

            spi = None
            cpi = None
            if workspace_metrics:
                spi = workspace_metrics.get("spi")
                cpi = workspace_metrics.get("cpi")
            return {
                "total_projects": str(total_projects),
                "on_track": str(on_track),
                "at_risk": str(at_risk),
                "open_risks": str(open_risks),
                "spi": f"{spi:.2f}" if isinstance(spi, (int, float)) else "—",
                "cpi": f"{cpi:.2f}" if isinstance(cpi, (int, float)) else "—",
            }
        except Exception:
            return {}

    computed = _compute_defaults()

    try:
        from .models import ExecutiveOverviewKpiCard

        rows = list(
            ExecutiveOverviewKpiCard.objects.filter(is_active=True).order_by(
                "display_order", "id"
            )
        )
        if not rows:
            return _merge_eo_kpi_cards(
                [_card_from_default(d, computed) for d in defaults],
                computed,
            )

        result = []
        for r in rows:
            if (r.key or "").strip().lower() in HIDDEN_EO_KPI_KEYS:
                continue
            v = (r.value_text or "").strip() or "—"
            if v in ("—", "-") and r.key in computed and computed[r.key] not in ("", "—", None):
                v = computed[r.key]
            subtitle = r.subtitle or ""
            result.append(
                {
                    "key": r.key,
                    "title": r.title,
                    "value_text": v,
                    "subtitle": subtitle,
                    "footer": r.footer or "",
                    "accent": r.accent or "cyan",
                }
            )
        return _merge_eo_kpi_cards(result, computed)
    except Exception:
        return _merge_eo_kpi_cards(
            [_card_from_default(d, computed) for d in defaults],
            computed,
        )


def get_executive_overview_tw_payload(tw_items, top_n=6):
    """
    Build executive_charts + executive_top_projects from Transformation Workspace `items`.

    TW register rows expose the display title as `name` (not `description`). PMBOK buckets
    come from `pmbok_label` (INITIATING / PLANNING / EXECUTING / MONITORING / CLOSING), not
    from the internal `phase` string (Brainstorming / Development / ...).
    """
    tw_items = tw_items or []
    status_order = [
        ("on_track", "On Track"),
        ("at_risk", "At Risk"),
        ("delayed", "Delayed"),
        ("blocked", "Blocked"),
        ("approved", "Approved"),
    ]
    status_counts = {k: 0 for k, _ in status_order}
    phase_order = [
        ("Initiating", "Initiating"),
        ("Planning", "Planning"),
        ("Executing", "Executing"),
        ("Monitoring", "Monitoring"),
        ("Closing", "Closing"),
    ]
    phase_counts = {k: 0 for k, _ in phase_order}
    pmbok_map = {
        "INITIATING": "Initiating",
        "PLANNING": "Planning",
        "EXECUTING": "Executing",
        "MONITORING": "Monitoring",
        "CLOSING": "Closing",
    }
    category_counts = {}
    for it in tw_items:
        sk = (it.get("register_status_effective") or it.get("register_status") or "").strip()
        if sk in status_counts:
            status_counts[sk] += 1
        pl = (it.get("pmbok_label") or "").strip().upper()
        bucket = pmbok_map.get(pl)
        if bucket:
            phase_counts[bucket] += 1
        cat = (it.get("category_display") or "").strip()
        if cat:
            category_counts[cat] = category_counts.get(cat, 0) + 1

    def _display_name(item):
        n = (item.get("name") or "").strip()
        if n and n != "—":
            return n
        oid = item.get("id")
        return f"Project #{oid}" if oid is not None else "—"

    top_projects = []
    for it in tw_items[:top_n]:
        top_projects.append(
            {
                "name": _display_name(it),
                "progress_pct": int(it.get("progress_pct") or 0),
                "status_display": (
                    (it.get("register_status_display") or "").strip()
                    or (it.get("register_badge_label") or "").strip()
                    or "—"
                ),
                "status_key": (
                    it.get("register_status_effective") or it.get("register_status") or ""
                ).strip(),
            }
        )

    def _pmo_tone_from_row_class(row_class):
        rc = (row_class or "").strip()
        if "tw-pmo-good" in rc:
            return "good"
        if "tw-pmo-bad" in rc:
            return "bad"
        return "warn"

    executive_pmo_health = []
    for it in tw_items[:8]:
        pct = int(it.get("pmo_score_pct") or 0)
        executive_pmo_health.append(
            {
                "name": _display_name(it),
                "log_id": (it.get("log_id") or "").strip(),
                "pmo_score_pct": pct,
                "tone": _pmo_tone_from_row_class(it.get("pmo_row_class")),
            }
        )

    deadline_rows = []
    for it in tw_items:
        if it.get("deadline") is None and it.get("deadline_days_int") is None:
            continue
        days = it.get("deadline_days_int")
        if days is None:
            urgency = "warn"
        elif days < 0:
            urgency = "bad"
        elif days <= 30:
            urgency = "warn"
        else:
            urgency = "good"
        lbl = (it.get("deadline_days_label") or "").strip()
        if not lbl and days is not None:
            lbl = f"{days}d"
        deadline_rows.append(
            {
                "name": _display_name(it),
                "log_id": (it.get("log_id") or "").strip(),
                "due_display": (it.get("deadline_display") or "").strip() or "—",
                "days": days,
                "days_label": lbl or "—",
                "urgency": urgency,
            }
        )
    deadline_rows.sort(
        key=lambda r: (
            r["days"] is None,
            r["days"] if r["days"] is not None else 10**9,
        )
    )
    deadline_rows = deadline_rows[:8]

    def _gantt_status_tone(sk):
        if sk == "on_track":
            return "good"
        if sk in ("delayed", "blocked"):
            return "bad"
        if sk == "at_risk":
            return "warn"
        return "neutral"

    def _fmt_date(d):
        if d is not None and hasattr(d, "strftime"):
            return d.strftime("%b %d, %Y")
        return str(d) if d else ""

    def _gantt_css_num(val):
        """ASCII decimals for CSS calc() (locale-safe, avoids broken positioning)."""
        try:
            v = float(val)
        except (TypeError, ValueError):
            return "0"
        v = max(0.0, min(100.0, v))
        s = f"{v:.8f}".rstrip("0").rstrip(".")
        return s if s else "0"

    gantt_projects = []
    gantt_range_start = ""
    gantt_range_end = ""
    gantt_candidates = []
    for it in tw_items:
        sd = it.get("start_date")
        ed = it.get("deadline")
        if sd is None or ed is None:
            continue
        if not hasattr(sd, "toordinal") or not hasattr(ed, "toordinal"):
            continue
        try:
            if sd > ed:
                sd, ed = ed, sd
        except (TypeError, ValueError):
            continue
        gantt_candidates.append((it, sd, ed))
    gantt_month_ticks = []
    gantt_now_pct = None
    gantt_now_pct_css = None
    month_axis_multi_year = False
    if gantt_candidates:
        from datetime import date as _gantt_date

        t0 = min(c[1] for c in gantt_candidates)
        t1 = max(c[2] for c in gantt_candidates)
        gantt_range_start = _fmt_date(t0)
        gantt_range_end = _fmt_date(t1)
        d0 = t0.date() if hasattr(t0, "date") else t0
        d1 = t1.date() if hasattr(t1, "date") else t1
        # Axis: January of the earliest-start year → last deadline (so labels run JAN…last month with data)
        axis_start = _gantt_date(d0.year, 1, 1)
        span_days = max(1, (d1 - axis_start).days)
        month_axis_multi_year = d1.year > axis_start.year
        _mon_abbr = (
            "",
            "JAN",
            "FEB",
            "MAR",
            "APR",
            "MAY",
            "JUN",
            "JUL",
            "AUG",
            "SEP",
            "OCT",
            "NOV",
            "DEC",
        )
        cur_m = axis_start
        end_m = _gantt_date(d1.year, d1.month, 1)
        while cur_m <= end_m:
            try:
                raw_days = (cur_m - axis_start).days
                lp_raw = max(0.0, min(100.0, 100.0 * raw_days / float(span_days)))
            except (TypeError, ValueError):
                lp_raw = 0.0
            lp = round(lp_raw, 2)
            # If range crosses calendar years, put 'YY on every month so JAN '25 vs JAN '26 is never ambiguous.
            if month_axis_multi_year:
                label = f"{_mon_abbr[cur_m.month]} {cur_m.year % 100:02d}"
            else:
                label = _mon_abbr[cur_m.month]
            gantt_month_ticks.append(
                {"label": label, "left_pct": lp, "left_css": _gantt_css_num(lp_raw)}
            )
            if cur_m.month == 12:
                cur_m = _gantt_date(cur_m.year + 1, 1, 1)
            else:
                cur_m = _gantt_date(cur_m.year, cur_m.month + 1, 1)
        gantt_month_ticks.sort(key=lambda z: (z["left_pct"], z["label"]))
        today = _gantt_date.today()
        if axis_start <= today <= d1:
            try:
                now_raw = max(
                    0.0,
                    min(100.0, 100.0 * (today - axis_start).days / float(span_days)),
                )
                gantt_now_pct = round(now_raw, 2)
                gantt_now_pct_css = _gantt_css_num(now_raw)
            except (TypeError, ValueError):
                gantt_now_pct = None
                gantt_now_pct_css = None
        for it, sd, ed in sorted(gantt_candidates, key=lambda c: c[1])[:12]:
            sk = (it.get("register_status_effective") or it.get("register_status") or "").strip()
            sdn = sd.date() if hasattr(sd, "date") else sd
            edn = ed.date() if hasattr(ed, "date") else ed
            dur = max(1, (edn - sdn).days)
            left_pct_raw = max(
                0.0,
                min(100.0, 100.0 * (sdn - axis_start).days / float(span_days)),
            )
            width_pct_raw = max(
                1.5, min(100.0 - left_pct_raw, 100.0 * dur / float(span_days))
            )
            prio = (it.get("register_priority_display") or "").strip()
            bar_lbl = (it.get("register_badge_label") or "").strip()
            if not bar_lbl:
                bar_lbl = (it.get("register_status_display") or "").strip()
            if len(bar_lbl) > 28:
                bar_lbl = bar_lbl[:27] + "…"
            gantt_projects.append(
                {
                    "name": _display_name(it),
                    "log_id": (it.get("log_id") or "").strip(),
                    "priority_display": prio,
                    "start_display": _fmt_date(sd),
                    "end_display": _fmt_date(ed),
                    "left_pct": round(left_pct_raw, 2),
                    "width_pct": round(width_pct_raw, 2),
                    "left_css": _gantt_css_num(left_pct_raw),
                    "width_css": _gantt_css_num(width_pct_raw),
                    "tone": _gantt_status_tone(sk),
                    "bar_label": bar_lbl,
                }
            )
    executive_gantt = {
        "projects": gantt_projects,
        "range_start": gantt_range_start,
        "range_end": gantt_range_end,
        "month_ticks": gantt_month_ticks,
        "now_pct": gantt_now_pct,
        "month_axis_multi_year": month_axis_multi_year,
        "month_tick_count": max(1, len(gantt_month_ticks)),
    }
    if gantt_now_pct_css is not None:
        executive_gantt["now_pct_css"] = gantt_now_pct_css

    # Budget vs EAC: EAC with BAC normalized to 1.0 per project (from TW EVM snapshot)
    budget_labels = []
    budget_values = []
    for it in tw_items:
        evm = it.get("evm") or {}
        eac = evm.get("eac")
        if eac is None:
            continue
        try:
            ratio = float(eac)
        except (TypeError, ValueError):
            continue
        ratio = round(min(2.5, max(0.0, ratio)), 3)
        _bn = _display_name(it)
        if len(_bn) > 44:
            _bn = _bn[:43] + "…"
        budget_labels.append(_bn)
        budget_values.append(ratio)
    _budget_order = sorted(range(len(budget_values)), key=lambda i: -budget_values[i])
    budget_labels = [budget_labels[i] for i in _budget_order][:10]
    budget_values = [budget_values[i] for i in _budget_order][:10]

    # Risk heat map: 5×5 matrix (prob → columns, impact ↑ rows) + tier colors (UI matches PMO matrix)
    prob_rank = {"High": 4.2, "Medium": 3.0, "Low": 1.8}
    hm_tier = [
        ["medium", "high", "high", "critical", "critical"],
        ["low", "medium", "high", "high", "critical"],
        ["low", "low", "medium", "high", "high"],
        ["low", "low", "low", "medium", "high"],
        ["low", "low", "low", "low", "medium"],
    ]
    hm_matrix = [
        [{"tier": hm_tier[r][c], "items": []} for c in range(5)] for r in range(5)
    ]

    def _risk_cell_code(item):
        lid = (item.get("log_id") or "").strip()
        if lid:
            return lid[:10]
        oid = item.get("id")
        return f"R-{int(oid):03d}" if oid is not None else "R-000"

    for it in tw_items:
        if (it.get("launch_status") or "").strip() == "done":
            continue
        risk = (it.get("risk") or "").strip()
        px = prob_rank.get(risk, 2.6)
        ri = int(it.get("raid_open_impact") or 0)
        py = float(ri) if ri >= 2 else prob_rank.get(risk, 2.2)
        col_idx = max(0, min(4, int(round(float(px))) - 1))
        row_idx = max(0, min(4, 5 - int(round(float(py)))))
        cell = hm_matrix[row_idx][col_idx]
        if len(cell["items"]) < 3:
            cell["items"].append(
                {
                    "code": _risk_cell_code(it),
                    "title": _display_name(it),
                }
            )

    has_risk_hm = any(
        cell["items"] for row in hm_matrix for cell in row
    )

    # Strategic alignment: fixed four objectives; map portfolio labels into buckets
    fixed_strategic = [
        "Cost Optimization",
        "Automation",
        "Compliance",
        "Digital Transformation",
    ]
    strategic_counts = {k: 0 for k in fixed_strategic}

    def _strategic_bucket(raw):
        n = (raw or "").strip().lower()
        if not n:
            return None
        if "cost" in n or "optim" in n or "saving" in n or "reduce cost" in n:
            return "Cost Optimization"
        if "automat" in n or "robot" in n or "rpa" in n:
            return "Automation"
        if "compliance" in n or "regulatory" in n or "audit" in n or "governance" in n:
            return "Compliance"
        if "digital" in n or "transform" in n:
            return "Digital Transformation"
        if "wms" in n or "erp" in n or "warehouse" in n or "integration" in n:
            return "Automation"
        if "security" in n or "cyber" in n:
            return "Compliance"
        return None

    for it in tw_items:
        raw = (it.get("strategic_alignment_display") or "").strip()
        b = _strategic_bucket(raw)
        if b:
            strategic_counts[b] += 1
        else:
            strategic_counts["Digital Transformation"] += 1

    executive_charts = {
        "status": {
            "labels": [lbl for _, lbl in status_order],
            "values": [status_counts[k] for k, _ in status_order],
        },
        "phase": {
            "labels": [lbl for _, lbl in phase_order],
            "values": [phase_counts[k] for k, _ in phase_order],
        },
        "category": {
            "labels": [
                k
                for k, _ in sorted(
                    category_counts.items(), key=lambda kv: (-kv[1], kv[0])
                )
            ][:8],
            "values": [
                v
                for _, v in sorted(
                    category_counts.items(), key=lambda kv: (-kv[1], kv[0])
                )
            ][:8],
            "total": sum(category_counts.values()),
        },
        "budget_eac": {
            "labels": budget_labels,
            "values": budget_values,
        },
        "risk_heatmap": {
            "matrix": hm_matrix,
            "has_data": has_risk_hm,
        },
        "alignment": {
            "labels": fixed_strategic,
            "values": [strategic_counts[k] for k in fixed_strategic],
        },
    }
    return {
        "executive_charts": executive_charts,
        "executive_top_projects": top_projects,
        "executive_pmo_health": executive_pmo_health,
        "executive_deadlines": deadline_rows,
        "executive_gantt": executive_gantt,
    }


def get_executive_charts_fallback_payload():
    """
    Minimal executive_charts when TW payload build fails (template + json_script need keys).
    """
    hm_tier = [
        ["medium", "high", "high", "critical", "critical"],
        ["low", "medium", "high", "high", "critical"],
        ["low", "low", "medium", "high", "high"],
        ["low", "low", "low", "medium", "high"],
        ["low", "low", "low", "low", "medium"],
    ]
    fixed = [
        "Cost Optimization",
        "Automation",
        "Compliance",
        "Digital Transformation",
    ]
    matrix = [[{"tier": hm_tier[r][c], "items": []} for c in range(5)] for r in range(5)]
    return {
        "status": {"labels": [], "values": []},
        "phase": {"labels": [], "values": []},
        "category": {"labels": [], "values": [], "total": 0},
        "budget_eac": {"labels": [], "values": []},
        "risk_heatmap": {"matrix": matrix, "has_data": False},
        "alignment": {"labels": fixed, "values": [0, 0, 0, 0]},
    }


def get_warehouse_overview_list():
    """
    Returns a list of warehouses with business_systems, employee_summary, and phase_statuses
    to display warehouse cards (like the first tabs image).
    """
    try:
        from .models import (
            Warehouse,
            WarehouseBusinessSystem,
            WarehouseEmployeeSummary,
            WarehousePhaseStatus,
        )

        warehouses = Warehouse.objects.all()
        result = []
        from .models import SYSTEM_STATUS_CHOICES

        # System status colors: Pending = orange, Completed = green
        _system_status_colors = {
            "pending_ph1": "#f57c00",
            "ph1_completed": "#2e7d32",
            "pending_ph2": "#f57c00",
            "ph2_completed": "#2e7d32",
        }
        _choice_labels = {
            value: label for value, label in SYSTEM_STATUS_CHOICES if value
        }

        for wh in warehouses:
            biz_systems = []
            for wbs in wh.business_systems.select_related(
                "business_unit", "system"
            ).all():
                val = wbs.system_status or ""
                biz_systems.append(
                    {
                        "business": wbs.business_unit.name,
                        "system": wbs.system_name_override
                        or (wbs.system.name if wbs.system else ""),
                        "status_name": _choice_labels.get(val, ""),
                        "status_color": _system_status_colors.get(val, "#6c757d"),
                    }
                )
            try:
                emp = wh.employee_summary
                # Chart percentage: (Pending or edit count / Allocated count) * 100 — chart shows if Allocated is defined
                chart_pct = None
                if emp.allocated_count is not None:
                    if emp.allocated_count > 0:
                        pending = emp.pending_or_edit_count or 0
                        chart_pct = round((pending / emp.allocated_count) * 100)
                        chart_pct = min(100, max(0, chart_pct))
                    else:
                        chart_pct = 0
                emp_summary = {
                    "allocated_count": emp.allocated_count,
                    "pending_or_edit_count": emp.pending_or_edit_count,
                    "phase_label": emp.phase_label,
                    "phase_status_label": emp.phase_status_label,
                    "employee_chart_pct": chart_pct,
                }
            except WarehouseEmployeeSummary.DoesNotExist:
                emp_summary = {
                    "allocated_count": None,
                    "pending_or_edit_count": None,
                    "phase_label": "",
                    "phase_status_label": "",
                    "employee_chart_pct": None,
                }
            phase_rows = []
            for ps in wh.phase_statuses.select_related(
                "business_unit", "activity", "status"
            ).all():
                phase_rows.append(
                    {
                        "business": ps.business_unit.name,
                        "activity": ps.activity.name,
                        "status_name": ps.status.name if ps.status else "",
                        "status_color": ps.status.color_hex if ps.status else "#6c757d",
                        "start_date": ps.start_date,
                        "end_date": ps.end_date,
                    }
                )
            # Warehouse badge color: if empty or gray, use color based on name (Active → green, Partial → orange)
            status_color = "#6c757d"
            if wh.status:
                hex_val = (wh.status.color_hex or "").strip()
                if hex_val and hex_val.lower() not in ("#6c757d", ""):
                    status_color = hex_val
                else:
                    name_lower = (wh.status.name or "").strip().lower()
                    if "active" in name_lower:
                        status_color = "#2e7d32"
                    elif "partial" in name_lower:
                        status_color = "#f57c00"
                    else:
                        status_color = "#2e7d32"
            result.append(
                {
                    "warehouse": wh,
                    "status_name": wh.status.name if wh.status else "",
                    "status_color": status_color,
                    "business_systems": biz_systems,
                    "employee_summary": emp_summary,
                    "phase_statuses": phase_rows,
                    "phase1_pct": wh.phase1_pct,
                    "phase2_pct": wh.phase2_pct,
                }
            )
        return result
    except Exception:
        return []


def get_clerk_interview_list():
    """Returns a list of Clerk Interview Tracking rows for Project Overview table. Columns: WH, Clerk Name, NATIONALITY, Report Used, Optimization Status, Strength, System Used, Business, Remark."""
    try:
        from .models import ClerkInterviewTracking

        rows = ClerkInterviewTracking.objects.all()
        return [
            {
                "wh": r.wh or "—",
                "clerk_name": r.clerk_name or "—",
                "nationality": r.nationality or "—",
                "optimization_status": r.optimization_status or "—",
                "system_used": r.system_used or "—",
                "business": r.business or "—",
                "remark": r.remark or "—",
            }
            for r in rows
        ]
    except Exception:
        return []


def get_clerk_details_list():
    """Returns list of Clerk Detail (interview profile) rows for Clerk details tab. Sidebar uses dept_name_en."""
    try:
        from .models import ClerkDetail

        rows = ClerkDetail.objects.all()
        return [
            {
                "id": r.id,
                "dept_name_en": r.dept_name_en or "—",
                "department": r.department or "—",
                "company": r.company or "—",
                "business": r.business or "—",
                "account": r.account or "—",
                "mobile": r.mobile or "—",
                "interview_date": r.interview_date or "—",
                "work_details": r.work_details or "",
                "reports_used": r.reports_used or "",
                "system_badge": r.system_badge or "",
            }
            for r in rows
        ]
    except Exception:
        return []


def get_weekly_project_tracker_list():
    """Returns list of Weekly Project Tracker rows for Progress Overview tab."""
    try:
        from .models import WeeklyProjectTrackerRow

        rows = WeeklyProjectTrackerRow.objects.all()
        return [
            {
                "week": r.week,
                "task": r.task,
                "status": r.status,
                "status_display": r.get_status_display(),
                "progress_pct": r.progress_pct,
                "impact": r.impact or "",
            }
            for r in rows
        ]
    except Exception:
        return []


def get_progress_status_list():
    """Returns list of Progress Status rows (Clerk, Account, Remark, Status)."""
    try:
        from .models import ProgressStatus

        rows = ProgressStatus.objects.all()
        return [
            {
                "clerk": r.clerk or "—",
                "account": r.account or "—",
                "remark": r.remark or "—",
                "status": r.status,
                "status_display": r.get_status_display(),
            }
            for r in rows
        ]
    except Exception:
        return []


def get_potential_challenges_list():
    """Returns list of Potential Challenges rows (Date, Challenges, Status, Progress %, Solutions)."""
    try:
        from .models import PotentialChallenge

        rows = PotentialChallenge.objects.all()
        return [
            {
                "date": r.date or "—",
                "challenges": r.challenges or "—",
                "status": r.status,
                "status_display": r.get_status_display(),
                "progress_pct": r.progress_pct,
                "solutions": r.solutions or "—",
            }
            for r in rows
        ]
    except Exception:
        return []


def get_recommendations_list():
    """
    Returns a list of "cards" for Recommendation Overview tab.
    Each card has business, user_name, logo_url (from first item's Custom icon if set), and items.
    Cards are grouped by (business, user_name); two cards per row in the UI.
    """
    try:
        from .models import Recommendation
        from itertools import groupby

        recs = Recommendation.objects.filter(is_active=True).order_by(
            "business", "user_name", "display_order", "id"
        )

        cards = []
        for (business, user_name), group in groupby(
            recs, key=lambda r: (r.business or "", r.user_name or "")
        ):
            items = [
                {
                    "id": r.id,
                    "title": r.title,
                    "description": r.description,
                    "icon_type": r.icon_type,
                    "custom_icon": r.custom_icon.url if r.custom_icon else None,
                    "icon_bg_color": r.icon_bg_color or "#f5f5f0",
                    "display_order": r.display_order,
                }
                for r in group
            ]
            if items:
                # Card header logo: first item's Custom icon (company logo) if set
                logo_url = next((i["custom_icon"] for i in items if i.get("custom_icon")), None)
                cards.append({
                    "business": business or "—",
                    "user_name": user_name or "",
                    "logo_url": logo_url,
                    "items": items,
                })
        return cards
    except Exception as e:
        print(f"[Recommendations] Error: {e}")
        return []


def get_project_tracker_list(project_type=None):
    """
    يعرض كل الأشهر اللي فيها داتا من الأدمن فقط (حتى لو سنة فاتت).
    الترتيب: من الأحدث (فوق) للأقدم (تحت).
    project_type: اختياري — "idea" أو "automation" لفلترة النتائج لكل الأشهر.
    """
    from datetime import date
    from calendar import month_abbr

    try:
        from .models import ProjectTrackerItem

        today = date.today()
        this_year, this_month = today.year, today.month

        def item_to_dict(obj):
            return {
                "id": obj.id,
                "description": obj.description,
                "person_name": obj.person_name,
                "project_type": getattr(obj, "project_type", "") or "",
                "project_type_display": obj.get_project_type_display() if getattr(obj, "project_type", None) else "",
                "company": getattr(obj, "company", "") or "",
                "department": getattr(obj, "department", "") or "",
                "start_date": obj.start_date,
                "start_date_display": obj.start_date.strftime("%b %d"),
                "end_date": obj.end_date,
                "end_date_display": obj.end_date.strftime("%b %d") if obj.end_date else "",
                "brainstorming_status": obj.brainstorming_status or "",
                "execution_status": obj.execution_status or "",
                "launch_status": obj.launch_status or "",
                "test_deadline_status": getattr(obj, "test_deadline_status", "") or "",
                "brainstorming_display": obj.get_brainstorming_status_display() or "",
                "execution_display": obj.get_execution_status_display() or "",
                "launch_display": obj.get_launch_status_display() or "",
                "test_deadline_display": obj.get_test_deadline_status_display() if getattr(obj, "test_deadline_status", None) is not None else "",
                "remarks": getattr(obj, "remarks", "") or "",
            }

        base_qs = ProjectTrackerItem.objects.filter(pmo_register_published=True)
        if project_type and project_type in ("idea", "automation"):
            base_qs = base_qs.filter(project_type=project_type)

        def phase_progress(items, phase_key):
            total = len(items)
            if total == 0:
                return {
                    "done": 0,
                    "working_on_it": 0,
                    "stuck": 0,
                    "empty": 0,
                    "total": 0,
                    "done_pct": 0,
                    "working_on_it_pct": 0,
                    "stuck_pct": 0,
                    "empty_pct": 100,
                }
            done = sum(1 for i in items if i.get(phase_key) == "done")
            working = sum(1 for i in items if i.get(phase_key) == "working_on_it")
            stuck = sum(1 for i in items if i.get(phase_key) == "stuck")
            empty = total - done - working - stuck
            done_pct = round(100 * done / total) if total else 0
            working_pct = round(100 * working / total) if total else 0
            stuck_pct = round(100 * stuck / total) if total else 0
            empty_pct = 100 - done_pct - working_pct - stuck_pct
            if empty_pct < 0:
                empty_pct = 0
            return {
                "done": done,
                "working_on_it": working,
                "stuck": stuck,
                "empty": empty,
                "total": total,
                "done_pct": done_pct,
                "working_on_it_pct": working_pct,
                "stuck_pct": stuck_pct,
                "empty_pct": empty_pct,
            }

        # كل الأشهر المميزة اللي فيها عناصر (من الأدمن)، من الأحدث للأقدم
        distinct_months = list(base_qs.dates("start_date", "month", order="DESC"))
        month_sections = []
        for month_date in distinct_months:
            y, m = month_date.year, month_date.month
            qs = (
                base_qs.filter(start_date__year=y, start_date__month=m)
                .order_by("-start_date", "display_order", "id")
            )
            items = [item_to_dict(o) for o in qs]
            progress = {
                "brainstorming": phase_progress(items, "brainstorming_status"),
                "execution": phase_progress(items, "execution_status"),
                "test_deadline": phase_progress(items, "test_deadline_status"),
                "launch": phase_progress(items, "launch_status"),
            }
            if y == this_year and m == this_month:
                label = "This month"
                css_class = "this-month"
            elif (y == this_year and m == this_month - 1) or (
                y == this_year - 1 and this_month == 1 and m == 12
            ):
                label = "Last month"
                css_class = "last-month"
            else:
                label = f"{month_abbr[m]} {y}"
                css_class = "month-other"
            # نسبة التنفيذ للشهر بناءً على Launch (done = مكتمل)
            launch_progress = progress["launch"]
            launch_done_pct = launch_progress["done_pct"] if launch_progress["total"] else 0
            month_sections.append({
                "label": label,
                "items": items,
                "progress": progress,
                "css_class": css_class,
                "launch_done_pct": launch_done_pct,
                "launch_total": launch_progress["total"],
            })

        this_month = month_sections[0]["items"] if month_sections else []
        last_month = month_sections[1]["items"] if len(month_sections) > 1 else []
        _empty = phase_progress([], "")
        this_month_progress = (
            month_sections[0]["progress"]
            if month_sections
            else {"brainstorming": _empty, "execution": _empty, "launch": _empty}
        )
        last_month_progress = (
            month_sections[1]["progress"]
            if len(month_sections) > 1
            else this_month_progress
        )

        # إجمالي التاب: كم مشروع Launch = Done ونسبتهم من كل المشاريع
        all_items = []
        for sec in month_sections:
            all_items.extend(sec["items"])
        total_all = len(all_items)
        done_all = sum(1 for i in all_items if i.get("launch_status") == "done")
        overall_launch_done_pct = round(100 * done_all / total_all) if total_all else 0

        return {
            "month_sections": month_sections,
            "this_month": this_month,
            "last_month": last_month,
            "this_month_progress": this_month_progress,
            "last_month_progress": last_month_progress,
            "current_project_type": project_type or "",
            "overall_launch_done_count": done_all,
            "overall_launch_total": total_all,
            "overall_launch_done_pct": overall_launch_done_pct,
        }
    except Exception as e:
        import traceback

        traceback.print_exc()

        def _empty_progress():
            return {
                "done": 0,
                "working_on_it": 0,
                "stuck": 0,
                "empty": 0,
                "total": 0,
                "done_pct": 0,
                "working_on_it_pct": 0,
                "stuck_pct": 0,
                "empty_pct": 100,
            }

        _empty = _empty_progress()
        return {
            "month_sections": [],
            "this_month": [],
            "last_month": [],
            "this_month_progress": {
                "brainstorming": _empty,
                "execution": _empty,
                "launch": _empty,
            },
            "last_month_progress": {
                "brainstorming": _empty,
                "execution": _empty,
                "launch": _empty,
            },
            "current_project_type": "",
            "overall_launch_done_count": 0,
            "overall_launch_total": 0,
            "overall_launch_done_pct": 0,
        }


def get_transformation_workspace(project_type=None):
    """
    Transformation Workspace: Project Register + KPIs from ProjectTrackerItem + PortfolioRaidItem (Admin).

    SPI (portfolio): mean of (Actual progress % ÷ Planned progress % from timeline) for active projects.
    CPI (portfolio): mean of (Planned hours ÷ Actual hours) when both set; else productivity ratio vs timeline.
    PMO score: weighted Progress/SPI/CPI/Risk/Updates per active project; card shows portfolio average %.
    """
    try:
        from django.db.models import Prefetch

        from .models import (
            PortfolioRaidItem,
            ProjectProcessStep,
            ProjectRegisterRemark,
            ProjectTrackerItem,
            WorkspaceDepartment,
            WorkspacePortfolioActivity,
            WorkspaceProjectCategory,
            WorkspaceStrategicAlignment,
        )
        from datetime import date, timedelta

        qs = ProjectTrackerItem.objects.select_related(
            "department_ref",
            "register_category",
            "strategic_alignment_ref",
        ).prefetch_related(
            Prefetch(
                "process_steps",
                queryset=ProjectProcessStep.objects.order_by("display_order", "id"),
            ),
            Prefetch(
                "raid_items",
                queryset=PortfolioRaidItem.objects.order_by("display_order", "id"),
            ),
            Prefetch(
                "register_remarks",
                queryset=ProjectRegisterRemark.objects.order_by("display_order", "id"),
            ),
        ).all()
        if project_type and project_type in ("idea", "automation"):
            qs = qs.filter(project_type=project_type)
        qs_all = qs.order_by("-created_at", "-id")
        qs = qs_all.filter(pmo_register_published=True)

        project_details_map = {}

        def remark_field(raw, prefix):
            """Extract value after 'Prefix:' from remarks (Add Project snapshot)."""
            pl = prefix.lower()
            for line in (raw or "").split("\n"):
                s = line.strip()
                if s.lower().startswith(pl):
                    return s.split(":", 1)[1].strip()
            return ""

        def enrich_detail_from_remarks(obj, payload):
            """
            When structured columns are empty, fill from remarks lines written by
            Add Project (same prefixes as project_portfolio_add_project).
            """
            raw = (getattr(obj, "remarks", "") or "").strip()
            if not raw:
                return
            pairs = [
                ("objective_sow", "objective:"),
                ("kpi_success_criteria", "kpi:"),
                ("resources_before_automation", "resources before automation:"),
                ("scope_in", "in scope:"),
                ("scope_out", "out of scope:"),
                ("scope_deliverables", "deliverables:"),
                ("scope_dependencies", "dependencies:"),
            ]
            lines = [ln.strip() for ln in raw.split("\n") if ln.strip()]

            def first_after(prefix):
                pl = prefix.lower()
                for line in lines:
                    if line.lower().startswith(pl):
                        return line.split(":", 1)[1].strip()
                return ""

            for field, prefix in pairs:
                if (payload.get(field) or "").strip():
                    continue
                val = first_after(prefix)
                if val:
                    payload[field] = val

            summ = payload.setdefault("summary", {})
            if not (summ.get("alignment_display") or "").strip():
                v = first_after("strategic alignment:")
                if v:
                    summ["alignment_display"] = v
            if not (summ.get("category_display") or "").strip():
                v = first_after("category:")
                if v:
                    summ["category_display"] = v

            biz = payload.setdefault("biz", {})
            if not (biz.get("sla_improvement") or "").strip():
                v = first_after("sla improvement:")
                if v:
                    biz["sla_improvement"] = v
            if not (biz.get("headcount_impact") or "").strip():
                v = first_after("headcount impact:")
                if v:
                    biz["headcount_impact"] = v
            crd = (biz.get("cost_reduction_pct_display") or "").strip()
            if not crd:
                v = first_after("cost reduction %:")
                if v:
                    biz["cost_reduction_pct_display"] = v.replace("%", "").strip()

        register_lookups = {
            "departments": [
                {"id": d.id, "name": d.name}
                for d in WorkspaceDepartment.objects.filter(is_active=True).order_by(
                    "display_order", "name"
                )
            ],
            "categories": [
                {"id": c.id, "name": c.name}
                for c in WorkspaceProjectCategory.objects.filter(is_active=True).order_by(
                    "display_order", "name"
                )
            ],
            "alignments": [
                {"id": a.id, "name": a.name}
                for a in WorkspaceStrategicAlignment.objects.filter(is_active=True).order_by(
                    "display_order", "name"
                )
            ],
        }

        status_score = {
            "done": 1.0,
            "working_on_it": 0.55,
            "stuck": 0.25,
            "": 0.0,
            None: 0.0,
        }

        def phase_label(val):
            v = (val or "").strip()
            if v == "done":
                return "Done"
            if v == "working_on_it":
                return "Working"
            if v == "stuck":
                return "Stuck"
            return "Not started"

        def calc_progress(item):
            vals = [
                item.brainstorming_status,
                item.execution_status,
                getattr(item, "test_deadline_status", ""),
                item.launch_status,
            ]
            total = sum(status_score.get(v, 0.0) for v in vals)
            return int(round((total / 4.0) * 100))

        def project_progress_pct(item):
            """Use saved % complete when set; otherwise derive from phase statuses."""
            stored = getattr(item, "progress_pct", None)
            if stored is not None:
                try:
                    return max(0, min(100, int(stored)))
                except (TypeError, ValueError):
                    pass
            return calc_progress(item)

        def current_phase(item):
            phases = [
                ("Brainstorming", item.brainstorming_status),
                ("Development", item.execution_status),
                ("Test", getattr(item, "test_deadline_status", "")),
                ("Launch", item.launch_status),
            ]
            for name, val in phases:
                if (val or "") != "done":
                    return name
            return "Completed"

        def risk_level(item):
            vals = [
                item.brainstorming_status,
                item.execution_status,
                getattr(item, "test_deadline_status", ""),
                item.launch_status,
            ]
            vals = [(v or "").strip() for v in vals]
            if "stuck" in vals:
                return "High"
            if "working_on_it" in vals:
                return "Medium"
            if "done" in vals and all(v == "done" for v in vals if v):
                return "Low"
            return "—"

        def register_remarks_payload(obj):
            try:
                rows = obj.register_remarks.all()
                return [
                    {"text": (r.text or "").strip()}
                    for r in rows
                    if (r.text or "").strip()
                ]
            except Exception:
                return []

        def register_risk_display(obj):
            rl = (getattr(obj, "register_risk_level", "") or "").strip()
            if rl in ("Low", "Medium", "High"):
                return rl
            rl = remark_field((getattr(obj, "remarks", "") or ""), "risk level:")
            if rl in ("Low", "Medium", "High"):
                return rl
            return risk_level(obj)

        def planned_progress_pct(obj, today):
            start, end = obj.start_date, obj.end_date
            if not start or not end or end <= start:
                return None
            duration = (end - start).days
            if duration <= 0:
                return None
            elapsed = (today - start).days
            elapsed = max(0, min(duration, elapsed))
            return (elapsed / float(duration)) * 100.0

        def risk_score_numeric(label):
            if label == "High":
                return 40.0
            if label == "Medium":
                return 70.0
            if label == "Low":
                return 100.0
            return 70.0

        def updates_score_numeric(obj, today):
            lu = getattr(obj, "last_status_update", None)
            if lu:
                days = (today - lu).days
                if days <= 7:
                    return 100.0
                if days <= 14:
                    return 70.0
                return 40.0
            return 60.0

        REGISTER_STATUS_BADGE = {
            "on_track": ("ON TRACK", "tw-st-ontrack"),
            "at_risk": ("AT RISK", "tw-st-atrisk"),
            "delayed": ("DELAYED", "tw-st-delayed"),
            "blocked": ("BLOCKED", "tw-st-blocked"),
            "approved": ("APPROVED", "tw-st-approved"),
        }

        PMBOK_PHASE_BADGE = {
            "Brainstorming": ("INITIATING", "tw-pmbok-init"),
            "Development": ("EXECUTING", "tw-pmbok-exec"),
            "Test": ("MONITORING", "tw-pmbok-mon"),
            "Launch": ("EXECUTING", "tw-pmbok-exec"),
            "Completed": ("CLOSING", "tw-pmbok-close"),
        }

        PRIORITY_BADGE_CLASS = {
            "critical": "aq-pri-critical",
            "high": "aq-pri-high",
            "medium": "aq-pri-medium",
            "low": "aq-pri-low",
        }

        def build_pending_approval_entry(obj):
            """Rich card + detail payload for manager Approval Queue (unpublished items)."""
            tday = date.today()
            prog_pct = project_progress_pct(obj)
            planned_pct = planned_progress_pct(obj, tday)
            spi_p = None
            if planned_pct is not None and planned_pct > 1e-6:
                spi_p = min(2.0, max(0.0, float(prog_pct) / float(planned_pct)))
            ph = getattr(obj, "planned_hours", None)
            ah = getattr(obj, "actual_hours", None)
            cpi_p = None
            try:
                if ph is not None and ah is not None and float(ah) > 0:
                    cpi_p = min(2.0, max(0.0, float(ph) / float(ah)))
                elif planned_pct is not None and planned_pct > 1e-6:
                    cpi_p = min(2.0, max(0.0, float(prog_pct) / float(planned_pct)))
            except (TypeError, ValueError, ZeroDivisionError):
                cpi_p = spi_p

            dept_label = "—"
            if getattr(obj, "department_ref_id", None) and obj.department_ref:
                dept_label = obj.department_ref.name
            elif getattr(obj, "department", None):
                dept_label = (obj.department or "").strip() or "—"

            lead = (getattr(obj, "project_lead", "") or "").strip()
            rp = (getattr(obj, "register_priority", "") or "").strip()
            rs_reg = (getattr(obj, "register_status", "") or "").strip()
            rp_disp = obj.get_register_priority_display() if rp else ""
            rs_disp = obj.get_register_status_display() if rs_reg else ""
            rs_eff = rs_reg
            if not rs_eff:
                if obj.end_date and obj.end_date < tday:
                    rs_eff = "delayed"
                elif spi_p is not None and spi_p < 0.85:
                    rs_eff = "at_risk"
                elif risk_level(obj) == "High":
                    rs_eff = "at_risk"
                else:
                    rs_eff = "on_track"

            cat_disp = ""
            if getattr(obj, "register_category_id", None) and obj.register_category:
                cat_disp = obj.register_category.name
            align_disp = ""
            if getattr(obj, "strategic_alignment_ref_id", None) and obj.strategic_alignment_ref:
                align_disp = obj.strategic_alignment_ref.name

            proc_steps = []
            for s in obj.process_steps.all():
                proc_steps.append(
                    {
                        "description": s.description or "",
                        "deadline": s.step_deadline.strftime("%b %d, %Y")
                        if s.step_deadline
                        else "",
                        "owner_name": s.owner_name or "",
                    }
                )
            raid_cat_abbr = {"risk": "R", "issue": "I", "dependency": "D", "assumption": "A"}
            raid_rows = []
            for r in obj.raid_items.all():
                raid_rows.append(
                    {
                        "category": r.get_category_display() if r.category else "",
                        "category_abbr": raid_cat_abbr.get(r.category or "", "?"),
                        "title": r.title or "",
                        "severity": r.get_severity_display() if r.severity else "",
                        "owner_name": r.owner_name or "",
                        "status": r.get_status_display() if r.status else "",
                    }
                )

            pc = (getattr(obj, "project_code", "") or "").strip()
            log_id = pc if pc else f"LOG-{obj.id:03d}"
            pt_disp = (
                obj.get_project_type_display()
                if getattr(obj, "project_type", None)
                else ""
            )
            subtitle_parts = []
            if cat_disp:
                subtitle_parts.append(cat_disp)
            if pt_disp:
                subtitle_parts.append(pt_disp)
            if not subtitle_parts and dept_label and dept_label != "—":
                subtitle_parts.append(dept_label)
            subtitle_line = " · ".join(subtitle_parts) if subtitle_parts else "—"

            phase_nm = current_phase(obj)
            pmbok_label, pmbok_badge_class = PMBOK_PHASE_BADGE.get(
                phase_nm, ("PLANNING", "tw-pmbok-plan")
            )
            reg_badge_label, reg_badge_class = REGISTER_STATUS_BADGE.get(
                rs_eff,
                ((rs_disp.upper() if rs_disp else "—"), "tw-st-none"),
            )
            if rs_eff not in REGISTER_STATUS_BADGE and rs_disp:
                reg_badge_label = rs_disp.upper()

            planned_single = 0.0
            if obj.start_date and obj.end_date and obj.end_date > obj.start_date:
                _dur = (obj.end_date - obj.start_date).days
                _el = (tday - obj.start_date).days
                planned_single = max(0.0, min(1.0, _el / float(_dur)))
            earned_single = prog_pct / 100.0
            penalty_single = 0.0
            if obj.end_date and obj.end_date < tday:
                penalty_single += 0.25
            if "stuck" in [
                (obj.brainstorming_status or "").strip(),
                (obj.execution_status or "").strip(),
                (getattr(obj, "test_deadline_status", "") or "").strip(),
                (obj.launch_status or "").strip(),
            ]:
                penalty_single += 0.20
            ac_single = planned_single * (1.0 + penalty_single)
            spi_u = spi_p if spi_p is not None else (
                earned_single / planned_single if planned_single > 1e-6 else 0.0
            )
            cpi_u = cpi_p if cpi_p is not None else (
                earned_single / ac_single if ac_single > 1e-6 else 0.0
            )
            spi_u = max(0.0, min(2.0, float(spi_u)))
            cpi_u = max(0.0, min(2.0, float(cpi_u)))
            cv_u = earned_single - ac_single
            eac_u = (1.0 / cpi_u) if cpi_u > 1e-6 else 0.0

            lu_dt = getattr(obj, "last_status_update", None)
            days_since_update = None
            if lu_dt:
                days_since_update = (tday - lu_dt).days
            _gov_appr = (getattr(obj, "gov_approval_status", "") or "").strip()

            remarks_txt = (getattr(obj, "remarks", "") or "").strip()
            budget_line = remark_field(remarks_txt, "budget (usd):") or ""

            detail_payload = {
                "objective_sow": getattr(obj, "objective_sow", "") or "",
                "kpi_success_criteria": getattr(obj, "kpi_success_criteria", "") or "",
                "scope_in": getattr(obj, "scope_in", "") or "",
                "scope_out": getattr(obj, "scope_out", "") or "",
                "scope_deliverables": getattr(obj, "scope_deliverables", "") or "",
                "scope_dependencies": getattr(obj, "scope_dependencies", "") or "",
                "process_steps": proc_steps,
                "raid_items": raid_rows,
                "gov": {
                    "submitted_by": getattr(obj, "gov_submitted_by", "") or "",
                    "reviewed_by": getattr(obj, "gov_reviewed_by", "") or "",
                    "approval_status": obj.get_gov_approval_status_display()
                    if _gov_appr
                    else "",
                    "stakeholders": getattr(obj, "gov_stakeholders", "") or "",
                    "operational_impact": getattr(obj, "gov_operational_impact", "") or "",
                    "assumptions_constraints": getattr(obj, "gov_assumptions_constraints", "")
                    or "",
                },
                "evm": {
                    "pv": round(planned_single, 3),
                    "ev": round(earned_single, 3),
                    "ac": round(ac_single, 3),
                    "cv": round(cv_u, 3),
                    "spi": round(spi_u, 2),
                    "cpi": round(cpi_u, 2),
                    "eac": round(eac_u, 2),
                },
                "summary": {
                    "log_id": log_id,
                    "pmbok_label": pmbok_label,
                    "register_badge_label": reg_badge_label,
                    "priority_display": rp_disp,
                    "category_display": cat_disp,
                    "alignment_display": align_disp,
                    "last_update_display": lu_dt.strftime("%b %d, %Y") if lu_dt else "",
                    "days_since_update": days_since_update,
                    "start_date_display": obj.start_date.strftime("%b %d, %Y")
                    if getattr(obj, "start_date", None)
                    else "",
                },
                "remarks": remarks_txt,
                "register_remarks": register_remarks_payload(obj),
                "company": (getattr(obj, "company", "") or "").strip(),
            }
            detail_payload.update(automation_fields_payload(obj))
            enrich_detail_from_remarks(obj, detail_payload)

            def _clip(s, n):
                t = (s or "").strip()
                return t if len(t) <= n else t[: n - 1].rstrip() + "…"

            meta_bits = []
            if cat_disp:
                meta_bits.append(cat_disp)
            if dept_label and dept_label != "—":
                meta_bits.append(dept_label)
            meta_bits.append("PM: " + (lead or "—"))
            if budget_line:
                meta_bits.append(budget_line)
            meta_line = " · ".join(meta_bits)

            card = {
                "id": obj.id,
                "name": obj.description or "—",
                "log_id": log_id,
                "project_lead": lead or "—",
                "company": (getattr(obj, "company", "") or "").strip(),
                "progress_pct": prog_pct,
                "deadline_display": obj.end_date.strftime("%b %d, %Y")
                if obj.end_date
                else "—",
                "deadline_iso": obj.end_date.isoformat() if obj.end_date else "",
                "created_display": obj.created_at.strftime("%b %d, %Y")
                if getattr(obj, "created_at", None)
                else "—",
                "subtitle_line": subtitle_line,
                "meta_line": meta_line,
                "register_badge_label": reg_badge_label,
                "register_badge_class": reg_badge_class,
                "pmbok_label": pmbok_label,
                "pmbok_badge_class": pmbok_badge_class,
                "priority_display": rp_disp,
                "priority_badge_class": PRIORITY_BADGE_CLASS.get(rp, "aq-pri-medium"),
                "project_type": (obj.project_type or "").strip(),
                "project_type_display": pt_disp or "—",
                "objective_preview": _clip(detail_payload.get("objective_sow", ""), 220),
                "kpi_preview": _clip(detail_payload.get("kpi_success_criteria", ""), 160),
                "scope_in_preview": _clip(detail_payload.get("scope_in", ""), 140),
                "scope_out_preview": _clip(detail_payload.get("scope_out", ""), 140),
                "detail": detail_payload,
            }
            return card

        items = []
        today = date.today()
        mq = (today.month - 1) // 3
        quarter_start_month = mq * 3 + 1
        quarter_start = date(today.year, quarter_start_month, 1)

        pv_sum = ev_sum = ac_sum = 0.0
        active_count = 0
        started_this_quarter = 0
        delayed_at_risk_count = 0
        spi_vals = []
        cpi_vals = []
        pmo_scores = []

        for obj in qs:
            is_completed = (obj.launch_status or "").strip() == "done"
            is_active = not is_completed
            prog_pct = project_progress_pct(obj)
            planned_pct = planned_progress_pct(obj, today)

            spi_p = None
            if planned_pct is not None and planned_pct > 1e-6:
                spi_p = min(2.0, max(0.0, float(prog_pct) / float(planned_pct)))

            ph = getattr(obj, "planned_hours", None)
            ah = getattr(obj, "actual_hours", None)
            cpi_p = None
            try:
                if ph is not None and ah is not None and float(ah) > 0:
                    cpi_p = min(2.0, max(0.0, float(ph) / float(ah)))
                elif planned_pct is not None and planned_pct > 1e-6:
                    cpi_p = min(2.0, max(0.0, float(prog_pct) / float(planned_pct)))
            except (TypeError, ValueError, ZeroDivisionError):
                cpi_p = spi_p

            rl = risk_level(obj)
            rs_num = risk_score_numeric(rl)
            us = updates_score_numeric(obj, today)
            spi_s = min(100.0, spi_p * 100.0) if spi_p is not None else 70.0
            cpi_s = min(100.0, cpi_p * 100.0) if cpi_p is not None else 70.0
            pmo_val = (
                0.35 * float(prog_pct)
                + 0.25 * spi_s
                + 0.20 * cpi_s
                + 0.10 * rs_num
                + 0.10 * us
            )
            pmo_score_pct = int(round(max(0.0, min(100.0, pmo_val))))

            if is_active:
                active_count += 1
                if obj.start_date and obj.start_date >= quarter_start:
                    started_this_quarter += 1
                if spi_p is not None:
                    spi_vals.append(spi_p)
                if cpi_p is not None:
                    cpi_vals.append(cpi_p)

                pmo_scores.append(pmo_val)

                is_delayed = False
                if obj.end_date and obj.end_date < today:
                    is_delayed = True
                elif spi_p is not None and spi_p < 0.85:
                    is_delayed = True
                if is_delayed:
                    delayed_at_risk_count += 1

            dept_label = "—"
            if getattr(obj, "department_ref_id", None) and obj.department_ref:
                dept_label = obj.department_ref.name
            elif getattr(obj, "department", None):
                dept_label = (obj.department or "").strip() or "—"

            lead = (getattr(obj, "project_lead", "") or "").strip()
            secondary = (obj.person_name or "").strip()
            owner_show = lead or secondary or "—"

            rp = (getattr(obj, "register_priority", "") or "").strip()
            rs_reg = (getattr(obj, "register_status", "") or "").strip()
            rp_disp = obj.get_register_priority_display() if rp else ""
            rs_disp = obj.get_register_status_display() if rs_reg else ""

            rs_eff = rs_reg
            if not rs_eff:
                if obj.end_date and obj.end_date < today:
                    rs_eff = "delayed"
                elif spi_p is not None and spi_p < 0.85:
                    rs_eff = "at_risk"
                elif risk_level(obj) == "High":
                    rs_eff = "at_risk"
                else:
                    rs_eff = "on_track"

            cat_disp = ""
            if getattr(obj, "register_category_id", None) and obj.register_category:
                cat_disp = obj.register_category.name

            align_disp = ""
            if getattr(obj, "strategic_alignment_ref_id", None) and obj.strategic_alignment_ref:
                align_disp = obj.strategic_alignment_ref.name

            cr = getattr(obj, "cost_reduction_pct", None)
            cr_disp = ""
            if cr is not None:
                cr_disp = str(cr)

            proc_steps = []
            for s in obj.process_steps.all():
                proc_steps.append(
                    {
                        "description": s.description or "",
                        "deadline": s.step_deadline.strftime("%b %d, %Y")
                        if s.step_deadline
                        else "",
                        "deadline_iso": s.step_deadline.isoformat()
                        if s.step_deadline
                        else "",
                        "owner_name": s.owner_name or "",
                    }
                )
            raid_cat_abbr = {"risk": "R", "issue": "I", "dependency": "D", "assumption": "A"}
            raid_rows = []
            for r in obj.raid_items.all():
                raid_rows.append(
                    {
                        "category": r.get_category_display() if r.category else "",
                        "category_code": (r.category or "").strip(),
                        "category_abbr": raid_cat_abbr.get(r.category or "", "?"),
                        "title": r.title or "",
                        "severity": r.get_severity_display() if r.severity else "",
                        "severity_code": (r.severity or "").strip(),
                        "owner_name": r.owner_name or "",
                        "status": r.get_status_display() if r.status else "",
                        "status_code": (r.status or "").strip(),
                    }
                )

            _sev_rank_open = {"critical": 5, "high": 4, "medium": 3, "low": 2}
            _raid_open_impact = 0
            _open_raid_count = 0
            for _r in raid_rows:
                if (_r.get("status_code") or "").strip().lower() != "open":
                    continue
                _open_raid_count += 1
                _sc = (_r.get("severity_code") or "").strip().lower()
                _raid_open_impact = max(
                    _raid_open_impact, _sev_rank_open.get(_sc, 0)
                )

            pc = (getattr(obj, "project_code", "") or "").strip()
            log_id = pc if pc else f"LOG-{obj.id:03d}"
            pt_disp = (
                obj.get_project_type_display()
                if getattr(obj, "project_type", None)
                else ""
            )
            subtitle_parts = []
            if cat_disp:
                subtitle_parts.append(cat_disp)
            if pt_disp:
                subtitle_parts.append(pt_disp)
            if not subtitle_parts and dept_label and dept_label != "—":
                subtitle_parts.append(dept_label)
            subtitle_line = " · ".join(subtitle_parts) if subtitle_parts else "—"

            phase_nm = current_phase(obj)
            pmbok_label, pmbok_badge_class = PMBOK_PHASE_BADGE.get(
                phase_nm, ("PLANNING", "tw-pmbok-plan")
            )
            reg_badge_label, reg_badge_class = REGISTER_STATUS_BADGE.get(
                rs_eff,
                ((rs_disp.upper() if rs_disp else "—"), "tw-st-none"),
            )
            if rs_eff not in REGISTER_STATUS_BADGE and rs_disp:
                reg_badge_label = rs_disp.upper()

            deadline_days_int = None
            deadline_iso = ""
            deadline_days_label = ""
            if obj.end_date:
                deadline_iso = obj.end_date.isoformat()
                deadline_days_int = (obj.end_date - today).days
                deadline_days_label = f"{deadline_days_int}d"

            if pmo_score_pct >= 75:
                pmo_row_class = "tw-pmo-good"
            elif pmo_score_pct >= 60:
                pmo_row_class = "tw-pmo-warn"
            else:
                pmo_row_class = "tw-pmo-bad"

            planned_single = 0.0
            if obj.start_date and obj.end_date and obj.end_date > obj.start_date:
                _dur = (obj.end_date - obj.start_date).days
                _el = (today - obj.start_date).days
                planned_single = max(0.0, min(1.0, _el / float(_dur)))
            earned_single = prog_pct / 100.0
            penalty_single = 0.0
            if obj.end_date and obj.end_date < today:
                penalty_single += 0.25
            if "stuck" in [
                (obj.brainstorming_status or "").strip(),
                (obj.execution_status or "").strip(),
                (getattr(obj, "test_deadline_status", "") or "").strip(),
                (obj.launch_status or "").strip(),
            ]:
                penalty_single += 0.20
            ac_single = planned_single * (1.0 + penalty_single)
            spi_u = spi_p if spi_p is not None else (
                earned_single / planned_single if planned_single > 1e-6 else 0.0
            )
            cpi_u = cpi_p if cpi_p is not None else (
                earned_single / ac_single if ac_single > 1e-6 else 0.0
            )
            spi_u = max(0.0, min(2.0, float(spi_u)))
            cpi_u = max(0.0, min(2.0, float(cpi_u)))
            cv_u = earned_single - ac_single
            eac_u = (1.0 / cpi_u) if cpi_u > 1e-6 else 0.0

            lu_dt = getattr(obj, "last_status_update", None)
            days_since_update = None
            if lu_dt:
                days_since_update = (today - lu_dt).days

            _gov_appr = (getattr(obj, "gov_approval_status", "") or "").strip()
            _auto = automation_fields_payload(obj)
            detail_payload = {
                "objective_sow": getattr(obj, "objective_sow", "") or "",
                "kpi_success_criteria": getattr(obj, "kpi_success_criteria", "") or "",
                "scope_in": getattr(obj, "scope_in", "") or "",
                "scope_out": getattr(obj, "scope_out", "") or "",
                "scope_deliverables": getattr(obj, "scope_deliverables", "") or "",
                "scope_dependencies": getattr(obj, "scope_dependencies", "") or "",
                "process_steps": proc_steps,
                "raid_items": raid_rows,
                "gov": {
                    "submitted_by": getattr(obj, "gov_submitted_by", "") or "",
                    "reviewed_by": getattr(obj, "gov_reviewed_by", "") or "",
                    "approval_status": obj.get_gov_approval_status_display()
                    if _gov_appr
                    else "",
                    "stakeholders": getattr(obj, "gov_stakeholders", "") or "",
                    "operational_impact": getattr(obj, "gov_operational_impact", "") or "",
                    "assumptions_constraints": getattr(obj, "gov_assumptions_constraints", "") or "",
                },
                "evm": {
                    "bac": 1.0,
                    "pv": round(planned_single, 3),
                    "ev": round(earned_single, 3),
                    "ac": round(ac_single, 3),
                    "cv": round(cv_u, 3),
                    "spi": round(spi_u, 2),
                    "cpi": round(cpi_u, 2),
                    "eac": round(eac_u, 2),
                },
                "summary": {
                    "log_id": log_id,
                    "pmo_score_pct": pmo_score_pct,
                    "pmbok_label": pmbok_label,
                    "register_badge_label": reg_badge_label,
                    "priority_display": rp_disp,
                    "category_display": cat_disp,
                    "alignment_display": align_disp,
                    "last_update_display": lu_dt.strftime("%b %d, %Y") if lu_dt else "",
                    "days_since_update": days_since_update,
                },
                "biz": {
                    "cost_reduction_pct_display": cr_disp,
                    "headcount_impact": (getattr(obj, "headcount_impact", "") or "").strip(),
                    "sla_improvement": (getattr(obj, "sla_improvement", "") or "").strip(),
                },
                "effort_hours": {
                    "planned": str(obj.planned_hours)
                    if getattr(obj, "planned_hours", None) is not None
                    else "",
                    "actual": str(obj.actual_hours)
                    if getattr(obj, "actual_hours", None) is not None
                    else "",
                },
                "form_edit": {
                    "project_name": (obj.description or "").strip(),
                    "company": (getattr(obj, "company", "") or "").strip(),
                    "project_lead": lead,
                    "person_name": (obj.person_name or "").strip(),
                    "department_id": getattr(obj, "department_ref_id", None),
                    "category_id": getattr(obj, "register_category_id", None),
                    "strategic_alignment_id": getattr(obj, "strategic_alignment_ref_id", None),
                    "register_priority": rp,
                    "register_status": rs_reg,
                    "start_date_iso": obj.start_date.isoformat()
                    if obj.start_date
                    else "",
                    "planned_deadline_iso": obj.end_date.isoformat()
                    if obj.end_date
                    else "",
                    "pmbok_phase": phase_nm if phase_nm in (
                        "Initiating",
                        "Planning",
                        "Execution",
                        "Monitoring",
                        "Closing",
                    ) else "",
                    "headcount_impact": (getattr(obj, "headcount_impact", "") or "").strip(),
                    "sla_improvement": (getattr(obj, "sla_improvement", "") or "").strip(),
                    "cost_reduction_pct": str(obj.cost_reduction_pct)
                    if getattr(obj, "cost_reduction_pct", None) is not None
                    else "",
                    "planned_hours": str(obj.planned_hours)
                    if getattr(obj, "planned_hours", None) is not None
                    else "",
                    "actual_hours": str(obj.actual_hours)
                    if getattr(obj, "actual_hours", None) is not None
                    else "",
                    "progress_pct": project_progress_pct(obj),
                    "register_risk_level": (getattr(obj, "register_risk_level", "") or "").strip(),
                    "gov_submitted_by": getattr(obj, "gov_submitted_by", "") or "",
                    "gov_reviewed_by": getattr(obj, "gov_reviewed_by", "") or "",
                    "gov_approval_status": _gov_appr,
                    "gov_stakeholders": getattr(obj, "gov_stakeholders", "") or "",
                    "gov_operational_impact": getattr(obj, "gov_operational_impact", "") or "",
                    "gov_assumptions_constraints": getattr(obj, "gov_assumptions_constraints", "")
                    or "",
                    "business_benefits": _auto["business_benefits"],
                },
                "register_remarks": register_remarks_payload(obj),
                "remarks": (getattr(obj, "remarks", "") or "").strip(),
            }
            detail_payload.update(_auto)
            enrich_detail_from_remarks(obj, detail_payload)
            project_details_map[str(obj.id)] = detail_payload

            remarks_txt = (getattr(obj, "remarks", "") or "").strip()
            company_show = (getattr(obj, "company", "") or "").strip() or remark_field(
                remarks_txt, "company:"
            )
            dept_show = dept_label
            if not dept_show or dept_show == "—":
                dv = remark_field(remarks_txt, "department:")
                if dv:
                    dept_show = dv
            cat_show = (cat_disp or "").strip() or remark_field(remarks_txt, "category:")
            align_show = (align_disp or "").strip() or remark_field(
                remarks_txt, "strategic alignment:"
            )

            items.append(
                {
                    "id": obj.id,
                    "name": obj.description or "—",
                    "project_code": pc,
                    "log_id": log_id,
                    "subtitle_line": subtitle_line,
                    "project_lead": lead,
                    "contact_secondary": secondary,
                    "project_type": (obj.project_type or "").strip(),
                    "project_type_display": pt_disp,
                    "company": company_show or "—",
                    "department": dept_show or "—",
                    "owner": owner_show,
                    "register_priority": rp,
                    "register_priority_display": rp_disp,
                    "register_status": rs_reg,
                    "register_status_effective": rs_eff,
                    "register_status_display": rs_disp,
                    "register_badge_label": reg_badge_label,
                    "register_badge_class": reg_badge_class,
                    "pmbok_label": pmbok_label,
                    "pmbok_badge_class": pmbok_badge_class,
                    "deadline_iso": deadline_iso,
                    "deadline_days_label": deadline_days_label,
                    "deadline_days_int": deadline_days_int,
                    "pmo_score_pct": pmo_score_pct,
                    "pmo_row_class": pmo_row_class,
                    "is_approved": bool(getattr(obj, "is_approved", False)),
                    "category_display": cat_show or cat_disp,
                    "strategic_alignment_display": align_show or align_disp,
                    "cost_reduction_pct_display": cr_disp,
                    "headcount_impact": (getattr(obj, "headcount_impact", "") or "").strip(),
                    "sla_improvement": (getattr(obj, "sla_improvement", "") or "").strip(),
                    "start_date": obj.start_date,
                    "start_date_display": obj.start_date.strftime("%b %d, %Y")
                    if obj.start_date
                    else "—",
                    "deadline": obj.end_date,
                    "deadline_display": obj.end_date.strftime("%b %d, %Y")
                    if obj.end_date
                    else "—",
                    "phase": phase_nm,
                    "progress_pct": prog_pct,
                    "risk": register_risk_display(obj),
                    "brainstorming_status": (obj.brainstorming_status or "").strip(),
                    "execution_status": (obj.execution_status or "").strip(),
                    "test_deadline_status": (getattr(obj, "test_deadline_status", "") or "").strip(),
                    "launch_status": (obj.launch_status or "").strip(),
                    "brainstorming_display": phase_label(obj.brainstorming_status),
                    "execution_display": phase_label(obj.execution_status),
                    "test_deadline_display": phase_label(getattr(obj, "test_deadline_status", "")),
                    "launch_display": phase_label(obj.launch_status),
                    "remarks": getattr(obj, "remarks", "") or "",
                    "days_since_status_update": days_since_update,
                    "evm": detail_payload.get("evm") or {},
                    "open_raid_count": _open_raid_count,
                    "raid_open_impact": _raid_open_impact,
                }
            )

            # Earned value rollups (same as before)
            if is_active:
                start = obj.start_date
                end = obj.end_date
                if start and end and end > start:
                    duration_days = (end - start).days
                    elapsed_days = (today - start).days
                    planned = max(0.0, min(1.0, elapsed_days / float(duration_days)))
                else:
                    planned = 0.0
                earned = max(0.0, min(1.0, prog_pct / 100.0))
                pv_sum += planned
                ev_sum += earned
                penalty = 0.0
                if obj.end_date and obj.end_date < today:
                    penalty += 0.25
                if "stuck" in [
                    (obj.brainstorming_status or "").strip(),
                    (obj.execution_status or "").strip(),
                    (getattr(obj, "test_deadline_status", "") or "").strip(),
                    (obj.launch_status or "").strip(),
                ]:
                    penalty += 0.20
                ac_sum += planned * (1.0 + penalty)

        portfolio_spi = sum(spi_vals) / len(spi_vals) if spi_vals else 1.0
        portfolio_cpi = sum(cpi_vals) / len(cpi_vals) if cpi_vals else portfolio_spi
        portfolio_spi = max(0.0, min(2.0, portfolio_spi))
        portfolio_cpi = max(0.0, min(2.0, portfolio_cpi))

        avg_pmo = int(round(sum(pmo_scores) / len(pmo_scores))) if pmo_scores else 0

        open_raid = PortfolioRaidItem.objects.filter(
            status="open",
            project__pmo_register_published=True,
        ).exclude(project__launch_status="done").count()
        critical_raid = PortfolioRaidItem.objects.filter(
            status="open",
            severity="critical",
            project__pmo_register_published=True,
        ).exclude(project__launch_status="done").count()

        spi_footer = (
            "≈ Target ≥0.90" if portfolio_spi >= 0.9 else "↓ Behind vs timeline plan"
        )
        cpi_footer = "≈ Target ≥0.90" if portfolio_cpi >= 0.9 else "↓ Below 0.90"
        raid_footer = (
            f"↑ {critical_raid} critical" if critical_raid else "No critical RAID items"
        )
        active_footer = (
            f"↑ {started_this_quarter} started this quarter"
            if started_this_quarter
            else "Portfolio"
        )
        delayed_footer = (
            f"↑ {delayed_at_risk_count} need action"
            if delayed_at_risk_count
            else "No delayed / at-risk"
        )
        if avg_pmo >= 75:
            pmo_footer = "Strong portfolio health"
        elif avg_pmo >= 60:
            pmo_footer = "Review SPI / CPI drivers"
        elif active_count:
            pmo_footer = "Needs leadership attention"
        else:
            pmo_footer = "Add projects to measure"

        def _fc(tone):
            return {
                "good": "tw-foot-good",
                "bad": "tw-foot-bad",
                "neutral": "tw-foot-neutral",
                "warn": "tw-foot-warn",
            }.get(tone, "tw-foot-neutral")

        metrics = {
            "active_projects": active_count,
            "delayed_at_risk": delayed_at_risk_count,
            "started_this_quarter": started_this_quarter,
            "spi": round(portfolio_spi, 2),
            "cpi": round(portfolio_cpi, 2),
            "open_raid_items": open_raid,
            "critical_raid_items": critical_raid,
            "avg_pmo_score": avg_pmo,
            "spi_footer": spi_footer,
            "cpi_footer": cpi_footer,
            "delayed_footer": delayed_footer,
            "active_footer": active_footer,
            "raid_footer": raid_footer,
            "pmo_footer": pmo_footer,
            "spi_footer_class": _fc("neutral" if portfolio_spi >= 0.9 else "bad"),
            "cpi_footer_class": _fc("neutral" if portfolio_cpi >= 0.9 else "bad"),
            "delayed_footer_class": _fc("bad" if delayed_at_risk_count else "good"),
            "active_footer_class": _fc("good" if started_this_quarter else "neutral"),
            "raid_footer_class": _fc("bad" if critical_raid else "neutral"),
            "pmo_footer_class": _fc(
                "good"
                if avg_pmo >= 75
                else ("warn" if avg_pmo >= 60 else ("bad" if active_count else "neutral"))
            ),
        }

        bac = float(active_count)
        pv = pv_sum
        ev = ev_sum
        ac = ac_sum
        ev_spi = (ev / pv) if pv > 0 else 0.0
        ev_cpi = (ev / ac) if ac > 0 else 0.0
        cv = ev - ac
        eac = (bac / ev_cpi) if ev_cpi > 0 else 0.0

        earned_value = {
            "bac": round(bac, 2),
            "pv": round(pv, 2),
            "ev": round(ev, 2),
            "ac": round(ac, 2),
            "cv": round(cv, 2),
            "eac": round(eac, 2),
            "spi": round(ev_spi, 2),
            "cpi": round(ev_cpi, 2),
        }

        active_alerts = []
        _alert_keys = set()

        def _push_alert(kind, message, context, time_label, dedupe_key):
            if dedupe_key in _alert_keys:
                return
            _alert_keys.add(dedupe_key)
            active_alerts.append(
                {
                    "kind": kind,
                    "message": message,
                    "context": context,
                    "time_label": time_label,
                }
            )

        if portfolio_cpi < 0.90:
            _push_alert(
                "warn",
                "Portfolio CPI below 0.90 — cost vs earned value pressure",
                "Portfolio-wide",
                "Portfolio",
                "portfolio_cpi",
            )
        if portfolio_spi < 0.85:
            _push_alert(
                "info",
                "Portfolio SPI below 0.85 — schedule vs timeline plan",
                "Portfolio-wide",
                "Portfolio",
                "portfolio_spi",
            )

        for it in items:
            lid = it["log_id"]
            nm = (it["name"] or "")[:42]
            ctx = f"{lid} {nm}"
            pid = it["id"]

            dd = it.get("deadline_days_int")
            if dd is not None:
                if dd < 0:
                    _push_alert(
                        "warn",
                        f"Milestone overdue by {abs(dd)} days",
                        ctx,
                        "Deadline",
                        f"overdue_{pid}",
                    )
                elif dd <= 90 and it["progress_pct"] < 92:
                    _push_alert(
                        "warn",
                        f"Deadline in {dd} days — progress {it['progress_pct']}%",
                        ctx,
                        "Timeline",
                        f"soon_{pid}",
                    )

            rsx = (it.get("register_status_effective") or "").strip()
            if rsx in ("at_risk", "delayed", "blocked"):
                _push_alert(
                    "warn",
                    f"Register status: {it.get('register_badge_label')}",
                    ctx,
                    "Status",
                    f"reg_{pid}_{rsx}",
                )

            dsi = it.get("days_since_status_update")
            if dsi is not None and dsi > 14:
                _push_alert(
                    "info",
                    f"No PMO status update for {dsi} days",
                    ctx,
                    "Stale",
                    f"stale_{pid}",
                )

        for raid in (
            PortfolioRaidItem.objects.filter(
                status="open",
                project__pmo_register_published=True,
            )
            .exclude(project__launch_status="done")
            .select_related("project")
            .order_by("project_id", "-severity", "id")[:22]
        ):
            proj = raid.project
            lid = (getattr(proj, "project_code", "") or "").strip() or f"LOG-{proj.id:03d}"
            sev = (raid.severity or "").strip()
            rk = "crit" if sev == "critical" else ("warn" if sev in ("high", "medium") else "info")
            msg = (raid.title or "Open RAID item")[:56]
            ctx = f"{lid} {(proj.description or '')[:36]}"
            _push_alert(rk, msg, ctx, "RAID", f"raid_open_{raid.id}")

        tracked_ids = list(qs_all.values_list("id", flat=True))
        if tracked_ids:
            for act in (
                WorkspacePortfolioActivity.objects.filter(project_id__in=tracked_ids)
                .select_related("project")
                .order_by("-created_at")[:15]
            ):
                p = act.project
                lid = (getattr(p, "project_code", "") or "").strip() or f"LOG-{p.id:03d}"
                ctx = f"{lid} {(p.description or '')[:36]}"
                _push_alert(
                    "act",
                    act.message,
                    ctx,
                    "Activity",
                    f"actlog_{act.id}",
                )

        _alert_rank = {"act": -1, "crit": 0, "warn": 1, "info": 2}
        active_alerts.sort(
            key=lambda a: (_alert_rank.get(a.get("kind"), 5), a.get("context") or "")
        )
        active_alerts = active_alerts[:30]

        pending_queue_items = []
        pending_queue_details = {}
        approval_queue_approved_count = qs_all.filter(
            pmo_register_published=True
        ).count()

        for obj in qs_all.filter(pmo_register_published=False).order_by(
            "-created_at", "-id"
        ):
            card = build_pending_approval_entry(obj)
            detail = card.pop("detail", {})
            pending_queue_details[str(obj.id)] = detail
            pending_queue_items.append(card)

        return {
            "items": items,
            "pending_queue_items": pending_queue_items,
            "pending_queue_details": pending_queue_details,
            "approval_queue_approved_count": approval_queue_approved_count,
            "current_project_type": project_type or "",
            "metrics": metrics,
            "earned_value": earned_value,
            "register_lookups": register_lookups,
            "project_details_map": project_details_map,
            "active_alerts": active_alerts,
        }
    except Exception:
        return {
            "items": [],
            "pending_queue_items": [],
            "pending_queue_details": {},
            "approval_queue_approved_count": 0,
            "current_project_type": "",
            "register_lookups": {
                "departments": [],
                "categories": [],
                "alignments": [],
            },
            "project_details_map": {},
            "active_alerts": [],
            "metrics": {
                "active_projects": 0,
                "delayed_at_risk": 0,
                "started_this_quarter": 0,
                "spi": 0.0,
                "cpi": 0.0,
                "open_raid_items": 0,
                "critical_raid_items": 0,
                "avg_pmo_score": 0,
                "spi_footer": "—",
                "cpi_footer": "—",
                "delayed_footer": "—",
                "active_footer": "—",
                "raid_footer": "—",
                "pmo_footer": "—",
                "spi_footer_class": "tw-foot-neutral",
                "cpi_footer_class": "tw-foot-neutral",
                "delayed_footer_class": "tw-foot-neutral",
                "active_footer_class": "tw-foot-neutral",
                "raid_footer_class": "tw-foot-neutral",
                "pmo_footer_class": "tw-foot-neutral",
            },
            "earned_value": {
                "bac": 0.0,
                "pv": 0.0,
                "ev": 0.0,
                "ac": 0.0,
                "cv": 0.0,
                "eac": 0.0,
                "spi": 0.0,
                "cpi": 0.0,
            },
        }


def get_project_portfolio_list(project_type=None):
    """Backward-compatible alias for Transformation Workspace context."""
    return get_transformation_workspace(project_type)


DEFAULT_PROJECT_PHASES = [
    {"name": "Phase 1 — Requirements & Design", "done": 0, "total": 0, "pct": 0},
    {"name": "Phase 2 — Development", "done": 0, "total": 0, "pct": 0},
    {"name": "Phase 3 — Testing & UAT", "done": 0, "total": 0, "pct": 0},
    {"name": "Phase 4 — Go Live", "done": 0, "total": 0, "pct": 0},
]


def _ensure_project_phases(project):
    """Every project shows the same 4-phase summary shell (even when empty)."""
    defaults = [dict(phase) for phase in DEFAULT_PROJECT_PHASES]
    existing = project.get("phases") or []
    if not existing:
        project["phases"] = defaults
        return project
    merged = []
    for i, default in enumerate(defaults):
        if i < len(existing):
            merged.append(existing[i])
        else:
            merged.append(dict(default))
    project["phases"] = merged
    return project


def _phase_number(label):
    import re

    match = re.search(r"phase\s*(\d+)", (label or ""), re.I)
    return int(match.group(1)) if match else None


def _recalc_project_phases_from_tasks(project):
    """Phase progress = actual tasks grouped by phase number (not static demo totals)."""
    _ensure_project_phases(project)
    phase_defs = project.get("phases") or [dict(p) for p in DEFAULT_PROJECT_PHASES]
    counts_by_num = {}

    for grp in project.get("tasks") or []:
        task_phase = (grp.get("phase") or "").strip()
        items = grp.get("items") or []
        phase_num = _phase_number(task_phase)
        if phase_num is None:
            continue
        bucket = counts_by_num.setdefault(phase_num, {"done": 0, "total": 0})
        bucket["total"] += len(items)
        bucket["done"] += sum(1 for t in items if t.get("status") == "done")

    recalced = []
    for ph_def in phase_defs:
        name = ph_def.get("name") or ""
        phase_num = _phase_number(name)
        stats = counts_by_num.get(phase_num, {"done": 0, "total": 0}) if phase_num else {"done": 0, "total": 0}
        total = stats["total"]
        done = stats["done"]
        pct = round(done / total * 100) if total else 0
        recalced.append({"name": name, "done": done, "total": total, "pct": pct})

    project["phases"] = recalced
    return project


def _recalc_project_metrics_from_tasks(project):
    """Derive progress, PMO score, SPI, and CPI from actual task statuses."""
    total = project.get("tasks_total", 0) or 0
    done = project.get("tasks_done", 0) or 0
    in_progress = project.get("tasks_in_progress", 0) or 0

    if total > 0:
        progress = round(done / total * 100)
        pmo_score = round((done * 100 + in_progress * 50) / total)
        spi = round(done / total, 2)
        cpi = round((done + 0.5 * in_progress) / total, 2)
    else:
        progress = 0
        pmo_score = 0
        spi = 0.0
        cpi = 0.0

    project["progress"] = progress
    project["pmo_score"] = pmo_score
    project["spi"] = spi
    project["cpi"] = cpi
    return project


def _recalc_project_task_counts(project):
    items = []
    for grp in project.get("tasks") or []:
        items.extend(grp.get("items") or [])
    project["tasks_total"] = len(items)
    project["tasks_done"] = sum(1 for t in items if t.get("status") == "done")
    project["tasks_in_progress"] = sum(1 for t in items if t.get("status") == "in_progress")
    project["tasks_pending"] = sum(
        1 for t in items if t.get("status") not in ("done", "in_progress")
    )
    _recalc_project_phases_from_tasks(project)
    _recalc_project_metrics_from_tasks(project)
    return project


def _merge_projects_tab_task_overrides(projects):
    from .models import ProjectsTabTaskStore

    overrides = {
        row.project_key: row.tasks
        for row in ProjectsTabTaskStore.objects.all()
    }
    for project in projects:
        if project.get("tracker_id"):
            _recalc_project_task_counts(project)
            continue
        key = project.get("id")
        if key and key in overrides:
            project["tasks"] = overrides[key]
        _recalc_project_task_counts(project)
    return projects


def _merge_cards_view_custom_projects(projects):
    from .models import ProjectsTabCardProject

    existing_ids = {p.get("id") for p in projects}
    for row in ProjectsTabCardProject.objects.all():
        payload = dict(row.data or {})
        payload["id"] = payload.get("id") or row.project_key
        if payload["id"] in existing_ids:
            continue
        _ensure_project_phases(payload)
        payload.setdefault("tasks", [])
        _recalc_project_task_counts(payload)
        projects.append(payload)
    return projects


def parse_estimated_time_saving_post(post):
    """Parse estimated_time_saving + unit from POST/JSON dict."""
    from decimal import Decimal, InvalidOperation

    raw = (post.get("estimated_time_saving") or "").strip()
    val = None
    if raw:
        try:
            val = Decimal(raw.replace(",", "."))
            if val < 0:
                val = None
        except (InvalidOperation, ValueError):
            val = None
    unit = (post.get("estimated_time_saving_unit") or "hours").strip().lower()
    if unit not in ("hours", "minutes"):
        unit = "hours"
    return val, unit


def format_estimated_time_saving_display(value, unit="hours"):
    if value is None:
        return ""
    u = (unit or "hours").strip().lower()
    label = "hours" if u == "hours" else "minutes"
    s = format(value, "f").rstrip("0").rstrip(".")
    return f"{s} {label}"


def estimated_time_saving_to_minutes(value, unit="hours"):
    """Normalize a single project's estimated saving to minutes."""
    from decimal import Decimal

    if value is None:
        return Decimal(0)
    v = Decimal(str(value))
    u = (unit or "hours").strip().lower()
    return v if u == "minutes" else v * Decimal(60)


def aggregate_portfolio_time_saved(qs):
    """
    Sum estimated_time_saving across projects, always displayed in hours.
    Per-project minutes are converted (e.g. 30 min → 0.5 hr) before summing.
    Returns (value_text, projects_with_savings_count).
    """
    from decimal import Decimal

    total_mins = Decimal(0)
    project_count = 0
    for obj in qs.only("estimated_time_saving", "estimated_time_saving_unit").iterator():
        val = getattr(obj, "estimated_time_saving", None)
        if val is None:
            continue
        total_mins += estimated_time_saving_to_minutes(
            val,
            getattr(obj, "estimated_time_saving_unit", "hours"),
        )
        project_count += 1

    hours = total_mins / Decimal(60)
    if hours <= 0:
        return "0 hrs", project_count

    if hours >= 100:
        return f"{int(hours)} hrs", project_count
    h_str = format(hours, "f").rstrip("0").rstrip(".")
    return f"{h_str} hrs", project_count


def automation_fields_payload(obj):
    """Business benefits for project detail / form_edit."""
    benefits = (getattr(obj, "business_benefits", "") or "").strip()
    if not benefits:
        parts = []
        val = getattr(obj, "estimated_time_saving", None)
        if val is not None:
            unit = (getattr(obj, "estimated_time_saving_unit", "") or "hours").strip() or "hours"
            parts.append(f"Estimated time saving: {val} {unit}")
        resources = (getattr(obj, "resources_before_automation", "") or "").strip()
        if resources:
            parts.append(resources)
        benefits = "\n".join(parts)
    return {"business_benefits": benefits}


CARDS_VIEW_CATEGORY_LABELS = {
    "automation": "AUTOMATION",
    "operations": "OPERATIONS",
    "digital": "DIGITAL",
}

CARDS_VIEW_STATUS_LABELS = {
    "on_track": "ON TRACK",
    "delayed": "DELAYED",
}


def apply_cards_view_meta_patch(project, meta):
    """Apply saved metadata overrides onto a cards-view project dict."""
    if not meta:
        return project
    if meta.get("title"):
        project["title"] = str(meta["title"]).strip()
    if "description" in meta:
        project["description"] = str(meta.get("description") or "").strip()
    if meta.get("owner") is not None:
        project["owner"] = str(meta.get("owner") or "").strip()
    if meta.get("phase"):
        project["phase"] = str(meta["phase"]).strip()
    category = (meta.get("category") or "").strip().lower()
    if category in CARDS_VIEW_CATEGORY_LABELS:
        project["category"] = category
        project["category_label"] = CARDS_VIEW_CATEGORY_LABELS[category]
    status = (meta.get("status") or "").strip().lower()
    if status in CARDS_VIEW_STATUS_LABELS:
        project["status"] = status
        project["status_label"] = CARDS_VIEW_STATUS_LABELS[status]
    if meta.get("deadline") is not None:
        project["deadline"] = str(meta.get("deadline") or "").strip()
    if "business_benefits" in meta:
        project["business_benefits"] = str(meta.get("business_benefits") or "").strip()
    return project


def _merge_projects_tab_meta_overrides(projects):
    from .models import ProjectsTabProjectMetaStore

    overrides = {
        row.project_key: row.meta
        for row in ProjectsTabProjectMetaStore.objects.all()
    }
    for project in projects:
        key = project.get("id")
        if key and key in overrides:
            apply_cards_view_meta_patch(project, overrides[key])
    return projects


def cards_project_key_from_title(title, existing_ids=None):
    """Derive a stable internal card id from the project title (no user-facing code)."""
    import re
    import uuid

    base = re.sub(r"[^a-z0-9]+", "-", (title or "").lower()).strip("-") or "project"
    key = base[:48]
    taken = {str(x).strip().lower() for x in (existing_ids or []) if x}
    if key not in taken:
        return key
    for n in range(2, 1000):
        candidate = f"{key}-{n}"
        if candidate not in taken:
            return candidate
    return f"{key}-{uuid.uuid4().hex[:6]}"


def build_cards_view_project(payload, existing_ids=None):
    """Normalize POST payload into a card project dict."""
    category = (payload.get("category") or "automation").strip().lower()
    if category not in CARDS_VIEW_CATEGORY_LABELS:
        category = "automation"
    status = (payload.get("status") or "on_track").strip().lower()
    if status not in CARDS_VIEW_STATUS_LABELS:
        status = "on_track"
    title = (payload.get("title") or "").strip()
    if not title:
        raise ValueError("Project title is required.")
    project_key = cards_project_key_from_title(title, existing_ids=existing_ids)
    deadline = (payload.get("deadline") or "").strip()
    phase = (payload.get("phase") or "Initiating").strip()
    project = {
        "id": project_key,
        "category": category,
        "category_label": CARDS_VIEW_CATEGORY_LABELS[category],
        "status": status,
        "status_label": CARDS_VIEW_STATUS_LABELS[status],
        "title": title,
        "description": (payload.get("description") or "").strip(),
        "business_benefits": (payload.get("business_benefits") or "").strip(),
        "progress": 0,
        "phase": phase,
        "owner": (payload.get("owner") or "").strip(),
        "pmo_score": 0,
        "deadline": deadline,
        "spi": 0.0,
        "cpi": 0.0,
        "tasks_done": 0,
        "tasks_total": 0,
        "tasks_in_progress": 0,
        "tasks_pending": 0,
        "phases": [dict(p) for p in DEFAULT_PROJECT_PHASES],
        "tasks": [],
        "remaining": [],
    }
    apply_cards_view_meta_patch(
        project,
        {"business_benefits": project["business_benefits"]},
    )
    return project


def _category_slug_from_tracker(obj):
    """Map tracker item to cards-view accent category."""
    if getattr(obj, "register_category_id", None) and obj.register_category:
        name = (obj.register_category.name or "").strip().lower()
        if "operation" in name:
            return "operations"
        if "digital" in name:
            return "digital"
        if "automation" in name:
            return "automation"
    pt = (obj.project_type or "").strip().lower()
    if pt == "automation":
        return "automation"
    return "digital"


def _register_status_to_card_status(rs_eff):
    if rs_eff in ("delayed", "at_risk", "blocked"):
        return "delayed"
    return "on_track"


def _tracker_progress_pct(obj):
    stored = getattr(obj, "progress_pct", None)
    if stored is not None:
        try:
            return max(0, min(100, int(stored)))
        except (TypeError, ValueError):
            pass
    status_score = {
        "done": 1.0,
        "working_on_it": 0.55,
        "stuck": 0.25,
        "": 0.0,
        None: 0.0,
    }
    vals = [
        obj.brainstorming_status,
        obj.execution_status,
        getattr(obj, "test_deadline_status", ""),
        obj.launch_status,
    ]
    total = sum(status_score.get(v, 0.0) for v in vals)
    return int(round((total / 4.0) * 100))


def _tracker_current_phase(obj):
    phases = [
        ("Initiating", obj.brainstorming_status),
        ("Executing", obj.execution_status),
        ("Monitoring", getattr(obj, "test_deadline_status", "")),
        ("Closing", obj.launch_status),
    ]
    for name, val in phases:
        if (val or "") != "done":
            return name
    return "Closing"


def _process_steps_to_task_groups(steps):
    items = []
    for step in steps:
        dl = step.step_deadline
        st = (getattr(step, "status", None) or "pending").strip()
        if st not in ("pending", "in_progress", "done"):
            st = "pending"
        items.append(
            {
                "id": str(step.id),
                "text": step.description or "",
                "deadline": dl.isoformat() if dl else "",
                "deadline_display": dl.strftime("%Y-%m-%d") if dl else "",
                "assignee": step.owner_name or "",
                "status": st,
                "business_benefits": (getattr(step, "business_benefits", "") or "").strip(),
            }
        )
    if not items:
        return []
    return [{"phase": "PROJECT TASKS", "items": items}]


def _tracker_item_to_card_project(obj):
    """Build a Cards View project dict from a published ProjectTrackerItem."""
    from datetime import date

    today = date.today()
    prog_pct = _tracker_progress_pct(obj)

    rs_reg = (getattr(obj, "register_status", "") or "").strip()
    rs_eff = rs_reg
    if not rs_eff:
        if obj.end_date and obj.end_date < today:
            rs_eff = "delayed"
        else:
            rs_eff = "on_track"

    card_status = _register_status_to_card_status(rs_eff)
    cat = _category_slug_from_tracker(obj)
    title = (obj.description or "").strip() or "—"
    pc = (getattr(obj, "project_code", "") or "").strip()
    log_id = pc if pc else f"LOG-{obj.id:03d}"
    lead = (getattr(obj, "project_lead", "") or "").strip()
    secondary = (obj.person_name or "").strip()
    owner = lead or secondary or "—"
    proc_steps = list(obj.process_steps.all())
    tasks = _process_steps_to_task_groups(proc_steps)

    project = {
        "id": str(obj.id),
        "tracker_id": obj.id,
        "code": log_id,
        "category": cat,
        "category_label": title,
        "status": card_status,
        "status_label": CARDS_VIEW_STATUS_LABELS[card_status],
        "title": title,
        "description": (getattr(obj, "objective_sow", "") or "").strip(),
        "business_benefits": automation_fields_payload(obj)["business_benefits"],
        "progress": prog_pct,
        "phase": _tracker_current_phase(obj),
        "owner": owner,
        "pmo_score": prog_pct,
        "deadline": obj.end_date.isoformat() if obj.end_date else "",
        "spi": round(prog_pct / 100.0, 2) if prog_pct else 0.0,
        "cpi": round(prog_pct / 100.0, 2) if prog_pct else 0.0,
        "tasks_done": 0,
        "tasks_total": 0,
        "tasks_in_progress": 0,
        "tasks_pending": 0,
        "phases": [dict(p) for p in DEFAULT_PROJECT_PHASES],
        "tasks": tasks,
        "remaining": [],
    }
    _recalc_project_task_counts(project)
    return project


def _get_projects_tab_demo_projects():
    """Fallback demo cards when no published tracker rows exist."""
    return [
        {
            "id": "log-069",
            "code": "LOG-069",
            "category": "automation",
            "category_label": "AUTOMATION",
            "status": "delayed",
            "status_label": "DELAYED",
            "title": "Daily Tamer Dashboard Enhancement",
            "description": (
                "Enhance the daily Tamer operations dashboard with new KPIs, "
                "automated data refresh, and alert thresholds for warehouse managers."
            ),
            "progress": 39,
            "phase": "Executing",
            "owner": "Aljwharah",
            "pmo_score": 48,
            "deadline": "2026-05-21",
            "spi": 0.62,
            "cpi": 0.71,
            "tasks_done": 5,
            "tasks_total": 12,
            "tasks_in_progress": 2,
            "tasks_pending": 5,
            "phases": [
                {"name": "Phase 1 — Requirements & Design", "done": 6, "total": 6, "pct": 100},
                {"name": "Phase 2 — Development", "done": 5, "total": 8, "pct": 65},
                {"name": "Phase 3 — Testing & UAT", "done": 0, "total": 5, "pct": 10},
                {"name": "Phase 4 — Go Live", "done": 0, "total": 3, "pct": 0},
            ],
            "tasks": [
                {
                    "phase": "PHASE 1 — REQUIREMENTS & DESIGN",
                    "items": [
                        {"text": "Map current dashboard KPIs", "status": "done", "assignee": "Aljwharah"},
                        {"text": "Define new metrics with ops team", "status": "done", "assignee": "Aljwharah"},
                        {"text": "Design wireframes", "status": "done", "assignee": "Aljwharah"},
                    ],
                },
                {
                    "phase": "PHASE 2 — DEVELOPMENT",
                    "items": [
                        {"text": "Build backend data pipeline", "status": "done", "assignee": "Aljwharah"},
                        {"text": "Develop dashboard UI components", "status": "done", "assignee": "Aljwharah"},
                        {"text": "Integrate SAP data source", "status": "in_progress", "assignee": "Aljwharah"},
                        {"text": "Connect automated refresh logic", "status": "in_progress", "assignee": "Aljwharah"},
                        {"text": "Add alert threshold rules", "status": "pending", "assignee": "Aljwharah"},
                    ],
                },
                {
                    "phase": "PHASE 3 — TESTING & UAT",
                    "items": [
                        {"text": "Write test scripts", "status": "pending", "assignee": "TBD"},
                        {"text": "UAT with warehouse managers", "status": "pending", "assignee": "Ops Team"},
                    ],
                },
                {
                    "phase": "PHASE 4 — GO LIVE",
                    "items": [
                        {"text": "Training session", "status": "pending", "assignee": "Aljwharah"},
                        {"text": "Go live & monitoring", "status": "pending", "assignee": "Aljwharah"},
                    ],
                },
            ],
            "remaining": [
                "Integrate SAP data source",
                "Connect automated refresh logic",
                "Add alert threshold rules",
                "Write test scripts",
                "UAT with warehouse managers",
                "Training session",
                "Go live & monitoring",
            ],
        },
        {
            "id": "log-067",
            "code": "LOG-067",
            "category": "automation",
            "category_label": "AUTOMATION",
            "status": "on_track",
            "status_label": "ON TRACK",
            "title": "Picker Performance Report Automation",
            "description": "Automate picker performance reporting with daily SAP extracts and email distribution.",
            "progress": 100,
            "phase": "Executing",
            "owner": "Aljwharah",
            "pmo_score": 94,
            "deadline": "2026-04-30",
            "spi": 1.05,
            "cpi": 1.02,
            "tasks_done": 8,
            "tasks_total": 8,
            "tasks_in_progress": 0,
            "tasks_pending": 0,
            "phases": [
                {"name": "Phase 1 — Requirements & Design", "done": 2, "total": 2, "pct": 100},
                {"name": "Phase 2 — Development", "done": 4, "total": 4, "pct": 100},
                {"name": "Phase 3 — Testing & UAT", "done": 1, "total": 1, "pct": 100},
                {"name": "Phase 4 — Go Live", "done": 1, "total": 1, "pct": 100},
            ],
            "tasks": [],
            "remaining": [],
        },
        {
            "id": "log-068",
            "code": "LOG-068",
            "category": "operations",
            "category_label": "OPERATIONS",
            "status": "on_track",
            "status_label": "ON TRACK",
            "title": "Picking Status",
            "description": "Real-time picking status visibility for warehouse floor supervisors.",
            "progress": 0,
            "phase": "Initiating",
            "owner": "Aljwharah",
            "pmo_score": 14,
            "deadline": "2026-06-30",
            "spi": 0.0,
            "cpi": 0.0,
            "tasks_done": 0,
            "tasks_total": 3,
            "tasks_in_progress": 1,
            "tasks_pending": 2,
            "phases": [
                {"name": "Phase 1 — Scoping", "done": 0, "total": 3, "pct": 0},
                {"name": "Phase 2 — Development", "done": 0, "total": 0, "pct": 0},
                {"name": "Phase 3 — Testing & UAT", "done": 0, "total": 0, "pct": 0},
                {"name": "Phase 4 — Go Live", "done": 0, "total": 0, "pct": 0},
            ],
            "tasks": [
                {
                    "phase": "PHASE 1 — SCOPING",
                    "items": [
                        {
                            "text": "Define scope with ops manager",
                            "status": "in_progress",
                            "assignee": "Aljwharah",
                        },
                        {
                            "text": "Map current picking flow",
                            "status": "pending",
                            "assignee": "Aljwharah",
                        },
                        {
                            "text": "Identify data sources",
                            "status": "pending",
                            "assignee": "Aljwharah",
                        },
                    ],
                },
            ],
            "remaining": [],
        },
        {
            "id": "log-066",
            "code": "LOG-066",
            "category": "automation",
            "category_label": "AUTOMATION",
            "status": "on_track",
            "status_label": "ON TRACK",
            "title": "Daily Activity Reports",
            "description": "Automated daily activity reports for inbound and outbound operations.",
            "progress": 72,
            "phase": "Executing",
            "owner": "PMO Team",
            "pmo_score": 72,
            "deadline": "2026-05-31",
            "spi": 0.88,
            "cpi": 0.91,
            "tasks_done": 9,
            "tasks_total": 12,
            "tasks_in_progress": 2,
            "tasks_pending": 1,
            "phases": [
                {"name": "Phase 1 — Requirements & Design", "done": 3, "total": 3, "pct": 100},
                {"name": "Phase 2 — Development", "done": 5, "total": 7, "pct": 72},
                {"name": "Phase 3 — Testing & UAT", "done": 1, "total": 2, "pct": 50},
            ],
            "tasks": [],
            "remaining": ["Finalize report templates", "UAT sign-off"],
        },
        {
            "id": "log-065",
            "code": "LOG-065",
            "category": "digital",
            "category_label": "DIGITAL",
            "status": "on_track",
            "status_label": "ON TRACK",
            "title": "VAS Dashboard",
            "description": "Value-added services dashboard for client-facing KPIs and SLA tracking.",
            "progress": 11,
            "phase": "Initiating",
            "owner": "PMO Team",
            "pmo_score": 11,
            "deadline": "2026-06-15",
            "spi": 0.45,
            "cpi": 0.52,
            "tasks_done": 1,
            "tasks_total": 9,
            "tasks_in_progress": 1,
            "tasks_pending": 7,
            "phases": [
                {"name": "Phase 1 — Requirements & Design", "done": 1, "total": 4, "pct": 25},
                {"name": "Phase 2 — Development", "done": 0, "total": 3, "pct": 0},
                {"name": "Phase 3 — Testing & UAT", "done": 0, "total": 2, "pct": 0},
            ],
            "tasks": [],
            "remaining": ["Define VAS KPIs", "Wireframe dashboard", "Data source mapping"],
        },
    ]


def get_projects_tab_data(project_type=None):
    """
    Cards View register: published ProjectTrackerItem rows from Admin (primary).
    Falls back to demo cards only when no published projects exist (local dev).
    """
    projects = []
    try:
        from django.db.models import Prefetch

        from .models import ProjectProcessStep, ProjectTrackerItem

        qs = (
            ProjectTrackerItem.objects.filter(pmo_register_published=True)
            .prefetch_related(
                Prefetch(
                    "process_steps",
                    queryset=ProjectProcessStep.objects.order_by("display_order", "id"),
                ),
            )
            .order_by("-created_at", "-id")
        )
        if project_type and project_type in ("idea", "automation"):
            qs = qs.filter(project_type=project_type)
        projects = [_tracker_item_to_card_project(obj) for obj in qs]
    except Exception:
        projects = []

    if not projects:
        from django.conf import settings

        # Demo cards only for local dev when the DB has no projects at all.
        # On production, unpublished admin rows must not be masked by fake portfolio data.
        try:
            has_any_tracker = ProjectTrackerItem.objects.exists()
        except Exception:
            has_any_tracker = False
        if settings.DEBUG and not has_any_tracker:
            projects = _get_projects_tab_demo_projects()

    for project in projects:
        _ensure_project_phases(project)
        project.setdefault("tasks", [])
    projects = _merge_cards_view_custom_projects(projects)
    projects = _merge_projects_tab_meta_overrides(projects)
    projects = _merge_projects_tab_task_overrides(projects)
    for project in projects:
        _recalc_project_task_counts(project)

    def _score_sort_key(item):
        """Ascending PMO score; cards at 100% progress pinned to the bottom."""
        progress = item.get("progress", 0) or 0
        pmo_score = item.get("pmo_score", 0) or 0
        if progress >= 100:
            return (2, pmo_score)
        return (1, pmo_score)

    projects.sort(key=_score_sort_key)
    return {"projects": projects}
