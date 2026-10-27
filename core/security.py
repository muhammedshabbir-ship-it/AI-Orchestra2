"""Users, password hashing, tamper-evident audit log and payee/limit checks (the Security agent's rules)."""
import hashlib
import hmac
import os
import re
import time

from . import db
from .money import fmt


def _hash(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 240_000).hex()


def create_user(username: str, password: str, role: str = "admin"):
    if len(password) < 10:
        raise ValueError("Password must be at least 10 characters.")
    salt = os.urandom(16).hex()
    db.x("INSERT INTO users(username,salt,pw_hash,role) VALUES(?,?,?,?)", (username.strip(), salt, _hash(password, salt), role))
    audit(username, "USER_CREATED", f"role={role}")


MAX_FAILS, LOCK_SECONDS = 5, 900


def is_locked(username: str) -> bool:
    """5 failed sign-ins in 15 minutes (since the last good sign-in) locks that username for the rest of the window."""
    name = username.strip()
    ok = db.q1("SELECT COALESCE(MAX(ts),0) t FROM audit WHERE actor=? AND action='LOGIN'", (name,))["t"]
    since = max(ok, time.time() - LOCK_SECONDS)
    n = db.q1("SELECT COUNT(*) n FROM audit WHERE actor=? AND action='LOGIN_FAILED' AND ts>?", (name, since))["n"]
    return n >= MAX_FAILS


def verify_user(username: str, password: str):
    if is_locked(username):
        return None
    u = db.q1("SELECT * FROM users WHERE username=?", (username.strip(),))
    if not u:
        return None
    if hmac.compare_digest(u["pw_hash"], _hash(password, u["salt"])):
        return u
    audit(username, "LOGIN_FAILED", "")
    return None


def has_users() -> bool:
    return db.q1("SELECT COUNT(*) n FROM users")["n"] > 0


def audit(actor: str, action: str, detail: str = ""):
    last = db.q1("SELECT hash FROM audit ORDER BY id DESC LIMIT 1")
    prev = last["hash"] if last else "GENESIS"
    ts = time.time()
    h = hashlib.sha256(f"{prev}|{ts}|{actor}|{action}|{detail}".encode()).hexdigest()
    db.x("INSERT INTO audit(ts,actor,action,detail,prev_hash,hash) VALUES(?,?,?,?,?,?)", (ts, actor, action, detail, prev, h))


def verify_audit_chain():
    """Return (ok, broken_at_id). Any edited or deleted row breaks the chain."""
    prev = "GENESIS"
    for r in db.q("SELECT * FROM audit ORDER BY id"):
        h = hashlib.sha256(f"{prev}|{r['ts']}|{r['actor']}|{r['action']}|{r['detail']}".encode()).hexdigest()
        if r["prev_hash"] != prev or r["hash"] != h:
            return False, r["id"]
        prev = r["hash"]
    return True, None


# ---------- payee validation ----------
def norm_bsb(bsb: str) -> str:
    d = re.sub(r"\D", "", bsb or "")
    if len(d) != 6:
        raise ValueError("BSB must be 6 digits.")
    return f"{d[:3]}-{d[3:]}"


def norm_account(acc: str) -> str:
    d = re.sub(r"\D", "", acc or "")
    if not 6 <= len(d) <= 9:
        raise ValueError("Account number must be 6 to 9 digits.")
    return d


def norm_payid(pid: str) -> str:
    p = (pid or "").strip()
    if re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", p):
        return p.lower()
    d = re.sub(r"[\s\-()]", "", p)
    if re.fullmatch(r"(\+?61|0)4\d{8}", d):  # mobile
        return d
    if re.fullmatch(r"\d{11}", d):  # ABN
        return d
    raise ValueError("PayID must be an email, an Australian mobile number or an 11-digit ABN.")


# ---------- release checks (Security agent rules) ----------
def check_release(payee_name, bsb, account, payid, amount_cents, available_cents, mode):
    """Returns (errors, warnings). Errors block the release, warnings need explicit confirmation."""
    errors, warnings = [], []
    if not payee_name or len(payee_name.strip()) < 2:
        errors.append("Payee full name is required.")
    if amount_cents <= 0:
        errors.append("Amount must be greater than zero.")
    if amount_cents > available_cents:
        errors.append(f"Amount exceeds available verified balance ({fmt(available_cents)}).")
    has_bank = bool(bsb and account)
    if not has_bank and not payid:
        errors.append("Enter BSB and account number, or a PayID.")
    if has_bank:
        try:
            norm_bsb(bsb); norm_account(account)
        except ValueError as e:
            errors.append(str(e))
    if payid:
        try:
            norm_payid(payid)
        except ValueError as e:
            errors.append(str(e))
    daily = int(db.get_setting("daily_limit_cents", "0"))
    if daily > 0:
        since = time.time() - 86400
        used = db.q1("SELECT COALESCE(SUM(amount_cents),0) s FROM releases WHERE mode=? AND status IN('APPROVED','EXPORTED','SETTLED') AND approved_ts>?", (mode, since))["s"]
        if used + amount_cents > daily:
            errors.append(f"Daily release limit {fmt(daily)} would be exceeded (already {fmt(used)} in 24h).")
    if has_bank and not errors:
        try:
            known = db.q1("SELECT 1 FROM payees WHERE bsb=? AND account=?", (norm_bsb(bsb), norm_account(account)))
        except ValueError:
            known = True
        if not known:
            warnings.append("New payee: this BSB and account has not been paid before. Check the details with the payee.")
    large = int(db.get_setting("large_release_cents", "10000000"))
    if amount_cents >= large:
        warnings.append(f"Large release (at or above {fmt(large)}). Type the amount to confirm.")
    dup = db.q1("SELECT 1 FROM releases WHERE amount_cents=? AND payee_name=? AND ts>? AND status!='CANCELLED'", (amount_cents, payee_name.strip(), time.time() - 3600))
    if dup:
        warnings.append("An identical release to this payee was created in the last hour.")
    return errors, warnings
