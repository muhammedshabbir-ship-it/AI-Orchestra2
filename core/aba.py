"""ABA (Cemtext / Direct Entry) file generator.

This is the standard Australian bulk direct-credit file. You upload it in your own bank's business
internet banking (or your payment provider's bulk-pay tool); the bank moves the money from your account.
Each record is exactly 120 characters.
"""
import datetime as dt

from . import security


def _fit(s, n, right=False, pad=" "):
    s = str(s)[:n]
    return s.rjust(n, pad) if right else s.ljust(n, pad)


def _clean(s):
    return "".join(ch if ch.isalnum() or ch in " -&./'" else " " for ch in (s or "")).upper()


def build_aba(releases, *, bank_abbrev, user_name, apca_id, description, own_bsb, own_account, remitter, balancing=True, when=None):
    when = when or dt.date.today()
    own_bsb = security.norm_bsb(own_bsb)
    own_account = security.norm_account(own_account)
    items = [r for r in releases if r["bsb"] and r["account"]]
    if not items:
        raise ValueError("No bank-account releases to export (PayID payments cannot go in an ABA file).")
    lines = []
    head = ("0" + " " * 17 + "01" + _fit(bank_abbrev.upper(), 3) + " " * 7 + _fit(_clean(user_name), 26)
            + _fit(apca_id, 6, right=True, pad="0") + _fit(_clean(description), 12) + when.strftime("%d%m%y") + " " * 40)
    lines.append(head)
    credit_total = 0
    for r in items:
        cents = int(r["amount_cents"])
        credit_total += cents
        lines.append("1" + _fit(r["bsb"], 7) + _fit(r["account"], 9, right=True) + " " + "53" + _fit(cents, 10, right=True, pad="0")
                     + _fit(_clean(r["payee_name"]), 32) + _fit(_clean(r["reference"]), 18) + _fit(own_bsb, 7)
                     + _fit(own_account, 9, right=True) + _fit(_clean(remitter), 16) + "0" * 8)
    debit_total = 0
    if balancing:
        debit_total = credit_total
        lines.append("1" + _fit(own_bsb, 7) + _fit(own_account, 9, right=True) + " " + "13" + _fit(debit_total, 10, right=True, pad="0")
                     + _fit("VAULT PAYMENT PLT", 32) + _fit("BALANCING", 18) + _fit(own_bsb, 7) + _fit(own_account, 9, right=True)
                     + _fit(_clean(remitter), 16) + "0" * 8)
    count = len(lines) - 1
    lines.append("7" + "999-999" + " " * 12 + _fit(abs(credit_total - debit_total), 10, right=True, pad="0")
                 + _fit(credit_total, 10, right=True, pad="0") + _fit(debit_total, 10, right=True, pad="0") + " " * 24
                 + _fit(count, 6, right=True, pad="0") + " " * 40)
    for ln in lines:
        assert len(ln) == 120, f"ABA record is {len(ln)} chars: {ln!r}"
    return "\r\n".join(lines) + "\r\n"
