import os
import json
import urllib.request
from datetime import datetime, timezone, timedelta

REPO = "Srivastava-Shrestha/MAY2026-Team-003"
TOKEN = os.environ["GH_TOKEN"]

NAME_MAP = {
    "Srivastava-Shrestha": "Shrestha",
    "23f2004336": "Shrishti",
    "22f3000162": "Pawan",
    "1mystic": "Atharv",
    "kavstea": "Kavisha",
}

def gh(path):
    url = f"https://api.github.com/repos/{REPO}/{path}"
    req = urllib.request.Request(url, headers={
        "Authorization": f"token {TOKEN}",
        "Accept": "application/vnd.github+json",
    })
    with urllib.request.urlopen(req) as r:
        return json.load(r)

def name(login):
    return NAME_MAP.get(login, login)

def fmt_date(iso):
    if not iso:
        return ""
    return iso[:10]

prs = gh("pulls?state=all&per_page=100")
issues_raw = gh("issues?state=all&per_page=100")
branches = gh("branches?per_page=100")

issues = [i for i in issues_raw if "pull_request" not in i]

open_prs   = [p for p in prs if p["state"] == "open"]
merged_prs = [p for p in prs if p.get("merged_at")]
closed_prs = [p for p in prs if p["state"] == "closed" and not p.get("merged_at")]

open_issues   = [i for i in issues if i["state"] == "open"]
closed_issues = [i for i in issues if i["state"] == "closed"]

IST = timezone(timedelta(hours=5, minutes=30))
now = datetime.now(IST).strftime("%d %b %Y %H:%M IST")

lines = []
lines.append(f"# 🔗 GitHub Tracker — Campus Connect")
lines.append(f"**Repo:** `{REPO}`  ")
lines.append(f"**Auto-updated:** {now}\n")
lines.append("---\n")

lines.append("## 📊 Summary\n")
lines.append("| Metric | Count |")
lines.append("|--------|-------|")
lines.append(f"| Total PRs | {len(prs)} |")
lines.append(f"| ✅ Merged | {len(merged_prs)} |")
lines.append(f"| ❌ Closed without merge | {len(closed_prs)} |")
lines.append(f"| 🟢 Open PRs | {len(open_prs)} |")
lines.append(f"| 🐛 Open Issues | {len(open_issues)} |")
lines.append(f"| ✔️ Closed Issues | {len(closed_issues)} |")
lines.append(f"| 🌿 Branches | {len(branches)} |")
lines.append("")

from collections import Counter
pr_by = Counter(name(p["user"]["login"]) for p in prs)
merged_by = Counter(name(p["user"]["login"]) for p in merged_prs)
open_by = Counter(name(p["user"]["login"]) for p in open_prs)

lines.append("---\n")
lines.append("## 👤 Per-Person Summary\n")
lines.append("| Person | Total PRs | Merged | Open |")
lines.append("|--------|-----------|--------|------|")
for person in ["Shrestha", "Shrishti", "Pawan", "Atharv", "Kavisha"]:
    lines.append(f"| **{person}** | {pr_by[person]} | {merged_by[person]} | {open_by[person]} |")
lines.append("")

lines.append("---\n")
lines.append("## 🔀 Pull Requests\n")

if open_prs:
    lines.append("### 🟢 Open\n")
    lines.append("| # | Title | Owner | Branch |")
    lines.append("|---|-------|-------|--------|")
    for p in open_prs:
        lines.append(f"| #{p['number']} | {p['title']} | **{name(p['user']['login'])}** | `{p['head']['ref']}` |")
    lines.append("")

if merged_prs:
    lines.append("### ✅ Merged\n")
    lines.append("| # | Title | Owner | Merged |")
    lines.append("|---|-------|-------|--------|")
    for p in merged_prs:
        lines.append(f"| #{p['number']} | {p['title']} | **{name(p['user']['login'])}** | {fmt_date(p.get('merged_at'))} |")
    lines.append("")

if closed_prs:
    lines.append("### ❌ Closed without merging\n")
    lines.append("| # | Title | Owner |")
    lines.append("|---|-------|-------|")
    for p in closed_prs:
        lines.append(f"| #{p['number']} | {p['title']} | **{name(p['user']['login'])}** |")
    lines.append("")

lines.append("---\n")
lines.append("## 🐛 Issues\n")

if open_issues:
    lines.append("### 🟢 Open\n")
    lines.append("| # | Title | Owner | Labels |")
    lines.append("|---|-------|-------|--------|")
    for i in open_issues:
        lbls = ", ".join(f"`{l['name']}`" for l in i.get("labels", []))
        lines.append(f"| #{i['number']} | {i['title']} | **{name(i['user']['login'])}** | {lbls} |")
    lines.append("")

if closed_issues:
    lines.append("### ✅ Closed\n")
    lines.append("| # | Title | Owner |")
    lines.append("|---|-------|-------|")
    for i in closed_issues:
        lines.append(f"| #{i['number']} | {i['title']} | **{name(i['user']['login'])}** |")
    lines.append("")

lines.append("---\n")
lines.append("## 🌿 Branches\n")

branch_owners = {}
for b in branches:
    n_raw = b["name"]
    owner = None
    for keyword, person in [("shrestha","Shrestha"),("shrishti","Shrishti"),("pawan","Pawan"),("atharv","Atharv"),("kavisha","Kavisha"),("kavstea","Kavisha")]:
        if keyword in n_raw.lower():
            owner = person
            break
    if owner not in branch_owners:
        branch_owners[owner] = []
    branch_owners[owner].append(n_raw)

for owner in ["Shrestha","Shrishti","Pawan","Atharv","Kavisha", None]:
    brs = branch_owners.get(owner, [])
    if not brs:
        continue
    label = owner if owner else "Base branches"
    lines.append(f"### {label} ({len(brs)})\n")
    for b in brs:
        lines.append(f"- `{b}`")
    lines.append("")

lines.append("---")
lines.append(f"_Auto-generated by GitHub Actions · {now}_")

output = "\n".join(lines)
with open("github-tracker.md", "w") as f:
    f.write(output)

print(f"✅ Tracker generated at {now}")
print(f"   PRs: {len(prs)} | Issues: {len(issues)} | Branches: {len(branches)}")
