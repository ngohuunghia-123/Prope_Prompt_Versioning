"""Add immutable source and conversion provenance to registry revisions.

Revision ID: 0013
Revises: 0012
"""

from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE registry.revision ADD COLUMN original_body text")
    op.execute("ALTER TABLE registry.revision ADD COLUMN original_format text")
    op.execute("ALTER TABLE registry.revision ADD COLUMN original_filename text")
    op.execute("ALTER TABLE registry.revision ADD COLUMN conversion_model text")
    op.execute("ALTER TABLE registry.revision ADD COLUMN conversion_schema_version text")
    op.execute(
        "UPDATE registry.revision SET original_body = body, original_format = 'legacy'"
    )
    op.execute("ALTER TABLE registry.revision ALTER COLUMN original_body SET NOT NULL")
    op.execute("ALTER TABLE registry.revision ALTER COLUMN original_format SET NOT NULL")
    op.execute(
        "ALTER TABLE registry.revision ADD CONSTRAINT ck_revision_original_body_length "
        "CHECK (char_length(original_body) <= 32768)"
    )
    op.execute(
        "ALTER TABLE registry.revision ADD CONSTRAINT ck_revision_original_format "
        "CHECK (original_format IN ('legacy', 'xml', 'txt', 'markdown', 'json', 'yaml'))"
    )
    op.execute(
        "ALTER TABLE registry.revision ADD CONSTRAINT ck_revision_original_filename "
        "CHECK (original_filename IS NULL OR (char_length(original_filename) BETWEEN 1 AND 255 "
        "AND original_filename !~ '[\\\\/]'))"
    )
    op.execute(
        "ALTER TABLE registry.revision ADD CONSTRAINT ck_revision_conversion_is_whole "
        "CHECK ((conversion_model IS NULL) = (conversion_schema_version IS NULL))"
    )
    op.execute(
        "ALTER TABLE registry.revision ADD CONSTRAINT ck_revision_conversion_matches_format "
        "CHECK ((original_format IN ('legacy', 'xml') AND conversion_model IS NULL) OR "
        "(original_format IN ('txt', 'markdown', 'json', 'yaml') AND conversion_model IS NOT NULL))"
    )
    op.execute(
        """
        CREATE FUNCTION registry.revision_defaults_direct_xml_provenance() RETURNS trigger
        LANGUAGE plpgsql
        AS $function$
        BEGIN
            IF NEW.original_body IS NULL THEN
                NEW.original_body := NEW.body;
            END IF;
            IF NEW.original_format IS NULL THEN
                NEW.original_format := 'xml';
            END IF;
            RETURN NEW;
        END;
        $function$
        """
    )
    op.execute(
        "CREATE TRIGGER revision_defaults_direct_xml_provenance "
        "BEFORE INSERT ON registry.revision FOR EACH ROW "
        "EXECUTE FUNCTION registry.revision_defaults_direct_xml_provenance()"
    )
    op.execute(
        "REVOKE ALL ON FUNCTION registry.revision_defaults_direct_xml_provenance() FROM PUBLIC"
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS revision_defaults_direct_xml_provenance ON registry.revision"
    )
    op.execute(
        "DROP FUNCTION IF EXISTS registry.revision_defaults_direct_xml_provenance()"
    )
    op.execute(
        "ALTER TABLE registry.revision DROP CONSTRAINT IF EXISTS ck_revision_conversion_matches_format"
    )
    op.execute(
        "ALTER TABLE registry.revision DROP CONSTRAINT IF EXISTS ck_revision_conversion_is_whole"
    )
    op.execute(
        "ALTER TABLE registry.revision DROP CONSTRAINT IF EXISTS ck_revision_original_filename"
    )
    op.execute(
        "ALTER TABLE registry.revision DROP CONSTRAINT IF EXISTS ck_revision_original_format"
    )
    op.execute(
        "ALTER TABLE registry.revision DROP CONSTRAINT IF EXISTS ck_revision_original_body_length"
    )
    op.execute("ALTER TABLE registry.revision DROP COLUMN conversion_schema_version")
    op.execute("ALTER TABLE registry.revision DROP COLUMN conversion_model")
    op.execute("ALTER TABLE registry.revision DROP COLUMN original_filename")
    op.execute("ALTER TABLE registry.revision DROP COLUMN original_format")
    op.execute("ALTER TABLE registry.revision DROP COLUMN original_body")
