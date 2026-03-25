"""Initial migration

Revision ID: 001
Revises:
Create Date: 2024-01-01 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'device_stats',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('device_id', sa.String(), nullable=False),
        sa.Column('timestamp', sa.String(), nullable=False),
        sa.Column('sensor1', sa.Float(), nullable=False),
        sa.Column('sensor2', sa.Float(), nullable=False),
        sa.Column('sensor3', sa.Float(), nullable=False),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('(CURRENT_TIMESTAMP)'),
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_device_stats_device_id', 'device_stats', ['device_id'])
    op.create_index('ix_device_stats_id', 'device_stats', ['id'])


def downgrade() -> None:
    op.drop_index('ix_device_stats_device_id', table_name='device_stats')
    op.drop_index('ix_device_stats_id', table_name='device_stats')
    op.drop_table('device_stats')
