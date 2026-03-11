from __future__ import annotations

from vps_cli.util import bold, c, dim

from .diff import FieldChange, ResourceDiff, SyncPlan

_ACTION_SYMBOLS = {
    "create": ("+", "32"),  # green
    "update": ("~", "33"),  # yellow
    "delete": ("-", "31"),  # red
    "orphan": ("?", "36"),  # cyan
}


def _format_field_change(fc: FieldChange) -> str:
    return f"{fc.field}: {fc.old!r} -> {fc.new!r}"


def _render_diff(diff: ResourceDiff) -> str:
    sym, color = _ACTION_SYMBOLS[diff.action]
    prefix = c(color, f"  {sym}")
    label = diff.action

    detail_parts: list[str] = []
    if diff.action == "update" and diff.changes:
        detail_parts = [_format_field_change(ch) for ch in diff.changes]
    elif diff.action == "create":
        detail_parts = ["new"]
    elif diff.action == "orphan":
        detail_parts = ["exists in panel but not in state.yml"]

    detail = f" ({', '.join(detail_parts)})" if detail_parts else ""

    return f'{prefix} {label} "{diff.name}"{dim(detail)}'


def render_plan(plan: SyncPlan) -> str:
    lines: list[str] = []

    sections = [
        ("Config Profiles", plan.config_profiles),
        ("Nodes", plan.nodes),
        ("Hosts", plan.hosts),
        ("Users", plan.users),
    ]

    for title, diffs in sections:
        lines.append(f"\n{bold(title)}:")
        if not diffs:
            lines.append(dim("  (no changes)"))
        else:
            for d in diffs:
                lines.append(_render_diff(d))

    return "\n".join(lines)
