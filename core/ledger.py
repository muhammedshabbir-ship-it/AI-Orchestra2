"""Vault ledger and the 'Vault Payment Plt' release workflow.

Rules that keep the numbers honest:
* The ledger only ever holds money that was recorded as a deposit. Nothing creates balance on its own.
* The reserve ceiling is a cap on the balance you allow the vault to hold. It does not add money.
* In LIVE mode a deposit counts as available only after you mark it verified against your bank statement.
* TEST mode keeps separate books and is always labelled, so test figures can never be mistaken for real funds.
"""
import time

from . import db, security
from .money import fmt

REFERENCE = "Vault Payment Plt"
WALLET = "VAULT"
DEFAULT_CEILING = 0  # starts at AUD 0.00. You set the ceiling (for example 1,000,000,000) before recording deposits


def mode() -> str:
    return db.get_setting("mode", "TEST")


def ceiling_cents() -> int:
    return int(db.get_setting("ceiling_cents", str(DEFAULT_CEILING)))


def set_ceiling(cents: int, actor: str):
    if cents < 0:
        raise ValueError("Ceiling cannot be negative.")
    old = ceiling_cents()
    db.set_setting("ceiling_cents", cents)
    security.audit(actor, "CEILING_CHANGED", f"{old} -> {cents}")


def balance_cents(m=None) -> int:
    m = m or mode()
    return db.q1("SELECT COALESCE(SUM(amount_cents),0) s FROM ledger WHERE mode=? AND wallet=?", (m, WALLET))["s"]


def available_cents(m=None) -> int:
    """Verified credits plus all debits (unverified deposits cannot be released)."""
    m = m or mode()
    return db.q1(
        "SELECT COALESCE(SUM(amount_cents),0) s FROM ledger WHERE mode=? AND wallet=? AND (amount_cents<0 OR verified=1)",
        (m, WALLET))["s"]


def unverified_cents(m=None) -> int:
    return balance_cents(m) - available_cents(m)


def record_deposit(amount_cents: int, source_ref: str, memo: str, actor: str, verified: bool = None):
    """Record real money that has arrived in the reserve account. source_ref is the bank/provider reference."""
    if amount_cents <= 0:
        raise ValueError("Deposit must be greater than zero.")
    m = mode()
    if ceiling_cents() <= 0:
        raise ValueError("Set the reserve ceiling first (Vault Terminal > Reserve ceiling tab).")
    if not source_ref.strip():
        raise ValueError("A bank or provider reference is required for every deposit.")
    if balance_cents(m) + amount_cents > ceiling_cents():
        raise ValueError(f"Deposit would take the vault above the reserve ceiling of {fmt(ceiling_cents())}. Raise the ceiling first.")
    if verified is None:
        verified = (m == "TEST")
    lid = db.x(
        "INSERT INTO ledger(ts,mode,wallet,kind,amount_cents,ref,memo,verified) VALUES(?,?,?,?,?,?,?,?)",
        (time.time(), m, WALLET, "DEPOSIT", amount_cents, source_ref.strip(), memo, 1 if verified else 0))
    security.audit(actor, "DEPOSIT_RECORDED", f"{m} {fmt(amount_cents)} ref={source_ref} verified={verified}")
    return lid


def verify_deposit(ledger_id: int, actor: str):
    row = db.q1("SELECT * FROM ledger WHERE id=? AND kind='DEPOSIT'", (ledger_id,))
    if not row:
        raise ValueError("Deposit not found.")
    db.x("UPDATE ledger SET verified=1 WHERE id=?", (ledger_id,))
    security.audit(actor, "DEPOSIT_VERIFIED", f"id={ledger_id} {fmt(row['amount_cents'])}")


# ---------- releases ----------
def create_release(payee_name, bsb, account, payid, amount_cents, memo, actor, confirmed_warnings=False):
    m = mode()
    errors, warnings = security.check_release(payee_name, bsb, account, payid, amount_cents, available_cents(m), m)
    if errors:
        raise ValueError(" ".join(errors))
    if warnings and not confirmed_warnings:
        raise ValueError("CONFIRM: " + " ".join(warnings))
    b = security.norm_bsb(bsb) if bsb else ""
    a = security.norm_account(account) if account else ""
    p = security.norm_payid(payid) if payid else ""
    rid = db.x(
        "INSERT INTO releases(ts,mode,status,payee_name,bsb,account,payid,amount_cents,reference,memo,created_by) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
        (time.time(), m, "DRAFT", payee_name.strip(), b, a, p, amount_cents, REFERENCE, memo, actor))
    security.audit(actor, "RELEASE_DRAFTED", f"#{rid} {m} {fmt(amount_cents)} to {payee_name.strip()}")
    return rid


def approve_release(release_id: int, actor: str):
    """Commit funds. Caller must already have re-verified the approver's password."""
    r = db.q1("SELECT * FROM releases WHERE id=?", (release_id,))
    if not r or r["status"] != "DRAFT":
        raise ValueError("Only a draft release can be approved.")
    m = r["mode"]
    if m != mode():
        raise ValueError(f"This release was drafted in {m} mode. Switch back to {m} mode or cancel it.")
    threshold = int(db.get_setting("dual_control_cents", "0"))
    admins = db.q1("SELECT COUNT(*) n FROM users WHERE role='admin'")["n"]
    if threshold > 0 and r["amount_cents"] >= threshold and admins > 1 and r["created_by"] == actor:
        raise ValueError("Dual control: a different admin must approve releases at or above the dual-control amount.")
    if r["amount_cents"] > available_cents(m):
        raise ValueError("Insufficient available verified balance.")
    ts = time.time()
    db.x("INSERT INTO ledger(ts,mode,wallet,kind,amount_cents,ref,release_id,memo,verified) VALUES(?,?,?,?,?,?,?,?,1)",
         (ts, m, WALLET, "RELEASE", -r["amount_cents"], REFERENCE, release_id, f"{REFERENCE}: {r['payee_name']}"))
    db.x("UPDATE releases SET status='APPROVED', approved_by=?, approved_ts=? WHERE id=?", (actor, ts, release_id))
    if r["bsb"] and r["account"]:
        if not db.q1("SELECT 1 FROM payees WHERE bsb=? AND account=?", (r["bsb"], r["account"])):
            db.x("INSERT INTO payees(name,bsb,account,payid,first_seen) VALUES(?,?,?,?,?)", (r["payee_name"], r["bsb"], r["account"], r["payid"], ts))
    security.audit(actor, "RELEASE_APPROVED", f"#{release_id} {m} {fmt(r['amount_cents'])} to {r['payee_name']}")


def mark_exported(release_ids, channel: str, batch_id: str, actor: str):
    for rid in release_ids:
        db.x("UPDATE releases SET status='EXPORTED', channel=?, batch_id=? WHERE id=? AND status='APPROVED'", (channel, batch_id, rid))
    security.audit(actor, "RELEASES_EXPORTED", f"{channel} batch={batch_id} ids={list(release_ids)}")


def mark_settled(release_id: int, actor: str):
    db.x("UPDATE releases SET status='SETTLED', settled_ts=? WHERE id=? AND status IN('APPROVED','EXPORTED')", (time.time(), release_id))
    security.audit(actor, "RELEASE_SETTLED", f"#{release_id}")


def cancel_release(release_id: int, actor: str):
    r = db.q1("SELECT * FROM releases WHERE id=?", (release_id,))
    if not r or r["status"] in ("SETTLED", "CANCELLED"):
        raise ValueError("This release cannot be cancelled.")
    if r["status"] in ("APPROVED", "EXPORTED"):
        db.x("INSERT INTO ledger(ts,mode,wallet,kind,amount_cents,ref,release_id,memo,verified) VALUES(?,?,?,?,?,?,?,?,1)",
             (time.time(), r["mode"], WALLET, "REVERSAL", r["amount_cents"], REFERENCE, release_id, f"Reversal of release #{release_id}"))
    db.x("UPDATE releases SET status='CANCELLED' WHERE id=?", (release_id,))
    security.audit(actor, "RELEASE_CANCELLED", f"#{release_id} was {r['status']}")


def releases(status=None, m=None):
    m = m or mode()
    if status:
        return db.q("SELECT * FROM releases WHERE mode=? AND status=? ORDER BY id DESC", (m, status))
    return db.q("SELECT * FROM releases WHERE mode=? ORDER BY id DESC", (m,))


def ledger_rows(m=None, limit=500):
    m = m or mode()
    return db.q("SELECT * FROM ledger WHERE mode=? ORDER BY id DESC LIMIT ?", (m, limit))


def summary() -> dict:
    m = mode()
    return {
        "mode": m,
        "ceiling_cents": ceiling_cents(),
        "balance_cents": balance_cents(m),
        "available_cents": available_cents(m),
        "unverified_cents": unverified_cents(m),
        "pending_drafts": len(releases("DRAFT", m)),
        "headroom_cents": max(0, ceiling_cents() - balance_cents(m)),
    }


STEPS = ["Drafted", "Approved (funds committed)", "Sent to bank", "Paid"]


def step_index(status: str) -> int:
    return {"DRAFT": 0, "APPROVED": 1, "EXPORTED": 2, "SETTLED": 3}.get(status, -1)


def action_queue() -> dict:
    """Everything waiting on you, in the order a transfer moves: approve -> send -> confirm paid, plus deposits to verify."""
    m = mode()
    return {
        "approve": releases("DRAFT", m),
        "send": releases("APPROVED", m),
        "confirm": releases("EXPORTED", m),
        "verify": [r for r in ledger_rows(m) if r["kind"] == "DEPOSIT" and not r["verified"]],
    }
