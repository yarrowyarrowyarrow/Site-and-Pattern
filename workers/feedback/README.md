# The feedback endpoint

The site's Feedback page posts here. It is a Cloudflare Worker on **your own
domain**, so a reader's words reach you and nobody else.

Everything below is done once. After that, publishing the site with
`--feedback-url` is the only step that repeats.

---

## What you need

A Cloudflare account with `grownativeplants.ca` already on it. You have this
already if the domain is served through Cloudflare.

## 1. Install the tool that deploys Workers

```
npm install -g wrangler
wrangler login
```

`wrangler` is Cloudflare's command-line tool. `wrangler login` opens a browser
and asks you to authorise it; that is the only time you log in.

## 2. Make somewhere to keep the reports

```
wrangler kv namespace create FEEDBACK
```

KV is Cloudflare's key-value store: a list of things you can write and read
back, which is all this needs. The command prints an `id` that looks like
`id = "a1b2c3..."`. **Copy that id** and paste it into `wrangler.toml` beside
this file, replacing `PUT_YOUR_KV_ID_HERE`.

## 3. Deploy

```
cd workers/feedback
wrangler deploy
```

It prints the address it deployed to, something like

```
https://feedback.<your-subdomain>.workers.dev
```

**That address is what the site posts to.** Copy it.

If you would rather it lived at `grownativeplants.ca/feedback-endpoint`, add a
route in the Cloudflare dashboard under Workers Routes; the site works either
way, and the workers.dev address is fine to start with.

## 4. Build the site with it

```
python -m src.cli build-site site_out --base-url https://grownativeplants.ca --feedback-url https://feedback.<your-subdomain>.workers.dev
```

**Without `--feedback-url` there is no form.** The Feedback page still exists
and still appears in the header, and it says the build cannot receive reports
and points at the repository. That is deliberate: a button that goes nowhere is
worse than no button.

## 5. Read what people send

```
wrangler kv key list --binding FEEDBACK --prefix feedback:
wrangler kv key get --binding FEEDBACK "feedback:2026-08-26T19:04:11.001Z:ab12cd34"
```

The first lists the reports newest-last by their timestamp key. The second
prints one. They are also browsable in the Cloudflare dashboard under
Workers & Pages, KV.

---

## What it stores, and what it does not

Stored: the message, the page the reader named, the timestamp, and their email
**only if they typed one**.

Not stored: IP address, user agent, cookies, or any identifier. The site tells
readers there is no account and no personal info required, and a server quietly
logging the sender would make that false. If you ever want abuse-tracking, that
is a decision to make openly and to change the page's wording for.

## What it refuses

- Anything that is not a POST.
- Anything over 8 KB.
- An empty message.
- Anything with the honeypot field filled: a hidden input a person never sees
  and a naive bot fills. Those are accepted with a normal-looking redirect and
  then dropped, so a script cannot tell it failed.
- More than 20 submissions in a minute across the whole site, counted in KV.
  Coarse on purpose: what this guards against is a script, and a person sending
  three reports in a minute has found three errors.

## If something goes wrong

`wrangler tail` streams the Worker's live logs while you test it. Submit the
form, watch what arrives.

A submission that redirects back to `/feedback/?error=...` was refused, and the
reason is in that parameter: `empty`, `too-long` or `slow-down`.
