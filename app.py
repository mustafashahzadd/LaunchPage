# merged_app.py — Unified UI for Launch Builder (R1) + Workshop Planner (R2)
# Keeps all features; adds R1 markdown parsers + R2 normalizers so the UI always works.

import io, json, zipfile, re
import datetime as dt
from typing import Any, Dict, List, Optional

import streamlit as st

# ============== Optional deps ==============
try:
    from ics import Calendar, Event
    ICS_AVAILABLE = True
except Exception:
    ICS_AVAILABLE = False

# ============== R1 (Launch) imports =========
# Functions — import the callables (NOT the modules)
try:
    from research import make_research as r1_make_research
    from planner  import make_plan     as r1_make_plan
    from production import (
        make_landing_assets as r1_make_assets,
        generate_custom_file as r1_generate_custom_file,
    )
    from github_client import GitHubClient
except Exception:
    # Quiet stubs keep the UI usable even if imports fail
    def r1_make_research(*a, **k): return ""
    def r1_make_plan(*a, **k):     return ""
    def r1_make_assets(*a, **k):   return {}
    def r1_generate_custom_file(*a, **k): return ""
    class GitHubClient:  # minimal stub
        def __init__(self, *a, **k): ...
        def get_authed_user(self): return "?"
        def ensure_repo(self, **k): ...
        def push_files(self, **k): ...

# ============== R2 (Workshop) imports =======
try:
    from researcher_work import make_workshop_research as r2_make_research
    from planner_work    import make_workshop_plan     as r2_make_plan
    from producer_work   import make_workshop_assets   as r2_make_assets
    try:
        from forms_api import create_google_form as r2_create_google_form
    except Exception:
        def r2_create_google_form(*a, **k): return {"editUrl": None, "responderUrl": None}
except Exception:
    def r2_make_research(*a, **k): return None
    def r2_make_plan(*a, **k):     return None
    def r2_make_assets(*a, **k):   return None
    def r2_create_google_form(*a, **k): return {"editUrl": None, "responderUrl": None}

# ======================
# Page config & Secrets
# ======================
st.set_page_config(page_title="AI Project Hub — Launch + Workshop", page_icon="🧭", layout="wide")
st.title("🧭 AI Project Hub")
st.caption("One UI for your Landing Page Builder (R1) and Workshop Planner (R2)")

GROQ_KEY     = st.secrets.get("GROQ_API_KEY", "")
GITHUB_TOKEN = st.secrets.get("GITHUB_TOKEN", "")
GITHUB_OWNER = st.secrets.get("GITHUB_OWNER", "")

# ----------------
# Namespaced state
# ----------------
st.session_state.setdefault("launch", {
    "project_data": {},
    "research": {},
    "plan": {},
    "files": {},
    "custom_files": [],
    "file_count": 0,
})
st.session_state.setdefault("workshop", {
    "research": None,
    "plan": None,
    "assets": None,
})

# ========= small getters =========
def _safe_get(obj, *names, default=""):
    """dict or object attribute getter"""
    if obj is None: return default
    if isinstance(obj, dict):
        for n in names:
            v = obj.get(n)
            if v: return v
    else:
        for n in names:
            v = getattr(obj, n, None)
            if v: return v
    return default

# ---------- parsing + normalization helpers ----------
_BUL = re.compile(r"^\s*[-*•]\s+(.*)$", re.M)

def _bullets(block: str) -> list[str]:
    return [m.strip() for m in _BUL.findall(block or "")]

def _section(md: str, heading: str) -> str:
    md = md or ""
    h = re.search(rf"^\s*#\s*{re.escape(heading)}\s*$", md, re.I | re.M)
    if not h: return ""
    start = h.end()
    nxt = re.search(r"^\s*#\s+.+$", md[start:], re.M)
    end = start + (nxt.start() if nxt else len(md)-start)
    return md[start:end].strip()

def _parse_keywords(block: str) -> list[str]:
    line = (block or "").splitlines()[0] if block else ""
    return [s.strip().rstrip(".;:,") for s in re.split(r",|\uFF0C", line) if s.strip()]

# --- R1 (Launch) markdown -> dict ---
def parse_launch_research(md: str, audience: str) -> dict:
    comps = []
    for item in _bullets(_section(md, "Top Competitors"))[:3]:
        parts = re.split(r"\s+—\s+|\s+-\s+", item, maxsplit=1)
        comps.append({"name": parts[0].strip(), "angle": parts[1].strip() if len(parts) > 1 else ""})
    risks = []
    for item in _bullets(_section(md, "Risks"))[:3]:
        parts = re.split(r"\s+—\s+|\s+-\s+", item, maxsplit=1)
        risks.append({"risk": parts[0].strip(), "mitigation": parts[1].strip() if len(parts) > 1 else ""})
    return {
        "markdown": (md or "").strip(),
        "hooks": _bullets(_section(md, "Hooks"))[:5],
        "keywords": _parse_keywords(_section(md, "Keywords"))[:8],
        "competitors": comps,
        "risks": risks,
        "audience": audience,
    }

def _parse_milestone_line(line: str) -> dict:
    parts = re.split(r"\s+—\s+|\s+-\s+", line)
    parts = [p.strip() for p in parts if p.strip()]
    title = parts[0] if parts else "Milestone"
    goal  = parts[1] if len(parts) > 1 else ""
    owner = parts[2] if len(parts) > 2 else "Owner"
    m = re.search(r"(\d+)", parts[3] if len(parts) > 3 else "")
    due_days = int(m.group(1)) if m else None
    return {"title": title, "goal": goal, "owner": owner, "due_days": due_days, "tasks": []}

def _parse_repo_settings(block: str, defaults: dict) -> dict:
    repo = dict(defaults)
    for item in _bullets(block):
        low = item.lower()
        if "private" in low or "public" in low: repo["private"] = ("public" not in low)
        if "license" in low:
            m = re.search(r"license[:\s]+([A-Za-z0-9.\-]+)", item, re.I)
            if m: repo["license"] = m.group(1)
        if "ci" in low or "workflow" in low or "github actions" in low:
            repo["add_ci"] = ("no" not in low)
    return repo

def parse_launch_plan(md: str, repo_defaults: dict) -> dict:
    return {
        "markdown": (md or "").strip(),
        "milestones": [_parse_milestone_line(x) for x in _bullets(_section(md, "Milestones"))],
        "success_metrics": _bullets(_section(md, "Success Metrics")),
        "copy_outline": _bullets(_section(md, "Copy Outline")) or ["Hero", "Quickstart", "Features", "FAQ", "Footer"],
        "repo": _parse_repo_settings(_section(md, "Repo Settings"), repo_defaults),
    }

# --- R2 normalization: model/dict/str -> dict with topics/risks/agenda/etc. ---
def _to_dict(x) -> dict:
    if x is None: return {}
    if isinstance(x, dict): return x
    if hasattr(x, "model_dump"):
        try: return x.model_dump()
        except Exception: pass
    if hasattr(x, "dict"):
        try: return x.dict()
        except Exception: pass
    try:
        return {k: v for k, v in vars(x).items() if not k.startswith("_")}
    except Exception:
        return {"raw": x}

def normalize_r2_research(x, fallback_text: str = "") -> dict:
    d = _to_dict(x)
    topics = d.get("topics") or []
    risks  = d.get("risks")  or []
    if not topics or not isinstance(topics, list):
        text = d.get("text") or d.get("summary") or d.get("markdown") or fallback_text
        topics = _bullets(_section(text, "Topics")) or _bullets(text)
    if not risks or not isinstance(risks, list):
        text = d.get("text") or d.get("summary") or d.get("markdown") or fallback_text
        candidates = _bullets(_section(text, "Risks")) or _bullets(text)
        risks = [{"risk": r, "mitigation": ""} for r in candidates[:5]]
    d["topics"] = topics[:10]
    d["risks"]  = risks[:10]
    return d

def normalize_r2_plan(x) -> dict:
    d = _to_dict(x)
    if isinstance(d.get("agenda"), str): d["agenda"] = _bullets(d["agenda"])
    d.setdefault("agenda", [])
    if isinstance(d.get("success_metrics"), str): d["success_metrics"] = _bullets(d["success_metrics"])
    d.setdefault("success_metrics", [])
    if isinstance(d.get("milestones"), str):
        d["milestones"] = [{"title": line, "tasks": [], "due": ""} for line in _bullets(d["milestones"])]
    d.setdefault("milestones", [])
    return d

def normalize_r2_assets(x) -> dict:
    d = _to_dict(x)
    d.setdefault("invite_email", d.get("invite") or d.get("email") or "")
    d.setdefault("poster_text", d.get("poster") or "")
    d.setdefault("checklist",   d.get("checklist") or "")
    return d

# ====================================================
# R1 — Launch Builder (mirrors the optimized builder)
# ====================================================
def render_launch():
    L = st.session_state.launch
    tabs = st.tabs(["📝 Input", "🔍 Research", "📋 Plan", "🏗️ Build", "🚀 Deploy"])

    # ------- Tab 1: Input -------
    with tabs[0]:
        st.header("Project Configuration")
        c1, c2 = st.columns(2)

        with c1:
            st.subheader("Project Details")
            brief    = st.text_area("What do you want to build?", height=100, placeholder="Describe your landing page idea…")
            product  = st.text_input("Product Name", placeholder="MyAwesomeAPI")
            audience = st.text_input("Target Audience", placeholder="Developers, Startups")

            st.subheader("Custom Files")
            ca, cb = st.columns([3,1])
            with ca: st.write(f"Files configured: {L['file_count']}")
            with cb:
                if st.button("➕ Add File", use_container_width=True): L['file_count'] += 1

            L['custom_files'] = []
            for i in range(L['file_count']):
                with st.expander(f"File {i+1}", expanded=True):
                    f1, f2, f3 = st.columns([2,3,1])
                    ftype = f1.selectbox("Type", ["HTML","CSS","JS"], key=f"launch_ftype_{i}")
                    fname = f2.text_input("Filename", f"custom_{i+1}.{ftype.lower()}", key=f"launch_fname_{i}")
                    if f3.button("🗑️", key=f"launch_del_{i}"):
                        L['file_count'] = max(0, L['file_count']-1); st.rerun()
                    fprompt = st.text_area("What should this file do?", height=60, placeholder=f"Describe the {ftype} component…", key=f"launch_fprompt_{i}")
                    L['custom_files'].append({"type": ftype, "name": fname, "prompt": fprompt})

        with c2:
            st.subheader("GitHub Settings")
            gh_owner  = st.text_input("GitHub Username/Org", value=GITHUB_OWNER)
            repo_name = st.text_input("Repository Name", "landing-page")
            repo_desc = st.text_input("Description", "AI-generated landing page")
            st.divider()
            private = st.checkbox("Private Repository", True)
            license = st.selectbox("License", ["MIT", "Apache-2.0", "None"])
            add_ci  = st.checkbox("Add CI/CD Workflow", False)
            st.divider()
            if st.button("💾 Save Configuration", type="primary", use_container_width=True):
                L['project_data'] = {
                    'brief': brief, 'product': product, 'audience': audience,
                    'github_owner': gh_owner, 'repo_name': repo_name, 'repo_desc': repo_desc,
                    'private': private, 'license': license, 'add_ci': add_ci,
                }
                st.success("Configuration saved!")

    # ------- Tab 2: Research -------
    with tabs[1]:
        st.header("Market Research")
        data = L['project_data']
        if not data.get('brief') or not data.get('product'):
            st.warning("⚠️ Please complete project configuration first")
        else:
            if st.button("🔍 Start Research", type="primary", use_container_width=True):
                with st.spinner("Analyzing market…"):
                    md = r1_make_research(GROQ_KEY, data['product'], data.get('audience',''), data['brief'])
                    L['research'] = parse_launch_research(md, data.get('audience',''))
                st.success("Research complete!")
            if L['research']:
                c1, c2 = st.columns(2)
                with c1:
                    st.subheader("🎯 Hooks")
                    for h in L['research'].get('hooks', []): st.write(f"• {h}")
                    st.subheader("🏆 Competitors")
                    for comp in L['research'].get('competitors', []):
                        if isinstance(comp, dict): st.write(f"**{comp.get('name')}**: {comp.get('angle')}")
                with c2:
                    st.subheader("🔑 Keywords")
                    st.info(", ".join(L['research'].get('keywords', [])))
                    st.subheader("⚠️ Risks")
                    for r in L['research'].get('risks', []):
                        if isinstance(r, dict):
                            with st.expander(r.get('risk','Risk')): st.write(r.get('mitigation',''))

    # ------- Tab 3: Plan -------
    with tabs[2]:
        st.header("Project Planning")
        data = L['project_data']
        if not data.get('brief'):
            st.warning("⚠️ Please configure project first")
        else:
            if st.button("📋 Create Plan", type="primary", use_container_width=True):
                with st.spinner("Creating plan…"):
                    md = r1_make_plan(
                        GROQ_KEY,
                        data.get('product','Product'),
                        data.get('audience','Developers'),
                        data['brief'],
                        (L.get('research') or {}).get('markdown', ''),  # pass research TEXT to planner
                        data.get('repo_name','landing-page'),
                        data.get('repo_desc','Landing page'),
                        data.get('private', True),
                        data.get('license','MIT'),
                        data.get('add_ci', False),
                    )
                    L['plan'] = parse_launch_plan(md, {
                        "name": data.get('repo_name','landing-page'),
                        "desc": data.get('repo_desc','Landing page'),
                        "private": data.get('private', True),
                        "license": data.get('license','MIT'),
                        "add_ci": data.get('add_ci', False),
                    })
                st.success("Plan created!")

            if L['plan']:
                plan_obj = L['plan']

                # If the planner (or parser) returned Markdown text, just show it.
                if isinstance(plan_obj, str):
                    st.subheader("📄 Plan (Markdown)")
                    st.markdown(plan_obj)
                else:
                    # ---------- Milestones ----------
                    st.markdown("### 📅 Milestones")
                    milestones = (
                        plan_obj.get("milestones")
                        or plan_obj.get("Milestones")
                        or []
                    )

                    # If parser left milestones as a single string block, just show it
                    if isinstance(milestones, str):
                        st.markdown(milestones)
                    else:
                        for i, m in enumerate(milestones, 1):
                            # Be flexible about field names
                            title = (
                                (m.get("title") if isinstance(m, dict) else None)
                                or (m.get("name") if isinstance(m, dict) else None)
                                or f"Milestone {i}"
                            )

                            due_days = (m.get("due_days") if isinstance(m, dict) else None) \
                                       or (m.get("eta_days") if isinstance(m, dict) else None) \
                                       or (m.get("days") if isinstance(m, dict) else None)

                            due_date = (m.get("due") if isinstance(m, dict) else None) \
                                       or (m.get("date") if isinstance(m, dict) else None)

                            # Compose header like “Title — Due 2025-09-10 · 7 days”
                            tags = []
                            if due_date: tags.append(f"Due {due_date}")
                            if due_days: tags.append(f"{due_days} days")
                            header = f"{title}" + (f" — {' · '.join(tags)}" if tags else "")

                            with st.expander(header, expanded=False):
                                tasks = (
                                    (m.get("tasks") if isinstance(m, dict) else None)
                                    or (m.get("subtasks") if isinstance(m, dict) else None)
                                    or (m.get("items") if isinstance(m, dict) else None)
                                    or []
                                )
                                for t in tasks:
                                    if isinstance(t, dict):
                                        desc = t.get("desc") or t.get("task") or t.get("title") or str(t)
                                        hrs  = t.get("effort_hrs") or t.get("hrs") or t.get("hours")
                                        st.write(f"• {desc}" + (f" ({hrs}h)" if hrs else ""))
                                    else:
                                        st.write(f"• {t}")

                    # ---------- Success Metrics ----------
                    st.markdown("### 📊 Success Metrics")
                    metrics = (
                        plan_obj.get("success_metrics")
                        or plan_obj.get("metrics")
                        or plan_obj.get("Success Metrics")
                        or []
                    )
                    if isinstance(metrics, str):
                        st.markdown(metrics)
                    else:
                        cols = st.columns(2)
                        for i, metric in enumerate(metrics):
                            with cols[i % 2]:
                                st.success(str(metric))


    # ------- Tab 4: Build -------
    with tabs[3]:
        st.header("File Generation")
        data = L['project_data']
        if not data.get('brief'):
            st.warning("⚠️ Please configure project first")
        else:
            if st.button("🏗️ Generate Files", type="primary", use_container_width=True):
                with st.spinner("Generating files…"):
                    files = r1_make_assets(
                        GROQ_KEY,
                        data.get('product','Product'),
                        data.get('audience','Developers'),
                        data['brief'],
                        L.get('research', {}),
                        L.get('plan', {}),
                    ) or {}
                    # Custom files
                    for custom in L['custom_files']:
                        if custom.get('prompt'):
                            content = r1_generate_custom_file(
                                GROQ_KEY, custom['type'], custom['prompt'],
                                data.get('product','Product'), L.get('research', {}),
                            )
                            files[custom['name']] = content
                    L['files'] = files
                st.success(f"Generated {len(L['files'])} files!")

            if L['files']:
                st.subheader("📁 Files")
                names = list(L['files'].keys())
                pick = st.selectbox("Select file to view:", [""] + names)
                if pick:
                    content = L['files'][pick]
                    c1, c2, _ = st.columns([1,1,4])
                    with c1:
                        st.download_button("📥 Download", content, pick, key=f"launch_dl_{pick}")
                    with c2:
                        if st.button("✏️ Edit", key=f"launch_edit_{pick}"):
                            st.session_state[f"launch_editing_{pick}"] = True
                    if st.session_state.get(f"launch_editing_{pick}"):
                        edited = st.text_area("Edit content:", content, height=400, key=f"launch_editor_{pick}")
                        if st.button("Save", key=f"launch_save_{pick}"):
                            L['files'][pick] = edited
                            del st.session_state[f"launch_editing_{pick}"]; st.success("Saved!"); st.rerun()
                    else:
                        lang = "html" if pick.endswith(".html") else "css" if pick.endswith(".css") else "javascript" if pick.endswith(".js") else "text"
                        st.code(content, language=lang, line_numbers=True)

                st.divider()
                c1, c2 = st.columns(2)
                with c1:
                    zbuf = io.BytesIO()
                    with zipfile.ZipFile(zbuf, 'w') as z:
                        for n, c in L['files'].items(): z.writestr(n, c)
                    zbuf.seek(0)
                    st.download_button("📦 Download All (ZIP)", zbuf.getvalue(),
                                       f"landing-{dt.datetime.now().strftime('%Y%m%d')}.zip", "application/zip")
                with c2:
                    if st.button("👁️ Preview", use_container_width=True):
                        html_files = [n for n in L['files'] if n.endswith('.html')]
                        if not html_files:
                            st.warning("No HTML files to preview")
                        else:
                            # Combine CSS & JS
                            all_css = "\n".join([f"/* {n} */\n{L['files'][n]}" for n in L['files'] if n.endswith('.css')])
                            all_js  = "\n".join([f"// {n}\n{L['files'][n]}" for n in L['files'] if n.endswith('.js')])
                            for html_file in html_files:
                                html = L['files'][html_file]
                                if all_css:
                                    if '</head>' in html:
                                        html = html.replace('</head>', f'<style>{all_css}</style>\n</head>')
                                    elif '<html>' in html:
                                        html = html.replace('<html>', '<html>\n<head>\n<style>' + all_css + '</style>\n</head>')
                                    else:
                                        html = f'<style>{all_css}</style>\n' + html
                                if all_js:
                                    if '</body>' in html:
                                        html = html.replace('</body>', f'<script>{all_js}</script>\n</body>')
                                    elif '</html>' in html:
                                        html = html.replace('</html>', f'<script>{all_js}</script>\n</html>')
                                    else:
                                        html = html + f"\n<script>{all_js}</script>"
                                st.subheader(f"Preview: {html_file}")
                                st.components.v1.html(html, height=700, scrolling=True)

    # ------- Tab 5: Deploy -------
# ------- Tab 5: Deploy -------
    with tabs[4]:
        st.header("Deployment")

    if not L["files"]:
        st.warning("⚠️ No files to deploy. Generate files first.")
    elif not GITHUB_TOKEN:
        st.warning("⚠️ GitHub token not configured")
        zbuf = io.BytesIO()
        with zipfile.ZipFile(zbuf, "w") as z:
            for n, c in L["files"].items():
                z.writestr(n, c)
        zbuf.seek(0)
        st.download_button(
            "📦 Download for Manual Deploy",
            zbuf.getvalue(),
            f"landing-{dt.datetime.now().strftime('%Y%m%d')}.zip",
            "application/zip",
        )
    else:
        data = L["project_data"]
        if st.button("🚀 Deploy to GitHub", type="primary", use_container_width=True):
            with st.spinner("Deploying…"):
                client = GitHubClient(GITHUB_TOKEN)

                # --- resolve & sanitize owner ---
                owner = data.get("github_owner")
                if not owner:
                    try:
                        owner = client.get_authenticated_user()["login"]  # newer name
                    except AttributeError:
                        owner = client.get_authed_user()["login"]         # older name
                owner = (owner or "").strip().strip("/").replace(" ", "").replace("@", "").replace("#", "")

                repo    = data.get("repo_name", "landing-page").strip()
                private = data.get("private", True)
                desc    = data.get("repo_desc", "Landing page")

                # --- create/ensure repo (support multiple client signatures) ---
                create_repo = getattr(client, "create_repo", None) or getattr(client, "ensure_repo", None)
                if create_repo is None:
                    raise RuntimeError("GitHubClient missing create/ensure repo method")

                try:
                    # common sig (owner, repo, private, description, auto_init=True)
                    create_repo(owner, repo, private, desc, auto_init=True)
                except TypeError:
                    try:
                        # alt sig (repo, private, description, auto_init=True)
                        create_repo(repo, private, desc, auto_init=True)
                    except TypeError:
                        # kwargs fallback
                        create_repo(owner=owner, repo=repo, private=private, description=desc, auto_init=True)
                except Exception as e:
                    # if already exists, carry on
                    if "exists" not in str(e).lower():
                        raise

                # --- verify branch / reachability ---
                branch = "main"
                get_def = getattr(client, "get_default_branch", None)
                if callable(get_def):
                    try:
                        branch = get_def(owner, repo) or branch
                    except Exception:
                        # repo likely created under authed user; switch owner
                        try:
                            authed = client.get_authenticated_user()["login"]
                        except Exception:
                            authed = owner
                        branch = get_def(authed, repo) or branch
                        owner = authed

                # --- push files (support both method names) ---
                upsert_files = getattr(client, "upsert_files", None) or getattr(client, "push_files", None)
                if upsert_files is None:
                    raise RuntimeError("GitHubClient missing upsert/push files method")

                upsert_files(owner, repo, branch, L["files"])

                st.success(f"✅ Deployed to github.com/{owner}/{repo}")
                st.balloons()


# ====================================================
# R2 — Workshop / Event Planner (with Google Forms)
# ====================================================
def render_workshop():
    W = st.session_state.workshop

    st.header("🎤 Workshop / Event Planner")
    today = dt.date.today()
    today_str = today.strftime("%Y-%m-%d")
    today_readable = today.strftime("%B %d, %Y")
    current_weekday = today.strftime("%A")
    st.info(f"📅 Today is {current_weekday}, {today_readable}")
    date_context = f"Today's date is {today_str} ({current_weekday}, {today_readable}). Use this as the reference point for scheduling milestones and deadlines."

    c1, c2 = st.columns(2)
    goal       = c1.text_input("Goal", "1-day AI workshop in 10 days")
    audience   = c1.text_input("Audience", "high-school students")
    constraints= c2.text_area("Constraints", "budget < $200; 25 attendees; include consent forms")

    def badge(ok, label): return f"{'✅' if ok else '⏳'} {label}"
    st.markdown(f"**Workflow:** {badge(bool(W['research']),'Research')} → {badge(bool(W['plan']),'Plan')} → {badge(bool(W['assets']),'Assets')}")

    b1, b2, b3, b4 = st.columns([1,1,1,1])

    # ---- Research ----
    if b1.button("1) Research", key="wk_research"):
        with st.spinner("Researching…"):
            raw = r2_make_research(goal, audience, constraints, date_context)
            W["research"] = normalize_r2_research(raw, f"{goal}\n{audience}\n{constraints}")
        r = W["research"]
        topics = _safe_get(r, "topics", default=[]) or []
        risks  = _safe_get(r, "risks",  default=[]) or []
        st.success(f"Research completed: identified {len(topics)} topics and {len(risks)} risks.")
        if topics: st.write("Top topics:", ", ".join(map(str, topics[:5])))

    # ---- Plan ----
    if b2.button("2) Plan", key="wk_plan"):
        with st.spinner("Planning…"):
            raw = r2_make_plan(goal, audience, constraints, date_context)
            W["plan"] = normalize_r2_plan(raw)
        p = W["plan"]
        agenda     = _safe_get(p, "agenda", default=[]) or []
        milestones = _safe_get(p, "milestones", default=[]) or []
        metrics    = _safe_get(p, "success_metrics", default=[]) or []
        st.success(f"Plan created: {len(agenda)} agenda items, {len(milestones)} milestones, and {len(metrics)} success metrics.")
        if milestones:
            first_title = _safe_get(milestones[0], "title", default="(untitled)")
            first_due   = _safe_get(milestones[0], "due",   default="TBD")
            st.write(f"First milestone: **{first_title}** — due **{first_due}**.")

    # ---- Assets + Google Form ----
    if b3.button("3) Produce Assets", key="wk_assets"):
        with st.spinner("Producing…"):
            raw_assets = r2_make_assets(goal, audience, constraints, W.get("plan"), W.get("research"), date_context)
            W["assets"] = normalize_r2_assets(raw_assets)

            form_info = {}
            try:
                form_info = r2_create_google_form(goal, audience) or {}
            except Exception:
                form_info = {}
            gform_url = form_info.get("responderUrl") or form_info.get("editUrl")
            if gform_url:
                if isinstance(W["assets"], dict):
                    W["assets"]["google_form_url"] = gform_url
                else:
                    setattr(W["assets"], "google_form_url", gform_url)

        a = W["assets"]
        invite = _safe_get(a, "invite_email", "invite", "email")
        poster = _safe_get(a, "poster_text", "poster")
        checklist = _safe_get(a, "checklist")
        pieces = sum(1 for x in [invite, poster, checklist] if x)
        st.success(f"Assets generated: {pieces} content pieces." + (f" Registration form is ready: { _safe_get(a,'google_form_url') }" if _safe_get(a, "google_form_url") else ""))

    # ---- Reset ----
    if b4.button("🧹 Reset", key="wk_reset"):
        W["research"] = W["plan"] = W["assets"] = None
        st.rerun()

    # ---- Research display ----
    if W["research"]:
        r = W["research"]
        st.subheader("🔎 Research")
        st.markdown("**Topics:**")
        for t in _safe_get(r, "topics", default=[]) or []: st.markdown(f"- {t}")
        st.markdown("**Risks:**")
        for rr in _safe_get(r, "risks", default=[]) or []:
            if isinstance(rr, dict):
                st.markdown(f"- {rr.get('risk')} → Mitigation: {rr.get('mitigation')}")
            else:
                st.markdown(f"- {rr}")
        notes = _safe_get(r, "budget_notes")
        if notes: st.markdown("**Budget Notes:**"); st.info(notes)

    # ---- Plan display ----
    if W["plan"]:
        p = W["plan"]
        st.subheader("📅 Plan")
        st.markdown("**Agenda:**")
        for a in _safe_get(p, "agenda", default=[]) or []: st.markdown(f"- {a}")
        milestones = _safe_get(p, "milestones", default=[]) or []
        for i, m in enumerate(milestones, 1):
            due = _safe_get(m, "due")
            try:
                milestone_date = dt.datetime.strptime(str(due), "%Y-%m-%d").date()
                days_from_today = (milestone_date - dt.date.today()).days
                if   days_from_today == 0: txt = " (📍 **TODAY**)"
                elif days_from_today == 1: txt = " (📅 **TOMORROW**)"
                elif days_from_today > 0:  txt = f" (⏰ in {days_from_today} days)"
                else:                      txt = f" (⚠️ {abs(days_from_today)} days overdue)"
            except Exception:
                txt = ""
            title = _safe_get(m, "title", default=f"Milestone {i}")
            st.markdown(f"**Milestone {i}: {title} (Due {due}{txt})**")
            for t in _safe_get(m, "tasks", default=[]) or []:
                desc = _safe_get(t, "desc"); hrs = _safe_get(t, "effort_hrs")
                st.markdown(f" - {desc} ({hrs} hrs)")

        st.markdown("**Success Metrics:**")
        for m in _safe_get(p, "success_metrics", default=[]) or []: st.markdown(f"- {m}")

    # ---- Assets display & downloads ----
    if W["assets"]:
        a = W["assets"]
        st.subheader("📢 Assets")
        inv = _safe_get(a, "invite_email", "invite", "email")
        poster_text = _safe_get(a, "poster_text", "poster")
        checklist = _safe_get(a, "checklist")
        st.write(f"Invite email length: {len(inv.split()) if inv else 0} words.")
        st.write(f"Poster text length: {len(poster_text.split()) if poster_text else 0} words.")
        st.write(f"Checklist items: {len(checklist.splitlines()) if checklist else 0}.")
        st.markdown("**Invite Email:**"); st.code(inv or "")
        st.markdown("**Poster Text:**");  st.code(poster_text or "")
        st.markdown("**Checklist:**");    st.code(checklist or "")

        gform = _safe_get(a, "google_form_url")
        if gform:
            st.markdown("**📋 Registration Form:**")
            st.markdown(f"🔗 [Open Form]({gform})")
            st.text_input("Form URL (copy this):", value=str(gform), key="form_url_copy")

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("invite_email.md", inv or "")
            z.writestr("poster.txt",     poster_text or "")
            z.writestr("checklist.md",   checklist or "")
            context = (f"Workshop Planning Session\nGenerated on: {dt.date.today().strftime('%B %d, %Y')}\n"
                       f"Reference Date: {dt.date.today().strftime('%Y-%m-%d')}\n"
                       f"Day of Week: {dt.date.today().strftime('%A')}\n")
            z.writestr("planning_date_context.txt", context)
            if gform: z.writestr("google_form_url.txt", str(gform))
        st.download_button("⬇️ Download Assets Pack (.zip)", buf.getvalue(), "workshop-assets.zip")

        # Deliver (.ics)
        if ICS_AVAILABLE and W["plan"]:
            cal = Calendar()
            for i, m in enumerate(_safe_get(W["plan"], "milestones", default=[]) or [], 1):
                e = Event()
                e.name = f"Milestone {i}: {_safe_get(m, 'title', default='')}"
                due = _safe_get(m, "due", default="")
                try:
                    dt_obj = dt.datetime.strptime(str(due), "%Y-%m-%d")
                    e.begin = dt_obj.replace(hour=9, minute=0); e.make_all_day()
                except Exception:
                    e.begin = f"{due} 09:00"; e.make_all_day()
                cal.events.add(e)
            st.download_button("📆 Download milestones.ics", str(cal).encode("utf-8"), "workshop-milestones.ics")

# ======================
# Router (sidebar)
# ======================
section = st.sidebar.radio("Choose module", ["🚀 Launch Builder (R1)", "🎤 Workshop Planner (R2)"])
if section.startswith("🚀"):
    render_launch()
else:
    render_workshop()
