import pandas as pd
import streamlit as st

import ui
from core import ledger
from core.money import fmt

ui.guard()
ui.mode_banner()
st.title("Accounting")
rows = ledger.ledger_rows(limit=5000)
if not rows:
    st.info("No ledger entries yet. Record a deposit on the Vault Terminal page.")
    st.stop()
df = pd.DataFrame(rows)
df["date"] = pd.to_datetime(df["ts"], unit="s")
df["AUD"] = df["amount_cents"] / 100
df["month"] = df["date"].dt.strftime("%Y-%m")

st.subheader("Monthly summary")
piv = df.pivot_table(index="month", columns="kind", values="AUD", aggfunc="sum", fill_value=0)
piv["Net movement"] = piv.sum(axis=1)
ui.show_df(piv.style.format("{:,.2f}"))
st.bar_chart(piv.drop(columns=["Net movement"]))

c = st.columns(3)
c[0].metric("Total deposits", fmt(int(df[df.kind == "DEPOSIT"].amount_cents.sum())))
c[1].metric("Total released", fmt(int(-df[df.kind == "RELEASE"].amount_cents.sum())))
c[2].metric("Reversals", fmt(int(df[df.kind == "REVERSAL"].amount_cents.sum())))

st.subheader("Journal")
view = df[["id", "date", "kind", "AUD", "ref", "release_id", "memo", "verified"]].rename(columns={"ref": "reference"})
ui.show_df(view, hide_index=True)
st.download_button("Download journal (CSV)", view.to_csv(index=False), file_name="vault_journal.csv", mime="text/csv")

st.subheader("Release register")
rel = pd.DataFrame(ledger.releases())
if not rel.empty:
    rel["AUD"] = rel["amount_cents"] / 100
    rel = rel[["id", "status", "payee_name", "bsb", "account", "payid", "AUD", "reference", "channel", "batch_id"]]
    ui.show_df(rel, hide_index=True)
    st.download_button("Download releases (CSV)", rel.to_csv(index=False), file_name="vault_releases.csv", mime="text/csv")
