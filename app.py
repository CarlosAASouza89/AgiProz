from __future__ import annotations

import os
import secrets
import re
import uuid
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from functools import wraps
from pathlib import Path

from flask import Flask, jsonify, request, session, send_from_directory
from werkzeug.security import check_password_hash, generate_password_hash

from db_adapter import USING_POSTGRES, get_connection

BASE_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = BASE_DIR / "instance"
DB_PATH = INSTANCE_DIR / "agiproz.sqlite3"
APP_TIMEZONE = ZoneInfo("America/Sao_Paulo")


def local_now():
    return datetime.now(APP_TIMEZONE)


def local_today():
    return local_now().date()

def get_secret_key():

    configured = os.environ.get("AGIPROZ_SECRET_KEY")
    if configured:
        return configured
    INSTANCE_DIR.mkdir(exist_ok=True)
    path = INSTANCE_DIR / ".secret_key"
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    key = secrets.token_urlsafe(48)
    path.write_text(key, encoding="utf-8")
    return key


app = Flask(__name__, static_folder=None)
app.config.update(
    SECRET_KEY=get_secret_key(),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("SESSION_COOKIE_SECURE", "0") == "1",
)




def get_db():
    return get_connection(INSTANCE_DIR, DB_PATH)




def init_db():
    if USING_POSTGRES:
        init_postgres_db()
        return
    with get_db() as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                login TEXT NOT NULL UNIQUE,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                force_password_change INTEGER NOT NULL DEFAULT 0,
                role TEXT NOT NULL CHECK(role IN ('admin','operator')),
                active INTEGER NOT NULL DEFAULT 1,
                created TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS admin_recovery (
                id INTEGER PRIMARY KEY CHECK(id=1),
                user_id TEXT NOT NULL UNIQUE,
                code_hash TEXT NOT NULL,
                created TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS clients (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                cpf TEXT NOT NULL UNIQUE,
                email TEXT NOT NULL UNIQUE,
                phone TEXT NOT NULL UNIQUE,
                address TEXT NOT NULL DEFAULT '',
                whatsapp_confirmed INTEGER NOT NULL DEFAULT 1,
                active INTEGER NOT NULL DEFAULT 1,
                created TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS loans (
                id TEXT PRIMARY KEY,
                client_id TEXT NOT NULL,
                amount NUMERIC NOT NULL,
                interest NUMERIC NOT NULL,
                installments INTEGER NOT NULL,
                frequency TEXT NOT NULL DEFAULT 'monthly' CHECK(frequency IN ('weekly','biweekly','monthly')),
                created TEXT NOT NULL,
                due TEXT NOT NULL,
                paid INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'open',
                FOREIGN KEY(client_id) REFERENCES clients(id)
            );

            CREATE TABLE IF NOT EXISTS installments (
                id TEXT PRIMARY KEY,
                loan_id TEXT NOT NULL,
                number INTEGER NOT NULL,
                due TEXT NOT NULL,
                value NUMERIC NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','paid','late')),
                paid_at TEXT,
                payment_id TEXT,
                UNIQUE(loan_id, number),
                FOREIGN KEY(loan_id) REFERENCES loans(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS payments (
                id TEXT PRIMARY KEY,
                loan_id TEXT NOT NULL,
                installment INTEGER NOT NULL,
                value NUMERIC NOT NULL,
                date TEXT NOT NULL,
                user_id TEXT NOT NULL,
                FOREIGN KEY(loan_id) REFERENCES loans(id),
                FOREIGN KEY(user_id) REFERENCES users(id),
                UNIQUE(loan_id, installment)
            );

            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                action TEXT NOT NULL,
                entity TEXT NOT NULL,
                entity_id TEXT,
                details TEXT,
                created TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                sender_id TEXT NOT NULL,
                recipient_id TEXT NOT NULL,
                subject TEXT NOT NULL,
                body TEXT NOT NULL,
                created TEXT NOT NULL,
                read_at TEXT,
                archived_sender INTEGER NOT NULL DEFAULT 0,
                archived_recipient INTEGER NOT NULL DEFAULT 0,
                deleted_sender INTEGER NOT NULL DEFAULT 0,
                deleted_recipient INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY(sender_id) REFERENCES users(id),
                FOREIGN KEY(recipient_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS message_drafts (
                id TEXT PRIMARY KEY,
                owner_id TEXT NOT NULL,
                recipient_id TEXT,
                subject TEXT NOT NULL DEFAULT '',
                body TEXT NOT NULL DEFAULT '',
                created TEXT NOT NULL,
                updated TEXT NOT NULL,
                FOREIGN KEY(owner_id) REFERENCES users(id),
                FOREIGN KEY(recipient_id) REFERENCES users(id)
            );
            """
        )
        admin_count = db.execute("SELECT COUNT(*) FROM users WHERE role='admin'").fetchone()[0]
        if admin_count > 1:
            raise RuntimeError("O banco contém mais de um administrador; corrija os dados antes de iniciar o AgiProz.")
        db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_one_admin ON users(role) WHERE role='admin'")

        user_cols = {r[1] for r in db.execute("PRAGMA table_info(users)").fetchall()}
        if "force_password_change" not in user_cols:
            db.execute("ALTER TABLE users ADD COLUMN force_password_change INTEGER NOT NULL DEFAULT 0")
        client_cols = {r[1] for r in db.execute("PRAGMA table_info(clients)").fetchall()}
        if "address" not in client_cols:
            db.execute("ALTER TABLE clients ADD COLUMN address TEXT NOT NULL DEFAULT ''")
        message_cols = {r[1] for r in db.execute("PRAGMA table_info(messages)").fetchall()}
        for col in ("archived_sender", "archived_recipient", "deleted_sender", "deleted_recipient"):
            if col not in message_cols:
                db.execute(f"ALTER TABLE messages ADD COLUMN {col} INTEGER NOT NULL DEFAULT 0")
        loan_cols = {r[1] for r in db.execute("PRAGMA table_info(loans)").fetchall()}
        if "frequency" not in loan_cols:
            db.execute("ALTER TABLE loans ADD COLUMN frequency TEXT NOT NULL DEFAULT 'monthly'")


        ddl = db.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='loans'").fetchone()[0] or ""
        if "'biweekly'" not in ddl:
            db.execute("PRAGMA foreign_keys=OFF")
            db.execute("ALTER TABLE payments RENAME TO payments_AgiProz_migration")
            db.execute("ALTER TABLE loans RENAME TO loans_AgiProz")
            db.execute("""CREATE TABLE loans (
                id TEXT PRIMARY KEY, client_id TEXT NOT NULL, amount REAL NOT NULL, interest REAL NOT NULL,
                installments INTEGER NOT NULL, frequency TEXT NOT NULL DEFAULT 'monthly' CHECK(frequency IN ('weekly','biweekly','monthly')),
                created TEXT NOT NULL, due TEXT NOT NULL, paid INTEGER NOT NULL DEFAULT 0, status TEXT NOT NULL DEFAULT 'open',
                FOREIGN KEY(client_id) REFERENCES clients(id)
            )""")
            db.execute("INSERT INTO loans SELECT id,client_id,amount,interest,installments,frequency,created,due,paid,status FROM loans_AgiProz")
            db.execute("DROP TABLE loans_AgiProz")
            db.execute("""CREATE TABLE payments (
                id TEXT PRIMARY KEY, loan_id TEXT NOT NULL, installment INTEGER NOT NULL, value NUMERIC NOT NULL,
                date TEXT NOT NULL, user_id TEXT NOT NULL, FOREIGN KEY(loan_id) REFERENCES loans(id), FOREIGN KEY(user_id) REFERENCES users(id)
            )""")
            db.execute("INSERT INTO payments SELECT id,loan_id,installment,value,date,user_id FROM payments_AgiProz_migration")
            db.execute("DROP TABLE payments_AgiProz_migration")
            db.execute("PRAGMA foreign_keys=ON")


        db.execute("CREATE INDEX IF NOT EXISTS idx_installments_loan ON installments(loan_id, number)")
        db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_payments_loan_installment ON payments(loan_id, installment)")
        loans_for_installments = db.execute("SELECT * FROM loans").fetchall()
        from datetime import timedelta
        from calendar import monthrange
        def previous_period(iso, frequency):
            current = date.fromisoformat(iso)
            if frequency == 'weekly': return (current - timedelta(days=7)).isoformat()
            if frequency == 'biweekly': return (current - timedelta(days=14)).isoformat()
            y,m,day=current.year,current.month,current.day
            m -= 1
            if m < 1: y -= 1; m = 12
            day=min(day,monthrange(y,m)[1])
            return f"{y:04d}-{m:02d}-{day:02d}"
        def next_period(iso, frequency):
            current=date.fromisoformat(iso)
            if frequency == 'weekly': return (current + timedelta(days=7)).isoformat()
            if frequency == 'biweekly': return (current + timedelta(days=14)).isoformat()
            y,m,day=current.year,current.month,current.day
            m += 1
            if m > 12: y += 1; m = 1
            day=min(day,monthrange(y,m)[1])
            return f"{y:04d}-{m:02d}-{day:02d}"
        for lrow in loans_for_installments:
            existing=db.execute("SELECT COUNT(*) FROM installments WHERE loan_id=?",(lrow['id'],)).fetchone()[0]
            if existing: continue
            first=lrow['due']
            for _ in range(int(lrow['paid'])): first=previous_period(first,lrow['frequency'])
            total=money(money(lrow['amount']) * (Decimal('1.00') + money(lrow['interest']) / Decimal('100')))
            value=money(total / int(lrow['installments']))
            dates=[]; cur=first
            for n in range(1,int(lrow['installments'])+1):
                dates.append(cur); cur=next_period(cur,lrow['frequency'])

            values=[value]*(len(dates)-1)+[money(total-value*(len(dates)-1))] if dates else []
            for n,due_date in enumerate(dates,1):
                paid=n<=int(lrow['paid'])
                db.execute("INSERT OR IGNORE INTO installments(id,loan_id,number,due,value,status,paid_at) VALUES(?,?,?,?,?,?,?)",
                           (uid('i'),lrow['id'],n,due_date,values[n-1],'paid' if paid else ('late' if due_date < iso_today() else 'pending'), iso_today() if paid else None))


        ensure_admin_recovery(db)



def init_postgres_db():
    schema = """
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        login TEXT NOT NULL UNIQUE,
        email TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        force_password_change INTEGER NOT NULL DEFAULT 0,
        role TEXT NOT NULL CHECK(role IN ('admin','operator')),
        active INTEGER NOT NULL DEFAULT 1,
        created TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS admin_recovery (
        id INTEGER PRIMARY KEY CHECK(id=1),
        user_id TEXT NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
        code_hash TEXT NOT NULL,
        created TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS clients (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        cpf TEXT NOT NULL UNIQUE,
        email TEXT NOT NULL UNIQUE,
        phone TEXT NOT NULL UNIQUE,
        address TEXT NOT NULL DEFAULT '',
        whatsapp_confirmed INTEGER NOT NULL DEFAULT 1,
        active INTEGER NOT NULL DEFAULT 1,
        created TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS loans (
        id TEXT PRIMARY KEY,
        client_id TEXT NOT NULL REFERENCES clients(id),
        amount NUMERIC(12,2) NOT NULL,
        interest NUMERIC(7,2) NOT NULL,
        installments INTEGER NOT NULL,
        frequency TEXT NOT NULL DEFAULT 'monthly' CHECK(frequency IN ('weekly','biweekly','monthly')),
        created TEXT NOT NULL,
        due TEXT NOT NULL,
        paid INTEGER NOT NULL DEFAULT 0,
        status TEXT NOT NULL DEFAULT 'open'
    );
    CREATE TABLE IF NOT EXISTS installments (
        id TEXT PRIMARY KEY,
        loan_id TEXT NOT NULL REFERENCES loans(id) ON DELETE CASCADE,
        number INTEGER NOT NULL,
        due TEXT NOT NULL,
        value NUMERIC(12,2) NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','paid','late')),
        paid_at TEXT,
        payment_id TEXT,
        UNIQUE(loan_id, number)
    );
    CREATE TABLE IF NOT EXISTS payments (
        id TEXT PRIMARY KEY,
        loan_id TEXT NOT NULL REFERENCES loans(id),
        installment INTEGER NOT NULL,
        value NUMERIC(12,2) NOT NULL,
        date TEXT NOT NULL,
        user_id TEXT NOT NULL REFERENCES users(id),
        UNIQUE(loan_id, installment)
    );
    CREATE TABLE IF NOT EXISTS audit_logs (
        id BIGSERIAL PRIMARY KEY,
        user_id TEXT REFERENCES users(id),
        action TEXT NOT NULL,
        entity TEXT NOT NULL,
        entity_id TEXT,
        details TEXT,
        created TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS messages (
        id TEXT PRIMARY KEY,
        sender_id TEXT NOT NULL REFERENCES users(id),
        recipient_id TEXT NOT NULL REFERENCES users(id),
        subject TEXT NOT NULL,
        body TEXT NOT NULL,
        created TEXT NOT NULL,
        read_at TEXT,
        archived_sender INTEGER NOT NULL DEFAULT 0,
        archived_recipient INTEGER NOT NULL DEFAULT 0,
        deleted_sender INTEGER NOT NULL DEFAULT 0,
        deleted_recipient INTEGER NOT NULL DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS message_drafts (
        id TEXT PRIMARY KEY,
        owner_id TEXT NOT NULL REFERENCES users(id),
        recipient_id TEXT REFERENCES users(id),
        subject TEXT NOT NULL DEFAULT '',
        body TEXT NOT NULL DEFAULT '',
        created TEXT NOT NULL,
        updated TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_installments_loan ON installments(loan_id, number);
    CREATE UNIQUE INDEX IF NOT EXISTS idx_payments_loan_installment ON payments(loan_id, installment);
    CREATE UNIQUE INDEX IF NOT EXISTS idx_one_admin ON users(role) WHERE role='admin';
    """
    with get_db() as db:
        db.executescript(schema)
        ensure_admin_recovery(db)


def generate_temporary_password():
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789@#"
    while True:
        password = "".join(secrets.choice(alphabet) for _ in range(12))
        if valid_password_policy(password):
            return password


def generate_recovery_code():

    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "AGI-" + "-".join("".join(secrets.choice(alphabet) for _ in range(4)) for _ in range(3))


def save_recovery_code_file(code):

    if USING_POSTGRES:
        return None
    INSTANCE_DIR.mkdir(exist_ok=True)
    path = INSTANCE_DIR / "admin_recovery_code.txt"
    path.write_text(
        "CHAVE DE RECUPERAÇÃO DO ADMINISTRADOR AGIPROZ\n\n"
        f"{code}\n\n"
        "Guarde esta chave em local seguro. Ela permite redefinir a senha do administrador.\n"
        "Não compartilhe esta chave.\n",
        encoding="utf-8",
    )


def ensure_admin_recovery(db):

    admin = db.execute("SELECT id FROM users WHERE role='admin' ORDER BY created LIMIT 1").fetchone()
    if not admin:
        return None
    existing = db.execute("SELECT 1 FROM admin_recovery WHERE id=1").fetchone()
    if existing:
        return None
    code = generate_recovery_code()
    db.execute(
        "INSERT INTO admin_recovery(id,user_id,code_hash,created) VALUES(1,?,?,?)",
        (admin["id"], generate_password_hash(code), local_now().isoformat(timespec="seconds")),
    )
    save_recovery_code_file(code)
    return code


MONEY_QUANTUM = Decimal("0.01")


def to_decimal(value, default=None):
    try:
        result = Decimal(str(value))
        if not result.is_finite():
            return default
        return result.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError):
        return default


def money(value):
    return Decimal(str(value)).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def money_json(value):
    return float(money(value))


def installment_date(first_due, frequency, number):
    if number <= 1:
        return first_due
    if frequency == "weekly":
        return first_due + timedelta(days=7 * (number - 1))
    if frequency == "biweekly":
        return first_due + timedelta(days=14 * (number - 1))

    month_index = first_due.month - 1 + (number - 1)
    year = first_due.year + month_index // 12
    month = month_index % 12 + 1
    from calendar import monthrange
    day = min(first_due.day, monthrange(year, month)[1])
    return date(year, month, day)


def uid(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4()}"


def iso_today():
    return local_today().isoformat()


def normalize_cpf(value):
    return "".join(ch for ch in str(value or "") if ch.isdigit())

def valid_cpf(value):
    cpf=normalize_cpf(value)
    if len(cpf)!=11 or len(set(cpf))==1:
        return False
    total=sum(int(cpf[i])*(10-i) for i in range(9))
    digit=11-(total%11)
    if digit>=10: digit=0
    if digit!=int(cpf[9]): return False
    total=sum(int(cpf[i])*(11-i) for i in range(10))
    digit=11-(total%11)
    if digit>=10: digit=0
    return digit==int(cpf[10])

def valid_name(value):
    name = " ".join(str(value or "").strip().split())
    return 3 <= len(name) <= 80 and bool(re.fullmatch(r"[A-Za-zÀ-ÖØ-öø-ÿ]+(?:[ '’\-][A-Za-zÀ-ÖØ-öø-ÿ]+)*", name))


def valid_login(value):
    login = str(value or "").strip().lower()
    return 3 <= len(login) <= 30 and bool(re.fullmatch(r"[a-z0-9][a-z0-9._-]*", login))


def valid_client_email(value):
    v = str(value or "").strip()
    if not v or v != v.lower() or any(ord(c) >= 128 for c in v):
        return False
    if len(v) > 120 or any(c.isspace() for c in v) or v.count("@") != 1:
        return False
    local, domain = v.rsplit("@", 1)
    if not local or not domain or local.startswith(".") or local.endswith(".") or ".." in local:
        return False
    return bool(re.fullmatch(r"[a-z0-9.!#$%&'*+/=?^_`{|}~-]+", local)) and bool(re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?\.[a-z]{2,63}", domain))

def is_internal_email(value):
    v = str(value or "").strip().lower()
    return valid_client_email(v) and v.endswith("@agiproz.local")

def valid_phone(value):
    phone = "".join(ch for ch in str(value or "") if ch.isdigit())
    return bool(re.fullmatch(r"[1-9][0-9]9[0-9]{8}", phone))

def valid_password_policy(value):
    p=str(value or "")
    return 8 <= len(p) <= 64 and not any(c.isspace() for c in p) and any(c.isupper() for c in p) and any(c.isdigit() for c in p) and any(not c.isalnum() for c in p)


def user_dict(row):
    return {
        "id": row["id"], "name": row["name"], "login": row["login"], "email": row["email"],
        "role": row["role"], "active": bool(row["active"]), "forcePasswordChange": bool(row["force_password_change"]) if "force_password_change" in row.keys() else False, "created": row["created"]
    }


def client_dict(row):
    return {
        "id": row["id"], "name": row["name"], "cpf": format_cpf(row["cpf"]), "email": row["email"],
        "phone": format_phone(row["phone"]), "address": row["address"] if "address" in row.keys() else "", "whatsappConfirmed": bool(row["whatsapp_confirmed"]),
        "active": bool(row["active"]), "created": row["created"]
    }


def loan_dict(row):
    return {
        "id": row["id"],
        "clientId": row["client_id"],
        "amount": money_json(row["amount"]),
        "interest": money_json(row["interest"]),
        "installments": row["installments"],
        "frequency": row["frequency"] if "frequency" in row.keys() else "monthly",
        "created": row["created"],
        "due": row["due"],
        "paid": row["paid"],
        "status": row["status"],
    }


def payment_dict(row):
    return {
        "id": row["id"],
        "loanId": row["loan_id"],
        "installment": row["installment"],
        "value": money_json(row["value"]),
        "date": row["date"],
    }


def installment_dict(row):
    due_date = date.fromisoformat(row["due"])
    late_days = max(0, (local_today() - due_date).days) if row["status"] != "paid" else 0
    late_interest = money(money(row["value"]) * Decimal("0.10") * late_days)
    status = "late" if row["status"] != "paid" and due_date < local_today() else row["status"]
    return {
        "id": row["id"],
        "loanId": row["loan_id"],
        "number": row["number"],
        "due": row["due"],
        "value": money_json(row["value"]),
        "status": status,
        "paidAt": row["paid_at"],
        "paymentId": row["payment_id"],
        "lateDays": late_days,
        "lateInterest": money_json(late_interest),
        "amountDue": money_json(money(row["value"]) + late_interest),
    }


def format_cpf(v):
    d = normalize_cpf(v)
    return f"{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:]}" if len(d) == 11 else v


def format_phone(v):
    d = "".join(ch for ch in str(v or "") if ch.isdigit())
    return f"({d[:2]}){d[2:7]}-{d[7:]}" if len(d) == 11 else v


def current_user():
    uid_ = session.get("user_id")
    if not uid_:
        return None
    with get_db() as db:
        row = db.execute("SELECT * FROM users WHERE id=?", (uid_,)).fetchone()
        return user_dict(row) if row else None



def require_login(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = current_user()
        if not user or not user["active"]:
            return jsonify(error="Não autenticado."), 401
        if user["forcePasswordChange"] and request.path != "/api/password/change":
            return jsonify(error="Altere a senha temporária antes de continuar.", forcePasswordChange=True), 403
        return fn(user, *args, **kwargs)
    return wrapper


def require_admin(fn):
    @wraps(fn)
    def wrapper(user, *args, **kwargs):
        if user["role"] != "admin":
            return jsonify(error="Acesso exclusivo do administrador."), 403
        return fn(user, *args, **kwargs)
    return wrapper


def audit(db, user_id, action, entity, entity_id=None, details=None):
    db.execute(
        "INSERT INTO audit_logs(user_id,action,entity,entity_id,details,created) VALUES(?,?,?,?,?,?)",
        (user_id, action, entity, entity_id, details or "", local_now().isoformat(timespec="seconds")),
    )


@app.get("/api/bootstrap")
def bootstrap():
    with get_db() as db:
        has_admin = db.execute("SELECT 1 FROM users WHERE role='admin' LIMIT 1").fetchone() is not None
    return jsonify(setupRequired=not has_admin, user=current_user())


@app.post("/api/setup")
def setup():
    data = request.get_json(silent=True) or {}
    name, email, password = str(data.get("name", "")).strip(), str(data.get("email", "")).strip().lower(), str(data.get("password", ""))
    if not valid_name(name):
        return jsonify(error="Informe um nome válido."), 400
    if not valid_password_policy(password):
        return jsonify(error="A senha deve ter no mínimo 8 caracteres, uma letra maiúscula, um número e um caractere especial."), 400
    if not is_internal_email(email):
        return jsonify(error="Use um e-mail válido no formato nome@agiproz.local."), 400
    with get_db() as db:
        if not USING_POSTGRES:
            db.execute("BEGIN IMMEDIATE")
        else:
            # Serialize first-admin setup in PostgreSQL so concurrent requests cannot
            # both observe an empty admin table before inserting.
            db.execute("SELECT pg_advisory_xact_lock(7142026)")
        if db.execute("SELECT 1 FROM users WHERE role='admin' LIMIT 1").fetchone():
            return jsonify(error="O administrador já foi configurado."), 409
        user_id = uid("u")
        db.execute("INSERT INTO users(id,name,login,email,password_hash,force_password_change,role,active,created) VALUES(?,?,?,?,?,?,?,?,?)", (user_id,name,"admin",email,generate_password_hash(password),0,"admin",1,iso_today()))
        recovery_code = generate_recovery_code()
        db.execute("INSERT INTO admin_recovery(id,user_id,code_hash,created) VALUES(1,?,?,?)", (user_id,generate_password_hash(recovery_code),local_now().isoformat(timespec="seconds")))
        save_recovery_code_file(recovery_code)
        audit(db, user_id, "CREATE", "user", user_id, "Administrador inicial criado")
    session["user_id"] = user_id
    return jsonify(user=current_user(), recoveryCode=recovery_code, recoveryStoredLocally=not USING_POSTGRES)


@app.post("/api/admin/recover")
def recover_admin_password():

    d = request.get_json(silent=True) or {}
    email = str(d.get("email", "")).strip().lower()
    code = str(d.get("recoveryCode", "")).strip().upper()
    password = str(d.get("password", ""))
    password2 = str(d.get("password2", ""))
    if not is_internal_email(email) or not code:
        return jsonify(error="Informe o e-mail do administrador e a chave de recuperação."), 400
    if not valid_password_policy(password):
        return jsonify(error="A nova senha deve ter no mínimo 8 caracteres, uma letra maiúscula, um número e um caractere especial."), 400
    if password != password2:
        return jsonify(error="As senhas não coincidem."), 400
    with get_db() as db:
        row = db.execute("SELECT * FROM users WHERE role='admin' AND lower(email)=?", (email,)).fetchone()
        recovery = db.execute("SELECT * FROM admin_recovery WHERE id=1").fetchone()
        if not row or not recovery or recovery["user_id"] != row["id"] or not check_password_hash(recovery["code_hash"], code):
            return jsonify(error="E-mail ou chave de recuperação inválidos."), 401
        db.execute("UPDATE users SET password_hash=?, force_password_change=0 WHERE id=?", (generate_password_hash(password), row["id"]))
        new_recovery_code = generate_recovery_code()
        db.execute("UPDATE admin_recovery SET code_hash=?, created=?, user_id=? WHERE id=1", (generate_password_hash(new_recovery_code), local_now().isoformat(timespec="seconds"), row["id"]))
        save_recovery_code_file(new_recovery_code)
        audit(db, row["id"], "RECOVER", "user", row["id"], "Senha do administrador redefinida; chave de recuperação rotacionada")
        updated = db.execute("SELECT * FROM users WHERE id=?", (row["id"],)).fetchone()
    session["user_id"] = row["id"]
    return jsonify(user=user_dict(updated), recoveryCode=new_recovery_code, recoveryStoredLocally=not USING_POSTGRES)


@app.post("/api/login")
def login():
    data = request.get_json(silent=True) or {}
    login_value = str(data.get("login", "")).strip().lower()
    password = str(data.get("password", ""))
    with get_db() as db:
        row = db.execute("SELECT * FROM users WHERE lower(login)=? OR lower(email)=?", (login_value, login_value)).fetchone()
        if not row or not check_password_hash(row["password_hash"], password):
            return jsonify(error="Login ou senha inválidos."), 401
        if not row["active"]:
            return jsonify(error="Este acesso está desativado pelo administrador."), 403
        session["user_id"] = row["id"]
        audit(db, row["id"], "LOGIN", "session", row["id"], "Login realizado")
        return jsonify(user=user_dict(row))


@app.post("/api/password/change")
@require_login
def change_password(user):
    d=request.get_json(silent=True) or {}; p=str(d.get("password", "")); p2=str(d.get("password2", ""))
    if not valid_password_policy(p): return jsonify(error="A senha deve ter no mínimo 8 caracteres, uma letra maiúscula, um número e um caractere especial."),400
    if p!=p2:return jsonify(error="As senhas não coincidem."),400
    with get_db() as db:
        db.execute("UPDATE users SET password_hash=?,force_password_change=0 WHERE id=?",(generate_password_hash(p),user["id"]))
        audit(db,user["id"],"UPDATE","user",user["id"],"Senha alterada")
        row=db.execute("SELECT * FROM users WHERE id=?",(user["id"],)).fetchone()
    return jsonify(user=user_dict(row))


@app.post("/api/logout")
def logout():
    session.clear()
    return jsonify(ok=True)


@app.get("/api/me")
@require_login
def me(user):
    return jsonify(user=user)


@app.get("/api/data")
@require_login
def data(user):
    with get_db() as db:
        # Operators only need active recipients for the messaging UI. Administrators
        # can see the full operator list, including inactive accounts.
        user_sql = "SELECT * FROM users WHERE active=1 ORDER BY name" if user["role"] != "admin" else "SELECT * FROM users ORDER BY name"
        users = [user_dict(r) for r in db.execute(user_sql)]
        clients = [client_dict(r) for r in db.execute("SELECT * FROM clients ORDER BY name")]
        loans = [loan_dict(r) for r in db.execute("SELECT * FROM loans ORDER BY created")]
        payments = [payment_dict(r) for r in db.execute("SELECT * FROM payments ORDER BY date")]
        installments = [installment_dict(r) for r in db.execute("SELECT * FROM installments ORDER BY loan_id, number")]
    return jsonify(users=users, clients=clients, loans=loans, payments=payments, installments=installments)


@app.get("/api/audit")
@require_login
@require_admin
def get_audit(user):
    with get_db() as db:
        rows = db.execute("SELECT a.*, u.name user_name FROM audit_logs a LEFT JOIN users u ON u.id=a.user_id ORDER BY a.id DESC LIMIT 200").fetchall()
        return jsonify(logs=[dict(r) for r in rows])


@app.post("/api/users")
@require_login
@require_admin
def create_user(user):
    d = request.get_json(silent=True) or {}
    name, login_v, email = str(d.get("name","")).strip(), str(d.get("login","")).strip().lower(), str(d.get("email","")).strip().lower()
    if not valid_name(name) or not valid_login(login_v) or not is_internal_email(email):
        return jsonify(error="Dados inválidos. Informe nome, login e e-mail @agiproz.local válidos."), 400
    with get_db() as db:
        if db.execute("SELECT 1 FROM users WHERE login=? OR email=?", (login_v,email)).fetchone():
            return jsonify(error="Login ou e-mail já utilizado."), 409
        uid_ = uid("u")
        temp_password = generate_temporary_password()
        db.execute("INSERT INTO users(id,name,login,email,password_hash,force_password_change,role,active,created) VALUES(?,?,?,?,?,?,?,?,?)", (uid_,name,login_v,email,generate_password_hash(temp_password),1,"operator",1,iso_today()))
        audit(db,user["id"],"CREATE","user",uid_,f"Operador {login_v} criado")
        row=db.execute("SELECT * FROM users WHERE id=?",(uid_,)).fetchone()
    return jsonify(user=user_dict(row), temporaryPassword=temp_password), 201


@app.post("/api/users/<uid_>/reset-password")
@require_login
@require_admin
def reset_operator_password(user, uid_):

    with get_db() as db:
        target = db.execute("SELECT * FROM users WHERE id=? AND role='operator'", (uid_,)).fetchone()
        if not target:
            return jsonify(error="Operador inválido."), 404
        temp_password = generate_temporary_password()
        db.execute("UPDATE users SET password_hash=?, force_password_change=1 WHERE id=?", (generate_password_hash(temp_password), uid_))
        audit(db, user["id"], "RESET_PASSWORD", "user", uid_, "Senha temporária do operador redefinida; troca obrigatória no próximo acesso")
        row = db.execute("SELECT * FROM users WHERE id=?", (uid_,)).fetchone()
    return jsonify(user=user_dict(row), temporaryPassword=temp_password)


@app.put("/api/users/<uid_>")
@require_login
@require_admin
def update_user(user, uid_):
    d=request.get_json(silent=True) or {}
    with get_db() as db:
        target=db.execute("SELECT * FROM users WHERE id=? AND role='operator'",(uid_,)).fetchone()
        if not target:return jsonify(error="Operador inválido."),404
        name,login_v,email=str(d.get("name","")).strip(),str(d.get("login","")).strip().lower(),str(d.get("email","")).strip().lower()
        if not valid_name(name) or not valid_login(login_v) or not is_internal_email(email):return jsonify(error="Informe nome, login e e-mail @agiproz.local válidos."),400
        if db.execute("SELECT 1 FROM users WHERE (login=? OR email=?) AND id<>?",(login_v,email,uid_)).fetchone():return jsonify(error="Login ou e-mail já utilizado."),409
        db.execute("UPDATE users SET name=?,login=?,email=? WHERE id=?",(name,login_v,email,uid_))
        if d.get("password"):
            p=str(d["password"])
            if not valid_password_policy(p):return jsonify(error="A senha deve ter no mínimo 8 caracteres, uma letra maiúscula, um número e um caractere especial."),400
            db.execute("UPDATE users SET password_hash=?,force_password_change=1 WHERE id=?",(generate_password_hash(p),uid_))
        audit(db,user["id"],"UPDATE","user",uid_,"Operador atualizado")
        row=db.execute("SELECT * FROM users WHERE id=?",(uid_,)).fetchone()
    return jsonify(user=user_dict(row))


@app.patch("/api/users/<uid_>/toggle")
@require_login
@require_admin
def toggle_user(user, uid_):
    with get_db() as db:
        row=db.execute("SELECT * FROM users WHERE id=? AND role='operator'",(uid_,)).fetchone()
        if not row:return jsonify(error="Operador inválido."),404
        active=0 if row["active"] else 1
        db.execute("UPDATE users SET active=? WHERE id=?",(active,uid_))
        audit(db,user["id"],"UPDATE","user",uid_,f"Operador {'ativado' if active else 'desativado'}")
    return jsonify(ok=True,active=bool(active))


@app.post("/api/clients")
@require_login
def create_client(user):
    d=request.get_json(silent=True) or {}
    name=str(d.get("name", "")).strip().upper()
    cpf=normalize_cpf(d.get("cpf"))
    email=str(d.get("email", "")).strip()
    phone="".join(c for c in str(d.get("phone", "")).strip() if c.isdigit())
    address=str(d.get("address", "")).strip()
    if not valid_name(name) or not valid_cpf(cpf) or not valid_phone(phone) or not valid_client_email(email) or not address:
        return jsonify(error="Confira nome, CPF, e-mail, telefone e endereço."),400
    if d.get("whatsappConfirmed") is not True:
        return jsonify(error="Confirme que o telefone informado possui WhatsApp."),400
    with get_db() as db:
        if db.execute("SELECT 1 FROM clients WHERE cpf=? OR email=? OR phone=?",(cpf,email,phone)).fetchone():return jsonify(error="CPF, e-mail ou celular já cadastrado."),409
        cid=uid("c");db.execute("INSERT INTO clients(id,name,cpf,email,phone,address,whatsapp_confirmed,active,created) VALUES(?,?,?,?,?,?,?,?,?)",(cid,name,cpf,email.lower(),phone,address,1,1,iso_today()))
        audit(db,user["id"],"CREATE","client",cid,"Cliente cadastrado")
        row=db.execute("SELECT * FROM clients WHERE id=?",(cid,)).fetchone()
    return jsonify(client=client_dict(row)),201


@app.put("/api/clients/<cid>")
@require_login
def update_client(user,cid):
    d=request.get_json(silent=True) or {}
    name=str(d.get("name", "")).strip().upper()
    cpf=normalize_cpf(d.get("cpf"))
    email=str(d.get("email", "")).strip().lower()
    phone="".join(c for c in str(d.get("phone", "")) if c.isdigit())
    address=str(d.get("address", "")).strip()
    with get_db() as db:
        if not db.execute("SELECT 1 FROM clients WHERE id=?",(cid,)).fetchone():return jsonify(error="Cliente não encontrado."),404
        if not valid_name(name) or not valid_cpf(cpf) or not valid_phone(phone) or not valid_client_email(email) or not address:return jsonify(error="Informe nome, CPF, e-mail, telefone e endereço corretamente."),400
        if d.get("whatsappConfirmed") is not True:return jsonify(error="Confirme que o telefone informado possui WhatsApp."),400
        if db.execute("SELECT 1 FROM clients WHERE (cpf=? OR email=? OR phone=?) AND id<>?",(cpf,email.lower(),phone,cid)).fetchone():return jsonify(error="CPF, e-mail ou celular já cadastrado."),409
        db.execute("UPDATE clients SET name=?,cpf=?,email=?,phone=?,address=?,whatsapp_confirmed=? WHERE id=?",(name,cpf,email.lower(),phone,address,1 if d.get("whatsappConfirmed",True) else 0,cid))
        audit(db,user["id"],"UPDATE","client",cid,"Cliente atualizado")
        row=db.execute("SELECT * FROM clients WHERE id=?",(cid,)).fetchone()
    return jsonify(client=client_dict(row))


@app.delete("/api/clients/<cid>")
@require_login
def delete_client(user, cid):
    with get_db() as db:
        row=db.execute("SELECT * FROM clients WHERE id=?",(cid,)).fetchone()
        if not row:return jsonify(error="Cliente não encontrado."),404
        if db.execute("SELECT 1 FROM loans WHERE client_id=? LIMIT 1",(cid,)).fetchone():
            return jsonify(error="Este cliente não pode ser excluído porque já possui ou possuiu empréstimo cadastrado."),400
        db.execute("DELETE FROM clients WHERE id=?",(cid,))
        audit(db,user["id"],"DELETE","client",cid,"Cliente excluído sem empréstimo")
    return jsonify(ok=True)


@app.post("/api/loans")
@require_login
def create_loan(user):
    data = request.get_json(silent=True) or {}
    client_id = str(data.get("clientId") or "").strip()
    frequency = str(data.get("frequency", "monthly")).strip().lower()
    due = str(data.get("due", "")).strip()

    amount = to_decimal(data.get("amount"))
    interest = to_decimal(data.get("interest"))
    try:
        installments = int(data.get("installments", 0))
        due_date = date.fromisoformat(due)
    except (TypeError, ValueError):
        return jsonify(error="Informe valores válidos para parcelas e vencimento."), 400

    if amount is None or interest is None:
        return jsonify(error="Informe valores numéricos válidos para valor e taxa."), 400
    if due_date < local_today():
        return jsonify(error="O primeiro vencimento não pode ser anterior à data atual."), 400
    if not (Decimal("50.00") <= amount <= Decimal("50000.00")):
        return jsonify(error="O valor do empréstimo deve estar entre R$ 50,00 e R$ 50.000,00."), 400
    if not (Decimal("0.00") <= interest <= Decimal("100.00")):
        return jsonify(error="A taxa de juros deve estar entre 0% e 100%."), 400
    if not (1 <= installments <= 36) or frequency not in {"weekly", "biweekly", "monthly"}:
        return jsonify(error="Dados do empréstimo inválidos."), 400

    with get_db() as db:
        if not db.execute("SELECT 1 FROM clients WHERE id=? AND active=1", (client_id,)).fetchone():
            return jsonify(error="Selecione um cliente ativo válido."), 400

        loan_id = uid("l")
        db.execute(
            "INSERT INTO loans(id,client_id,amount,interest,installments,frequency,created,due,paid,status) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (loan_id, client_id, amount, interest, installments, frequency, iso_today(), due, 0, "open"),
        )

        total = money(amount * (Decimal("1.00") + interest / Decimal("100")))
        base_value = money(total / installments)
        first_values = [base_value] * installments
        first_values[-1] = money(total - sum(first_values[:-1], Decimal("0.00")))

        for number in range(1, installments + 1):
            installment_due = installment_date(due_date, frequency, number).isoformat()
            db.execute(
                "INSERT INTO installments(id,loan_id,number,due,value,status) VALUES(?,?,?,?,?,?)",
                (uid("i"), loan_id, number, installment_due, first_values[number - 1], "pending"),
            )

        audit(db, user["id"], "CREATE", "loan", loan_id, "Empréstimo criado")
        row = db.execute("SELECT * FROM loans WHERE id=?", (loan_id,)).fetchone()

    return jsonify(loan=loan_dict(row)), 201


@app.post("/api/payments")
@require_login
def create_payment(user):
    data = request.get_json(silent=True) or {}
    loan_id = str(data.get("loanId") or "").strip()
    installment_id = str(data.get("installmentId") or "").strip()

    with get_db() as db:
        if not USING_POSTGRES:
            db.execute("BEGIN IMMEDIATE")
        loan = db.execute("SELECT * FROM loans WHERE id=?", (loan_id,)).fetchone()
        if not loan:
            return jsonify(error="Contrato não encontrado."), 404

        if USING_POSTGRES:
            db.execute("SELECT id FROM loans WHERE id=? FOR UPDATE", (loan_id,)).fetchone()

        if installment_id:
            installment = db.execute(
                "SELECT * FROM installments WHERE id=? AND loan_id=?",
                (installment_id, loan_id),
            ).fetchone()
        else:
            installment = db.execute(
                "SELECT * FROM installments WHERE loan_id=? AND status!='paid' ORDER BY number LIMIT 1",
                (loan_id,),
            ).fetchone()

        if not installment:
            return jsonify(error="Nenhuma parcela pendente encontrada."), 400

        first_open = db.execute(
            "SELECT * FROM installments WHERE loan_id=? AND status!='paid' ORDER BY number LIMIT 1",
            (loan_id,),
        ).fetchone()
        if first_open and first_open["id"] != installment["id"]:
            return jsonify(error=f"A parcela {first_open['number']} deve ser paga primeiro."), 400

        if db.execute(
            "SELECT 1 FROM payments WHERE loan_id=? AND installment=?",
            (loan_id, installment["number"]),
        ).fetchone():
            return jsonify(error="Esta parcela já possui um pagamento registrado."), 409

        paid_date = iso_today()
        late_days = max(0, (local_today() - date.fromisoformat(installment["due"])).days)
        amount_due = money(money(installment["value"]) * (Decimal("1.00") + Decimal("0.10") * late_days))
        payment_id = uid("p")

        db.execute(
            "INSERT INTO payments(id,loan_id,installment,value,date,user_id) VALUES(?,?,?,?,?,?)",
            (payment_id, loan_id, installment["number"], amount_due, paid_date, user["id"]),
        )
        db.execute(
            "UPDATE installments SET status='paid',paid_at=?,payment_id=? WHERE id=? AND status!='paid'",
            (paid_date, payment_id, installment["id"]),
        )

        paid = int(loan["paid"]) + 1
        status = "paid" if paid >= int(loan["installments"]) else "open"
        db.execute("UPDATE loans SET paid=?,status=? WHERE id=?", (paid, status, loan_id))
        audit(db, user["id"], "CREATE", "payment", payment_id, f"Parcela {installment['number']}/{loan['installments']} paga")
        updated_loan = db.execute("SELECT * FROM loans WHERE id=?", (loan_id,)).fetchone()

    return jsonify(
        payment={
            "id": payment_id,
            "loanId": loan_id,
            "installment": installment["number"],
            "value": money_json(amount_due),
            "date": paid_date,
        },
        loan=loan_dict(updated_loan),
    ), 201


@app.delete("/api/payments/<pid>")
@require_login
def undo_payment(user, pid):

    with get_db() as db:
        payment=db.execute("SELECT * FROM payments WHERE id=?",(pid,)).fetchone()
        if not payment:return jsonify(error="Pagamento não encontrado."),404
        loan=db.execute("SELECT * FROM loans WHERE id=?",(payment["loan_id"],)).fetchone()
        inst=db.execute("SELECT * FROM installments WHERE loan_id=? AND number=?",(loan["id"],payment["installment"])).fetchone() if loan else None
        if not loan or not inst:return jsonify(error="Dados da parcela não encontrados."),404
        last=db.execute("SELECT * FROM payments WHERE loan_id=? ORDER BY installment DESC,date DESC,id DESC LIMIT 1",(loan["id"],)).fetchone()
        if not last or last["id"]!=pid:return jsonify(error="Somente o último pagamento do contrato pode ser desfeito."),400
        db.execute("DELETE FROM payments WHERE id=?",(pid,))
        status_inst="late" if inst["due"]<iso_today() else "pending"
        db.execute("UPDATE installments SET status=?,paid_at=NULL,payment_id=NULL WHERE id=?",(status_inst,inst["id"]))
        paid=max(0,int(loan["paid"])-1)
        db.execute("UPDATE loans SET paid=?,status='open' WHERE id=?",(paid,loan["id"]))
        audit(db,user["id"],"DELETE","payment",pid,f"Pagamento da parcela {payment['installment']} desfeito")
        updated=db.execute("SELECT * FROM loans WHERE id=?",(loan["id"],)).fetchone()
    return jsonify(ok=True,loan=loan_dict(updated))


def message_dict(row):
    return {
        "id": row["id"],
        "senderId": row["sender_id"],
        "senderName": row["sender_name"],
        "senderEmail": row["sender_email"],
        "recipientId": row["recipient_id"],
        "recipientName": row["recipient_name"],
        "recipientEmail": row["recipient_email"],
        "subject": row["subject"],
        "body": row["body"],
        "created": row["created"],
        "readAt": row["read_at"],
        "archivedSender": bool(row["archived_sender"]),
        "archivedRecipient": bool(row["archived_recipient"]),
        "deletedSender": bool(row["deleted_sender"]),
        "deletedRecipient": bool(row["deleted_recipient"]),
    }


@app.get("/api/messages")
@require_login
def get_messages(user):
    with get_db() as db:
        rows = db.execute(
            """SELECT m.*, s.name sender_name, s.email sender_email,
                      r.name recipient_name, r.email recipient_email
               FROM messages m
               JOIN users s ON s.id=m.sender_id
               JOIN users r ON r.id=m.recipient_id
              WHERE m.sender_id=? OR m.recipient_id=?
              ORDER BY m.created DESC""",
            (user["id"], user["id"]),
        ).fetchall()
        unread = db.execute("SELECT COUNT(*) FROM messages WHERE recipient_id=? AND read_at IS NULL AND deleted_recipient=0", (user["id"],)).fetchone()[0]
        drafts = db.execute("SELECT COUNT(*) FROM message_drafts WHERE owner_id=?", (user["id"],)).fetchone()[0]
        return jsonify(messages=[message_dict(r) for r in rows], unreadCount=unread, draftCount=drafts)


@app.delete("/api/messages/<mid>/purge")
@require_login
def purge_message(user,mid):
    with get_db() as db:
        row=db.execute("SELECT * FROM messages WHERE id=? AND (sender_id=? OR recipient_id=?)",(mid,user["id"],user["id"])).fetchone()
        if not row:return jsonify(error="Mensagem não encontrada."),404
        mine_deleted = row["deleted_sender"] if row["sender_id"]==user["id"] else row["deleted_recipient"]
        if not mine_deleted:return jsonify(error="Mova a mensagem para a lixeira antes de excluir definitivamente."),400
        other_deleted = row["deleted_recipient"] if row["sender_id"]==user["id"] else row["deleted_sender"]
        if other_deleted:
            db.execute("DELETE FROM messages WHERE id=?",(mid,))
        else:
            col="deleted_sender" if row["sender_id"]==user["id"] else "deleted_recipient"
            db.execute(f"UPDATE messages SET {col}=1 WHERE id=?",(mid,))
        audit(db,user["id"],"DELETE","message",mid,"Mensagem excluída definitivamente para este usuário")
    return jsonify(ok=True)


@app.get("/api/messages/drafts")
@require_login
def get_drafts(user):
    with get_db() as db:
        rows = db.execute(
            """SELECT d.*, r.name recipient_name, r.email recipient_email
               FROM message_drafts d LEFT JOIN users r ON r.id=d.recipient_id
              WHERE d.owner_id=? ORDER BY d.updated DESC""", (user["id"],)
        ).fetchall()
        drafts=[]
        for r in rows:
            drafts.append({"id":r["id"],"recipientId":r["recipient_id"],"recipientName":r["recipient_name"],"recipientEmail":r["recipient_email"],"subject":r["subject"],"body":r["body"],"created":r["created"],"updated":r["updated"]})
        return jsonify(drafts=drafts)


@app.post("/api/messages")
@require_login
def send_message(user):
    d=request.get_json(silent=True) or {}
    recipient_id=str(d.get("recipientId", "")).strip()
    subject=str(d.get("subject", "")).strip()
    body=str(d.get("body", "")).strip()
    if not recipient_id or not subject or not body:
        return jsonify(error="Informe destinatário, assunto e mensagem."),400
    if len(subject)>120 or len(body)>5000:
        return jsonify(error="Assunto ou mensagem excede o limite permitido."),400
    if recipient_id==user["id"]:
        return jsonify(error="Escolha outro usuário como destinatário."),400
    with get_db() as db:
        recipient=db.execute("SELECT * FROM users WHERE id=? AND active=1",(recipient_id,)).fetchone()
        if not recipient:return jsonify(error="Destinatário não encontrado ou desativado."),404
        mid=uid("msg"); created=local_now().isoformat(timespec="seconds")
        db.execute("INSERT INTO messages(id,sender_id,recipient_id,subject,body,created,read_at,archived_sender,archived_recipient,deleted_sender,deleted_recipient) VALUES(?,?,?,?,?,?,NULL,0,0,0,0)",(mid,user["id"],recipient_id,subject,body,created))
        audit(db,user["id"],"CREATE","message",mid,f"Mensagem interna enviada para {recipient['email']}")
    return jsonify(ok=True,id=mid),201


@app.post("/api/messages/drafts")
@require_login
def save_draft(user):
    d=request.get_json(silent=True) or {}
    draft_id=str(d.get("id") or uid("draft")); recipient_id=str(d.get("recipientId") or "").strip() or None
    subject=str(d.get("subject", ""))[:120]; body=str(d.get("body", ""))[:5000]; now=local_now().isoformat(timespec="seconds")
    with get_db() as db:
        if recipient_id and not db.execute("SELECT 1 FROM users WHERE id=? AND active=1",(recipient_id,)).fetchone():
            return jsonify(error="Destinatário inválido."),400
        exists=db.execute("SELECT 1 FROM message_drafts WHERE id=? AND owner_id=?",(draft_id,user["id"])).fetchone()
        if exists:
            db.execute("UPDATE message_drafts SET recipient_id=?,subject=?,body=?,updated=? WHERE id=? AND owner_id=?",(recipient_id,subject,body,now,draft_id,user["id"]))
        else:
            db.execute("INSERT INTO message_drafts(id,owner_id,recipient_id,subject,body,created,updated) VALUES(?,?,?,?,?,?,?)",(draft_id,user["id"],recipient_id,subject,body,now,now))
    return jsonify(ok=True,id=draft_id),201


@app.delete("/api/messages/drafts/<draft_id>")
@require_login
def delete_draft(user,draft_id):
    with get_db() as db:
        if db.execute("DELETE FROM message_drafts WHERE id=? AND owner_id=?",(draft_id,user["id"])).rowcount==0:
            return jsonify(error="Rascunho não encontrado."),404
    return jsonify(ok=True)


@app.post("/api/messages/drafts/<draft_id>/send")
@require_login
def send_draft(user,draft_id):
    with get_db() as db:
        d=db.execute("SELECT * FROM message_drafts WHERE id=? AND owner_id=?",(draft_id,user["id"])).fetchone()
        if not d:return jsonify(error="Rascunho não encontrado."),404
        recipient_id=d["recipient_id"]; subject=d["subject"].strip(); body=d["body"].strip()
        if not recipient_id or not subject or not body:return jsonify(error="Complete destinatário, assunto e mensagem antes de enviar."),400
        recipient=db.execute("SELECT * FROM users WHERE id=? AND active=1",(recipient_id,)).fetchone()
        if not recipient:return jsonify(error="Destinatário não encontrado ou desativado."),404
        mid=uid("msg"); created=local_now().isoformat(timespec="seconds")
        db.execute("INSERT INTO messages(id,sender_id,recipient_id,subject,body,created,read_at,archived_sender,archived_recipient,deleted_sender,deleted_recipient) VALUES(?,?,?,?,?,?,NULL,0,0,0,0)",(mid,user["id"],recipient_id,subject,body,created))
        db.execute("DELETE FROM message_drafts WHERE id=? AND owner_id=?",(draft_id,user["id"]))
        audit(db,user["id"],"CREATE","message",mid,f"Rascunho enviado para {recipient['email']}")
    return jsonify(ok=True,id=mid),201


@app.patch("/api/messages/<mid>/read")
@require_login
def mark_message_read(user,mid):
    with get_db() as db:
        row=db.execute("SELECT * FROM messages WHERE id=? AND recipient_id=? AND deleted_recipient=0",(mid,user["id"])).fetchone()
        if not row:return jsonify(error="Mensagem não encontrada."),404
        read_at=local_now().isoformat(timespec="seconds")
        db.execute("UPDATE messages SET read_at=? WHERE id=?",(read_at,mid))
    return jsonify(ok=True,readAt=read_at)


@app.patch("/api/messages/<mid>/archive")
@require_login
def archive_message(user,mid):
    with get_db() as db:
        row=db.execute("SELECT * FROM messages WHERE id=? AND (sender_id=? OR recipient_id=?)",(mid,user["id"],user["id"])).fetchone()
        if not row:return jsonify(error="Mensagem não encontrada."),404
        col="archived_sender" if row["sender_id"]==user["id"] else "archived_recipient"
        db.execute(f"UPDATE messages SET {col}=1 WHERE id=?",(mid,))
        audit(db,user["id"],"UPDATE","message",mid,"Mensagem arquivada")
    return jsonify(ok=True)


@app.patch("/api/messages/<mid>/restore")
@require_login
def restore_message(user,mid):
    with get_db() as db:
        row=db.execute("SELECT * FROM messages WHERE id=? AND (sender_id=? OR recipient_id=?)",(mid,user["id"],user["id"])).fetchone()
        if not row:return jsonify(error="Mensagem não encontrada."),404
        col="archived_sender" if row["sender_id"]==user["id"] else "archived_recipient"
        db.execute(f"UPDATE messages SET {col}=0 WHERE id=?",(mid,))
    return jsonify(ok=True)


@app.delete("/api/messages/<mid>")
@require_login
def delete_message(user,mid):
    with get_db() as db:
        row=db.execute("SELECT * FROM messages WHERE id=? AND (sender_id=? OR recipient_id=?)",(mid,user["id"],user["id"])).fetchone()
        if not row:return jsonify(error="Mensagem não encontrada."),404
        if row["sender_id"]==user["id"]:
            db.execute("UPDATE messages SET deleted_sender=1, archived_sender=0 WHERE id=?",(mid,))
        else:
            db.execute("UPDATE messages SET deleted_recipient=1, archived_recipient=0 WHERE id=?",(mid,))
        audit(db,user["id"],"DELETE","message",mid,"Mensagem movida para lixeira")
    return jsonify(ok=True)


@app.get("/")
def index():
    return send_from_directory(BASE_DIR, "index.html")


@app.get("/<path:path>")
def static_files(path):
    if path.startswith("api/"):
        return jsonify(error="Rota não encontrada."),404
    file_path=BASE_DIR/path
    if file_path.is_file():
        return send_from_directory(BASE_DIR,path)
    return send_from_directory(BASE_DIR,"index.html")


init_db()

if __name__ == "__main__":
    print(f"AgiProz rodando em http://127.0.0.1:5500")
    app.run(host="127.0.0.1", port=5500, debug=False)
