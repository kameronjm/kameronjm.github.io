"""add_model_config_and_coefficients

Revision ID: 3cc648ecef4a
Revises: 5eb88cfe79cf
Create Date: 2026-06-08 17:52:12.240260

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import Text
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '3cc648ecef4a'
down_revision: Union[str, Sequence[str], None] = '5eb88cfe79cf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('custom_model_configurations',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(length=150), nullable=False),
    sa.Column('league', sa.String(length=10), nullable=False),
    sa.Column('target_type', sa.String(length=30), nullable=False, comment='regression or classification'),
    sa.Column('target_stat', sa.String(length=100), nullable=False, comment='The outcome variable: e.g. total_points, win, over_under'),
    sa.Column('feature_list', postgresql.JSON(astext_type=Text()), nullable=False, comment='JSON array of feature key strings selected for this model'),
    sa.Column('rolling_window', sa.Integer(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_model_config_league_active', 'custom_model_configurations', ['league', 'is_active'], unique=False)
    op.create_table('model_coefficients',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('config_id', sa.UUID(), nullable=False),
    sa.Column('intercept', sa.Float(), nullable=False),
    sa.Column('weights', postgresql.JSON(astext_type=Text()), nullable=False, comment='Map of feature_name -> coefficient beta_n'),
    sa.Column('r_value', sa.Float(), nullable=True),
    sa.Column('test_loss', sa.Float(), nullable=True),
    sa.Column('train_samples', sa.Integer(), nullable=True),
    sa.Column('test_samples', sa.Integer(), nullable=True),
    sa.Column('metadata_extra', postgresql.JSON(astext_type=Text()), nullable=True, comment='Scaler params, feature means, etc.'),
    sa.Column('trained_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['config_id'], ['custom_model_configurations.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_coefficients_config', 'model_coefficients', ['config_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_coefficients_config', table_name='model_coefficients')
    op.drop_table('model_coefficients')
    op.drop_index('ix_model_config_league_active', table_name='custom_model_configurations')
    op.drop_table('custom_model_configurations')
