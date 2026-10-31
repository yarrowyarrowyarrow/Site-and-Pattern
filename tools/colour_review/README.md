# The flower colour review (V3.33)

You look at photographs of each plant in flower and say what colour it is.
About 200 plants matter (the rest are optional), at roughly a minute or two
each, and you can stop and carry on whenever you like. The why and the order
of the list are in
[`docs/plans/V3.33-flower-colours-from-photographs.md`](../../docs/plans/V3.33-flower-colours-from-photographs.md).

## On your PC

You need this repository on your computer (the branch `V3.33` or later),
Python, and an internet connection. Open a terminal in the repository's folder.

**1. Check the script understands iNaturalist's answers** (a few seconds):

```bash
python scripts/fetch_colour_evidence.py --probe "Ratibida columnifera"
```

It asks iNaturalist about one plant, Prairie Coneflower, and prints what came
back. Good: a line starting `Chosen:`, a few observations each with a
`photo url=` ending in `.jpg`, and `Photographs this script would show: 3` (or
any number above 0). Not good: a line saying a field is missing, or `HTTP 403`.
If you see either, stop and send the whole output to a session: the script was
written without seeing a real answer, and this is the check.

**2. Fetch the photographs** (about 15–20 minutes for everything):

```bash
python scripts/fetch_colour_evidence.py
```

It works down the list, one plant at a time, printing a line per plant such as
`  12/343 Stiff Goldenrod: 6 photographs`. It pauses a second between
requests, which iNaturalist asks of anyone using its API. Press Ctrl+C to stop
at any time; running the same command again carries on where it stopped.
`--no-flora` leaves out the last, optional part of the list (plants already
read from a flora), which saves about a third of the time.

**3. Look.** The script ends with `Wrote …colour_review.html`. Open that file
(double-click it, or drag it into your browser). For each plant:

- The top line says what the app says now and why the plant is on the list.
- Six photographs of it **in flower**, from Alberta and Saskatchewan where
  there are enough. Click one to open it on iNaturalist.
- Press its colours, **the main one first**. A second colour means "and
  sometimes" (white to pink, yellow with a red centre). Press a colour again
  to take it back.
- **Looks right** keeps what the app says. **No showy flower** for a tree or
  shrub whose flowers nobody would notice. **Can't tell** leaves it as it is,
  and it stays on the list.

Your answers are kept in that browser as you go. Close it and come back
whenever you like.

**4. Send your answers.** Press **Save my answers**. Your browser saves
`colour_answers.json` (usually to Downloads). Attach that file in a message to
a session, or press **Copy answers** and paste. You can send part of the list
and the rest later: answers already sent are kept.

## In a session

```bash
python scripts/fold_colour_answers.py colour_answers.json          # check
python scripts/fold_colour_answers.py colour_answers.json --write  # fold in
```

The first only checks: every answer must name a plant on the list and colours
from the buckets, and nothing is written if any does not. The second writes
`data/plants_master.json` (the colour, the colour list, and `photo` as the
source) and `data/flower_colour_checks.json` (the record, with the
observations shown). Then bump `_SCHEMA_VERSION` in `src/db/plants.py` and run
the tests; `tests/test_colour_checks.py` fails if the two files disagree.
