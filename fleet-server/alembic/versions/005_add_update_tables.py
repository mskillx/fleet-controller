"""Add update_packages and update_jobs tables

Revision ID: 005
Revises: 004
Create Date: 2026-03-31 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = '005'
down_revision = '004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'update_packages',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('version', sa.String(), nullable=False),
        sa.Column('filename', sa.String(), nullable=False),
        sa.Column('checksum_sha256', sa.String(), nullable=False),
        sa.Column('size_bytes', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('1')),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('(CURRENT_TIMESTAMP)'),
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('version'),
    )
    op.create_index('ix_update_packages_id', 'update_packages', ['id'])
    op.create_index('ix_update_packages_version', 'update_packages', ['version'])

    op.create_table(
        'update_jobs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('deploy_id', sa.String(), nullable=False),
        sa.Column('device_id', sa.String(), nullable=False),
        sa.Column('version', sa.String(), nullable=False),
        sa.Column('batch_index', sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column('status', sa.String(), nullable=False, server_default=sa.text("'pending'")),
        sa.Column('error_msg', sa.Text(), nullable=True),
        sa.Column('command_id', sa.String(), nullable=True),
        sa.Column(
            'started_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('(CURRENT_TIMESTAMP)'),
        ),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_update_jobs_id', 'update_jobs', ['id'])
    op.create_index('ix_update_jobs_deploy_id', 'update_jobs', ['deploy_id'])
    op.create_index('ix_update_jobs_device_id', 'update_jobs', ['device_id'])
    op.create_index('ix_update_jobs_command_id', 'update_jobs', ['command_id'])


def downgrade() -> None:
    op.drop_index('ix_update_jobs_command_id', table_name='update_jobs')
    op.drop_index('ix_update_jobs_device_id', table_name='update_jobs')
    op.drop_index('ix_update_jobs_deploy_id', table_name='update_jobs')
    op.drop_index('ix_update_jobs_id', table_name='update_jobs')
    op.drop_table('update_jobs')

    op.drop_index('ix_update_packages_version', table_name='update_packages')
    op.drop_index('ix_update_packages_id', table_name='update_packages')
    op.drop_table('update_packages')
