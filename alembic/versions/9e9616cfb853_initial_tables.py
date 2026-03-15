"""initial tables

Revision ID: 9e9616cfb853
Revises:
Create Date: 2026-03-15 13:37:42.483912

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '9e9616cfb853'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create xsmb_results table
    op.create_table(
        'xsmb_results',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('draw_date', sa.Date(), nullable=False),
        sa.Column('day_of_week', sa.SmallInteger(), nullable=False),
        sa.Column('giai_db', sa.String(length=5), nullable=False),
        sa.Column('giai_1', sa.String(length=5), nullable=False),
        sa.Column('giai_2_1', sa.String(length=5), nullable=False),
        sa.Column('giai_2_2', sa.String(length=5), nullable=False),
        sa.Column('giai_3_1', sa.String(length=5), nullable=False),
        sa.Column('giai_3_2', sa.String(length=5), nullable=False),
        sa.Column('giai_3_3', sa.String(length=5), nullable=False),
        sa.Column('giai_3_4', sa.String(length=5), nullable=False),
        sa.Column('giai_3_5', sa.String(length=5), nullable=False),
        sa.Column('giai_3_6', sa.String(length=5), nullable=False),
        sa.Column('giai_4_1', sa.String(length=4), nullable=False),
        sa.Column('giai_4_2', sa.String(length=4), nullable=False),
        sa.Column('giai_4_3', sa.String(length=4), nullable=False),
        sa.Column('giai_4_4', sa.String(length=4), nullable=False),
        sa.Column('giai_5_1', sa.String(length=4), nullable=False),
        sa.Column('giai_5_2', sa.String(length=4), nullable=False),
        sa.Column('giai_5_3', sa.String(length=4), nullable=False),
        sa.Column('giai_5_4', sa.String(length=4), nullable=False),
        sa.Column('giai_5_5', sa.String(length=4), nullable=False),
        sa.Column('giai_5_6', sa.String(length=4), nullable=False),
        sa.Column('giai_6_1', sa.String(length=3), nullable=False),
        sa.Column('giai_6_2', sa.String(length=3), nullable=False),
        sa.Column('giai_6_3', sa.String(length=3), nullable=False),
        sa.Column('giai_7_1', sa.String(length=2), nullable=False),
        sa.Column('giai_7_2', sa.String(length=2), nullable=False),
        sa.Column('giai_7_3', sa.String(length=2), nullable=False),
        sa.Column('giai_7_4', sa.String(length=2), nullable=False),
        sa.Column('raw_string', sa.String(length=110), nullable=True),
        sa.Column('loto_array', postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column('de_dau', sa.String(length=2), nullable=True),
        sa.Column('de_duoi', sa.String(length=2), nullable=True),
        sa.Column('ky_tu', sa.String(length=100), nullable=True),
        sa.Column('source', sa.String(length=50), nullable=True),
        sa.Column('source_url', sa.Text(), nullable=True),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('draw_date'),
    )
    op.create_index('idx_xsmb_draw_date', 'xsmb_results', [sa.text('draw_date DESC')], unique=False)
    op.create_index('idx_xsmb_giai_db', 'xsmb_results', ['giai_db'], unique=False)
    op.create_index('idx_xsmb_de_dau', 'xsmb_results', ['de_dau'], unique=False)
    op.create_index('idx_xsmb_day_of_week', 'xsmb_results', ['day_of_week'], unique=False)
    op.create_index(
        'idx_xsmb_year_month',
        'xsmb_results',
        [sa.text("extract(year from draw_date)"), sa.text("extract(month from draw_date)")],
        unique=False,
    )

    # Create scrape_jobs table
    op.create_table(
        'scrape_jobs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('total_days', sa.Integer(), nullable=False),
        sa.Column('scraped_days', sa.Integer(), nullable=False),
        sa.Column('skipped_days', sa.Integer(), nullable=False),
        sa.Column('failed_days', sa.Integer(), nullable=False),
        sa.Column('error_log', sa.Text(), nullable=True),
        sa.Column('started_at', postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('completed_at', postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )

    # Create scrape_logs table
    op.create_table(
        'scrape_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('job_id', sa.Integer(), nullable=True),
        sa.Column('draw_date', sa.Date(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('source', sa.String(length=50), nullable=True),
        sa.Column('source_url', sa.Text(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=False),
        sa.Column('response_time_ms', sa.Integer(), nullable=True),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['job_id'], ['scrape_jobs.id']),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('scrape_logs')
    op.drop_table('scrape_jobs')
    op.drop_index('idx_xsmb_year_month', table_name='xsmb_results')
    op.drop_index('idx_xsmb_day_of_week', table_name='xsmb_results')
    op.drop_index('idx_xsmb_de_dau', table_name='xsmb_results')
    op.drop_index('idx_xsmb_giai_db', table_name='xsmb_results')
    op.drop_index('idx_xsmb_draw_date', table_name='xsmb_results')
    op.drop_table('xsmb_results')
