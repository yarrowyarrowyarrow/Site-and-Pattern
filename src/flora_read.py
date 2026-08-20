"""
src/flora_read.py — read four numbers off ONE published description, on a click.

Design principle P9 (uncertainty is a feature) — see docs/DESIGN_PHILOSOPHY.md.

WHAT THIS IS, AND WHAT IT DELIBERATELY IS NOT
The catalogue describes 307 flowering species and has verified almost none of
them. The numbers that would fix that are published — Flora of North America
gives ray counts and head diameters outright — and reading 400 pages by hand is
a cost measured in evenings. So this exists. But the difference between a
reading aid and a scrape is not a matter of degree or of politeness, and this
module is built so the difference is structural rather than promised:

* **One species per call.** There is no function here that takes a list, and
  none that iterates the catalogue. Adding one would be the whole change, and
  it would be visible in a diff. That absence is the design.
* **``robots.txt`` decides, and the UI cannot overrule it.** Checked before
  every request via the standard library. Disallowed means refused.
* **Only the numbers.** :func:`parse_description` returns four integers and a
  float and drops everything else on the floor. The prose is never stored, never
  written to the catalogue, and never cached to disk — this module has no cache.
  Facts about a plant are nobody's property; the sentences a botanist wrote
  around them are, and those stay where they are.
* **Nothing is written without a person.** The result is a *proposal* that lands
  in the bench's sliders. Somebody looks at it against the render and presses
  Save, or does not.
* **It is off unless switched on.** ``scripts/tune_morphology.py`` exposes none
  of this without ``--flora-fetch``, whose help text points at the terms you
  should read first.

WHY THAT IS NOT SIMPLY "IT IS FINE"
Facts are not copyrightable in either Canada (*CCH v Law Society of Upper
Canada*, 2004 SCC 13) or the US (*Feist*, 1991), and a person reading "ray
florets 8-21" and recording 8 and 21 is recording facts. Two honest caveats,
which is why the guard rails above exist rather than an argument:

1. A *compilation* of facts can be protected where its selection and
   arrangement are original — so doing this to all 400 species systematically
   is a different act from doing it to one, whatever each individual number is.
2. A flora's range is a botanist's judgement of what is typical for a taxon,
   synthesised across many specimens. That is nearer authorship than a
   measurement is.

And copyright is not the only constraint: a site's Terms of Use are a contract
and can forbid automated access whatever copyright permits. **Read them before
passing the flag.** See docs/DATA_SOURCES.md, which also lists the
better-licensed sources worth exhausting first — Budd's *Flora of the Canadian
Prairie Provinces* is a Government of Canada publication AND regionally correct,
which makes it the better book for this app on both counts.

P12: this reads the botanical description of a flower. It does not seek, parse
or store traditional, cultural or Indigenous knowledge of a plant.
"""

from __future__ import annotations

import re
import urllib.parse
import urllib.request
import urllib.robotparser
from dataclasses import dataclass, field

# Named so the operator of any server this touches can tell what it is and who
# to complain to. An anonymous User-Agent is the mark of somebody who expects to
# be objected to.
USER_AGENT = ("Site-and-Pattern/1.0 (native-plant design app, noncommercial; "
              "one page per human click; "
              "https://github.com/yarrowyarrowyarrow/site-and-pattern)")

# Courtesy floor between requests. The real limit is that a person has to click.
MIN_INTERVAL_S = 2.0

TIMEOUT_S = 20.0

# Refuse anything enormous — a description page is tens of KB, and a reader that
# will happily pull down 50 MB is a reader that is doing something else.
MAX_BYTES = 2_000_000


class NotPermitted(RuntimeError):
    """robots.txt disallows this URL. Not a transport error and not retryable —
    the answer is no."""


@dataclass
class FloraReading:
    """What one page yielded. Every field optional: a description that does not
    give a diameter must produce no diameter rather than a plausible one (P9)."""

    petal_count: int | None = None
    florets_per_head: int | None = None
    flower_diameter_cm: float | None = None
    flowering_stems: int | None = None
    citation: str = ""
    matched: list = field(default_factory=list)   # which phrases fired, for review

    def as_patch(self) -> dict:
        """The subset the bench should pre-fill, provenance included. Only keys
        that actually got a value — a `None` here would clear a number somebody
        measured with a ruler."""
        out = {k: v for k, v in (
            ("petal_count", self.petal_count),
            ("florets_per_head", self.florets_per_head),
            ("flower_diameter_cm", self.flower_diameter_cm),
            ("flowering_stems", self.flowering_stems),
        ) if v is not None}
        if out:
            out["flower_data_source"] = "flora"
            out["flower_data_citation"] = self.citation
        return out


# ── robots ──────────────────────────────────────────────────────────────────

_robots_cache: dict = {}


def robots_allows(url: str, user_agent: str = USER_AGENT) -> bool:
    """Does this site's robots.txt permit fetching ``url``?

    Cached per host for the process only — repeatedly asking for the same file
    is itself impolite. **Fails CLOSED**: an unreadable or unreachable
    robots.txt returns False. That is the opposite of the usual convention, on
    purpose: the usual convention optimises for the crawler getting its data,
    and here the cost of a wrong "yes" is somebody's goodwill.
    """
    parts = urllib.parse.urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.netloc:
        return False
    root = f"{parts.scheme}://{parts.netloc}"
    rp = _robots_cache.get(root)
    if rp is None:
        rp = urllib.robotparser.RobotFileParser()
        rp.set_url(root + "/robots.txt")
        try:
            rp.read()
        except Exception:                                   # noqa: BLE001
            _robots_cache[root] = False
            return False
        _robots_cache[root] = rp
    if rp is False:
        return False
    return bool(rp.can_fetch(user_agent, url))


# ── fetch ───────────────────────────────────────────────────────────────────

_last_fetch = [0.0]


def fetch_page(url: str, *, timeout: float = TIMEOUT_S) -> str:
    """One page, as text. Raises :class:`NotPermitted` if robots.txt says no.

    Note what is missing: there is no ``urls`` parameter, no retry loop and no
    disk cache. Each of those would make this useful for a job it should not do.
    """
    if not robots_allows(url):
        raise NotPermitted(
            f"robots.txt does not permit fetching {url} — "
            f"read the page in a browser instead")
    import time                                             # noqa: PLC0415
    wait = MIN_INTERVAL_S - (time.monotonic() - _last_fetch[0])
    if wait > 0:
        time.sleep(wait)
    req = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT,
                      "Accept": "text/html,application/xhtml+xml"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read(MAX_BYTES)
        charset = resp.headers.get_content_charset() or "utf-8"
    _last_fetch[0] = time.monotonic()
    return raw.decode(charset, errors="replace")


# ── parse ───────────────────────────────────────────────────────────────────

_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")


def strip_html(html: str) -> str:
    """Tags out, entities in, whitespace collapsed. Enough to run a regex over;
    this is not trying to be a browser."""
    import html as _html                                    # noqa: PLC0415
    text = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", html)
    text = _TAG.sub(" ", text)
    return _WS.sub(" ", _html.unescape(text)).strip()


# Floras write ranges with an en dash as often as a hyphen, and hedge with
# parenthetical extremes: "ray florets (5-)8-21(-30)". The extremes are
# deliberately dropped before matching — a TYPICAL value is what the generator
# wants, and the once-in-a-thousand specimen is noise here. Any parenthesis
# opening on a digit or a dash is one of these; in a botanical description
# nothing else looks like that.
_EXTREME = re.compile(r"\(\s*[-–—]?\s*\d[^)]*\)")

_NUM = r"\d+(?:\.\d+)?"
_RANGE = rf"(?:{_NUM}\s*[-–—]\s*)?{_NUM}"

# The range must be matched WHOLE. Without this the engine happily backtracks
# to a shorter prefix that satisfies the unit guard below — "stems 10-30 cm"
# matches as "10-3" and a plant's height becomes its number of stems.
# `\.\d` and not a bare `\.`: a decimal point continues the number, a full stop
# ends the sentence, and "disc florets 60-90." must not be refused for having
# reached the end of one.
_WHOLE = r"(?![-–—\d]|\.\d)"


def _mid(text: str) -> float | None:
    """The middle of a written range. `8-21` is 14.5; a bare `13` is 13."""
    nums = [float(n) for n in re.findall(r"\d+(?:\.\d+)?", text or "")]
    if not nums:
        return None
    return (min(nums) + max(nums)) / 2.0


# Each entry: field, the phrase that identifies it, and whether it needs a unit
# conversion. Written against the idiom of Flora of North America's
# descriptions, which is the most consistent prose in the business.
#
# Two traps this has to avoid, both of which produce a confident wrong number:
#
#   "ray florets 8-16"  — the bare `florets` phrase matches inside this, so the
#                         disc count silently becomes the ray count. `(?<!ray )`
#                         is what stops it.
#   "stems 10-30 cm"    — that is a HEIGHT. A count carries no unit, so any
#                         number followed by one is refused (`_NO_UNIT`). This
#                         is the difference between "twenty flowering stems" and
#                         "twenty centimetres tall", and nothing else in the
#                         sentence distinguishes them.
_NO_UNIT = r"(?!\s*(?:cm|mm|dm|m\b|inch))"

_PATTERNS = (
    ("petal_count", rf"ray (?:florets|flowers)\s*(?:are\s*)?({_RANGE}){_WHOLE}{_NO_UNIT}", None),
    ("petal_count", rf"\bpetals\s*({_RANGE}){_WHOLE}{_NO_UNIT}", None),
    ("petal_count", rf"\btepals\s*({_RANGE}){_WHOLE}{_NO_UNIT}", None),
    ("florets_per_head", rf"disc (?:florets|flowers)\s*({_RANGE}){_WHOLE}{_NO_UNIT}", None),
    ("florets_per_head", rf"(?<!ray )(?<!ligulate )\bflorets\s*({_RANGE}){_WHOLE}{_NO_UNIT}", None),
    ("flower_diameter_cm", rf"heads?\s*({_RANGE})\s*cm\s*(?:diam|across|wide)", 1.0),
    ("flower_diameter_cm", rf"heads?\s*({_RANGE})\s*mm\s*(?:diam|across|wide)", 0.1),
    ("flower_diameter_cm", rf"(?:corollas?|flowers?)\s*({_RANGE})\s*cm\s*(?:diam|across|wide)", 1.0),
    ("flower_diameter_cm", rf"(?:corollas?|flowers?)\s*({_RANGE})\s*mm\s*(?:diam|across|wide)", 0.1),
    ("flower_diameter_cm", rf"laminae\s*({_RANGE})\s*mm", 0.1),
    ("flowering_stems", rf"(?:stems|scapes)\s*({_RANGE}){_WHOLE}{_NO_UNIT}", None),
)

_COUNT_MAX = {"petal_count": 40, "florets_per_head": 250, "flowering_stems": 60}


def parse_description(text: str, *, citation: str = "") -> FloraReading:
    """Four numbers out of a botanical description. Everything else is dropped.

    Deliberately conservative: the first phrase that matches for a field wins
    and later ones are ignored, a value outside the range the catalogue can hold
    is discarded rather than clamped, and a field with no match stays ``None``.
    A wrong number that looks confident is worse than no number, because the
    render makes it look considered.
    """
    text = strip_html(text) if "<" in text else _WS.sub(" ", text)
    low = _EXTREME.sub(" ", text.lower())
    out = FloraReading(citation=citation)
    for fieldname, pattern, factor in _PATTERNS:
        if getattr(out, fieldname) is not None:
            continue
        m = re.search(pattern, low)
        if not m:
            continue
        mid = _mid(m.group(1))
        if mid is None:
            continue
        if factor is not None:
            val = round(mid * factor, 2)
            if not 0.05 <= val <= 60:
                continue
            out.flower_diameter_cm = val
        else:
            val = int(round(mid))
            if not 1 <= val <= _COUNT_MAX[fieldname]:
                continue
            setattr(out, fieldname, val)
        out.matched.append(f"{fieldname}: {m.group(0).strip()}")
    return out


def read_species(url: str, *, citation: str = "") -> FloraReading:
    """Fetch one page and read the numbers off it.

    The whole public surface for going to the network, and it takes a single
    URL. Callers that want a second species call it again, which is a thing a
    person does with a click and not a thing a loop does unattended.
    """
    html = fetch_page(url)
    return parse_description(html, citation=citation or url)
