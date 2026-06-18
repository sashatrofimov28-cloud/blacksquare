from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date
from pathlib import Path
import sqlite3, calendar as pycal
import os

app = Flask(__name__)
BASE_DIR = Path(__file__).resolve().parent
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'blacksquare_stock_crm_v2')
DB = os.environ.get('DATABASE_PATH', str(BASE_DIR / 'blacksquare_stock_crm_v2.db'))
DEFAULT_PASSWORD = 'blacksquare'

PERMS = {
    'calendar': 'Календарь',
    'services': 'Услуги',
    'crm': 'CRM',
    'stock': 'Склад',
    'salary': 'Зарплата',
    'analytics': 'Статистика',
    'employees': 'Сотрудники и права',
    'delete_appointments': 'Удаление записей',
    'certificates': 'Сертификаты',
    'extra_services': 'Допуслуги в заказе',
    'phone_access': 'Доступ к телефонам',
}

def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con

def now(): return datetime.now().strftime('%Y-%m-%d %H:%M')
def today(): return date.today().isoformat()
def hm2m(hm):
    h, m = map(int, hm.split(':'))
    return h * 60 + m
def m2hm(minutes): return f'{minutes // 60:02d}:{minutes % 60:02d}'

def init_db():
    con = db(); c = con.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE, password_hash TEXT, role TEXT, full_name TEXT, active INTEGER DEFAULT 1, hired_at TEXT, fired_at TEXT, created_at TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS user_permissions(user_id INTEGER, permission TEXT, allowed INTEGER DEFAULT 0, UNIQUE(user_id, permission))")
    c.execute("CREATE TABLE IF NOT EXISTS services(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, duration_min INTEGER, base_price REAL DEFAULT 0, active INTEGER DEFAULT 1, comment TEXT, created_at TEXT)")
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
    con.commit()

    default_users = [('director','director','Директор'),('admin','admin','Администратор'),('katya','master','Катя'),('stas','master','Стас')]
    for username, role, full_name in default_users:
        c.execute("INSERT OR IGNORE INTO users(username,password_hash,role,full_name,hired_at,created_at) VALUES(?,?,?,?,?,?)", (username, generate_password_hash(DEFAULT_PASSWORD), role, full_name, today(), now()))
        uid = c.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()['id']
        for p in PERMS:
            if role == 'director': allowed = 1
            elif role == 'admin': allowed = 1 if p in ['calendar','services','crm','employees','delete_appointments','extra_services','certificates','phone_access'] else 0
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
    con.commit(); con.close()

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
    if row: return row['id']
    con.execute("INSERT INTO clients(name,phone,source,stage,created_at) VALUES(?,?,?,?,?)", (name,phone,'Запись','Новый',now()))
    return con.execute("SELECT last_insert_rowid() id").fetchone()['id']

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
    if row: return row
    return {'start_time':'09:00','end_time':'20:00','is_day_off':0}

def slot_free(con, uid, d, start, end):
    s = hm2m(start); e = hm2m(end)
    rows = con.execute("SELECT start_time,end_time FROM appointments WHERE employee_id=? AND appointment_date=? AND status!='Отменен'", (uid,d)).fetchall()
    for r in rows:
        if s < hm2m(r['end_time']) and e > hm2m(r['start_time']):
            return False
    return True

def available_slots(con, uid, sid, d):
    service = con.execute("SELECT * FROM services WHERE id=? AND active=1", (sid,)).fetchone()
    emp = con.execute("SELECT * FROM users WHERE id=? AND active=1 AND role!='director'", (uid,)).fetchone()
    if not service or not emp or not employee_can_service(con, uid, sid): return []
    sched = get_schedule(con, uid, d)
    if int(sched['is_day_off']): return []
    dur = int(service['duration_min']); t = hm2m(sched['start_time']); end_day = hm2m(sched['end_time']); out = []
    while t + dur <= end_day:
        a = m2hm(t); b = m2hm(t+dur)
        if slot_free(con, uid, d, a, b): out.append({'start':a,'end':b})
        t += 30
    return out

@app.context_processor
def inject():
    return {'user':current_user(),'has_perm':has_perm,'perms':PERMS,'visible_phone':visible_phone,'mask_phone':mask_phone}

@app.route('/')
def index():
    if current_user():
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/healthz')
@app.route('/health')
def healthz():
    return jsonify(status='ok')

_db_initialized = False

def ensure_db():
    global _db_initialized
    if not _db_initialized:
        init_db()
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
    if u['role'] == 'master':
        upcoming = con.execute("SELECT a.*,u.full_name employee_name FROM appointments a LEFT JOIN users u ON u.id=a.employee_id WHERE employee_id=? AND status NOT IN ('Закрыт','Отменен') ORDER BY appointment_date ASC,start_time ASC LIMIT 12", (u['id'],)).fetchall()
        completed = con.execute("SELECT a.*,u.full_name employee_name FROM appointments a LEFT JOIN users u ON u.id=a.employee_id WHERE employee_id=? AND status='Закрыт' ORDER BY appointment_date DESC,start_time DESC LIMIT 12", (u['id'],)).fetchall()
        total = con.execute("SELECT COALESCE(SUM(amount),0) s FROM salary WHERE employee_id=?", (u['id'],)).fetchone()['s']
        con.close(); return render_template('master_dashboard.html', upcoming=upcoming, completed=completed, total=total)

    stats = {
        'appointments': con.execute("SELECT COUNT(*) c FROM appointments").fetchone()['c'],
        'active': con.execute("SELECT COUNT(*) c FROM appointments WHERE status NOT IN ('Закрыт','Отменен')").fetchone()['c'],
        'revenue': con.execute("SELECT COALESCE(SUM(price),0) s FROM appointments WHERE status='Закрыт'").fetchone()['s'],
        'certificate_paid': con.execute("SELECT COALESCE(SUM(certificate_paid),0) s FROM appointments WHERE status='Закрыт'").fetchone()['s'],
        'material_m2': con.execute("SELECT COALESCE(SUM(material_m2),0) s FROM appointments WHERE status='Закрыт'").fetchone()['s'],
        'material_cost': con.execute("SELECT COALESCE(SUM(material_cost),0) s FROM appointments WHERE status='Закрыт'").fetchone()['s'],
        'salary': con.execute("SELECT COALESCE(SUM(salary_amount),0) s FROM appointments WHERE status='Закрыт'").fetchone()['s'],
        'profit': con.execute("SELECT COALESCE(SUM(profit),0) s FROM appointments WHERE status='Закрыт'").fetchone()['s'],
        'stock_items': con.execute("SELECT COUNT(*) c FROM stock_items WHERE active=1").fetchone()['c'],
    }
    rows = con.execute("SELECT a.*,u.full_name employee_name FROM appointments a LEFT JOIN users u ON u.id=a.employee_id ORDER BY appointment_date DESC,start_time DESC LIMIT 20").fetchall()
    requests = con.execute("SELECT pr.*,u.full_name user_name,a.client_name,a.plate_number FROM phone_access_requests pr LEFT JOIN users u ON u.id=pr.user_id LEFT JOIN appointments a ON a.id=pr.appointment_id WHERE pr.status='Ожидает' ORDER BY pr.id DESC LIMIT 20").fetchall()
    con.close(); return render_template('dashboard.html', stats=stats, rows=rows, requests=requests)

@app.route('/booking', methods=['GET','POST'])
def booking():
    con = db()
    if request.method == 'POST':
        sid = request.form['service_id']; uid = request.form['employee_id']; d = request.form['appointment_date']; start = request.form['start_time']
        service = con.execute("SELECT * FROM services WHERE id=? AND active=1", (sid,)).fetchone()
        emp = con.execute("SELECT * FROM users WHERE id=? AND active=1", (uid,)).fetchone()
        if not service or not emp or not employee_can_service(con, uid, sid):
            flash('Мастер не выполняет эту услугу'); return redirect(url_for('booking'))
        end = m2hm(hm2m(start) + int(service['duration_min']))
        if not slot_free(con, uid, d, start, end):
            flash('Это окно уже занято'); return redirect(url_for('booking'))
        name = request.form['client_name']; phone = request.form['phone']; car = request.form.get('car',''); plate = request.form.get('plate_number','').upper().replace(' ','')
        cid = get_client(con,name,phone); carid = get_car(con,cid,car,plate)
        con.execute("INSERT INTO appointments(client_id,car_id,client_name,phone,car,plate_number,service_id,service_name,appointment_date,start_time,end_time,duration_min,status,employee_id,price,comment,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (cid,carid,name,phone,car,plate,sid,service['name'],d,start,end,service['duration_min'],'Записан',uid,service['base_price'],request.form.get('comment',''),now()))
        con.commit(); con.close()
        return render_template('booking_success.html', service=service, emp=emp, d=d, start=start, end=end)
    services = con.execute("SELECT * FROM services WHERE active=1 ORDER BY name").fetchall()
    con.close(); return render_template('booking.html', services=services)

@app.route('/api/masters')
def api_masters():
    con = db(); sid = request.args.get('service_id')
    rows = con.execute("SELECT u.id,u.full_name FROM users u JOIN user_services us ON us.user_id=u.id WHERE us.service_id=? AND us.allowed=1 AND u.active=1 AND u.role!='director' ORDER BY u.full_name", (sid,)).fetchall()
    con.close(); return jsonify([{'id':r['id'],'name':r['full_name']} for r in rows])

@app.route('/api/slots')
def api_slots():
    con = db(); out = available_slots(con, request.args.get('employee_id'), request.args.get('service_id'), request.args.get('date')); con.close()
    return jsonify(out)

@app.route('/calendar', methods=['GET','POST'])
@login_required
@perm_required('calendar')
def calendar_view():
    con = db(); u = current_user()
    if request.method == 'POST':
        sid = request.form['service_id']; uid = request.form['employee_id']; d = request.form['appointment_date']; start = request.form['start_time']
        service = con.execute("SELECT * FROM services WHERE id=?", (sid,)).fetchone()
        end = m2hm(hm2m(start) + int(service['duration_min']))
        if not slot_free(con, uid, d, start, end):
            flash('Время занято'); return redirect(url_for('calendar_view', date=d))
        name = request.form['client_name']; phone = request.form['phone']; car = request.form.get('car',''); plate = request.form.get('plate_number','').upper().replace(' ','')
        cid = get_client(con,name,phone); carid = get_car(con,cid,car,plate)
        con.execute("INSERT INTO appointments(client_id,car_id,client_name,phone,car,plate_number,service_id,service_name,appointment_date,start_time,end_time,duration_min,status,employee_id,price,comment,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (cid,carid,name,phone,car,plate,sid,service['name'],d,start,end,service['duration_min'],'Записан',uid,service['base_price'],request.form.get('comment',''),now()))
        con.commit(); flash('Запись добавлена вручную')
        return redirect(url_for('calendar_view', date=d))

    selected = request.args.get('date') or today(); q = request.args.get('q','').strip()
    month = datetime.strptime(selected, '%Y-%m-%d').date().replace(day=1)
    first, days = pycal.monthrange(month.year, month.month)
    cells = [None] * first
    for day in range(1, days+1):
        ds = date(month.year, month.month, day).isoformat()
        if u['role'] == 'master':
            cnt = con.execute("SELECT COUNT(*) c FROM appointments WHERE appointment_date=? AND employee_id=?", (ds,u['id'])).fetchone()['c']
            closed = con.execute("SELECT COUNT(*) c FROM appointments WHERE appointment_date=? AND employee_id=? AND status='Закрыт'", (ds,u['id'])).fetchone()['c']
        else:
            cnt = con.execute("SELECT COUNT(*) c FROM appointments WHERE appointment_date=?", (ds,)).fetchone()['c']
            closed = con.execute("SELECT COUNT(*) c FROM appointments WHERE appointment_date=? AND status='Закрыт'", (ds,)).fetchone()['c']
        cells.append({'day':day,'date':ds,'count':cnt,'closed':closed})
    while len(cells) % 7: cells.append(None)
    sql = "SELECT a.*,u.full_name employee_name FROM appointments a LEFT JOIN users u ON u.id=a.employee_id WHERE appointment_date=?"
    params = [selected]
    if u['role'] == 'master':
        sql += " AND employee_id=?"; params.append(u['id'])
    if q:
        sql += " AND (phone LIKE ? OR plate_number LIKE ? OR client_name LIKE ? OR car LIKE ?)"; params += [f'%{q}%']*4
    sql += " ORDER BY start_time"
    rows = con.execute(sql, params).fetchall()
    load = con.execute("SELECT COUNT(*) c, COALESCE(SUM(duration_min),0) mins FROM appointments WHERE appointment_date=? AND status!='Отменен'", (selected,)).fetchone()
    services = con.execute("SELECT * FROM services WHERE active=1 ORDER BY name").fetchall()
    employees = con.execute("SELECT * FROM users WHERE active=1 AND role!='director' ORDER BY full_name").fetchall()
    con.close()
    return render_template('calendar.html', cells=cells, rows=rows, selected=selected, q=q, load=load, services=services, employees=employees)

@app.route('/appointment/<int:aid>/extra', methods=['POST'])
@login_required
@perm_required('extra_services')
def add_extra(aid):
    con = db(); u = current_user()
    ap = con.execute("SELECT * FROM appointments WHERE id=?", (aid,)).fetchone()
    if ap and (u['role'] != 'master' or ap['employee_id'] == u['id']):
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
    if ex and ap and (u['role'] != 'master' or ap['employee_id'] == u['id']):
        con.execute("DELETE FROM appointment_extras WHERE id=?", (eid,))
        con.execute("UPDATE appointments SET extras_total=extras_total-?, price=price-? WHERE id=?", (ex['price'],ex['price'],aid))
        con.commit(); flash('Допуслуга удалена')
    con.close(); return redirect(url_for('close_appointment', aid=aid))

@app.route('/appointment/<int:aid>/close', methods=['GET','POST'])
@login_required
@perm_required('calendar')
def close_appointment(aid):
    con = db(); u = current_user()
    ap = con.execute("SELECT a.*,u.full_name employee_name FROM appointments a LEFT JOIN users u ON u.id=a.employee_id WHERE a.id=?", (aid,)).fetchone()
    if not ap:
        con.close(); flash('Запись не найдена'); return redirect(url_for('calendar_view'))
    if u['role'] == 'master' and ap['employee_id'] != u['id']:
        con.close(); flash('Можно закрывать только свои записи'); return redirect(url_for('calendar_view'))
    if request.method == 'POST':
        price = float(request.form.get('price') or 0); mid = request.form.get('material_id') or None
        length = float(request.form.get('material_length_m') or 0); width_cm = float(request.form.get('material_width_cm') or 0)
        m2 = length * (width_cm/100); salary_amount = float(request.form.get('salary_amount') or 0); material_cost = 0
        if mid and m2 > 0:
            mat = con.execute("SELECT * FROM stock_items WHERE id=?", (mid,)).fetchone()
            if not mat or mat['balance'] < m2:
                flash('На складе не хватает материала'); return redirect(url_for('close_appointment', aid=aid))
            material_cost = m2 * float(mat['cost_per_unit'])
            con.execute("UPDATE stock_items SET balance=balance-? WHERE id=?", (m2,mid))
            con.execute("INSERT INTO stock_moves(item_id,appointment_id,user_id,change_qty,move_type,comment,created_at) VALUES(?,?,?,?,?,?,?)", (mid,aid,u['id'],-m2,'Списание по заказу',f'{length} м × {width_cm} см = {m2:.2f} м²',now()))
        cert_number = request.form.get('cert_number','')
        cert_amount = request.form.get('cert_amount') or 0
        ok, cert_msg = pay_certificate_for_appointment(con, aid, cert_number, cert_amount, request.form.get('cert_comment',''))
        if not ok:
            flash(cert_msg)
            return redirect(url_for('close_appointment', aid=aid))
        cert_paid = float(ap['certificate_paid'] or 0) + float(cert_amount or 0)
        profit = price - cert_paid - material_cost - salary_amount
        con.execute("UPDATE appointments SET status='Закрыт',price=?,material_id=?,material_length_m=?,material_width_cm=?,material_m2=?,material_cost=?,salary_amount=?,profit=?,comment=?,closed_at=? WHERE id=?",
                    (price,mid,length,width_cm,m2,material_cost,salary_amount,profit,request.form.get('comment',''),now(),aid))
        if salary_amount > 0:
            con.execute("INSERT INTO salary(employee_id,appointment_id,period,amount,comment,created_at) VALUES(?,?,?,?,?,?)", (ap['employee_id'],aid,datetime.now().strftime('%m.%Y'),salary_amount,'ЗП из закрытой записи',now()))
        con.commit(); con.close(); flash('Запись закрыта'); return redirect(url_for('calendar_view', date=ap['appointment_date']))
    materials = con.execute("SELECT id,name,balance,cost_per_unit FROM stock_items WHERE active=1 AND category='film' AND (visible_to_staff=1 OR ?='director') ORDER BY name", (u['role'],)).fetchall()
    extras = con.execute("SELECT * FROM appointment_extras WHERE appointment_id=? ORDER BY id DESC", (aid,)).fetchall()
    con.close(); return render_template('close.html', ap=ap, materials=materials, extras=extras, is_master=(u['role']=='master'))

@app.route('/appointment/<int:aid>/delete', methods=['POST'])
@login_required
@perm_required('delete_appointments')
def delete_appointment(aid):
    con = db()
    ap = con.execute("SELECT * FROM appointments WHERE id=?", (aid,)).fetchone()
    if ap:
        if ap['material_id'] and ap['material_m2'] > 0:
            con.execute("UPDATE stock_items SET balance=balance+? WHERE id=?", (ap['material_m2'], ap['material_id']))
        con.execute("DELETE FROM appointment_extras WHERE appointment_id=?", (aid,))
        con.execute("DELETE FROM salary WHERE appointment_id=?", (aid,))
        con.execute("DELETE FROM appointments WHERE id=?", (aid,))
        con.commit(); flash('Запись удалена')
    con.close(); return redirect(url_for('calendar_view', date=request.form.get('date') or today()))


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
@perm_required('calendar')
def cancel(aid):
    con = db(); con.execute("UPDATE appointments SET status='Отменен' WHERE id=?", (aid,)); con.commit(); con.close()
    flash('Запись отменена'); return redirect(url_for('calendar_view', date=request.form.get('date') or today()))

@app.route('/certificates', methods=['GET','POST'])
@login_required
@perm_required('certificates')
def certificates():
    con = db()
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'create':
            number = request.form['cert_number'].strip().upper(); nominal = float(request.form.get('nominal') or 0)
            try:
                con.execute("INSERT INTO certificates(cert_number,nominal,balance,client_name,phone,comment,created_at) VALUES(?,?,?,?,?,?,?)", (number,nominal,nominal,request.form.get('client_name',''),request.form.get('phone',''),request.form.get('comment',''),now()))
                cid = con.execute("SELECT last_insert_rowid() id").fetchone()['id']
                con.execute("INSERT INTO certificate_moves(certificate_id,user_id,amount,move_type,comment,created_at) VALUES(?,?,?,?,?,?)", (cid,current_user()['id'],nominal,'Создание','Сертификат создан',now()))
                con.commit(); flash('Сертификат создан')
            except sqlite3.IntegrityError:
                flash('Такой номер сертификата уже есть')
        elif action == 'pay':
            return certificate_pay_internal(con)
        return redirect(url_for('certificates'))
    rows = con.execute("SELECT * FROM certificates ORDER BY id DESC").fetchall()
    moves = con.execute("SELECT cm.*,c.cert_number,u.full_name user_name FROM certificate_moves cm LEFT JOIN certificates c ON c.id=cm.certificate_id LEFT JOIN users u ON u.id=cm.user_id ORDER BY cm.id DESC LIMIT 100").fetchall()
    appointments = con.execute("SELECT id,appointment_date,start_time,client_name,plate_number,service_name FROM appointments WHERE status!='Закрыт' ORDER BY appointment_date DESC,start_time DESC LIMIT 50").fetchall()
    con.close(); return render_template('certificates.html', rows=rows, moves=moves, appointments=appointments)

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
        con.execute("INSERT INTO services(name,duration_min,base_price,comment,created_at) VALUES(?,?,?,?,?)", (request.form['name'],int(request.form['duration_min']),float(request.form.get('base_price') or 0),request.form.get('comment',''),now()))
        con.commit(); flash('Услуга создана'); return redirect(url_for('services'))
    rows = con.execute("SELECT * FROM services ORDER BY active DESC,name").fetchall()
    con.close(); return render_template('services.html', rows=rows)

@app.route('/services/<int:sid>/update', methods=['POST'])
@login_required
@perm_required('services')
def service_update(sid):
    con = db(); con.execute("UPDATE services SET name=?,duration_min=?,base_price=?,active=? WHERE id=?", (request.form['name'],int(request.form['duration_min']),float(request.form.get('base_price') or 0),1 if request.form.get('active') else 0,sid)); con.commit(); con.close()
    flash('Услуга обновлена'); return redirect(url_for('services'))

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
        role = request.form.get('role','master')
        try:
            con.execute("INSERT INTO users(username,password_hash,role,full_name,active,hired_at,created_at) VALUES(?,?,?,?,1,?,?)", (request.form['username'].strip(),generate_password_hash(request.form.get('password') or DEFAULT_PASSWORD),role,request.form['full_name'],today(),now()))
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
    con.close(); return render_template('employees.html', rows=rows, services=services, user_perms=perms, user_services=user_services, schedules=schedules)

@app.route('/employees/<int:uid>/update', methods=['POST'])
@login_required
@perm_required('employees')
def employee_update(uid):
    con = db(); role = request.form.get('role'); active = 1 if request.form.get('active') else 0
    con.execute("UPDATE users SET role=?,active=?,fired_at=? WHERE id=?", (role,active,None if active else today(),uid))
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
            else:
                unit = 'шт'; w = 0; l = 0; bal = float(request.form.get('balance') or 0)
            cost = float(request.form.get('cost_total') or 0) if is_director else 0
            cpm = cost / bal if cost and bal > 0 else 0
            visible = 1 if request.form.get('visible_to_staff') else 0
            con.execute("INSERT INTO stock_items(name,category,unit,width_m,length_m,balance,cost_total,cost_per_unit,visible_to_staff,comment,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)", (request.form['name'],category,unit,w,l,bal,cost,cpm,visible,request.form.get('comment',''),now()))
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
    if u['role'] == 'master':
        rows = con.execute("SELECT * FROM salary WHERE employee_id=? ORDER BY id DESC", (u['id'],)).fetchall()
        total = con.execute("SELECT COALESCE(SUM(amount),0) s FROM salary WHERE employee_id=?", (u['id'],)).fetchone()['s']
        con.close(); return render_template('master_salary.html', rows=rows, total=total)
    rows = con.execute("SELECT s.*,u.full_name employee_name FROM salary s LEFT JOIN users u ON u.id=s.employee_id ORDER BY s.id DESC").fetchall()
    totals = con.execute("SELECT u.full_name,COALESCE(SUM(s.amount),0) total FROM users u LEFT JOIN salary s ON s.employee_id=u.id GROUP BY u.id").fetchall()
    con.close(); return render_template('salary.html', rows=rows, totals=totals)

@app.route('/analytics')
@login_required
@perm_required('analytics')
def analytics():
    con = db(); start = request.args.get('start') or today(); end = request.args.get('end') or today()
    stats = {
        'revenue': con.execute("SELECT COALESCE(SUM(price),0) s FROM appointments WHERE status='Закрыт' AND appointment_date BETWEEN ? AND ?", (start,end)).fetchone()['s'],
        'profit': con.execute("SELECT COALESCE(SUM(profit),0) s FROM appointments WHERE status='Закрыт' AND appointment_date BETWEEN ? AND ?", (start,end)).fetchone()['s'],
        'mat': con.execute("SELECT COALESCE(SUM(material_cost),0) s FROM appointments WHERE status='Закрыт' AND appointment_date BETWEEN ? AND ?", (start,end)).fetchone()['s'],
        'salary': con.execute("SELECT COALESCE(SUM(salary_amount),0) s FROM appointments WHERE status='Закрыт' AND appointment_date BETWEEN ? AND ?", (start,end)).fetchone()['s'],
        'm2': con.execute("SELECT COALESCE(SUM(material_m2),0) s FROM appointments WHERE status='Закрыт' AND appointment_date BETWEEN ? AND ?", (start,end)).fetchone()['s'],
    }
    by_day = con.execute("SELECT appointment_date, COUNT(*) cnt, COALESCE(SUM(price),0) revenue, COALESCE(SUM(profit),0) profit, COALESCE(SUM(material_m2),0) m2 FROM appointments WHERE status='Закрыт' AND appointment_date BETWEEN ? AND ? GROUP BY appointment_date ORDER BY appointment_date DESC", (start,end)).fetchall()
    by_employee = con.execute("SELECT u.full_name,COUNT(a.id) cnt,COALESCE(SUM(a.price),0) revenue,COALESCE(SUM(a.salary_amount),0) salary,COALESCE(SUM(a.material_m2),0) m2,COALESCE(SUM(a.profit),0) profit FROM users u LEFT JOIN appointments a ON a.employee_id=u.id AND a.status='Закрыт' AND a.appointment_date BETWEEN ? AND ? GROUP BY u.id", (start,end)).fetchall()
    con.close(); return render_template('analytics.html', stats=stats, by_day=by_day, by_employee=by_employee, start=start, end=end)

@app.route('/crm', methods=['GET','POST'])
@login_required
@perm_required('crm')
def crm():
    con = db()
    if request.method == 'POST':
        con.execute("INSERT INTO clients(name,phone,source,stage,reason,comment,created_at) VALUES(?,?,?,?,?,?,?)", (request.form.get('name'), request.form.get('phone'), request.form.get('source','Ручное добавление'), request.form.get('stage','Новый'), request.form.get('reason',''), request.form.get('comment',''), now()))
        cid = con.execute("SELECT last_insert_rowid() id").fetchone()['id']
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
    cars = con.execute("SELECT * FROM cars WHERE client_id=? ORDER BY id DESC", (cid,)).fetchall()
    visits = con.execute("SELECT a.*,u.full_name employee_name FROM appointments a LEFT JOIN users u ON u.id=a.employee_id WHERE client_id=? ORDER BY appointment_date DESC,start_time DESC", (cid,)).fetchall()
    con.close(); return render_template('client_card.html', client=client, cars=cars, visits=visits)

if __name__ == '__main__':
    ensure_db()
    app.run(
        debug=os.environ.get('FLASK_DEBUG') == '1',
        host=os.environ.get('HOST', '127.0.0.1'),
        port=int(os.environ.get('PORT', '5000')),
    )
