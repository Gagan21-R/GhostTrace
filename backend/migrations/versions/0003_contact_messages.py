"""contact messages from the public landing page

Revision ID: 0003
Revises: 0002
"""
from alembic import op
import sqlalchemy as sa


revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('contact_messages',
                    sa.Column('id', sa.String(length=32), nullable=False),
                    sa.Column('name', sa.String(length=120), nullable=False),
                    sa.Column('email', sa.String(length=254), nullable=False),
                    sa.Column('organisation', sa.String(length=160), nullable=False, server_default=''),
                    sa.Column('topic', sa.String(length=40), nullable=False, server_default='general'),
                    sa.Column('message', sa.Text(), nullable=False),
                    sa.Column('client_ip', sa.String(length=64), nullable=False, server_default=''),
                    sa.Column('status', sa.String(length=16), nullable=False, server_default='new'),
                    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
                    sa.PrimaryKeyConstraint('id'))
    op.create_index('ix_contact_messages_created_at', 'contact_messages', ['created_at'])


def downgrade() -> None:
    op.drop_index('ix_contact_messages_created_at', table_name='contact_messages')
    op.drop_table('contact_messages')
