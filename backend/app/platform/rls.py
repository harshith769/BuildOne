"""SQL for the standard row-level-security policies (ADR-0013, data-model.md §3).

Migrations call `company_data_policies()` for every table holding a company's data (facts, obligations, ...),
so each one gets identical SQL. Read access (`can_read`: members of any role, and members of an org holding an
active access grant) appears only in the SELECT policy; writes need `can_edit` (owner or member). Grants and
viewers therefore never write.

FROZEN OUTPUT: migrations that already ran depend on this text. Never change what an existing function returns;
add a new function (e.g. `company_data_policies_v2`) instead.
"""

from __future__ import annotations

import re

_TABLE = re.compile(r"^[a-z_]+\.[a-z_]+$")


def company_data_policies(table: str) -> list[str]:
    """Statements that enable and force RLS on `table` (schema-qualified) and create the four policies."""
    if not _TABLE.fullmatch(table):
        raise ValueError(f"expected schema.table, got {table!r}")
    scoped = "org_id = platform.current_org_id()"
    read = f"({scoped} AND tenancy.can_read(org_id))"
    edit = f"({scoped} AND tenancy.can_edit(org_id))"
    return [
        f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY",
        f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY",
        f"CREATE POLICY tenant_read ON {table} FOR SELECT USING {read}",
        f"CREATE POLICY tenant_insert ON {table} FOR INSERT WITH CHECK {edit}",
        f"CREATE POLICY tenant_update ON {table} FOR UPDATE USING {edit} WITH CHECK {edit}",
        f"CREATE POLICY tenant_delete ON {table} FOR DELETE USING {edit}",
    ]
