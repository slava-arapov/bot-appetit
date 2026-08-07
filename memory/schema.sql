CREATE TABLE IF NOT EXISTS users (
  user_id INTEGER PRIMARY KEY,
  username TEXT,
  status TEXT NOT NULL,              -- pending/approved/rejected
  requested_at TEXT,
  approved_at TEXT,
  rejected_at TEXT,
  rejection_notified INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS profiles (
  user_id INTEGER PRIMARY KEY REFERENCES users(user_id),
  onboarding_done INTEGER NOT NULL DEFAULT 0,
  onboarding_step INTEGER NOT NULL DEFAULT 0,
  servings TEXT,
  cooking_time TEXT,
  current_context_notes TEXT,
  current_context_updated TEXT
);

CREATE TABLE IF NOT EXISTS profile_tags (
  id INTEGER PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(user_id),
  kind TEXT NOT NULL,   -- likes / dislikes / restrictions / equipment
  value TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_profile_tags_user ON profile_tags(user_id, kind);

CREATE TABLE IF NOT EXISTS history (
  id INTEGER PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(user_id),
  dish TEXT NOT NULL,
  rating TEXT,
  date TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_history_user ON history(user_id, date);

CREATE TABLE IF NOT EXISTS pantry_items (
  id INTEGER PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(user_id),
  name TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'have',
  added_date TEXT,
  expiry_date TEXT,
  quantity TEXT
);
CREATE INDEX IF NOT EXISTS idx_pantry_user ON pantry_items(user_id);

CREATE TABLE IF NOT EXISTS context_messages (
  id INTEGER PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(user_id),
  role TEXT NOT NULL,
  content TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_context_user ON context_messages(user_id, id);

CREATE TABLE IF NOT EXISTS stats (
  key TEXT PRIMARY KEY,
  value INTEGER NOT NULL DEFAULT 0
);
