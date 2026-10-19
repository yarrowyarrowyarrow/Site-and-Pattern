# Picking each plant's photographs (V3.35)

Up to six photographs a plant, the first one leading everywhere: the plant
list, the plant's page in the app, and its page on the website. Every photo
offered may ship (CC0, CC BY or CC BY-SA) and carries its credit. Why and how:
[`docs/plans/V3.35-several-photos-a-plant.md`](../../docs/plans/V3.35-several-photos-a-plant.md).

## On your PC

You need this repository on the branch `V3.35` or later, Python, and an
internet connection. Open a terminal in the repository's folder.

**1. Check the script understands iNaturalist's answers** (a few seconds):

```bash
python scripts/fetch_photo_candidates.py --probe "Ratibida columnifera"
```

It asks about Prairie Coneflower each way the full run will: in flower, in
fruit, with no flowers, in winter, and its own iNaturalist page. Good: each
block ends `photographs this script would offer:` with a number above 0, and
the last says how many photographs its own page has. Not good: a line saying a
field is missing, `HTTP 4xx`, or a final message to send the output to a
session. Then stop and send it.

**2. Fetch the candidates** (about an hour; it can run while you do other things):

```bash
python scripts/fetch_photo_candidates.py
```

It first puts the plants in order (a few seconds), then prints a line per
plant, such as `  12/424 Stiff Goldenrod: 17 photographs to pick from`. Plants
with no photo yet come first. Ctrl+C stops it; the same command carries on.

**3. Pick.** The script ends with `Wrote …photo_review.html`. Open that file in
your browser. Each plant starts with a suggestion under *Your picks*: the
best-liked photo in flower first, then one of the whole plant, one of its fruit
and one in winter where there is one.

- Click a photo under *To pick from* to add it; click it again to take it out.
- *Lead* moves a pick to the front. The first one leads everywhere.
- The box under each pick says what it shows; change it if it is wrong.
- **Use these** when a plant looks right. **Keep the photo it has** leaves a
  plant as it is.

Your work stays in that browser. Do as many as you like at a sitting.

**4. Send your picks.** Press **Save my picks** (it saves `photo_picks.json`,
usually to Downloads) and attach the file in a message to a session. You can
send part and the rest later.

## In a session

```bash
python scripts/fold_photo_picks.py photo_picks.json          # check
python scripts/fold_photo_picks.py photo_picks.json --write  # fold in
```

The first only checks; nothing is written if any pick fails. The second writes
`data/plant_photos.json` and each picked plant's photo in
`data/plants_master.json`. Then bump `_SCHEMA_VERSION`, on a new branch if the
current one has shipped, and run the tests.
