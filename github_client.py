# github_client.py — simplify: no branch creation, always push to default branch
import base64
import json
import os
from typing import Dict, Optional

import requests

API = "https://api.github.com"
HEADERS_BASE = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}


class GitHubClient:
    def __init__(self, token: Optional[str] = None, user_agent: str = "landing-builder/1.0"):
        self.token = token or os.getenv("GITHUB_TOKEN")
        if not self.token:
            raise RuntimeError("Missing GitHub token (set GITHUB_TOKEN or add to .streamlit/secrets.toml).")
        self.headers = {**HEADERS_BASE, "Authorization": f"Bearer {self.token}", "User-Agent": user_agent}
        self._me: Optional[dict] = None

    # ---------- Identity ----------
    def get_authenticated_user(self) -> dict:
        if self._me is None:
            r = requests.get(f"{API}/user", headers=self.headers, timeout=30)
            r.raise_for_status()
            self._me = r.json()
        return self._me

    def get_account_type(self, owner: str) -> Optional[str]:
        """Return 'User' or 'Organization' (or None if not found)."""
        r = requests.get(f"{API}/users/{owner}", headers=self.headers, timeout=30)
        if r.status_code == 200:
            return r.json().get("type")
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return None

    # ---------- Repos ----------
    def create_repo(
        self,
        name: str,
        private: bool = True,
        description: str = "",
        auto_init: bool = False,
        owner: Optional[str] = None,
    ) -> dict:
        """
        Create a repo under the authenticated user or an org.
        - If owner is None or equals the authenticated user -> POST /user/repos
        - Else if owner is an Organization                  -> POST /orgs/{owner}/repos
        - Else (owner is another user)                      -> not allowed by PAT
        """
        me = self.get_authenticated_user()["login"]
        payload = {"name": name, "private": private, "description": description, "auto_init": auto_init}

        if owner is None or owner == me:
            url = f"{API}/user/repos"
        else:
            acct_type = self.get_account_type(owner)
            if acct_type == "Organization":
                url = f"{API}/orgs/{owner}/repos"
            elif acct_type == "User":
                raise RuntimeError(
                    f"Cannot create repo under user '{owner}' with a token for '{me}'. "
                    f"Use that user's token or leave owner blank to use '{me}'."
                )
            else:
                raise RuntimeError(f"Owner '{owner}' not found or inaccessible.")

        r = requests.post(url, headers=self.headers, json=payload, timeout=30)
        if r.status_code in (201, 202):
            return r.json()
        if r.status_code in (409, 422):
            info = self.get_repo(owner or me, name)
            if info:
                return info
        raise RuntimeError(f"Create repo failed: {r.status_code} {r.text}")

    def get_repo(self, owner: str, repo: str) -> Optional[dict]:
        r = requests.get(f"{API}/repos/{owner}/{repo}", headers=self.headers, timeout=30)
        if r.status_code == 200:
            return r.json()
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return None

    # ---------- Files (no branch creation; always push to default) ----------
    def _get_default_branch(self, owner: str, repo: str) -> str:
        info = self.get_repo(owner, repo)
        if not info:
            raise RuntimeError(f"Repository {owner}/{repo} not found or inaccessible.")
        return info.get("default_branch", "main")

    def _get_file_sha(self, owner: str, repo: str, path: str, branch: str) -> Optional[str]:
        r = requests.get(
            f"{API}/repos/{owner}/{repo}/contents/{path}",
            headers=self.headers,
            params={"ref": branch},
            timeout=30,
        )
        if r.status_code == 200:
            return r.json().get("sha")
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return None

    def upsert_file(self, owner: str, repo: str, branch: str, path: str, content_str: str, message: str) -> dict:
        url = f"{API}/repos/{owner}/{repo}/contents/{path}"
        sha = self._get_file_sha(owner, repo, path, branch)
        payload = {
            "message": message,
            "content": base64.b64encode(content_str.encode("utf-8")).decode("utf-8"),
            "branch": branch,
        }
        if sha:
            payload["sha"] = sha
        r = requests.put(url, headers=self.headers, json=payload, timeout=30)
        if r.status_code not in (200, 201):
            raise RuntimeError(f"Upload failed for {path}: {r.status_code} {r.text}")
        return r.json()

    def upsert_files(self, owner: str, repo: str, branch: Optional[str], files: Dict[str, str], prefix_msg: str = "Add"):
        """
        Push files to the repo's default branch (ignores the 'branch' arg if provided).
        This avoids any branch creation and eliminates 409s on refs.
        """
        target_branch = self._get_default_branch(owner, repo)
        for path, content in files.items():
            self.upsert_file(owner, repo, target_branch, path, content, f"{prefix_msg} {path}")
