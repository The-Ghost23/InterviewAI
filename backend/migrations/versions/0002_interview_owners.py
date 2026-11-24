"""Isolate interview ownership; legacy rows remain unassigned and private."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
revision = '0002_interview_owners'
down_revision = '0001_interview_history'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('interviews', sa.Column('owner_id', UUID(as_uuid=True), nullable=True), schema='interviewai')
    op.create_index('ix_interviewai_interviews_owner_id', 'interviews', ['owner_id'], schema='interviewai')
    # No new grants or Data API exposure. Policies constrain any future authenticated access.
    op.execute("CREATE POLICY own_interviews ON interviewai.interviews FOR ALL TO authenticated USING (owner_id = (select auth.uid())) WITH CHECK (owner_id = (select auth.uid()))")
    op.execute("CREATE POLICY own_turns ON interviewai.interview_turns FOR ALL TO authenticated USING (EXISTS (SELECT 1 FROM interviewai.interviews i WHERE i.id = interview_id AND i.owner_id = (select auth.uid()))) WITH CHECK (EXISTS (SELECT 1 FROM interviewai.interviews i WHERE i.id = interview_id AND i.owner_id = (select auth.uid())))")

def downgrade():
    op.execute('DROP POLICY own_turns ON interviewai.interview_turns')
    op.execute('DROP POLICY own_interviews ON interviewai.interviews')
    op.drop_index('ix_interviewai_interviews_owner_id', table_name='interviews', schema='interviewai')
    op.drop_column('interviews', 'owner_id', schema='interviewai')
