#!/usr/bin/env python3
"""
scripts/retag_releases.py — point each release tag at the commit it shipped.

WHY THIS EXISTS
---------------
Both release workflows create their tag through `softprops/action-gh-release`,
which creates the tag when it does not already exist. Until V2.72 neither
passed `target_commitish`, and with that field absent GitHub anchors a new tag
to the **repository's default branch** rather than to the commit being built.
`main` has not moved since the V2.20 merge, so every tag from V2.21 onward
landed on that one commit.

Nothing about the downloads was ever wrong: the `.dmg` and `.exe` are uploaded
release assets, not built from the tag, and the in-app updater reads the
release's `tag_name` rather than the tag's target. What was wrong is what the
tag *says*: click "V2.65" on GitHub and you get V2.20's source tree.

V2.72 fixes the cause. This script fixes the history, and is a one-off: once it
has run, new releases tag themselves correctly.

WHAT IT DOES
------------
For every remote tag named `V<major>.<minor>` that has a branch of the same
name, it moves the tag to that branch's tip. The branch tip is the right
target by this repo's own definition - CLAUDE.md: "Each release branch contains
a single increment of work" - and in practice it is also the commit that was
built, because both workflows rerun on *every* push to a V-branch and update
the release in place, so the last push is what the published assets came from.

A tag with no matching branch is left alone and reported. So is `v1.64`, which
is lowercase and predates the convention.

RUNNING IT
----------
    python3 scripts/retag_releases.py            # dry run: prints the plan
    python3 scripts/retag_releases.py --apply    # actually moves the tags

The dry run reaches the network but only to *read* (`git ls-remote`). Nothing
is pushed without `--apply`.

**`--apply` force-updates shared refs.** Before pushing, it writes the current
tag → commit mapping to `tags-before.txt` and prints the command that puts
everything back, so the operation is reversible. Anyone else with a clone will
need `git fetch --tags --force` afterwards; a plain fetch keeps their old tags
and reports nothing.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys

REMOTE = "origin"
BACKUP = "tags-before.txt"
#: `V2.71` yes, `v1.64` no. The lowercase tag predates the branch convention
#: and has no branch to check against.
_VERSION = re.compile(r"^V(\d+)\.(\d+)$")
#: How many refspecs to hand `git push` at once. One push per tag is ~100 round
#: trips; all of them in one is a command line long enough to worry about.
_BATCH = 25


def _git(*args: str) -> str:
    out = subprocess.run(["git", *args], capture_output=True, text=True)
    if out.returncode != 0:
        sys.exit(f"git {' '.join(args)} failed:\n{out.stderr.strip()}")
    return out.stdout


def _remote_refs(kind: str) -> dict:
    """``{name: sha}`` for the remote's tags or branches."""
    flag = "--tags" if kind == "tags" else "--heads"
    refs = {}
    for line in _git("ls-remote", flag, REMOTE).splitlines():
        sha, ref = line.split()
        name = ref.rsplit("/", 1)[-1]
        # `^{}` rows are annotated tags' dereferenced commits. These tags are
        # all lightweight, but reading them as separate refs would be wrong.
        if not name.endswith("^{}"):
            refs[name] = sha
    return refs


def _subject(sha: str) -> str:
    out = subprocess.run(["git", "log", "--format=%s", "-1", sha],
                         capture_output=True, text=True)
    return out.stdout.strip()[:64] if out.returncode == 0 else "(not fetched)"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true",
                    help="actually move the tags (default is a dry run)")
    args = ap.parse_args()

    print("Reading remote refs ...")
    tags, heads = _remote_refs("tags"), _remote_refs("heads")

    plan, orphans, already = [], [], []
    for name, sha in tags.items():
        if not _VERSION.match(name):
            continue
        if name not in heads:
            orphans.append(name)
        elif heads[name] == sha:
            already.append(name)
        else:
            plan.append((name, sha, heads[name]))
    plan.sort(key=lambda r: [int(p) for p in r[0][1:].split(".")])

    print(f"\n{len(plan)} tags to move, {len(already)} already correct, "
          f"{len(orphans)} with no branch")
    if orphans:
        print(f"  left alone (no branch of that name): {', '.join(sorted(orphans))}")
    if not plan:
        print("\nNothing to do.")
        return 0

    # Objects have to be local for git to push them, so make sure the branches
    # are fetched before promising anything.
    print("\nFetching branches so the targets are available locally ...")
    _git("fetch", REMOTE)

    print(f"\n{'tag':<8} {'from':<10} {'to':<10} commit")
    for name, old, new in plan:
        print(f"{name:<8} {old[:8]:<10} {new[:8]:<10} {_subject(new)}")

    if not args.apply:
        print(f"\nDRY RUN. Nothing was pushed. Re-run with --apply to move "
              f"these {len(plan)} tags.")
        return 0

    with open(BACKUP, "w", encoding="utf-8") as f:
        for name, old, _new in plan:
            f.write(f"{old} refs/tags/{name}\n")
    print(f"\nOld state saved to {BACKUP}. To undo:\n"
          f"  awk '{{print $1\":\"$2}}' {BACKUP} | xargs git push {REMOTE} --force")

    refspecs = [f"{new}:refs/tags/{name}" for name, _old, new in plan]
    for i in range(0, len(refspecs), _BATCH):
        batch = refspecs[i:i + _BATCH]
        print(f"\nPushing {len(batch)} tags ...")
        subprocess.run(["git", "push", REMOTE, "--force", *batch], check=True)

    print("\nVerifying ...")
    after = _remote_refs("tags")
    bad = [n for n, _o, new in plan if after.get(n) != new]
    if bad:
        print(f"STILL WRONG: {', '.join(bad)}")
        return 1
    print(f"All {len(plan)} tags now point at their branch tip.")
    print("Anyone with an existing clone needs:  git fetch --tags --force")
    return 0


if __name__ == "__main__":
    sys.exit(main())
