"""Initial plan schema.

Revision ID: 001_initial
Revises:
Create Date: 2026-08-19

Idempotent: if tables already exist (created by metadata.create_all), skip.
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "001_initial"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("plan_meta"):
        return

    op.create_table(
        "plan_meta",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_start", sa.Date(), nullable=False),
        sa.CheckConstraint("id = 1", name="single_plan"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "tasks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=512), nullable=False),
        sa.Column("description", sa.Text(), server_default="", nullable=False),
        sa.Column("assignee", sa.String(length=256), server_default="", nullable=False),
        sa.Column("duration_days", sa.Integer(), nullable=False),
        sa.Column("lag_days", sa.Integer(), server_default="0", nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "task_predecessors",
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.Column("predecessor_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["predecessor_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("task_id", "predecessor_id"),
    )


def downgrade() -> None:
    op.drop_table("task_predecessors")
    op.drop_table("tasks")
    op.drop_table("plan_meta")
