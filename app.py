# app.py - Unified AI Project Hub with consistent theming (fixed Feature 3 display + cleaned call flow)
import streamlit as st
import io
import zipfile
import json
import tempfile
import os
from datetime import datetime
import datetime as dt

# --- Optional imports ---
try:
    from forms_api import create_google_form  # used by Workshop (optional)
except Exception:
    def create_google_form(*args, **kwargs):
        return None

try:
    from producer_blog import create_docx_file, create_pdf_file
except Exception:
    create_docx_file = None
    create_pdf_file = None

# =========================
# Page configuration & Theme
# =========================
st.set_page_config(
    page_title="ActionPlanner AI",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
<style>
    /* Main theme colors */
    :root {
        --primary: #2E86AB;
        --secondary: #A23B72;
        --success: #28a745;
        --warning: #ffc107;
        --info: #17a2b8;
        --dark: #2c3e50;
        --light: #f8f9fa;
    }

    /* Consistent button styling */
    .stButton > button {
        border-radius: 8px;
        font-weight: 600;
        transition: all 0.3s ease;
    }
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    }

    /* Tab styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: #f0f2f6;
        padding: 4px;
        border-radius: 12px;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px;
        padding: 8px 16px;
        font-weight: 500;
    }
    .stTabs [aria-selected="true"] {
        background-color: white;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }

    /* Cards */
    .info-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 1.5rem;
        border-radius: 12px;
        margin-bottom: 1.5rem;
    }
    .feature-card {
        background: white;
        padding: 1.5rem;
        border-radius: 12px;
        border: 1px solid #e0e0e0;
        margin-bottom: 1rem;
        transition: transform 0.3s ease;
    }
    .feature-card:hover {
        transform: translateY(-4px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
    }

    /* Progress chips */
    .progress-step {
        display: inline-block;
        padding: 0.5rem 1rem;
        border-radius: 20px;
        margin: 0 0.25rem;
        font-weight: 500;
    }
    .progress-step.active { background: var(--primary); color: white; }
    .progress-step.completed { background: var(--success); color: white; }

    /* File grid */
    .file-item {
        padding: 0.75rem;
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        cursor: pointer;
        transition: all 0.3s ease;
    }
    .file-item:hover { background: #f0f2f6; border-color: var(--primary); }
</style>
""",
    unsafe_allow_html=True,
)

# =========================
# Session State
# =========================
if "launch" not in st.session_state:
    st.session_state.launch = {
        "project_data": {},
        "research": {},
        "plan": {},
        "files": {},
        "custom_files": [],
        "file_count": 0,
    }

if "workshop" not in st.session_state:
    st.session_state.workshop = {
        "research": None,
        "plan": None,
        "assets": None,
        "date": None,
        "days_until": None,
    }

if "research_blog" not in st.session_state:
    st.session_state.research_blog = {
        "research_content": None,
        "letter_structure": None,
        "blog_structure": None,
        "final_assets": None,
    }

# =========================
# Dynamic imports with fallbacks
# =========================
try:
    # Launch Builder imports
    from research import make_research
    from planner import make_plan
    from production import make_landing_assets, generate_custom_file
    from github_client import GitHubClient
except Exception:
    def make_research(*args, **kwargs):
        return {}

    def make_plan(*args, **kwargs):
        return {}

    def make_landing_assets(*args, **kwargs):
        return {}

    def generate_custom_file(*args, **kwargs):
        return ""

    class GitHubClient:
        def __init__(self, *args):
            pass
        def get_authenticated_user(self):
            return {"login": "me"}
        def create_repo(self, *a, **k):
            return True
        def upsert_files(self, *a, **k):
            return True

try:
    # Workshop imports
    from researcher_work import make_workshop_research
    from planner_work import make_workshop_plan
    from producer_work import make_workshop_assets
except Exception:
    def make_workshop_research(*args, **kwargs):
        return None

    def make_workshop_plan(*args, **kwargs):
        return None

    def make_workshop_assets(*args, **kwargs):
        return None

try:
    # Research Letter & Blog imports
    from researcher_blog import make_research_for_letter
    from planner_blog import make_research_letter, make_blog_post
    from producer_blog import generate_final_assets  # (create_docx_file/create_pdf_file handled above)
except Exception:
    def make_research_for_letter(*args, **kwargs):
        return None

    def make_research_letter(*args, **kwargs):
        return None

    def make_blog_post(*args, **kwargs):
        return None

    def generate_final_assets(*args, **kwargs):
        return None

# =========================
# Secrets
# =========================
openai_key = st.secrets.get("OPENAI_API_KEY", "")
github_token = st.secrets.get("GITHUB_TOKEN", "")

if not openai_key:
    st.error("⚠️ Please add GROQ_API_KEY to .streamlit/secrets.toml")
    st.stop()

# =========================
# Header
# =========================
st.markdown(
    """
<div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 2rem; border-radius: 12px; margin-bottom: 2rem; text-align: center;">
  <h1 style="color: white; margin: 0;">🚀 Action_Planner AI</h1>
  <p style="color: rgba(255,255,255,0.9); margin-top: 0.5rem;">From Idea to Launch: Automating Your Creative Vision</p>
</div>
""",
    unsafe_allow_html=True,
)

# =========================
# Sidebar
# =========================
with st.sidebar:
    st.markdown("### 🎯 Select Feature")
    feature = st.radio(
        "Choose your tool:",
        [
            "🚀 Landing Page Builder",
            "🎤 Workshop Planner",
            "📬 Research Letter & Blog",
        ],
        label_visibility="collapsed",
    )

    st.markdown("---")
    st.markdown("### 📊 Quick Stats")
    if feature == "🚀 Landing Page Builder":
        files_count = len(st.session_state.launch.get("files", {}))
        st.metric("Files Generated", files_count)
    elif feature == "🎤 Workshop Planner":
        has_plan = "✅" if st.session_state.workshop.get("plan") else "❌"
        st.metric("Plan Ready", has_plan)
    else:
        has_final = st.session_state.research_blog.get("final_assets")
        if has_final:
            # any content?
            if isinstance(has_final, dict):
                has_content = bool(
                    has_final.get("letter_content") or has_final.get("blog_content")
                )
            else:
                has_content = bool(
                    getattr(has_final, "letter_content", None)
                    or getattr(has_final, "blog_content", None)
                )
            has_content = "✅" if has_content else "❌"
        else:
            has_content = "❌"
        st.metric("Content Ready", has_content)

# =========================
# Feature 1: Landing Page Builder
# =========================
if feature == "🚀 Landing Page Builder":
    st.markdown(
        """
    <div class="info-card">
        <h3>🚀 Landing Page Builder</h3>
        <p>Create professional landing pages with AI-powered research, planning, and code generation</p>
    </div>
    """,
        unsafe_allow_html=True,
    )

    tabs = st.tabs(["📝 Configure", "🔍 Research", "📋 Plan", "🏗️ Build", "🚀 Deploy"])

    # 1) Configure
    with tabs[0]:
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### Project Details")
            project_brief = st.text_area(
                "What do you want to build?",
                height=100,
                placeholder="Describe your landing page idea...",
                key="project_brief",
            )
            product_name = st.text_input(
                "Product Name", placeholder="MyAwesomeAPI", key="product_name"
            )
            audience = st.text_input(
                "Target Audience", placeholder="Developers, Startups", key="audience"
            )

            # Custom files config
            st.markdown("#### Custom Files")
            if "file_count" not in st.session_state:
                st.session_state.file_count = 0

            col_a, col_b = st.columns([3, 1])
            with col_a:
                st.write(f"Files configured: {st.session_state.file_count}")
            with col_b:
                if st.button("➕ Add", key="add_file_btn"):
                    st.session_state.file_count += 1

            custom_configs = []
            for i in range(st.session_state.file_count):
                with st.expander(f"File {i+1}", expanded=False):
                    fcol1, fcol2, fcol3 = st.columns([2, 3, 1])
                    with fcol1:
                        file_type = st.selectbox(
                            "Type", ["HTML", "CSS", "JS"], key=f"ftype_{i}"
                        )
                    with fcol2:
                        file_name = st.text_input(
                            "Name", f"custom_{i+1}.{file_type.lower()}", key=f"fname_{i}"
                        )
                    with fcol3:
                        if st.button("🗑️", key=f"del_{i}"):
                            st.session_state.file_count -= 1
                            st.rerun()

                    file_prompt = st.text_area(
                        "Description",
                        placeholder=f"What should this {file_type} file do?",
                        key=f"fprompt_{i}",
                        height=60,
                    )
                    custom_configs.append(
                        {"type": file_type, "name": file_name, "prompt": file_prompt}
                    )

            st.session_state.launch["custom_files"] = custom_configs

        with col2:
            st.markdown("#### GitHub Settings")
            github_owner = st.text_input(
                "GitHub Username/Org", value=st.secrets.get("GITHUB_OWNER", ""), key="github_owner"
            )
            repo_name = st.text_input("Repository Name", "landing-page", key="repo_name")
            repo_desc = st.text_input(
                "Description", "AI-generated landing page", key="repo_desc"
            )

            st.divider()
            private = st.checkbox("Private Repository", True, key="private")
            license = st.selectbox("License", ["MIT", "Apache-2.0", "None"], key="license")
            add_ci = st.checkbox("Add CI/CD", False, key="add_ci")

            if st.button("💾 Save Configuration", type="primary", use_container_width=True):
                st.session_state.launch["project_data"] = {
                    "brief": project_brief,
                    "product": product_name,
                    "audience": audience,
                    "github_owner": github_owner,
                    "repo_name": repo_name,
                    "repo_desc": repo_desc,
                    "private": private,
                    "license": license,
                    "add_ci": add_ci,
                }
                st.success("✅ Configuration saved!")

    # 2) Research
    with tabs[1]:
        data = st.session_state.launch["project_data"]
        if not data.get("brief") or not data.get("product"):
            st.warning("⚠️ Please complete configuration first")
        else:
            if st.button("🔍 Start Research", type="primary", use_container_width=True):
                with st.spinner("Analyzing market..."):
                    research = make_research(
                        openai_key, data["product"], data.get("audience", ""), data["brief"]
                    )
                    st.session_state.launch["research"] = research
                    st.success("✅ Research complete!")

            research_data = st.session_state.launch.get("research")
            if research_data:
                # If model returned Markdown (string), render it directly.
                if isinstance(research_data, str):
                    st.markdown("#### 🔍 Research (Markdown)")
                    st.markdown(research_data)
                else:
                    # Old structured dict path
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown("#### 🎯 Hooks")
                        for hook in (research_data.get("hooks", []) or []):
                            st.write(f"• {hook}")

                        st.markdown("#### 🏆 Competitors")
                        for comp in (research_data.get("competitors", []) or []):
                            if isinstance(comp, dict):
                                st.write(f"**{comp.get('name')}**: {comp.get('angle')}")
                            else:
                                st.write(f"• {comp}")

                    with col2:
                        st.markdown("#### 🔑 Keywords")
                        keys = research_data.get("keywords", []) or []
                        if keys:
                            st.info(", ".join(keys))

                        st.markdown("#### ⚠️ Risks")
                        for risk in (research_data.get("risks", []) or []):
                            if isinstance(risk, dict):
                                with st.expander(risk.get("risk", "Risk")):
                                    st.write(risk.get("mitigation", ""))
                            else:
                                st.write(f"• {risk}")

    # 3) Plan
    # 3) Plan
    with tabs[2]:
        data = st.session_state.launch["project_data"]
        if data.get("brief"):
            if st.button("📋 Create Plan", type="primary", use_container_width=True):
                with st.spinner("Planning..."):
                    plan = make_plan(
                        openai_key,
                        data.get("product", "Product"),
                        data.get("audience", "Developers"),
                        data["brief"],
                        st.session_state.launch.get("research", {}),
                        data.get("repo_name", "landing-page"),
                        data.get("repo_desc", "Landing page"),
                        data.get("private", True),
                        data.get("license", "MIT"),
                        data.get("add_ci", False),
                    )
                    st.session_state.launch["plan"] = plan
                    st.success("✅ Plan created!")

            plan_data = st.session_state.launch.get("plan")
            if plan_data:
                # If model returned Markdown (string), render it directly.
                if isinstance(plan_data, str):
                    st.markdown("#### 📋 Plan (Markdown)")
                    st.markdown(plan_data)
                else:
                    # Old structured dict path
                    st.markdown("#### 📅 Milestones")
                    for m in (plan_data.get("milestones", []) or []):
                        title = m.get("title", "Milestone")
                        due_days = m.get("due_days", "")
                        with st.expander(f"{title} - {due_days} days"):
                            for task in (m.get("tasks", []) or []):
                                st.write(f"• {task.get('desc')} ({task.get('effort_hrs')}h)")

                    st.markdown("#### 📊 Success Metrics")
                    for metric in (plan_data.get("success_metrics", []) or []):
                        st.success(metric)
        else:
            st.warning("⚠️ Please complete configuration first")

    # 4) Build
    with tabs[3]:
        data = st.session_state.launch["project_data"]
        if data.get("brief"):
            if st.button("🏗️ Generate Files", type="primary", use_container_width=True):
                with st.spinner("Generating..."):
                    files = make_landing_assets(
                        openai_key,
                        data.get("product", "Product"),
                        data.get("audience", "Developers"),
                        data["brief"],
                        st.session_state.launch.get("research", {}),
                        st.session_state.launch.get("plan", {}),
                    ) or {}

                    # Custom requested files
                    for custom in st.session_state.launch.get("custom_files", []):
                        if custom.get("prompt"):
                            content = generate_custom_file(
                                openai_key,
                                custom["type"],
                                custom["prompt"],
                                data.get("product", "Product"),
                                st.session_state.launch.get("research", {}),
                            )
                            files[custom["name"]] = content

                    st.session_state.launch["files"] = files
                    st.success(f"✅ Generated {len(files)} files!")

            if st.session_state.launch["files"]:
                st.markdown("#### 📁 Generated Files")
                file_names = list(st.session_state.launch["files"].keys())
                selected_file = st.selectbox("Select file:", [""] + file_names)
                if selected_file:
                    file_content = st.session_state.launch["files"][selected_file]
                    col1, col2, col3 = st.columns([1, 1, 4])
                    with col1:
                        st.download_button("📥 Download", file_content, selected_file)
                    with col2:
                        if st.button("✏️ Edit", key=f"edit_{selected_file}"):
                            st.session_state[f"editing_{selected_file}"] = True

                    if st.session_state.get(f"editing_{selected_file}"):
                        edited = st.text_area(
                            "Edit:", file_content, height=400, key=f"editor_{selected_file}"
                        )
                        if st.button("Save", key=f"save_{selected_file}"):
                            st.session_state.launch["files"][selected_file] = edited
                            del st.session_state[f"editing_{selected_file}"]
                            st.success("Saved!")
                            st.rerun()
                    else:
                        lang = (
                            "html"
                            if selected_file.endswith(".html")
                            else "css"
                            if selected_file.endswith(".css")
                            else "javascript"
                            if selected_file.endswith(".js")
                            else "text"
                        )
                        st.code(file_content, language=lang, line_numbers=True)

                # ZIP + Preview
                st.divider()
                col1, col2 = st.columns(2)
                with col1:
                    zip_buffer = io.BytesIO()
                    with zipfile.ZipFile(zip_buffer, "w") as zf:
                        for name, content in st.session_state.launch["files"].items():
                            zf.writestr(name, content)
                    zip_buffer.seek(0)
                    st.download_button(
                        "📦 Download All (ZIP)",
                        zip_buffer.getvalue(),
                        f"landing-{datetime.now().strftime('%Y%m%d')}.zip",
                        "application/zip",
                        use_container_width=True,
                    )
                with col2:
                    if st.button("👁️ Preview", use_container_width=True):
                        html_files = [
                            f for f in st.session_state.launch["files"].keys() if f.endswith(".html")
                        ]
                        if html_files:
                            all_css = "".join(
                                [
                                    f"\n/* {f} */\n{st.session_state.launch['files'][f]}\n"
                                    for f in st.session_state.launch["files"].keys()
                                    if f.endswith(".css")
                                ]
                            )
                            all_js = "".join(
                                [
                                    f"\n// {f}\n{st.session_state.launch['files'][f]}\n"
                                    for f in st.session_state.launch["files"].keys()
                                    if f.endswith(".js")
                                ]
                            )
                            for html_file in html_files:
                                html = st.session_state.launch["files"][html_file]
                                if all_css and "</head>" in html:
                                    html = html.replace("</head>", f"<style>{all_css}</style>\n</head>")
                                if all_js and "</body>" in html:
                                    html = html.replace("</body>", f"<script>{all_js}</script>\n</body>")
                                st.subheader(f"Preview: {html_file}")
                                st.components.v1.html(html, height=700, scrolling=True)

    # 5) Deploy
    with tabs[4]:
        if not st.session_state.launch["files"]:
            st.warning("⚠️ No files to deploy")
        elif not github_token:
            st.warning("⚠️ GitHub token not configured")
        else:
            data = st.session_state.launch["project_data"]
            if st.button("🚀 Deploy to GitHub", type="primary", use_container_width=True):
                try:
                    with st.spinner("Deploying..."):
                        gh = GitHubClient(github_token)
                        owner = data.get("github_owner") or gh.get_authenticated_user()[
                            "login"
                        ]
                        gh.create_repo(
                            data.get("repo_name", "landing-page"),
                            data.get("private", True),
                            data.get("repo_desc", "Landing page"),
                            auto_init=True,
                        )
                        gh.upsert_files(
                            owner,
                            data.get("repo_name", "landing-page"),
                            "main",
                            st.session_state.launch["files"],
                        )
                        st.success(
                            f"✅ Deployed to github.com/{owner}/{data.get('repo_name')}"
                        )
                        st.balloons()
                except Exception as e:
                    st.error(f"Error: {str(e)}")

# =========================
# Feature 2: Workshop Planner
# =========================
if feature == "🎤 Workshop Planner":
    st.markdown(
        """
    <div class="info-card">
        <h3>🎤 Workshop Planner</h3>
        <p>Plan and organize workshops with AI-generated schedules, materials, and registration forms</p>
    </div>
    """,
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns(2)
    with col1:
        goal = st.text_input("Workshop Goal", "1-day AI workshop")
        audience = st.text_input("Target Audience", "high-school students")
        workshop_date = st.date_input(
            "Workshop Date",
            value=dt.date.today() + dt.timedelta(days=10),
            min_value=dt.date.today(),
            help="Select when the workshop will be held",
        )
    with col2:
        constraints = st.text_area("Constraints", "budget < $200; 25 attendees")
        days_until = (workshop_date - dt.date.today()).days
        if days_until > 0:
            st.info(f"📅 Workshop in {days_until} days")
        elif days_until == 0:
            st.warning("📅 Workshop is today!")
        else:
            st.error(f"📅 Workshop date is in the past ({abs(days_until)} days ago)")
        st.session_state.workshop["date"] = workshop_date
        st.session_state.workshop["days_until"] = days_until

    full_goal = f"{goal} in {days_until} days" if days_until > 0 else goal

    # Workflow buttons
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        if st.button("🔍 Research", type="primary", use_container_width=True):
            with st.spinner("Researching..."):
                date_context = (
                    f"Today is {dt.date.today()}. The workshop is scheduled for {workshop_date}."
                )
                research = make_workshop_research(
                    full_goal, audience, constraints, date_context
                )
                st.session_state.workshop["research"] = research
                st.success("✅ Research complete!")
    with c2:
        if st.button("📋 Plan", type="primary", use_container_width=True):
            with st.spinner("Planning..."):
                date_context = (
                    f"Today is {dt.date.today()}. The workshop is scheduled for {workshop_date}."
                )
                plan = make_workshop_plan(full_goal, audience, constraints, date_context)
                st.session_state.workshop["plan"] = plan
                st.success("✅ Plan created!")
    with c3:
        if st.button("🎨 Generate Assets", type="primary", use_container_width=True):
            with st.spinner("Generating..."):
                date_context = (
                    f"Today is {dt.date.today()}. The workshop is scheduled for {workshop_date}."
                )
                assets = make_workshop_assets(
                    full_goal,
                    audience,
                    constraints,
                    st.session_state.workshop.get("plan"),
                    st.session_state.workshop.get("research"),
                    date_context,
                )
                st.session_state.workshop["assets"] = assets
                st.success("✅ Assets generated!")
    with c4:
        if st.button("🔄 Reset", use_container_width=True):
            st.session_state.workshop = {
                "research": None,
                "plan": None,
                "assets": None,
                "date": None,
                "days_until": None,
            }
            st.rerun()

    # Research results
    if st.session_state.workshop.get("research"):
        st.markdown("#### 🔍 Research Results")
        research_data = st.session_state.workshop["research"]
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Topics:**")
            topics = (
                research_data.get("topics", [])
                if isinstance(research_data, dict)
                else getattr(research_data, "topics", [])
            )
            for topic in topics[:5]:
                st.write(f"• {topic}")
        with col2:
            st.markdown("**Risks:")
            risks = (
                research_data.get("risks", [])
                if isinstance(research_data, dict)
                else getattr(research_data, "risks", [])
            )
            for risk in risks[:3]:
                if isinstance(risk, dict):
                    st.write(f"• {risk.get('risk', risk)}")
                else:
                    st.write(f"• {risk}")

    # Plan results
    if st.session_state.workshop.get("plan"):
        st.markdown("#### 📋 Plan Details")
        plan_data = st.session_state.workshop["plan"]
        agenda = (
            plan_data.get("agenda", [])
            if isinstance(plan_data, dict)
            else getattr(plan_data, "agenda", [])
        )
        milestones = (
            plan_data.get("milestones", [])
            if isinstance(plan_data, dict)
            else getattr(plan_data, "milestones", [])
        )
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Agenda:**")
            for item in agenda[:5]:
                st.write(f"• {item}")
        with col2:
            st.markdown("**Milestones:**")
            for milestone in milestones[:3]:
                if isinstance(milestone, dict):
                    title = milestone.get("title", "")
                    due = milestone.get("due", milestone.get("due_days", ""))
                    if title:
                        txt = f"**{title}**"
                        if due:
                            txt += f" (Due: {due})"
                        st.write(txt)
                        tasks = milestone.get("tasks", [])
                        for task in tasks[:2]:
                            if isinstance(task, dict):
                                task_desc = task.get("desc", task.get("description", ""))
                                if task_desc:
                                    st.write(f"  - {task_desc}")
                            elif isinstance(task, str):
                                st.write(f"  - {task}")
                elif isinstance(milestone, str):
                    st.write(f"• {milestone}")

    # Assets (GUARDED: only render when available)
    if st.session_state.workshop.get("assets"):
        st.markdown("#### 📧 Generated Assets")
        assets_data = st.session_state.workshop["assets"]
        # normalize
        if isinstance(assets_data, dict):
            invite = assets_data.get("invite_email", "")
            poster = assets_data.get("poster_text", "")
            checklist = assets_data.get("checklist", "")
            gform = assets_data.get("google_form_url")
        else:
            invite = getattr(assets_data, "invite_email", "")
            poster = getattr(assets_data, "poster_text", "")
            checklist = getattr(assets_data, "checklist", "")
            gform = getattr(assets_data, "google_form_url", None)

        invite = invite.replace("\\n", "\n").replace("\\t", "\t")
        poster = poster.replace("\\n", "\n").replace("\\t", "\t")
        checklist = checklist.replace("\\n", "\n").replace("\\t", "\t")

        tab1, tab2, tab3 = st.tabs(["📧 Invite Email", "📋 Poster", "✅ Checklist"])
        with tab1:
            st.text_area("Invite Email", invite, height=300)
            st.download_button("📥 Download", invite, "invite_email.txt", "text/plain")
        with tab2:
            st.text_area("Poster Text", poster, height=300)
            st.download_button("📥 Download", poster, "poster.txt", "text/plain")
        with tab3:
            st.text_area("Checklist", checklist, height=300)
            st.download_button("📥 Download", checklist, "checklist.txt", "text/plain")

        if gform:
            st.markdown("**📋 Registration Form**")
            st.link_button("Open Google Form", gform)
            st.text_input("Copy form URL:", value=str(gform), key="form_url_copy")

        st.divider()
        # Build ZIP with all assets
        ws = st.session_state.get("workshop", {})
        ws_date = ws.get("date")
        ws_days = ws.get("days_until")
        ws_date_txt = ws_date.strftime("%Y-%m-%d") if isinstance(ws_date, dt.date) else "N/A"
        ws_days_txt = str(ws_days) if isinstance(ws_days, int) else "N/A"

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            zf.writestr("invite_email.txt", invite)
            zf.writestr("poster.txt", poster)
            zf.writestr("checklist.txt", checklist)
            zf.writestr(
                "workshop_info.txt",
                f"Workshop Date: {ws_date_txt}\nDays until workshop: {ws_days_txt}",
            )
            if gform:
                zf.writestr("google_form_url.txt", str(gform))
        zip_buffer.seek(0)
        st.download_button(
            "📦 Download All Assets",
            zip_buffer.getvalue(),
            f"workshop-assets-{ws_date_txt}.zip",
            "application/zip",
        )

# =========================
# Helper for Feature 3 inline rendering
# =========================

def _render_research_outputs(assets_data):
    """Normalize and render Research Letter & Blog outputs immediately inline.
    Shows tabs + downloads and success message. Safe with dicts/Pydantic objects/objects.
    """
    if assets_data is None:
        return

    # Normalize to dict-like
    if hasattr(assets_data, "model_dump"):
        assets = assets_data.model_dump()
    elif hasattr(assets_data, "dict"):
        assets = assets_data.dict()
    else:
        assets = assets_data

    # Extract
    if isinstance(assets, dict):
        letter_content = str(
            assets.get("letter_content")
            or assets.get("letter")
            or assets.get("email_text")
            or ""
        )
        blog_content = str(
            assets.get("blog_content")
            or assets.get("blog")
            or assets.get("post_markdown")
            or ""
        )
    else:
        letter_content = str(
            getattr(assets_data, "letter_content", "")
            or getattr(assets_data, "letter", "")
            or getattr(assets_data, "email_text", "")
        )
        blog_content = str(
            getattr(assets_data, "blog_content", "")
            or getattr(assets_data, "blog", "")
            or getattr(assets_data, "post_markdown", "")
        )

    # Properly unescape literal sequences (do NOT strip real newlines)
    if letter_content:
        letter_content = letter_content.replace("\\n", "\n").replace("\\t", "\t")
    if blog_content:
        blog_content = blog_content.replace("\\n", "\n").replace("\\t", "\t")

    # Cleanup: remove noisy prefixes and fix headings like "##Heading" -> "## Heading"
    import re
    def _clean_markdown(md: str) -> str:
        if not md:
            return ""
        md = re.sub(r"^\s*#{1,6}\s*OUTPUT\s+[AB]:.*\n", "", md, flags=re.I|re.M)
        md = re.sub(r"^(#{1,6})([^#\s])", r"\1 \2", md, flags=re.M)
        md = re.sub(r"(?<!\n)\n(#{1,6} )", r"\n\n\1", md)  # ensure blank line before headings
        return md.strip()

    letter_content = _clean_markdown(letter_content)
    blog_content   = _clean_markdown(blog_content)

    if not (letter_content or blog_content):
        st.warning("No content returned from generator.")
        return

    # One-time beautifier CSS (safe to inject here)
    st.markdown(
        """
        <style>
        .md-card{
          background:#fff;border:1px solid #e9eaee;border-radius:14px;
          padding:1.1rem 1.25rem;box-shadow:0 2px 10px rgba(0,0,0,0.04);margin-bottom:1rem;
        }
        .md-card h1,.md-card h2,.md-card h3{margin:0.6rem 0 0.3rem 0;line-height:1.25;}
        .md-card p{margin:0.4rem 0 1rem 0;}
        .md-card ul,.md-card ol{margin:0.25rem 0 1rem 1.25rem;}
        .md-card li{margin:0.2rem 0;}
        </style>
        """,
        unsafe_allow_html=True,
    )

    tab1, tab2 = st.tabs(["📧 Research Letter", "📝 Blog Post"])

    with tab1:
        st.markdown("#### 📧 Research Letter (Email Ready)")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.download_button(
                "📄 Download as TXT",
                letter_content,
                "research_letter.txt",
                "text/plain",
                key="dl_letter_txt",
            )
        with c2:
            if callable(create_docx_file):
                tmp_docx = tempfile.NamedTemporaryFile(delete=False, suffix=".docx").name
                try:
                    create_docx_file(letter_content, tmp_docx)
                    with open(tmp_docx, "rb") as f:
                        st.download_button(
                            "📄 Download as DOCX",
                            f.read(),
                            "research_letter.docx",
                            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            key="dl_letter_docx",
                        )
                finally:
                    try: os.unlink(tmp_docx)
                    except Exception: pass
        with c3:
            if callable(create_pdf_file):
                tmp_pdf = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf").name
                try:
                    create_pdf_file(letter_content, tmp_pdf)
                    with open(tmp_pdf, "rb") as f:
                        st.download_button(
                            "📑 Download as PDF",
                            f.read(),
                            "research_letter.pdf",
                            "application/pdf",
                            key="dl_letter_pdf",
                        )
                finally:
                    try: os.unlink(tmp_pdf)
                    except Exception: pass

        # Formatted / Raw toggle
        view_mode_letter = st.radio(
            "Letter view", ["Formatted", "Raw"], horizontal=True, key="letter_view_mode"
        )
        if view_mode_letter == "Formatted":
            st.markdown("<div class='md-card'>", unsafe_allow_html=True)
            st.markdown(letter_content, unsafe_allow_html=False)
            st.markdown("</div>", unsafe_allow_html=True)
        else:
            st.text_area("Letter Content (raw)", letter_content, height=420, key="letter_raw")

    with tab2:
        st.markdown("#### 📝 Blog Post (Web Ready)")
        st.download_button(
            "💾 Download Blog Content",
            blog_content,
            "blog_post.txt",
            "text/plain",
            key="dl_blog_txt",
        )

        view_mode_blog = st.radio(
            "Blog view", ["Formatted", "Raw"], horizontal=True, key="blog_view_mode"
        )
        if view_mode_blog == "Formatted":
            st.markdown("<div class='md-card'>", unsafe_allow_html=True)
            st.markdown(blog_content, unsafe_allow_html=False)
            st.markdown("</div>", unsafe_allow_html=True)
        else:
            st.text_area("Blog Content (raw)", blog_content, height=420, key="blog_raw")

    st.success("🎉 Research Letter and Blog Post ready for use!")
    st.balloons()


# =========================
# Feature 3: Research Letter & Blog (FIXED: always displays after 4th tick)
# =========================
if feature == "📬 Research Letter & Blog":
    st.markdown(
        """
    <div class="info-card">
        <h3>📬 Research Letter & Blog Generator</h3>
        <p>Transform any topic into professional research letters and blog posts with citations</p>
    </div>
    """,
        unsafe_allow_html=True,
    )

    # Inputs
    col1, col2 = st.columns([3, 1])
    with col1:
        research_topic = st.text_input(
            "Research Topic",
            placeholder="e.g., Latest AI trends in healthcare, Blockchain in supply chain...",
            key="research_topic",
        )
        # save for ZIP meta
  
    with col2:
        st.write("")
        st.write("")

    # ---------- Local helpers (Feature 3) ----------
    def _normalize_letter_blog(assets_data):
        """Return (letter_text, blog_text) from various asset shapes (dict/object)."""
        letter_content, blog_content = "", ""
        if assets_data is None:
            return letter_content, blog_content

        # Normalize
        if hasattr(assets_data, "model_dump"):
            assets = assets_data.model_dump()
        elif hasattr(assets_data, "dict"):
            assets = assets_data.dict()
        else:
            assets = assets_data

        if isinstance(assets, dict):
            letter_content = str(
                assets.get("letter_content")
                or assets.get("letter")
                or assets.get("email_text")
                or ""
            )
            blog_content = str(
                assets.get("blog_content")
                or assets.get("blog")
                or assets.get("post_markdown")
                or ""
            )
        else:
            letter_content = str(
                getattr(assets_data, "letter_content", "")
                or getattr(assets_data, "letter", "")
                or getattr(assets_data, "email_text", "")
            )
            blog_content = str(
                getattr(assets_data, "blog_content", "")
                or getattr(assets_data, "blog", "")
                or getattr(assets_data, "post_markdown", "")
            )

        # Properly unescape literals
        if letter_content:
            letter_content = letter_content.replace("\\n", "\n").replace("\\t", "\t")
        if blog_content:
            blog_content = blog_content.replace("\\n", "\n").replace("\\t", "\t")
        return letter_content, blog_content

    def _build_research_zip(letter_text: str, blog_text: str, topic: str):
        """Create a ZIP bytes payload of outputs."""
        import io, zipfile
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            if letter_text:
                zf.writestr("research_letter.txt", letter_text)
            if blog_text:
                zf.writestr("blog_post.txt", blog_text)
            meta = f"Topic: {topic or 'N/A'}\nGenerated: {dt.date.today()}\n"
            zf.writestr("meta.txt", meta)
        buf.seek(0)
        return buf.getvalue()

    # Generate button + 4-step flow
    if st.button("🚀 Generate Research Content", type="primary", use_container_width=True):
        if not research_topic:
            st.error("Please enter a research topic!")
        else:
            date_context = f"Today's date is {dt.date.today().strftime('%Y-%m-%d')}"
            try:
                with st.spinner("Step 1/4: Researching topic..."):
                    research_content = make_research_for_letter(research_topic, date_context)
                    st.session_state.research_blog["research_content"] = research_content
                    st.success("✅ Research completed")

                with st.spinner("Step 2/4: Planning letter structure..."):
                    letter_structure = make_research_letter(
                        research_topic, research_content, date_context
                    )
                    st.session_state.research_blog["letter_structure"] = letter_structure
                    st.success("✅ Letter planned")

                with st.spinner("Step 3/4: Planning blog structure..."):
                    blog_structure = make_blog_post(
                        research_topic, research_content, date_context
                    )
                    st.session_state.research_blog["blog_structure"] = blog_structure
                    st.success("✅ Blog planned")

                with st.spinner("Step 4/4: Generating final content..."):
                    final_assets = generate_final_assets(
                        research_topic, letter_structure, blog_structure, date_context
                    )
                    st.session_state.research_blog["final_assets"] = final_assets

                # Build ZIP directly from whatever came back (download-first UX)
                letter_text, blog_text = _normalize_letter_blog(final_assets)
                zip_bytes = _build_research_zip(letter_text, blog_text, research_topic)

                st.success("✅ Content generated!")
                st.download_button(
                    "📦 Download Research Pack (ZIP)",
                    zip_bytes,
                    file_name=f"research_pack_{dt.date.today().strftime('%Y%m%d')}.zip",
                    mime="application/zip",
                    use_container_width=True,
                    key="zip_download_inline",
                )

            except Exception as e:
                st.error(f"Generation failed: {str(e)}")

    # --- DISPLAY (always runs while in this feature) ---
    assets_data = st.session_state.research_blog.get("final_assets")
    if assets_data:
        # Show content inline
        _render_research_outputs(assets_data)

        # Also offer the ZIP download
        lt, bt = _normalize_letter_blog(assets_data)
        zip_bytes = _build_research_zip(lt, bt, research_topic)
        st.download_button(
            "📦 Download Research Pack (ZIP)",
            zip_bytes,
            file_name=f"research_pack_{dt.date.today().strftime('%Y%m%d')}.zip",
            mime="application/zip",
            use_container_width=True,
            key="zip_download_persistent",
        )
    else:
        st.info("Run the generator above to produce a research letter, blog post, and ZIP bundle.")


# =========================
# Footer
# =========================
st.markdown("---")
st.markdown(
    """
<div style="text-align: center; padding: 2rem; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 12px; color: white;">
  <h3 style="margin: 0;">AI Project Hub</h3>
  <p style="margin: 0.5rem 0 0 0; opacity: 0.9;">Landing Pages • Workshop Planning • Research Content</p>
</div>
""",
    unsafe_allow_html=True,
)
