"""add_portfolio_and_placed_bets

Revision ID: 29673c4def17
Revises: 3cc648ecef4a
Create Date: 2026-06-08 18:22:26.995237

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '29673c4def17'
down_revision: Union[str, Sequence[str], None] = '3cc648ecef4a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('portfolios',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('starting_balance', sa.Float(), nullable=False),
    sa.Column('current_balance', sa.Float(), nullable=False),
    sa.Column('currency', sa.String(length=10), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('placed_bets',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('portfolio_id', sa.UUID(), nullable=False),
    sa.Column('ev_opportunity_id', sa.UUID(), nullable=False),
    sa.Column('model_id', sa.UUID(), nullable=True),
    sa.Column('stake_amount', sa.Float(), nullable=False),
    sa.Column('odds_taken', sa.Float(), nullable=False, comment='Decimal odds at time of placement'),
    sa.Column('status', sa.String(length=20), nullable=False, comment='PENDING, WON, LOST, PUSH'),
    sa.Column('pnl', sa.Float(), nullable=True),
    sa.Column('placed_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['ev_opportunity_id'], ['ev_opportunities.id'], ),
    sa.ForeignKeyConstraint(['model_id'], ['custom_model_configurations.id'], ),
    sa.ForeignKeyConstraint(['portfolio_id'], ['portfolios.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_placed_bets_portfolio', 'placed_bets', ['portfolio_id'], unique=False)
    op.create_index('ix_placed_bets_status', 'placed_bets', ['status'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_placed_bets_status', table_name='placed_bets')
    op.drop_index('ix_placed_bets_portfolio', table_name='placed_bets')
    op.drop_table('placed_bets')
    op.drop_table('portfolios')
