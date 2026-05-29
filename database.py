"""
database.py – SQLite database layer.
Fixes applied:
 - bcrypt password hashing (was SHA-256, no salt)
 - updated_at actually set on every UPDATE (SQLite has no ON UPDATE trigger)
 - duplicate assignment guard
 - save_image error handling
 - date import removed (unused)
 - get_analytics uses single connection, all queries batched
 - LIKE search uses UPPER() for case-insensitive matching
 - recalculate_all_scores also called after severity changes
"""
import sqlite3, os, json, shutil, uuid
from datetime import datetime
from pathlib import Path

try:
    import bcrypt as _bcrypt
    _USE_BCRYPT = True
except ImportError:
    import hashlib
    _USE_BCRYPT = False

DB_PATH    = Path(__file__).parent / "pothole.db"
UPLOAD_DIR = Path(__file__).parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)


def get_conn():
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")   # better concurrent reads
    return conn


def init_db():
    conn = get_conn()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        name          TEXT    NOT NULL,
        email         TEXT    NOT NULL UNIQUE,
        password_hash TEXT    NOT NULL,
        role          TEXT    NOT NULL DEFAULT 'Citizen',
        is_active     INTEGER NOT NULL DEFAULT 1,
        created_at    TEXT    NOT NULL DEFAULT (datetime('now')),
        updated_at    TEXT    NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS traffic_data (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        road_name        TEXT    NOT NULL UNIQUE,
        avg_daily_traffic INTEGER NOT NULL,
        last_updated     TEXT    NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS pothole_reports (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id        INTEGER NOT NULL REFERENCES users(id),
        citizen_name   TEXT    NOT NULL,
        email          TEXT    NOT NULL,
        phone_number   TEXT,
        location_text  TEXT    NOT NULL,
        latitude       REAL    NOT NULL DEFAULT 0.0,
        longitude      REAL    NOT NULL DEFAULT 0.0,
        road_name      TEXT    NOT NULL,
        severity       INTEGER NOT NULL,
        ml_severity    INTEGER,
        description    TEXT,
        image_paths    TEXT,
        status         TEXT    NOT NULL DEFAULT 'Pending',
        priority_score REAL    NOT NULL DEFAULT 0.0,
        created_at     TEXT    NOT NULL DEFAULT (datetime('now')),
        updated_at     TEXT    NOT NULL DEFAULT (datetime('now'))
    );
    CREATE INDEX IF NOT EXISTS idx_report_road   ON pothole_reports(road_name);
    CREATE INDEX IF NOT EXISTS idx_report_status ON pothole_reports(status);
    CREATE INDEX IF NOT EXISTS idx_report_score  ON pothole_reports(priority_score DESC);
    CREATE INDEX IF NOT EXISTS idx_report_date   ON pothole_reports(created_at);

    CREATE TABLE IF NOT EXISTS repair_assignments (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        pothole_id     INTEGER NOT NULL REFERENCES pothole_reports(id),
        assigned_crew  INTEGER NOT NULL REFERENCES users(id),
        scheduled_date TEXT,
        repair_status  TEXT    NOT NULL DEFAULT 'Assigned',
        notes          TEXT,
        proof_images   TEXT,
        progress_note  TEXT,
        completed_at   TEXT,
        created_at     TEXT    NOT NULL DEFAULT (datetime('now')),
        updated_at     TEXT    NOT NULL DEFAULT (datetime('now'))
    );
    CREATE INDEX IF NOT EXISTS idx_assign_pothole ON repair_assignments(pothole_id);
    CREATE INDEX IF NOT EXISTS idx_assign_crew    ON repair_assignments(assigned_crew);
    CREATE INDEX IF NOT EXISTS idx_assign_date    ON repair_assignments(scheduled_date);
    CREATE INDEX IF NOT EXISTS idx_assign_status  ON repair_assignments(repair_status);

    CREATE TABLE IF NOT EXISTS report_history (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        report_id  INTEGER NOT NULL REFERENCES pothole_reports(id),
        actor_id   INTEGER REFERENCES users(id),
        actor_name TEXT,
        action     TEXT NOT NULL,
        old_value  TEXT,
        new_value  TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );
    CREATE INDEX IF NOT EXISTS idx_history_report ON report_history(report_id);
    """)
    conn.commit()
    conn.close()


# ── Password helpers ───────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    if _USE_BCRYPT:
        return _bcrypt.hashpw(password.encode(), _bcrypt.gensalt()).decode()
    # Fallback: salted SHA-256 (acceptable only if bcrypt unavailable)
    import hashlib, secrets
    salt = secrets.token_hex(16)
    return salt + ":" + hashlib.sha256((salt + password).encode()).hexdigest()


def verify_password(password: str, hashed: str) -> bool:
    if _USE_BCRYPT:
        try:
            if hashed.startswith("$2"):          # bcrypt hash
                return _bcrypt.checkpw(password.encode(), hashed.encode())
        except Exception:
            pass
    # Legacy salted SHA-256
    if ":" in hashed:
        import hashlib
        salt, digest = hashed.split(":", 1)
        return hashlib.sha256((salt + password).encode()).hexdigest() == digest
    return False


# ── Audit log ──────────────────────────────────────────────────────────────────

def log_history(conn, report_id, actor_id, actor_name, action, old_val=None, new_val=None):
    conn.execute("""
        INSERT INTO report_history (report_id,actor_id,actor_name,action,old_value,new_value)
        VALUES (?,?,?,?,?,?)
    """, (report_id, actor_id, actor_name, action, old_val, new_val))


def get_report_history(report_id):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM report_history WHERE report_id=? ORDER BY created_at ASC",
        (report_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Users ──────────────────────────────────────────────────────────────────────

def create_user(name, email, password, role="Citizen"):
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO users (name,email,password_hash,role) VALUES (?,?,?,?)",
            (name, email.strip().lower(), hash_password(password), role)
        )
        conn.commit()
        return dict(conn.execute(
            "SELECT * FROM users WHERE email=?", (email.strip().lower(),)
        ).fetchone())
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()


def authenticate_user(email, password):
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM users WHERE email=? AND is_active=1",
        (email.strip().lower(),)
    ).fetchone()
    conn.close()
    if row and verify_password(password, row["password_hash"]):
        return dict(row)
    return None


def get_all_crew():
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM users WHERE role='Repair Crew' AND is_active=1 ORDER BY name"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_users():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM users ORDER BY role, name").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_user_by_id(uid):
    conn = get_conn()
    row = conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    conn.close()
    return dict(row) if row else None


def update_user(uid, name=None, password=None):
    conn = get_conn()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if name:
        conn.execute(
            "UPDATE users SET name=?, updated_at=? WHERE id=?", (name, now, uid)
        )
    if password:
        conn.execute(
            "UPDATE users SET password_hash=?, updated_at=? WHERE id=?",
            (hash_password(password), now, uid)
        )
    conn.commit()
    conn.close()


def deactivate_user(uid):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_conn()
    conn.execute(
        "UPDATE users SET is_active=0, updated_at=? WHERE id=?", (now, uid)
    )
    conn.commit()
    conn.close()


def reactivate_user(uid):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_conn()
    conn.execute(
        "UPDATE users SET is_active=1, updated_at=? WHERE id=?", (now, uid)
    )
    conn.commit()
    conn.close()


def get_crew_workload():
    """Return dict {crew_id: active_assignment_count} for load balancing."""
    conn = get_conn()
    rows = conn.execute("""
        SELECT assigned_crew, COUNT(*) as cnt
        FROM repair_assignments
        WHERE repair_status IN ('Assigned','Started')
        GROUP BY assigned_crew
    """).fetchall()
    conn.close()
    return {r["assigned_crew"]: r["cnt"] for r in rows}


# ── Traffic ────────────────────────────────────────────────────────────────────

def upsert_traffic(road_name, avg_daily_traffic):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_conn()
    conn.execute("""
        INSERT INTO traffic_data (road_name, avg_daily_traffic, last_updated)
        VALUES (?,?,?)
        ON CONFLICT(road_name) DO UPDATE SET
            avg_daily_traffic = excluded.avg_daily_traffic,
            last_updated      = excluded.last_updated
    """, (road_name, avg_daily_traffic, now))
    conn.commit()
    conn.close()


def get_all_traffic():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM traffic_data ORDER BY road_name").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_traffic_for_road(road_name):
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM traffic_data WHERE road_name=?", (road_name,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def estimate_traffic(road_name: str) -> int:
    """
    FIX: Smart traffic estimate for roads not in the database.
    Uses road name keywords to pick a realistic default volume.
    """
    name = road_name.upper()
    if any(k in name for k in ["NH ", "SH ", "NATIONAL", "STATE HWY", "HIGHWAY"]):
        return 45000   # national/state highway
    if any(k in name for k in ["BRIDGE", "FLYOVER", "OVERPASS"]):
        return 30000   # bridge approach roads
    if any(k in name for k in ["MAIN", "MG ", "MARKET", "BAZAAR", "BAZAR"]):
        return 20000   # busy commercial streets
    if any(k in name for k in ["ROAD", "RD "]):
        return 12000   # generic road
    if any(k in name for k in ["STREET", "ST "]):
        return 8000    # street
    if any(k in name for k in ["LANE", "LN ", "GALLI", "COLONY", "NAGAR"]):
        return 3000    # residential lane
    if any(k in name for k in ["CIRCLE", "CROSS", "JUNCTION"]):
        return 15000   # junction/circle
    return 8000        # default fallback


def get_or_estimate_traffic(road_name: str) -> int:
    """
    Return actual traffic volume if known, else estimate and auto-save.
    This ensures new roads always get a priority score.
    """
    row = get_traffic_for_road(road_name)
    if row:
        return row["avg_daily_traffic"]
    # Auto-create with estimate so it appears in Traffic dialog
    estimated = estimate_traffic(road_name)
    upsert_traffic(road_name, estimated)
    return estimated


# ── Reports ────────────────────────────────────────────────────────────────────

def create_report(user_id, citizen_name, email, phone, location_text,
                  lat, lng, road_name, severity, description, image_paths,
                  priority_score, ml_severity=None):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_conn()
    c = conn.execute("""
        INSERT INTO pothole_reports
        (user_id, citizen_name, email, phone_number, location_text,
         latitude, longitude, road_name, severity, ml_severity,
         description, image_paths, status, priority_score, created_at, updated_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (user_id, citizen_name, email, phone, location_text,
          lat, lng, road_name, severity, ml_severity,
          description,
          json.dumps(image_paths) if image_paths else None,
          "Pending", priority_score, now, now))
    conn.commit()
    rid = c.lastrowid
    log_history(conn, rid, user_id, citizen_name, "Created", None, "Pending")
    conn.commit()
    row = conn.execute("SELECT * FROM pothole_reports WHERE id=?", (rid,)).fetchone()
    conn.close()
    return dict(row)


def get_reports(status=None, min_severity=None, search=None,
                sort_by="priority_score", order="DESC",
                user_id=None, limit=500, offset=0):
    conn = get_conn()
    sql = """
        SELECT r.*, u.name AS reporter_name
        FROM pothole_reports r
        JOIN users u ON r.user_id = u.id
        WHERE 1=1
    """
    params = []
    if status:
        sql += " AND r.status=?";         params.append(status)
    if min_severity:
        sql += " AND r.severity>=?";      params.append(min_severity)
    if search:
        # FIX #30: case-insensitive search via UPPER()
        sql += """ AND (
            UPPER(r.road_name)     LIKE UPPER(?) OR
            UPPER(r.location_text) LIKE UPPER(?) OR
            UPPER(r.description)   LIKE UPPER(?)
        )"""
        params += [f"%{search}%"] * 3
    if user_id:
        sql += " AND r.user_id=?";        params.append(user_id)

    valid_cols = {"priority_score","created_at","severity","road_name","status"}
    if sort_by not in valid_cols:
        sort_by = "priority_score"
    sql += f" ORDER BY r.{sort_by} {'ASC' if order=='ASC' else 'DESC'}"
    sql += " LIMIT ? OFFSET ?"
    params += [limit, offset]

    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_report_count(status=None, min_severity=None, search=None, user_id=None):
    """Total count for pagination."""
    conn = get_conn()
    sql = "SELECT COUNT(*) FROM pothole_reports r WHERE 1=1"
    params = []
    if status:   sql += " AND r.status=?";    params.append(status)
    if min_severity: sql += " AND r.severity>=?"; params.append(min_severity)
    if search:
        sql += " AND (UPPER(r.road_name) LIKE UPPER(?) OR UPPER(r.location_text) LIKE UPPER(?))"
        params += [f"%{search}%", f"%{search}%"]
    if user_id:  sql += " AND r.user_id=?";   params.append(user_id)
    count = conn.execute(sql, params).fetchone()[0]
    conn.close()
    return count


def get_report_by_id(rid):
    conn = get_conn()
    row = conn.execute("SELECT * FROM pothole_reports WHERE id=?", (rid,)).fetchone()
    conn.close()
    return dict(row) if row else None


def update_report_status(rid, status, actor_id=None, actor_name=None):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_conn()
    old = conn.execute(
        "SELECT status FROM pothole_reports WHERE id=?", (rid,)
    ).fetchone()
    old_status = old["status"] if old else None
    conn.execute(
        "UPDATE pothole_reports SET status=?, updated_at=? WHERE id=?",
        (status, now, rid)
    )
    log_history(conn, rid, actor_id, actor_name or "Admin",
                "Status changed", old_status, status)
    conn.commit()
    conn.close()


def update_report_severity(rid, severity, actor_id=None, actor_name=None):
    """Update severity and immediately recalculate priority score."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_conn()
    old = conn.execute(
        "SELECT severity, road_name FROM pothole_reports WHERE id=?", (rid,)
    ).fetchone()

    from priority_engine import PriorityEngine
    engine = PriorityEngine()
    traffic_rows = conn.execute(
        "SELECT road_name, avg_daily_traffic FROM traffic_data"
    ).fetchall()
    traffic_lookup = {r["road_name"]: r["avg_daily_traffic"] for r in traffic_rows}
    max_traffic = max(traffic_lookup.values(), default=5000)
    traffic = traffic_lookup.get(old["road_name"],
                              estimate_traffic(old["road_name"])) if old else 8000
    new_score = engine.calculate_score(severity, traffic, max_traffic)

    conn.execute(
        "UPDATE pothole_reports SET severity=?, priority_score=?, updated_at=? WHERE id=?",
        (severity, new_score, now, rid)
    )
    log_history(conn, rid, actor_id, actor_name or "Admin",
                "Severity changed", str(old["severity"]) if old else None, str(severity))
    conn.commit()
    conn.close()
    return new_score


def delete_report(rid):
    conn = get_conn()
    conn.execute("DELETE FROM repair_assignments WHERE pothole_id=?", (rid,))
    conn.execute("DELETE FROM report_history WHERE report_id=?", (rid,))
    conn.execute("DELETE FROM pothole_reports WHERE id=?", (rid,))
    conn.commit()
    conn.close()


def get_nearby_reports(lat, lng, radius_m=50):
    """
    Return open reports within radius_m metres using flat-earth approximation.
    1 degree lat ≈ 111,000 m; 1 degree lng ≈ 111,000 * cos(lat) m.
    """
    import math
    dlat = radius_m / 111000
    dlng = radius_m / (111000 * max(math.cos(math.radians(lat)), 0.001))
    conn = get_conn()
    rows = conn.execute("""
        SELECT id, road_name, severity, status, latitude, longitude
        FROM pothole_reports
        WHERE status != 'Fixed'
          AND latitude  BETWEEN ? AND ?
          AND longitude BETWEEN ? AND ?
    """, (lat-dlat, lat+dlat, lng-dlng, lng+dlng)).fetchall()
    conn.close()
    results = []
    for r in rows:
        dist = math.sqrt(
            ((r["latitude"] - lat) * 111000) ** 2 +
            ((r["longitude"] - lng) * 111000 * math.cos(math.radians(lat))) ** 2
        )
        if dist <= radius_m:
            results.append({**dict(r), "distance_m": int(dist)})
    results.sort(key=lambda x: x["distance_m"])
    return results


def recalculate_all_scores():
    from priority_engine import PriorityEngine
    engine = PriorityEngine()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_conn()
    traffic_rows = conn.execute(
        "SELECT road_name, avg_daily_traffic FROM traffic_data"
    ).fetchall()
    traffic_lookup = {r["road_name"]: r["avg_daily_traffic"] for r in traffic_rows}
    reports = conn.execute(
        "SELECT id, road_name, severity FROM pothole_reports WHERE status != 'Fixed'"
    ).fetchall()
    # Ensure every report road has traffic data (auto-estimate if missing)
    for r in reports:
        if r["road_name"] not in traffic_lookup:
            estimated = estimate_traffic(r["road_name"])
            upsert_traffic(r["road_name"], estimated)
            traffic_lookup[r["road_name"]] = estimated
    max_traffic = max(traffic_lookup.values(), default=8000)
    for r in reports:
        traffic = traffic_lookup.get(r["road_name"], 8000)
        score = engine.calculate_score(r["severity"], traffic, max_traffic)
        conn.execute(
            "UPDATE pothole_reports SET priority_score=?, updated_at=? WHERE id=?",
            (score, now, r["id"])
        )
    conn.commit()
    conn.close()
    return len(reports)


# ── Assignments ────────────────────────────────────────────────────────────────

def has_active_assignment(pothole_id) -> bool:
    """FIX #4: prevent duplicate active assignments."""
    conn = get_conn()
    row = conn.execute("""
        SELECT COUNT(*) FROM repair_assignments
        WHERE pothole_id=? AND repair_status IN ('Assigned','Started')
    """, (pothole_id,)).fetchone()
    conn.close()
    return row[0] > 0


def create_assignment(pothole_id, crew_id, scheduled_date=None, notes=None,
                      actor_id=None, actor_name=None):
    if has_active_assignment(pothole_id):
        raise ValueError("This report already has an active assignment.")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_conn()
    conn.execute("""
        INSERT INTO repair_assignments
        (pothole_id, assigned_crew, scheduled_date, notes, created_at, updated_at)
        VALUES (?,?,?,?,?,?)
    """, (pothole_id, crew_id, scheduled_date, notes, now, now))
    conn.execute(
        "UPDATE pothole_reports SET status='Scheduled', updated_at=? WHERE id=?",
        (now, pothole_id)
    )
    log_history(conn, pothole_id, actor_id, actor_name or "Admin",
                "Crew assigned", None, f"crew_id={crew_id}")
    conn.commit()
    conn.close()


def get_assignments(crew_id=None, status=None):
    conn = get_conn()
    sql = """
        SELECT a.*, p.road_name, p.severity, p.location_text, p.priority_score,
               p.latitude, p.longitude, p.description, p.image_paths,
               u.name AS crew_name
        FROM repair_assignments a
        JOIN pothole_reports p ON a.pothole_id = p.id
        JOIN users u ON a.assigned_crew = u.id
        WHERE 1=1
    """
    params = []
    if crew_id:
        sql += " AND a.assigned_crew=?"; params.append(crew_id)
    if status:
        sql += " AND a.repair_status=?"; params.append(status)
    sql += " ORDER BY COALESCE(a.scheduled_date,'9999') ASC, a.created_at ASC"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_assignment_status(aid, status, progress_note=None,
                              proof_images=None, actor_id=None, actor_name=None):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_conn()
    old = conn.execute(
        "SELECT repair_status, pothole_id FROM repair_assignments WHERE id=?", (aid,)
    ).fetchone()
    if not old:
        conn.close()
        return

    pothole_id = old["pothole_id"]
    proof_json = json.dumps(proof_images) if proof_images else None

    if status == "Completed":
        conn.execute("""
            UPDATE repair_assignments
            SET repair_status=?, completed_at=?, updated_at=?,
                progress_note=COALESCE(?,progress_note),
                proof_images=COALESCE(?,proof_images)
            WHERE id=?
        """, (status, now, now, progress_note, proof_json, aid))
        conn.execute(
            "UPDATE pothole_reports SET status='Fixed', updated_at=? WHERE id=?",
            (now, pothole_id)
        )
        log_history(conn, pothole_id, actor_id, actor_name or "Crew",
                    "Repair completed", old["repair_status"], "Fixed")
    elif status == "Started":
        conn.execute("""
            UPDATE repair_assignments
            SET repair_status=?, updated_at=?,
                progress_note=COALESCE(?,progress_note),
                proof_images=COALESCE(?,proof_images)
            WHERE id=?
        """, (status, now, progress_note, proof_json, aid))
        conn.execute(
            "UPDATE pothole_reports SET status='In Progress', updated_at=? WHERE id=?",
            (now, pothole_id)
        )
        log_history(conn, pothole_id, actor_id, actor_name or "Crew",
                    "Work started", old["repair_status"], "In Progress")
    else:
        conn.execute("""
            UPDATE repair_assignments
            SET repair_status=?, updated_at=?,
                progress_note=COALESCE(?,progress_note)
            WHERE id=?
        """, (status, now, progress_note, aid))
        if status == "Cancelled":
            conn.execute(
                "UPDATE pothole_reports SET status='Unresolved', updated_at=? WHERE id=?",
                (now, pothole_id)
            )
            log_history(conn, pothole_id, actor_id, actor_name or "Crew",
                        "Assignment cancelled", old["repair_status"], "Unresolved")
    conn.commit()
    conn.close()


# ── Image helpers ──────────────────────────────────────────────────────────────

def save_image(src_path: str, subfolder: str = "potholes") -> str | None:
    """
    Copy image into uploads dir. Returns stored absolute path, or None on error.
    FIX #14: proper error handling instead of unhandled exception.
    """
    try:
        src = Path(src_path)
        if not src.exists():
            return None
        dest_dir = UPLOAD_DIR / subfolder
        dest_dir.mkdir(parents=True, exist_ok=True)
        ext  = src.suffix.lower() or ".jpg"
        dest = dest_dir / f"{uuid.uuid4().hex}{ext}"

        # Compress with PIL if available
        try:
            from PIL import Image as PILImage
            img = PILImage.open(src)
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            img.thumbnail((1200, 1200), PILImage.LANCZOS)
            img.save(str(dest), optimize=True, quality=85)
        except Exception:
            shutil.copy2(str(src), str(dest))

        return str(dest)
    except Exception as e:
        print(f"[save_image] ERROR: {e}")
        return None


# ── Analytics ──────────────────────────────────────────────────────────────────

def get_analytics():
    """FIX #20: single connection, all queries batched."""
    conn = get_conn()
    total    = conn.execute("SELECT COUNT(*) FROM pothole_reports").fetchone()[0]
    active   = conn.execute(
        "SELECT COUNT(*) FROM pothole_reports WHERE status IN ('Scheduled','In Progress')"
    ).fetchone()[0]
    fixed    = conn.execute(
        "SELECT COUNT(*) FROM pothole_reports WHERE status='Fixed'"
    ).fetchone()[0]
    pending  = conn.execute(
        "SELECT COUNT(*) FROM pothole_reports WHERE status='Pending'"
    ).fetchone()[0]
    high_pri = conn.execute(
        "SELECT COUNT(*) FROM pothole_reports WHERE priority_score>=50"
    ).fetchone()[0]

    status_dist = conn.execute(
        "SELECT status, COUNT(*) AS cnt FROM pothole_reports GROUP BY status"
    ).fetchall()

    # FIX #20: no reversed(list(...)) — query ASC directly
    monthly = conn.execute("""
        SELECT strftime('%Y-%m', created_at) AS month, COUNT(*) AS cnt
        FROM pothole_reports
        GROUP BY month
        ORDER BY month ASC
        LIMIT 12
    """).fetchall()

    top_roads = conn.execute("""
        SELECT road_name, COUNT(*) AS cnt
        FROM pothole_reports
        GROUP BY road_name
        ORDER BY cnt DESC
        LIMIT 8
    """).fetchall()

    conn.close()
    return {
        "total": total, "active": active, "fixed": fixed,
        "pending": pending, "high_priority": high_pri,
        "status_dist": [dict(r) for r in status_dist],
        "monthly":     [dict(r) for r in monthly],
        "top_roads":   [dict(r) for r in top_roads],
    }


# ── Seed ───────────────────────────────────────────────────────────────────────

def seed_sample_data():
    conn = get_conn()
    existing = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    conn.close()
    if existing > 0:
        return

    admin = create_user("Admin User",   "admin@potholefix.gov", "admin123", "Admin")
    crew1 = create_user("Ravi Kumar",   "ravi@crew.gov",        "crew123",  "Repair Crew")
    crew2 = create_user("Priya Nair",   "priya@crew.gov",       "crew123",  "Repair Crew")
    c1    = create_user("Arjun Shetty", "arjun@citizen.com",    "pass123",  "Citizen")
    c2    = create_user("Divya Rao",    "divya@citizen.com",    "pass123",  "Citizen")

    # Real Mangaluru road coordinates (approximate)
    roads_coords = [
        ("MG Road",              18000, 12.8698, 74.8426),
        ("NH 66",                27000, 12.9141, 74.8560),
        ("Hampankatta",          12000, 12.8677, 74.8430),
        ("Attavar Bridge",       15000, 12.8712, 74.8398),
        ("KS Rao Road",          10000, 12.8655, 74.8438),
        ("Bejai Road",            5000, 12.8701, 74.8412),
        ("Bunts Hostel Circle",   9000, 12.8723, 74.8445),
        ("Kankanady Road",        7000, 12.8631, 74.8365),
    ]
    for road, vol, _, _ in roads_coords:
        upsert_traffic(road, vol)

    from priority_engine import PriorityEngine
    engine = PriorityEngine()
    tl    = {r: v for r, v, _, _ in roads_coords}
    coord = {r: (lat, lng) for r, _, lat, lng in roads_coords}
    max_t = max(tl.values())

    samples = [
        (c1["id"], "Arjun Shetty", "arjun@citizen.com", "9876543210",
         "Near KSRTC Bus Stand",        "MG Road",              9,
         "Large pothole causing traffic jams, dangerous at night"),
        (c2["id"], "Divya Rao",    "divya@citizen.com", None,
         "Before Petrol Bunk",          "NH 66",                8,
         "Multiple potholes in a row, vehicles swerving"),
        (c1["id"], "Arjun Shetty", "arjun@citizen.com", None,
         "Junction near Hotel Malabar", "Hampankatta",          7,
         "Water logging makes pothole invisible in rain"),
        (c2["id"], "Divya Rao",    "divya@citizen.com", "9876001111",
         "Attavar Bridge approach",     "Attavar Bridge",       6,
         "Near bridge railing, risky for two-wheelers"),
        (c1["id"], "Arjun Shetty", "arjun@citizen.com", None,
         "Near St. Aloysius College",   "Kankanady Road",       5,
         "Small but deep pothole in school zone"),
        (c2["id"], "Divya Rao",    "divya@citizen.com", None,
         "Bejai Market Road",           "Bejai Road",           4,
         "Patch came off, needs re-tarmacking"),
        (c1["id"], "Arjun Shetty", "arjun@citizen.com", None,
         "KS Rao Road near Syndicate Bank", "KS Rao Road",     7,
         "Road breaking up along entire stretch"),
    ]

    conn = get_conn()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    report_ids = {}
    for (uid, cname, email, phone, loc, road, sev, desc) in samples:
        traffic  = tl.get(road, 5000)
        score    = engine.calculate_score(sev, traffic, max_t)
        lat, lng = coord.get(road, (12.87, 74.84))
        c = conn.execute("""
            INSERT INTO pothole_reports
            (user_id,citizen_name,email,phone_number,location_text,latitude,longitude,
             road_name,severity,description,status,priority_score,created_at,updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (uid,cname,email,phone,loc,lat,lng,road,sev,desc,"Pending",score,now,now))
        report_ids[road] = c.lastrowid

    conn.execute("UPDATE pothole_reports SET status='Fixed',       updated_at=? WHERE road_name='Bejai Road'", (now,))
    conn.execute("UPDATE pothole_reports SET status='In Progress', updated_at=? WHERE road_name='KS Rao Road'", (now,))
    conn.execute("UPDATE pothole_reports SET status='Scheduled',   updated_at=? WHERE road_name='Bunts Hostel Circle'", (now,))
    conn.commit()

    # Seed one assignment (skip duplicate check via direct insert)
    rid = report_ids.get("KS Rao Road")
    if rid and crew1:
        conn.execute("""
            INSERT INTO repair_assignments
            (pothole_id,assigned_crew,scheduled_date,repair_status,notes,created_at,updated_at)
            VALUES (?,?,?,?,?,?,?)
        """, (rid, crew1["id"], "2025-06-15", "Started",
              "Crew dispatched with patching equipment", now, now))
        conn.commit()
    conn.close()
