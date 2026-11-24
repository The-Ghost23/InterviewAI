"""Persistent interview sessions and evaluated turns in a private schema."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_interview_history"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute("REVOKE ALL ON SCHEMA interviewai FROM PUBLIC")
    op.create_table("interviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("role", sa.String(100), nullable=False),
        sa.Column("topic", sa.String(100), nullable=False),
        sa.Column("difficulty", sa.String(20), nullable=False),
        sa.Column("question_count", sa.Integer(), nullable=False),
        sa.Column("question_number", sa.Integer(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("model", sa.String(128), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="0"),
        sa.CheckConstraint("question_count BETWEEN 1 AND 10", name="question_count_range"),
        sa.CheckConstraint("question_number BETWEEN 1 AND question_count", name="question_number_range"),
        sa.CheckConstraint("status IN ('awaiting_answer', 'feedback', 'completed')", name="status_values"),
        sa.CheckConstraint("difficulty IN ('Beginner', 'Intermediate', 'Advanced')", name="difficulty_values"),
        sa.CheckConstraint("char_length(question) BETWEEN 1 AND 600", name="question_length"),
        sa.CheckConstraint("revision >= 0", name="nonnegative_revision"),
        schema="interviewai")
    op.create_index("ix_interviews_created_id", "interviews", [sa.text("created_at DESC"), sa.text("id DESC")], schema="interviewai")
    op.create_table("interview_turns",
        sa.Column("interview_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("interviewai.interviews.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("question_number", sa.Integer(), primary_key=True),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("feedback", postgresql.JSONB(), nullable=False),
        sa.CheckConstraint("question_number BETWEEN 1 AND 10", name="turn_number_range"),
        sa.CheckConstraint("char_length(answer) BETWEEN 2 AND 4000", name="answer_length"),
        sa.CheckConstraint("char_length(question) BETWEEN 1 AND 600", name="turn_question_length"),
        sa.CheckConstraint("jsonb_typeof(feedback) = 'object'", name="feedback_object"),
        schema="interviewai")
    for table in ("interviews", "interview_turns", "alembic_version"):
        op.execute(f"ALTER TABLE interviewai.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"REVOKE ALL ON TABLE interviewai.{table} FROM PUBLIC")


def downgrade():
    op.drop_table("interview_turns", schema="interviewai")
    op.drop_index("ix_interviews_created_id", table_name="interviews", schema="interviewai")
    op.drop_table("interviews", schema="interviewai")
