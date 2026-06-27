"""sprint5_partitioning

Revision ID: 9e8a56f2d2b5
Revises: 153ff2ab9b38
Create Date: 2026-06-26 13:25:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9e8a56f2d2b5'
down_revision: Union[str, None] = '153ff2ab9b38'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create audit_logs range-partitioned table
    op.execute("""
    CREATE TABLE audit_logs (
        id UUID NOT NULL,
        user_id UUID REFERENCES users(id) ON DELETE SET NULL,
        org_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
        ip_address VARCHAR(45),
        action VARCHAR(255) NOT NULL,
        resource VARCHAR(255),
        metadata_json TEXT,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
        PRIMARY KEY (id, created_at)
    ) PARTITION BY RANGE (created_at);
    """)

    # 2. Create default partition for audit_logs
    op.execute("""
    CREATE TABLE audit_logs_default PARTITION OF audit_logs DEFAULT;
    """)

    # 3. Create usage_metrics range-partitioned table
    op.execute("""
    CREATE TABLE usage_metrics (
        id UUID NOT NULL,
        org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
        metric_type VARCHAR(100) NOT NULL,
        value DOUBLE PRECISION NOT NULL,
        metadata_json TEXT,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
        PRIMARY KEY (id, created_at)
    ) PARTITION BY RANGE (created_at);
    """)

    # 4. Create default partition for usage_metrics
    op.execute("""
    CREATE TABLE usage_metrics_default PARTITION OF usage_metrics DEFAULT;
    """)

    # 5. Create PL/pgSQL function to dynamically build monthly partitions
    op.execute("""
    CREATE OR REPLACE FUNCTION create_monthly_partitions() RETURNS void AS $$
    DECLARE
        curr_month TIMESTAMP WITH TIME ZONE;
        next_month TIMESTAMP WITH TIME ZONE;
        curr_partition_name TEXT;
        next_partition_name TEXT;
        start_date TEXT;
        end_date TEXT;
    BEGIN
        -- Current Month Audit Logs
        curr_month := date_trunc('month', now());
        curr_partition_name := 'audit_logs_' || to_char(curr_month, 'YYYY_MM');
        start_date := to_char(curr_month, 'YYYY-MM-DD');
        end_date := to_char(curr_month + interval '1 month', 'YYYY-MM-DD');
        
        IF NOT EXISTS (SELECT 1 FROM pg_class WHERE relname = curr_partition_name) THEN
            EXECUTE format('CREATE TABLE %I PARTITION OF audit_logs FOR VALUES FROM (%L) TO (%L)', curr_partition_name, start_date, end_date);
        END IF;

        -- Next Month Audit Logs
        next_month := date_trunc('month', now() + interval '1 month');
        next_partition_name := 'audit_logs_' || to_char(next_month, 'YYYY_MM');
        start_date := to_char(next_month, 'YYYY-MM-DD');
        end_date := to_char(next_month + interval '1 month', 'YYYY-MM-DD');

        IF NOT EXISTS (SELECT 1 FROM pg_class WHERE relname = next_partition_name) THEN
            EXECUTE format('CREATE TABLE %I PARTITION OF audit_logs FOR VALUES FROM (%L) TO (%L)', next_partition_name, start_date, end_date);
        END IF;

        -- Current Month Usage Metrics
        curr_partition_name := 'usage_metrics_' || to_char(curr_month, 'YYYY_MM');
        start_date := to_char(curr_month, 'YYYY-MM-DD');
        end_date := to_char(curr_month + interval '1 month', 'YYYY-MM-DD');
        
        IF NOT EXISTS (SELECT 1 FROM pg_class WHERE relname = curr_partition_name) THEN
            EXECUTE format('CREATE TABLE %I PARTITION OF usage_metrics FOR VALUES FROM (%L) TO (%L)', curr_partition_name, start_date, end_date);
        END IF;

        -- Next Month Usage Metrics
        next_partition_name := 'usage_metrics_' || to_char(next_month, 'YYYY_MM');
        start_date := to_char(next_month, 'YYYY-MM-DD');
        end_date := to_char(next_month + interval '1 month', 'YYYY-MM-DD');

        IF NOT EXISTS (SELECT 1 FROM pg_class WHERE relname = next_partition_name) THEN
            EXECUTE format('CREATE TABLE %I PARTITION OF usage_metrics FOR VALUES FROM (%L) TO (%L)', next_partition_name, start_date, end_date);
        END IF;
    END;
    $$ LANGUAGE plpgsql;
    """)

    # 6. Initialize initial partitions immediately
    op.execute("SELECT create_monthly_partitions();")

    # 7. Safe pg_cron job schedule
    op.execute("""
    DO $$
    BEGIN
        IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_cron') THEN
            PERFORM cron.schedule('create-monthly-partitions-job', '0 0 1 * *', 'SELECT create_monthly_partitions();');
        END IF;
    EXCEPTION
        WHEN OTHERS THEN
            RAISE NOTICE 'Could not schedule partition creation job via pg_cron';
    END;
    $$;
    """)


def downgrade() -> None:
    # 1. Safe pg_cron job unschedule
    op.execute("""
    DO $$
    BEGIN
        IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_cron') THEN
            PERFORM cron.unschedule('create-monthly-partitions-job');
        END IF;
    EXCEPTION
        WHEN OTHERS THEN
            NULL;
    END;
    $$;
    """)

    # 2. Drop the PL/pgSQL function
    op.execute("DROP FUNCTION IF EXISTS create_monthly_partitions();")

    # 3. Drop tables (automatically drops active partitions)
    op.execute("DROP TABLE IF EXISTS usage_metrics_default;")
    op.execute("DROP TABLE IF EXISTS usage_metrics;")
    op.execute("DROP TABLE IF EXISTS audit_logs_default;")
    op.execute("DROP TABLE IF EXISTS audit_logs;")
