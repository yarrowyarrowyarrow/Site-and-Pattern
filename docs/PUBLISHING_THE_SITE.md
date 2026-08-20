# Publishing the plant directory

How to get the website online, in plain steps. Written in answer to:

> "I want to publish this once it is in a state that I am happy with. Please
> explain in simple terms how I can easily and affordably get this site publicly
> available."

**Short answer: it is free, and it is about twenty minutes of setup once.**

The site is a folder of ordinary HTML files. No server, no database, no
programming language runs when somebody visits. That is why hosting it costs
nothing: the hosts below all give away unlimited bandwidth for static files,
because serving a file is nearly free for them.

---

## Step 1: build the folder

```bash
python -m src.cli build-site public
```

That writes about 1,660 files into a new folder called `public`: 432 species
pages, 1,138 wildlife pages, the ecoregion map, the browse page and its search
index. The counts are computed at build time and printed at the end, so the
numbers in this paragraph are illustrative and the ones on your screen are
real.

Open `public/index.html` in a browser to check it before anybody else sees it.

Rebuild it any time the catalogue changes. Nothing is stored anywhere else, so
the folder is always a fresh snapshot of the database.

### One thing to decide before you publish

By default **321 of the photographs are hotlinked**, meaning the page points at the
photo on iNaturalist rather than carrying a copy. That is legal and correctly
credited, but it means the pages load slower and a photo can disappear if the
source removes it. To bundle copies instead, warm the local image cache first
(open the plant browser in the app and scroll through it) and rebuild. The build
tells you which it did:

```
photos: 0 copied from cache, 321 left as links
```

---

## Step 2: pick where it lives

All three of these are genuinely free for a site this size. Pick by how you want
to update it.

| | How you publish | Free tier | Best if |
|---|---|---|---|
| **GitHub Pages** | commit the folder, or push a branch | unlimited, 1 GB site | the code is already on GitHub, which it is |
| **Netlify** | drag the folder onto their page | 100 GB/month | you want the simplest possible first publish |
| **Cloudflare Pages** | connect the repo, or upload | unlimited bandwidth | you expect real traffic |

**The recommendation is GitHub Pages**, because the repository is already there
and publishing becomes one command rather than a separate account.

### GitHub Pages, concretely

1. In the repository on github.com: **Settings → Pages**.
2. Under "Build and deployment", set **Source** to *Deploy from a branch*.
3. Choose the branch `gh-pages` and folder `/ (root)`. Save.
4. Push the built folder to that branch:

```bash
python -m src.cli build-site public
cd public
git init -b gh-pages
git add -A
git commit -m "Publish the plant directory"
git remote add origin https://github.com/yarrowyarrowyarrow/Site-and-Pattern.git
git push -f origin gh-pages
```

A minute or two later the site is at
`https://yarrowyarrowyarrow.github.io/Site-and-Pattern/`.

To update it later, repeat those same commands. The `-f` is safe here and only
here: the `gh-pages` branch holds *generated* files, so overwriting it loses
nothing that is not rebuilt from the catalogue in seconds. Never use `-f` on a
`V*.*` branch.

### Netlify, if you would rather not touch git for this

Go to <https://app.netlify.com/drop>, drag the `public` folder onto the page.
That is the whole procedure; the site is live in about ten seconds on a random
address like `wandering-fern-3f8a12.netlify.app`. Sign up (free) to keep it and
to rename it to something sayable.

---

## Step 3: your own domain name

The only part that costs money. A `.ca` or `.com` is roughly **$15 to $20 a
year** from Namecheap, Cloudflare Registrar or Porkbun.

`grownativeplants.ca` was registered in V2.70. Here is the whole setup, once.

### 3a. Build with the domain as the base URL

```bash
python -m src.cli build-site public --base-url https://grownativeplants.ca/
```

**This is the step people miss, and it breaks the domain silently.** GitHub
Pages stores a custom domain in a file called `CNAME` at the root of the
`gh-pages` branch. Publishing replaces that branch's contents wholesale, so a
domain typed into the Pages settings survives exactly until the next rebuild
and then reverts to `*.github.io`, with the custom domain 404ing and nothing in
the build output to notice.

So the build writes the file. It derives the host from `--base-url` rather than
taking a separate flag, because two settings that have to agree do not stay in
agreement. Check it landed:

```bash
cat public/CNAME
```

Should print `grownativeplants.ca`. If it prints nothing, the base URL was
wrong or missing, and publishing would drop the domain.

### 3b. DNS at the registrar

Four `A` records and four `AAAA` records on the bare domain, all with host `@`
(some registrars call it blank, or the domain itself):

| Type | Host | Value |
|---|---|---|
| A | @ | 185.199.108.153 |
| A | @ | 185.199.109.153 |
| A | @ | 185.199.110.153 |
| A | @ | 185.199.111.153 |
| AAAA | @ | 2606:50c0:8000::153 |
| AAAA | @ | 2606:50c0:8001::153 |
| AAAA | @ | 2606:50c0:8002::153 |
| AAAA | @ | 2606:50c0:8003::153 |
| CNAME | www | yarrowyarrowyarrow.github.io |

Four of each because they are GitHub's four edge servers: any one of them can
be down and the site stays up. The `www` row is a CNAME rather than an A record
because it points at a *name*, so it keeps working if GitHub renumbers.

**Check these against GitHub's own docs before typing them** ("Managing a
custom domain for your GitHub Pages site"). They have been stable for years and
they are still somebody else's infrastructure.

### 3c. Tell GitHub

Repository → **Settings → Pages → Custom domain**, enter `grownativeplants.ca`,
Save. Then tick **Enforce HTTPS** once it becomes available, which can take an
hour while a certificate is issued.

DNS takes minutes to hours to propagate. Until it does, the domain may show a
GitHub 404 page; that is normal and not a sign the records are wrong.

The old address keeps working: GitHub redirects
`yarrowyarrowyarrow.github.io/Site-and-Pattern/` to the custom domain, so no
existing link breaks.

---

## Step 4: find out whether anyone is reading it (optional)

Off unless you ask for it. With no analytics argument the site makes **no
request to anywhere else at all**, which is how it has always shipped and the
default this step does not change.

There are two counters you can turn on, separately or together. Both are free,
neither sets a cookie, neither keeps a per-visitor identifier, and either one
adds a line to the footer of every page saying it is there. That is the price
of admission: a script that needed a consent banner would not be in here.

| | Answers | Keeps history |
|---|---|---|
| **Cloudflare Web Analytics** | *is anybody reading this at all* | free tier holds roughly the last day |
| **Umami** | *which pages, and is it growing* | months |

**Turn on Umami if you only turn on one.** Cloudflare's short window is the
whole reason this step gained a second option in V2.73: a 24-hour snapshot
cannot show you that March had twice February's readers, or that one species
page is where most people arrive.

**Why not Google Analytics.** It would give far more numbers than you need and
would put a consent obligation on a catalogue that currently has none.

### 4a. Umami — the one that keeps history

1. Sign up at **[cloud.umami.is](https://cloud.umami.is)** (there is a free
   tier; check their pricing page for the current event limit).
2. **Add a website**, name it and enter `grownativeplants.ca`.
3. Open that website's **Settings**. Copy the **Website ID** — a UUID, five
   groups of hex digits separated by hyphens, like
   `0f8c1a2b-3d4e-5f60-7182-93a4b5c6d7e8`.

Copy the **ID**, not the tracking-code snippet and not the share URL. The build
writes the snippet for you, and the share URL is a different thing entirely.

```bash
python -m src.cli build-site public --base-url https://grownativeplants.ca/ \
  --umami-website-id 0f8c1a2b-3d4e-5f60-7182-93a4b5c6d7e8
```

If you signed up in Umami's **EU region**, add
`--umami-src https://eu.umami.is/script.js` — the ID alone will not find it,
and the symptom is a dashboard that stays at zero.

### 4b. Cloudflare — keep it as the control

Get the token once:

1. In the Cloudflare dashboard, left sidebar: **Analytics & Logs → Web
   Analytics**.
2. **Add a site**, enter `grownativeplants.ca`, and it shows you a snippet.
3. You do not need the snippet. Copy only the long value after `"token":` —
   32 characters, letters and digits.

You can pass both flags at once, and for the first fortnight you should:

```bash
python -m src.cli build-site public --base-url https://grownativeplants.ca/ \
  --analytics-token PASTE_THE_TOKEN_HERE \
  --umami-website-id 0f8c1a2b-3d4e-5f60-7182-93a4b5c6d7e8
```

Two counters on the same pages should report roughly the same traffic. If Umami
shows nothing while Cloudflare shows visitors, the problem is the Umami setup,
not the audience. Once the two agree, drop `--analytics-token` and Cloudflare
is off with no other change.

### 4c. Reading the build output

**What these flags do.** Each adds one `<script>` to the end of every page and
adds a sentence to the footer naming what is there.

**How to read the output.** The last line of the build now names the providers
it embedded:

```
  analytics: Cloudflare Web Analytics + Umami embedded, disclosed in the footer
  analytics: Umami embedded, disclosed in the footer
  analytics: none (the site makes no external request)
```

Read that line. It is the only way to know which kind of build you just made,
and it is why the line names them rather than saying "yes".

**What failure looks like.** A mistyped token or a website ID that is not a
UUID is *refused with an error* rather than published, because the value goes
into 2,000 pages and a broken one would be silent. But a value that is
well-formed and belongs to somebody else's site will **not** error: it will
build cleanly and record nothing. So after publishing, visit the site yourself
and check the number moves. Cloudflare usually shows it within a few minutes;
Umami shows the visit almost immediately, on its **Realtime** page.

**The one that will confuse you later:** `cloud.umami.is/script.js` is on the
common ad-blocker lists, so some of your visitors are never counted and the
number is a floor, not a total. The fix is to serve the script from your own
domain, and that is what `--umami-src` is for — it takes any https URL, so if
you ever self-host Umami, only the build command changes.

---

## What is already handled

Worth knowing so you do not go looking for it:

- **No em dashes.** Normalised at the point every string passes through, and a
  test fails the build if one appears.
- **No uncredited photographs.** A photo without an attributable credit is not
  published at all, so there is nothing to audit before going live.
- **No Indigenous knowledge** (P12). The `notes` field is withheld from the
  public site by default, and the statement that the catalogue contains none
  and none should be inferred from it sits in the **footer of every page**, not
  only on the About page. A test fails the build if any page is missing it.
- **Every fact carries its source or says it is missing.** The map states the
  survey its boundaries come from and how far they were simplified; guessed
  flower colours are marked *not verified* rather than presented as fact.
- **It works with no scripts.** Filtering uses a small script, but every page is
  readable and every link works with JavaScript switched off.

## What to check before you publish

1. Open `public/index.html` locally and click through a species page, the
   ecoregion map, and a wildlife page.
2. Decide the photo question above (hotlinked or bundled).
3. Decide whether the 276 unverified flower colours are acceptable to publish
   marked as unverified. They are marked honestly, but they are visible.
   `docs/DATA_GAPS.md` has the worklist for closing that.

---

## Cost, all in

| | |
|---|---|
| Hosting | **$0** |
| HTTPS certificate | **$0** |
| Domain name | **$0**, or ~$18/year if you want your own |
| Rebuilding after a catalogue change | one command |
