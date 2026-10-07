"""Knowledge base: sources, versions, chunks, embeddings (data-model.md §4.7, data-pipeline.md, ADR-0014).

Revision ID: 0007_knowledge
Revises: 0006_invitation_expiry_backstop
Create Date: 2026-10-07

Global tables (no org_id, no RLS): public legal text, written only by app_ingest (the ingestion CLI) and read by
the services. Nothing is ever deleted: superseding a version flips `status` and `is_active`, and DELETE/TRUNCATE
are revoked from every role that can connect, so citations keep resolving to the exact version cited.
`pending_review` versions (OCR'd or publisher-OCR pages below the S1 confidence threshold) are inactive until
approved. Embeddings: bge-base-en-v1.5 int8, D = 768 (S2); HNSW m=16, ef_construction=64.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0007_knowledge"
down_revision: str | None = "0006_invitation_expiry_backstop"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = (
    "knowledge.sources, knowledge.source_versions, knowledge.chunks, knowledge.chunk_embeddings"
)


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE knowledge.sources (
            id uuid PRIMARY KEY,
            key text NOT NULL UNIQUE CHECK (key ~ '^[a-z][a-z0-9_]{2,62}$'),
            title text NOT NULL,
            authority text NOT NULL,
            jurisdiction text NOT NULL CHECK (jurisdiction IN ('IN', 'IN-TG')),
            doc_type text NOT NULL CHECK (doc_type IN
                ('act', 'rules', 'notification', 'circular', 'form_instructions', 'guidance')),
            official_url text NOT NULL CHECK (official_url ~ '^https://')
        )
        """
    )
    op.execute(
        """
        CREATE TABLE knowledge.source_versions (
            id uuid PRIMARY KEY,
            source_id uuid NOT NULL REFERENCES knowledge.sources (id) ON DELETE RESTRICT,
            version int NOT NULL CHECK (version > 0),
            content_sha256 text NOT NULL CHECK (content_sha256 ~ '^[0-9a-f]{64}$'),
            storage_key text NOT NULL,
            published_on date NULL,
            effective_from date NOT NULL,
            effective_to date NULL CHECK (effective_to IS NULL OR effective_to > effective_from),
            parser text NOT NULL,
            status text NOT NULL CHECK (status IN ('active', 'superseded', 'pending_review')),
            review jsonb NOT NULL DEFAULT '{}' CHECK (jsonb_typeof(review) = 'object'),
            fetched_at timestamptz NOT NULL,
            UNIQUE (source_id, version)
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX source_versions_one_active_idx ON knowledge.source_versions (source_id) "
        "WHERE status = 'active'"
    )
    op.execute(
        """
        CREATE TABLE knowledge.chunks (
            id uuid PRIMARY KEY,
            source_version_id uuid NOT NULL REFERENCES knowledge.source_versions (id) ON DELETE RESTRICT,
            parent_id uuid NULL REFERENCES knowledge.chunks (id) ON DELETE RESTRICT,
            kind text NOT NULL CHECK (kind IN ('section', 'annex', 'table', 'parent')),
            section_path text NOT NULL,
            node_paths text[] NOT NULL,
            heading text NOT NULL,
            ordinal int NOT NULL CHECK (ordinal >= 0),
            text text NOT NULL,
            token_count int NOT NULL CHECK (token_count > 0),
            jurisdiction text NOT NULL CHECK (jurisdiction IN ('IN', 'IN-TG')),
            doc_type text NOT NULL,
            effective_from date NOT NULL,
            effective_to date NULL,
            is_active bool NOT NULL,
            tsv tsvector GENERATED ALWAYS AS (to_tsvector('english', heading || ' ' || text)) STORED
        )
        """
    )
    op.execute("CREATE INDEX chunks_source_version_id_idx ON knowledge.chunks (source_version_id)")
    op.execute("CREATE INDEX chunks_parent_id_idx ON knowledge.chunks (parent_id)")
    op.execute(
        "CREATE INDEX chunks_filter_idx ON knowledge.chunks (is_active, jurisdiction, effective_from)"
    )
    op.execute("CREATE INDEX chunks_tsv_idx ON knowledge.chunks USING gin (tsv)")
    op.execute(
        """
        CREATE TABLE knowledge.chunk_embeddings (
            chunk_id uuid NOT NULL REFERENCES knowledge.chunks (id) ON DELETE RESTRICT,
            model_id text NOT NULL,
            embedding vector(768) NOT NULL,
            PRIMARY KEY (chunk_id, model_id)
        )
        """
    )
    op.execute(
        "CREATE INDEX chunk_embeddings_hnsw_idx ON knowledge.chunk_embeddings "
        "USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64)"
    )
    # Services read; only app_ingest writes; nobody deletes (citations must keep resolving).
    op.execute(f"REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON {TABLES} FROM app_api, app_worker")
    op.execute(f"GRANT SELECT ON {TABLES} TO app_api, app_worker")
    op.execute(f"REVOKE DELETE, TRUNCATE ON {TABLES} FROM app_ingest")
    op.execute(f"GRANT SELECT, INSERT, UPDATE ON {TABLES} TO app_ingest")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS knowledge.chunk_embeddings")
    op.execute("DROP TABLE IF EXISTS knowledge.chunks")
    op.execute("DROP TABLE IF EXISTS knowledge.source_versions")
    op.execute("DROP TABLE IF EXISTS knowledge.sources")
