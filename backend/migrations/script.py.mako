"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

Reviewed SQL only (.claude/rules/migrations.md): one logical change; new tenant tables get org_id NOT NULL,
an indexed FK, ENABLE + FORCE ROW LEVEL SECURITY and the tenant_isolation policy in this same revision.
"""

from collections.abc import Sequence

from alembic import op

revision: str = ${repr(up_revision)}
down_revision: str | None = ${repr(down_revision)}
branch_labels: str | Sequence[str] | None = ${repr(branch_labels)}
depends_on: str | Sequence[str] | None = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else 'raise NotImplementedError("write reviewed SQL with op.execute()")'}


def downgrade() -> None:
    ${downgrades if downgrades else 'raise NotImplementedError("write the reverse SQL")'}
