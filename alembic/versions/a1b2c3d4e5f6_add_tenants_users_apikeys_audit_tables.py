"""add_tenants_users_apikeys_audit_tables

Revision ID: a1b2c3d4e5f6
Revises: 520660ac8f99
Create Date: 2026-06-11

Adds enterprise-grade tables:
- tenants: multi-tenancy isolation
- users: user accounts with roles/scopes
- api_keys: API key hash authentication
- policy_audit_logs: immutable audit trail
- tool_calls: agent tool execution audit
"""
from alembic import op
import sqlalchemy as sa

revision = 'a1b2c3d4e5f6'
down_revision = '1070839c1c30'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── tenants ──
    op.create_table(
        'tenants',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(200), nullable=False, unique=True),
        sa.Column('display_name', sa.String(500), nullable=False, server_default=''),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('1')),
        sa.Column('config_json', sa.Text()),
        sa.Column('max_users', sa.Integer()),
        sa.Column('max_documents', sa.Integer()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_tenants_name', 'tenants', ['name'])

    # ── users ──
    op.create_table(
        'users',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('tenant_id', sa.String(36), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('username', sa.String(200), nullable=False),
        sa.Column('email', sa.String(300)),
        sa.Column('password_hash', sa.String(256)),
        sa.Column('roles_json', sa.Text(), nullable=False, server_default='[]'),
        sa.Column('scopes_json', sa.Text(), nullable=False, server_default='[]'),
        sa.Column('department', sa.String(200)),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('1')),
        sa.Column('last_login_at', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_users_tenant_id', 'users', ['tenant_id'])
    op.create_index('ix_users_username', 'users', ['username'])

    # ── api_keys ──
    op.create_table(
        'api_keys',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('tenant_id', sa.String(36), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('key_hash', sa.String(64), nullable=False, unique=True),
        sa.Column('key_prefix', sa.String(8), nullable=False),
        sa.Column('name', sa.String(200), nullable=False, server_default=''),
        sa.Column('scopes_json', sa.Text(), nullable=False, server_default='[]'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('1')),
        sa.Column('expires_at', sa.DateTime(timezone=True)),
        sa.Column('last_used_at', sa.DateTime(timezone=True)),
        sa.Column('rate_limit_rpm', sa.Integer()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_api_keys_user_id', 'api_keys', ['user_id'])
    op.create_index('ix_api_keys_tenant_id', 'api_keys', ['tenant_id'])
    op.create_index('ix_api_keys_key_hash', 'api_keys', ['key_hash'])

    # ── policy_audit_logs ──
    op.create_table(
        'policy_audit_logs',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('tenant_id', sa.String(100), nullable=False),
        sa.Column('user_id', sa.String(36)),
        sa.Column('event_type', sa.String(50), nullable=False),
        sa.Column('action', sa.String(100), nullable=False),
        sa.Column('resource_type', sa.String(100)),
        sa.Column('resource_id', sa.String(100)),
        sa.Column('detail_json', sa.Text()),
        sa.Column('risk_level', sa.String(20)),
        sa.Column('ip_address', sa.String(45)),
        sa.Column('user_agent', sa.String(500)),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_policy_audit_logs_tenant_id', 'policy_audit_logs', ['tenant_id'])
    op.create_index('ix_policy_audit_logs_event_type', 'policy_audit_logs', ['event_type'])
    op.create_index('ix_policy_audit_logs_created_at', 'policy_audit_logs', ['created_at'])

    # ── tool_calls ──
    op.create_table(
        'tool_calls',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('run_id', sa.String(36)),
        sa.Column('tenant_id', sa.String(100), nullable=False),
        sa.Column('tool_name', sa.String(100), nullable=False),
        sa.Column('params_json', sa.Text()),
        sa.Column('result_json', sa.Text()),
        sa.Column('success', sa.Boolean(), nullable=False, server_default=sa.text('1')),
        sa.Column('error_message', sa.Text()),
        sa.Column('permission_result', sa.String(20)),
        sa.Column('permission_reason', sa.String(500)),
        sa.Column('idempotency_key', sa.String(64)),
        sa.Column('latency_ms', sa.Float(), server_default='0.0'),
        sa.Column('retry_count', sa.Integer(), server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_tool_calls_run_id', 'tool_calls', ['run_id'])
    op.create_index('ix_tool_calls_tenant_id', 'tool_calls', ['tenant_id'])
    op.create_index('ix_tool_calls_tool_name', 'tool_calls', ['tool_name'])
    op.create_index('ix_tool_calls_idempotency_key', 'tool_calls', ['idempotency_key'])
    op.create_index('ix_tool_calls_created_at', 'tool_calls', ['created_at'])


def downgrade() -> None:
    op.drop_table('tool_calls')
    op.drop_table('policy_audit_logs')
    op.drop_table('api_keys')
    op.drop_table('users')
    op.drop_table('tenants')
