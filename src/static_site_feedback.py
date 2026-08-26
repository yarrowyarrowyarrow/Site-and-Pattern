"""
static_site_feedback.py — a way to tell us we are wrong, without an account.

Design principle P9 — see docs/DESIGN_PHILOSOPHY.md. A catalogue that says
"these pages are wrong in places" and then asks you to open a GitHub issue has
made reporting an error harder than living with it, which is a strange thing to
do about the pages it least wants to be wrong.

The author's ask: *"I think github is too intimidating for most. I'd like it to
be a box where feedback can be filled in and sent directly from the website, no
account or personal info required."*

Why this needs a decision and not just a form
---------------------------------------------
The site is static files on GitHub Pages. A form that sends anything needs a
server, and every page here says the site makes no external request. Both are
true, and this is the seam between them:

* **The page still makes no request when it loads.** The form posts only when
  somebody presses the button, which is a thing they chose to do. The footer
  sentence is narrowed to say exactly that rather than left to imply more.
* **The endpoint is the author's own**, a Cloudflare Worker on their domain
  (`workers/feedback/`), so nothing is routed through a third party who did not
  ask to be involved. It is configured per build like the analytics token and a
  build without one gets no form at all.

A plain form POST, not `fetch`
------------------------------
`method="post"` with the Worker replying `303 See Other` back to a thank-you
page on this site. It costs one page navigation and buys: it works with
JavaScript off, it works when a script is blocked, and it has no failure mode
where the button does nothing and the reader cannot tell whether their words
went anywhere. `browse.js` stays the site's only script.

What we ask for
---------------
The message, and nothing else that is required. An email box is offered and
labelled optional, for somebody who wants an answer; leaving it blank sends the
report anyway. There is no name field, no account, and no analytics on this
page beyond whatever the build already carries.
"""

from __future__ import annotations

from src.static_site_render import _crumb, _esc, _page

#: Where the reader lands after the Worker accepts a report.
THANKS_PATH = "feedback/sent/"

#: The bot trap. A real person never sees or fills this; a naive scraper fills
#: every input it finds. Named for something plausible so it is not obviously a
#: trap, and the Worker drops any submission that arrives with it set.
HONEYPOT = "website"


def render_feedback(model: dict, endpoint: str) -> str:
    """The feedback page. ``endpoint`` empty means no form is published."""
    if not endpoint:
        return _page(
            "Feedback", "How to report an error in this catalogue.",
            _no_endpoint_body(), 1)

    body = f"""
{_crumb([("", "Feedback")], 1)}
<h1>Tell us what is wrong</h1>
<p class="lede">These pages are wrong in places. A wrong flower colour, a plant
that does not grow where we say, a photograph credited to the wrong person: all
of it is useful and none of it needs an account.</p>

<form class="feedback" method="post" action="{_esc(endpoint)}">
  <label for="fb-msg">What did you find?</label>
  <textarea id="fb-msg" name="message" rows="8" required
            placeholder="Which page, and what is wrong with it."></textarea>

  <label for="fb-page">The page it is about <span class="opt">optional</span></label>
  <input type="text" id="fb-page" name="page" autocomplete="off"
         placeholder="Paste the address, or name the plant">

  <label for="fb-email">Your email <span class="opt">optional, only if you
  want a reply</span></label>
  <input type="email" id="fb-email" name="email" autocomplete="off">

  <div class="hp" aria-hidden="true">
    <label for="fb-hp">Leave this empty</label>
    <input type="text" id="fb-hp" name="{HONEYPOT}" tabindex="-1"
           autocomplete="off">
  </div>

  <button type="submit">Send</button>
</form>

<p class="note">We keep the message, and the email only if you gave one. No
account, no name, no tracking on this page. If you would rather use GitHub, the
catalogue and its data are
<a href="https://github.com/yarrowyarrowyarrow/Site-and-Pattern">public</a>.</p>
"""
    return _page("Feedback", "Report an error in this catalogue. No account "
                             "needed.", body, 1)


def render_thanks(model: dict) -> str:
    """Where the Worker sends somebody after it takes their report."""
    body = f"""
{_crumb([("feedback/", "Feedback"), ("", "Sent")], 2)}
<h1>Thank you</h1>
<p class="lede">Your report has been received.</p>
<p>If you left an email we may write back with what we found. If you did not,
the report is still read: most corrections to this catalogue have come from
somebody noticing one wrong thing on one page.</p>
<p><a class="button" href="../../">Back to the catalogue</a></p>
"""
    return _page("Thank you", "Your report has been received.", body, 2)


def _no_endpoint_body() -> str:
    """The honest page for a build with no endpoint configured.

    Not an empty form and not a silent omission: a build that cannot receive
    feedback should say so rather than showing a button that goes nowhere.
    """
    return f"""
{_crumb([("", "Feedback")], 1)}
<h1>Tell us what is wrong</h1>
<p class="lede">These pages are wrong in places, and knowing which is how they
get better.</p>
<p>This build has no feedback address configured, so there is no form here.
Errors and photograph credit problems can be reported as issues on the
<a href="https://github.com/yarrowyarrowyarrow/Site-and-Pattern">project
repository</a>.</p>
"""
