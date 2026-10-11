"""Initial schema setup with TimescaleDB compatibility

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-10-11 20:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. users table
    op.create_table(
        'users',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('locale', sa.String(length=10), nullable=False, server_default='en-US'),
        sa.Column('notification_prefs', sa.JSON(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_users_email', 'users', ['email'], unique=True)

    # 2. products table
    op.create_table(
        'products',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('canonical_key', sa.String(length=255), nullable=False),
        sa.Column('platform', sa.String(length=50), nullable=False),
        sa.Column('url', sa.Text(), nullable=False),
        sa.Column('title', sa.String(length=500), nullable=False),
        sa.Column('image_url', sa.Text(), nullable=True),
        sa.Column('currency', sa.String(length=10), nullable=False, server_default='USD'),
        sa.Column('region', sa.String(length=10), nullable=False, server_default='US'),
        sa.Column('category', sa.String(length=100), nullable=True),
        sa.Column('first_seen_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('poll_interval_s', sa.Integer(), nullable=False, server_default='21600'),
        sa.Column('next_poll_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('is_dormant', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('last_price', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('all_time_low', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('all_time_high', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('last_observed_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_products_canonical_key', 'products', ['canonical_key'], unique=True)
    op.create_index('ix_products_platform', 'products', ['platform'])
    op.create_index('ix_products_category', 'products', ['category'])
    op.create_index('ix_products_next_poll_at', 'products', ['next_poll_at'])

    # 3. subscriptions table
    op.create_table(
        'subscriptions',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('product_id', sa.String(length=36), nullable=False),
        sa.Column('target_price', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'product_id', name='uq_user_product_subscription')
    )
    op.create_index('ix_subscriptions_user_id', 'subscriptions', ['user_id'])
    op.create_index('ix_subscriptions_product_id', 'subscriptions', ['product_id'])
    op.create_index('ix_subscriptions_is_active', 'subscriptions', ['is_active'])

    # 4. alerts table
    op.create_table(
        'alerts',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('subscription_id', sa.String(length=36), nullable=False),
        sa.Column('fired_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('trigger_price', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('channel', sa.String(length=50), nullable=False),
        sa.Column('trigger_type', sa.String(length=50), nullable=False),
        sa.Column('is_read', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('idempotency_key', sa.String(length=255), nullable=False),
        sa.ForeignKeyConstraint(['subscription_id'], ['subscriptions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('idempotency_key')
    )
    op.create_index('ix_alerts_subscription_id', 'alerts', ['subscription_id'])
    op.create_index('ix_alerts_is_read', 'alerts', ['is_read'])

    # 5. price_history table
    op.create_table(
        'price_history',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('product_id', sa.String(length=36), nullable=False),
        sa.Column('observed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('price', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('currency', sa.String(length=10), nullable=False),
        sa.Column('availability', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('source_run_id', sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_price_history_product_observed', 'price_history', ['product_id', 'observed_at'])
    op.create_index('ix_price_history_observed_at', 'price_history', ['observed_at'])

    # 6. chat tables
    op.create_table(
        'chat_conversations',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False, server_default='New Chat'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_chat_conversations_user_id', 'chat_conversations', ['user_id'])

    op.create_table(
        'chat_messages',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('conversation_id', sa.String(length=36), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('sources', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['conversation_id'], ['chat_conversations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_chat_messages_conversation_id', 'chat_messages', ['conversation_id'])

    # TimescaleDB hypertable setup (runs if timescaledb extension is available)
    try:
        op.execute("SELECT create_hypertable('price_history', 'observed_at', if_not_exists => TRUE);")
    except Exception:
        pass


def downgrade() -> None:
    op.drop_table('chat_messages')
    op.drop_table('chat_conversations')
    op.drop_table('price_history')
    op.drop_table('alerts')
    op.drop_table('subscriptions')
    op.drop_table('products')
    op.drop_table('users')
