#!/usr/bin/env python3
"""Refresh the live sections of README.md using the GitHub REST API.

Standard library only, so the workflow needs no dependency install step.
"""

import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timezone

USERNAME = os.environ.get("GH_USERNAME", "UdayKumar08")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
README = os.path.join(os.path.dirname(__file__), "..", "README.md")
MAX_ACTIVITY = 6
MAX_REPOS = 6


def api(path):
    req = urllib.request.Request(
        f"https://api.github.com{path}",
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": f"{USERNAME}-profile-readme",
            **({"Authorization": f"Bearer {TOKEN}"} if TOKEN else {}),
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def day(iso):
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).strftime("%d %b %Y")


def link(repo):
    return f"[{repo}](https://github.com/{repo})"


def describe(event):
    kind = event["type"]
    repo = link(event["repo"]["name"])
    p = event.get("payload", {})
    if kind == "PushEvent":
        n = len(p.get("commits", [])) or p.get("size", 1)
        return f"Pushed {n} commit{'s' if n != 1 else ''} to {repo}"
    if kind == "PullRequestEvent":
        pr = p.get("pull_request", {})
        action = "Merged" if pr.get("merged") else p.get("action", "updated").capitalize()
        return f"{action} pull request #{pr.get('number')} in {repo}"
    if kind == "IssuesEvent":
        return f"{p.get('action', 'updated').capitalize()} issue #{p.get('issue', {}).get('number')} in {repo}"
    if kind == "IssueCommentEvent":
        return f"Commented on #{p.get('issue', {}).get('number')} in {repo}"
    if kind == "CreateEvent":
        ref = p.get("ref_type", "repository")
        return f"Created a new {ref} in {repo}" if ref != "repository" else f"Created repository {repo}"
    if kind == "WatchEvent":
        return f"Starred {repo}"
    if kind == "ForkEvent":
        return f"Forked {repo}"
    if kind == "ReleaseEvent":
        return f"Published a release in {repo}"
    return None


def recent_activity():
    own_profile_repo = f"{USERNAME}/{USERNAME}".lower()
    lines = []
    for event in api(f"/users/{USERNAME}/events/public?per_page=50"):
        # Skip this repo's own bot commits so the feed shows real work.
        if event["repo"]["name"].lower() == own_profile_repo:
            continue
        text = describe(event)
        if text:
            lines.append(f"- {text} on {day(event['created_at'])}")
        if len(lines) >= MAX_ACTIVITY:
            break
    return "\n".join(lines) or "No public activity in the last few weeks."


def latest_repos():
    repos = api(f"/users/{USERNAME}/repos?sort=pushed&direction=desc&per_page=30&type=owner")
    lines = []
    for r in repos:
        if r["fork"] or r["name"].lower() == USERNAME.lower():
            continue
        desc = (r.get("description") or "").strip()
        lang = r.get("language")
        extras = ", ".join(x for x in (lang, f"updated {day(r['pushed_at'])}") if x)
        line = f"- [{r['name']}]({r['html_url']}) ({extras})"
        if desc:
            line += f": {desc}"
        lines.append(line)
        if len(lines) >= MAX_REPOS:
            break
    return "\n".join(lines) or "No public repositories yet."


def stats():
    user = api(f"/users/{USERNAME}")
    repos = api(f"/users/{USERNAME}/repos?per_page=100&type=owner")
    stars = sum(r["stargazers_count"] for r in repos if not r["fork"])
    langs = {}
    for r in repos:
        if not r["fork"] and r.get("language"):
            langs[r["language"]] = langs.get(r["language"], 0) + 1
    top = ", ".join(k for k, _ in sorted(langs.items(), key=lambda kv: -kv[1])[:4]) or "n/a"
    return (
        f"I have {user['public_repos']} public repositories, {stars} stars across them, "
        f"{user['followers']} followers, and I spend most of my public time in {top}."
    )


def replace(text, name, body):
    pattern = re.compile(rf"(<!--{name}:START-->)(.*?)(<!--{name}:END-->)", re.S)
    if not pattern.search(text):
        sys.exit(f"Marker {name} not found in README.md")
    return pattern.sub(lambda m: f"{m.group(1)}\n{body}\n{m.group(3)}", text)


def main():
    with open(README, encoding="utf-8") as f:
        text = f.read()

    text = replace(text, "RECENT_ACTIVITY", recent_activity())
    text = replace(text, "LATEST_REPOS", latest_repos())
    text = replace(text, "STATS", stats())

    stamp = datetime.now(timezone.utc).strftime("%d %b %Y, %H:%M UTC")
    text = re.sub(
        r"(<!--UPDATED:START-->)(.*?)(<!--UPDATED:END-->)",
        lambda m: f"{m.group(1)}{stamp}{m.group(3)}",
        text,
        flags=re.S,
    )

    with open(README, "w", encoding="utf-8") as f:
        f.write(text)


if __name__ == "__main__":
    main()
