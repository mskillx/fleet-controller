"""Add response column to command_logs

Revision ID: 002
Revises: 001
Create Date: 2025-01-01 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('command_logs', sa.Column('response', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('command_logs', 'response')
