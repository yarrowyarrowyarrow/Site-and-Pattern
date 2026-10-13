# 10 · Finishing: publishing it free, and being able to walk away

*Part of the [homeowner-path plan](README.md). Work items **FN-1 to FN-14**;
owner decisions **D1 to D7** ([12-decisions.md](12-decisions.md)).*

The owner: *"I would at most publish it in a free way with a link for people to
donate a coffee or $5… [I] would simply like it to reach a place that I can move
on to other projects rather than ceaselessly working at this."*

So "finished" has two halves: the app is good enough to hand to a stranger
(the rest of this plan), and the things around the app are settled so it keeps
working without its author (this part). Nothing here is code that a homeowner
sees, except a donate link and a feedback form. Most of it is licences,
signatures, outside services and a runbook.

## In one paragraph

One problem is serious enough to stop a public release: **the repository is
licensed PolyForm Noncommercial, and the app is built on PyQt6, which is
licensed GPL v3** (or commercially). A program that ships PyQt6 to the public
under terms the GPL does not allow needs a PyQt commercial licence. Relicensing
the app as **GPL-3.0** fixes that, and also qualifies it for **free Windows code
signing** from the SignPath Foundation, which requires an OSI licence (D1, D2).
Beyond that: the installers are unsigned, so Windows and macOS warn strangers
away (FN-3, FN-4); three outside services need attribution the app does not
give (FN-5); the map's tile requests do not identify the app (FN-6); every push
publishes a release every user is offered (five on 8 October 2026; FN-7); and
*Send Feedback* needs a GitHub account (FN-8). Then a runbook, so the friend
can keep it alive (FN-13, FN-14).

---

## 1. What "finished" means (decision D7)

The app is finished when all of these are true:

1. **The homeowner path works for strangers**: four of five people in the
   usability sessions (01 §6, FN-9) complete *start a plan*, *get a
   suggestion*, *get what you need for the nursery* and *come back next week*
   unaided.
2. **No known High defect** remains from the first review (R1–R40) or this plan
   (EDF, OVF, PYF), as [11-work-plan.md](11-work-plan.md) tracks.
3. **Installing it does not look like malware**: the Windows installer is signed;
   the macOS build is notarized, or the download page says plainly how to open
   it (D3).
4. **The licence is settled** and compatible with what the installer contains
   (D1), with third-party notices shipped (FN-2).
5. **Every outside service is used within its terms and credited** (FN-5, FN-6).
6. **Users get only releases the owner chose** (FN-7).
7. **A stranger can say something without an account** (FN-8), and can
   support the app if they want to (FN-10).
8. **A one-page guide** exists on the website (FN-11).
9. **The runbook exists, and someone besides the owner can cut a release**
   (FN-13, FN-14).
10. **The freezes are in force**: the 3D preview (G4) and the website (G5) take
    fixes only.

**Not part of finishing:** the Calgary and Regina editions (ED-15, ED-16), new
3D features, new data beyond the jobs this plan names (the spread review, the
toxicity of the top 60, photos), and anything a not-for persona asks for
(01 §2).

## 2. The licence (D1)

### 2.1 The conflict

- `LICENSE` is the **PolyForm Noncommercial License 1.0.0**: anyone may use the
  code for noncommercial purposes; commercial use is not granted.
- `requirements.txt` builds on **PyQt6** and **PyQt6-WebEngine**. Riverbank
  Computing licenses PyQt6 under the **GPL v3** or a commercial licence, and
  says that if a use is not compatible with the GPL, a commercial licence is
  required ([riverbankcomputing.com](https://www.riverbankcomputing.com/commercial)).
- The installers bundle PyQt6 (`scripts/packaging/permadesign.spec`), so
  publishing them distributes PyQt6 together with the app.
- The GPL does not allow added restrictions such as "noncommercial", so an app
  distributed under PolyForm Noncommercial alone is not a GPL-compatible use.
  *This reading is from the licences' terms and secondary sources, not legal
  advice; Riverbank answers this question for free.*

The repository is public, so the source is already available; the conflict is
about the terms, not about hiding code.

### 2.2 The options

| Option | What it takes | Keeps "noncommercial"? | Unlocks free signing? | Cost |
|---|---|---|---|---|
| **(a) Relicense the app as GPL-3.0** (recommended) | Change `LICENSE`; the owner holds all the copyright, so the owner can relicense; say so in the README and the About box | No: anyone may sell copies, but must pass on the source and the same freedoms | **Yes** (SignPath, §3) | None |
| (b) Port to **PySide6** (Qt for Python, LGPL v3) and keep PolyForm NC | Mechanical changes across the Qt code (`pyqtSignal` → `Signal`, imports, a few API differences), re-test everything; LGPL obligations (the Qt libraries replaceable, which PyInstaller's one-folder build allows; notices) | Yes | No (PolyForm is not OSI) | 1–3 weeks of work and risk |
| (c) Buy a **PyQt commercial licence** | A purchase from Riverbank (price not checked) | Yes | No | Money, renewed per their terms |

**Why (a):** the owner wants it free and to move on. GPL-3.0 costs nothing,
changes no code, and makes the free signing service available. The risk it
accepts, that someone sells copies, is small for an app that is free to
download, and they would have to publish their changes.

**Data is separate from code.** The catalogue's photographs carry their own
licences and credits (since V2.47), and the occurrence-derived data its own; the
installer distributes them alongside the program, which the GPL allows. RM-7 and
ED-13 already take the CC BY-NC records in `data/fetched/` out of the installer.
P12 is untouched by any option.

### 2.3 Third-party notices (FN-2)

The installer should carry one `THIRD_PARTY_NOTICES` file listing what it
bundles and under what licence: Qt and Qt WebEngine (LGPL v3, with Chromium's
notices), PyQt6 (GPL v3), Leaflet and Leaflet.draw (BSD-2-Clause), three.js
0.180.0 (MIT), Spark 2.1.0 (MIT, until RM-2 removes it), shapely, numpy,
rasterio and pyproj where bundled, and PyInstaller's bootloader (GPL with its
exception). `html/vendor/README.md` already lists the web libraries and versions.

## 3. Signing the installers (D2, D3)

Today both release workflows build **unsigned** installers. An unsigned
download that few people have run makes Windows SmartScreen show *Windows
protected your PC* with the Run button hidden behind *More info*, and macOS
refuses to open it outright.

| Platform | Option | What it needs | Cost | Status |
|---|---|---|---|---|
| Windows | **SignPath Foundation** (recommended with D1 (a)) | An OSI-approved licence with no commercial dual-licensing, a public repository, a fully automated build from the repository (the GitHub workflows already are), no proprietary components; the certificate names *SignPath Foundation* as publisher ([signpath.org](https://signpath.org/terms)) | Free | Reported from SignPath's terms |
| Windows | **Azure Artifact Signing** (formerly Trusted Signing) | Generally available since January 2026 to organizations or **individuals in the USA and Canada**; identity checked with government photo ID | US$9.99 a month for up to 5,000 signatures | Reported (DevClass, Jan 2026) |
| Windows | Unsigned, with instructions | The download page shows the SmartScreen screen and says *More info → Run anyway* | None | Loses some strangers at the first step |
| macOS | **Apple Developer Program** + notarization in the macOS workflow | An Apple developer account; `codesign` and `notarytool` steps in `release-macos.yml` | US$99 a year | Well known; not re-checked |
| macOS | Unsigned, with instructions | macOS 15 (Sequoia) removed the Control-click → Open bypass; the person must try to open the app, then go to **System Settings → Privacy & Security → Open Anyway**. Reports disagree on whether that still appears in 15.1 | None | Reported (Macworld, OSNews) |
| macOS | Drop the macOS build | Edmonton homeowners mostly use Windows (assumed, not measured) | Saves the $99 and the workflow | — |

## 4. Outside services: terms, credit and what breaks (FN-5, FN-6)

What the app calls, found by listing every URL host in `src/` and `html/map/`.

| Service | Used for | Terms that matter | Credited in the app? | If it stops |
|---|---|---|---|---|
| **Open-Meteo** (`api.open-meteo.com`, `archive-api.open-meteo.com`) | Elevation, climate, wind | Free API for **non-commercial** use, under 10,000 calls a day; data CC BY 4.0, credit required (*"Weather data by Open-Meteo.com"*) ([open-meteo.com/en/terms](https://open-meteo.com/en/terms)) | **No** (the data dialog does not name it) | Region normals (ED-6); wind and elevation absent |
| **Nominatim** (OpenStreetMap) | Address search | One request a second at most, an identifying User-Agent, no autocomplete, credit to OpenStreetMap (ODbL) | Map tiles credit OSM; the search does not | *Click your yard on the map* (WD) |
| **OpenStreetMap tiles** | The street map | An identifying User-Agent; no heavy use | Yes (Leaflet attribution, `01-core.js:528`) | Blank map offline (R9) |
| **Esri World Imagery** (`server.arcgisonline.com`) | The satellite view | Governed by the Esri Master License Agreement; whether use outside Esri software needs an ArcGIS account or key **was not established** (D4) | Yes (`01-core.js:525, 586`) | Street map only |
| **Overpass API** (two mirrors) | Buildings, trees, roads | Fair use; ODbL | Partly | *Scan this area* returns nothing |
| **ISRIC SoilGrids** (`rest.isric.org`) | Soil when the offline pack is absent | CC BY 4.0 | **No** | Prairie soil fallback (distance-limited by ED-6) |
| **NRCan datacube** (HRDEM) | LiDAR elevation (advanced) | Open Government Licence – Canada; credit | Check | Open-Meteo elevation |
| **City of Edmonton Open Data** | 0.5 m contours (advanced) | City's open data licence; credit | Check | HRDEM |
| **Meta / WRI canopy height** (AWS) | Trees for *Scan this area* | CC BY 4.0 | Yes ("Meta" named) | Satellite-based detection |
| **iNaturalist** | Plant photographs | Per-photo licence and credit | Yes (since V2.47) | Cached photos still show |
| **GitHub API** | *Check for Updates* | 60 unauthenticated requests an hour per address | — | No update offered |
| **Mapbox** | Optional satellite with the person's own token (advanced) | The person's own account | Yes | Not used by default |

**Privacy, in one paragraph for the About box and the website:** the address a
person types goes to OpenStreetMap's search; the pin's coordinates go to
Open-Meteo, SoilGrids, the map tile servers and, when asked, Overpass, NRCan and
the City of Edmonton; nothing else leaves the computer; the app has no analytics
and no account; feedback is sent only when the person sends it. Photographs a
person adds have their location data removed (`src/photo_import.py`, V2.35).

**Identifying the app (FN-6).** The Python requests send
`PermaDesign/1.0 (https://github.com/yarrowyarrowyarrow/permadesign)`
(`src/http_utils.py:28` and four copies), which names the pre-rebrand product
and repository; GitHub redirects the URL. The map's tile requests go out from
Qt WebEngine with its default browser User-Agent, which the OpenStreetMap tile
policy asks apps not to use. One string, `SiteAndPattern/<version>
(+https://grownativeplants.ca/app/)`, set on the web profile and in
`http_utils`, fixes both. (The legacy string was kept on purpose once; that
reason belongs to the old name and should be revisited, not assumed.)

## 5. Releases: a stable channel (FN-7, D5)

Both release workflows run on **every push to a `V*.*` branch** and publish a
**full** release (neither sets `prerelease`, so it defaults to false). The updater offers every full release to
every installed copy: on 8 October 2026 that was five (V3.13 to V3.17) in one
day. Fine for the owner; not for a stranger who is offered an update every few
hours.

The updater **already skips prereleases** (`src/github_releases.py:161-176`).
So: publish every push as a **prerelease**, and add a manual
`workflow_dispatch` workflow, *Promote release*, that flips a chosen one to a
full release with its notes. The tag naming (`release-V…`) is unchanged, and the
in-app updater needs no change. The owner (or the friend) promotes perhaps
three or four times a year.

## 6. Donations (FN-10, D6)

- **Where:** Help › *Support this app…*, one line in the About box, the website
  footer and the download page. **Never** in the planning flow, never a pop-up,
  never a count of days used.
- **Words:** *Site & Pattern is free. If it helped your yard, you can buy its
  maker a coffee.* and the link.
- **Platform:** Ko-fi, Buy Me a Coffee, GitHub Sponsors or Liberapay; fees and
  payout terms differ and were not compared (D6).
- **Tax:** donations to a person are not charitable donations (no receipts);
  whether they are income is a question for an accountant, not checked here.

## 7. Feedback without an account (FN-8)

*Help › Send Feedback…* builds a GitHub *new issue* link (`src/feedback.py:98-119`),
which needs a GitHub account the persona does not have. The website already has
an account-free form (`src/static_site_feedback.py`, V2.80), which says why: a
GitHub issue *"has made reporting an error harder than living with it"*. Point
the app's dialog at that form, carrying the version and the diagnostics the
dialog already gathers, and keep *Report it on GitHub* as a second link for
those who have an account.

## 8. A one-page guide (FN-11)

On the website, `grownativeplants.ca/app/`:

1. Download (Windows, Mac), with the screenshots of what the first launch
   warning looks like and what to click (until signing, §3).
2. Five steps with one picture each: find your yard, outline a bed, plan my
   yard, look at the overview, print the plan.
3. *Not an identification guide* (09 §4), what the app sends where (§4), how to
   give feedback, how to support it.

Help gets one item, *How to plan your yard*, opening that page. No manual inside
the app beyond the getting-started strip.

## 9. Pin the build (FN-12)

The final release should build the same way next year. Today `requirements.txt`
sets floors (`PyQt6>=6.6.0`), the Windows job runs on `windows-latest` and the
macOS job on `macos-14` under Rosetta. Add a constraints file with the exact
versions of the release that passed the usability sessions, pin the Windows
runner image, and record both in the runbook. A future change of Qt or Python is
then a choice, not a surprise.

## 10. The runbook (FN-13, FN-14)

A new `docs/MAINTENANCE.md`, short, for the friend:

- **Cut a release:** push a V-branch (a prerelease builds), install it on a
  real Windows laptop, open the example, plan a yard, print it; then *Promote
  release*.
- **Every year:** check the region's rules dates (the pack test fails at 24
  months, ED-14); check that the five nurseries still trade; renew the signing
  account and the domain (grownativeplants.ca); read Open-Meteo's and Esri's
  terms again; run the test suite on the pinned build.
- **When a service breaks:** what the app does without it (§4) and where its
  code is.
- **Feedback:** read the form's inbox monthly; answer what is a bug; decline
  what a not-for persona asks for (01 §2), with the reason.
- **What not to do:** `git pull` a V-branch (CLAUDE.md); push to `main`; delete
  a `V*` tag.
- **Access:** the friend is a GitHub collaborator, can run the workflows, and
  knows where the signing account and the domain registrar are. The README says
  *Status: finished; maintained for fixes.*

## 11. Work items

| ID | Item | Effort | Depends on |
|---|---|---|---|
| **FN-1** | **Settle the licence** (D1). For (a): replace `LICENSE` with GPL-3.0, update the README's licence section and Help › About; a test that `LICENSE` names the licence the About box states. For (b): a separate plan. *Accept:* the licence and the bundled PyQt6 are compatible on the owner's reading, ideally confirmed by Riverbank | S (a) / L (b) | D1 |
| **FN-2** | **Third-party notices** (§2.3), generated from `html/vendor/README.md` and the installed packages' metadata, shipped in the installer. **Tests:** the spec includes the file; every vendored library is named. | S | FN-1 |
| **FN-3** | **Sign the Windows installer** (D2): the SignPath or Azure step in `release-windows.yml`, the installer and the program both signed. *Accept:* a fresh download shows no SmartScreen block | M | FN-1 for SignPath |
| **FN-4** | **macOS** (D3): notarize in `release-macos.yml`, or put the *Open Anyway* steps on the download page, or drop the build. | M / S | D3 |
| **FN-5** | **Credit every source and say what leaves the computer** (§4): Open-Meteo, SoilGrids, OpenStreetMap search, NRCan, the City of Edmonton in *Where This Data Came From*; the privacy paragraph in About and on the website. **Tests:** the data dialog names each service a `src/` URL points at (a test reads the host list). | S | — |
| **FN-6** | **Identify the app** on every request (§4); Nominatim queried on Enter only and cached per query. **Tests:** `http_utils`' User-Agent and the web profile's agree and carry the version. | S | — |
| **FN-7** | **A stable channel** (§5): `prerelease: true` in both release workflows; a *Promote release* workflow. **Tests:** `test_installer_script`-style checks on the workflow files. *Accept:* a push no longer offers an update to installed copies until promoted | S | D5 |
| **FN-8** | **Feedback without an account** (§7). *Accept:* the dialog's Send opens the website form with the version filled in | S | — |
| **FN-9** | **Usability sessions** (01 §6) with three to five homeowners, after the simple app is built; results written into a plan file; fixes scheduled. | M (people's time) | MD-1, ST-4, PY-1, OV-1 |
| **FN-10** | **Support this app** (§6). | S | D6 |
| **FN-11** | **The one-page guide** (§8) and Help's link. | S | FN-3/FN-4 for the screenshots |
| **FN-12** | **Pin the build** (§9). | S | — |
| **FN-13** | **`docs/MAINTENANCE.md`** (§10) and the README's status line. | S | FN-7 |
| **FN-14** | **A second maintainer**: collaborator access, the workflows run by them once, the account and domain notes. | S | FN-13 |

## 12. Decisions for the owner

- **D1.** The licence: GPL-3.0 (recommended), a PySide6 port keeping PolyForm
  Noncommercial, or a PyQt commercial licence.
- **D2.** Windows signing: SignPath (free; needs D1 (a); SignPath shown as
  publisher), Azure Artifact Signing (US$9.99 a month; the owner shown as
  publisher), or unsigned with instructions.
- **D3.** macOS: notarize (US$99 a year), ship unsigned with instructions, or
  stop building for macOS.
- **D4.** Satellite imagery: read Esri's terms and keep it if they allow it
  (recommended first step), move to an Esri key-based plan, or make the street
  map the only default.
- **D5.** A stable channel: prereleases by default and a promote step
  (recommended), or keep releasing every push.
- **D6.** The donation platform and the exact words.
- **D7.** Accept §1 as the definition of finished.

## 13. What could not be checked

- **No lawyer read §2.** It rests on the licences' text as summarised by
  Riverbank's page and secondary sources. Riverbank answers licensing questions
  (their commercial page gives the address).
- The signing services' current terms and prices are from search summaries
  (SignPath's terms page; DevClass on Azure Artifact Signing, January 2026).
- Esri's terms for World Imagery outside Esri software, Open-Meteo's view of a
  free app with a donate link, and the PyQt commercial price were not
  established.
- Whether Edmonton homeowners use Windows more than macOS was assumed.
- The macOS *Open Anyway* behaviour on 15.1 and later is disputed in the
  sources; test on a real Mac.
