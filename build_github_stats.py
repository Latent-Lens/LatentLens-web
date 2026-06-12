#!/usr/bin/env python3
import json
import os
import re
import sys
import time
import urllib.request
import urllib.parse
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ENV_FILE = ROOT / "misc" / ".env"
REPOSITORIES_HTML = ROOT / "pages" / "repositories.html"

def load_env():
    token = os.environ.get("GITHUB_TOKEN")
    if not token and ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("GITHUB_TOKEN="):
                token = line.split("=", 1)[1].strip()
    return token

def graphql_query(token, query, variables):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "LatentLens-Builder"
        }
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())

def get_total_commits_all_time(token, login):
    url = f"https://api.github.com/search/commits?q=author:{login}"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.cloak-preview",
            "User-Agent": "LatentLens-Builder"
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            return data.get("total_count", 0)
    except Exception as e:
        print(f"Warning: Could not fetch total commits for {login} via search API: {e}")
        return 0

def calculate_lines_of_code(token, login, repos):
    total_added = 0
    total_deleted = 0
    last_year_added = 0
    last_year_deleted = 0
    
    one_year_ago = datetime.now() - timedelta(days=365)
    
    print(f"\n  [Phase 1/2] Waking up GitHub caching workers for {len(repos)} repos...")
    for repo in repos:
        url = f"https://api.github.com/repos/{login}/{repo}/stats/contributors"
        req = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "LatentLens-Builder"
            }
        )
        try:
            with urllib.request.urlopen(req, timeout=5):
                pass
        except Exception:
            pass # Ignore errors during wake-up phase
            
    print(f"\n  [Phase 2/2] Calculating lines of code for {login}...")
    for idx, repo in enumerate(repos, 1):
        url = f"https://api.github.com/repos/{login}/{repo}/stats/contributors"
        
        # We can afford to wait longer because all workers were triggered simultaneously!
        # The user requested up to 20 minutes per repo (1200 seconds = 240 retries * 5s)
        retries = 240
        contributors_data = []
        print(f"    [{idx}/{len(repos)}] Fetching stats for {login}/{repo}...", end=" ")
        sys.stdout.flush()
        
        for attempt in range(1, retries + 1):
            req = urllib.request.Request(
                url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github.v3+json",
                    "User-Agent": "LatentLens-Builder"
                }
            )
            try:
                with urllib.request.urlopen(req, timeout=10) as resp:
                    if resp.status == 202:
                        print(f"\n\t(Wait... {attempt}/{retries})", end=" ")
                        sys.stdout.flush()
                        time.sleep(5)
                        continue
                    if resp.status == 204:
                        contributors_data = []
                        print("Done!", end="")
                        break
                    contributors_data = json.loads(resp.read())
                    print("Done!", end="")
                    break
            except Exception as e:
                print(f"Error ({e})", end="")
                break
        
        if not contributors_data or not isinstance(contributors_data, list):
            print() # Print newline if skipped
            continue
            
        repo_added = 0
        repo_deleted = 0
        
        for contributor in contributors_data:
            if contributor.get('author') and contributor['author'].get('login', '').lower() == login.lower():
                for week in contributor.get('weeks', []):
                    ts = datetime.fromtimestamp(week['w'])
                    added = week['a']
                    deleted = abs(week['d'])
                    
                    repo_added += added
                    repo_deleted += deleted
                    
                    total_added += added
                    total_deleted += deleted
                    
                    if ts > one_year_ago:
                        last_year_added += added
                        last_year_deleted += deleted
                break # Found the user, move to next repo
                
        print(f" [+{repo_added} / -{repo_deleted}]")
                
    return total_added, total_deleted, last_year_added, last_year_deleted

USER_QUERY = """
query($login: String!) {
  user(login: $login) {
    name
    login
    avatarUrl
    bio
    followers { totalCount }
    publicRepos: repositories(privacy: PUBLIC, ownerAffiliations: OWNER, first: 100) { totalCount nodes { name } }
    privateRepos: repositories(privacy: PRIVATE, ownerAffiliations: OWNER, first: 100) { totalCount nodes { name } }
    repositoriesContributedTo(privacy: PUBLIC) { totalCount }
    contributionsCollection {
      totalCommitContributions
      restrictedContributionsCount
    }
  }
  organization(login: $login) {
    name
    login
    avatarUrl
    description
    publicRepos: repositories(privacy: PUBLIC, first: 100) { totalCount nodes { name } }
    privateRepos: repositories(privacy: PRIVATE, first: 100) { totalCount nodes { name } }
  }
}
"""

REPOS_QUERY = """
query($login: String!) {
  organization(login: $login) {
    repositories(first: 100, privacy: PUBLIC, isFork: false, orderBy: {field: PUSHED_AT, direction: DESC}) {
      nodes {
        name
        url
        description
        stargazerCount
        forkCount
        languages(first: 3, orderBy: {field: SIZE, direction: DESC}) {
          nodes {
            name
            color
          }
        }
      }
    }
  }
}
"""

def format_number(num):
    if num >= 1000000:
        return f"{num/1000000:.1f}M"
    if num >= 1000:
        return f"{num/1000:.1f}k"
    return str(num)

def build_stats():
    token = load_env()
    if not token:
        print("Error: No GITHUB_TOKEN found in environment or misc/.env.")
        sys.exit(1)

    print("Fetching data for bioinformike and Latent-Lens...")
    
    users = ["Latent-Lens", "bioinformike"]
    stats_html = ""

    for login in users:
        res = graphql_query(token, USER_QUERY, {"login": login})
        data = res.get("data", {})
        
        is_org = bool(data.get("organization"))
        profile = data.get("organization") if is_org else data.get("user")
        
        if not profile:
            print(f"Warning: Could not find profile for {login}")
            continue
        
        name = profile.get("name") or login
        avatar = profile.get("avatarUrl")
        public_repos = profile.get("publicRepos", {}).get("totalCount", 0)
        private_repos = profile.get("privateRepos", {}).get("totalCount", 0)
        bio = profile.get("bio") or profile.get("description") or ""
        url = f"https://github.com/{login}"
        
        repo_names = [r["name"] for r in profile.get("publicRepos", {}).get("nodes", [])]
        if "privateRepos" in profile:
            repo_names += [r["name"] for r in profile.get("privateRepos", {}).get("nodes", [])]
            
        if login == "Latent-Lens":
            all_time_commits = 0
        else:
            all_time_commits = get_total_commits_all_time(token, login)
        
        # User specific stats
        commits_this_year = 0
        contrib_to = 0
        if not is_org:
            commits_this_year = profile["contributionsCollection"]["totalCommitContributions"] + profile["contributionsCollection"]["restrictedContributionsCount"]
            contrib_to = profile["repositoriesContributedTo"]["totalCount"]

        stats_html += f"""
      <div class="stat-card">
        <img src="{avatar}" alt="{login}" class="stat-avatar">
        <div class="stat-info">
          <h3><a href="{url}" target="_blank" rel="noopener noreferrer">{name}</a></h3>
          <p>{bio}</p>
          <div style="display: flex; gap: 2rem;">
              <div class="stat-numbers">
                <span>{public_repos} Public / {private_repos} Private Repos</span>
                """
            
        if login != "Latent-Lens":
            if not is_org:
                stats_html += f"""
                    <span>{format_number(commits_this_year)} Commits (this year)</span>
                    <span>{format_number(all_time_commits)} Commits (all time)</span>
                    """
            else:
                stats_html += f"""
                    <span>{format_number(all_time_commits)} Commits (all time)</span>
                    """
                
            stats_html += f"""
              </div>
            </div>
          </div>
        </div>"""
        else:
            stats_html += f"""
              </div>
          </div>
        </div>
      </div>"""

    print("Fetching repositories for Latent-Lens...")
    repo_res = graphql_query(token, REPOS_QUERY, {"login": "Latent-Lens"})
    repos = repo_res.get("data", {}).get("organization", {}).get("repositories", {}).get("nodes", [])

    repos_html = ""
    for repo in repos:
        name = repo["name"]
        url = repo["url"]
        desc = repo["description"] or "No description provided."
        stars = repo["stargazerCount"]
        forks = repo["forkCount"]
        
        langs_html = ""
        for lang in repo["languages"]["nodes"]:
            color = lang["color"] or "#cccccc"
            langs_html += f'<span class="repo-meta-item"><span class="lang-dot" style="background-color: {color}"></span>{lang["name"]}</span>'

        repos_html += f"""
      <div class="repo-card">
        <h3 class="repo-name">
          <svg aria-hidden="true" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true" class="repo-icon"><path d="M2 2.5A2.5 2.5 0 0 1 4.5 0h8.75a.75.75 0 0 1 .75.75v12.5a.75.75 0 0 1-.75.75h-2.5a.75.75 0 0 1 0-1.5h1.75v-2h-8a1 1 0 0 0-.714 1.7.75.75 0 1 1-1.072 1.05A2.495 2.495 0 0 1 2 11.5Zm10.5-1h-8a1 1 0 0 0-1 1v6.708A2.486 2.486 0 0 1 4.5 9h8ZM5 12.25a.25.25 0 0 1 .25-.25h3.5a.25.25 0 0 1 .25.25v3.25a.25.25 0 0 1-.4.2l-1.45-1.087a.249.249 0 0 0-.3 0L5.4 15.7a.25.25 0 0 1-.4-.2Z"></path></svg>
          <a href="{url}" target="_blank" rel="noopener noreferrer">{name}</a>
        </h3>
        <p class="repo-desc">{desc}</p>
        <div class="repo-meta">
          {langs_html}
          <span class="repo-meta-item" title="Stars">
            <svg aria-hidden="true" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true" class="repo-icon"><path d="M8 .25a.75.75 0 0 1 .673.418l1.882 3.815 4.21.612a.75.75 0 0 1 .416 1.279l-3.046 2.97.719 4.192a.751.751 0 0 1-1.088.791L8 12.347l-3.766 1.98a.75.75 0 0 1-1.088-.79l.72-4.194L.818 6.374a.75.75 0 0 1 .416-1.28l4.21-.611L7.327.668A.75.75 0 0 1 8 .25Z"></path></svg>
            {stars}
          </span>
          <span class="repo-meta-item" title="Forks">
            <svg aria-hidden="true" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true" class="repo-icon"><path d="M5 5.372v.878c0 .414.336.75.75.75h4.5a.75.75 0 0 0 .75-.75v-.878a2.25 2.25 0 1 1 1.5 0v.878a2.25 2.25 0 0 1-2.25 2.25h-1.5v2.128a2.251 2.251 0 1 1-1.5 0V8.5h-1.5A2.25 2.25 0 0 1 3.5 6.25v-.878a2.25 2.25 0 1 1 1.5 0ZM5 3.25a.75.75 0 1 0-1.5 0 .75.75 0 0 0 1.5 0Zm6.75.75a.75.75 0 1 0 0-1.5.75.75 0 0 0 0 1.5Zm-3 8.75a.75.75 0 1 0-1.5 0 .75.75 0 0 0 1.5 0Z"></path></svg>
            {forks}
          </span>
        </div>
      </div>"""

    # Update repositories.html
    html_content = REPOSITORIES_HTML.read_text(encoding="utf-8")
    
    # Replace stats
    stats_pattern = re.compile(r'(<div class="github-stats-container"[^>]*>).*?(</div>\s*<h2)', re.DOTALL)
    html_content = stats_pattern.sub(rf'\1\n{stats_html}\n    \2', html_content)
    
    # Replace repos
    repos_pattern = re.compile(r'(<div class="repo-grid"[^>]*>).*?(</div>\s*</section>)', re.DOTALL)
    html_content = repos_pattern.sub(rf'\1\n{repos_html}\n      \2', html_content)

    REPOSITORIES_HTML.write_text(html_content, encoding="utf-8")
    print("Successfully built repositories.html!")

if __name__ == "__main__":
    build_stats()
