# The Edmonton list review (V3.12)

The page where the owner rules on the species that the Edmonton rule
(`src/local_flora.py`) cannot settle from herbarium records alone. In V3.12
that is 108 species:

- 73 with one or two collections within 50 km;
- 30 seen within 50 km but never collected there;
- 3 with no records in the cache at all;
- 2 that passed the rule and look like planted trees or a monitoring plot.

**Published at <https://claude.ai/artifact/VPeWXtdA1FFRD1n67MyNSg>**, which is
private to the owner. Each card shows the species' evidence and a read from
`reads.py`, labelled as opinion. Then there are three buttons and a reason. A
`native` or `not_native` ruling is printed beside the plant in the app and on
the website, so its reason is written for readers.

## Bringing the rulings back

The page keeps rulings in its own database (collection `rulings`, one document
per species, keyed by `build.doc_id`). A Claude Code session folds them in:

1. `ArtifactData` `list` on collection `rulings` of the page above, with
   `out_dir` set to a scratch directory. That saves one JSON file per ruling.
2. `python scripts/derive_local_flora.py --merge <that directory>`. Every ruling
   is checked before anything is written. A ruling needs a reason, the name must
   be in the catalogue, and no ruling can make a plant native here unless VASCAN
   records it native in Alberta. `native`/`not_native` replace a species'
   ruling, and `unsettled` removes one. It then rewrites `data/local_flora.json`.
3. Run the tests, commit both data files, and bump nothing: the list is read
   from file, not seeded.

The page's own *Copy* box holds the same rulings as one file, in case the owner
hands it over that way. `--merge` takes that file too.

## Rebuilding the page

    python -m tools.local_flora_review.build      # -> build/local_flora_review/edmonton.html

Rebuild after a re-harvest or a catalogue change moves species between tiers,
then republish to the **same** artifact URL (pass it as `url`), so rulings
already made stay with the page. The build prints any species with no read in
`reads.py`. The page still shows such a species, marked "No read written".
