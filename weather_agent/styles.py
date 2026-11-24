"""App-wide CSS: the navy "Zentro AI Weather Agent" look from the design reference."""

CSS = """
<style>
:root {
  --bg:#060c1a; --panel:#0a1224; --card:#0d1730; --card-2:#101c38; --border:rgba(96,130,200,.18);
  --text:#e6ecf8; --muted:#8b9bb8; --blue:#2563eb; --blue-2:#3b82f6; --active:#13254d;
}
.stApp { background:var(--bg); color:var(--text); }
[data-testid="stHeader"] { background:transparent; }
[data-testid="stToolbar"], [data-testid="stDecoration"] { display:none; }
[data-testid="stSidebar"] [data-testid="stVerticalBlock"] { gap:.2rem; }
div[class*="st-key-quick_"] button > div, div[class*="st-key-new_query"] button > div,
div[class*="st-key-example_"] button > div { justify-content:flex-start; width:100%; }
div[class*="st-key-quick_"] button p, div[class*="st-key-example_"] button p { text-align:left; }
.block-container { max-width:1180px; padding:1.1rem 1.6rem 6rem; }

/* ---------- sidebar ---------- */
[data-testid="stSidebar"] { background:var(--panel); border-right:1px solid var(--border); }
[data-testid="stSidebarUserContent"] { padding-top:.6rem; }
.brand { display:flex; align-items:center; gap:.75rem; padding:.2rem .2rem 1rem; }
.brand-icon { width:46px; height:46px; display:flex; align-items:center; justify-content:center; font-size:1.9rem;
  filter:drop-shadow(0 0 10px rgba(59,130,246,.55)); }
.brand-name { font-weight:700; font-size:1.15rem; color:#fff; line-height:1.1; }
.brand-sub { color:#c9d4ea; font-size:.86rem; display:flex; align-items:center; gap:.4rem; }
.ai-chip { background:linear-gradient(135deg,#6d28d9,#4f46e5); color:#fff; font-size:.68rem; font-weight:700;
  padding:.05rem .4rem; border-radius:6px; }
div[class*="st-key-new_query"] button { background:#15203b; border:1px solid var(--border); color:#fff;
  justify-content:flex-start; padding:.65rem .9rem; border-radius:10px; font-weight:600; }
div[class*="st-key-new_query"] button:hover { border-color:var(--blue-2); }
[data-testid="stSidebar"] [data-testid="stPageLink"] a { padding:.55rem .8rem; border-radius:10px; }
[data-testid="stSidebar"] [data-testid="stPageLink"] a:hover { background:rgba(255,255,255,.035); }
[data-testid="stSidebar"] [data-testid="stPageLink"] a:focus { box-shadow:none; outline:none; }
div[class*="st-key-nav_active"] [data-testid="stPageLink"] a { background:var(--active);
  box-shadow:inset 0 0 0 1px rgba(59,130,246,.35); }
.side-title { color:var(--muted); font-size:.85rem; margin:1rem .2rem .35rem; }
div[class*="st-key-quick_"] button { background:transparent; border:0; color:#c9d4ea; justify-content:flex-start;
  padding:.35rem .6rem; font-size:.86rem; border-radius:8px; min-height:0; }
div[class*="st-key-quick_"] button:hover { background:#111d38; color:#fff; }
div[class*="st-key-quick_active"] button { background:var(--active); color:#fff; }
.pro-card { margin-top:1.2rem; border:1px solid var(--border); border-radius:12px; padding:.8rem .9rem;
  background:linear-gradient(160deg,#0f1a34,#0a1226); }
.pro-row { display:flex; align-items:center; justify-content:space-between; font-weight:600; }
.pro-active { background:rgba(34,197,94,.15); color:#4ade80; font-size:.72rem; padding:.1rem .5rem; border-radius:999px;
  border:1px solid rgba(34,197,94,.35); }
.pro-feat { color:var(--muted); font-size:.75rem; margin-top:.45rem; }

/* ---------- top bar ---------- */
.topbar-title { display:flex; align-items:center; gap:.8rem; }
.topbar-icon { font-size:2.1rem; }
.topbar-name { font-size:1.35rem; font-weight:700; color:#fff; line-height:1.15; }
.topbar-sub { color:var(--muted); font-size:.82rem; }
div[class*="st-key-top_searchbox"] input { background:var(--card); border-radius:10px; }
div[class*="st-key-top_"] button { background:var(--card); border:1px solid var(--border); color:#e6ecf8;
  border-radius:10px; min-height:2.5rem; }
div[class*="st-key-top_"] button:hover { border-color:var(--blue-2); }
div[class*="st-key-top_avatar"] button { border-radius:999px; background:linear-gradient(135deg,#2563eb,#1d4ed8);
  font-weight:700; border:0; }
.topbar-sep { border:0; border-top:1px solid var(--border); margin:.4rem 0 1rem; }

/* ---------- chat ---------- */
.msg-user { display:flex; justify-content:flex-end; align-items:flex-start; gap:.7rem; margin:.4rem 0 .1rem; }
.bubble-user { background:linear-gradient(135deg,#1d4ed8,#1e40af); color:#fff; padding:.7rem 1rem;
  border-radius:16px 16px 4px 16px; max-width:62%; font-size:.95rem; line-height:1.45; }
.avatar-user { width:38px; height:38px; border-radius:999px; background:#1b2847; display:flex; align-items:center;
  justify-content:center; flex-shrink:0; }
.msg-time { text-align:right; color:var(--muted); font-size:.75rem; margin:0 3.4rem .6rem 0; }
.msg-ai { display:flex; align-items:center; gap:.7rem; margin:.3rem 0 .9rem; }
.avatar-ai { width:36px; height:36px; border-radius:999px; background:linear-gradient(135deg,#4f46e5,#2563eb);
  display:flex; align-items:center; justify-content:center; font-weight:700; font-size:.85rem; color:#fff; flex-shrink:0; }
.bubble-ai { background:var(--card-2); border:1px solid var(--border); padding:.6rem .95rem;
  border-radius:4px 14px 14px 14px; font-size:.95rem; }

/* ---------- analysis card ---------- */
div[class*="st-key-analysis_"] { background:var(--card); border:1px solid var(--border); border-radius:14px;
  padding:1rem 1.2rem .8rem; margin:.2rem 0 1rem; }
.an-title { font-weight:700; font-size:1rem; margin-bottom:.5rem; color:#fff; }
.an-list { list-style:none; padding:0; margin:0; }
.an-list li { margin:.22rem 0; font-size:.9rem; display:flex; gap:.5rem; align-items:flex-start; }
.an-check { background:#16a34a; color:#fff; border-radius:999px; width:17px; height:17px; font-size:.65rem; flex-shrink:0;
  display:inline-flex; align-items:center; justify-content:center; margin-top:.15rem; }
div[class*="st-key-analysis_"] .stDownloadButton button { background:transparent; border:1.5px solid #a855f7; color:#fff;
  border-radius:999px; padding:.7rem 1.1rem; font-weight:600; box-shadow:0 0 18px rgba(168,85,247,.25); }
div[class*="st-key-analysis_"] .stDownloadButton button:hover { background:rgba(168,85,247,.12); }
.an-note { color:var(--muted); font-size:.72rem; text-align:center; margin-top:.4rem; }

/* ---------- inputs & generic ---------- */
[data-testid="stChatInput"] { border-radius:14px; }
[data-testid="stBottomBlockContainer"] { max-width:1180px; padding-bottom:1.2rem; }
[data-testid="stExpander"] { border:1px solid var(--border); border-radius:12px; background:var(--card); }
[data-testid="stMetric"] { background:var(--card); border:1px solid var(--border); border-radius:12px; padding:.6rem .8rem; }
.stButton > button[kind="primary"] { background:var(--blue); border:0; }
.risk { display:inline-block; padding:.12rem .6rem; border-radius:999px; font-size:.75rem; font-weight:600; }
.risk-Low, .risk-None { background:rgba(34,197,94,.16); color:#4ade80; }
.risk-Moderate { background:rgba(245,158,11,.16); color:#fbbf24; }
.risk-High { background:rgba(239,68,68,.16); color:#f87171; }
.risk-Severe { background:rgba(153,27,27,.45); color:#fecaca; }
.examples-title { color:var(--muted); font-size:.85rem; margin:1rem 0 .4rem; }
div[class*="st-key-example_"] button { background:var(--card); border:1px solid var(--border); border-radius:12px;
  color:#dbe4f5; min-height:3rem; justify-content:flex-start; text-align:left; }
div[class*="st-key-example_"] button:hover { border-color:var(--blue-2); }
.welcome { text-align:center; padding:2rem 1rem 1rem; }
.welcome-icon { font-size:3.4rem; filter:drop-shadow(0 0 18px rgba(59,130,246,.6)); }
.welcome h2 { font-size:1.9rem; margin:.5rem 0 .3rem; color:#fff; }
.welcome p { color:var(--muted); max-width:38rem; margin:0 auto; }
</style>
"""
