from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_file
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from werkzeug.middleware.proxy_fix import ProxyFix
from datetime import datetime, date, timedelta
from pathlib import Path
import sqlite3, calendar as pycal, json, shutil, threading, time, re, random, io, base64, hashlib
import os

try:
    from pywebpush import webpush, WebPushException
except ImportError:
    webpush = None
    WebPushException = Exception

BASE_DIR = Path(__file__).resolve().parent
app = Flask(
    __name__,
    template_folder=str(BASE_DIR / 'templates'),
    static_folder=str(BASE_DIR / 'static'),
)
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'blacksquare_stock_crm_v2')
DEFAULT_PASSWORD = 'blacksquare'
DB_FILENAME = 'blacksquare_stock_crm_v2.db'
PERSISTENT_DB_DIRS = ('/data', '/app/data')

def database_activity_score(db_path):
    path = Path(db_path)
    if not path.exists() or path.stat().st_size == 0:
        return 0
    try:
        con = sqlite3.connect(str(path))
        con.row_factory = sqlite3.Row
        appts = con.execute("SELECT COUNT(*) c FROM appointments").fetchone()['c']
        clients = con.execute("SELECT COUNT(*) c FROM clients").fetchone()['c']
        con.close()
        return int(appts) * 10 + int(clients)
    except Exception:
        return 0

def resolve_database_path():
    explicit = os.environ.get('DATABASE_PATH', '').strip()
    candidates = []
    if explicit:
        candidates.append(explicit)
    for root in PERSISTENT_DB_DIRS:
        candidates.append(str(Path(root) / DB_FILENAME))
    candidates.append(str(BASE_DIR / DB_FILENAME))
    seen = set()
    ordered = []
    for item in candidates:
        if item not in seen:
            seen.add(item)
            ordered.append(item)

    best_path = None
    best_score = -1
    for path in ordered:
        score = database_activity_score(path)
        if score > best_score:
            best_score = score
            best_path = path
    if best_path and best_score > 0:
        return best_path

    for path in ordered:
        try:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            test_file = Path(path).parent / '.write_test'
            test_file.write_text('ok')
            test_file.unlink(missing_ok=True)
            return path
        except OSError:
            continue
    return ordered[0] if ordered else str(BASE_DIR / DB_FILENAME)

def backup_sources():
    sources = []
    for root in PERSISTENT_DB_DIRS:
        backup_dir = Path(root) / 'backups'
        if backup_dir.exists():
            sources.extend(backup_dir.glob('blacksquare_*.db'))
        latest = Path(root) / f'{DB_FILENAME}.latest.bak'
        if latest.exists():
            sources.append(latest)
        db_file = Path(root) / DB_FILENAME
        if db_file.exists():
            sources.append(db_file)
    explicit = os.environ.get('DATABASE_PATH', '').strip()
    if explicit:
        db_file = Path(explicit)
        if db_file.exists():
            sources.append(db_file)
        latest = db_file.with_suffix(db_file.suffix + '.latest.bak')
        if latest.exists():
            sources.append(latest)
        backup_dir = db_file.parent / 'backups'
        if backup_dir.exists():
            sources.extend(backup_dir.glob('blacksquare_*.db'))
    unique = {}
    for src in sources:
        unique[str(src.resolve()) if src.exists() else str(src)] = src
    return sorted(unique.values(), key=lambda p: (database_activity_score(p), p.stat().st_mtime if p.exists() else 0), reverse=True)

def restore_database_if_needed():
    db_path = Path(DB)
    if database_activity_score(db_path) > 0:
        return False
    for src in backup_sources():
        if database_activity_score(src) <= 0:
            continue
        db_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, db_path)
        return True
    return False

def remote_db_configured():
    return all(os.environ.get(key) for key in ('S3_ENDPOINT', 'S3_BUCKET', 'S3_ACCESS_KEY', 'S3_SECRET_KEY'))

def remote_db_key():
    return os.environ.get('S3_DB_KEY', 'db/blacksquare_stock_crm_v2.db')

def remote_restore_database():
    if not remote_db_configured():
        return False
    db_path = Path(DB)
    if database_activity_score(db_path) > 0:
        return False
    try:
        import boto3
        from botocore.config import Config
        client = boto3.client(
            's3',
            endpoint_url=os.environ['S3_ENDPOINT'].rstrip('/'),
            aws_access_key_id=os.environ['S3_ACCESS_KEY'],
            aws_secret_access_key=os.environ['S3_SECRET_KEY'],
            region_name=os.environ.get('S3_REGION', 'ru-1'),
            config=Config(signature_version='s3v4'),
        )
        db_path.parent.mkdir(parents=True, exist_ok=True)
        client.download_file(os.environ['S3_BUCKET'], remote_db_key(), str(db_path))
        return database_activity_score(db_path) > 0
    except Exception:
        return False

def remote_backup_database():
    if not remote_db_configured():
        return False
    db_path = Path(DB)
    if database_activity_score(db_path) == 0:
        return False
    try:
        import boto3
        from botocore.config import Config
        client = boto3.client(
            's3',
            endpoint_url=os.environ['S3_ENDPOINT'].rstrip('/'),
            aws_access_key_id=os.environ['S3_ACCESS_KEY'],
            aws_secret_access_key=os.environ['S3_SECRET_KEY'],
            region_name=os.environ.get('S3_REGION', 'ru-1'),
            config=Config(signature_version='s3v4'),
        )
        client.upload_file(str(db_path), os.environ['S3_BUCKET'], remote_db_key())
        return True
    except Exception:
        return False

DB = resolve_database_path()

PERMS = {
    'calendar': 'Календарь',
    'services': 'Услуги',
    'crm': 'CRM',
    'stock': 'Склад',
    'salary': 'Зарплата',
    'analytics': 'Статистика',
    'employees': 'Сотрудники и права',
    'delete_appointments': 'Удаление записей',
    'edit_closed_appointments': 'Редактирование закрытых заказов',
    'certificates': 'Сертификаты',
    'extra_services': 'Допуслуги в заказе',
    'phone_access': 'Доступ к телефонам',
    'finance': 'Финансы',
}

WEEKDAYS = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
MONTHS_RU = ['', 'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь', 'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь']

def db():
    Path(DB).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con

def now(): return datetime.now().strftime('%Y-%m-%d %H:%M')
def today(): return date.today().isoformat()
def hm2m(hm):
    parts = (hm or '0:0').split(':')
    return int(parts[0]) * 60 + int(parts[1])
def m2hm(minutes): return f'{minutes // 60:02d}:{minutes % 60:02d}'
def normalize_hm(hm):
    if not hm:
        return ''
    parts = str(hm).strip().split(':')
    if len(parts) < 2:
        return ''
    try:
        return f'{int(parts[0]):02d}:{int(parts[1]):02d}'
    except ValueError:
        return ''

EMPLOYEE_NAME_SQL = """COALESCE(
    (SELECT GROUP_CONCAT(u2.full_name, ', ')
     FROM appointment_employees ae
     JOIN users u2 ON u2.id = ae.employee_id
     WHERE ae.appointment_id = a.id),
    u.full_name
) AS employee_name"""

def list_masters(con):
    return con.execute("SELECT * FROM users WHERE active=1 AND role='master' ORDER BY full_name").fetchall()

def parse_employee_ids(form):
    ids = []
    for raw in form.getlist('employee_ids'):
        if raw and str(raw).strip():
            ids.append(int(raw))
    seen = set()
    out = []
    for eid in ids:
        if eid not in seen:
            seen.add(eid)
            out.append(eid)
    return out

def validate_master_ids(con, employee_ids):
    if not employee_ids:
        return False, 'Укажите хотя бы одного мастера'
    placeholders = ','.join('?' * len(employee_ids))
    found = con.execute(
        f"SELECT id FROM users WHERE active=1 AND role='master' AND id IN ({placeholders})",
        employee_ids,
    ).fetchall()
    if len(found) != len(employee_ids):
        return False, 'Выбран недопустимый мастер'
    return True, ''

def set_appointment_employees(con, aid, employee_ids):
    con.execute("DELETE FROM appointment_employees WHERE appointment_id=?", (aid,))
    for eid in employee_ids:
        con.execute(
            "INSERT INTO appointment_employees(appointment_id,employee_id,created_at) VALUES(?,?,?)",
            (aid, eid, now()),
        )

def parse_service_ids(form):
    ids = []
    for raw in form.getlist('service_ids'):
        if raw and str(raw).strip():
            ids.append(int(raw))
    if not ids and form.get('service_id'):
        ids.append(int(form.get('service_id')))
    seen = set()
    out = []
    for sid in ids:
        if sid not in seen:
            seen.add(sid)
            out.append(sid)
    return out

def validate_service_ids(con, service_ids, online_only=False):
    if not service_ids:
        return False, 'Выберите хотя бы одну услугу'
    placeholders = ','.join('?' * len(service_ids))
    sql = f"SELECT id FROM services WHERE active=1 AND id IN ({placeholders})"
    if online_only:
        sql += " AND online_calendar=1"
    found = con.execute(sql, service_ids).fetchall()
    if len(found) != len(service_ids):
        return False, 'Выбрана недоступная услуга' if not online_only else 'Выбрана услуга, недоступная для онлайн-записи'
    return True, ''

def list_service_categories(con, active_only=True):
    sql = "SELECT * FROM service_categories"
    if active_only:
        sql += " WHERE active=1"
    sql += " ORDER BY sort_order, name"
    return con.execute(sql).fetchall()

def parse_category_id(raw):
    if raw in (None, ''):
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None

def group_services_for_admin(rows, categories):
    grouped = []
    seen = set()
    for cat in categories:
        items = [s for s in rows if s['category_id'] == cat['id']]
        grouped.append({'category': cat, 'services': items})
        seen.update(s['id'] for s in items)
    other = [s for s in rows if s['id'] not in seen]
    if other:
        grouped.append({'category': {'id': None, 'name': 'Прочее'}, 'services': other})
    return grouped

def group_services_by_category(services, categories):
    grouped = []
    seen = set()
    for cat in categories:
        items = [s for s in services if s['category_id'] == cat['id']]
        if items:
            grouped.append({'category': cat, 'services': items})
            seen.update(s['id'] for s in items)
    other = [s for s in services if s['id'] not in seen]
    if other:
        grouped.append({'category': {'id': None, 'name': 'Без подраздела'}, 'services': other})
    return grouped

def set_appointment_services(con, aid, service_ids):
    con.execute("DELETE FROM appointment_services WHERE appointment_id=?", (aid,))
    for sid in service_ids:
        con.execute(
            "INSERT INTO appointment_services(appointment_id,service_id,created_at) VALUES(?,?,?)",
            (aid, sid, now()),
        )

def get_appointment_service_ids(con, aid, primary_id=None):
    rows = con.execute(
        "SELECT service_id FROM appointment_services WHERE appointment_id=? ORDER BY id",
        (aid,),
    ).fetchall()
    if rows:
        return [r['service_id'] for r in rows]
    return [primary_id] if primary_id else []

def resolve_services_bundle(con, service_ids):
    if not service_ids:
        return None
    placeholders = ','.join('?' * len(service_ids))
    rows = con.execute(
        f"SELECT * FROM services WHERE active=1 AND id IN ({placeholders})",
        service_ids,
    ).fetchall()
    if len(rows) != len(service_ids):
        return None
    order = {sid: i for i, sid in enumerate(service_ids)}
    rows = sorted(rows, key=lambda r: order.get(r['id'], 999))
    return {
        'ids': service_ids,
        'rows': rows,
        'name': ' + '.join(r['name'] for r in rows),
        'duration_min': sum(int(r['duration_min'] or 0) for r in rows),
        'base_price': sum(float(r['base_price'] or 0) for r in rows),
        'primary_id': service_ids[0],
    }

def employee_can_all_services(con, uid, service_ids):
    return all(employee_can_service(con, uid, sid) for sid in service_ids)

def parse_service_ids_from_request(args):
    ids = []
    for raw in args.getlist('service_ids') if hasattr(args, 'getlist') else []:
        if raw and str(raw).strip():
            ids.append(int(raw))
    raw_list = args.get('service_ids', '') if hasattr(args, 'get') else ''
    if not ids and raw_list:
        for part in str(raw_list).split(','):
            if part.strip():
                ids.append(int(part.strip()))
    if not ids and args.get('service_id'):
        ids.append(int(args.get('service_id')))
    seen = set()
    out = []
    for sid in ids:
        if sid not in seen:
            seen.add(sid)
            out.append(sid)
    return out

def get_appointment_employee_ids(con, aid, primary_id=None):
    rows = con.execute(
        "SELECT employee_id FROM appointment_employees WHERE appointment_id=? ORDER BY id",
        (aid,),
    ).fetchall()
    if rows:
        return [r['employee_id'] for r in rows]
    return [primary_id] if primary_id else []

def user_on_appointment(con, aid, uid, primary_id=None):
    if primary_id and int(primary_id) == int(uid):
        return True
    return bool(con.execute(
        "SELECT 1 FROM appointment_employees WHERE appointment_id=? AND employee_id=?",
        (aid, uid),
    ).fetchone())

def master_appointment_filter_sql():
    return "(a.employee_id=? OR EXISTS (SELECT 1 FROM appointment_employees ae WHERE ae.appointment_id=a.id AND ae.employee_id=?))"

def can_manage_open_appointment(u, con, ap):
    if not ap or ap['status'] in ('Закрыт', 'Отменен'):
        return False
    if has_perm('calendar'):
        return True
    if u['role'] == 'master' and user_on_appointment(con, ap['id'], u['id'], ap['employee_id']):
        return True
    return False

def init_db():
    con = db(); c = con.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE, password_hash TEXT, role TEXT, full_name TEXT, active INTEGER DEFAULT 1, hired_at TEXT, fired_at TEXT, created_at TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS user_permissions(user_id INTEGER, permission TEXT, allowed INTEGER DEFAULT 0, UNIQUE(user_id, permission))")
    c.execute("CREATE TABLE IF NOT EXISTS services(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, duration_min INTEGER, base_price REAL DEFAULT 0, active INTEGER DEFAULT 1, comment TEXT, created_at TEXT, category_id INTEGER, online_calendar INTEGER DEFAULT 1)")
    c.execute("CREATE TABLE IF NOT EXISTS service_categories(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, sort_order INTEGER DEFAULT 0, active INTEGER DEFAULT 1, created_at TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS user_services(user_id INTEGER, service_id INTEGER, allowed INTEGER DEFAULT 1, UNIQUE(user_id, service_id))")
    c.execute("CREATE TABLE IF NOT EXISTS schedules(user_id INTEGER, work_date TEXT, start_time TEXT, end_time TEXT, is_day_off INTEGER DEFAULT 0, comment TEXT, UNIQUE(user_id, work_date))")
    c.execute("CREATE TABLE IF NOT EXISTS clients(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, phone TEXT, source TEXT, stage TEXT DEFAULT 'Новый', reason TEXT, comment TEXT, created_at TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS cars(id INTEGER PRIMARY KEY AUTOINCREMENT, client_id INTEGER, car_model TEXT, plate_number TEXT, created_at TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS stock_items(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, category TEXT DEFAULT 'film', unit TEXT DEFAULT 'm2', width_m REAL DEFAULT 1.52, length_m REAL DEFAULT 0, balance REAL DEFAULT 0, cost_total REAL DEFAULT 0, cost_per_unit REAL DEFAULT 0, visible_to_staff INTEGER DEFAULT 0, active INTEGER DEFAULT 1, comment TEXT, created_at TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS stock_moves(id INTEGER PRIMARY KEY AUTOINCREMENT, item_id INTEGER, appointment_id INTEGER, user_id INTEGER, change_qty REAL, move_type TEXT, comment TEXT, created_at TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS appointments(id INTEGER PRIMARY KEY AUTOINCREMENT, client_id INTEGER, car_id INTEGER, client_name TEXT, phone TEXT, car TEXT, plate_number TEXT, service_id INTEGER, service_name TEXT, appointment_date TEXT, start_time TEXT, end_time TEXT, duration_min INTEGER, status TEXT DEFAULT 'Записан', employee_id INTEGER, price REAL DEFAULT 0, extras_total REAL DEFAULT 0, certificate_paid REAL DEFAULT 0, material_id INTEGER, material_length_m REAL DEFAULT 0, material_width_cm REAL DEFAULT 0, material_m2 REAL DEFAULT 0, material_cost REAL DEFAULT 0, salary_amount REAL DEFAULT 0, profit REAL DEFAULT 0, comment TEXT, closed_at TEXT, created_at TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS appointment_extras(id INTEGER PRIMARY KEY AUTOINCREMENT, appointment_id INTEGER, name TEXT, price REAL DEFAULT 0, employee_id INTEGER, created_at TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS salary(id INTEGER PRIMARY KEY AUTOINCREMENT, employee_id INTEGER, appointment_id INTEGER, period TEXT, amount REAL, comment TEXT, created_at TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS certificates(id INTEGER PRIMARY KEY AUTOINCREMENT, cert_number TEXT UNIQUE, nominal REAL, balance REAL, status TEXT DEFAULT 'Активен', client_name TEXT, phone TEXT, comment TEXT, created_at TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS certificate_moves(id INTEGER PRIMARY KEY AUTOINCREMENT, certificate_id INTEGER, appointment_id INTEGER, user_id INTEGER, amount REAL, move_type TEXT, comment TEXT, created_at TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS phone_access_requests(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, appointment_id INTEGER, client_id INTEGER, phone TEXT, reason TEXT, status TEXT DEFAULT 'Ожидает', approved_until TEXT, created_at TEXT, decided_at TEXT, decided_by INTEGER)")
    c.execute("CREATE TABLE IF NOT EXISTS appointment_materials(id INTEGER PRIMARY KEY AUTOINCREMENT, appointment_id INTEGER, item_id INTEGER, qty REAL DEFAULT 0, length_m REAL DEFAULT 0, width_cm REAL DEFAULT 0, cost REAL DEFAULT 0, comment TEXT, created_at TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS finance_payments(id INTEGER PRIMARY KEY AUTOINCREMENT, category TEXT, title TEXT, amount REAL DEFAULT 0, due_date TEXT, paid_amount REAL DEFAULT 0, paid_date TEXT, status TEXT DEFAULT 'Ожидает', comment TEXT, created_at TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS push_subscriptions(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, endpoint TEXT UNIQUE, p256dh TEXT, auth TEXT, created_at TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS app_settings(key TEXT PRIMARY KEY, value TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS employee_weekly_schedule(user_id INTEGER, weekday INTEGER, start_time TEXT, end_time TEXT, is_day_off INTEGER DEFAULT 0, UNIQUE(user_id, weekday))")
    c.execute("CREATE TABLE IF NOT EXISTS appointment_employees(id INTEGER PRIMARY KEY AUTOINCREMENT, appointment_id INTEGER, employee_id INTEGER, created_at TEXT, UNIQUE(appointment_id, employee_id))")
    c.execute("CREATE TABLE IF NOT EXISTS appointment_services(id INTEGER PRIMARY KEY AUTOINCREMENT, appointment_id INTEGER, service_id INTEGER, created_at TEXT, UNIQUE(appointment_id, service_id))")
    c.execute("CREATE TABLE IF NOT EXISTS director_notification_prefs(user_id INTEGER PRIMARY KEY, notify_new INTEGER DEFAULT 1, notify_closed INTEGER DEFAULT 1, notify_daily INTEGER DEFAULT 1)")
    c.execute("CREATE TABLE IF NOT EXISTS director_employee_notify(director_id INTEGER, employee_id INTEGER, enabled INTEGER DEFAULT 1, UNIQUE(director_id, employee_id))")
    c.execute("CREATE TABLE IF NOT EXISTS daily_reports(report_date TEXT PRIMARY KEY, revenue REAL DEFAULT 0, salary REAL DEFAULT 0, profit REAL DEFAULT 0, certificate_paid REAL DEFAULT 0, material_cost REAL DEFAULT 0, m2 REAL DEFAULT 0, appointments_count INTEGER DEFAULT 0, by_employee_json TEXT, created_at TEXT, notified INTEGER DEFAULT 0)")
    c.execute("CREATE TABLE IF NOT EXISTS bonus_transactions(id INTEGER PRIMARY KEY AUTOINCREMENT, client_id INTEGER, appointment_id INTEGER, type TEXT, amount REAL DEFAULT 0, percent REAL, visit_price REAL, balance_after REAL DEFAULT 0, comment TEXT, user_id INTEGER, created_at TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS friend_cards(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, client_id INTEGER, card_number TEXT UNIQUE, access_token TEXT UNIQUE, discount_percent REAL DEFAULT 10, active INTEGER DEFAULT 1, comment TEXT, created_at TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS friend_discount_codes(id INTEGER PRIMARY KEY AUTOINCREMENT, friend_card_id INTEGER, code TEXT, created_at TEXT, expires_at TEXT, used_at TEXT, appointment_id INTEGER)")
    c.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_friend_discount_code_active ON friend_discount_codes(code) WHERE used_at IS NULL")
    con.commit()
    migrate_db(c)

    default_users = [('director','director','Директор'),('admin','admin','Администратор'),('katya','master','Катя'),('stas','master','Стас')]
    for username, role, full_name in default_users:
        c.execute("INSERT OR IGNORE INTO users(username,password_hash,role,full_name,hired_at,created_at) VALUES(?,?,?,?,?,?)", (username, generate_password_hash(DEFAULT_PASSWORD), role, full_name, today(), now()))
        uid = c.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()['id']
        for p in PERMS:
            if role == 'director': allowed = 1
            elif role == 'admin': allowed = 1 if p in ['calendar','services','crm','employees','delete_appointments','extra_services','certificates','phone_access','edit_closed_appointments'] else 0
            elif p == 'finance': allowed = 0
            else: allowed = 1 if p in ['calendar','salary','extra_services'] else 0
            c.execute("INSERT OR IGNORE INTO user_permissions(user_id,permission,allowed) VALUES(?,?,?)", (uid,p,allowed))

    if c.execute("SELECT COUNT(*) c FROM services").fetchone()['c'] == 0:
        for name, dur, price in [('Тонировка задней части',180,5500),('Передние боковые',90,2500),('Атермальная пленка',180,6000),('Обучение тонировке',360,20000)]:
            c.execute("INSERT INTO services(name,duration_min,base_price,created_at) VALUES(?,?,?,?)", (name,dur,price,now()))

    masters = c.execute("SELECT id FROM users WHERE role!='director'").fetchall()
    services = c.execute("SELECT id FROM services").fetchall()
    for u in masters:
        for s in services:
            c.execute("INSERT OR IGNORE INTO user_services(user_id,service_id,allowed) VALUES(?,?,1)", (u['id'],s['id']))
    for u in c.execute("SELECT id, role FROM users").fetchall():
        for p in PERMS:
            if p == 'finance':
                allowed = 1 if u['role'] == 'director' else 0
            elif u['role'] == 'director':
                allowed = 1
            elif u['role'] == 'admin':
                allowed = 1 if p in ['calendar','services','crm','employees','delete_appointments','extra_services','certificates','phone_access','edit_closed_appointments'] else 0
            else:
                allowed = 1 if p in ['calendar','salary','extra_services'] else 0
            c.execute("INSERT OR IGNORE INTO user_permissions(user_id,permission,allowed) VALUES(?,?,?)", (u['id'], p, allowed))
    con.commit(); con.close()

def backup_database():
    """Копия базы перед обновлениями — данные не теряются при деплое."""
    db_path = Path(DB)
    if not db_path.exists() or db_path.stat().st_size == 0:
        return
    if database_activity_score(db_path) == 0:
        return
    backup_dir = db_path.parent / 'backups'
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    shutil.copy2(db_path, backup_dir / f'blacksquare_{stamp}.db')
    shutil.copy2(db_path, backup_dir / f'blacksquare_{today()}.db')
    shutil.copy2(db_path, str(db_path) + '.latest.bak')
    old = sorted(backup_dir.glob('blacksquare_2*.db'), key=lambda p: p.stat().st_mtime, reverse=True)
    for path in old[15:]:
        path.unlink(missing_ok=True)
    remote_backup_database()

def migrate_db(c):
    """Добавляет новые колонки и настройки без потери данных."""
    backup_database()
    cols = {r[1] for r in c.execute("PRAGMA table_info(stock_items)").fetchall()}
    if 'cost_mode' not in cols:
        c.execute("ALTER TABLE stock_items ADD COLUMN cost_mode TEXT DEFAULT 'per_roll'")
    if 'cost_per_meter' not in cols:
        c.execute("ALTER TABLE stock_items ADD COLUMN cost_per_meter REAL DEFAULT 0")
    c.execute("INSERT OR IGNORE INTO app_settings(key,value) VALUES('stats_refresh','live')")
    c.execute("INSERT OR IGNORE INTO app_settings(key,value) VALUES('stats_cached','{}')")
    for p in PERMS:
        for u in c.execute("SELECT id, role FROM users").fetchall():
            if p == 'edit_closed_appointments':
                allowed = 1 if u['role'] in ('director', 'admin') else 0
            elif u['role'] == 'director':
                allowed = 1
            elif u['role'] == 'admin':
                allowed = 1 if p in ['calendar','services','crm','employees','delete_appointments','extra_services','certificates','phone_access','edit_closed_appointments'] else 0
            else:
                allowed = 1 if p in ['calendar','salary','extra_services'] else 0
            c.execute("INSERT OR IGNORE INTO user_permissions(user_id,permission,allowed) VALUES(?,?,?)", (u['id'], p, allowed))
    for row in c.execute("SELECT id, employee_id FROM appointments WHERE employee_id IS NOT NULL").fetchall():
        c.execute(
            "INSERT OR IGNORE INTO appointment_employees(appointment_id,employee_id,created_at) VALUES(?,?,?)",
            (row['id'], row['employee_id'], now()),
        )
    c.execute("CREATE TABLE IF NOT EXISTS appointment_services(id INTEGER PRIMARY KEY AUTOINCREMENT, appointment_id INTEGER, service_id INTEGER, created_at TEXT, UNIQUE(appointment_id, service_id))")
    for row in c.execute("SELECT id, service_id FROM appointments WHERE service_id IS NOT NULL").fetchall():
        c.execute(
            "INSERT OR IGNORE INTO appointment_services(appointment_id,service_id,created_at) VALUES(?,?,?)",
            (row['id'], row['service_id'], now()),
        )
    c.execute("INSERT OR IGNORE INTO app_settings(key,value) VALUES('telegram_enabled','0')")
    c.execute("INSERT OR IGNORE INTO app_settings(key,value) VALUES('telegram_chat_id','')")
    c.execute("INSERT OR IGNORE INTO app_settings(key,value) VALUES('telegram_update_offset','0')")
    c.execute("INSERT OR IGNORE INTO app_settings(key,value) VALUES('telegram_wake_name','пантюха')")
    c.execute("UPDATE app_settings SET value='пантюха' WHERE key='telegram_wake_name' AND value IN ('', 'сквер')")
    c.execute("INSERT OR IGNORE INTO app_settings(key,value) VALUES('bonus_enabled','1')")
    c.execute("INSERT OR IGNORE INTO app_settings(key,value) VALUES('bonus_percent','3')")
    c.execute("INSERT OR IGNORE INTO app_settings(key,value) VALUES('bonus_from_visit','2')")
    c.execute("INSERT OR IGNORE INTO app_settings(key,value) VALUES('friend_discount_percent','10')")
    c.execute("INSERT OR IGNORE INTO app_settings(key,value) VALUES('openai_api_key','')")
    client_cols = {r[1] for r in c.execute("PRAGMA table_info(clients)").fetchall()}
    if 'bonus_code' not in client_cols:
        c.execute("ALTER TABLE clients ADD COLUMN bonus_code TEXT")
    if 'bonus_balance' not in client_cols:
        c.execute("ALTER TABLE clients ADD COLUMN bonus_balance REAL DEFAULT 0")
    if 'bonus_enabled' not in client_cols:
        c.execute("ALTER TABLE clients ADD COLUMN bonus_enabled INTEGER DEFAULT 1")
    if 'bonus_percent' not in client_cols:
        c.execute("ALTER TABLE clients ADD COLUMN bonus_percent REAL")
    for row in c.execute("SELECT id FROM clients WHERE bonus_code IS NULL OR bonus_code=''").fetchall():
        code = make_bonus_code(c, row['id'])
        c.execute("UPDATE clients SET bonus_code=? WHERE id=?", (code, row['id']))
    c.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_clients_bonus_code ON clients(bonus_code)")
    appt_cols = {r[1] for r in c.execute("PRAGMA table_info(appointments)").fetchall()}
    if 'friend_discount_code' not in appt_cols:
        c.execute("ALTER TABLE appointments ADD COLUMN friend_discount_code TEXT")
    if 'friend_discount_amount' not in appt_cols:
        c.execute("ALTER TABLE appointments ADD COLUMN friend_discount_amount REAL DEFAULT 0")
    env_chat = os.environ.get('TELEGRAM_CHAT_ID', '').strip()
    if env_chat:
        c.execute("INSERT INTO app_settings(key,value) VALUES('telegram_chat_id',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (env_chat,))
        c.execute("INSERT INTO app_settings(key,value) VALUES('telegram_enabled','1') ON CONFLICT(key) DO UPDATE SET value='1'")
    for d in c.execute("SELECT id FROM users WHERE role='director'").fetchall():
        c.execute(
            "INSERT OR IGNORE INTO director_notification_prefs(user_id,notify_new,notify_closed,notify_daily) VALUES(?,?,?,?)",
            (d['id'], 1, 1, 1),
        )
        for m in c.execute("SELECT id FROM users WHERE role='master' AND active=1").fetchall():
            c.execute(
                "INSERT OR IGNORE INTO director_employee_notify(director_id,employee_id,enabled) VALUES(?,?,?)",
                (d['id'], m['id'], 1),
            )
    c.execute("INSERT OR IGNORE INTO app_settings(key,value) VALUES('last_daily_report_date','')")
    c.execute("CREATE TABLE IF NOT EXISTS service_categories(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, sort_order INTEGER DEFAULT 0, active INTEGER DEFAULT 1, created_at TEXT)")
    c.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_service_categories_name ON service_categories(name)")
    service_cols = {r[1] for r in c.execute("PRAGMA table_info(services)").fetchall()}
    if 'category_id' not in service_cols:
        c.execute("ALTER TABLE services ADD COLUMN category_id INTEGER")
    if 'online_calendar' not in service_cols:
        c.execute("ALTER TABLE services ADD COLUMN online_calendar INTEGER DEFAULT 1")
    if c.execute("SELECT COUNT(*) c FROM service_categories").fetchone()['c'] == 0:
        c.execute("INSERT INTO service_categories(name,sort_order,created_at) VALUES(?,?,?)", ('Тонировка', 1, now()))
        tint_id = c.execute("SELECT id FROM service_categories WHERE name='Тонировка'").fetchone()['id']
        for row in c.execute("SELECT id, name FROM services").fetchall():
            name_l = (row['name'] or '').lower()
            if 'обучен' in name_l:
                continue
            c.execute("UPDATE services SET category_id=? WHERE id=?", (tint_id, row['id']))

def get_setting(key, default=''):
    con = db()
    row = con.execute("SELECT value FROM app_settings WHERE key=?", (key,)).fetchone()
    con.close()
    return row['value'] if row else default

def set_setting(key, value):
    con = db()
    con.execute("INSERT INTO app_settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))
    con.commit()
    con.close()

def film_cost_per_unit(width_m, length_m, balance, cost_mode, cost_total, cost_per_meter):
    w = float(width_m or 1.52)
    if cost_mode == 'per_meter' and cost_per_meter:
        return float(cost_per_meter) / w if w else float(cost_per_meter)
    if cost_total and balance > 0:
        return float(cost_total) / float(balance)
    roll_m2 = w * float(length_m or 0)
    if cost_mode == 'per_roll' and cost_total and roll_m2 > 0:
        return float(cost_total) / roll_m2
    return 0

def compute_dashboard_stats(con):
    today_s = today()
    closed_today = "status='Закрыт' AND appointment_date=?"
    return {
        'appointments': con.execute("SELECT COUNT(*) c FROM appointments").fetchone()['c'],
        'active': con.execute("SELECT COUNT(*) c FROM appointments WHERE status NOT IN ('Закрыт','Отменен')").fetchone()['c'],
        'revenue': con.execute(f"SELECT COALESCE(SUM(price),0) s FROM appointments WHERE {closed_today}", (today_s,)).fetchone()['s'],
        'certificate_paid': con.execute(f"SELECT COALESCE(SUM(certificate_paid),0) s FROM appointments WHERE {closed_today}", (today_s,)).fetchone()['s'],
        'material_m2': con.execute(f"SELECT COALESCE(SUM(material_m2),0) s FROM appointments WHERE {closed_today}", (today_s,)).fetchone()['s'],
        'material_cost': con.execute(f"SELECT COALESCE(SUM(material_cost),0) s FROM appointments WHERE {closed_today}", (today_s,)).fetchone()['s'],
        'salary': con.execute(f"SELECT COALESCE(SUM(salary_amount),0) s FROM appointments WHERE {closed_today}", (today_s,)).fetchone()['s'],
        'profit': con.execute(f"SELECT COALESCE(SUM(profit),0) s FROM appointments WHERE {closed_today}", (today_s,)).fetchone()['s'],
        'stock_items': con.execute("SELECT COUNT(*) c FROM stock_items WHERE active=1").fetchone()['c'],
        'today': today_s,
    }

def compute_day_stats(con, day):
    row = con.execute(
        "SELECT COUNT(*) cnt, COALESCE(SUM(price),0) revenue, COALESCE(SUM(salary_amount),0) salary, "
        "COALESCE(SUM(profit),0) profit, COALESCE(SUM(certificate_paid),0) certificate_paid, "
        "COALESCE(SUM(material_cost),0) material_cost, COALESCE(SUM(material_m2),0) m2 "
        "FROM appointments WHERE status='Закрыт' AND appointment_date=?",
        (day,),
    ).fetchone()
    by_employee = con.execute(
        "SELECT u.id, u.full_name, COUNT(a.id) cnt, COALESCE(SUM(a.price),0) revenue, COALESCE(SUM(a.salary_amount),0) salary "
        "FROM users u LEFT JOIN appointments a ON a.employee_id=u.id AND a.status='Закрыт' AND a.appointment_date=? "
        "WHERE u.role='master' AND u.active=1 GROUP BY u.id ORDER BY u.full_name",
        (day,),
    ).fetchall()
    employees = []
    for e in by_employee:
        if e['cnt']:
            employees.append({'id': e['id'], 'name': e['full_name'], 'cnt': e['cnt'], 'revenue': e['revenue'], 'salary': e['salary']})
    return {
        'date': day,
        'appointments': row['cnt'],
        'revenue': row['revenue'],
        'salary': row['salary'],
        'profit': row['profit'],
        'certificate_paid': row['certificate_paid'],
        'material_cost': row['material_cost'],
        'm2': row['m2'],
        'by_employee': employees,
    }

def refresh_dashboard_stats():
    """Пересчитывает показатели главной (касса, прибыль и т.д.) сразу после закрытия записи."""
    con = db()
    stats = compute_dashboard_stats(con)
    con.close()
    set_setting('stats_cached', json.dumps({'at': now(), 'stats': stats}, ensure_ascii=False))
    return stats

def dashboard_stats():
    interval = get_setting('stats_refresh', 'live')
    if interval == 'live':
        con = db()
        stats = compute_dashboard_stats(con)
        con.close()
        return stats, now()
    cached_raw = get_setting('stats_cached', '{}')
    try:
        cached = json.loads(cached_raw)
    except json.JSONDecodeError:
        cached = {}
    now_dt = datetime.now()
    need_refresh = True
    if cached.get('at'):
        last = datetime.strptime(cached['at'], '%Y-%m-%d %H:%M')
        delta = now_dt - last
        if interval == 'weekly' and delta.days < 7:
            need_refresh = False
        elif interval == 'monthly' and (now_dt.year, now_dt.month) == (last.year, last.month):
            need_refresh = False
        elif interval == 'daily' and delta.days < 1:
            need_refresh = False
    if need_refresh:
        con = db()
        stats = compute_dashboard_stats(con)
        con.close()
        set_setting('stats_cached', json.dumps({'at': now(), 'stats': stats}, ensure_ascii=False))
        return stats, now()
    return cached.get('stats', {}), cached.get('at', '')

def service_price_label(price):
    p = float(price or 0)
    return f'от {p:.0f} ₽' if p else 'цена по согласованию'

def current_user():
    if 'uid' not in session: return None
    con = db(); u = con.execute("SELECT * FROM users WHERE id=? AND active=1", (session['uid'],)).fetchone(); con.close()
    return u

def has_perm(perm):
    u = current_user()
    if not u: return False
    if u['role'] == 'director': return True
    con = db(); r = con.execute("SELECT allowed FROM user_permissions WHERE user_id=? AND permission=?", (u['id'],perm)).fetchone(); con.close()
    return bool(r and r['allowed'])


def mask_phone(phone):
    phone = phone or ''
    if len(phone) <= 4:
        return 'скрыт'
    return phone[:2] + '***' + phone[-2:]

def phone_allowed_for_appointment(user_id, appointment_id):
    u = current_user()
    if not u:
        return False
    if u['role'] == 'director' or has_perm('phone_access'):
        return True
    con = db()
    row = con.execute(
        "SELECT * FROM phone_access_requests WHERE user_id=? AND appointment_id=? AND status='Одобрен' AND approved_until>=?",
        (user_id, appointment_id, now())
    ).fetchone()
    con.close()
    return bool(row)

def visible_phone(row):
    u = current_user()
    if not u:
        return mask_phone(row['phone'])
    try:
        aid = row['id']
    except Exception:
        return mask_phone(row['phone'])
    return row['phone'] if phone_allowed_for_appointment(u['id'], aid) else mask_phone(row['phone'])

def login_required(fn):
    from functools import wraps
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user(): return redirect(url_for('login'))
        return fn(*args, **kwargs)
    return wrapper

def perm_required(perm):
    def deco(fn):
        from functools import wraps
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not has_perm(perm):
                flash('Нет доступа к этому разделу')
                return redirect(url_for('dashboard'))
            return fn(*args, **kwargs)
        return wrapper
    return deco

def get_client(con, name, phone):
    row = con.execute("SELECT id FROM clients WHERE phone=?", (phone,)).fetchone()
    if row:
        ensure_client_bonus_code(con, row['id'])
        return row['id']
    con.execute("INSERT INTO clients(name,phone,source,stage,created_at) VALUES(?,?,?,?,?)", (name,phone,'Запись','Новый',now()))
    cid = con.execute("SELECT last_insert_rowid() id").fetchone()['id']
    ensure_client_bonus_code(con, cid)
    return cid

def get_car(con, client_id, car, plate):
    row = con.execute("SELECT id FROM cars WHERE client_id=? AND (plate_number=? OR car_model=?)", (client_id,plate,car)).fetchone()
    if row: return row['id']
    con.execute("INSERT INTO cars(client_id,car_model,plate_number,created_at) VALUES(?,?,?,?)", (client_id,car,plate,now()))
    return con.execute("SELECT last_insert_rowid() id").fetchone()['id']

def employee_can_service(con, uid, sid):
    row = con.execute("SELECT allowed FROM user_services WHERE user_id=? AND service_id=?", (uid,sid)).fetchone()
    return bool(row and row['allowed'])

def get_schedule(con, uid, d):
    row = con.execute("SELECT * FROM schedules WHERE user_id=? AND work_date=?", (uid,d)).fetchone()
    if row:
        return row
    weekday = datetime.strptime(d, '%Y-%m-%d').weekday()
    wrow = con.execute("SELECT * FROM employee_weekly_schedule WHERE user_id=? AND weekday=?", (uid, weekday)).fetchone()
    if wrow:
        return wrow
    return {'start_time':'09:00','end_time':'20:00','is_day_off':0}

def slot_free(con, uid, d, start, end):
    s = hm2m(start); e = hm2m(end)
    rows = con.execute(
        "SELECT a.start_time,a.end_time FROM appointments a "
        "WHERE a.appointment_date=? AND a.status!='Отменен' "
        "AND (a.employee_id=? OR EXISTS ("
        "SELECT 1 FROM appointment_employees ae WHERE ae.appointment_id=a.id AND ae.employee_id=?"
        "))",
        (d, uid, uid),
    ).fetchall()
    for r in rows:
        if s < hm2m(r['end_time']) and e > hm2m(r['start_time']):
            return False
    return True

def available_slots_for_duration(con, uid, duration_min, d):
    emp = con.execute("SELECT * FROM users WHERE id=? AND active=1 AND role='master'", (uid,)).fetchone()
    if not emp:
        return []
    sched = get_schedule(con, uid, d)
    if int(sched['is_day_off']):
        return []
    dur = int(duration_min)
    t = hm2m(sched['start_time'])
    end_day = hm2m(sched['end_time'])
    out = []
    while t + dur <= end_day:
        a = m2hm(t)
        b = m2hm(t + dur)
        if slot_free(con, uid, d, a, b):
            out.append({'start': a, 'end': b})
        t += 30
    return out

def available_slots(con, uid, sid, d):
    bundle = resolve_services_bundle(con, [int(sid)] if sid else [])
    if not bundle or not employee_can_all_services(con, uid, bundle['ids']):
        return []
    return available_slots_for_duration(con, uid, bundle['duration_min'], d)

def online_slot_allowed(con, uid, service_ids, d, start):
    start = normalize_hm(start)
    bundle = resolve_services_bundle(con, service_ids)
    if not start or not bundle or not employee_can_all_services(con, uid, service_ids):
        return False
    return any(
        normalize_hm(s['start']) == start
        for s in available_slots_for_duration(con, uid, bundle['duration_min'], d)
    )

def booking_public_url():
    explicit = os.environ.get('PUBLIC_BASE_URL', '').strip().rstrip('/')
    if explicit:
        return f'{explicit}/booking'
    return url_for('booking', _external=True)

def public_base_url():
    explicit = os.environ.get('PUBLIC_BASE_URL', '').strip().rstrip('/')
    if explicit:
        return explicit
    return request.url_root.rstrip('/') if request else ''

def bonus_card_url(code):
    base = public_base_url() or booking_public_url().rsplit('/booking', 1)[0]
    return f'{base}/bonus/{code}'

def make_bonus_code(con, client_id=None):
    if client_id:
        code = f'BS{int(client_id):06d}'
        row = con.execute("SELECT id FROM clients WHERE bonus_code=? AND id!=?", (code, client_id)).fetchone()
        if not row:
            return code
    for _ in range(30):
        code = 'BS' + ''.join(random.choices('0123456789', k=8))
        if not con.execute("SELECT id FROM clients WHERE bonus_code=?", (code,)).fetchone():
            return code
    return f'BS{int(time.time())}'

def ensure_client_bonus_code(con, client_id):
    row = con.execute("SELECT bonus_code FROM clients WHERE id=?", (client_id,)).fetchone()
    if row and row['bonus_code']:
        return row['bonus_code']
    code = make_bonus_code(con, client_id)
    con.execute("UPDATE clients SET bonus_code=? WHERE id=?", (code, client_id))
    return code

def bonus_system_enabled():
    return get_setting('bonus_enabled', '1') == '1'

def global_bonus_percent():
    try:
        return float(get_setting('bonus_percent', '3') or 3)
    except ValueError:
        return 3.0

def client_bonus_percent(client):
    if client['bonus_percent'] is not None and str(client['bonus_percent']).strip() != '':
        try:
            return float(client['bonus_percent'])
        except ValueError:
            pass
    return global_bonus_percent()

def bonus_from_visit_number():
    try:
        return max(1, int(get_setting('bonus_from_visit', '2') or 2))
    except ValueError:
        return 2

def add_bonus_transaction(con, client_id, tx_type, amount, balance_after, comment='', appointment_id=None, percent=None, visit_price=None, user_id=None):
    con.execute(
        "INSERT INTO bonus_transactions(client_id,appointment_id,type,amount,percent,visit_price,balance_after,comment,user_id,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
        (client_id, appointment_id, tx_type, amount, percent, visit_price, balance_after, comment, user_id, now()),
    )

def spend_client_bonus(con, client_id, amount, appointment_id=None, user_id=None, comment=''):
    amount = round(float(amount or 0), 2)
    if amount <= 0:
        return True, ''
    client = con.execute("SELECT * FROM clients WHERE id=?", (client_id,)).fetchone()
    if not client:
        return False, 'Клиент не найден'
    balance = float(client['bonus_balance'] or 0)
    if amount > balance:
        return False, f'Недостаточно бонусов (доступно {balance:.0f} ₽)'
    new_balance = round(balance - amount, 2)
    con.execute("UPDATE clients SET bonus_balance=? WHERE id=?", (new_balance, client_id))
    add_bonus_transaction(con, client_id, 'spend', -amount, new_balance, comment or 'Списание бонусов', appointment_id, user_id=user_id)
    return True, ''

def accrue_bonus_on_close(con, ap, price, user_id=None, skip_bonus=False):
    if skip_bonus:
        return 0, ''
    if not bonus_system_enabled():
        return 0, ''
    client_id = ap['client_id']
    if not client_id:
        return 0, ''
    if client_has_friend_card(con, client_id):
        return 0, ''
    client = con.execute("SELECT * FROM clients WHERE id=?", (client_id,)).fetchone()
    if not client or not int(client['bonus_enabled'] or 0):
        return 0, ''
    if con.execute("SELECT id FROM bonus_transactions WHERE appointment_id=? AND type='earn'", (ap['id'],)).fetchone():
        return 0, ''
    prev_closed = con.execute(
        "SELECT COUNT(*) c FROM appointments WHERE client_id=? AND status='Закрыт' AND id!=?",
        (client_id, ap['id']),
    ).fetchone()['c']
    visit_no = int(prev_closed) + 1
    if visit_no < bonus_from_visit_number():
        return 0, ''
    percent = client_bonus_percent(client)
    amount = round(float(price or 0) * percent / 100.0, 2)
    if amount <= 0:
        return 0, ''
    ensure_client_bonus_code(con, client_id)
    new_balance = round(float(client['bonus_balance'] or 0) + amount, 2)
    con.execute("UPDATE clients SET bonus_balance=? WHERE id=?", (new_balance, client_id))
    add_bonus_transaction(
        con, client_id, 'earn', amount, new_balance,
        f'Начисление {percent:g}% за визит №{visit_no}',
        ap['id'], percent, price, user_id,
    )
    return amount, f'Начислено {amount:.0f} бонусов ({percent:g}%)'

def adjust_client_bonus(con, client_id, delta, user_id=None, comment=''):
    client = con.execute("SELECT * FROM clients WHERE id=?", (client_id,)).fetchone()
    if not client:
        return False, 'Клиент не найден'
    delta = round(float(delta), 2)
    new_balance = round(float(client['bonus_balance'] or 0) + delta, 2)
    if new_balance < 0:
        return False, 'Баланс не может быть отрицательным'
    ensure_client_bonus_code(con, client_id)
    con.execute("UPDATE clients SET bonus_balance=? WHERE id=?", (new_balance, client_id))
    add_bonus_transaction(con, client_id, 'adjust', delta, new_balance, comment or 'Корректировка', user_id=user_id)
    return True, ''

def bonus_qr_png(url):
    try:
        import qrcode
        img = qrcode.make(url, box_size=8, border=2)
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        return buf.getvalue()
    except Exception:
        return None

def friend_card_url(token):
    base = public_base_url() or booking_public_url().rsplit('/booking', 1)[0]
    return f'{base}/friend/{token}'

def make_friend_access_token(con):
    for _ in range(30):
        token = hashlib.sha256(f'friend{time.time()}{random.random()}'.encode()).hexdigest()[:16]
        if not con.execute("SELECT id FROM friend_cards WHERE access_token=?", (token,)).fetchone():
            return token
    return hashlib.sha256(str(time.time()).encode()).hexdigest()[:16]

def make_friend_card_number(con):
    row = con.execute(
        "SELECT COALESCE(MAX(CAST(card_number AS INTEGER)), 10000) n FROM friend_cards WHERE card_number GLOB '1[0-9][0-9][0-9][0-9]'"
    ).fetchone()
    return str(int(row['n']) + 1)

def global_friend_discount_percent():
    try:
        return float(get_setting('friend_discount_percent', '10') or 10)
    except ValueError:
        return 10.0

def client_has_friend_card(con, client_id):
    if not client_id:
        return False
    return bool(con.execute("SELECT id FROM friend_cards WHERE client_id=? AND active=1", (client_id,)).fetchone())

def issue_friend_discount_code(con, friend_card_id):
    con.execute(
        "UPDATE friend_discount_codes SET expires_at=? WHERE friend_card_id=? AND used_at IS NULL",
        (now(), friend_card_id),
    )
    for _ in range(80):
        code = '1' + ''.join(random.choices('0123456789', k=3))
        busy = con.execute(
            "SELECT id FROM friend_discount_codes WHERE code=? AND used_at IS NULL AND expires_at > ?",
            (code, now()),
        ).fetchone()
        if not busy:
            expires = (datetime.now() + timedelta(hours=24)).strftime('%Y-%m-%d %H:%M')
            con.execute(
                "INSERT INTO friend_discount_codes(friend_card_id,code,created_at,expires_at) VALUES(?,?,?,?)",
                (friend_card_id, code, now(), expires),
            )
            return code
    code = '1' + str(int(time.time()) % 1000).zfill(3)
    expires = (datetime.now() + timedelta(hours=24)).strftime('%Y-%m-%d %H:%M')
    con.execute(
        "INSERT INTO friend_discount_codes(friend_card_id,code,created_at,expires_at) VALUES(?,?,?,?)",
        (friend_card_id, code, now(), expires),
    )
    return code

def lookup_friend_discount_code(con, code):
    code = (code or '').strip()
    if not code:
        return None, ''
    row = con.execute(
        "SELECT fdc.*, fc.name, fc.card_number, fc.discount_percent, fc.active, fc.client_id "
        "FROM friend_discount_codes fdc "
        "JOIN friend_cards fc ON fc.id=fdc.friend_card_id "
        "WHERE fdc.code=? AND fdc.used_at IS NULL AND fdc.expires_at > ? AND fc.active=1",
        (code, now()),
    ).fetchone()
    if not row:
        return None, 'Код скидки не найден, просрочен или уже использован'
    return row, ''

def use_friend_discount_code(con, code_row, appointment_id):
    con.execute(
        "UPDATE friend_discount_codes SET used_at=?, appointment_id=? WHERE id=?",
        (now(), appointment_id, code_row['id']),
    )

def _derive_vapid_public_key(private_key):
    if not private_key:
        return ''
    try:
        from py_vapid import Vapid
        from cryptography.hazmat.primitives import serialization
        import base64
        raw = private_key.strip()
        if raw.startswith('-----BEGIN'):
            vapid = Vapid.from_pem(raw.encode())
        else:
            vapid = Vapid.from_string(private_key=raw)
        pub_bytes = vapid.public_key.public_bytes(
            serialization.Encoding.X962,
            serialization.PublicFormat.UncompressedPoint,
        )
        return base64.urlsafe_b64encode(pub_bytes).decode().rstrip('=')
    except Exception:
        return ''

def load_vapid_keys():
    private = os.environ.get('VAPID_PRIVATE_KEY', '').strip()
    public = os.environ.get('VAPID_PUBLIC_KEY', '').strip()
    if not private:
        return '', public
    derived = _derive_vapid_public_key(private)
    if derived:
        return private, derived
    return private, public

VAPID_PRIVATE_KEY, VAPID_PUBLIC_KEY = load_vapid_keys()
VAPID_CLAIMS = {'sub': 'mailto:director@blacksquare72.ru'}

def vapid_public_key():
    return VAPID_PUBLIC_KEY

def save_push_subscription(user_id, sub):
    if not sub or not sub.get('endpoint') or not sub.get('keys'):
        return False
    con = db()
    con.execute(
        "INSERT INTO push_subscriptions(user_id,endpoint,p256dh,auth,created_at) VALUES(?,?,?,?,?) "
        "ON CONFLICT(endpoint) DO UPDATE SET user_id=excluded.user_id,p256dh=excluded.p256dh,auth=excluded.auth",
        (user_id, sub['endpoint'], sub['keys']['p256dh'], sub['keys']['auth'], now()),
    )
    con.commit()
    con.close()
    return True

def send_push_to_user(user_id, title, body, url='/'):
    if not webpush:
        return False, 'Модуль pywebpush не установлен на сервере'
    if not VAPID_PRIVATE_KEY:
        return False, 'VAPID ключ не настроен на сервере'
    con = db()
    subs = con.execute("SELECT * FROM push_subscriptions WHERE user_id=?", (user_id,)).fetchall()
    if not subs:
        con.close()
        return False, 'Нет подписки на сервере. Нажмите «Включить уведомления» в профиле.'
    if url.startswith('/'):
        base = os.environ.get('PUBLIC_BASE_URL', '').strip().rstrip('/')
        if base:
            url = base + url
    stamp = int(time.time())
    payload = json.dumps({
        'title': title,
        'body': body,
        'url': url,
        'tag': f'bs-{user_id}-{stamp}',
    }, ensure_ascii=False)
    sent = False
    last_err = 'Не удалось доставить уведомление'
    stale = False
    last_code = None
    push_headers = {'Urgency': 'high', 'Topic': f'bs-{user_id}'}
    for s in subs:
        subscription_info = {
            'endpoint': s['endpoint'],
            'keys': {'p256dh': s['p256dh'], 'auth': s['auth']},
        }
        claims = dict(VAPID_CLAIMS)
        delivered = False
        for encoding in ('aes128gcm', 'aesgcm'):
            try:
                webpush(
                    subscription_info=subscription_info,
                    data=payload,
                    vapid_private_key=VAPID_PRIVATE_KEY,
                    vapid_claims=claims,
                    content_encoding=encoding,
                    ttl=86400,
                    headers=push_headers,
                )
                delivered = True
                break
            except WebPushException as e:
                resp = getattr(e, 'response', None)
                last_code = getattr(resp, 'status_code', None)
                last_err = str(resp.text if resp is not None else e)[:200]
                if encoding == 'aesgcm':
                    if last_code in (401, 403, 404, 410):
                        stale = True
                        con.execute("DELETE FROM push_subscriptions WHERE id=?", (s['id'],))
                        con.commit()
        if not delivered and not stale:
            try:
                webpush(
                    subscription_info=subscription_info,
                    data=None,
                    vapid_private_key=VAPID_PRIVATE_KEY,
                    vapid_claims=dict(VAPID_CLAIMS),
                    ttl=86400,
                    headers=push_headers,
                )
                delivered = True
            except WebPushException as e:
                resp = getattr(e, 'response', None)
                last_code = getattr(resp, 'status_code', None)
                last_err = str(resp.text if resp is not None else e)[:200]
                if last_code in (401, 403, 404, 410):
                    stale = True
                    con.execute("DELETE FROM push_subscriptions WHERE id=?", (s['id'],))
                    con.commit()
        if delivered:
            sent = True
    con.close()
    if sent:
        return True, None
    if stale or last_code in (401, 403, 404, 410):
        return False, 'Подписка устарела. Нажмите «Отключить», затем снова «Включить уведомления» в профиле.'
    if 'подписк' not in last_err.lower():
        last_err = 'Не удалось отправить уведомление. Попробуйте отключить и снова включить push в профиле.'
    return False, last_err

def telegram_bot_token():
    return os.environ.get('TELEGRAM_BOT_TOKEN', '').strip() or get_setting('telegram_bot_token', '').strip()

def telegram_chat_id():
    return os.environ.get('TELEGRAM_CHAT_ID', '').strip() or get_setting('telegram_chat_id', '').strip()

def telegram_enabled():
    env = os.environ.get('TELEGRAM_ENABLED', '').strip().lower()
    if env in ('1', 'true', 'yes', 'on'):
        return True
    if env in ('0', 'false', 'no', 'off'):
        return False
    return get_setting('telegram_enabled', '0') == '1'

def telegram_wake_name():
    return os.environ.get('TELEGRAM_WAKE_NAME', '').strip() or get_setting('telegram_wake_name', 'пантюха').strip()

def openai_api_key():
    env = os.environ.get('OPENAI_API_KEY', '').strip()
    if env:
        return env
    return get_setting('openai_api_key', '').strip()

_telegram_bot_id = None

def telegram_bot_id():
    global _telegram_bot_id
    if _telegram_bot_id:
        return _telegram_bot_id
    token = telegram_bot_token()
    if not token:
        return None
    import urllib.request
    try:
        with urllib.request.urlopen(f'https://api.telegram.org/bot{token}/getMe', timeout=10) as resp:
            data = json.loads(resp.read().decode())
            if data.get('ok'):
                _telegram_bot_id = data['result']['id']
                return _telegram_bot_id
    except Exception:
        pass
    return None

def _post_telegram_message(token, chat_id, text):
    import urllib.request
    import urllib.parse
    payload = urllib.parse.urlencode({
        'chat_id': chat_id,
        'text': text[:4096],
        'parse_mode': 'HTML',
        'disable_web_page_preview': 'true',
    }).encode()
    req = urllib.request.Request(
        f'https://api.telegram.org/bot{token}/sendMessage',
        data=payload,
        method='POST',
    )
    with urllib.request.urlopen(req, timeout=12) as resp:
        return json.loads(resp.read().decode())

def send_telegram_message(text, force=False):
    if not force and not telegram_enabled():
        return False, 'Telegram выключен'
    token = telegram_bot_token()
    chat_id = telegram_chat_id()
    if not token:
        return False, 'Укажите TELEGRAM_BOT_TOKEN в настройках сервера'
    if not chat_id:
        return False, 'Укажите ID чата в настройках'
    try:
        data = _post_telegram_message(token, chat_id, text)
        if data.get('ok'):
            return True, None
        params = data.get('parameters') or {}
        new_id = params.get('migrate_to_chat_id')
        if new_id:
            set_setting('telegram_chat_id', str(new_id))
            set_setting('telegram_enabled', '1')
            data = _post_telegram_message(token, new_id, text)
            if data.get('ok'):
                return True, None
        return False, str(data.get('description', 'Ошибка Telegram'))
    except Exception as e:
        return False, str(e)[:200]

def telegram_discover_chats():
    token = telegram_bot_token()
    if not token:
        return []
    import urllib.request
    try:
        with urllib.request.urlopen(f'https://api.telegram.org/bot{token}/getUpdates?limit=50', timeout=12) as resp:
            data = json.loads(resp.read().decode())
            chats = {}
            order = 0
            for item in data.get('result', []):
                order += 1
                chat = None
                if item.get('message'):
                    chat = item['message'].get('chat')
                elif item.get('channel_post'):
                    chat = item['channel_post'].get('chat')
                elif item.get('my_chat_member'):
                    chat = item['my_chat_member'].get('chat')
                cid = chat.get('id') if chat else None
                if cid is not None:
                    title = chat.get('title') or chat.get('first_name') or str(cid)
                    chats[str(cid)] = {'title': title, 'order': order}
            rows = sorted(chats.items(), key=lambda x: x[1]['order'], reverse=True)
            return [{'id': k, 'title': v['title']} for k, v in rows]
    except Exception:
        return []

def telegram_pick_chat(chats):
    if not chats:
        return None
    for c in chats:
        if str(c['id']).startswith('-100'):
            return c
    for c in chats:
        if str(c['id']).startswith('-'):
            return c
    return chats[0]

def telegram_autoconfigure():
    if not telegram_bot_token():
        return False
    chats = telegram_discover_chats()
    if not chats:
        return False
    current = telegram_chat_id()
    if telegram_enabled() and current:
        if any(str(c['id']) == str(current) for c in chats):
            return False
        if str(current).startswith('-') and not str(current).startswith('-100'):
            chosen = telegram_pick_chat(chats)
            if chosen and str(chosen['id']) != str(current):
                set_setting('telegram_chat_id', str(chosen['id']))
                send_telegram_message('<b>BlackSquare CRM</b>\nЧат обновлён после перехода в супергруппу.', force=True)
                return True
        return False
    chosen = telegram_pick_chat(chats)
    if not chosen:
        return False
    set_setting('telegram_chat_id', str(chosen['id']))
    set_setting('telegram_enabled', '1')
    send_telegram_message('<b>BlackSquare CRM</b>\nУведомления о записях подключены.', force=True)
    return True

TELEGRAM_Z_HELP = (
    '<b>Запись из чата</b>\n'
    '<code>/z Киа Рио на 15:00 тонировка задней полусферы</code>\n'
    '<code>/z завтра приора 14:00 передняя полусфера</code>\n'
    '<code>/z приора 15.00 задняя полусфера (завтра)</code>\n\n'
    '<b>Голосом</b> (начните с имени бота):\n'
    '«Пантюха, Киа Рио на 15:00 тонировка задней полусферы завтра»\n'
    'Или голосовое <b>ответом</b> на сообщение бота.\n\n'
    'Дата: <code>сегодня</code>, <code>завтра</code>, <code>22.06</code> — в начале, в конце или в скобках'
)

_TELEGRAM_DATE_TOKEN = r'сегодня|завтра|послезавтра|\d{1,2}[./]\d{1,2}(?:[./]\d{2,4})?'

def preprocess_telegram_booking_body(body):
    body = re.sub(r'\s+', ' ', (body or '').strip())
    if not body:
        return '', None
    date_token = None
    paren = re.search(
        rf'\(\s*({_TELEGRAM_DATE_TOKEN})\s*\)',
        body,
        flags=re.IGNORECASE,
    )
    if paren:
        date_token = paren.group(1)
        body = (body[:paren.start()] + ' ' + body[paren.end():]).strip()
    lead = re.match(rf'^({_TELEGRAM_DATE_TOKEN})\s+', body, flags=re.IGNORECASE)
    if lead:
        date_token = date_token or lead.group(1)
        body = body[lead.end():].strip()
    trail = re.search(rf'\s+({_TELEGRAM_DATE_TOKEN})\s*$', body, flags=re.IGNORECASE)
    if trail:
        date_token = date_token or trail.group(1)
        body = body[:trail.start()].strip()
    return body, date_token

def parse_booking_body(body):
    body, date_token = preprocess_telegram_booking_body(body)
    if not body:
        return None, TELEGRAM_Z_HELP
    m = re.match(
        r'^(.+?)\s+(?:на\s+)?(\d{1,2}[:.]\d{2})\s+(.+)$',
        body,
        flags=re.IGNORECASE,
    )
    if not m:
        return None, (
            'Не понял запись.\n'
            'Пример: <code>Киа Рио на 15:00 тонировка задней полусферы завтра</code>'
        )
    car, start_raw, rest = m.group(1).strip(), m.group(2), m.group(3).strip()
    start = normalize_hm(start_raw.replace('.', ':'))
    if not start:
        return None, 'Укажите время в формате 14:00 или 15.00'
    ap_date = parse_telegram_booking_date(date_token)
    service_text, price = split_telegram_service_price(rest)
    return {
        'date': ap_date,
        'car': car,
        'start': start,
        'service_text': service_text,
        'price': price,
    }, None

def telegram_reply(chat_id, text, reply_to=None):
    token = telegram_bot_token()
    if not token or not chat_id:
        return False, 'Telegram не настроен'
    import urllib.request
    import urllib.parse
    payload = {'chat_id': chat_id, 'text': text[:4096], 'parse_mode': 'HTML', 'disable_web_page_preview': 'true'}
    if reply_to:
        payload['reply_to_message_id'] = reply_to
    data = urllib.parse.urlencode(payload).encode()
    req = urllib.request.Request(f'https://api.telegram.org/bot{token}/sendMessage', data=data, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            body = json.loads(resp.read().decode())
            if body.get('ok'):
                return True, None
            return False, str(body.get('description', 'Ошибка Telegram'))
    except Exception as e:
        return False, str(e)[:200]

def parse_telegram_z_command(text):
    raw = (text or '').strip()
    if not raw.lower().startswith('/z'):
        return None, None
    body = re.sub(r'^/z(?:@\w+)?\s*', '', raw, flags=re.IGNORECASE).strip()
    return parse_booking_body(body)

def parse_telegram_booking_date(token):
    if not token or str(token).lower() == 'сегодня':
        return today()
    if str(token).lower() == 'завтра':
        return (date.today() + timedelta(days=1)).isoformat()
    if str(token).lower() == 'послезавтра':
        return (date.today() + timedelta(days=2)).isoformat()
    token = str(token).replace('/', '.')
    parts = token.split('.')
    try:
        if len(parts) == 2:
            d, m = int(parts[0]), int(parts[1])
            y = date.today().year
        else:
            d, m, y = int(parts[0]), int(parts[1]), int(parts[2])
            if y < 100:
                y += 2000
        return date(y, m, d).isoformat()
    except (ValueError, TypeError):
        return today()

def split_telegram_service_price(rest):
    m = re.match(r'^(.+?)\s+(\d{3,7})$', rest.strip())
    if m:
        return m.group(1).strip(), float(m.group(2))
    return rest.strip(), None

def normalize_voice_transcript(text):
    t = (text or '').strip()
    t = re.sub(r'\s+', ' ', t)
    t = re.sub(
        r'(\d+|один|два|три|четыре|пять|шесть|семь|восемь|девять|десять)\s+тысяч[аи]?\b',
        lambda m: str(_spoken_cardinal_to_int(m.group(1)) * 1000),
        t,
        flags=re.IGNORECASE,
    )
    t = re.sub(r'\bна\s+час\b', '13:00', t, flags=re.IGNORECASE)
    return t.strip()

def _spoken_cardinal_to_int(word):
    if str(word).isdigit():
        return int(word)
    table = {
        'один': 1, 'два': 2, 'три': 3, 'четыре': 4, 'пять': 5,
        'шесть': 6, 'семь': 7, 'восемь': 8, 'девять': 9, 'десять': 10,
    }
    return table.get(str(word).lower(), 0)

def strip_wake_name(text):
    name = telegram_wake_name().lower()
    if not name:
        return text, False
    raw = (text or '').strip()
    low = raw.lower()
    patterns = [
        rf'^(?:эй\s+|слушай\s+)?{re.escape(name)}[!,.\s—-]+',
        rf'^{re.escape(name)}$',
    ]
    for pattern in patterns:
        m = re.match(pattern, low, flags=re.IGNORECASE)
        if m:
            return raw[m.end():].strip(' ,.—-'), True
    first = re.split(r'[\s,]+', low, maxsplit=1)[0].strip('.,!:')
    if first == name:
        parts = re.split(r'[\s,]+', raw, maxsplit=1)
        return (parts[1].strip() if len(parts) > 1 else ''), True
    return raw, False

def telegram_message_to_bot(msg):
    reply = msg.get('reply_to_message') or {}
    author = reply.get('from') or {}
    if not author.get('is_bot'):
        return False
    bot_id = telegram_bot_id()
    return not bot_id or author.get('id') == bot_id

def telegram_download_file(file_id):
    token = telegram_bot_token()
    if not token:
        return None, 'Telegram не настроен'
    import urllib.request
    try:
        with urllib.request.urlopen(f'https://api.telegram.org/bot{token}/getFile?file_id={file_id}', timeout=15) as resp:
            meta = json.loads(resp.read().decode())
        if not meta.get('ok'):
            return None, 'Не удалось получить файл'
        path = meta['result']['file_path']
        with urllib.request.urlopen(f'https://api.telegram.org/file/bot{token}/{path}', timeout=30) as resp:
            return resp.read(), None
    except Exception as e:
        return None, str(e)[:160]

def transcribe_voice_bytes(audio_bytes, filename='voice.ogg'):
    api_key = openai_api_key()
    if not api_key:
        return None, 'Голосовые: укажите ключ OpenAI в Настройках CRM или OPENAI_API_KEY на Timeweb'
    boundary = '----BlackSquare' + os.urandom(8).hex()
    parts = [
        f'--{boundary}\r\nContent-Disposition: form-data; name="model"\r\n\r\nwhisper-1\r\n'.encode(),
        f'--{boundary}\r\nContent-Disposition: form-data; name="language"\r\n\r\nru\r\n'.encode(),
        (
            f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{filename}"\r\n'
            f'Content-Type: audio/ogg\r\n\r\n'
        ).encode() + audio_bytes + b'\r\n',
        f'--{boundary}--\r\n'.encode(),
    ]
    body = b''.join(parts)
    import urllib.request
    import urllib.error
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': f'multipart/form-data; boundary={boundary}',
    }
    delays = (0, 4, 10, 20)
    last_err = ''
    for attempt, delay in enumerate(delays):
        if delay:
            time.sleep(delay)
        req = urllib.request.Request(
            'https://api.openai.com/v1/audio/transcriptions',
            data=body,
            method='POST',
            headers=headers,
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode())
                text = (data.get('text') or '').strip()
                if text:
                    return text, None
                return None, 'Пустая расшифровка'
        except urllib.error.HTTPError as e:
            detail = ''
            try:
                detail = json.loads(e.read().decode()).get('error', {}).get('message', '')
            except Exception:
                pass
            last_err = detail or str(e)
            if e.code == 429 and attempt < len(delays) - 1:
                retry_after = e.headers.get('Retry-After')
                if retry_after:
                    try:
                        time.sleep(min(30, int(retry_after)))
                    except ValueError:
                        pass
                continue
            if e.code == 429:
                return None, 'OpenAI: слишком много запросов. Подождите 1–2 минуты или запишите текстом: /z ...'
            if e.code == 401:
                return None, 'OpenAI: неверный ключ API — проверьте в Настройках CRM'
            if e.code == 402 or 'quota' in last_err.lower() or 'billing' in last_err.lower():
                return None, 'OpenAI: закончился лимит или нет оплаты на аккаунте OpenAI'
            return None, f'Расшифровка OpenAI ({e.code}): {last_err[:120]}'
        except Exception as e:
            return None, f'Расшифровка: {str(e)[:120]}'
    return None, 'OpenAI: лимит запросов. Подождите и повторите или используйте /z текстом'

_voice_last_by_chat = {}

def voice_rate_ok(chat_id):
    now_t = time.time()
    last = _voice_last_by_chat.get(str(chat_id), 0)
    if now_t - last < 12:
        return False, 'Подождите ~15 секунд между голосовыми'
    _voice_last_by_chat[str(chat_id)] = now_t
    return True, ''

def process_telegram_booking(chat_id, parsed, author='', reply_to=None, source='text'):
    con = db()
    try:
        ap, err = create_telegram_z_appointment(con, parsed, author, source=source)
    finally:
        con.close()
    if err:
        telegram_reply(chat_id, f'❌ {err}', reply_to)
        return
    telegram_reply(
        chat_id,
        (
            f'<b>✅ Записано #{ap["id"]}</b>\n'
            f'📅 {ap["date"]} {ap["start"]}–{ap["end"]}\n'
            f'🚗 {ap["car"]}\n'
            f'✂️ {ap["service_name"]}\n'
            f'💰 {ap["price"]:.0f} ₽'
        ),
        reply_to,
    )

def handle_telegram_voice(msg):
    chat = msg.get('chat') or {}
    chat_id = str(chat.get('id', ''))
    allowed = telegram_chat_id()
    if allowed and chat_id != str(allowed):
        return
    voice = msg.get('voice') or msg.get('audio')
    if not voice:
        return
    reply_to = msg.get('message_id')
    replied_to_bot = telegram_message_to_bot(msg)
    audio, err = telegram_download_file(voice['file_id'])
    if err:
        telegram_reply(chat_id, f'❌ {err}', reply_to)
        return
    ok, rate_err = voice_rate_ok(chat_id)
    if not ok:
        telegram_reply(chat_id, f'⏳ {rate_err}', reply_to)
        return
    transcript, err = transcribe_voice_bytes(audio)
    if err:
        telegram_reply(chat_id, f'❌ {err}', reply_to)
        return
    body, woke = strip_wake_name(transcript)
    if not woke and not replied_to_bot:
        return
    body = normalize_voice_transcript(body)
    parsed, err = parse_booking_body(body)
    if err:
        wake = telegram_wake_name()
        telegram_reply(
            chat_id,
            f'🎤 Услышал: <i>{transcript}</i>\n\n{err}\n\nНачните с «{wake}» или ответьте голосом на сообщение бота.',
            reply_to,
        )
        return
    author = ''
    frm = msg.get('from') or {}
    if frm.get('username'):
        author = '@' + frm['username']
    elif frm.get('first_name'):
        author = frm['first_name']
    process_telegram_booking(chat_id, parsed, author, reply_to, source='голос')

def _service_query_tokens(text):
    aliases = {
        'полусфера': 'част', 'полусферы': 'част', 'полусферу': 'част', 'полусфере': 'част',
        'часть': 'част', 'части': 'част', 'частью': 'част',
        'задняя': 'задн', 'задней': 'задн', 'заднюю': 'задн', 'задние': 'задн',
        'передняя': 'передн', 'передней': 'передн', 'передние': 'передн', 'переднюю': 'передн',
        'боковые': 'боков', 'боковая': 'боков', 'боковых': 'боков', 'боковое': 'боков',
        'тонировка': 'тонир', 'тонировку': 'тонир', 'тонировки': 'тонир',
        'атермальная': 'атерм', 'атермальную': 'атерм',
        'пленка': 'плен', 'плёнка': 'плен', 'пленку': 'плен',
    }
    words = re.findall(r'[a-zа-яё0-9]+', (text or '').lower(), flags=re.IGNORECASE)
    out = set()
    for word in words:
        if len(word) < 2:
            continue
        out.add(word)
        out.add(aliases.get(word, word))
        if len(word) > 4:
            out.add(word[:5])
    return out

def _service_match_score(query, service_name):
    q = (query or '').lower().strip()
    n = (service_name or '').lower().strip()
    if not q or not n:
        return 0
    if q in n or n in q:
        return 100
    q_words = _service_query_tokens(q)
    n_words = _service_query_tokens(n)
    overlap = len(q_words & n_words)
    partial = 0
    for qw in q_words:
        if len(qw) < 3:
            continue
        for nw in n_words:
            if qw in nw or nw in qw:
                partial += 1
                break
    return overlap * 10 + partial

def find_services_by_text(con, text):
    text_l = text.lower().strip()
    rows = con.execute("SELECT * FROM services WHERE active=1 ORDER BY name").fetchall()
    if not rows:
        return None, 'В CRM нет активных услуг'
    scored = []
    for s in rows:
        score = _service_match_score(text_l, s['name'])
        if score:
            scored.append((score, s))
    if not scored:
        names = ', '.join(r['name'] for r in rows[:8])
        return None, f'Услуга не найдена: «{text}». Примеры: {names}'
    scored.sort(key=lambda x: (-x[0], x[1]['name']))
    return [scored[0][1]], ''

def create_telegram_z_appointment(con, parsed, author='', source='text'):
    services, err = find_services_by_text(con, parsed['service_text'])
    if err:
        return None, err
    bundle = resolve_services_bundle(con, [s['id'] for s in services])
    if not bundle:
        return None, 'Не удалось подобрать услугу'
    start = parsed['start']
    end = m2hm(hm2m(start) + int(bundle['duration_min']))
    price = float(parsed['price'] if parsed['price'] is not None else bundle['base_price'] or 0)
    car = parsed['car']
    phone = f"TG:{re.sub(r'\\s+', '', car.lower())[:24]}"
    name = car.title()
    cid = get_client(con, name, phone)
    carid = get_car(con, cid, car, '')
    comment = f'Telegram {source}{(": " + author) if author else ""}'
    con.execute(
        "INSERT INTO appointments(client_id,car_id,client_name,phone,car,plate_number,service_id,service_name,appointment_date,start_time,end_time,duration_min,status,employee_id,price,comment,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (cid, carid, name, phone, car, '', bundle['primary_id'], bundle['name'], parsed['date'], start, end, bundle['duration_min'], 'Записан', None, price, comment, now()),
    )
    aid = con.execute("SELECT last_insert_rowid() id").fetchone()['id']
    set_appointment_services(con, aid, bundle['ids'])
    con.commit()
    remote_backup_database()
    return {
        'id': aid,
        'date': parsed['date'],
        'start': start,
        'end': end,
        'car': car,
        'service_name': bundle['name'],
        'price': price,
    }, None

def handle_telegram_message(msg):
    chat = msg.get('chat') or {}
    chat_id = str(chat.get('id', ''))
    allowed = telegram_chat_id()
    if allowed and chat_id != str(allowed):
        return
    if msg.get('voice') or msg.get('audio'):
        handle_telegram_voice(msg)
        return
    text = (msg.get('text') or '').strip()
    if not text:
        return
    low = text.lower()
    if low.startswith('/help'):
        telegram_reply(chat_id, TELEGRAM_Z_HELP, msg.get('message_id'))
        return
    if low == '/z' or re.match(r'^/z@\w+$', low):
        telegram_reply(chat_id, TELEGRAM_Z_HELP, msg.get('message_id'))
        return
    if not low.startswith('/z'):
        return
    parsed, err = parse_telegram_z_command(text)
    if err:
        telegram_reply(chat_id, err, msg.get('message_id'))
        return
    author = ''
    frm = msg.get('from') or {}
    if frm.get('username'):
        author = '@' + frm['username']
    elif frm.get('first_name'):
        author = frm['first_name']
    process_telegram_booking(chat_id, parsed, author, msg.get('message_id'), source='/z')

def process_telegram_updates():
    token = telegram_bot_token()
    if not token:
        return
    offset = int(get_setting('telegram_update_offset', '0') or 0)
    import urllib.request
    url = f'https://api.telegram.org/bot{token}/getUpdates?timeout=20&limit=20'
    if offset:
        url += f'&offset={offset + 1}'
    try:
        with urllib.request.urlopen(url, timeout=25) as resp:
            data = json.loads(resp.read().decode())
    except Exception:
        return
    if not data.get('ok'):
        return
    last_id = offset
    for item in data.get('result', []):
        last_id = max(last_id, int(item.get('update_id', 0)))
        msg = item.get('message') or item.get('edited_message')
        if msg:
            handle_telegram_message(msg)
    if last_id > offset:
        set_setting('telegram_update_offset', str(last_id))

def telegram_poll_loop():
    time.sleep(5)
    while True:
        try:
            process_telegram_updates()
        except Exception:
            pass
        time.sleep(2)

def notify_telegram_new_appointment(ap_date, start_time, client_name, service_name, masters_str, car='', source=''):
    if source == 'Telegram /z':
        return
    telegram_autoconfigure()
    if not telegram_enabled():
        return
    car_part = f'\n🚗 {car}' if car else ''
    src = f'\n📲 {source}' if source else ''
    text = (
        f'<b>Новая запись</b>{src}\n'
        f'📅 {ap_date} {start_time}\n'
        f'👤 {client_name}{car_part}\n'
        f'✂️ {service_name}\n'
        f'👨‍🔧 {masters_str}'
    )
    send_telegram_message(text)

def appointment_master_names(con, ap):
    ids = get_appointment_employee_ids(con, ap['id'], ap['employee_id'])
    if not ids:
        return '—'
    placeholders = ','.join('?' * len(ids))
    rows = con.execute(
        f"SELECT full_name FROM users WHERE id IN ({placeholders}) ORDER BY full_name",
        ids,
    ).fetchall()
    return ', '.join(r['full_name'] for r in rows) or '—'

def notify_telegram_appointment_closed(con, ap, price=None):
    telegram_autoconfigure()
    if not telegram_enabled():
        return
    master = appointment_master_names(con, ap)
    car = (ap['car'] or ap['plate_number'] or '').strip()
    bits = [ap['client_name']]
    if master and master != '—':
        bits.append(f'мастер {master}')
    if car:
        bits.append(car)
    text = f"<b>Запись закрыта</b>\n{' · '.join(bits)}"
    send_telegram_message(text)

def notify_telegram_daily_report(report_date, stats):
    if not telegram_enabled():
        return
    lines = [f'<b>Отчёт за {report_date}</b>', f'💰 Касса: {stats["revenue"]:.0f} ₽', f'📋 Закрыто: {stats["appointments"]}']
    for e in stats.get('by_employee', []):
        lines.append(f'{e["name"]}: {e["revenue"]:.0f} ₽')
    send_telegram_message('\n'.join(lines))

def notify_employee_appointment(employee_ids, ap_date, start_time, client_name, service_name, car='', source=''):
    if not isinstance(employee_ids, (list, tuple)):
        employee_ids = [employee_ids]
    car_part = f' · {car}' if car else ''
    body = f'{ap_date} {start_time} — {client_name}{car_part} · {service_name}'
    for employee_id in employee_ids:
        send_push_to_user(employee_id, 'Новая запись BlackSquare', body, url_for('calendar_view', date=ap_date))
    con = db()
    notify_directors_new_appointment(con, employee_ids, ap_date, start_time, client_name, service_name, car)
    names = []
    for eid in employee_ids:
        u = con.execute("SELECT full_name FROM users WHERE id=?", (eid,)).fetchone()
        if u:
            names.append(u['full_name'])
    notify_telegram_new_appointment(ap_date, start_time, client_name, service_name, ', '.join(names) or '—', car, source)
    con.close()

def get_directors(con):
    return con.execute("SELECT id, full_name FROM users WHERE role='director' AND active=1").fetchall()

def get_director_notification_prefs(con, director_id):
    row = con.execute("SELECT * FROM director_notification_prefs WHERE user_id=?", (director_id,)).fetchone()
    if not row:
        return {'notify_new': 1, 'notify_closed': 1, 'notify_daily': 1}
    return dict(row)

def director_wants_employee(con, director_id, employee_id):
    row = con.execute(
        "SELECT enabled FROM director_employee_notify WHERE director_id=? AND employee_id=?",
        (director_id, employee_id),
    ).fetchone()
    return bool(row['enabled']) if row else True

def notify_directors_new_appointment(con, employee_ids, ap_date, start_time, client_name, service_name, car=''):
    if not isinstance(employee_ids, (list, tuple)):
        employee_ids = [employee_ids]
    names = []
    for eid in employee_ids:
        u = con.execute("SELECT full_name FROM users WHERE id=?", (eid,)).fetchone()
        if u:
            names.append(u['full_name'])
    masters_str = ', '.join(names) if names else '—'
    car_part = f' · {car}' if car else ''
    body = f'{masters_str}: {ap_date} {start_time} — {client_name}{car_part} · {service_name}'
    for d in get_directors(con):
        prefs = get_director_notification_prefs(con, d['id'])
        if not prefs.get('notify_new'):
            continue
        if not any(director_wants_employee(con, d['id'], int(eid)) for eid in employee_ids):
            continue
        send_push_to_user(d['id'], 'Новая запись BlackSquare', body, url_for('calendar_view', date=ap_date))

def notify_directors_appointment_closed(con, ap, price):
    body = f'{ap["client_name"]} · {ap["service_name"]} — {price:.0f} ₽'
    for d in get_directors(con):
        prefs = get_director_notification_prefs(con, d['id'])
        if not prefs.get('notify_closed'):
            continue
        send_push_to_user(
            d['id'], 'Запись закрыта BlackSquare', body,
            url_for('analytics', start=ap['appointment_date'], end=ap['appointment_date']),
        )

def build_daily_report_message(stats):
    lines = [
        f"Касса: {stats['revenue']:.0f} ₽",
        f"ЗП всего: {stats['salary']:.0f} ₽",
        f"Закрыто записей: {stats['appointments']}",
    ]
    for e in stats['by_employee']:
        lines.append(f"{e['name']}: {e['revenue']:.0f} ₽ / ЗП {e['salary']:.0f} ₽")
    return '\n'.join(lines)

def save_and_notify_daily_report(con, report_date):
    if con.execute("SELECT 1 FROM daily_reports WHERE report_date=?", (report_date,)).fetchone():
        return False
    stats = compute_day_stats(con, report_date)
    con.execute(
        "INSERT INTO daily_reports(report_date,revenue,salary,profit,certificate_paid,material_cost,m2,appointments_count,by_employee_json,created_at,notified) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,1)",
        (
            report_date, stats['revenue'], stats['salary'], stats['profit'], stats['certificate_paid'],
            stats['material_cost'], stats['m2'], stats['appointments'],
            json.dumps(stats['by_employee'], ensure_ascii=False), now(),
        ),
    )
    con.commit()
    body = build_daily_report_message(stats)
    title = f'Отчёт за {report_date} готов'
    day_url = url_for('analytics', start=report_date, end=report_date)
    for d in get_directors(con):
        prefs = get_director_notification_prefs(con, d['id'])
        if prefs.get('notify_daily'):
            send_push_to_user(d['id'], title, body, day_url)
    notify_telegram_daily_report(report_date, stats)
    return True

def daily_report_target_date():
    now_dt = datetime.now()
    if now_dt.hour == 23 and now_dt.minute >= 59:
        return today()
    if now_dt.hour == 0 and now_dt.minute < 10:
        return (date.today() - timedelta(days=1)).isoformat()
    return None

def maybe_run_daily_report():
    report_date = daily_report_target_date()
    if not report_date:
        return
    if get_setting('last_daily_report_date', '') == report_date:
        return
    con = db()
    if con.execute("SELECT 1 FROM daily_reports WHERE report_date=?", (report_date,)).fetchone():
        set_setting('last_daily_report_date', report_date)
        con.close()
        return
    if save_and_notify_daily_report(con, report_date):
        set_setting('last_daily_report_date', report_date)
    con.close()

def _daily_report_loop():
    while True:
        try:
            maybe_run_daily_report()
        except Exception:
            pass
        time.sleep(30)

_scheduler_started = False
_scheduler_lock = threading.Lock()

def start_scheduler():
    global _scheduler_started
    with _scheduler_lock:
        if _scheduler_started:
            return
        _scheduler_started = True
    threading.Thread(target=_daily_report_loop, daemon=True, name='daily-report').start()
    threading.Thread(target=telegram_poll_loop, daemon=True, name='telegram-bot').start()

def check_finance_reminders(user):
    if user['role'] != 'director' and not has_perm('finance'):
        return
    key = f'finance_remind_{today()}'
    if session.get(key):
        return
    session[key] = True
    con = db()
    today_s = today()
    rows = con.execute(
        "SELECT * FROM finance_payments WHERE status!='Оплачен' AND due_date<=date(?, '+3 day') ORDER BY due_date",
        (today_s,)
    ).fetchall()
    con.close()
    for r in rows:
        days = (datetime.strptime(r['due_date'], '%Y-%m-%d').date() - date.today()).days
        if days < 0:
            msg = f'Просрочено: {r["title"]} — {r["amount"]:.0f} ₽'
        elif days == 0:
            msg = f'Сегодня оплатить: {r["title"]} — {r["amount"]:.0f} ₽'
        else:
            msg = f'Через {days} дн.: {r["title"]} — {r["amount"]:.0f} ₽'
        send_push_to_user(user['id'], 'Финансы BlackSquare', msg, url_for('finance'))

def user_has_stock_perm(con, user):
    if not user:
        return False
    if user['role'] == 'director':
        return True
    row = con.execute(
        "SELECT allowed FROM user_permissions WHERE user_id=? AND permission='stock'",
        (user['id'],),
    ).fetchone()
    return bool(row and row['allowed'])

def list_stock_for_writeoff(con, user):
    """Материалы для списания при закрытии заказа — без права «Склад»."""
    if not user:
        return []
    if user_has_stock_perm(con, user):
        return con.execute(
            "SELECT id,name,balance,cost_per_unit,category,unit FROM stock_items WHERE active=1 ORDER BY category,name"
        ).fetchall()
    return con.execute(
        "SELECT id,name,0 AS balance,cost_per_unit,category,unit FROM stock_items WHERE active=1 ORDER BY category,name"
    ).fetchall()

def write_off_material(con, aid, uid, item_id, qty, length_m, width_cm, comment=''):
    item = con.execute("SELECT * FROM stock_items WHERE id=? AND active=1", (item_id,)).fetchone()
    if not item or qty <= 0:
        return 0, 'Некорректный материал'
    if item['balance'] < qty:
        return 0, f'На складе не хватает: {item["name"]}'
    cost = qty * float(item['cost_per_unit'] or 0)
    con.execute("UPDATE stock_items SET balance=balance-? WHERE id=?", (qty, item_id))
    con.execute(
        "INSERT INTO stock_moves(item_id,appointment_id,user_id,change_qty,move_type,comment,created_at) VALUES(?,?,?,?,?,?,?)",
        (item_id, aid, uid, -qty, 'Списание по заказу', comment or f'{qty} {item["unit"]}', now())
    )
    con.execute(
        "INSERT INTO appointment_materials(appointment_id,item_id,qty,length_m,width_cm,cost,comment,created_at) VALUES(?,?,?,?,?,?,?,?)",
        (aid, item_id, qty, length_m, width_cm, cost, comment, now())
    )
    return cost, ''

def restore_appointment_materials(con, aid, ap=None):
    mats = con.execute("SELECT * FROM appointment_materials WHERE appointment_id=?", (aid,)).fetchall()
    for m in mats:
        con.execute("UPDATE stock_items SET balance=balance+? WHERE id=?", (m['qty'], m['item_id']))
    con.execute("DELETE FROM appointment_materials WHERE appointment_id=?", (aid,))
    if ap and ap['material_id'] and ap['material_m2'] > 0:
        con.execute("UPDATE stock_items SET balance=balance+? WHERE id=?", (ap['material_m2'], ap['material_id']))

@app.context_processor
def inject():
    return {
        'user': current_user(),
        'has_perm': has_perm,
        'perms': PERMS,
        'visible_phone': visible_phone,
        'mask_phone': mask_phone,
        'booking_url': booking_public_url(),
        'vapid_public_key': vapid_public_key(),
        'request': request,
        'service_price_label': service_price_label,
        'weekdays': WEEKDAYS,
        'today': today(),
    }

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        return login()
    if current_user():
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/healthz')
@app.route('/health')
def healthz():
    return jsonify(status='ok')

_db_initialized = False

def ensure_db():
    global _db_initialized
    if not _db_initialized:
        remote_restore_database()
        restore_database_if_needed()
        init_db()
        telegram_autoconfigure()
        start_scheduler()
        _db_initialized = True

@app.before_request
def prepare_db():
    if request.endpoint not in ('healthz', 'health'):
        ensure_db()

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        con = db(); u = con.execute("SELECT * FROM users WHERE username=? AND active=1", (request.form.get('username','').strip(),)).fetchone(); con.close()
        if u and check_password_hash(u['password_hash'], request.form.get('password','')):
            session['uid'] = u['id']; return redirect(url_for('dashboard'))
        flash('Неверный логин или пароль')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear(); return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    con = db(); u = current_user()
    check_finance_reminders(u)
    if u['role'] == 'master':
        mf = master_appointment_filter_sql()
        upcoming = con.execute(f"SELECT a.*,{EMPLOYEE_NAME_SQL} FROM appointments a LEFT JOIN users u ON u.id=a.employee_id WHERE {mf} AND status NOT IN ('Закрыт','Отменен') ORDER BY appointment_date ASC,start_time ASC LIMIT 12", (u['id'], u['id'])).fetchall()
        completed = con.execute(f"SELECT a.*,{EMPLOYEE_NAME_SQL} FROM appointments a LEFT JOIN users u ON u.id=a.employee_id WHERE {mf} AND status='Закрыт' ORDER BY appointment_date DESC,start_time DESC LIMIT 12", (u['id'], u['id'])).fetchall()
        total = con.execute("SELECT COALESCE(SUM(amount),0) s FROM salary WHERE employee_id=?", (u['id'],)).fetchone()['s']
        con.close(); return render_template('master_dashboard.html', upcoming=upcoming, completed=completed, total=total)

    stats, stats_updated = dashboard_stats()
    rows = con.execute(f"SELECT a.*,{EMPLOYEE_NAME_SQL} FROM appointments a LEFT JOIN users u ON u.id=a.employee_id ORDER BY appointment_date DESC,start_time DESC LIMIT 20").fetchall()
    requests = con.execute("SELECT pr.*,u.full_name user_name,a.client_name,a.plate_number FROM phone_access_requests pr LEFT JOIN users u ON u.id=pr.user_id LEFT JOIN appointments a ON a.id=pr.appointment_id WHERE pr.status='Ожидает' ORDER BY pr.id DESC LIMIT 20").fetchall()
    con.close(); return render_template('dashboard.html', stats=stats, stats_updated=stats_updated, rows=rows, requests=requests)

@app.route('/booking', methods=['GET','POST'])
def booking():
    con = db()
    if request.method == 'POST':
        service_ids = parse_service_ids(request.form)
        uid = request.form.get('employee_id', '').strip()
        d = request.form.get('appointment_date', '').strip()
        start = normalize_hm(request.form.get('start_time', ''))
        ok, err = validate_service_ids(con, service_ids, online_only=True)
        if not ok or not uid or not d or not start:
            con.close()
            flash(err or 'Заполните все поля и выберите свободное время из списка.')
            return redirect(url_for('booking'))
        bundle = resolve_services_bundle(con, service_ids)
        emp = con.execute("SELECT * FROM users WHERE id=? AND active=1 AND role='master'", (uid,)).fetchone()
        if not bundle or not emp or not employee_can_all_services(con, uid, service_ids):
            con.close()
            flash('Мастер не выполняет выбранные услуги')
            return redirect(url_for('booking'))
        end = m2hm(hm2m(start) + int(bundle['duration_min']))
        if not online_slot_allowed(con, uid, service_ids, d, start):
            con.close()
            flash('Это время недоступно для онлайн-записи. Выберите свободное окно из списка.')
            return redirect(url_for('booking'))
        name = request.form['client_name']; phone = request.form['phone']; car = request.form.get('car',''); plate = request.form.get('plate_number','').upper().replace(' ','')
        cid = get_client(con,name,phone); carid = get_car(con,cid,car,plate)
        price = float(request.form.get('price') or bundle['base_price'] or 0)
        con.execute("INSERT INTO appointments(client_id,car_id,client_name,phone,car,plate_number,service_id,service_name,appointment_date,start_time,end_time,duration_min,status,employee_id,price,comment,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (cid,carid,name,phone,car,plate,bundle['primary_id'],bundle['name'],d,start,end,bundle['duration_min'],'Записан',uid,price,request.form.get('comment',''),now()))
        aid = con.execute("SELECT last_insert_rowid() id").fetchone()['id']
        set_appointment_employees(con, aid, [int(uid)])
        set_appointment_services(con, aid, service_ids)
        con.commit()
        remote_backup_database()
        notify_employee_appointment(uid, d, start, name, bundle['name'], car or plate, source='Онлайн-запись')
        con.close()
        return render_template('booking_success.html', services=bundle['rows'], service_name=bundle['name'], emp=emp, d=d, start=start, end=end)
    services = con.execute(
        "SELECT * FROM services WHERE active=1 AND online_calendar=1 ORDER BY category_id, name"
    ).fetchall()
    categories = list_service_categories(con)
    service_groups = group_services_by_category(services, categories)
    con.close()
    return render_template('booking.html', services=services, service_groups=service_groups, default_date=today())

@app.route('/api/masters')
def api_masters():
    con = db()
    service_ids = parse_service_ids_from_request(request.args)
    if not service_ids:
        con.close()
        return jsonify([])
    ok, _ = validate_service_ids(con, service_ids, online_only=True)
    if not ok:
        con.close()
        return jsonify([])
    placeholders = ','.join('?' * len(service_ids))
    rows = con.execute(
        f"SELECT u.id,u.full_name FROM users u WHERE u.active=1 AND u.role='master' "
        f"AND (SELECT COUNT(*) FROM user_services us WHERE us.user_id=u.id AND us.service_id IN ({placeholders}) AND us.allowed=1) = ? "
        f"ORDER BY u.full_name",
        service_ids + [len(service_ids)],
    ).fetchall()
    con.close()
    return jsonify([{'id': r['id'], 'name': r['full_name']} for r in rows])

@app.route('/api/slots')
def api_slots():
    con = db()
    service_ids = parse_service_ids_from_request(request.args)
    uid = request.args.get('employee_id')
    d = request.args.get('date')
    if service_ids:
        ok, _ = validate_service_ids(con, service_ids, online_only=True)
        if not ok:
            con.close()
            return jsonify([])
    bundle = resolve_services_bundle(con, service_ids) if service_ids else None
    out = available_slots_for_duration(con, uid, bundle['duration_min'], d) if bundle else []
    con.close()
    return jsonify(out)

@app.route('/calendar', methods=['GET','POST'])
@login_required
@perm_required('calendar')
def calendar_view():
    con = db(); u = current_user()
    master_error = False
    service_error = False
    form_data = None
    if request.method == 'POST':
        form_data = request.form
        employee_ids = parse_employee_ids(request.form)
        service_ids = parse_service_ids(request.form)
        ok, err = validate_master_ids(con, employee_ids)
        if not ok:
            flash(err)
            master_error = True
        else:
            ok, err = validate_service_ids(con, service_ids)
            if not ok:
                flash(err)
                service_error = True
            else:
                bundle = resolve_services_bundle(con, service_ids)
                d = request.form['appointment_date']; start = request.form['start_time']
                end = m2hm(hm2m(start) + int(bundle['duration_min']))
                name = request.form['client_name']; phone = request.form['phone']; car = request.form.get('car',''); plate = request.form.get('plate_number','').upper().replace(' ','')
                cid = get_client(con,name,phone); carid = get_car(con,cid,car,plate)
                price = float(request.form.get('price') or bundle['base_price'] or 0)
                primary = employee_ids[0]
                con.execute("INSERT INTO appointments(client_id,car_id,client_name,phone,car,plate_number,service_id,service_name,appointment_date,start_time,end_time,duration_min,status,employee_id,price,comment,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                            (cid,carid,name,phone,car,plate,bundle['primary_id'],bundle['name'],d,start,end,bundle['duration_min'],'Записан',primary,price,request.form.get('comment',''),now()))
                aid = con.execute("SELECT last_insert_rowid() id").fetchone()['id']
                set_appointment_employees(con, aid, employee_ids)
                set_appointment_services(con, aid, service_ids)
                con.commit()
                notify_employee_appointment(employee_ids, d, start, name, bundle['name'], car or plate, source='Ручная запись')
                flash('Запись добавлена вручную')
                con.close()
                return redirect(url_for('calendar_view', date=d))

    selected = request.args.get('date') or today(); q = request.args.get('q','').strip()
    month = datetime.strptime(selected, '%Y-%m-%d').date().replace(day=1)
    first, days = pycal.monthrange(month.year, month.month)
    cells = [None] * first
    mf = master_appointment_filter_sql()
    for day in range(1, days+1):
        ds = date(month.year, month.month, day).isoformat()
        if u['role'] == 'master':
            cnt = con.execute(f"SELECT COUNT(*) c FROM appointments a WHERE appointment_date=? AND {mf}", (ds,u['id'],u['id'])).fetchone()['c']
            closed = con.execute(f"SELECT COUNT(*) c FROM appointments a WHERE appointment_date=? AND {mf} AND status='Закрыт'", (ds,u['id'],u['id'])).fetchone()['c']
        else:
            cnt = con.execute("SELECT COUNT(*) c FROM appointments WHERE appointment_date=?", (ds,)).fetchone()['c']
            closed = con.execute("SELECT COUNT(*) c FROM appointments WHERE appointment_date=? AND status='Закрыт'", (ds,)).fetchone()['c']
        cells.append({'day':day,'date':ds,'count':cnt,'closed':closed})
    while len(cells) % 7: cells.append(None)
    sql = f"SELECT a.*,{EMPLOYEE_NAME_SQL} FROM appointments a LEFT JOIN users u ON u.id=a.employee_id WHERE appointment_date=?"
    params = [selected]
    if u['role'] == 'master':
        sql += f" AND {mf}"; params.extend([u['id'], u['id']])
    if q:
        sql += " AND (phone LIKE ? OR plate_number LIKE ? OR client_name LIKE ? OR car LIKE ?)"; params += [f'%{q}%']*4
    sql += " ORDER BY start_time"
    rows = con.execute(sql, params).fetchall()
    load = con.execute("SELECT COUNT(*) c, COALESCE(SUM(duration_min),0) mins FROM appointments WHERE appointment_date=? AND status!='Отменен'", (selected,)).fetchone()
    services = con.execute("SELECT * FROM services WHERE active=1 ORDER BY name").fetchall()
    employees = list_masters(con)
    masters_json = json.dumps([{'id': e['id'], 'name': e['full_name']} for e in employees])
    services_json = json.dumps([{'id': s['id'], 'name': s['name'], 'price': s['base_price'], 'duration': s['duration_min']} for s in services])
    con.close()
    month_start = datetime.strptime(selected, '%Y-%m-%d').date().replace(day=1)
    if month_start.month == 1:
        prev_month_start = date(month_start.year - 1, 12, 1)
    else:
        prev_month_start = date(month_start.year, month_start.month - 1, 1)
    if month_start.month == 12:
        next_month_start = date(month_start.year + 1, 1, 1)
    else:
        next_month_start = date(month_start.year, month_start.month + 1, 1)
    calendar_month_title = f'{MONTHS_RU[month_start.month]} {month_start.year}'
    return render_template(
        'calendar.html',
        cells=cells,
        rows=rows,
        selected=selected,
        q=q,
        load=load,
        services=services,
        employees=employees,
        masters_json=masters_json,
        services_json=services_json,
        master_error=master_error,
        service_error=service_error,
        form_data=form_data,
        calendar_month_title=calendar_month_title,
        prev_month_date=prev_month_start.isoformat(),
        next_month_date=next_month_start.isoformat(),
    )

@app.route('/appointment/<int:aid>/extra', methods=['POST'])
@login_required
@perm_required('extra_services')
def add_extra(aid):
    con = db(); u = current_user()
    ap = con.execute("SELECT * FROM appointments WHERE id=?", (aid,)).fetchone()
    if ap and (u['role'] != 'master' or user_on_appointment(con, aid, u['id'], ap['employee_id'])):
        name = request.form.get('extra_name','').strip(); price = float(request.form.get('extra_price') or 0)
        if name:
            con.execute("INSERT INTO appointment_extras(appointment_id,name,price,employee_id,created_at) VALUES(?,?,?,?,?)", (aid,name,price,u['id'],now()))
            con.execute("UPDATE appointments SET extras_total=extras_total+?, price=price+? WHERE id=?", (price,price,aid))
            con.commit(); flash('Допуслуга добавлена')
    con.close(); return redirect(url_for('close_appointment', aid=aid))

@app.route('/appointment/<int:aid>/extra/<int:eid>/delete', methods=['POST'])
@login_required
@perm_required('extra_services')
def delete_extra(aid, eid):
    con = db(); u = current_user()
    ex = con.execute("SELECT * FROM appointment_extras WHERE id=? AND appointment_id=?", (eid,aid)).fetchone()
    ap = con.execute("SELECT * FROM appointments WHERE id=?", (aid,)).fetchone()
    if ex and ap and (u['role'] != 'master' or user_on_appointment(con, aid, u['id'], ap['employee_id'])):
        con.execute("DELETE FROM appointment_extras WHERE id=?", (eid,))
        con.execute("UPDATE appointments SET extras_total=extras_total-?, price=price-? WHERE id=?", (ex['price'],ex['price'],aid))
        con.commit(); flash('Допуслуга удалена')
    con.close(); return redirect(url_for('close_appointment', aid=aid))

def reset_appointment_close_data(con, aid, ap):
    restore_appointment_materials(con, aid, ap)
    con.execute("DELETE FROM salary WHERE appointment_id=?", (aid,))
    con.execute("UPDATE appointments SET material_id=NULL,material_length_m=0,material_width_cm=0,material_m2=0,material_cost=0,salary_amount=0,profit=0,closed_at=NULL WHERE id=?", (aid,))

def process_materials_from_form(con, aid, uid, form):
    material_cost = 0
    total_m2 = 0
    first_film_id = None
    first_len = first_w = 0
    item_ids = form.getlist('material_item_id')
    lengths = form.getlist('material_length_m')
    widths = form.getlist('material_width_cm')
    qtys = form.getlist('material_qty')
    for i, item_id in enumerate(item_ids):
        if not item_id:
            continue
        item = con.execute("SELECT * FROM stock_items WHERE id=? AND active=1", (item_id,)).fetchone()
        if not item:
            return None, 'Материал не найден'
        if item['category'] == 'film':
            length = float(lengths[i] if i < len(lengths) else 0 or 0)
            width = float(widths[i] if i < len(widths) else 0 or 0)
            qty = length * (width / 100)
            comment = f'{length} м × {width} см = {qty:.2f} м²'
            if not first_film_id:
                first_film_id = item_id
                first_len, first_w = length, width
        else:
            length = width = 0
            qty = float(qtys[i] if i < len(qtys) else 0 or 0)
            comment = f'{qty} {item["unit"]}'
        if qty <= 0:
            continue
        cost, err = write_off_material(con, aid, uid, int(item_id), qty, length, width, comment)
        if err:
            return None, err
        material_cost += cost
        if item['category'] == 'film':
            total_m2 += qty
    return {
        'material_cost': material_cost,
        'total_m2': total_m2,
        'first_film_id': first_film_id,
        'first_len': first_len,
        'first_w': first_w,
    }, ''

@app.route('/appointment/<int:aid>/edit', methods=['GET', 'POST'])
@login_required
def edit_appointment(aid):
    con = db(); u = current_user()
    ap = con.execute(f"SELECT a.*,{EMPLOYEE_NAME_SQL} FROM appointments a LEFT JOIN users u ON u.id=a.employee_id WHERE a.id=?", (aid,)).fetchone()
    if not ap:
        con.close(); flash('Запись не найдена'); return redirect(url_for('calendar_view'))
    is_closed = ap['status'] == 'Закрыт'
    if is_closed:
        if not has_perm('edit_closed_appointments'):
            con.close(); flash('Нет права редактировать закрытые заказы'); return redirect(url_for('calendar_view', date=ap['appointment_date']))
    elif not has_perm('calendar'):
        con.close(); flash('Нет доступа'); return redirect(url_for('dashboard'))
    if u['role'] == 'master' and not user_on_appointment(con, aid, u['id'], ap['employee_id']) and not is_closed:
        con.close(); flash('Можно редактировать только свои записи'); return redirect(url_for('calendar_view'))
    master_error = False
    if request.method == 'POST':
        if is_closed:
            reset_appointment_close_data(con, aid, ap)
            ap = con.execute("SELECT * FROM appointments WHERE id=?", (aid,)).fetchone()
            price = float(request.form.get('price') or 0)
            salary_amount = float(request.form.get('salary_amount') or 0)
            mat, err = process_materials_from_form(con, aid, u['id'], request.form)
            if err:
                con.rollback(); con.close(); flash(err); return redirect(url_for('edit_appointment', aid=aid))
            material_cost = mat['material_cost']
            cert_number = request.form.get('cert_number', '')
            cert_amount = request.form.get('cert_amount') or 0
            ok, cert_msg = pay_certificate_for_appointment(con, aid, cert_number, cert_amount, request.form.get('cert_comment', ''))
            if not ok:
                con.rollback(); con.close(); flash(cert_msg); return redirect(url_for('edit_appointment', aid=aid))
            cert_paid = float(ap['certificate_paid'] or 0) + float(cert_amount or 0)
            profit = price - cert_paid - material_cost - salary_amount
            con.execute(
                "UPDATE appointments SET status='Закрыт',price=?,material_id=?,material_length_m=?,material_width_cm=?,material_m2=?,material_cost=?,salary_amount=?,profit=?,comment=?,closed_at=? WHERE id=?",
                (price, mat['first_film_id'], mat['first_len'], mat['first_w'], mat['total_m2'], material_cost, salary_amount, profit, request.form.get('comment', ap['comment'] or ''), now(), aid)
            )
            if salary_amount > 0:
                con.execute("INSERT INTO salary(employee_id,appointment_id,period,amount,comment,created_at) VALUES(?,?,?,?,?,?)",
                            (ap['employee_id'], aid, datetime.now().strftime('%m.%Y'), salary_amount, request.form.get('comment', '') or 'ЗП из закрытой записи', now()))
            con.commit()
            refresh_dashboard_stats()
            con.close(); flash('Закрытый заказ обновлён')
            return redirect(url_for('calendar_view', date=ap['appointment_date']))
        employee_ids = parse_employee_ids(request.form)
        ok, err = validate_master_ids(con, employee_ids)
        if not ok:
            con.close(); flash(err); return redirect(url_for('edit_appointment', aid=aid, master_error=1))
        service_ids = parse_service_ids(request.form)
        ok, err = validate_service_ids(con, service_ids)
        if not ok:
            con.close(); flash(err); return redirect(url_for('edit_appointment', aid=aid))
        bundle = resolve_services_bundle(con, service_ids)
        primary = employee_ids[0]; d = request.form['appointment_date']; start = request.form['start_time']
        end = m2hm(hm2m(start) + int(bundle['duration_min']))
        name = request.form['client_name']; phone = request.form['phone']; car = request.form.get('car', ''); plate = request.form.get('plate_number', '').upper().replace(' ', '')
        price = float(request.form.get('price') or bundle['base_price'] or 0)
        con.execute(
            "UPDATE appointments SET client_name=?,phone=?,car=?,plate_number=?,service_id=?,service_name=?,appointment_date=?,start_time=?,end_time=?,duration_min=?,employee_id=?,price=?,comment=? WHERE id=?",
            (name, phone, car, plate, bundle['primary_id'], bundle['name'], d, start, end, bundle['duration_min'], primary, price, request.form.get('comment', ''), aid)
        )
        set_appointment_employees(con, aid, employee_ids)
        set_appointment_services(con, aid, service_ids)
        con.commit(); con.close(); flash('Запись обновлена')
        return redirect(url_for('calendar_view', date=d))
    materials = list_stock_for_writeoff(con, u)
    extras = con.execute("SELECT * FROM appointment_extras WHERE appointment_id=? ORDER BY id DESC", (aid,)).fetchall()
    used_materials = con.execute(
        "SELECT am.*, si.name, si.category, si.unit FROM appointment_materials am LEFT JOIN stock_items si ON si.id=am.item_id WHERE am.appointment_id=?",
        (aid,)
    ).fetchall()
    services = con.execute("SELECT * FROM services WHERE active=1 ORDER BY name").fetchall()
    employees = list_masters(con)
    selected_employee_ids = get_appointment_employee_ids(con, aid, ap['employee_id'])
    selected_service_ids = get_appointment_service_ids(con, aid, ap['service_id'])
    master_error = request.args.get('master_error') == '1'
    masters_json = json.dumps([{'id': e['id'], 'name': e['full_name']} for e in employees])
    services_json = json.dumps([{'id': s['id'], 'name': s['name'], 'price': s['base_price'], 'duration': s['duration_min']} for s in services])
    con.close()
    return render_template('edit_appointment.html', ap=ap, materials=materials, extras=extras, used_materials=used_materials, services=services, employees=employees, selected_employee_ids=selected_employee_ids, selected_service_ids=selected_service_ids, masters_json=masters_json, services_json=services_json, is_closed=is_closed, is_master=(u['role'] == 'master'), master_error=master_error)

@app.route('/appointment/<int:aid>/close', methods=['GET','POST'])
@login_required
@perm_required('calendar')
def close_appointment(aid):
    con = db(); u = current_user()
    ap = con.execute(f"SELECT a.*,{EMPLOYEE_NAME_SQL} FROM appointments a LEFT JOIN users u ON u.id=a.employee_id WHERE a.id=?", (aid,)).fetchone()
    if not ap:
        con.close(); flash('Запись не найдена'); return redirect(url_for('calendar_view'))
    if u['role'] == 'master' and not user_on_appointment(con, aid, u['id'], ap['employee_id']):
        con.close(); flash('Можно закрывать только свои записи'); return redirect(url_for('calendar_view'))
    if request.method == 'POST':
        price = float(request.form.get('price') or 0)
        salary_amount = float(request.form.get('salary_amount') or 0)
        mat, err = process_materials_from_form(con, aid, u['id'], request.form)
        if err:
            con.close(); flash(err); return redirect(url_for('close_appointment', aid=aid))
        material_cost = mat['material_cost']
        total_m2 = mat['total_m2']
        first_film_id = mat['first_film_id']
        cert_number = request.form.get('cert_number','')
        cert_amount = request.form.get('cert_amount') or 0
        ok, cert_msg = pay_certificate_for_appointment(con, aid, cert_number, cert_amount, request.form.get('cert_comment',''))
        if not ok:
            flash(cert_msg)
            return redirect(url_for('close_appointment', aid=aid))
        cert_paid = float(ap['certificate_paid'] or 0) + float(cert_amount or 0)
        bonus_spent = float(request.form.get('bonus_spent') or 0)
        if bonus_spent > 0 and ap['client_id']:
            ok, berr = spend_client_bonus(con, ap['client_id'], bonus_spent, aid, u['id'], 'Списание при закрытии визита')
            if not ok:
                con.close()
                flash(berr)
                return redirect(url_for('close_appointment', aid=aid))
        friend_discount_code = request.form.get('friend_discount_code', '').strip()
        friend_discount_amount = 0.0
        friend_discount_applied = False
        if friend_discount_code:
            fc_row, ferr = lookup_friend_discount_code(con, friend_discount_code)
            if not fc_row:
                con.close()
                flash(ferr)
                return redirect(url_for('close_appointment', aid=aid))
            percent = float(fc_row['discount_percent'] or global_friend_discount_percent())
            friend_discount_amount = round(float(price) * percent / 100.0, 2)
            price = round(float(price) - friend_discount_amount, 2)
            friend_discount_applied = True
        profit = price - cert_paid - material_cost - salary_amount - bonus_spent
        con.execute("UPDATE appointments SET status='Закрыт',price=?,material_id=?,material_length_m=?,material_width_cm=?,material_m2=?,material_cost=?,salary_amount=?,profit=?,comment=?,friend_discount_code=?,friend_discount_amount=?,closed_at=? WHERE id=?",
                    (price, first_film_id, mat['first_len'], mat['first_w'], total_m2, material_cost, salary_amount, profit, request.form.get('comment',''), friend_discount_code if friend_discount_applied else None, friend_discount_amount, now(), aid))
        if friend_discount_applied:
            use_friend_discount_code(con, fc_row, aid)
        if salary_amount > 0:
            con.execute("INSERT INTO salary(employee_id,appointment_id,period,amount,comment,created_at) VALUES(?,?,?,?,?,?)", (ap['employee_id'], aid, datetime.now().strftime('%m.%Y'), salary_amount, request.form.get('comment','') or 'ЗП из закрытой записи', now()))
        ap_closed = con.execute("SELECT * FROM appointments WHERE id=?", (aid,)).fetchone()
        earned, earn_msg = accrue_bonus_on_close(con, ap_closed, price, u['id'], skip_bonus=friend_discount_applied)
        con.commit()
        refresh_dashboard_stats()
        notify_directors_appointment_closed(con, ap_closed, price)
        notify_telegram_appointment_closed(con, ap_closed, price)
        con.close()
        extra = []
        if friend_discount_applied:
            extra.append(f'Скидка для друзей −{friend_discount_amount:.0f} ₽')
        if earn_msg:
            extra.append(earn_msg)
        flash('Запись закрыта' + (f'. {" · ".join(extra)}' if extra else ''))
        return redirect(url_for('calendar_view', date=ap['appointment_date']))
    materials = list_stock_for_writeoff(con, u)
    extras = con.execute("SELECT * FROM appointment_extras WHERE appointment_id=? ORDER BY id DESC", (aid,)).fetchall()
    client_bonus = None
    if ap['client_id']:
        client_bonus = con.execute("SELECT bonus_balance, bonus_code, bonus_enabled FROM clients WHERE id=?", (ap['client_id'],)).fetchone()
    con.close()
    return render_template('close.html', ap=ap, materials=materials, extras=extras, is_master=(u['role']=='master'), client_bonus=client_bonus, bonus_percent=global_bonus_percent(), friend_discount_percent=global_friend_discount_percent())

@app.route('/api/friend_discount_check')
@login_required
def api_friend_discount_check():
    code = request.args.get('code', '').strip()
    con = db()
    row, err = lookup_friend_discount_code(con, code)
    con.close()
    if not row:
        return jsonify(ok=False, message=err or 'Код не найден')
    return jsonify(
        ok=True,
        percent=float(row['discount_percent'] or global_friend_discount_percent()),
        name=row['name'],
        card_number=row['card_number'],
    )

@app.route('/appointment/<int:aid>/delete', methods=['POST'])
@login_required
@perm_required('delete_appointments')
def delete_appointment(aid):
    con = db()
    ap = con.execute("SELECT * FROM appointments WHERE id=?", (aid,)).fetchone()
    if ap:
        restore_appointment_materials(con, aid, ap)
        con.execute("DELETE FROM appointment_extras WHERE appointment_id=?", (aid,))
        con.execute("DELETE FROM appointment_employees WHERE appointment_id=?", (aid,))
        con.execute("DELETE FROM salary WHERE appointment_id=?", (aid,))
        con.execute("DELETE FROM appointments WHERE id=?", (aid,))
        con.commit()
        if ap['status'] == 'Закрыт':
            refresh_dashboard_stats()
        con.close(); flash('Запись удалена')
    else:
        con.close()
    return redirect(url_for('calendar_view', date=request.form.get('date') or today()))
@app.route('/phone_request/<int:aid>', methods=['POST'])
@login_required
def phone_request(aid):
    con = db()
    u = current_user()
    ap = con.execute("SELECT * FROM appointments WHERE id=?", (aid,)).fetchone()
    if not ap:
        con.close()
        flash('Запись не найдена')
        return redirect(url_for('dashboard'))
    exists = con.execute("SELECT id FROM phone_access_requests WHERE user_id=? AND appointment_id=? AND status='Ожидает'", (u['id'], aid)).fetchone()
    if not exists:
        con.execute("INSERT INTO phone_access_requests(user_id,appointment_id,client_id,phone,reason,created_at) VALUES(?,?,?,?,?,?)",
                    (u['id'], aid, ap['client_id'], ap['phone'], request.form.get('reason',''), now()))
        con.commit()
        flash('Запрос на доступ к номеру отправлен директору')
    else:
        flash('Запрос уже отправлен и ожидает решения')
    con.close()
    return redirect(request.referrer or url_for('dashboard'))

@app.route('/phone_request/<int:rid>/approve', methods=['POST'])
@login_required
def approve_phone_request(rid):
    if current_user()['role'] != 'director' and not has_perm('phone_access'):
        flash('Нет доступа')
        return redirect(url_for('dashboard'))
    con = db()
    # доступ до конца текущего дня
    until = datetime.now().strftime('%Y-%m-%d') + ' 23:59'
    con.execute("UPDATE phone_access_requests SET status='Одобрен', approved_until=?, decided_at=?, decided_by=? WHERE id=?",
                (until, now(), current_user()['id'], rid))
    con.commit()
    con.close()
    flash('Доступ к номеру одобрен до конца дня')
    return redirect(url_for('dashboard'))

@app.route('/phone_request/<int:rid>/deny', methods=['POST'])
@login_required
def deny_phone_request(rid):
    if current_user()['role'] != 'director' and not has_perm('phone_access'):
        flash('Нет доступа')
        return redirect(url_for('dashboard'))
    con = db()
    con.execute("UPDATE phone_access_requests SET status='Отклонен', decided_at=?, decided_by=? WHERE id=?", (now(), current_user()['id'], rid))
    con.commit()
    con.close()
    flash('Запрос отклонен')
    return redirect(url_for('dashboard'))

def pay_certificate_for_appointment(con, aid, number, amount, comment):
    number = (number or '').strip().upper()
    amount = float(amount or 0)
    if not number or amount <= 0:
        return True, ''
    cert = con.execute("SELECT * FROM certificates WHERE cert_number=? AND status='Активен'", (number,)).fetchone()
    if not cert:
        return False, 'Сертификат не найден или не активен'
    if cert['balance'] < amount:
        return False, f'Недостаточно средств на сертификате. Остаток: {cert["balance"]:.0f} ₽'
    new_balance = cert['balance'] - amount
    status = 'Использован' if new_balance <= 0 else 'Активен'
    con.execute("UPDATE certificates SET balance=?, status=? WHERE id=?", (new_balance, status, cert['id']))
    con.execute("INSERT INTO certificate_moves(certificate_id,appointment_id,user_id,amount,move_type,comment,created_at) VALUES(?,?,?,?,?,?,?)",
                (cert['id'], aid, current_user()['id'], -amount, 'Списание из закрытия записи', comment, now()))
    con.execute("UPDATE appointments SET certificate_paid=certificate_paid+? WHERE id=?", (amount, aid))
    return True, f'Списано с сертификата {amount:.0f} ₽'


CERT_TEMPLATE_PATH = BASE_DIR / 'static' / 'certificate_template.pdf'
CERT_LAYOUT_PATH = BASE_DIR / 'static' / 'certificate_layout.json'

# Запасные координаты (доли страницы), если линии не найдены.
CERT_PDF_LAYOUT = {
    'number_y': 0.145,
    'number_right': 48,
    'number_fontsize': 12,
    'amount_y': 0.655,
    'amount_left': 0.250,
    'amount_right': 0.735,
    'amount_fontsize': 28,
}

def _cluster_scan_lines(rows, gap=4):
    if not rows:
        return []
    rows = sorted(rows, key=lambda row: row['y'])
    clusters = [[rows[0]]]
    for row in rows[1:]:
        if row['y'] - clusters[-1][-1]['y'] <= gap:
            clusters[-1].append(row)
        else:
            clusters.append([row])
    merged = []
    for cluster in clusters:
        best = max(cluster, key=lambda row: row['len'])
        merged.append({
            'y': sum(row['y'] for row in cluster) / len(cluster),
            'x1': min(row['x1'] for row in cluster),
            'x2': max(row['x2'] for row in cluster),
            'len': best['len'],
        })
    return sorted(merged, key=lambda row: row['y'])

def _scan_certificate_image_lines(page):
    import fitz
    w, h = page.rect.width, page.rect.height
    scale = 2
    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), colorspace=fitz.csRGB)
    pw = pix.width
    data = pix.samples
    threshold = 180
    min_run = int(pw * 0.08)
    rows = []
    for y in range(pix.height):
        best_run = 0
        best_x1 = best_x2 = 0
        run = 0
        cur_x1 = 0
        for x in range(pw):
            i = (y * pw + x) * 3
            r, g, b = data[i], data[i + 1], data[i + 2]
            if r >= threshold and g >= threshold and b >= threshold:
                if run == 0:
                    cur_x1 = x
                run += 1
            else:
                if run > best_run:
                    best_run = run
                    best_x1, best_x2 = cur_x1, x
                run = 0
        if run > best_run:
            best_run = run
            best_x1, best_x2 = cur_x1, pw
        if best_run >= min_run:
            rows.append({
                'y': y / scale,
                'x1': best_x1 / scale,
                'x2': best_x2 / scale,
                'len': best_run / scale,
            })
    lines = _cluster_scan_lines(rows)
    return [line for line in lines if line['len'] < w * 0.9]

def _pick_certificate_lines(lines, w, h):
    number_line = None
    amount_line = None
    upper_lines = [
        line for line in lines
        if line['y'] < h * 0.22 and line['x2'] > w * 0.72 and line['len'] < w * 0.25
    ]
    if upper_lines:
        number_line = max(upper_lines, key=lambda line: line['x2'])
    mid_lines = [
        line for line in lines
        if h * 0.35 < line['y'] < h * 0.82 and w * 0.15 < line['len'] < w * 0.85
    ]
    if mid_lines:
        amount_line = max(mid_lines, key=lambda line: line['len'])
    return number_line, amount_line

def _layout_from_lines(number_line, amount_line, w, h, fallback):
    num_fs = fallback['number_fontsize']
    amt_fs = fallback['amount_fontsize']
    if number_line:
        num_y = number_line['y'] - num_fs * 0.2
        num_x_right = number_line['x2'] - 8
    else:
        num_y = h * fallback['number_y']
        num_x_right = w - fallback['number_right']
    if amount_line:
        amt_y = amount_line['y'] - amt_fs * 0.15
        amount_left = amount_line['x1'] + 8
        amount_right = amount_line['x2'] - 8
    else:
        amt_y = h * fallback['amount_y']
        amount_left = w * fallback['amount_left']
        amount_right = w * fallback['amount_right']
    return {
        'number_y': num_y,
        'number_x_right': num_x_right,
        'number_fontsize': num_fs,
        'amount_y': amt_y,
        'amount_left': amount_left,
        'amount_right': amount_right,
        'amount_fontsize': amt_fs,
    }

def calibrate_certificate_layout(page):
    w, h = page.rect.width, page.rect.height
    fallback = CERT_PDF_LAYOUT
    vector_lines = _certificate_horizontal_lines(page)
    number_line, amount_line = _pick_certificate_lines(vector_lines, w, h)
    if not number_line or not amount_line:
        image_lines = _scan_certificate_image_lines(page)
        img_number, img_amount = _pick_certificate_lines(image_lines, w, h)
        number_line = number_line or img_number
        amount_line = amount_line or img_amount

    texts = _certificate_text_boxes(page)
    summa = next((t for t in texts if 'СУММ' in t['upper'] or t['upper'].startswith('SUMMA')), None)
    rub = next((t for t in texts if 'РУБ' in t['upper'] or t['upper'].startswith('RUB')), None)
    number_mark = next((t for t in texts if t['upper'] in ('№', 'NO', 'Nº', 'N°') or '№' in t['text']), None)

    if not number_line and number_mark:
        layout = _layout_from_lines(None, amount_line, w, h, fallback)
        layout['number_y'] = number_mark['cy'] + fallback['number_fontsize'] * 0.35
        layout['number_x_right'] = w - fallback['number_right']
        return layout

    layout = _layout_from_lines(number_line, amount_line, w, h, fallback)
    if rub and amount_line and rub['x0'] > amount_line['x2'] - 20:
        layout['amount_right'] = rub['x0'] - 8
    elif rub and not amount_line:
        layout['amount_right'] = max(layout['amount_left'] + 80, rub['x0'] - 8)
        layout['amount_y'] = rub['y1'] - 2
    elif summa and not amount_line:
        layout['amount_y'] = summa['y1'] + (h * fallback['amount_y'] - summa['y1']) + layout['amount_fontsize'] * 0.2
    return layout

def save_certificate_layout(page):
    layout = calibrate_certificate_layout(page)
    w, h = page.rect.width, page.rect.height
    payload = {
        'number_y_ratio': layout['number_y'] / h,
        'number_x_right_ratio': layout['number_x_right'] / w,
        'number_fontsize': layout['number_fontsize'],
        'amount_y_ratio': layout['amount_y'] / h,
        'amount_left_ratio': layout['amount_left'] / w,
        'amount_right_ratio': layout['amount_right'] / w,
        'amount_fontsize': layout['amount_fontsize'],
    }
    CERT_LAYOUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    CERT_LAYOUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')

def load_certificate_layout(page):
    if not CERT_LAYOUT_PATH.exists():
        return None
    try:
        data = json.loads(CERT_LAYOUT_PATH.read_text(encoding='utf-8'))
        w, h = page.rect.width, page.rect.height
        return {
            'number_y': h * float(data['number_y_ratio']),
            'number_x_right': w * float(data['number_x_right_ratio']),
            'number_fontsize': int(data['number_fontsize']),
            'amount_y': h * float(data['amount_y_ratio']),
            'amount_left': w * float(data['amount_left_ratio']),
            'amount_right': w * float(data['amount_right_ratio']),
            'amount_fontsize': int(data['amount_fontsize']),
        }
    except Exception:
        return None

def _certificate_horizontal_lines(page):
    w = page.rect.width
    lines = []
    for drawing in page.get_drawings():
        for item in drawing.get('items', ()):
            if item[0] != 'l':
                continue
            p1, p2 = item[1], item[2]
            if abs(p1.y - p2.y) > 4:
                continue
            x1, x2 = sorted((p1.x, p2.x))
            if (x2 - x1) < w * 0.12:
                continue
            lines.append({'x1': x1, 'x2': x2, 'y': (p1.y + p2.y) / 2})
    return sorted(lines, key=lambda line: line['y'])

def _certificate_text_boxes(page):
    boxes = []
    for block in page.get_text('dict').get('blocks', ()):
        if block.get('type') != 0:
            continue
        for line in block.get('lines', ()):
            for span in line.get('spans', ()):
                text = span.get('text', '').strip()
                if not text:
                    continue
                x0, y0, x1, y1 = span['bbox']
                boxes.append({
                    'text': text,
                    'upper': text.upper(),
                    'x0': x0, 'y0': y0, 'x1': x1, 'y1': y1,
                    'cx': (x0 + x1) / 2,
                    'cy': (y0 + y1) / 2,
                })
    return boxes

def certificate_overlay_positions(page):
    saved = load_certificate_layout(page)
    if saved:
        return saved
    return calibrate_certificate_layout(page)

def make_certificate_number(con):
    row = con.execute(
        "SELECT COALESCE(MAX(CAST(cert_number AS INTEGER)), 100000) n FROM certificates WHERE cert_number GLOB '[0-9]*'"
    ).fetchone()
    return str(int(row['n']) + 1)

def ensure_certificate_template():
    CERT_TEMPLATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    if CERT_TEMPLATE_PATH.exists() and CERT_TEMPLATE_PATH.stat().st_size > 500:
        return str(CERT_TEMPLATE_PATH)
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.colors import Color
        w, h = A4
        c = canvas.Canvas(str(CERT_TEMPLATE_PATH), pagesize=A4)
        c.setFillColor(Color(0.05, 0.05, 0.05))
        c.rect(0, 0, w, h, fill=1, stroke=0)
        c.setStrokeColor(Color(1, 1, 1))
        c.setLineWidth(1.5)
        c.rect(28, 28, w - 56, h - 56, fill=0, stroke=1)
        c.setFillColor(Color(1, 1, 1))
        c.setFont('Helvetica', 11)
        c.drawRightString(w - 70, h - 52, 'No')
        c.line(w - 170, h - 56, w - 48, h - 56)
        c.setFont('Helvetica-Bold', 28)
        c.drawCentredString(w / 2, h - 130, 'PODAROCHNYI')
        c.drawCentredString(w / 2, h - 168, 'SERTIFIKAT')
        c.setFont('Helvetica', 14)
        c.drawCentredString(w / 2, h - 250, 'SUMMA:')
        c.line(w * 0.22, h - 290, w * 0.62, h - 290)
        c.drawString(w * 0.64, h - 298, 'RUB.')
        c.setFont('Helvetica-Bold', 16)
        c.drawCentredString(w / 2, 95, 'V KVADRATE')
        c.setFont('Helvetica', 8)
        c.drawCentredString(w / 2, 52, 'TONIROVKA | POLIROVKA | KERAMIKA | ZASHCHITNYE POKRYTIYA / PLYONKI')
        c.save()
    except Exception:
        return None
    return str(CERT_TEMPLATE_PATH)

def _overlay_certificate_amount(page, amount_txt, pos, white):
    import fitz
    amt_fs = pos['amount_fontsize']
    rect = fitz.Rect(
        pos['amount_left'],
        pos['amount_y'] - amt_fs * 0.9,
        pos['amount_right'],
        pos['amount_y'] + amt_fs * 0.05,
    )
    leftover = page.insert_textbox(
        rect,
        amount_txt,
        fontsize=amt_fs,
        fontname='helv',
        color=white,
        align=fitz.TEXT_ALIGN_CENTER,
    )
    if leftover >= 0:
        return
    amt_tw = fitz.get_text_length(amount_txt, fontname='helv', fontsize=amt_fs)
    amt_x = (pos['amount_left'] + pos['amount_right']) / 2 - amt_tw / 2
    page.insert_text(
        (amt_x, pos['amount_y']),
        amount_txt,
        fontsize=amt_fs,
        fontname='helv',
        color=white,
    )

def render_certificate_pdf(cert_number, amount):
    template = ensure_certificate_template()
    amount_txt = f'{int(round(float(amount))):,}'.replace(',', ' ')
    if template:
        try:
            import fitz
            doc = fitz.open(template)
            page = doc[0]
            white = (1, 1, 1)
            pos = certificate_overlay_positions(page)
            num_fs = pos['number_fontsize']
            num_tw = fitz.get_text_length(str(cert_number), fontname='helv', fontsize=num_fs)
            num_x = pos['number_x_right'] - num_tw
            page.insert_text(
                (num_x, pos['number_y']),
                str(cert_number),
                fontsize=num_fs,
                fontname='helv',
                color=white,
            )
            _overlay_certificate_amount(page, amount_txt, pos, white)
            pdf = doc.tobytes()
            doc.close()
            return pdf
        except Exception:
            pass
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.colors import Color
        buf = io.BytesIO()
        w, h = A4
        c = canvas.Canvas(buf, pagesize=A4)
        c.setFillColor(Color(0.05, 0.05, 0.05))
        c.rect(0, 0, w, h, fill=1, stroke=0)
        c.setFillColor(Color(1, 1, 1))
        c.setFont('Helvetica-Bold', 24)
        c.drawCentredString(w / 2, h - 120, 'PODAROCHNYI SERTIFIKAT')
        c.setFont('Helvetica', 14)
        c.drawRightString(w - 40, h - 50, f'No {cert_number}')
        c.setFont('Helvetica-Bold', 36)
        c.drawCentredString(w / 2, h / 2, f'{amount_txt} RUB')
        c.save()
        return buf.getvalue()
    except Exception:
        return None


@app.route('/api/certificate_balance')
@login_required
def api_certificate_balance():
    number = request.args.get('number','').strip().upper()
    con = db()
    cert = con.execute("SELECT cert_number,balance,status FROM certificates WHERE cert_number=?", (number,)).fetchone()
    con.close()
    if not cert:
        return jsonify({"ok": False, "message": "Сертификат не найден"})
    return jsonify({"ok": True, "balance": cert["balance"], "status": cert["status"]})


@app.route('/appointment/<int:aid>/cancel', methods=['POST'])
@login_required
def cancel(aid):
    con = db(); u = current_user()
    ap = con.execute("SELECT * FROM appointments WHERE id=?", (aid,)).fetchone()
    if not ap:
        con.close(); flash('Запись не найдена'); return redirect(url_for('calendar_view'))
    if not can_manage_open_appointment(u, con, ap):
        con.close(); flash('Нет доступа или запись уже закрыта'); return redirect(url_for('calendar_view', date=request.form.get('date') or ap['appointment_date']))
    reason = (request.form.get('cancel_reason') or 'Не приехал').strip()
    note = f'Отмена: {reason}'
    comment = f"{ap['comment']}\n{note}".strip() if ap['comment'] else note
    con.execute("UPDATE appointments SET status='Отменен', comment=? WHERE id=?", (comment, aid))
    con.commit(); con.close()
    flash('Запись отменена'); return redirect(url_for('calendar_view', date=request.form.get('date') or ap['appointment_date']))

@app.route('/appointment/<int:aid>/reschedule', methods=['POST'])
@login_required
def reschedule_appointment(aid):
    con = db(); u = current_user()
    ap = con.execute("SELECT * FROM appointments WHERE id=?", (aid,)).fetchone()
    if not ap:
        con.close(); flash('Запись не найдена'); return redirect(url_for('calendar_view'))
    if not can_manage_open_appointment(u, con, ap):
        con.close(); flash('Нет доступа или запись уже закрыта'); return redirect(url_for('calendar_view', date=request.form.get('date') or ap['appointment_date']))
    d = request.form.get('appointment_date', '').strip()
    start = request.form.get('start_time', '').strip()
    if not d or not start:
        con.close(); flash('Укажите дату и время'); return redirect(url_for('calendar_view', date=ap['appointment_date']))
    duration = int(ap['duration_min'] or 0)
    if not duration:
        service_ids = get_appointment_service_ids(con, aid, ap['service_id'])
        bundle = resolve_services_bundle(con, service_ids)
        duration = int(bundle['duration_min']) if bundle else 60
    end = m2hm(hm2m(start) + duration)
    note = f'Перенос: {ap["appointment_date"]} {ap["start_time"]} → {d} {start}'
    comment = f"{ap['comment']}\n{note}".strip() if ap['comment'] else note
    con.execute(
        "UPDATE appointments SET appointment_date=?, start_time=?, end_time=?, duration_min=?, comment=? WHERE id=?",
        (d, start, end, duration, comment, aid),
    )
    con.commit()
    employee_ids = get_appointment_employee_ids(con, aid, ap['employee_id'])
    con.close()
    notify_employee_appointment(employee_ids, d, start, ap['client_name'], ap['service_name'], ap['car'] or ap['plate_number'])
    flash('Запись перенесена'); return redirect(url_for('calendar_view', date=d))

@app.route('/certificates', methods=['GET','POST'])
@login_required
@perm_required('certificates')
def certificates():
    con = db()
    u = current_user()
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'create':
            nominal = float(request.form.get('nominal') or 0)
            if nominal <= 0:
                con.close()
                flash('Укажите сумму сертификата')
                return redirect(url_for('certificates'))
            number = make_certificate_number(con)
            try:
                con.execute(
                    "INSERT INTO certificates(cert_number,nominal,balance,client_name,phone,comment,created_at) VALUES(?,?,?,?,?,?,?)",
                    (number, nominal, nominal, request.form.get('client_name', ''), request.form.get('phone', ''), request.form.get('comment', ''), now()),
                )
                cid = con.execute("SELECT last_insert_rowid() id").fetchone()['id']
                con.execute(
                    "INSERT INTO certificate_moves(certificate_id,user_id,amount,move_type,comment,created_at) VALUES(?,?,?,?,?,?)",
                    (cid, u['id'], nominal, 'Создание', 'Сертификат создан', now()),
                )
                con.commit()
                con.close()
                flash(f'Сертификат №{number} создан — скачайте PDF')
                return redirect(url_for('certificate_pdf', cid=cid))
            except sqlite3.IntegrityError:
                con.close()
                flash('Не удалось создать сертификат — повторите')
        elif action == 'upload_template':
            if u['role'] != 'director':
                con.close()
                flash('Только директор может менять шаблон PDF')
                return redirect(url_for('certificates'))
            f = request.files.get('template_pdf')
            if not f or not f.filename:
                con.close()
                flash('Выберите PDF-файл')
                return redirect(url_for('certificates'))
            if not f.filename.lower().endswith('.pdf'):
                con.close()
                flash('Нужен файл PDF')
                return redirect(url_for('certificates'))
            CERT_TEMPLATE_PATH.parent.mkdir(parents=True, exist_ok=True)
            f.save(str(CERT_TEMPLATE_PATH))
            if CERT_LAYOUT_PATH.exists():
                CERT_LAYOUT_PATH.unlink()
            try:
                import fitz
                doc = fitz.open(str(CERT_TEMPLATE_PATH))
                save_certificate_layout(doc[0])
                doc.close()
            except Exception:
                pass
            con.close()
            flash('Шаблон сертификата загружен')
        elif action == 'delete':
            if u['role'] != 'director':
                con.close()
                flash('Только директор может удалять сертификаты')
                return redirect(url_for('certificates'))
            cid = int(request.form.get('cert_id') or 0)
            cert = con.execute("SELECT id,cert_number FROM certificates WHERE id=?", (cid,)).fetchone()
            if not cert:
                con.close()
                flash('Сертификат не найден')
                return redirect(url_for('certificates'))
            con.execute("DELETE FROM certificate_moves WHERE certificate_id=?", (cid,))
            con.execute("DELETE FROM certificates WHERE id=?", (cid,))
            con.commit()
            con.close()
            flash(f'Сертификат №{cert["cert_number"]} удалён')
        elif action == 'pay':
            return certificate_pay_internal(con)
        con.close()
        return redirect(url_for('certificates'))
    rows = con.execute("SELECT * FROM certificates ORDER BY id DESC").fetchall()
    moves = con.execute("SELECT cm.*,c.cert_number,u.full_name user_name FROM certificate_moves cm LEFT JOIN certificates c ON c.id=cm.certificate_id LEFT JOIN users u ON u.id=cm.user_id ORDER BY cm.id DESC LIMIT 100").fetchall()
    appointments = con.execute("SELECT id,appointment_date,start_time,client_name,plate_number,service_name FROM appointments WHERE status!='Закрыт' ORDER BY appointment_date DESC,start_time DESC LIMIT 50").fetchall()
    has_template = CERT_TEMPLATE_PATH.exists() and CERT_TEMPLATE_PATH.stat().st_size > 500
    con.close()
    return render_template('certificates.html', rows=rows, moves=moves, appointments=appointments, has_template=has_template, is_director=(u['role'] == 'director'))

@app.route('/certificates/<int:cid>/pdf')
@login_required
@perm_required('certificates')
def certificate_pdf(cid):
    con = db()
    cert = con.execute("SELECT * FROM certificates WHERE id=?", (cid,)).fetchone()
    con.close()
    if not cert:
        flash('Сертификат не найден')
        return redirect(url_for('certificates'))
    pdf = render_certificate_pdf(cert['cert_number'], cert['nominal'])
    if not pdf:
        flash('Не удалось сформировать PDF')
        return redirect(url_for('certificates'))
    return send_file(
        io.BytesIO(pdf),
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f'sertifikat_{cert["cert_number"]}.pdf',
    )

def certificate_pay_internal(con):
    number = request.form['cert_number'].strip().upper(); amount = float(request.form.get('amount') or 0); aid = request.form.get('appointment_id') or None
    cert = con.execute("SELECT * FROM certificates WHERE cert_number=? AND status='Активен'", (number,)).fetchone()
    if not cert:
        flash('Сертификат не найден или не активен'); con.close(); return redirect(url_for('certificates'))
    if cert['balance'] < amount:
        flash(f'Недостаточно средств. Остаток: {cert["balance"]:.0f} ₽'); con.close(); return redirect(url_for('certificates'))
    new_balance = cert['balance'] - amount; status = 'Использован' if new_balance <= 0 else 'Активен'
    con.execute("UPDATE certificates SET balance=?, status=? WHERE id=?", (new_balance,status,cert['id']))
    con.execute("INSERT INTO certificate_moves(certificate_id,appointment_id,user_id,amount,move_type,comment,created_at) VALUES(?,?,?,?,?,?,?)", (cert['id'],aid,current_user()['id'],-amount,'Списание',request.form.get('comment',''),now()))
    if aid:
        con.execute("UPDATE appointments SET certificate_paid=certificate_paid+? WHERE id=?", (amount,aid))
    con.commit(); flash(f'Списано {amount:.0f} ₽. Остаток: {new_balance:.0f} ₽')
    con.close(); return redirect(url_for('certificates'))

@app.route('/services', methods=['GET','POST'])
@login_required
@perm_required('services')
def services():
    con = db()
    if request.method == 'POST':
        action = request.form.get('action', 'create_service')
        if action == 'create_category':
            name = (request.form.get('name') or '').strip()
            if not name:
                flash('Укажите название подраздела')
            else:
                try:
                    sort_order = int(request.form.get('sort_order') or 0)
                    con.execute(
                        "INSERT INTO service_categories(name,sort_order,created_at) VALUES(?,?,?)",
                        (name, sort_order, now()),
                    )
                    con.commit()
                    flash(f'Подраздел «{name}» создан')
                except sqlite3.IntegrityError:
                    flash('Такой подраздел уже есть')
        elif action == 'delete_category':
            cid = int(request.form.get('category_id') or 0)
            used = con.execute("SELECT COUNT(*) c FROM services WHERE category_id=?", (cid,)).fetchone()['c']
            if used:
                flash('В подразделе есть услуги — сначала перенесите их в другой подраздел')
            else:
                con.execute("DELETE FROM service_categories WHERE id=?", (cid,))
                con.commit()
                flash('Подраздел удалён')
        else:
            category_id = parse_category_id(request.form.get('category_id'))
            online_calendar = 1 if request.form.get('online_calendar') else 0
            con.execute(
                "INSERT INTO services(name,duration_min,base_price,comment,category_id,online_calendar,created_at) VALUES(?,?,?,?,?,?,?)",
                (
                    request.form['name'],
                    int(request.form['duration_min']),
                    float(request.form.get('base_price') or 0),
                    request.form.get('comment', ''),
                    category_id,
                    online_calendar,
                    now(),
                ),
            )
            con.commit()
            flash('Услуга создана')
        tab = request.form.get('return_tab') or request.args.get('tab', '')
        con.close()
        return redirect(url_for('services', tab=tab) if tab else url_for('services'))
    rows = con.execute(
        "SELECT s.*, c.name category_name FROM services s "
        "LEFT JOIN service_categories c ON c.id=s.category_id "
        "ORDER BY COALESCE(c.sort_order, 999), c.name, s.active DESC, s.name"
    ).fetchall()
    categories = list_service_categories(con, active_only=False)
    service_groups = group_services_for_admin(rows, categories)
    active_tab = request.args.get('tab', '')
    if not active_tab and service_groups:
        cid = service_groups[0]['category']['id']
        active_tab = f"cat-{cid}" if cid is not None else 'cat-other'
    con.close()
    return render_template(
        'services.html',
        rows=rows,
        categories=categories,
        service_groups=service_groups,
        active_tab=active_tab,
    )

@app.route('/services/<int:sid>/update', methods=['POST'])
@login_required
@perm_required('services')
def service_update(sid):
    con = db()
    category_id = parse_category_id(request.form.get('category_id'))
    online_calendar = 1 if request.form.get('online_calendar') else 0
    con.execute(
        "UPDATE services SET name=?,duration_min=?,base_price=?,active=?,category_id=?,online_calendar=? WHERE id=?",
        (
            request.form['name'],
            int(request.form['duration_min']),
            float(request.form.get('base_price') or 0),
            1 if request.form.get('active') else 0,
            category_id,
            online_calendar,
            sid,
        ),
    )
    con.commit()
    con.close()
    flash('Услуга обновлена')
    tab = request.form.get('return_tab', '')
    return redirect(url_for('services', tab=tab) if tab else url_for('services'))

@app.route('/services/<int:sid>/delete', methods=['POST'])
@login_required
@perm_required('services')
def service_delete(sid):
    con = db(); used = con.execute("SELECT COUNT(*) c FROM appointments WHERE service_id=?", (sid,)).fetchone()['c']
    if used:
        con.execute("UPDATE services SET active=0 WHERE id=?", (sid,)); flash('Услуга скрыта, потому что уже есть в истории')
    else:
        con.execute("DELETE FROM user_services WHERE service_id=?", (sid,)); con.execute("DELETE FROM services WHERE id=?", (sid,)); flash('Услуга удалена')
    con.commit(); con.close(); return redirect(url_for('services'))

@app.route('/employees', methods=['GET','POST'])
@login_required
@perm_required('employees')
def employees():
    con = db()
    if request.method == 'POST':
        if request.form.get('form_type') == 'schedule':
            con.execute("INSERT INTO schedules(user_id,work_date,start_time,end_time,is_day_off,comment) VALUES(?,?,?,?,?,?) ON CONFLICT(user_id,work_date) DO UPDATE SET start_time=excluded.start_time,end_time=excluded.end_time,is_day_off=excluded.is_day_off,comment=excluded.comment", (request.form['user_id'],request.form['work_date'],request.form.get('start_time') or '09:00',request.form.get('end_time') or '20:00',1 if request.form.get('is_day_off') else 0,request.form.get('comment','')))
            con.commit(); flash('График сохранен'); return redirect(url_for('employees'))
        if request.form.get('form_type') == 'weekly':
            uid = int(request.form['user_id'])
            for wd in range(7):
                con.execute(
                    "INSERT INTO employee_weekly_schedule(user_id,weekday,start_time,end_time,is_day_off) VALUES(?,?,?,?,?) "
                    "ON CONFLICT(user_id,weekday) DO UPDATE SET start_time=excluded.start_time,end_time=excluded.end_time,is_day_off=excluded.is_day_off",
                    (uid, wd, request.form.get(f'start_{wd}') or '09:00', request.form.get(f'end_{wd}') or '20:00', 1 if request.form.get(f'off_{wd}') else 0)
                )
            con.commit(); flash('Недельный график сохранён'); return redirect(url_for('employees', user_id=uid))
        role = request.form.get('role','master')
        password = request.form.get('password', '').strip()
        if not password:
            flash('Укажите пароль для нового сотрудника')
            con.close()
            return redirect(url_for('employees'))
        try:
            con.execute("INSERT INTO users(username,password_hash,role,full_name,active,hired_at,created_at) VALUES(?,?,?,?,1,?,?)", (request.form['username'].strip(),generate_password_hash(password),role,request.form['full_name'],today(),now()))
            uid = con.execute("SELECT last_insert_rowid() id").fetchone()['id']
            for p in PERMS:
                con.execute("INSERT INTO user_permissions(user_id,permission,allowed) VALUES(?,?,?)", (uid,p,1 if role == 'director' or request.form.get('perm_'+p) else 0))
            for sid in request.form.getlist('service_ids'):
                con.execute("INSERT INTO user_services(user_id,service_id,allowed) VALUES(?,?,1)", (uid,sid))
            con.commit(); flash('Сотрудник создан')
        except sqlite3.IntegrityError:
            flash('Такой логин уже есть')
        return redirect(url_for('employees'))
    rows = con.execute("SELECT * FROM users ORDER BY active DESC, role, full_name").fetchall()
    services = con.execute("SELECT * FROM services WHERE active=1 ORDER BY name").fetchall()
    schedules = con.execute("SELECT s.*,u.full_name FROM schedules s JOIN users u ON u.id=s.user_id ORDER BY work_date DESC LIMIT 100").fetchall()
    perms = {}; user_services = {}
    for r in con.execute("SELECT * FROM user_permissions").fetchall():
        perms.setdefault(r['user_id'], {})[r['permission']] = r['allowed']
    for r in con.execute("SELECT * FROM user_services").fetchall():
        user_services.setdefault(r['user_id'], {})[r['service_id']] = r['allowed']
    weekly = {}
    for r in con.execute("SELECT * FROM employee_weekly_schedule").fetchall():
        weekly.setdefault(r['user_id'], {})[r['weekday']] = r
    selected_user = request.args.get('user_id', type=int) or (rows[0]['id'] if rows else None)
    con.close(); return render_template('employees.html', rows=rows, services=services, user_perms=perms, user_services=user_services, schedules=schedules, weekly=weekly, selected_user=selected_user)

@app.route('/employees/<int:uid>/update', methods=['POST'])
@login_required
@perm_required('employees')
def employee_update(uid):
    con = db(); u = current_user(); role = request.form.get('role'); active = 1 if request.form.get('active') else 0
    full_name = request.form.get('full_name', '').strip()
    if not full_name:
        con.close()
        flash('Укажите имя сотрудника')
        return redirect(url_for('employees'))
    new_password = request.form.get('password', '').strip()
    if new_password:
        if u['role'] != 'director' and u['id'] != uid:
            con.close()
            flash('Пароль другого пользователя может менять только директор')
            return redirect(url_for('employees'))
        con.execute("UPDATE users SET password_hash=? WHERE id=?", (generate_password_hash(new_password), uid))
    con.execute("UPDATE users SET full_name=?,role=?,active=?,fired_at=? WHERE id=?", (full_name, role, active, None if active else today(), uid))
    for p in PERMS:
        con.execute("INSERT INTO user_permissions(user_id,permission,allowed) VALUES(?,?,?) ON CONFLICT(user_id,permission) DO UPDATE SET allowed=excluded.allowed", (uid,p,1 if role == 'director' or request.form.get('perm_'+p) else 0))
    con.execute("DELETE FROM user_services WHERE user_id=?", (uid,))
    for sid in request.form.getlist('service_ids'):
        con.execute("INSERT INTO user_services(user_id,service_id,allowed) VALUES(?,?,1)", (uid,sid))
    con.commit(); con.close(); flash('Сотрудник обновлен'); return redirect(url_for('employees'))

@app.route('/stock', methods=['GET','POST'])
@login_required
@perm_required('stock')
def stock():
    con = db(); u = current_user(); is_director = u['role'] == 'director'
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add':
            category = request.form.get('category','film')
            if category == 'film':
                unit = 'm2'; w = float(request.form.get('width_m') or 1.52); l = float(request.form.get('length_m') or 0); bal = float(request.form.get('balance') or w*l)
                cost_mode = request.form.get('cost_mode', 'per_roll')
                cost_per_meter = float(request.form.get('cost_per_meter') or 0) if is_director else 0
                cost = float(request.form.get('cost_total') or 0) if is_director else 0
                cpm = film_cost_per_unit(w, l, bal, cost_mode, cost, cost_per_meter)
            else:
                unit = 'шт'; w = 0; l = 0; bal = float(request.form.get('balance') or 0)
                cost_mode = 'per_unit'; cost_per_meter = 0
                cost = float(request.form.get('cost_total') or 0) if is_director else 0
                cpm = cost / bal if cost and bal > 0 else 0
            visible = 1 if request.form.get('visible_to_staff') else 0
            con.execute("INSERT INTO stock_items(name,category,unit,width_m,length_m,balance,cost_total,cost_per_unit,cost_mode,cost_per_meter,visible_to_staff,comment,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (request.form['name'],category,unit,w,l,bal,cost,cpm,cost_mode,cost_per_meter,visible,request.form.get('comment',''),now()))
            item_id = con.execute("SELECT last_insert_rowid() id").fetchone()['id']
            con.execute("INSERT INTO stock_moves(item_id,user_id,change_qty,move_type,comment,created_at) VALUES(?,?,?,?,?,?)", (item_id,u['id'],bal,'Поступление','Добавлено на склад',now()))
            con.commit(); flash('Позиция добавлена')
        elif action == 'writeoff':
            item_id = request.form.get('item_id'); qty = float(request.form.get('qty') or 0); comment = request.form.get('comment','')
            item = con.execute("SELECT * FROM stock_items WHERE id=?", (item_id,)).fetchone()
            if item and qty > 0 and item['balance'] >= qty:
                con.execute("UPDATE stock_items SET balance=balance-? WHERE id=?", (qty,item_id))
                con.execute("INSERT INTO stock_moves(item_id,user_id,change_qty,move_type,comment,created_at) VALUES(?,?,?,?,?,?)", (item_id,u['id'],-qty,'Ручное списание',comment,now()))
                con.commit(); flash('Списано со склада')
            else:
                flash('Недостаточно остатка или ошибка')
        elif action == 'delete' and is_director:
            item_id = request.form.get('item_id')
            used = con.execute("SELECT COUNT(*) c FROM stock_moves WHERE item_id=? AND move_type='Списание по заказу'", (item_id,)).fetchone()['c']
            if used:
                con.execute("UPDATE stock_items SET active=0 WHERE id=?", (item_id,))
                con.commit(); flash('Позиция скрыта — есть история списаний')
            else:
                con.execute("DELETE FROM stock_moves WHERE item_id=?", (item_id,))
                con.execute("DELETE FROM stock_items WHERE id=?", (item_id,))
                con.commit(); flash('Позиция удалена')
        return redirect(url_for('stock'))
    film = con.execute("SELECT * FROM stock_items WHERE category='film' ORDER BY active DESC,name").fetchall()
    tools = con.execute("SELECT * FROM stock_items WHERE category!='film' ORDER BY active DESC,name").fetchall()
    moves = con.execute("SELECT sm.*,si.name item_name,si.unit,u.full_name user_name FROM stock_moves sm LEFT JOIN stock_items si ON si.id=sm.item_id LEFT JOIN users u ON u.id=sm.user_id ORDER BY sm.id DESC LIMIT 100").fetchall()
    con.close(); return render_template('stock.html', film=film, tools=tools, moves=moves, is_director=is_director)

@app.route('/salary')
@login_required
@perm_required('salary')
def salary():
    con = db(); u = current_user()
    employee_id = request.args.get('employee_id', type=int)
    if u['role'] == 'master':
        employee_id = u['id']
    if u['role'] == 'master':
        rows = con.execute(
            """SELECT s.*, a.client_name, a.plate_number, a.car, a.service_name, a.appointment_date,
                      a.start_time, a.end_time, a.comment visit_comment, a.closed_at, a.price, a.material_m2,
                      a.material_cost, a.extras_total, a.certificate_paid
               FROM salary s
               LEFT JOIN appointments a ON a.id=s.appointment_id
               WHERE s.employee_id=? ORDER BY s.id DESC""",
            (u['id'],)
        ).fetchall()
        details = {}
        for r in rows:
            if r['appointment_id']:
                details[r['id']] = {
                    'materials': con.execute(
                        "SELECT am.*, si.name, si.unit FROM appointment_materials am LEFT JOIN stock_items si ON si.id=am.item_id WHERE am.appointment_id=?",
                        (r['appointment_id'],)
                    ).fetchall(),
                    'extras': con.execute("SELECT * FROM appointment_extras WHERE appointment_id=? ORDER BY id", (r['appointment_id'],)).fetchall(),
                }
        total = con.execute("SELECT COALESCE(SUM(amount),0) s FROM salary WHERE employee_id=?", (u['id'],)).fetchone()['s']
        con.close()
        return render_template('master_salary.html', rows=rows, total=total, details=details, employees=[], employee_id=u['id'])
    sql = """SELECT s.*, u.full_name employee_name, a.client_name, a.plate_number, a.car, a.service_name,
                  a.appointment_date, a.start_time, a.end_time, a.comment visit_comment, a.closed_at,
                  a.price, a.material_m2, a.material_cost, a.extras_total, a.certificate_paid
           FROM salary s
           LEFT JOIN users u ON u.id=s.employee_id
           LEFT JOIN appointments a ON a.id=s.appointment_id
           WHERE 1=1"""
    params = []
    if employee_id:
        sql += " AND s.employee_id=?"
        params.append(employee_id)
    sql += " ORDER BY s.id DESC"
    rows = con.execute(sql, params).fetchall()
    details = {}
    for r in rows:
        if r['appointment_id']:
            details[r['id']] = {
                'materials': con.execute(
                    "SELECT am.*, si.name, si.unit FROM appointment_materials am LEFT JOIN stock_items si ON si.id=am.item_id WHERE am.appointment_id=?",
                    (r['appointment_id'],)
                ).fetchall(),
                'extras': con.execute("SELECT * FROM appointment_extras WHERE appointment_id=? ORDER BY id", (r['appointment_id'],)).fetchall(),
            }
    totals = con.execute("SELECT u.id,u.full_name,COALESCE(SUM(s.amount),0) total FROM users u LEFT JOIN salary s ON s.employee_id=u.id GROUP BY u.id").fetchall()
    employees = con.execute("SELECT id,full_name FROM users WHERE active=1 ORDER BY full_name").fetchall()
    con.close()
    return render_template('salary.html', rows=rows, totals=totals, details=details, employees=employees, employee_id=employee_id)

@app.route('/analytics')
@login_required
@perm_required('analytics')
def analytics():
    con = db()
    month_start = date.today().replace(day=1).isoformat()
    start = request.args.get('start') or month_start
    end = request.args.get('end') or today()
    stats = {
        'revenue': con.execute("SELECT COALESCE(SUM(price),0) s FROM appointments WHERE status='Закрыт' AND appointment_date BETWEEN ? AND ?", (start,end)).fetchone()['s'],
        'profit': con.execute("SELECT COALESCE(SUM(profit),0) s FROM appointments WHERE status='Закрыт' AND appointment_date BETWEEN ? AND ?", (start,end)).fetchone()['s'],
        'mat': con.execute("SELECT COALESCE(SUM(material_cost),0) s FROM appointments WHERE status='Закрыт' AND appointment_date BETWEEN ? AND ?", (start,end)).fetchone()['s'],
        'salary': con.execute("SELECT COALESCE(SUM(salary_amount),0) s FROM appointments WHERE status='Закрыт' AND appointment_date BETWEEN ? AND ?", (start,end)).fetchone()['s'],
        'm2': con.execute("SELECT COALESCE(SUM(material_m2),0) s FROM appointments WHERE status='Закрыт' AND appointment_date BETWEEN ? AND ?", (start,end)).fetchone()['s'],
        'certificate_paid': con.execute("SELECT COALESCE(SUM(certificate_paid),0) s FROM appointments WHERE status='Закрыт' AND appointment_date BETWEEN ? AND ?", (start,end)).fetchone()['s'],
        'stock_items': con.execute("SELECT COUNT(*) c FROM stock_items WHERE active=1").fetchone()['c'],
        'appointments': con.execute("SELECT COUNT(*) c FROM appointments WHERE appointment_date BETWEEN ? AND ? AND status='Закрыт'", (start,end)).fetchone()['c'],
    }
    by_day = con.execute("SELECT appointment_date, COUNT(*) cnt, COALESCE(SUM(price),0) revenue, COALESCE(SUM(profit),0) profit, COALESCE(SUM(material_m2),0) m2, COALESCE(SUM(salary_amount),0) salary FROM appointments WHERE status='Закрыт' AND appointment_date BETWEEN ? AND ? GROUP BY appointment_date ORDER BY appointment_date DESC", (start,end)).fetchall()
    by_employee = con.execute("SELECT u.full_name,COUNT(a.id) cnt,COALESCE(SUM(a.price),0) revenue,COALESCE(SUM(a.salary_amount),0) salary,COALESCE(SUM(a.material_m2),0) m2,COALESCE(SUM(a.profit),0) profit FROM users u LEFT JOIN appointments a ON a.employee_id=u.id AND a.status='Закрыт' AND a.appointment_date BETWEEN ? AND ? GROUP BY u.id", (start,end)).fetchall()
    archived_days = {r['report_date']: r for r in con.execute("SELECT * FROM daily_reports WHERE report_date BETWEEN ? AND ? ORDER BY report_date DESC", (start, end)).fetchall()}
    day_detail = None
    day_archived = None
    if start == end:
        day_detail = compute_day_stats(con, start)
        day_archived = archived_days.get(start)
    con.close()
    return render_template('analytics.html', stats=stats, by_day=by_day, by_employee=by_employee, start=start, end=end, day_detail=day_detail, day_archived=day_archived, archived_days=archived_days)

@app.route('/crm', methods=['GET','POST'])
@login_required
@perm_required('crm')
def crm():
    con = db()
    if request.method == 'POST':
        con.execute("INSERT INTO clients(name,phone,source,stage,reason,comment,created_at) VALUES(?,?,?,?,?,?,?)", (request.form.get('name'), request.form.get('phone'), request.form.get('source','Ручное добавление'), request.form.get('stage','Новый'), request.form.get('reason',''), request.form.get('comment',''), now()))
        cid = con.execute("SELECT last_insert_rowid() id").fetchone()['id']
        ensure_client_bonus_code(con, cid)
        car = request.form.get('car','')
        plate = request.form.get('plate_number','').upper().replace(' ','')
        if car or plate:
            con.execute("INSERT INTO cars(client_id,car_model,plate_number,created_at) VALUES(?,?,?,?)", (cid, car, plate, now()))
        con.commit()
        flash('Клиент добавлен в CRM')
        return redirect(url_for('crm'))
    q = request.args.get('q','').strip()
    if q:
        rows = con.execute("SELECT DISTINCT c.* FROM clients c LEFT JOIN cars car ON car.client_id=c.id WHERE c.phone LIKE ? OR c.name LIKE ? OR car.plate_number LIKE ? OR car.car_model LIKE ? ORDER BY c.id DESC", [f'%{q}%']*4).fetchall()
    else:
        rows = con.execute("SELECT * FROM clients ORDER BY id DESC").fetchall()
    con.close(); return render_template('crm.html', rows=rows, q=q)


@app.route('/crm/<int:cid>/bonus', methods=['POST'])
@login_required
@perm_required('crm')
def client_bonus_action(cid):
    con = db()
    u = current_user()
    action = request.form.get('action', '')
    if action == 'adjust':
        delta = float(request.form.get('bonus_delta') or 0)
        comment = request.form.get('bonus_comment', '').strip()
        ok, err = adjust_client_bonus(con, cid, delta, u['id'], comment)
        con.commit() if ok else None
        con.close()
        flash(f'Бонусы обновлены' if ok else err)
    elif action == 'toggle':
        row = con.execute("SELECT bonus_enabled FROM clients WHERE id=?", (cid,)).fetchone()
        if row:
            con.execute("UPDATE clients SET bonus_enabled=? WHERE id=?", (0 if int(row['bonus_enabled'] or 0) else 1, cid))
            con.commit()
        con.close()
        flash('Настройка бонусов сохранена')
    elif action == 'percent':
        raw = request.form.get('bonus_percent', '').strip()
        val = float(raw) if raw else None
        con.execute("UPDATE clients SET bonus_percent=? WHERE id=?", (val, cid))
        con.commit()
        con.close()
        flash('Персональный процент сохранён')
    elif action == 'regenerate':
        code = make_bonus_code(con, cid)
        con.execute("UPDATE clients SET bonus_code=? WHERE id=?", (code, cid))
        con.commit()
        con.close()
        flash(f'Новый код: {code}')
    else:
        con.close()
    return redirect(url_for('client_card', cid=cid))

@app.route('/crm/<int:cid>/bonus-qr.png')
@login_required
@perm_required('crm')
def client_bonus_qr(cid):
    con = db()
    client = con.execute("SELECT bonus_code FROM clients WHERE id=?", (cid,)).fetchone()
    con.close()
    if not client or not client['bonus_code']:
        return 'No code', 404
    png = bonus_qr_png(bonus_card_url(client['bonus_code']))
    if not png:
        return 'QR unavailable', 503
    return app.response_class(png, mimetype='image/png')

@app.route('/crm/<int:cid>/update', methods=['POST'])
@login_required
@perm_required('crm')
def client_update(cid):
    con = db()
    con.execute("UPDATE clients SET name=?, phone=?, source=?, stage=?, reason=?, comment=? WHERE id=?",
                (request.form.get('name'), request.form.get('phone'), request.form.get('source'), request.form.get('stage'), request.form.get('reason'), request.form.get('comment'), cid))
    car = request.form.get('car','')
    plate = request.form.get('plate_number','').upper().replace(' ','')
    if car or plate:
        exists = con.execute("SELECT id FROM cars WHERE client_id=? AND (plate_number=? OR car_model=?)", (cid, plate, car)).fetchone()
        if not exists:
            con.execute("INSERT INTO cars(client_id,car_model,plate_number,created_at) VALUES(?,?,?,?)", (cid, car, plate, now()))
    con.commit()
    con.close()
    flash('Карточка клиента обновлена')
    return redirect(url_for('client_card', cid=cid))

@app.route('/crm/<int:cid>')
@login_required
@perm_required('crm')
def client_card(cid):
    con = db()
    client = con.execute("SELECT * FROM clients WHERE id=?", (cid,)).fetchone()
    if not client:
        con.close()
        flash('Клиент не найден')
        return redirect(url_for('crm'))
    ensure_client_bonus_code(con, cid)
    client = con.execute("SELECT * FROM clients WHERE id=?", (cid,)).fetchone()
    cars = con.execute("SELECT * FROM cars WHERE client_id=? ORDER BY id DESC", (cid,)).fetchall()
    visits = con.execute("SELECT a.*,u.full_name employee_name FROM appointments a LEFT JOIN users u ON u.id=a.employee_id WHERE client_id=? ORDER BY appointment_date DESC,start_time DESC", (cid,)).fetchall()
    bonus_tx = con.execute(
        "SELECT bt.*, u.full_name user_name FROM bonus_transactions bt LEFT JOIN users u ON u.id=bt.user_id WHERE bt.client_id=? ORDER BY bt.id DESC LIMIT 50",
        (cid,),
    ).fetchall()
    closed_visits = con.execute("SELECT COUNT(*) c FROM appointments WHERE client_id=? AND status='Закрыт'", (cid,)).fetchone()['c']
    friend_card = con.execute("SELECT * FROM friend_cards WHERE client_id=? AND active=1", (cid,)).fetchone()
    con.close()
    card_url = bonus_card_url(client['bonus_code']) if client['bonus_code'] else ''
    friend_card_url_val = friend_card_url(friend_card['access_token']) if friend_card else ''
    return render_template(
        'client_card.html',
        client=client,
        cars=cars,
        visits=visits,
        bonus_tx=bonus_tx,
        card_url=card_url,
        global_bonus_percent=global_bonus_percent(),
        bonus_from_visit=bonus_from_visit_number(),
        closed_visits=closed_visits,
        friend_card=friend_card,
        friend_card_url=friend_card_url_val,
    )

@app.route('/bonus/<code>')
def bonus_card_public(code):
    con = db()
    client = con.execute("SELECT * FROM clients WHERE bonus_code=?", (code.upper(),)).fetchone()
    if not client:
        con.close()
        return render_template('bonus_card.html', found=False), 404
    closed_visits = con.execute("SELECT COUNT(*) c FROM appointments WHERE client_id=? AND status='Закрыт'", (client['id'],)).fetchone()['c']
    percent = client_bonus_percent(client)
    con.close()
    return render_template(
        'bonus_card.html',
        found=True,
        client=client,
        card_url=bonus_card_url(client['bonus_code']),
        percent=percent,
        closed_visits=closed_visits,
        bonus_from_visit=bonus_from_visit_number(),
    )


@app.route('/friend/<token>')
def friend_card_public(token):
    con = db()
    card = con.execute("SELECT * FROM friend_cards WHERE access_token=? AND active=1", (token,)).fetchone()
    if not card:
        con.close()
        return render_template('friend_card.html', found=False), 404
    discount_code = issue_friend_discount_code(con, card['id'])
    con.commit()
    con.close()
    return render_template(
        'friend_card.html',
        found=True,
        card=card,
        discount_code=discount_code,
        card_url=friend_card_url(card['access_token']),
        discount_percent=float(card['discount_percent'] or global_friend_discount_percent()),
    )

@app.route('/settings/friend/<int:fid>/qr.png')
@login_required
def friend_card_qr(fid):
    u = current_user()
    if u['role'] != 'director':
        return 'Forbidden', 403
    con = db()
    card = con.execute("SELECT access_token FROM friend_cards WHERE id=?", (fid,)).fetchone()
    con.close()
    if not card:
        return 'No card', 404
    png = bonus_qr_png(friend_card_url(card['access_token']))
    if not png:
        return 'QR unavailable', 503
    return app.response_class(png, mimetype='image/png')


@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    u = current_user()
    if request.method == 'POST':
        form_type = request.form.get('form_type', 'password')
        if form_type == 'notifications' and u['role'] == 'director':
            con = db()
            con.execute(
                "INSERT INTO director_notification_prefs(user_id,notify_new,notify_closed,notify_daily) VALUES(?,?,?,?) "
                "ON CONFLICT(user_id) DO UPDATE SET notify_new=excluded.notify_new,notify_closed=excluded.notify_closed,notify_daily=excluded.notify_daily",
                (
                    u['id'],
                    1 if request.form.get('notify_new') else 0,
                    1 if request.form.get('notify_closed') else 0,
                    1 if request.form.get('notify_daily') else 0,
                ),
            )
            selected = {int(x) for x in request.form.getlist('notify_employee_ids')}
            for m in con.execute("SELECT id FROM users WHERE role='master' AND active=1").fetchall():
                con.execute(
                    "INSERT INTO director_employee_notify(director_id,employee_id,enabled) VALUES(?,?,?) "
                    "ON CONFLICT(director_id,employee_id) DO UPDATE SET enabled=excluded.enabled",
                    (u['id'], m['id'], 1 if m['id'] in selected else 0),
                )
            con.commit()
            con.close()
            flash('Настройки уведомлений сохранены')
            return redirect(url_for('profile'))
        if form_type == 'weekly':
            con = db()
            for wd in range(7):
                con.execute(
                    "INSERT INTO employee_weekly_schedule(user_id,weekday,start_time,end_time,is_day_off) VALUES(?,?,?,?,?) "
                    "ON CONFLICT(user_id,weekday) DO UPDATE SET start_time=excluded.start_time,end_time=excluded.end_time,is_day_off=excluded.is_day_off",
                    (u['id'], wd, request.form.get(f'start_{wd}') or '09:00', request.form.get(f'end_{wd}') or '20:00', 1 if request.form.get(f'off_{wd}') else 0)
                )
            con.commit()
            con.close()
            flash('Ваш график работы сохранён')
            return redirect(url_for('profile'))
        current_pw = request.form.get('current_password', '')
        new_pw = request.form.get('new_password', '').strip()
        confirm_pw = request.form.get('confirm_password', '').strip()
        con = db()
        row = con.execute("SELECT password_hash FROM users WHERE id=?", (u['id'],)).fetchone()
        if not check_password_hash(row['password_hash'], current_pw):
            con.close()
            flash('Неверный текущий пароль')
            return redirect(url_for('profile'))
        if len(new_pw) < 4:
            con.close()
            flash('Новый пароль слишком короткий')
            return redirect(url_for('profile'))
        if new_pw != confirm_pw:
            con.close()
            flash('Пароли не совпадают')
            return redirect(url_for('profile'))
        con.execute("UPDATE users SET password_hash=? WHERE id=?", (generate_password_hash(new_pw), u['id']))
        con.commit()
        con.close()
        flash('Пароль изменён')
        return redirect(url_for('profile'))
    con = db()
    weekly_rows = {r['weekday']: r for r in con.execute("SELECT * FROM employee_weekly_schedule WHERE user_id=?", (u['id'],)).fetchall()}
    notify_prefs = get_director_notification_prefs(con, u['id']) if u['role'] == 'director' else None
    notify_employees = {}
    masters = []
    if u['role'] == 'director':
        masters = con.execute("SELECT id, full_name FROM users WHERE role='master' AND active=1 ORDER BY full_name").fetchall()
        for r in con.execute("SELECT employee_id, enabled FROM director_employee_notify WHERE director_id=?", (u['id'],)).fetchall():
            notify_employees[r['employee_id']] = r['enabled']
    con.close()
    return render_template('profile.html', weekly=weekly_rows, notify_prefs=notify_prefs, masters=masters, notify_employees=notify_employees)


@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    u = current_user()
    if u['role'] != 'director':
        flash('Только директор может менять настройки')
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        action = request.form.get('action', 'stats')
        if action == 'stats':
            set_setting('stats_refresh', request.form.get('stats_refresh', 'daily'))
            con = db()
            stats = compute_dashboard_stats(con)
            con.close()
            set_setting('stats_cached', json.dumps({'at': now(), 'stats': stats}, ensure_ascii=False))
            flash('Настройки статистики сохранены')
        elif action == 'refresh_stats':
            con = db()
            stats = compute_dashboard_stats(con)
            con.close()
            set_setting('stats_cached', json.dumps({'at': now(), 'stats': stats}, ensure_ascii=False))
            flash('Статистика на главной обновлена')
        elif action == 'backup':
            backup_database()
            flash('Резервная копия базы создана')
        elif action == 'restore':
            restored = remote_restore_database() or restore_database_if_needed()
            if restored:
                flash('База восстановлена из резервной копии')
            else:
                flash('Не найдена резервная копия с данными')
        elif action == 'bonus_save':
            set_setting('bonus_enabled', '1' if request.form.get('bonus_enabled') else '0')
            set_setting('bonus_percent', request.form.get('bonus_percent', '3').strip() or '3')
            set_setting('bonus_from_visit', request.form.get('bonus_from_visit', '2').strip() or '2')
            flash('Настройки бонусной программы сохранены')
        elif action == 'friend_save':
            set_setting('friend_discount_percent', request.form.get('friend_discount_percent', '10').strip() or '10')
            flash('Настройки карт для друзей сохранены')
        elif action == 'friend_add':
            con = db()
            name = request.form.get('friend_name', '').strip()
            if not name:
                con.close()
                flash('Укажите имя для карты')
                return redirect(url_for('settings'))
            client_id = request.form.get('friend_client_id', '').strip()
            client_id = int(client_id) if client_id else None
            percent = float(request.form.get('friend_card_percent') or global_friend_discount_percent())
            card_number = make_friend_card_number(con)
            token = make_friend_access_token(con)
            con.execute(
                "INSERT INTO friend_cards(name,client_id,card_number,access_token,discount_percent,active,comment,created_at) VALUES(?,?,?,?,?,1,?,?)",
                (name, client_id, card_number, token, percent, request.form.get('friend_comment', '').strip(), now()),
            )
            if client_id:
                con.execute("UPDATE clients SET bonus_enabled=0 WHERE id=?", (client_id,))
            con.commit()
            con.close()
            flash(f'Карта для друзей выдана: №{card_number} · {name}')
        elif action == 'friend_toggle':
            con = db()
            fid = int(request.form.get('friend_id') or 0)
            row = con.execute("SELECT active, client_id FROM friend_cards WHERE id=?", (fid,)).fetchone()
            if row:
                new_active = 0 if int(row['active'] or 0) else 1
                con.execute("UPDATE friend_cards SET active=? WHERE id=?", (new_active, fid))
                if row['client_id']:
                    con.execute("UPDATE clients SET bonus_enabled=? WHERE id=?", (1 if not new_active else 0, row['client_id']))
                con.commit()
            con.close()
            flash('Карта обновлена')
        elif action == 'friend_delete':
            con = db()
            fid = int(request.form.get('friend_id') or 0)
            row = con.execute("SELECT client_id FROM friend_cards WHERE id=?", (fid,)).fetchone()
            if row:
                if row['client_id']:
                    con.execute("UPDATE clients SET bonus_enabled=1 WHERE id=?", (row['client_id'],))
                con.execute("DELETE FROM friend_discount_codes WHERE friend_card_id=?", (fid,))
                con.execute("DELETE FROM friend_cards WHERE id=?", (fid,))
                con.commit()
            con.close()
            flash('Карта удалена')
        elif action == 'openai_save':
            key = request.form.get('openai_api_key', '').strip()
            if key:
                set_setting('openai_api_key', key)
                flash('Ключ OpenAI сохранён — голосовые записи в Telegram включены')
            else:
                flash('Введите ключ OpenAI (начинается с sk-)')
            set_setting('telegram_enabled', '1' if request.form.get('telegram_enabled') else '0')
            set_setting('telegram_chat_id', request.form.get('telegram_chat_id', '').strip())
            wake = request.form.get('telegram_wake_name', '').strip()
            if wake:
                set_setting('telegram_wake_name', wake.lower())
            flash('Настройки Telegram сохранены')
        elif action == 'telegram_test':
            ok, err = send_telegram_message('<b>Тест</b>\nУведомления BlackSquare CRM работают.', force=True)
            flash('Тестовое сообщение отправлено в чат' if ok else f'Telegram: {err}')
        elif action == 'telegram_discover':
            telegram_autoconfigure()
            chats = telegram_discover_chats()
            if chats:
                flash('Найденные чаты: ' + ', '.join(f'{c["title"]} ({c["id"]})' for c in chats))
            else:
                flash('Чаты не найдены. Напишите что-нибудь боту в рабочем чате и повторите поиск.')
        return redirect(url_for('settings'))
    telegram_autoconfigure()
    stats_refresh = get_setting('stats_refresh', 'live')
    stats_updated = json.loads(get_setting('stats_cached', '{}')).get('at', '')
    con = db()
    db_info = {
        'appointments': con.execute("SELECT COUNT(*) c FROM appointments").fetchone()['c'],
        'clients': con.execute("SELECT COUNT(*) c FROM clients").fetchone()['c'],
    }
    friend_discount_percent = get_setting('friend_discount_percent', '10')
    friend_cards_raw = con.execute(
        "SELECT fc.*, c.name client_name FROM friend_cards fc LEFT JOIN clients c ON c.id=fc.client_id ORDER BY fc.id DESC"
    ).fetchall()
    clients = con.execute("SELECT id, name, phone FROM clients ORDER BY name").fetchall()
    con.close()
    backup_dir = Path(DB).parent / 'backups'
    backups = sorted(backup_dir.glob('blacksquare_*.db'), key=lambda p: p.stat().st_mtime, reverse=True)[:5] if backup_dir.exists() else []
    telegram_on = get_setting('telegram_enabled', '0') == '1'
    telegram_chat = get_setting('telegram_chat_id', '')
    telegram_token_ok = bool(telegram_bot_token())
    telegram_wake = get_setting('telegram_wake_name', 'пантюха')
    openai_ok = bool(openai_api_key())
    openai_key = openai_api_key()
    openai_masked = ('sk-…' + openai_key[-4:]) if len(openai_key) > 8 else ''
    bonus_on = get_setting('bonus_enabled', '1') == '1'
    bonus_percent = get_setting('bonus_percent', '3')
    bonus_from_visit = get_setting('bonus_from_visit', '2')
    friend_cards = []
    for r in friend_cards_raw:
        fc = dict(r)
        fc['card_url'] = friend_card_url(r['access_token'])
        friend_cards.append(fc)
    return render_template(
        'settings.html',
        stats_refresh=stats_refresh,
        stats_updated=stats_updated,
        db_path=DB,
        db_info=db_info,
        backups=backups,
        telegram_on=telegram_on,
        telegram_chat=telegram_chat,
        telegram_token_ok=telegram_token_ok,
        telegram_wake=telegram_wake,
        openai_ok=openai_ok,
        openai_masked=openai_masked,
        bonus_on=bonus_on,
        bonus_percent=bonus_percent,
        bonus_from_visit=bonus_from_visit,
        friend_discount_percent=friend_discount_percent,
        friend_cards=friend_cards,
        clients=clients,
    )


@app.route('/finance', methods=['GET', 'POST'])
@login_required
@perm_required('finance')
def finance():
    con = db()
    u = current_user()
    if request.method == 'POST':
        action = request.form.get('action', 'add')
        if action == 'add':
            con.execute(
                "INSERT INTO finance_payments(category,title,amount,due_date,paid_amount,status,comment,created_at) VALUES(?,?,?,?,0,'Ожидает',?,?)",
                (
                    request.form.get('category', 'rent'),
                    request.form.get('title', '').strip() or ('Аренда' if request.form.get('category') == 'rent' else 'Коммунальные'),
                    float(request.form.get('amount') or 0),
                    request.form.get('due_date'),
                    request.form.get('comment', ''),
                    now(),
                ),
            )
            con.commit()
            flash('Платёж добавлен')
        elif action == 'pay':
            pid = request.form.get('payment_id')
            paid = float(request.form.get('paid_amount') or 0)
            con.execute(
                "UPDATE finance_payments SET paid_amount=?, paid_date=?, status='Оплачен' WHERE id=?",
                (paid, today(), pid),
            )
            con.commit()
            flash('Отмечено как оплачено')
        elif action == 'delete':
            con.execute("DELETE FROM finance_payments WHERE id=?", (request.form.get('payment_id'),))
            con.commit()
            flash('Платёж удалён')
        con.close()
        return redirect(url_for('finance', month=request.form.get('month') or request.args.get('month')))

    month_s = request.args.get('month') or date.today().strftime('%Y-%m')
    month = datetime.strptime(month_s + '-01', '%Y-%m-%d').date()
    first, days = pycal.monthrange(month.year, month.month)
    cells = [None] * first
    payments = con.execute("SELECT * FROM finance_payments ORDER BY due_date DESC").fetchall()
    by_date = {}
    for p in payments:
        by_date.setdefault(p['due_date'], []).append(p)
    for day in range(1, days + 1):
        ds = date(month.year, month.month, day).isoformat()
        day_payments = by_date.get(ds, [])
        cells.append({'day': day, 'date': ds, 'payments': day_payments, 'total': sum(float(x['amount'] or 0) for x in day_payments)})
    while len(cells) % 7:
        cells.append(None)

    today_s = today()
    con.execute("UPDATE finance_payments SET status='Просрочен' WHERE status='Ожидает' AND due_date<?", (today_s,))
    con.commit()
    rent_rows = [p for p in payments if p['category'] == 'rent']
    util_rows = [p for p in payments if p['category'] == 'utilities']
    pending = con.execute("SELECT COALESCE(SUM(amount - paid_amount),0) s FROM finance_payments WHERE status!='Оплачен'").fetchone()['s']
    overdue = con.execute("SELECT COALESCE(SUM(amount - paid_amount),0) s FROM finance_payments WHERE status='Просрочен'").fetchone()['s']
    con.close()
    prev_month = (month.replace(day=1) - timedelta(days=1)).strftime('%Y-%m')
    next_month = (month.replace(day=28) + timedelta(days=4)).replace(day=1).strftime('%Y-%m')
    return render_template(
        'finance.html',
        cells=cells,
        month=month_s,
        rent_rows=rent_rows,
        util_rows=util_rows,
        pending=pending,
        overdue=overdue,
        prev_month=prev_month,
        next_month=next_month,
        selected=request.args.get('date') or today_s,
    )


@app.route('/manifest.webmanifest')
def manifest():
    return app.send_static_file('manifest.webmanifest')


@app.route('/sw.js')
def service_worker():
    resp = app.send_static_file('sw.js')
    resp.headers['Content-Type'] = 'application/javascript'
    resp.headers['Service-Worker-Allowed'] = '/'
    resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return resp


@app.route('/api/push-status', methods=['GET'])
@login_required
def push_status():
    if not VAPID_PRIVATE_KEY:
        return jsonify({'ok': False, 'subscribed': False, 'error': 'Push не настроен на сервере'})
    u = current_user()
    con = db()
    count = con.execute("SELECT COUNT(*) c FROM push_subscriptions WHERE user_id=?", (u['id'],)).fetchone()['c']
    con.close()
    return jsonify({
        'ok': True,
        'subscribed': count > 0,
        'count': count,
        'vapid_public_key': VAPID_PUBLIC_KEY,
        'push_key_version': 3,
    })


@app.route('/api/push-subscribe', methods=['POST'])
@login_required
def push_subscribe():
    data = request.get_json(silent=True) or {}
    sub = data.get('subscription')
    if not sub:
        return jsonify({'ok': False, 'error': 'Нет данных подписки'}), 400
    if not VAPID_PRIVATE_KEY:
        return jsonify({'ok': False, 'error': 'Push не настроен на сервере'}), 503
    u = current_user()
    save_push_subscription(u['id'], sub)
    if data.get('sync'):
        return jsonify({'ok': True, 'subscribed': True, 'vapid_public_key': VAPID_PUBLIC_KEY})
    test_sent, test_err = send_push_to_user(u['id'], 'BlackSquare', 'Уведомления подключены! Вы будете получать оповещения о записях.', url_for('profile'))
    if not test_sent:
        con = db()
        con.execute("DELETE FROM push_subscriptions WHERE endpoint=? AND user_id=?", (sub['endpoint'], u['id']))
        con.commit()
        con.close()
        return jsonify({'ok': False, 'error': test_err or 'Не удалось отправить тестовое уведомление'})
    return jsonify({'ok': True, 'test_sent': True, 'vapid_public_key': VAPID_PUBLIC_KEY})


@app.route('/api/push-test', methods=['POST'])
@login_required
def push_test():
    if not VAPID_PRIVATE_KEY:
        return jsonify({'ok': False, 'error': 'Push не настроен на сервере'})
    u = current_user()
    data = request.get_json(silent=True) or {}
    sub = data.get('subscription')
    if sub:
        save_push_subscription(u['id'], sub)
    ok, err = send_push_to_user(u['id'], 'BlackSquare — тест', 'Если вы видите это — уведомления работают.', url_for('dashboard'))
    if ok:
        return jsonify({'ok': True})
    if sub:
        con = db()
        con.execute("DELETE FROM push_subscriptions WHERE endpoint=? AND user_id=?", (sub['endpoint'], u['id']))
        con.commit()
        con.close()
    return jsonify({'ok': False, 'error': err or 'Не удалось отправить. Нажмите «Отключить», затем снова «Включить».'})


@app.route('/api/push-unsubscribe', methods=['POST'])
@login_required
def push_unsubscribe():
    data = request.get_json(silent=True) or {}
    endpoint = data.get('endpoint')
    if endpoint:
        con = db()
        con.execute("DELETE FROM push_subscriptions WHERE endpoint=? AND user_id=?", (endpoint, current_user()['id']))
        con.commit()
        con.close()
    return jsonify({'ok': True})


@app.route('/api/cron/daily-report')
def cron_daily_report():
    token = request.args.get('token') or request.headers.get('X-Cron-Token', '')
    if token != os.environ.get('CRON_SECRET', 'blacksquare-cron'):
        return jsonify({'ok': False, 'error': 'forbidden'}), 403
    report_date = request.args.get('date') or daily_report_target_date() or today()
    con = db()
    created = save_and_notify_daily_report(con, report_date)
    if created:
        set_setting('last_daily_report_date', report_date)
    con.close()
    return jsonify({'ok': True, 'date': report_date, 'created': created})


if __name__ == '__main__':
    port = 8000
    app.run(host='0.0.0.0', port=port, debug=False)
