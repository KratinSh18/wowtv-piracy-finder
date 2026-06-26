"""
SQLite-backed fingerprint store -- this is your "reference catalog" of WOW TV
content. Audio landmark hashes are indexed for fast inverted lookup (the same
idea Shazam uses to search millions of tracks in milliseconds).

Tables:
  works         one row per reference clip you ingest (title, path, duration)
  audio_hashes  (hash, work_id, offset_frame)   -- indexed on `hash`
  video_hashes  (work_id, t_seconds, phash_hex) -- indexed on `work_id`
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from . import config

_SCHEMA = """
CREATE TABLE IF NOT EXISTS works (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    title     TEXT NOT NULL,
    path      TEXT,
    duration  REAL,
    kind      TEXT,
    created   TEXT
);
CREATE TABLE IF NOT EXISTS audio_hashes (
    hash      INTEGER NOT NULL,
    work_id   INTEGER NOT NULL,
    offset    INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS video_hashes (
    work_id   INTEGER NOT NULL,
    t         REAL NOT NULL,
    phash     TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS detections (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    source        TEXT NOT NULL,
    platform      TEXT,
    work_id       INTEGER,
    matched_title TEXT,
    verdict       TEXT,
    confidence    REAL,
    offset_sec    REAL,
    video_overlap REAL,
    detected_speed REAL,
    sha256        TEXT,
    first_seen    TEXT,
    last_seen     TEXT,
    UNIQUE(source, work_id)
);
CREATE INDEX IF NOT EXISTS idx_audio_hash  ON audio_hashes(hash);
CREATE INDEX IF NOT EXISTS idx_video_work  ON video_hashes(work_id);
CREATE INDEX IF NOT EXISTS idx_det_platform ON detections(platform);
"""


class FingerprintDB:
    def __init__(self, path: str = config.DB_DEFAULT):
        self.path = path
        self.conn = sqlite3.connect(path)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self.conn.executescript(_SCHEMA)
        self.conn.commit()

    # -- writes ------------------------------------------------------------
    def add_work(self, title, path, duration, kind="reference") -> int:
        cur = self.conn.execute(
            "INSERT INTO works(title, path, duration, kind, created) VALUES(?,?,?,?,?)",
            (title, str(path) if path else None, float(duration or 0.0), kind,
             datetime.now(timezone.utc).isoformat(timespec="seconds")),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def add_audio_hashes(self, work_id: int, hashes):
        self.conn.executemany(
            "INSERT INTO audio_hashes(hash, work_id, offset) VALUES(?,?,?)",
            ((int(h), work_id, int(t)) for h, t in hashes),
        )
        self.conn.commit()

    def add_video_hashes(self, work_id: int, vhashes):
        self.conn.executemany(
            "INSERT INTO video_hashes(work_id, t, phash) VALUES(?,?,?)",
            ((work_id, float(t), format(int(h), "016x")) for t, h in vhashes),
        )
        self.conn.commit()

    def add_detection(self, rec: dict):
        """Insert or update (by source+work) a confirmed detection. Builds a
        case history across many platforms over time without duplicates."""
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self.conn.execute(
            """
            INSERT INTO detections
              (source, platform, work_id, matched_title, verdict, confidence,
               offset_sec, video_overlap, detected_speed, sha256, first_seen, last_seen)
            VALUES (:source, :platform, :work_id, :matched_title, :verdict, :confidence,
               :offset_sec, :video_overlap, :detected_speed, :sha256, :now, :now)
            ON CONFLICT(source, work_id) DO UPDATE SET
               platform=excluded.platform, matched_title=excluded.matched_title,
               verdict=excluded.verdict, confidence=excluded.confidence,
               offset_sec=excluded.offset_sec, video_overlap=excluded.video_overlap,
               detected_speed=excluded.detected_speed, sha256=excluded.sha256,
               last_seen=excluded.last_seen
            """,
            {**rec, "now": now},
        )
        self.conn.commit()

    def list_detections(self, platform: str | None = None):
        q = ("SELECT source, platform, matched_title, verdict, confidence, "
             "offset_sec, video_overlap, detected_speed, sha256, first_seen, last_seen "
             "FROM detections")
        params = ()
        if platform:
            q += " WHERE platform=?"
            params = (platform,)
        q += " ORDER BY confidence DESC, last_seen DESC"
        keys = ("source", "platform", "matched_title", "verdict", "confidence",
                "offset_sec", "video_overlap", "detected_speed", "sha256",
                "first_seen", "last_seen")
        return [dict(zip(keys, r)) for r in self.conn.execute(q, params).fetchall()]

    def remove_work(self, work_id: int):
        for tbl in ("audio_hashes", "video_hashes", "detections"):
            self.conn.execute(f"DELETE FROM {tbl} WHERE work_id=?", (work_id,))
        self.conn.execute("DELETE FROM works WHERE id=?", (work_id,))
        self.conn.commit()

    # -- reads -------------------------------------------------------------
    def lookup_audio_batch(self, hashes) -> dict:
        """hash -> [(work_id, offset_frame), ...] for the given query hashes."""
        uniq = list({int(h) for h in hashes})
        out: dict = {}
        cur = self.conn.cursor()
        CHUNK = 900  # stay under SQLite's variable limit
        for i in range(0, len(uniq), CHUNK):
            chunk = uniq[i:i + CHUNK]
            q = "SELECT hash, work_id, offset FROM audio_hashes WHERE hash IN (%s)" % \
                ",".join("?" * len(chunk))
            for h, w, o in cur.execute(q, chunk):
                out.setdefault(h, []).append((w, o))
        return out

    def video_hashes(self, work_id: int):
        cur = self.conn.execute(
            "SELECT t, phash FROM video_hashes WHERE work_id=?", (work_id,)
        )
        return [(t, int(p, 16)) for t, p in cur.fetchall()]

    def get_work(self, work_id: int):
        cur = self.conn.execute(
            "SELECT id, title, path, duration, kind, created FROM works WHERE id=?",
            (work_id,),
        )
        row = cur.fetchone()
        if not row:
            return None
        keys = ("id", "title", "path", "duration", "kind", "created")
        return dict(zip(keys, row))

    def list_works(self):
        cur = self.conn.execute(
            "SELECT id, title, path, duration, kind, created FROM works ORDER BY id"
        )
        keys = ("id", "title", "path", "duration", "kind", "created")
        return [dict(zip(keys, r)) for r in cur.fetchall()]

    def stats(self) -> dict:
        c = self.conn
        return {
            "works": c.execute("SELECT COUNT(*) FROM works").fetchone()[0],
            "audio_hashes": c.execute("SELECT COUNT(*) FROM audio_hashes").fetchone()[0],
            "video_hashes": c.execute("SELECT COUNT(*) FROM video_hashes").fetchone()[0],
            "detections": c.execute("SELECT COUNT(*) FROM detections").fetchone()[0],
        }

    def close(self):
        self.conn.close()
