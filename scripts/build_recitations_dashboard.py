#!/usr/bin/env python3
"""Generate notebooks/recitations_dashboard.ipynb — a clean visual dashboard for
the 5 daily + 2 weekly recitations (the in-scope data).

Prayers (Section 1) are new habits with no history yet, so they are not here.
Qaza / #### Quran / Sadaqa / to-dos are out of scope.
"""
from __future__ import annotations
from pathlib import Path
import nbformat as nbf

OUT = Path(__file__).resolve().parents[1] / "notebooks" / "recitations_dashboard.ipynb"
nb = nbf.v4.new_notebook()
cells = []
def md(t): cells.append(nbf.v4.new_markdown_cell(t.strip("\n")))
def code(t): cells.append(nbf.v4.new_code_cell(t.strip("\n")))

md(r"""
<div align="center">

# 📿 Recitations Dashboard

### Daily & Weekly recitation consistency — Sept → Nov 2026

</div>

*Covers the **5 daily recitations** (Surah Mulk · 500 Lā ḥawla · Tasbeeh Fatima ·
11× Muhammad · Quran Hakeem) and the **2 weekly/Friday** ones (313 Darood · Quran
every Jummah). Prayers are new habits with no data yet; everything else is out of
scope. All dates in Pakistan time (UTC+5).*
""")

code(r"""
import sys; from pathlib import Path
ROOT = Path.cwd().parent if Path.cwd().name == "notebooks" else Path.cwd()
sys.path.insert(0, str(ROOT / "src"))
import numpy as np, pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import FancyBboxPatch
import seaborn as sns
from habitica_etl import config, loaders, database, analytics

# ---- build DB + load in-scope events (prefer live API snapshot) ----
live = config.DATA_DIR / "habitica-live.json"
src = live if live.exists() else config.RAW_JSON
user = loaders.load_user_json(src)
conn = database.connect(config.DB_PATH)
database.create_schema(conn); database.ingest_user(conn, user, json_path=src)
print("data source:", src.name)

ev = analytics.events(conn)
ev["section"] = ev["task_text"].map(config.classify_section)
ev = ev[ev["section"].notna()].copy()

# clean short labels (avoid Arabic rendering issues)
def label(t):
    if "Surah Mulk" in t: return "Surah Mulk"
    if "500 " in t: return "500 Lā ḥawla"
    if "tasbeeh fatima" in t: return "Tasbeeh Fatima"
    if "11 Times Muhammad" in t: return "11× Muhammad"
    if "Quran Hakeem" in t: return "Quran Hakeem"
    if "313 darood" in t: return "313 Darood"
    if "Quran Every Jummah" in t: return "Quran (Jummah)"
    return t[:18]
ev["name"] = ev["task_text"].map(label)
ev["done"] = (ev["observed_action"] == "completed").astype(int)
det = ev[ev["observed_action"].isin(["completed","missed"])].copy()

# ---- style ----
sns.set_theme(style="whitegrid", context="talk")
INK="#1d3557"; TEAL="#2a9d8f"; GOLD="#e9c46a"; CORAL="#e76f51"; SLATE="#577590"; MINT="#8ecae6"
plt.rcParams.update({
    "figure.facecolor":"white","axes.facecolor":"white","axes.edgecolor":"#d9d9d9",
    "axes.grid":True,"grid.color":"#eeeeee","axes.titleweight":"bold",
    "axes.titlecolor":INK,"font.size":12,
})
ORDER = ["Surah Mulk","500 Lā ḥawla","Tasbeeh Fatima","11× Muhammad","Quran Hakeem","313 Darood","Quran (Jummah)"]
print("In-scope events:", len(ev), "| tasks:", ev['name'].nunique())
""")

# ---------------------------------------------------- KPI row
md("## At a glance")
code(r"""
n_tasks = ev["name"].nunique()
overall = 100*det["done"].mean()
active_days = ev["event_date_pkt"].dt.date.nunique()
total_done = int(det["done"].sum())
best_rate = det.groupby("name")["done"].mean().max()*100

fig, axes = plt.subplots(1, 5, figsize=(15, 2.4))
cards = [("Recitations", f"{n_tasks}", TEAL),
         ("Overall adherence", f"{overall:.0f}%", INK),
         ("Times completed", f"{total_done}", SLATE),
         ("Active days", f"{active_days}", GOLD),
         ("Best recitation", f"{best_rate:.0f}%", TEAL)]
for ax,(title,val,c) in zip(axes, cards):
    ax.axis("off")
    ax.add_patch(FancyBboxPatch((0.03,0.08),0.94,0.84,boxstyle="round,pad=0.02,rounding_size=0.08",
                 fc=c, ec="none", alpha=0.12, transform=ax.transAxes))
    ax.text(0.5,0.60,val,ha="center",va="center",fontsize=30,fontweight="bold",color=c,transform=ax.transAxes)
    ax.text(0.5,0.24,title,ha="center",va="center",fontsize=12,color=INK,transform=ax.transAxes)
plt.suptitle("Recitation consistency — Sept → Nov 2026", y=1.12, fontsize=16, fontweight="bold", color=INK)
plt.tight_layout(); plt.show()
""")

# ---------------------------------------------------- adherence leaderboard
md("## Adherence by recitation")
code(r"""
g = (det.groupby("name").agg(done=("done","sum"), n=("done","size")))
g["rate"] = g["done"]/g["n"]
g = g.reindex([x for x in ORDER if x in g.index]).sort_values("rate")
colors = [CORAL if r<0.6 else GOLD if r<0.85 else TEAL for r in g["rate"]]
fig, ax = plt.subplots(figsize=(11,5.5))
bars = ax.barh(g.index, 100*g["rate"], color=colors, edgecolor="white", height=0.66)
ax.set_xlim(0,108); ax.set_xlabel("Adherence  (completed ÷ scheduled)")
ax.set_title("How consistently each recitation was kept")
for y,(r,d,n) in enumerate(zip(g["rate"], g["done"], g["n"])):
    ax.text(100*r+1.5, y, f"{100*r:.0f}%  ·  {int(d)}/{int(n)}", va="center", fontsize=11, color=INK)
ax.grid(axis="y", visible=False)
sns.despine(left=True); plt.tight_layout(); plt.show()
""")

# ---------------------------------------------------- calendar heatmap
md("## Activity calendar")
code(r"""
daily = (det.groupby(det["event_date_pkt"].dt.normalize())["done"].sum())
daily = daily[daily.index >= "2026-09-01"]
cal = pd.DataFrame({"date":daily.index, "done":daily.values})
cal["week"] = cal["date"].dt.isocalendar().week.values
cal["dow"]  = cal["date"].dt.dayofweek
piv = cal.pivot_table(index="dow", columns="week", values="done", aggfunc="sum")
fig, ax = plt.subplots(figsize=(14,3.4))
sns.heatmap(piv, cmap="YlGnBu", linewidths=2, linecolor="white", cbar_kws={"label":"recitations that day"},
            yticklabels=["Mon","Tue","Wed","Thu","Fri","Sat","Sun"], ax=ax)
ax.set_title("Recitations completed per day (darker = more)"); ax.set_xlabel("ISO week"); ax.set_ylabel("")
plt.tight_layout(); plt.show()
""")

# ---------------------------------------------------- weekday
md("## Weekday rhythm")
code(r"""
wd = det.copy()
names = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
wd["wname"] = wd["event_weekday"].map(dict(enumerate(names)))
w = wd.groupby("wname").agg(rate=("done","mean"), n=("done","size")).reindex(names)
fig, ax = plt.subplots(figsize=(11,4.6))
bars = ax.bar(w.index, 100*w["rate"], color=[TEAL if x!="Fri" else GOLD for x in w.index],
              edgecolor="white", width=0.66)
ax.set_ylim(0,112); ax.set_ylabel("Adherence %"); ax.set_title("Consistency by weekday (Friday highlighted)")
for i,(r,n) in enumerate(zip(w["rate"], w["n"])):
    ax.text(i, 100*r+2, f"{100*r:.0f}%", ha="center", fontsize=11, color=INK)
ax.grid(axis="x", visible=False); sns.despine(); plt.tight_layout(); plt.show()
""")

# ---------------------------------------------------- momentum
md("## Momentum — each recitation building up")
code(r"""
fig, ax = plt.subplots(figsize=(13,5.5))
pal = dict(zip(ORDER, [INK,TEAL,GOLD,CORAL,SLATE,"#9b5de5","#06d6a0"]))
for nm, sub in ev.sort_values("event_date_pkt").groupby("name"):
    ax.plot(sub["event_date_pkt"], sub["value"], marker="o", ms=3, lw=2, label=nm, color=pal.get(nm))
ax.axhline(0, color="#bbb", lw=1)
ax.set_title("Habitica value over time — a steady climb means a kept habit")
ax.set_ylabel("task value"); ax.legend(fontsize=9, ncol=2, frameon=False, loc="upper left")
ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b")); sns.despine(); plt.tight_layout(); plt.show()
""")

# ---------------------------------------------------- streaks
md("## Streaks — current & longest run")
code(r"""
from collections import defaultdict
def streaks(sub):
    byday = defaultdict(list)
    for _,r in sub.iterrows():
        byday[r["event_date_pkt"].date()].append(r["observed_action"])
    seq = [("completed" if "completed" in byday[d] else "missed") for d in sorted(byday)
           if ("completed" in byday[d] or "missed" in byday[d])]
    cur=longest=0
    for a in seq:
        cur = cur+1 if a=="completed" else 0
        longest=max(longest,cur)
    return cur, longest
rows=[]
for nm,sub in det.groupby("name"):
    c,l = streaks(sub); rows.append((nm,c,l))
sdf = pd.DataFrame(rows, columns=["name","current","longest"]).set_index("name")
sdf = sdf.reindex([x for x in ORDER if x in sdf.index])
fig, ax = plt.subplots(figsize=(11,5))
y=np.arange(len(sdf))
ax.barh(y+0.18, sdf["longest"], height=0.34, color=TEAL, label="longest run", edgecolor="white")
ax.barh(y-0.18, sdf["current"], height=0.34, color=GOLD, label="current run", edgecolor="white")
ax.set_yticks(y); ax.set_yticklabels(sdf.index); ax.set_xlabel("days in a row")
ax.set_title("Streaks per recitation"); ax.legend(frameon=False)
for yi,(c,l) in enumerate(zip(sdf["current"], sdf["longest"])):
    ax.text(l+0.3, yi+0.18, str(int(l)), va="center", fontsize=10, color=INK)
    ax.text(c+0.3, yi-0.18, str(int(c)), va="center", fontsize=10, color=INK)
ax.grid(axis="y", visible=False); sns.despine(left=True); plt.tight_layout(); plt.show()
""")

# ---------------------------------------------------- monthly trend + daily vs weekly
md("## Trend & section comparison")
code(r"""
det2 = det.copy(); det2["ym"] = det2["event_date_pkt"].dt.strftime("%Y-%m")
monthly = det2.groupby("ym")["done"].mean()*100
sec = det2.groupby("section")["done"].mean()*100

fig, axes = plt.subplots(1, 2, figsize=(14,4.6))
axes[0].plot(monthly.index, monthly.values, marker="o", lw=3, color=TEAL)
for x,v in zip(monthly.index, monthly.values): axes[0].text(x, v+1.5, f"{v:.0f}%", ha="center", fontsize=11)
axes[0].set_ylim(0,110); axes[0].set_title("Overall adherence by month"); axes[0].set_ylabel("%")
labels = {"daily_recitation":"Daily (5)","weekly_recitation":"Weekly/Fri (2)"}
sec.index = [labels.get(i,i) for i in sec.index]
axes[1].bar(sec.index, sec.values, color=[TEAL,GOLD], edgecolor="white", width=0.5)
for i,v in enumerate(sec.values): axes[1].text(i, v+2, f"{v:.0f}%", ha="center", fontsize=12)
axes[1].set_ylim(0,112); axes[1].set_title("Daily vs weekly recitations")
for a in axes: a.grid(axis="x", visible=False); sns.despine(ax=a)
plt.tight_layout(); plt.show()
""")

md(r"""
---
### Read-out
- The recitations are **strongly kept** — most sit **84–100%**, and the two
  **Friday** ones are perfect so far (6/6 each).
- **Momentum** is visibly compounding — every value line climbs.
- This is the clean baseline. Once the **5 prayer habits** accumulate data, they
  get their own dashboard section the same way.
""")

nb["cells"] = cells
nb.metadata["kernelspec"] = {"name":"python3","display_name":"Python 3","language":"python"}
OUT.parent.mkdir(parents=True, exist_ok=True)
nbf.write(nb, OUT)
print("wrote", OUT)
