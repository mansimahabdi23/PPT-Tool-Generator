"""PostgreSQL + pgvector asset store — production backend.

Activate by setting DATABASE_URL in the environment (or .env):
    DATABASE_URL=postgresql://user:pass@localhost:5432/imocha

Prerequisites
-------------
    # Install the Postgres extension (run once as superuser):
    psql -c "CREATE EXTENSION IF NOT EXISTS vector;"

    # Install Python packages (already in pyproject.toml):
    pip install psycopg2-binary pgvector

    # Run schema migration (see SCHEMA_SQL below or scripts/migrate_assets.py):
    python -m scripts.migrate_assets

Architecture (docs §9)
-----------------------
Only approved assets are ever indexed. "approved-only" is structural —
pending/deprecated records exist in the table but the retrieval query
filters by status='approved' before the vector operator runs.

The `embedding <=> query_vector` expression uses the pgvector cosine-distance
operator (<=>). Lower distance = higher relevance; ORDER BY ASC + LIMIT k.
"""

from __future__ import annotations

from typing import Any

from app.models.asset import BrandAsset, BrandAssetUpdate
from app.models.enums import AssetSlot, AssetStatus, AssetType
from app.services.asset_store import AssetRecord, EMBED_DIM, _embed, _to_brand_asset

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

SCHEMA_SQL = f"""
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS brand_assets (
    id            TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    type          TEXT NOT NULL,
    slot          TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'approved',
    version       TEXT NOT NULL DEFAULT 'v1.0',
    owner         TEXT NOT NULL DEFAULT 'Design',
    expires_at    TEXT,
    tags          TEXT[] NOT NULL DEFAULT '{{}}',
    thumbnail_url TEXT NOT NULL DEFAULT '',
    max_items     INTEGER,
    width_emu     INTEGER,
    height_emu    INTEGER,
    embedding     vector({EMBED_DIM}) NOT NULL
);

-- Partial index: only approved assets are ever retrieved.
-- Unapproved records physically cannot appear in retrieval results.
CREATE INDEX IF NOT EXISTS idx_assets_approved_slot
    ON brand_assets (slot)
    WHERE status = 'approved';
""".strip()


# ---------------------------------------------------------------------------
# PostgresAssetStore
# ---------------------------------------------------------------------------

class PostgresAssetStore:
    """Production asset store backed by PostgreSQL + pgvector.

    Parameters
    ----------
    conn : psycopg2 connection (caller manages pool / lifetime)

    Usage
    -----
    import psycopg2
    from pgvector.psycopg2 import register_vector

    conn = psycopg2.connect(DATABASE_URL)
    register_vector(conn)
    store = PostgresAssetStore(conn)
    store.setup_schema()          # idempotent, run once
    """

    def __init__(self, conn: Any) -> None:
        self._conn = conn

    def setup_schema(self) -> None:
        """Create extension + table (idempotent)."""
        with self._conn.cursor() as cur:
            cur.execute(SCHEMA_SQL)
        self._conn.commit()

    def put(self, record: AssetRecord) -> None:
        sql = """
            INSERT INTO brand_assets
                (id, name, type, slot, status, version, owner, expires_at,
                 tags, thumbnail_url, max_items, width_emu, height_emu, embedding)
            VALUES
                (%(id)s, %(name)s, %(type)s, %(slot)s, %(status)s, %(version)s,
                 %(owner)s, %(expires_at)s, %(tags)s, %(thumbnail_url)s,
                 %(max_items)s, %(width_emu)s, %(height_emu)s, %(embedding)s)
            ON CONFLICT (id) DO UPDATE SET
                name=EXCLUDED.name, type=EXCLUDED.type, slot=EXCLUDED.slot,
                status=EXCLUDED.status, version=EXCLUDED.version, owner=EXCLUDED.owner,
                expires_at=EXCLUDED.expires_at, tags=EXCLUDED.tags,
                thumbnail_url=EXCLUDED.thumbnail_url, max_items=EXCLUDED.max_items,
                width_emu=EXCLUDED.width_emu, height_emu=EXCLUDED.height_emu,
                embedding=EXCLUDED.embedding;
        """
        with self._conn.cursor() as cur:
            cur.execute(sql, {
                "id": record.id,
                "name": record.name,
                "type": record.type.value,
                "slot": record.slot.value,
                "status": record.status.value,
                "version": record.version,
                "owner": record.owner,
                "expires_at": record.expires_at,
                "tags": record.tags,
                "thumbnail_url": record.thumbnail_url,
                "max_items": record.max_items,
                "width_emu": record.width_emu,
                "height_emu": record.height_emu,
                "embedding": record.embedding,
            })
        self._conn.commit()

    def update(self, asset_id: str, patch: BrandAssetUpdate) -> AssetRecord:
        record = self.get(asset_id)
        if record is None:
            raise KeyError(f"Asset {asset_id!r} not found")
        from dataclasses import replace
        changes = {k: v for k, v in patch.model_dump().items() if v is not None}
        if "name" in changes or "tags" in changes:
            new_name = changes.get("name", record.name)
            new_tags = changes.get("tags", record.tags)
            changes["embedding"] = _embed(f"{new_name} {' '.join(new_tags)}")
        updated = replace(record, **changes)
        self.put(updated)
        return updated

    def get(self, asset_id: str) -> AssetRecord | None:
        sql = "SELECT * FROM brand_assets WHERE id = %s"
        with self._conn.cursor() as cur:
            cur.execute(sql, (asset_id,))
            row = cur.fetchone()
        return _row_to_record(cur, row) if row else None

    def list_all(
        self,
        type_filter: AssetType | None = None,
        status_filter: AssetStatus | None = None,
    ) -> list[BrandAsset]:
        conditions = []
        params: list[Any] = []
        if type_filter is not None:
            conditions.append(f"type = %s")
            params.append(type_filter.value)
        if status_filter is not None:
            conditions.append(f"status = %s")
            params.append(status_filter.value)
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        sql = f"SELECT * FROM brand_assets {where}"
        with self._conn.cursor() as cur:
            cur.execute(sql, params)
            cols = [d[0] for d in cur.description]
            rows = cur.fetchall()
        return [_to_brand_asset(_dict_to_record(dict(zip(cols, r)))) for r in rows]

    def retrieve(
        self,
        slot: AssetSlot,
        item_count: int | None = None,
        query_text: str = "",
        asset_type: AssetType | None = None,
        k: int = 5,
    ) -> list[BrandAsset]:
        """Deterministic filter → vector rank via pgvector <=> operator."""
        q_vec = _embed(query_text) if query_text.strip() else [0.0] * EMBED_DIM
        conditions = [
            "status = 'approved'",
            "slot = %(slot)s",
        ]
        params: dict[str, Any] = {"slot": slot.value, "k": k, "q_vec": q_vec}
        if item_count is not None:
            conditions.append("(max_items IS NULL OR max_items >= %(item_count)s)")
            params["item_count"] = item_count
        if asset_type is not None:
            conditions.append("type = %(asset_type)s")
            params["asset_type"] = asset_type.value
        where = " AND ".join(conditions)
        sql = f"""
            SELECT *, embedding <=> %(q_vec)s::vector AS _dist
            FROM brand_assets
            WHERE {where}
            ORDER BY _dist ASC
            LIMIT %(k)s;
        """
        with self._conn.cursor() as cur:
            cur.execute(sql, params)
            cols = [d[0] for d in cur.description if d[0] != "_dist"]
            rows = cur.fetchall()
        records = [_dict_to_record(dict(zip(cols, r[:len(cols)]))) for r in rows]
        return [_to_brand_asset(r) for r in records]

    def count(self) -> int:
        with self._conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM brand_assets")
            return cur.fetchone()[0]


# ---------------------------------------------------------------------------
# Row helpers
# ---------------------------------------------------------------------------

def _row_to_record(cur: Any, row: tuple) -> AssetRecord:
    cols = [d[0] for d in cur.description]
    return _dict_to_record(dict(zip(cols, row)))


def _dict_to_record(d: dict) -> AssetRecord:
    return AssetRecord(
        id=d["id"],
        name=d["name"],
        type=AssetType(d["type"]),
        slot=AssetSlot(d["slot"]),
        status=AssetStatus(d["status"]),
        version=d["version"],
        owner=d["owner"],
        expires_at=d.get("expires_at"),
        tags=list(d.get("tags") or []),
        thumbnail_url=d.get("thumbnail_url", ""),
        max_items=d.get("max_items"),
        width_emu=d.get("width_emu"),
        height_emu=d.get("height_emu"),
        embedding=list(d.get("embedding") or [0.0] * EMBED_DIM),
    )
