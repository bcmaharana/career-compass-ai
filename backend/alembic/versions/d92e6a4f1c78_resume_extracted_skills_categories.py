"""resume extracted skills categories

Revision ID: d92e6a4f1c78
Revises: c3f8a217b4d6
Create Date: 2026-08-05 15:30:00.000000

Companion to c3f8a217b4d6 for `resumes.extracted_data` — a resume row is
write-once (per the domain's own docs) and stores the LLM's normalized
extraction verbatim in an opaque JSON blob, so ExtractedResumeData.skills'
shape change (flat string -> {"name", "category"} object, to carry a
per-item category through the review/merge flow) also needs a backfill
here. Without it, any resume parsed before this change (skills stored as
plain strings) would fail Pydantic validation on the next GET/merge call,
since ExtractedResumeData.skills now requires the object shape — caught
live by checking a real already-parsed resume against the new schema
before shipping, not by review.

Only rows whose `skills` array actually contains plain strings are
touched (a defensive check, not an assumption) — any resume already
matching the new object shape (parsed after this change ships) is left
alone.
"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'd92e6a4f1c78'
down_revision: str | None = 'c3f8a217b4d6'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    # resumes is tenant-owned with forced RLS (Phase 5 migration) —
    # Alembic has no app.tenant_id session context, same cross-tenant
    # backfill caveat as every other data migration in this codebase.
    op.execute("ALTER TABLE resumes DISABLE ROW LEVEL SECURITY")
    op.execute(
        """
        UPDATE resumes
        SET extracted_data = jsonb_set(
            extracted_data::jsonb,
            '{skills}',
            (
                SELECT COALESCE(
                    jsonb_agg(
                        CASE WHEN jsonb_typeof(elem) = 'string'
                             THEN jsonb_build_object('name', elem #>> '{}', 'category', NULL)
                             ELSE elem
                        END
                    ),
                    '[]'::jsonb
                )
                FROM jsonb_array_elements(extracted_data::jsonb -> 'skills') elem
            )
        )
        WHERE extracted_data IS NOT NULL
          AND jsonb_typeof(extracted_data::jsonb -> 'skills') = 'array'
          AND jsonb_array_length(extracted_data::jsonb -> 'skills') > 0
          AND EXISTS (
              SELECT 1
              FROM jsonb_array_elements(extracted_data::jsonb -> 'skills') e
              WHERE jsonb_typeof(e) = 'string'
          )
        """
    )
    op.execute("ALTER TABLE resumes ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE resumes FORCE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.execute("ALTER TABLE resumes DISABLE ROW LEVEL SECURITY")
    op.execute(
        """
        UPDATE resumes
        SET extracted_data = jsonb_set(
            extracted_data::jsonb,
            '{skills}',
            (
                SELECT COALESCE(
                    jsonb_agg(
                        CASE WHEN jsonb_typeof(elem) = 'object'
                             THEN elem -> 'name'
                             ELSE elem
                        END
                    ),
                    '[]'::jsonb
                )
                FROM jsonb_array_elements(extracted_data::jsonb -> 'skills') elem
            )
        )
        WHERE extracted_data IS NOT NULL
          AND jsonb_typeof(extracted_data::jsonb -> 'skills') = 'array'
          AND jsonb_array_length(extracted_data::jsonb -> 'skills') > 0
        """
    )
    op.execute("ALTER TABLE resumes ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE resumes FORCE ROW LEVEL SECURITY")
