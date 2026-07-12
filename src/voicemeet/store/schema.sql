CREATE TABLE IF NOT EXISTS sessions (
    id            TEXT PRIMARY KEY,
    title         TEXT,
    started_at    TEXT NOT NULL,
    ended_at      TEXT,
    duration_s    REAL DEFAULT 0,
    participants  TEXT DEFAULT '[]',
    topics        TEXT DEFAULT '[]',
    raw_audio_path TEXT,
    status        TEXT NOT NULL DEFAULT 'recording',
    summary_markdown TEXT,
    mode          TEXT NOT NULL DEFAULT 'room'
);

CREATE TABLE IF NOT EXISTS segments (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT NOT NULL,
    idx         INTEGER NOT NULL,
    start_ms    INTEGER NOT NULL,
    end_ms      INTEGER NOT NULL,
    text        TEXT NOT NULL DEFAULT '',
    speaker     TEXT,
    confidence  REAL,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_segments_session ON segments(session_id);

CREATE TABLE IF NOT EXISTS exports (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT NOT NULL,
    format      TEXT NOT NULL,
    path        TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_exports_session ON exports(session_id);
