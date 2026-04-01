"""Replace sensor columns with new device stats fields

Revision ID: 004
Revises: 003
Create Date: 2026-03-31 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('device_stats') as batch_op:
        batch_op.drop_column('sensor1')
        batch_op.drop_column('sensor2')
        batch_op.drop_column('sensor3')
        batch_op.drop_column('version')
        batch_op.add_column(sa.Column('last_acquisition', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('last_boot', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('lights_on', sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column('disk_usage', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('analysis_queue', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('is_camera_acquiring', sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column('lidar', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('com4', sa.Float(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('device_stats') as batch_op:
        batch_op.drop_column('last_acquisition')
        batch_op.drop_column('last_boot')
        batch_op.drop_column('lights_on')
        batch_op.drop_column('disk_usage')
        batch_op.drop_column('analysis_queue')
        batch_op.drop_column('is_camera_acquiring')
        batch_op.drop_column('lidar')
        batch_op.drop_column('com4')
        batch_op.add_column(sa.Column('sensor1', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('sensor2', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('sensor3', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('version', sa.String(), nullable=True))
