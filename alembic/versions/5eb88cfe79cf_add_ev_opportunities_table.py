"""add_ev_opportunities_table

Revision ID: 5eb88cfe79cf
Revises: 8834de17870f
Create Date: 2026-06-08 17:36:46.366939

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5eb88cfe79cf'
down_revision: Union[str, Sequence[str], None] = '8834de17870f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('ev_opportunities',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('fixture_id', sa.UUID(), nullable=False),
    sa.Column('market_odds_id', sa.UUID(), nullable=False),
    sa.Column('sportsbook', sa.String(length=50), nullable=False),
    sa.Column('market_type', sa.String(length=30), nullable=False),
    sa.Column('selection', sa.String(length=150), nullable=False),
    sa.Column('odds_american', sa.Integer(), nullable=False),
    sa.Column('implied_probability', sa.Float(), nullable=False),
    sa.Column('fair_probability', sa.Float(), nullable=False),
    sa.Column('edge', sa.Float(), nullable=False),
    sa.Column('ev_percentage', sa.Float(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('discovered_at', sa.DateTime(timezone=True),
              server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['fixture_id'], ['fixtures.id'], ),
    sa.ForeignKeyConstraint(['market_odds_id'], ['market_odds.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(
        'ix_ev_opps_active', 'ev_opportunities',
        ['is_active', 'ev_percentage'], unique=False,
    )
    op.create_index(
        'ix_ev_opps_fixture', 'ev_opportunities',
        ['fixture_id'], unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_ev_opps_fixture', table_name='ev_opportunities')
    op.drop_index('ix_ev_opps_active', table_name='ev_opportunities')
    op.drop_table('ev_opportunities')
