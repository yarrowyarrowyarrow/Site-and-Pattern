# The Edmonton list review (V3.12)

The page where the owner answers for the species that the Edmonton rule
(`src/local_flora.py`) cannot settle from herbarium records alone. In V3.12
that is 108 species:

- 73 with one or two collections within 50 km;
- 30 seen within 50 km but never collected there;
- 3 with no records in the cache at all;
- 2 that passed the rule and look like planted trees or a monitoring plot.

**Published at <https://claude.ai/artifact/VPeWXtdA1FFRD1n67MyNSg>**, which is
private to the owner. Each card shows the species' evidence and a read from
`reads.py`, labelled as opinion. Each card asks one question, *Native around
Edmonton?*, with a **Yes** and a **No**.

The owner answers only where confident and leaves the rest. They asked for no
reasons, so there is no text box. A tap saves at once, and tapping the same
answer again takes it back. An answer reaches the app and the website as
"Native, confirmed on review." or "Not native here, on review." followed by the
evidence, and nothing the owner wrote is ever printed.

## Bringing the answers back

The page keeps answers in its own database (collection `rulings`, one document
per species, keyed by `build.doc_id`). Each document has a `ruling` and an `on`
date:

- `native` means yes;
- `not_native` means no;
- `unsettled` means an answer was taken back.

The page keeps `unsettled` rows so that the next fold-in removes the answer they
replaced. A Claude Code session folds them in:

1. `ArtifactData` `list` on collection `rulings` of the page above, with
   `query.limit` 1000 and `out_dir` set to a scratch directory. That saves one
   JSON file per row.
2. `python scripts/derive_local_flora.py --merge <that directory>`. Every answer
   is checked before anything is written: the name must be in the catalogue, and
   no answer can make a plant native here unless VASCAN records it native in
   Alberta. A yes or a no replaces a species' ruling, and `unsettled` removes
   one. A `reason`, if one ever appears, is dropped. It then rewrites
   `data/local_flora.json`.
3. Run the tests, commit both data files, and bump nothing: the list is read
   from file, not seeded.

The page's own *Copy* box holds the same answers as one file, in case the owner
hands it over that way. `--merge` takes that file too.

## Rebuilding the page

    python -m tools.local_flora_review.build      # -> build/local_flora_review/edmonton.html

Rebuild after a re-harvest or a catalogue change moves species between tiers,
then republish to the **same** artifact URL (pass it as `url`), so answers
already given stay with the page. The build prints any species with no read in
`reads.py`. The page still shows such a species, marked "No read written".
