# app.py — plain-English Research/Plan, JSON Production, single-file package, fixed GitHub deploy
import io
import re
import zipfile
from datetime import datetime

import streamlit as st

from research import make_research
from planner import make_plan
from production import make_landing_assets, generate_custom_file
from github_client import GitHubClient

st.set_page_config(page_title="Landing Page Builder", page_icon="🚀", layout="wide")


# ---------------------------
# Helpers: parse Markdown → dict (for production.py compatibility)
# ---------------------------
BULLET_PREFIX = ("- ", "• ", "* ")


def _parse_research_markdown(md: str) -> dict:
    """
    Expect sections:
      # Overview
      # Top Competitors   (bullets)
      # Hooks             (bullets)
      # Keywords          (single line, comma-separated)
      # Risks             (bullets)
    Returns dict with keys that production.py expects (hooks, keywords).
    """
    out = {"overview": "", "competitors": [], "hooks": [], "keywords": [], "risks": []}
    current = None

    for raw in md.splitlines():
        line = raw.strip()
        low = line.lower()

        if low.startswith("# overview"):
            current = "overview"
            continue
        if "top competitors" in low and line.startswith("#"):
            current = "competitors"
            continue
        if low.startswith("# hooks"):
            current = "hooks"
            continue
        if low.startswith("# keywords"):
            current = "keywords"
            continue
        if low.startswith("# risks"):
            current = "risks"
            continue

        if not line or line.startswith("#"):
            continue

        if current == "overview":
            out["overview"] += (line + " ")
        elif current in ("competitors", "hooks", "risks"):
            if line.startswith(BULLET_PREFIX) or re.match(r"^\d+[\.\)]\s+", line):
                item = re.sub(r"^(\*|-|•|\d+[\.\)])\s*", "", line).strip()
                if item:
                    out[current].append(item)
        elif current == "keywords":
            parts = [p.strip() for p in line.split(",") if p.strip()]
            out["keywords"].extend(parts)

    out["overview"] = out["overview"].strip()
    return out


def _parse_plan_markdown(md: str, private: bool, license_name: str, add_ci: bool) -> dict:
    """
    Expect sections:
      # One-Line Strategy
      # Milestones
      # Success Metrics
      # Copy Outline       (bullets)
      # Risks & Mitigations
      # Repo Settings
    We only need copy_outline + repo for production.py.
    """
    out = {
        "copy_outline": [],
        "repo": {"private": private, "license": license_name, "add_ci": add_ci},
    }
    current = None

    for raw in md.splitlines():
        line = raw.strip()
        low = line.lower()

        if low.startswith("# copy outline"):
            current = "copy_outline"
            continue
        if low.startswith("# repo settings"):
            current = "repo"
            continue
        if line.startswith("#"):
            current = None
            continue
        if not line:
            continue

        if current == "copy_outline":
            if line.startswith(BULLET_PREFIX) or re.match(r"^\d+[\.\)]\s+", line):
                section = re.sub(r"^(\*|-|•|\d+[\.\)])\s*", "", line).strip().rstrip(" .")
                if section:
                    out["copy_outline"].append(section)
        elif current == "repo":
            if "mit" in low:
                out["repo"]["license"] = "MIT"
            elif "apache" in low:
                out["repo"]["license"] = "Apache-2.0"
            if "ci" in low or "cicd" in low or "ci/cd" in low:
                out["repo"]["add_ci"] = True
            if "public" in low:
                out["repo"]["private"] = False
            if "private" in low:
                out["repo"]["private"] = True

    if not out["copy_outline"]:
        out["copy_outline"] = ["Hero", "Quickstart", "Features", "FAQ", "Footer"]
    return out


# ---------------------------
# Helpers: enforce single-file package for users
# ---------------------------
def inline_assets(files: dict) -> dict:
    """Inline styles.css and script.js into index.html (if present)."""
    html = files.get("index.html", "")
    css = files.pop("styles.css", "")
    js = files.pop("script.js", "")
    if html:
        if css and "</head>" in html:
            html = html.replace("</head>", f"<style>\n{css}\n</style>\n</head>")
        if js and "</body>" in html:
            html = html.replace("</body>", f"<script>\n{js}\n</script>\n</body>")
        files["index.html"] = html
    return files


def enforce_single_file_package(files: dict) -> dict:
    """
    Keep a minimal package for end users:
      - index.html (with inlined CSS/JS)
      - README.md
      - any explicitly requested custom_* files
    Remove everything else (LICENSE, DEPLOY.md, CI workflows, etc.).
    """
    files = inline_assets(files)
    keep = {"index.html", "README.md"}
    keep |= {name for name in list(files.keys()) if name.startswith("custom_")}
    for name in list(files.keys()):
        if name not in keep:
            del files[name]
    return files


# ---------------------------
# Session State
# ---------------------------
if "research_text" not in st.session_state:
    st.session_state.research_text = ""
if "plan_text" not in st.session_state:
    st.session_state.plan_text = ""
if "research_dict" not in st.session_state:
    st.session_state.research_dict = {}
if "plan_dict" not in st.session_state:
    st.session_state.plan_dict = {}
if "files" not in st.session_state:
    st.session_state.files = {}
if "custom_files" not in st.session_state:
    st.session_state.custom_files = []

# ---------------------------
# UI — Inputs
# ---------------------------
st.title("🚀 Landing Page Builder")

groq_key = st.secrets.get("GROQ_API_KEY", "")
github_token = st.secrets.get("GITHUB_TOKEN", "")

if not groq_key:
    st.error("Please add GROQ_API_KEY to .streamlit/secrets.toml")
    st.stop()

st.header("📝 Project Details")
col1, col2 = st.columns(2)

with col1:
    project_brief = st.text_area("What do you want to build?", height=100)
    product_name = st.text_input("Product Name", "MyAPI")
    audience = st.text_input("Target Audience", "Developers")

    st.subheader("Custom Files")
    num_files = st.number_input("How many additional files?", 0, 10, 0)
    if num_files > 0:
        st.session_state.custom_files = []
        for i in range(num_files):
            with st.expander(f"File {i+1}"):
                file_type = st.selectbox(f"Type", ["HTML", "CSS", "JS"], key=f"type_{i}")
                default_name = f"custom_{i+1}.{file_type.lower()}" if file_type else "file.txt"
                file_name = st.text_input("Filename", default_name, key=f"name_{i}")
                file_prompt = st.text_area(
                    "What should this file do?",
                    placeholder="E.g., Create a pricing table with 3 tiers...",
                    key=f"prompt_{i}",
                )
                st.session_state.custom_files.append(
                    {"type": file_type, "name": file_name, "prompt": file_prompt}
                )

with col2:
    st.subheader("GitHub Settings")
    github_owner = st.text_input("Owner (username or org)", st.secrets.get("GITHUB_OWNER", ""))
    repo_name = st.text_input("Repository Name", "landing-page")
    repo_desc = st.text_input("Description", "Auto-generated landing page")
    private = st.checkbox("Private Repo", True)
    license_name = st.selectbox("License", ["MIT", "Apache-2.0", "None"])
    add_ci = st.checkbox("Add CI/CD")


# ---------------------------
# Research
# ---------------------------
st.header("🔍 Research")
if st.button("Start Research"):
    with st.spinner("Researching..."):
        research_text = make_research(groq_key, product_name, audience, project_brief)
        st.session_state.research_text = research_text
        st.session_state.research_dict = _parse_research_markdown(research_text)

if st.session_state.research_text:
    st.markdown(st.session_state.research_text)

# ---------------------------
# Plan
# ---------------------------
st.header("📋 Planning")
if st.button("Create Plan", disabled=not bool(st.session_state.research_text)):
    with st.spinner("Planning..."):
        plan_text = make_plan(
            groq_key,
            product_name,
            audience,
            project_brief,
            st.session_state.research_text,  # pass readable research text
            repo_name,
            repo_desc,
            private,
            license_name,
            add_ci,
        )
        st.session_state.plan_text = plan_text
        st.session_state.plan_dict = _parse_plan_markdown(plan_text, private, license_name, add_ci)

if st.session_state.plan_text:
    st.markdown(st.session_state.plan_text)

# ---------------------------
# Production
# ---------------------------
st.header("🏗️ Production")
if st.button("Generate Files", disabled=not bool(st.session_state.plan_text)):
    with st.spinner("Generating landing page..."):
        # Base files from production (expects dicts)
        st.session_state.files = make_landing_assets(
            groq_key,
            product_name,
            audience,
            project_brief,
            st.session_state.research_dict,
            st.session_state.plan_dict,
        )

        # Custom files
        if st.session_state.custom_files:
            with st.spinner("Generating custom files..."):
                for custom_file in st.session_state.custom_files:
                    if custom_file["prompt"]:
                        content = generate_custom_file(
                            groq_key,
                            custom_file["type"],
                            custom_file["prompt"],
                            product_name,
                            st.session_state.research_dict,
                        )
                        st.session_state.files[custom_file["name"]] = content

        # Always ship a minimal, single-file package (+ README + custom_*)
        st.session_state.files = enforce_single_file_package(st.session_state.files)

# ---------------------------
# File viewer + Download/ZIP + Preview
# ---------------------------
if st.session_state.files:
    st.subheader("📁 Generated Files")
    cols = st.columns(3)
    file_names = list(st.session_state.files.keys())

    for idx, file_name in enumerate(file_names):
        with cols[idx % 3]:
            if st.button(f"📄 {file_name}", key=f"view_{file_name}"):
                st.session_state.selected_file = file_name

    if "selected_file" in st.session_state:
        selected_file = st.session_state.selected_file
        st.subheader(f"Viewing: {selected_file}")

        file_content = st.session_state.files[selected_file]
        if selected_file.endswith(".html"):
            lang = "html"
        elif selected_file.endswith(".css"):
            lang = "css"
        elif selected_file.endswith(".js"):
            lang = "javascript"
        else:
            lang = "markdown"

        st.code(file_content, language=lang, line_numbers=True)

        col1, col2 = st.columns(2)
        with col1:
            st.download_button(
                f"⬇️ Download {selected_file}",
                file_content,
                selected_file,
                key=f"dl_{selected_file}",
            )

        with col2:
            if st.button(f"✏️ Edit {selected_file}"):
                st.session_state[f"editing_{selected_file}"] = True

        if st.session_state.get(f"editing_{selected_file}"):
            edited_content = st.text_area(
                "Edit content:",
                value=file_content,
                height=400,
                key=f"editor_{selected_file}",
            )
            if st.button("Save Changes", key=f"save_{selected_file}"):
                st.session_state.files[selected_file] = edited_content
                st.session_state[f"editing_{selected_file}"] = False
                st.rerun()

    st.divider()
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as zf:
        for name, content in st.session_state.files.items():
            zf.writestr(name, content)
    zip_buffer.seek(0)

    col1, col2 = st.columns(2)
    with col1:
        st.download_button(
            "📦 Download All Files (ZIP)",
            zip_buffer.getvalue(),
            f"landing-page-{datetime.now().strftime('%Y%m%d-%H%M%S')}.zip",
            "application/zip",
        )

    with col2:
        if st.button("👁️ Preview Landing Page"):
            html_content = st.session_state.files.get("index.html", "")
            if html_content:
                st.components.v1.html(html_content, height=600, scrolling=True)

# ---------------------------
# Deploy to GitHub
# ---------------------------
st.header("🚀 Deploy")
if st.button("Push to GitHub", disabled=not github_token or not st.session_state.files):
    try:
        gh = GitHubClient(github_token)

        me = gh.get_authenticated_user()["login"]
        owner_for_creation = (github_owner or "").strip() or me

        # Create repo with an initial commit to avoid branch conflicts
        # gh.create_repo(repo_name, private, repo_desc, auto_init=True, owner=owner_for_creation)
        gh.create_repo(repo_name, private, repo_desc, auto_init=True, owner=owner_for_creation)


        # Push files to 'main'
        gh.upsert_files(owner_for_creation, repo_name, "main", st.session_state.files)

        st.success(f"✅ Deployed to github.com/{owner_for_creation}/{repo_name}")
        st.balloons()
    except Exception as e:
        st.error(str(e))
