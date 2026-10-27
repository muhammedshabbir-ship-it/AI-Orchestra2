import pandas as pd
import streamlit as st

import ui
from core import agents, db, ledger, security
from core.money import fmt, to_cents

ui.guard(admin=True)
st.title("Security and Settings")
me = ui.username()
is_admin = ui.user()["role"] == "admin"

st.subheader("Audit log integrity")
ok, bad = security.verify_audit_chain()
_ = st.success("Audit chain verified: no entries have been edited or removed.") if ok else st.error(f"Audit chain BROKEN at entry #{bad}. Records were changed or deleted.")

st.subheader("Mode")
m = ledger.mode()
st.write(f"Current mode: **{m}**. TEST and LIVE keep completely separate books.")
if is_admin:
    if m == "TEST":
        st.caption("Before going LIVE: use your own bank account, fund it, then record each real deposit here and verify it against your bank statement. Your first live payment should be a small one.")
        typed = st.text_input("Type LIVE to switch to LIVE mode")
        if ui.password_ok("pwmode") and st.button("Switch to LIVE") and typed == "LIVE":
            db.set_setting("mode", "LIVE"); security.audit(me, "MODE_CHANGED", "TEST -> LIVE"); st.rerun()
    elif st.button("Switch back to TEST"):
        db.set_setting("mode", "TEST"); security.audit(me, "MODE_CHANGED", "LIVE -> TEST"); st.rerun()

st.subheader("Release limits (Security agent rules)")
with st.form("limits"):
    daily = st.text_input("Daily release limit AUD (0 = no limit)", f"{int(db.get_setting('daily_limit_cents', '0')) // 100}")
    large = st.text_input("Large-release confirmation at or above AUD", f"{int(db.get_setting('large_release_cents', '10000000')) // 100}")
    dual = st.text_input("Dual control: a second admin must approve at or above AUD (0 = off)", f"{int(db.get_setting('dual_control_cents', '0')) // 100}")
    if st.form_submit_button("Save limits") and is_admin:
        try:
            db.set_setting("daily_limit_cents", to_cents(daily)); db.set_setting("large_release_cents", to_cents(large)); db.set_setting("dual_control_cents", to_cents(dual))
            security.audit(me, "LIMITS_CHANGED", f"daily={daily} large={large} dual={dual}"); st.success("Saved.")
        except ValueError as e:
            st.error(str(e))

st.subheader("Users")
ui.show_df(pd.DataFrame(db.q("SELECT username, role FROM users")), hide_index=True)
if is_admin:
    with st.form("newuser"):
        u = st.text_input("New username"); p = st.text_input("Password (10+ chars)", type="password"); r = st.selectbox("Role", ["admin", "viewer"])
        if st.form_submit_button("Add user"):
            try:
                security.create_user(u, p, r); st.success("User added."); st.rerun()
            except Exception as e:
                st.error(str(e))

st.subheader("AI keys")
st.caption("Paste a key and press Save. It is stored in a file on this computer (data/secrets.env), never in the database or audit log, and is shown masked. Use a key with a spend limit and keep the data folder private. You only need ONE of the two AI keys.")
import os
from core import secrets

with st.expander("How to create an OpenRouter API key (one key, many AI models)"):
    st.markdown("""
1. Go to **openrouter.ai** and sign in (Google, GitHub or email).
2. Open **Credits** and add credit (for example USD 10). Paid models need credit.
3. Open **Keys** (openrouter.ai/keys) and press **Create Key**.
4. Give it a name such as *AI Orchestra*, and set a **credit limit** so it can never overspend.
5. Copy the key now (it starts with `sk-or-`). It is shown only once.
6. Paste it below and press **Save key**, then **Test key**.
7. Choose the model below. Browse model names at openrouter.ai/models and copy the model ID (for example `anthropic/claude-sonnet-4.5`). Pick one that supports tools.
""")
with st.expander("How to create an Anthropic (Claude) API key"):
    st.markdown("""
1. Go to **console.anthropic.com** and sign in.
2. Open **Billing** and add credit.
3. Open **API Keys** and press **Create Key**. Name it *AI Orchestra*.
4. Copy the key (it starts with `sk-ant-`). It is shown only once.
5. Paste it below and press **Save key**, then **Test key**.
""")

KEYS = [("OPENROUTER_API_KEY", "OpenRouter API key", "Starts with sk-or-. Create at openrouter.ai/keys."),
        ("ANTHROPIC_API_KEY", "Anthropic (Claude) API key", "Starts with sk-ant-. Create at console.anthropic.com > API Keys."),
        ("FIGMA_TOKEN", "Figma personal access token (optional)", "Figma > Settings > Security > Personal access tokens.")]
for kname, label, hint in KEYS:
    cur = os.environ.get(kname)
    st.markdown(f"**{label}**: " + (f"✅ set (`{secrets.mask(cur)}`, from {secrets.source(kname)})" if cur else "❌ not set"))
    if is_admin:
        with st.form(f"form_{kname}", clear_on_submit=True):
            val = st.text_input(f"Paste {label}", type="password", help=hint, key=f"in_{kname}")
            if st.form_submit_button("Save key"):
                try:
                    secrets.save(kname, val)
                    security.audit(me, "API_KEY_SAVED", kname)
                    st.success("Saved. It is active now."); st.rerun()
                except ValueError as e:
                    st.error(str(e))
        c1, c2 = st.columns(2)
        if kname in ("ANTHROPIC_API_KEY", "OPENROUTER_API_KEY") and cur and c1.button("Test key", key=f"test_{kname}"):
            with st.spinner("Checking..."):
                ok, msg = secrets.check_anthropic() if kname == "ANTHROPIC_API_KEY" else secrets.check_openrouter()
            (st.success if ok else st.error)(msg)
        if cur and c2.button("Remove key", key=f"rm_{kname}"):
            secrets.delete(kname); security.audit(me, "API_KEY_REMOVED", kname); st.rerun()

st.markdown("**Which AI service should the agents use?**")
if is_admin:
    with st.form("llm"):
        opts = ["auto", "openrouter", "anthropic"]
        pv = st.selectbox("Service", opts, index=opts.index(db.get_setting("llm_provider", "auto")),
                          help="Auto uses Anthropic if its key is set, otherwise OpenRouter.")
        om = st.text_input("OpenRouter model ID", db.get_setting("openrouter_model", agents.DEFAULT_OR_MODEL),
                           help="Copy from openrouter.ai/models. Must support tool calling.")
        if st.form_submit_button("Save AI settings"):
            db.set_setting("llm_provider", pv); db.set_setting("openrouter_model", om.strip() or agents.DEFAULT_OR_MODEL)
            security.audit(me, "LLM_SETTINGS", f"{pv} {om}"); st.success("Saved.")
st.write(f"Active service now: **{agents.provider() or 'none (add a key)'}** · Anthropic model `{agents.MODEL}` · OpenRouter model `{db.get_setting('openrouter_model', agents.DEFAULT_OR_MODEL)}`")

st.subheader("Audit log")
ui.show_df(pd.DataFrame([{**r, "ts": ui.ts(r["ts"])} for r in db.q("SELECT ts,actor,action,detail FROM audit ORDER BY id DESC LIMIT 300")]), hide_index=True)
