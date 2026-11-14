"""Hindi / Kannada translations of case title, description and objective

Revision ID: 0006
Revises: 0005
"""
from alembic import op
import sqlalchemy as sa


revision = '0006'
down_revision = '0005'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('cases') as b:
        b.add_column(sa.Column('translations', sa.JSON(), nullable=False, server_default='{}'))


def downgrade() -> None:
    with op.batch_alter_table('cases') as b:
        b.drop_column('translations')
