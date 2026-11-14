"""alternative hypothesis testing engine: versioned analyses and investigator feedback

Revision ID: 0005
Revises: 0004
"""
from alembic import op
import sqlalchemy as sa


revision = '0005'
down_revision = '0004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('hypothesis_analyses',
                    sa.Column('id', sa.String(length=32), nullable=False),
                    sa.Column('case_id', sa.String(length=32), sa.ForeignKey('cases.id', ondelete='CASCADE'), nullable=False),
                    sa.Column('run_id', sa.String(length=32), nullable=True),
                    sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
                    sa.Column('trigger', sa.String(length=64), nullable=False, server_default='manual'),
                    *[sa.Column(c, sa.JSON(), nullable=False) for c in ('evidence_ids', 'question', 'hypotheses', 'matrix', 'counter',
                                                                         'comparison', 'next_evidence', 'review', 'changes', 'baseline')],
                    sa.Column('approval_status', sa.String(length=16), nullable=False, server_default='pending'),
                    sa.Column('approval_note', sa.Text(), nullable=True),
                    sa.Column('approved_by', sa.String(length=32), sa.ForeignKey('users.id'), nullable=True),
                    sa.Column('created_by', sa.String(length=32), sa.ForeignKey('users.id'), nullable=True),
                    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
                    sa.PrimaryKeyConstraint('id'))
    op.create_index('ix_hypothesis_analyses_case_id', 'hypothesis_analyses', ['case_id'])
    op.create_table('hypothesis_feedback',
                    sa.Column('id', sa.String(length=32), nullable=False),
                    sa.Column('case_id', sa.String(length=32), sa.ForeignKey('cases.id', ondelete='CASCADE'), nullable=False),
                    sa.Column('user_id', sa.String(length=32), sa.ForeignKey('users.id'), nullable=True),
                    sa.Column('hypothesis_id', sa.String(length=16), nullable=False),
                    sa.Column('action', sa.String(length=16), nullable=False),
                    sa.Column('payload', sa.JSON(), nullable=False),
                    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
                    sa.PrimaryKeyConstraint('id'))
    op.create_index('ix_hypothesis_feedback_case_id', 'hypothesis_feedback', ['case_id'])


def downgrade() -> None:
    op.drop_table('hypothesis_feedback')
    op.drop_table('hypothesis_analyses')
