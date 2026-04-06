"""Initial migration — all tables for CHC Backend MVP.

Revision ID: 001_initial
Create Date: 2026-04-06
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Tenants
    op.create_table('tenants',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('tenant_code', sa.String(50), unique=True, nullable=False),
        sa.Column('subdomain', sa.String(100), unique=True, nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('logo_s3_key', sa.String(500), nullable=True),
        sa.Column('primary_color', sa.String(7), nullable=True),
        sa.Column('display_name', sa.String(255), nullable=True),
        sa.Column('custom_email_domain', sa.String(255), nullable=True),
        sa.Column('etariff_daily_limit', sa.Integer(), default=10),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )

    # Tenant email configs
    op.create_table('tenant_email_configs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('tenant_id', sa.Integer(), sa.ForeignKey('tenants.id'), unique=True, nullable=False),
        sa.Column('smtp_host', sa.String(255), nullable=False),
        sa.Column('smtp_port', sa.Integer(), default=587),
        sa.Column('sender_email', sa.String(255), nullable=False),
        sa.Column('sender_name', sa.String(255), nullable=False),
        sa.Column('smtp_username', sa.String(255), nullable=False),
        sa.Column('smtp_password', sa.String(500), nullable=False),
        sa.Column('is_enabled', sa.Boolean(), default=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )

    # Users
    op.create_table('users',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('tenant_id', sa.Integer(), sa.ForeignKey('tenants.id'), nullable=True),
        sa.Column('email', sa.String(255), unique=True, nullable=False),
        sa.Column('password_hash', sa.String(255), nullable=False),
        sa.Column('full_name', sa.String(255), nullable=False),
        sa.Column('username', sa.String(100), unique=True, nullable=True),
        sa.Column('role', sa.Enum('super_admin', 'tenant_admin', 'expert', 'user', name='userrole'), nullable=False),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('is_first_login', sa.Boolean(), default=True),
        sa.Column('company_name', sa.String(255), nullable=True),
        sa.Column('tax_code', sa.String(20), nullable=True),
        sa.Column('company_address', sa.Text(), nullable=True),
        sa.Column('contact_person', sa.String(255), nullable=True),
        sa.Column('phone', sa.String(20), nullable=True),
        sa.Column('contact_email', sa.String(255), nullable=True),
        sa.Column('industry', sa.String(255), nullable=True),
        sa.Column('company_type', sa.String(50), nullable=True),
        sa.Column('locale', sa.String(5), default='vi'),
        sa.Column('login_attempts', sa.Integer(), default=0),
        sa.Column('locked_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )

    # Password reset tokens
    op.create_table('password_reset_tokens',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('token', sa.String(255), unique=True, nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )

    # Requests (CHC orders + E-Tariff)
    op.create_table('requests',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('tenant_id', sa.Integer(), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('display_id', sa.String(50), unique=True, nullable=False),
        sa.Column('type', sa.Enum('chc', 'etariff_manual', 'etariff_batch', name='requesttype'), nullable=False),
        sa.Column('status', sa.Enum('pending', 'processing', 'completed', 'delivered', 'cancelled', name='requeststatus'), default='pending'),
        sa.Column('chc_modules', postgresql.ARRAY(sa.String(50)), nullable=True),
        sa.Column('assigned_expert_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('assigned_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('manual_input_data', sa.Text(), nullable=True),
        sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('delivered_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('admin_notes', sa.Text(), nullable=True),
    )

    # Request files
    op.create_table('request_files',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('request_id', sa.Integer(), sa.ForeignKey('requests.id'), nullable=False),
        sa.Column('original_filename', sa.String(255), nullable=False),
        sa.Column('s3_key', sa.String(500), nullable=True),
        sa.Column('file_size', sa.Integer(), nullable=True),
        sa.Column('ai_status', sa.String(20), default='not_started'),
        sa.Column('ai_s3_key', sa.String(500), nullable=True),
        sa.Column('expert_s3_key', sa.String(500), nullable=True),
        sa.Column('expert_pdf_s3_key', sa.String(500), nullable=True),
        sa.Column('reviewed_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('request_files')
    op.drop_table('requests')
    op.drop_table('password_reset_tokens')
    op.drop_table('users')
    op.drop_table('tenant_email_configs')
    op.drop_table('tenants')
    op.execute("DROP TYPE IF EXISTS userrole")
    op.execute("DROP TYPE IF EXISTS requesttype")
    op.execute("DROP TYPE IF EXISTS requeststatus")
