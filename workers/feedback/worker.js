/*
 * workers/feedback/worker.js — the endpoint the site's feedback form posts to.
 *
 * Deployed to Cloudflare Workers on the site's own domain, so a reader's words
 * go to the person who runs the catalogue and to nobody else. See README.md
 * beside this file for the deploy steps.
 *
 * What it does, and deliberately does not do:
 *
 *   - Accepts one form POST, stores it in KV, and redirects the browser back
 *     to a thank-you page on the site. A redirect and not a JSON reply,
 *     because the form is a plain `method="post"` form that works with
 *     JavaScript switched off, and the browser is navigating.
 *   - Stores the message, the page it names, and the email ONLY if one was
 *     given. It does not store an IP address, a user agent, or a cookie. The
 *     site promised no account and no personal info; a server quietly logging
 *     the sender would make that false.
 *   - Drops anything with the honeypot field filled. A person never sees it.
 *   - Refuses anything but POST, and anything over 8 KB.
 *
 * Rate limiting is by KV counter per minute, coarse on purpose: the failure it
 * is guarding against is a script, and a person sending three reports in a
 * minute is somebody who found three errors.
 */

const MAX_BYTES = 8 * 1024;
const MAX_PER_MINUTE = 20;

export default {
  async fetch(request, env) {
    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: cors(env) });
    }
    if (request.method !== "POST") {
      return new Response("Send a POST.", { status: 405, headers: cors(env) });
    }

    const site = (env.SITE_URL || "").replace(/\/+$/, "");
    const thanks = site + "/feedback/sent/";
    const back = site + "/feedback/";

    const body = await request.text();
    if (body.length > MAX_BYTES) {
      return redirect(back + "?error=too-long", env);
    }

    const form = new URLSearchParams(body);
    // The honeypot. Silently accepted so a bot cannot tell it failed, and
    // silently dropped so we never see it.
    if ((form.get("website") || "").trim() !== "") {
      return redirect(thanks, env);
    }

    const message = (form.get("message") || "").trim();
    if (!message) {
      return redirect(back + "?error=empty", env);
    }

    if (await overLimit(env)) {
      return redirect(back + "?error=slow-down", env);
    }

    const record = {
      message: message.slice(0, 4000),
      page: (form.get("page") || "").trim().slice(0, 500),
      // Absent, not empty, when nobody gave one: a key that is always there
      // reads as "we asked and they refused", which is not what happened.
      ...(form.get("email") ? { email: form.get("email").trim().slice(0, 200) }
                            : {}),
      at: new Date().toISOString(),
    };

    const key = `feedback:${record.at}:${crypto.randomUUID().slice(0, 8)}`;
    await env.FEEDBACK.put(key, JSON.stringify(record));

    return redirect(thanks, env);
  },
};

function redirect(url, env) {
  // 303 and not 302: the browser must GET the thank-you page rather than
  // re-POST to it, or a refresh sends the report again.
  return new Response(null,
    { status: 303, headers: { Location: url, ...cors(env) } });
}

function cors(env) {
  // Present so a future scripted submission works; a plain form POST does not
  // need it, because the browser is navigating rather than reading a response.
  return {
    "Access-Control-Allow-Origin": env.SITE_URL || "*",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
  };
}

async function overLimit(env) {
  const bucket = `rate:${new Date().toISOString().slice(0, 16)}`;
  const seen = parseInt(await env.FEEDBACK.get(bucket) || "0", 10);
  if (seen >= MAX_PER_MINUTE) return true;
  await env.FEEDBACK.put(bucket, String(seen + 1), { expirationTtl: 120 });
  return false;
}
