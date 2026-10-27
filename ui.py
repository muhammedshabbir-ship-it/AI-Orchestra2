import datetime as dt

import streamlit as st

from core import ledger, security


def user():
    return st.session_state.get("user")


def username():
    u = user()
    return u["username"] if u else "anonymous"


def ts(t):
    return dt.datetime.fromtimestamp(t).strftime("%Y-%m-%d %H:%M") if t else ""


def mode_badge_html() -> str:
    if ledger.mode() == "LIVE":
        return '<span class="pill pill-live"><i></i>Live</span>'
    return '<span class="pill pill-test"><i></i>Test books</span>'


def mode_banner():
    """Kept for the pages; the mode pill now lives in the sidebar so pages stay clean."""
    return None


def guard(admin: bool = False):
    """Stop the page unless someone is signed in (and is an admin, for money and control pages)."""
    u = user()
    if not u:
        st.error("Please sign in first.")
        st.stop()
    if admin and u.get("role") != "admin":
        st.warning("This page is for admin users.")
        st.stop()


def password_ok(key: str, label: str = "Re-enter your password to confirm") -> bool:
    pw = st.text_input(label, type="password", key=key)
    if not pw:
        return False
    if security.verify_user(username(), pw):
        return True
    st.error("Password incorrect.")
    return False


def show_df(df, **kw):
    """st.dataframe that works on old Streamlit (use_container_width) and new (width='stretch')."""
    try:
        st.dataframe(df, width="stretch", **kw)
    except TypeError:
        st.dataframe(df, use_container_width=True, **kw)


CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
html, body, [class*="css"], .stApp { font-family: 'Inter', system-ui, sans-serif; }

/* ---- animated deep-blue background ---- */
.stApp {
  background:
    radial-gradient(1200px 700px at 12% -10%, rgba(52,110,255,.28), transparent 60%),
    radial-gradient(900px 600px at 95% 10%, rgba(0,190,255,.16), transparent 55%),
    linear-gradient(135deg, #040B22 0%, #07112B 45%, #0A1B4A 100%);
  background-size: 140% 140%, 140% 140%, 200% 200%;
  animation: bgdrift 26s ease-in-out infinite alternate;
}
@keyframes bgdrift { from { background-position: 0% 0%, 100% 0%, 0% 50%; } to { background-position: 30% 20%, 70% 30%, 100% 50%; } }
.stApp::before, .stApp::after {
  content: ""; position: fixed; border-radius: 50%; filter: blur(70px); opacity: .35; pointer-events: none; z-index: 0;
}
.stApp::before { width: 420px; height: 420px; background: #2f6bff; top: 8%; left: -120px; animation: floaty 18s ease-in-out infinite; }
.stApp::after  { width: 360px; height: 360px; background: #00c2ff; bottom: -100px; right: -80px; animation: floaty 22s ease-in-out infinite reverse; }
@keyframes floaty { 0%,100% { transform: translate(0,0) scale(1); } 50% { transform: translate(60px,-50px) scale(1.15); } }
[data-testid="stAppViewContainer"], [data-testid="stMain"], [data-testid="stSidebar"] { position: relative; z-index: 1; }
[data-testid="stHeader"] { background: transparent; }
footer, #MainMenu, .stDeployButton, [data-testid="stStatusWidget"] { visibility: hidden; }

/* ---- sidebar ---- */
[data-testid="stSidebar"] {
  background: linear-gradient(180deg, rgba(8,20,58,.96), rgba(5,12,36,.98));
  border-right: 1px solid rgba(110,150,255,.15);
}
.brand { font-weight: 800; font-size: 1.35rem; letter-spacing: .3px; padding: .2rem 0 .6rem 0;
  background: linear-gradient(90deg, #7fb0ff, #35d0ff, #ffd479); -webkit-background-clip: text; background-clip: text; color: transparent;
  background-size: 200% 100%; animation: shine 6s linear infinite; }
@keyframes shine { to { background-position: 200% 0; } }

/* ---- headings ---- */
h1 { font-weight: 800 !important; letter-spacing: -.5px;
  background: linear-gradient(90deg, #ffffff 0%, #9cc2ff 60%, #ffd479 100%); -webkit-background-clip: text; background-clip: text; color: transparent;
  animation: fadeUp .5s ease both; }
h2, h3 { font-weight: 700 !important; color: #dfe9ff; animation: fadeUp .5s ease both; }
@keyframes fadeUp { from { opacity: 0; transform: translateY(12px); } to { opacity: 1; transform: none; } }

/* ---- metric cards ---- */
[data-testid="stMetric"] {
  background: linear-gradient(150deg, rgba(40,82,190,.42), rgba(10,26,70,.62));
  border: 1px solid rgba(130,170,255,.22); border-radius: 18px; padding: 18px 20px;
  box-shadow: 0 10px 30px rgba(0,0,0,.35), inset 0 1px 0 rgba(255,255,255,.06);
  backdrop-filter: blur(10px); transition: transform .25s ease, box-shadow .25s ease, border-color .25s ease;
  animation: fadeUp .6s ease both; position: relative; overflow: hidden;
}
[data-testid="stMetric"]::after { content: ""; position: absolute; top: 0; left: -60%; width: 40%; height: 100%;
  background: linear-gradient(100deg, transparent, rgba(255,255,255,.10), transparent); transform: skewX(-20deg); animation: sweep 7s ease-in-out infinite; }
@keyframes sweep { 0%, 70% { left: -60%; } 100% { left: 140%; } }
[data-testid="stMetric"]:hover { transform: translateY(-5px); border-color: rgba(120,190,255,.6); box-shadow: 0 18px 40px rgba(20,80,255,.30); }
[data-testid="stMetricLabel"] p { color: #9db8f5 !important; font-weight: 600; text-transform: uppercase; font-size: .72rem !important; letter-spacing: .8px; }
[data-testid="stMetricValue"] { font-weight: 800; color: #ffffff; font-size: 1.4rem; }
[data-testid="stMetricValue"] > div { white-space: normal !important; overflow: visible !important; text-overflow: clip !important; line-height: 1.2; }
[data-testid="stMainBlockContainer"] { padding-top: 2.5rem; }
[data-testid="stColumn"]:nth-child(2) [data-testid="stMetric"] { animation-delay: .08s; }
[data-testid="stColumn"]:nth-child(3) [data-testid="stMetric"] { animation-delay: .16s; }
[data-testid="stColumn"]:nth-child(4) [data-testid="stMetric"] { animation-delay: .24s; }
[data-testid="stColumn"]:nth-child(5) [data-testid="stMetric"] { animation-delay: .32s; }

/* ---- buttons ---- */
.stButton > button, .stDownloadButton > button, [data-testid="stFormSubmitButton"] > button {
  border-radius: 12px; border: 1px solid rgba(130,170,255,.35); background: rgba(30,60,140,.45); color: #eaf1ff; font-weight: 600;
  transition: transform .18s ease, box-shadow .18s ease, background .18s ease;
}
.stButton > button:hover, .stDownloadButton > button:hover, [data-testid="stFormSubmitButton"] > button:hover {
  transform: translateY(-2px); box-shadow: 0 8px 22px rgba(60,130,255,.40); border-color: #7fb0ff; color: #fff; }
.stButton > button[kind="primary"], [data-testid="stFormSubmitButton"] > button[kind="primary"] {
  background: linear-gradient(90deg, #2f6bff, #00b7ff); border: none; color: #fff; box-shadow: 0 6px 20px rgba(0,140,255,.35); }

/* ---- tabs, expanders, forms, inputs ---- */
[data-baseweb="tab-list"] { gap: 6px; }
[data-baseweb="tab"] { border-radius: 10px 10px 0 0; transition: background .2s; }
[data-baseweb="tab"]:hover { background: rgba(80,130,255,.15); }
[data-testid="stExpander"], [data-testid="stForm"] {
  background: rgba(14,32,82,.55); border: 1px solid rgba(120,160,255,.18) !important; border-radius: 16px;
  backdrop-filter: blur(8px); animation: fadeUp .5s ease both; }
[data-testid="stExpander"]:hover { border-color: rgba(120,180,255,.45) !important; }
input, textarea, [data-baseweb="select"] > div { background-color: rgba(8,20,58,.75) !important; border-radius: 10px !important; }
input:focus, textarea:focus { box-shadow: 0 0 0 2px rgba(76,141,255,.55) !important; }
[data-testid="stDataFrame"] { border-radius: 14px; overflow: hidden; border: 1px solid rgba(120,160,255,.2); animation: fadeUp .6s ease both; }
[data-testid="stAlert"] { border-radius: 14px; animation: fadeUp .5s ease both; }
.stProgress > div > div > div > div { background: linear-gradient(90deg, #2f6bff, #35d0ff, #ffd479); background-size: 200% 100%; animation: shine 3s linear infinite; }

/* ---- mode pill ---- */
.pill-row { display: flex; justify-content: flex-end; margin-bottom: -2.2rem; }
.pill { display: inline-flex; align-items: center; gap: 7px; font-size: .75rem; font-weight: 700; padding: 5px 12px; border-radius: 999px;
  border: 1px solid rgba(255,255,255,.15); background: rgba(10,26,70,.7); color: #cfe0ff; }
.pill i { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
.pill-live { color: #b9ffd9; } .pill-live i { background: #21e08a; animation: pulse 1.8s infinite; }
.pill-test { color: #ffe3a6; } .pill-test i { background: #ffb938; animation: pulse 2.4s infinite; }
@keyframes pulse { 0% { box-shadow: 0 0 0 0 rgba(120,255,190,.6); } 70% { box-shadow: 0 0 0 9px rgba(120,255,190,0); } 100% { box-shadow: 0 0 0 0 rgba(120,255,190,0); } }

/* ---- login hero ---- */
.hero { text-align: center; padding: 3.5rem 0 1rem 0; animation: fadeUp .8s ease both; }
.hero .logo { font-size: 4rem; display: inline-block; animation: bob 3.2s ease-in-out infinite; filter: drop-shadow(0 0 24px rgba(80,160,255,.8)); }
@keyframes bob { 0%,100% { transform: translateY(0) rotate(-3deg); } 50% { transform: translateY(-12px) rotate(3deg); } }
.hero h1 { font-size: 3rem; margin: .3rem 0 0 0; }
.hero p { color: #9db8f5; font-size: 1.05rem; margin-top: .2rem; }
</style>
"""


def inject_css():
    st.markdown(CSS, unsafe_allow_html=True)
