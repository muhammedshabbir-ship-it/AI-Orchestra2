# AI Orchestra Platform (Streamlit)

A personal agent system: 19 agents, the Vault E-Terminal (AUD wallet with manual transfers), a gold register, accounting, build tools and 6/12/24-hour autonomous jobs. Built for your own use with your own money, not for customers or third parties.

## Run
Windows: double-click `run_windows.bat`. Other systems: `pip install -r requirements.txt` then `streamlit run app.py`.
Add an AI key in the app: **Security and Settings > AI keys**. You need ONE of: an **OpenRouter** key (sk-or-..., many models, one bill) or an **Anthropic** key (sk-ant-...). Step-by-step instructions for creating each key are on that page.

**Create an OpenRouter key:** openrouter.ai > sign in > Credits (add credit) > Keys > Create Key > name it, set a credit limit > copy it (shown once) > paste in the app > Save key > Test key. Then choose a model ID from openrouter.ai/models on the same page.
Phone / Play Store / hosting: see `PLAYSTORE_GUIDE.md`.
First launch asks you to create the admin account. Data lives in `data/orchestra.db` (back it up).

## Quick start in the Vault E-Terminal
1. **Set your reserve volume** (the most the vault may hold, e.g. 1,000,000,000). Commas are fine.
2. **Record the funds you hold** on the Deposits tab. In live mode tick "This money is already in my bank account".
3. **Manual release** to a PayID, or BSB + account number + account name. Approve it, then export the bank file or send the PayID from your bank app.

## How real money works here
* The vault **records and controls** money. It never creates it. Balance only comes from deposits you record
  with a bank/provider reference. The **reserve ceiling** starts at AUD 0.00. You set it (for example 1,000,000,000) before recording deposits. It is a cap.
* **TEST mode** (default) has separate books and is labelled everywhere. **LIVE mode** counts a deposit as
  available only after you verify it against your bank statement.
* Release = draft -> you re-enter your password to approve (funds committed in ledger) -> **export** -> you mark paid
  after the bank confirms. Every transfer carries the reference **Vault Payment Plt**.
* **BSB + account + name:** the app builds a standard **ABA direct-entry file**. Upload it in your bank's business
  internet banking and the bank moves the money. **PayID:** listed for you to send from your bank app/provider.
* No card numbers or CVCs are collected or stored.
* Agents can read the vault and **draft** releases. No agent tool can approve, export or send money.

## Go-live checklist
1. Use your own bank account that supports bulk direct credit (ABA files) in online banking, and get your APCA user ID from the bank. Ask the bank to raise your daily online payment limit if needed.
2. Security and Settings: set limits and dual control. Vault Terminal > Export: enter your bank file details.
3. Fund the reserve account. Switch to LIVE. Record each deposit, then mark it verified against the statement.
4. Do a small first release, upload its ABA file, confirm the bank result, then mark paid.

## Gold
Add bars only if a custodian holds them (custodian + certificate reference required). Value = fine oz x USD/oz,
converted at USD/AUD. "Fetch live prices" uses gold-api.com and frankfurter.app; if unreachable, enter prices manually.

## Limits to know
* Autonomous jobs run in a background thread of the Streamlit server: keep the server running (VPS/always-on PC).
* Memory is a searchable database table (keyword search), not a vector database.
* Direct bank-API payouts are not built in (they need your bank's or provider's own API access). ABA file export and PayID instructions are the supported routes.
* Back up `data/`, put the app behind HTTPS (e.g. a reverse proxy) before exposing it beyond your own network.

## Tests
`python -m pytest tests` (26 tests: ledger, limits, ABA format, audit chain, gold, agents, Streamlit pages).
