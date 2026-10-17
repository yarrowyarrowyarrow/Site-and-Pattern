"""
feedback.py — turn what a user wants to say into something the author receives.

Design principle P13 — see docs/DESIGN_PHILOSOPHY.md

Qt-free core. The app had no way to send feedback at all: a tester who found the
quiz crashing, or simply got stuck, had to already know the maintainer. Every
piece needed was present — QDesktopServices is used elsewhere, the repo is known
to ``github_releases``, and the app already gathers its version, schema version
and commit for the About dialog — there was just no button.

Two deliberate choices:

  * **Broader than a bug tracker.** The categories below cover getting stuck and
    liking something, not only breakage. Most of what a first user knows is not
    a defect report, and a form that only accepts defects collects only defects
    — which is exactly the feedback a design tool least needs.
  * **No account needed (FN-8, V3.31).** A GitHub issue needs a GitHub
    account most people do not have, so the dialog also shows an address to
    copy (``region.feedback_address``, the edition's mailbox) and copies the
    whole message, details included, for any email program. GitHub stays the
    second way.
  * **Nothing is sent silently.** The submission is a prefilled URL the user
    opens and reviews before posting. Diagnostics are opt-in and shown in full
    first. An app that mails home about its user without showing them what it
    said has spent trust it cannot easily get back.
"""

from __future__ import annotations

import platform
import urllib.parse

# (key, menu-ish label, the issue label to file it under, the prompt shown above
# the text box). Ordered by how often a real tester has something of each kind.
CATEGORIES: tuple[tuple[str, str, str, str], ...] = (
    ("stuck", "I got stuck", "confusing",
     "What were you trying to do, and where did it stop making sense?"),
    ("idea", "I have an idea", "enhancement",
     "What would you like it to do?"),
    ("broken", "Something's broken", "bug",
     "What happened, and what did you expect instead?"),
    ("liked", "Something I liked", "praise",
     "What worked well? (Useful — it says what not to change.)"),
)

_TITLES = {
    "stuck": "Confusing: ",
    "idea": "Idea: ",
    "broken": "Bug: ",
    "liked": "Liked: ",
}


def category_keys() -> list[str]:
    return [c[0] for c in CATEGORIES]


def category(key: str) -> tuple[str, str, str, str]:
    for c in CATEGORIES:
        if c[0] == key:
            return c
    return CATEGORIES[0]


def diagnostics(version: str = "", schema_version=None) -> dict:
    """The small, boring facts that make a report actionable.

    Deliberately excludes anything about the user's *design* — where they live
    is in their project, and a bug report is not a reason to collect it.
    """
    out = {
        "App version": version or "dev (source checkout)",
        "OS": f"{platform.system()} {platform.release()}",
        "Python": platform.python_version(),
    }
    if schema_version is not None:
        out["DB schema"] = str(schema_version)
    return out


def format_diagnostics(diag: dict) -> str:
    """Exactly what the user is shown, and exactly what gets attached."""
    return "\n".join(f"{k}: {v}" for k, v in (diag or {}).items())


def build_body(message: str, diag: dict | None = None) -> str:
    body = (message or "").strip() or "(no description given)"
    if diag:
        body += "\n\n---\n" + format_diagnostics(diag)
    return body


def build_title(key: str, message: str) -> str:
    """A one-line summary from the first line of the message."""
    first = (message or "").strip().splitlines()[0] if (message or "").strip() else ""
    first = first.strip()
    if len(first) > 70:
        first = first[:67].rstrip() + "…"
    return _TITLES.get(key, "") + (first or "(no summary)")


def issue_url(key: str, message: str, diag: dict | None = None,
              repo: str = "") -> str:
    """A GitHub "new issue" URL with the title, body and label prefilled.

    The user still sees and posts it — this only saves them the typing, and lets
    them read what is about to be published before it is.
    """
    if not repo:
        try:
            from src.github_releases import DEFAULT_REPO
            repo = DEFAULT_REPO
        except Exception:                       # noqa: BLE001
            repo = ""
    if not repo:
        return ""
    _k, _label, issue_label, _prompt = category(key)
    query = urllib.parse.urlencode({
        "title": build_title(key, message),
        "body": build_body(message, diag),
        "labels": issue_label,
    })
    return f"https://github.com/{repo}/issues/new?{query}"


def email_subject(key: str, message: str) -> str:
    return "Site & Pattern: " + build_title(key, message)


def email_text(key: str, message: str, diag: dict | None = None) -> str:
    """What *Copy message* puts on the clipboard: the subject on the first
    line, then the body, so a paste into any email says everything."""
    return (f"Subject: {email_subject(key, message)}\n\n"
            f"{build_body(message, diag)}\n")


def mailto_url(address: str, key: str, message: str,
               diag: dict | None = None) -> str:
    """A ``mailto:`` link with the subject and body filled in, or ``""`` with
    no address. A convenience only: the address shown is the thing, because a
    computer with no email program set up opens nothing."""
    if not address:
        return ""
    query = urllib.parse.urlencode(
        {"subject": email_subject(key, message),
         "body": build_body(message, diag)},
        quote_via=urllib.parse.quote)
    return f"mailto:{address}?{query}"
