# The stock review (V3.25)

Where the owner keeps what Edmonton's native-plant nurseries actually stock, so
the availability levels (`src/local_stock.py`) come from real stock rather than
the V3.14 guess. A session cannot reach any nursery's website, so the evidence
comes in here.

**Published at <https://claude.ai/artifact/M34LyMq1RPqXcNRTLuDmwW>**, private
to the owner. Two ways to use it:

- **Add a nursery's list.** Pick the nursery, the month the list is from, and
  plants or seed; paste the list as copied from the nursery's website or
  availability sheet. The page shows which plants it found, which are not on
  the Edmonton list (kept, never ranked), and every line it could not read.
  *Save this list* keeps it. A list can be removed again.
- **Mark the plants you know**: Common, Sometimes, Seed only or Hard to find.
  A tap saves; the same tap again takes it back. Answers win over the lists,
  except that a restoration plant is never Common.

Each plant shows its level as the app would rank it with everything so far.

## Bringing it back

The page keeps two collections in its own database: `lists` (one document per
nursery, month and form, carrying the pasted `text`, and `removed` once taken
off) and `rulings` (one per species, `scientific_name`, `tier`, `on`; an empty
tier is an answer taken back). A Claude Code session folds them in:

1. `ArtifactData` `list` on `lists` and on `rulings` of the page above, with
   `query.limit` 1000 and `out_dir` set to one scratch directory.
2. `python scripts/merge_stock.py --merge <that directory>`: a dry run that
   reads every list again with `src/stock_lists.match`, checks each nursery
   against the pack and each name against the catalogue, and prints what it
   would change and every line it could not read.
3. The same with `--write`, which rewrites `data/regions/edmonton/stock.json`.
   Run the tests and commit. No schema bump: the stock is read from file.

The page's *Copy* box holds the same thing as one file, which `--merge` also
takes.

## Rebuilding the page

    python -m tools.stock_review.build     # -> build/stock_review/edmonton.html

Rebuild after a fold-in (so the page's "in the app" lists and answers are
current) or after the Edmonton list changes, and republish to the **same**
URL, so what is already saved stays with the page.
