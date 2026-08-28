"""
static_site_feedback.py — a way to say what you think, without an account.

Design principle P9 — see docs/DESIGN_PHILOSOPHY.md. A catalogue that says
"these pages are wrong in places" and then asks you to open a GitHub issue has
made reporting an error harder than living with it, which is a strange thing to
do about the pages it least wants to be wrong.

Asking for more than errors (V2.80)
-----------------------------------
The first version was headed *"Tell us what is wrong"* and every line of it
assumed the reader had found a fault. Reported as:

    "The feedback page text focuses on what is wrong. I would like it not to be
     so negative and more broadly ask 'What did you like? What can be
     improved?'"

Two reasons that framing was costing something. A page that only invites
complaints gets only complaints, and what people find *useful* is the thing
this catalogue has no other way of learning, since it counts page views and
nothing else. And a reader who liked it has nowhere to say so, which makes the
form feel like a returns desk.

The error path is unchanged and still named, because a wrong flower colour is
worth more than a compliment. It is now one of the things you might write
rather than the only one.

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
<h1>What did you think?</h1>
<p class="lede">What you found useful is as worth knowing as what you would
change. This catalogue counts page views and nothing else, so the only way it
learns which parts are working is if somebody says so.</p>
<p>Corrections are just as welcome: a flower colour that looks wrong, a plant
that does not grow where we say it does, a photograph credited to the wrong
person. Most of what has been fixed here started with one person noticing one
thing on one page. None of it needs an account.</p>

<form class="feedback" method="post" action="{_esc(endpoint)}">
  <label for="fb-msg">What did you like? What could be better?</label>
  <textarea id="fb-msg" name="message" rows="8" required
            placeholder="Anything at all. A page that helped, something that
confused you, a plant you expected to find, or an error."></textarea>

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
    return _page("Feedback", "Tell us what worked and what could be better. "
                             "No account needed.", body, 1)


def render_thanks(model: dict) -> str:
    """Where the Worker sends somebody after it takes their report."""
    body = f"""
{_crumb([("feedback/", "Feedback"), ("", "Sent")], 2)}
<h1>Thank you</h1>
<p class="lede">That has been sent, and it will be read.</p>
<p>If you left an email we may write back. If you did not, it is still read:
most of what has changed here began with somebody noticing one thing on one
page and taking a minute to say so.</p>
<p><a class="button" href="../../">Back to the catalogue</a></p>
"""
    return _page("Thank you", "Thank you, your message has been sent.", body, 2)


def _no_endpoint_body() -> str:
    """The honest page for a build with no endpoint configured.

    Not an empty form and not a silent omission: a build that cannot receive
    feedback should say so rather than showing a button that goes nowhere.
    """
    return f"""
{_crumb([("", "Feedback")], 1)}
<h1>What did you think?</h1>
<p class="lede">What you found useful, what you would change, and anything here
that is simply wrong: all of it is worth knowing.</p>
<p>This build has no feedback address configured, so there is no form here.
Anything you would have written can go as an issue on the
<a href="https://github.com/yarrowyarrowyarrow/Site-and-Pattern">project
repository</a>.</p>
"""
