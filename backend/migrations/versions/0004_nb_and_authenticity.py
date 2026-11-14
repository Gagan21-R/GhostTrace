"""naive bayes message classifications and message authenticity assessments

Revision ID: 0004
Revises: 0003
"""
from alembic import op
import sqlalchemy as sa


revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('message_classifications',
                    sa.Column('id', sa.String(length=32), nullable=False),
                    sa.Column('case_id', sa.String(length=32), sa.ForeignKey('cases.id', ondelete='CASCADE'), nullable=False),
                    sa.Column('evidence_id', sa.String(length=32), sa.ForeignKey('evidence.id', ondelete='CASCADE'), nullable=False),
                    sa.Column('segment_id', sa.String(length=32), nullable=True),
                    sa.Column('scope', sa.String(length=16), nullable=False),
                    sa.Column('locator', sa.String(length=128), nullable=False, server_default=''),
                    sa.Column('author', sa.String(length=255), nullable=True),
                    sa.Column('text', sa.Text(), nullable=False, server_default=''),
                    sa.Column('label', sa.String(length=32), nullable=False),
                    sa.Column('confidence', sa.Float(), nullable=False),
                    sa.Column('uncertain', sa.Boolean(), nullable=False, server_default=sa.false()),
                    sa.Column('probabilities', sa.JSON(), nullable=False),
                    sa.Column('top_terms', sa.JSON(), nullable=False),
                    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
                    sa.PrimaryKeyConstraint('id'))
    op.create_index('ix_message_classifications_case_id', 'message_classifications', ['case_id'])
    op.create_index('ix_message_classifications_evidence_id', 'message_classifications', ['evidence_id'])
    op.create_index('ix_message_classifications_label', 'message_classifications', ['label'])
    op.create_table('authenticity_assessments',
                    sa.Column('id', sa.String(length=32), nullable=False),
                    sa.Column('case_id', sa.String(length=32), sa.ForeignKey('cases.id', ondelete='CASCADE'), nullable=False),
                    sa.Column('run_id', sa.String(length=32), nullable=True),
                    sa.Column('evidence_id', sa.String(length=32), sa.ForeignKey('evidence.id', ondelete='CASCADE'), nullable=False),
                    sa.Column('disputed_text', sa.Text(), nullable=False),
                    sa.Column('claimed_sender', sa.String(length=255), nullable=True),
                    sa.Column('message_time', sa.String(length=64), nullable=True),
                    sa.Column('verdict', sa.String(length=40), nullable=False),
                    sa.Column('fabrication_score', sa.Float(), nullable=False, server_default='0'),
                    sa.Column('compromise_score', sa.Float(), nullable=False, server_default='0'),
                    sa.Column('indicators', sa.JSON(), nullable=False),
                    sa.Column('tool_trace', sa.JSON(), nullable=False),
                    sa.Column('recommendations', sa.JSON(), nullable=False),
                    sa.Column('summary', sa.Text(), nullable=False, server_default=''),
                    sa.Column('mode', sa.String(length=32), nullable=False, server_default='deterministic-planner'),
                    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
                    sa.PrimaryKeyConstraint('id'))
    op.create_index('ix_authenticity_assessments_case_id', 'authenticity_assessments', ['case_id'])
    op.create_index('ix_authenticity_assessments_evidence_id', 'authenticity_assessments', ['evidence_id'])


def downgrade() -> None:
    op.drop_table('authenticity_assessments')
    op.drop_table('message_classifications')
