"""
seed_data.py — Initial plant catalogue for Alberta / Canadian Prairies (Zone 3-4).

Can be run directly to reset the database:
    python -m src.db.seed_data

Each tuple matches the INSERT column order in plants.py:
  (common_name, scientific_name, plant_type,
   hardiness_zone_min, hardiness_zone_max,
   sun_requirement, water_needs,
   native_region, permaculture_uses,
   spacing_meters, mature_height_meters, notes)
"""

# sun_requirement values : full_sun | partial_shade | full_shade
# water_needs values     : low | medium | high
# plant_type values      : tree | shrub | herb | groundcover | vine | root

SEED_PLANTS: list[tuple] = [

    # ── TREES ──────────────────────────────────────────────────────────────

    (
        "Trembling Aspen", "Populus tremuloides", "tree", 1, 8,
        "full_sun", "low", "Western Canada",
        "windbreak,pioneer,wildlife_habitat,biomass",
        5.0, 20.0,
        "Fast-growing native. Excellent pioneer species and windbreak. "
        "Spreads via root suckers to form clonal groves."
    ),
    (
        "White Spruce", "Picea glauca", "tree", 2, 6,
        "full_sun", "low", "Western Canada",
        "windbreak,wildlife_habitat",
        4.0, 25.0,
        "Classic prairie shelterbelt evergreen. Dense year-round wind shelter. "
        "Slow-growing but very long-lived."
    ),
    (
        "Paper Birch", "Betula papyrifera", "tree", 2, 7,
        "full_sun", "medium", "Western Canada",
        "pioneer,wildlife_habitat",
        5.0, 20.0,
        "Beautiful white-barked native. Pioneer species for forest edges. "
        "Important for many insects and birds."
    ),
    (
        "Goodland Apple", "Malus 'Goodland'", "tree", 3, 5,
        "full_sun", "medium", "Canada",
        "food_forest,pollinator",
        4.0, 5.0,
        "Hardy prairie apple bred at Morden Research Station. "
        "Red fruit ripens in August. Reliable producer in Zone 3."
    ),
    (
        "Norland Apple", "Malus 'Norland'", "tree", 3, 5,
        "full_sun", "medium", "Canada",
        "food_forest,pollinator",
        4.0, 4.5,
        "Very early apple — ripens late July. Red-striped fruit. "
        "Excellent for Zone 3 prairie orchards."
    ),
    (
        "Evans Cherry", "Prunus cerasus 'Evans'", "tree", 3, 8,
        "full_sun", "medium", "Canada",
        "food_forest,pollinator,wildlife_habitat",
        4.0, 4.0,
        "Most reliable cherry for Alberta. Self-fertile. Tart dark-red fruit. "
        "Excellent fresh and for jams/pies."
    ),
    (
        "Pembina Plum", "Prunus nigra 'Pembina'", "tree", 3, 5,
        "full_sun", "medium", "Western Canada",
        "food_forest,pollinator",
        4.0, 5.0,
        "Large sweet purple plum. Needs a pollinator such as Brookgold. "
        "Native wild plum species."
    ),
    (
        "Brookgold Plum", "Prunus 'Brookgold'", "tree", 3, 5,
        "full_sun", "medium", "Canada",
        "food_forest,pollinator",
        4.0, 4.5,
        "Yellow freestone plum with excellent flavour. "
        "Pollinates Pembina. Developed at Beaverlodge Research Station."
    ),
    (
        "Siberian Larch", "Larix sibirica", "tree", 2, 5,
        "full_sun", "low", "Northern Asia",
        "windbreak,biomass",
        5.0, 30.0,
        "Deciduous conifer — stunning gold in autumn. "
        "Excellent for shelterbelts. Very cold-hardy and fast-growing."
    ),
    (
        "Bur Oak", "Quercus macrocarpa", "tree", 3, 8,
        "full_sun", "low", "North America",
        "wildlife_habitat,pioneer",
        8.0, 20.0,
        "Hardy native prairie oak. Extremely drought-tolerant and long-lived. "
        "Acorns are important wildlife food. Slow to establish."
    ),

    # ── SHRUBS ─────────────────────────────────────────────────────────────

    (
        "Saskatoon Berry", "Amelanchier alnifolia", "shrub", 2, 6,
        "full_sun", "low", "Western Canada",
        "food_forest,pollinator,wildlife_habitat",
        1.5, 4.0,
        "Quintessential Alberta fruiting shrub. Sweet blueberry-like fruit in July. "
        "Drought-tolerant once established. Native."
    ),
    (
        "Chokecherry", "Prunus virginiana", "shrub", 2, 7,
        "full_sun", "low", "Western Canada",
        "food_forest,wildlife_habitat,windbreak",
        2.0, 5.0,
        "Native prairie shrub. Tart cherries excellent for jelly and syrup. "
        "Important wildlife food source. Forms thickets."
    ),
    (
        "Buffalo Berry", "Shepherdia canadensis", "shrub", 2, 7,
        "partial_shade", "low", "Western Canada",
        "nitrogen_fixer,wildlife_habitat,food_forest",
        2.0, 2.5,
        "Native nitrogen-fixing shrub. Tolerates shade and poor soils. "
        "Tart orange-red berries high in vitamin C."
    ),
    (
        "Prickly Rose", "Rosa acicularis", "shrub", 1, 7,
        "full_sun", "low", "Western Canada",
        "food_forest,pollinator,wildlife_habitat,medicine",
        1.5, 1.5,
        "Alberta's provincial flower. Native. Fragrant pink blooms June-July. "
        "Large orange-red rose hips very high in vitamin C. Essential for pollinators and birds."
    ),
    (
        "Black Currant", "Ribes nigrum", "shrub", 3, 7,
        "partial_shade", "medium", "Northern Europe",
        "food_forest,pollinator",
        1.5, 1.8,
        "Very high vitamin C. Tolerates partial shade. "
        "Strong musky flavour — excellent for jam and juice."
    ),
    (
        "Red Currant", "Ribes rubrum", "shrub", 3, 7,
        "partial_shade", "medium", "Northern Europe",
        "food_forest,pollinator",
        1.2, 1.5,
        "Prolific producer of tart red berries. "
        "More shade-tolerant than most fruiting shrubs."
    ),
    (
        "Gooseberry", "Ribes uva-crispa", "shrub", 3, 7,
        "partial_shade", "medium", "Europe",
        "food_forest,pollinator",
        1.2, 1.5,
        "Hardy. Disease-resistant varieties available. "
        "Large berries excellent for desserts and preserves."
    ),
    (
        "Raspberry", "Rubus idaeus", "shrub", 3, 8,
        "full_sun", "medium", "North America/Europe",
        "food_forest,pollinator,wildlife_habitat",
        0.6, 1.5,
        "Easy to grow; spreads by runners. 'Boyne' and 'Souris' are excellent "
        "Alberta varieties. Mulch well in Zone 3."
    ),
    (
        "Nanking Cherry", "Prunus tomentosa", "shrub", 2, 6,
        "full_sun", "low", "Asia",
        "food_forest,pollinator,windbreak",
        2.0, 2.5,
        "Very hardy, prolific small cherry. Excellent hedge or windbreak plant. "
        "Birds love the fruit. Plant two for cross-pollination."
    ),
    (
        "Potentilla (Shrubby)", "Potentilla fruticosa", "shrub", 2, 6,
        "full_sun", "low", "Western Canada",
        "pollinator,pioneer",
        0.8, 1.0,
        "Native prairie shrub. Very long bloom season (June–frost). "
        "Extremely drought-tolerant. Good habitat plant."
    ),
    (
        "Red Osier Dogwood", "Cornus sericea", "shrub", 2, 7,
        "partial_shade", "high", "Western Canada",
        "wildlife_habitat,windbreak,pioneer",
        2.0, 2.5,
        "Native riparian shrub. Striking red stems provide winter interest. "
        "Excellent for erosion control along waterways."
    ),
    (
        "Snowberry", "Symphoricarpos albus", "shrub", 2, 7,
        "partial_shade", "low", "Western Canada",
        "wildlife_habitat,pioneer,groundcover",
        1.0, 1.2,
        "Native understory shrub. White berries persist all winter — important bird food. "
        "Tolerates shade. Spreads by rhizomes to form dense colonies."
    ),
    (
        "Elderberry", "Sambucus canadensis", "shrub", 3, 7,
        "partial_shade", "medium", "North America",
        "food_forest,pollinator,wildlife_habitat,medicine",
        2.0, 3.0,
        "Edible/medicinal flowers and berries. Prefers moist sites. "
        "Spreads by suckers. Important for pollinators."
    ),
    (
        "Highbush Cranberry", "Viburnum trilobum", "shrub", 2, 7,
        "partial_shade", "medium", "Western Canada",
        "food_forest,wildlife_habitat",
        2.0, 3.0,
        "Native fruiting shrub. Tart cranberry-like berries persist through winter, "
        "feeding birds. Beautiful red autumn colour."
    ),
    (
        "Wolf Willow", "Elaeagnus commutata", "shrub", 1, 5,
        "full_sun", "low", "Western Canada",
        "nitrogen_fixer,windbreak,wildlife_habitat,pioneer",
        2.0, 3.0,
        "Native silver-leafed nitrogen-fixer. Extremely cold-hardy. "
        "Intensely fragrant yellow flowers. Spreads by rhizomes."
    ),
    (
        "Haskap (Blue Honeysuckle)", "Lonicera caerulea", "shrub", 2, 8,
        "full_sun", "medium", "Northern Eurasia",
        "food_forest,pollinator,wildlife_habitat",
        1.5, 2.0,
        "One of the earliest fruiting shrubs (June). Dark blue berries with "
        "blueberry flavour. 'Borealis' + 'Tundra' are a good Alberta pair."
    ),

    # ── HERBS & PERENNIALS ─────────────────────────────────────────────────

    (
        "Comfrey", "Symphytum officinale", "herb", 3, 9,
        "partial_shade", "medium", "Europe",
        "dynamic_accumulator,biomass,medicine,pollinator",
        0.6, 1.2,
        "Deep taproot mines minerals from subsoil. Leaves are superb green mulch "
        "and liquid fertiliser. Use 'Bocking 14' sterile variety to prevent spreading."
    ),
    (
        "Yarrow", "Achillea millefolium", "herb", 3, 9,
        "full_sun", "low", "North America",
        "dynamic_accumulator,pollinator,medicine,pioneer",
        0.3, 0.6,
        "Native prairie flower. Drought-tolerant. Attracts vast numbers of beneficial "
        "insects. Medicinal and a classic companion plant."
    ),
    (
        "Bee Balm (Wild Bergamot)", "Monarda fistulosa", "herb", 3, 9,
        "full_sun", "medium", "North America",
        "pollinator,medicine,pioneer",
        0.4, 0.9,
        "Native prairie wildflower. Loved by bees, butterflies and hummingbirds. "
        "Spreads gently. Aromatic foliage deters pests."
    ),
    (
        "Purple Coneflower", "Echinacea purpurea", "herb", 3, 9,
        "full_sun", "low", "North America",
        "pollinator,medicine,wildlife_habitat",
        0.4, 1.0,
        "Drought-tolerant prairie flower. Medicinal — supports immune function. "
        "Seed heads feed finches and sparrows over winter."
    ),
    (
        "Chives", "Allium schoenoprasum", "herb", 3, 9,
        "full_sun", "medium", "North America/Europe",
        "pollinator,pest_repellent",
        0.2, 0.3,
        "Easy perennial allium. Repels aphids when planted near roses and carrots. "
        "Purple flowers attract pollinators all summer."
    ),
    (
        "Horseradish", "Armoracia rusticana", "herb", 3, 9,
        "full_sun", "medium", "Eastern Europe",
        "dynamic_accumulator,pest_repellent",
        0.6, 0.9,
        "Vigorous deep-rooted perennial. Dynamic accumulator. "
        "Plant where it can naturalize — very hard to remove once established."
    ),
    (
        "Rhubarb", "Rheum rhabarbarum", "herb", 3, 8,
        "full_sun", "medium", "Asia",
        "food_forest",
        1.0, 1.0,
        "Long-lived perennial. Red stalks excellent for pies and jams. "
        "Very productive in Alberta. Note: leaves are toxic."
    ),
    (
        "Lovage", "Levisticum officinale", "herb", 3, 8,
        "full_sun", "medium", "Europe",
        "dynamic_accumulator,pollinator,medicine",
        0.6, 2.0,
        "Giant celery-flavoured perennial herb. Deep root accumulates minerals. "
        "Excellent back-of-border plant. Attracts beneficial wasps."
    ),
    (
        "Wild Mint", "Mentha arvensis", "herb", 3, 8,
        "partial_shade", "high", "Western Canada",
        "medicine,pollinator,pest_repellent",
        0.3, 0.4,
        "The only mint truly native to Alberta. Grows along stream banks and moist "
        "meadows. Aromatic — edible and medicinal. Spreads by runners in moist soil."
    ),
    (
        "Prairie Crocus", "Pulsatilla patens", "herb", 2, 7,
        "full_sun", "low", "Western Canada",
        "pollinator,pioneer",
        0.2, 0.2,
        "Alberta's provincial wildflower. One of the very first plants to bloom in "
        "spring (March-April). Silky purple blooms. Deep taproot — do not transplant."
    ),
    (
        "Fireweed", "Chamerion angustifolium", "herb", 2, 7,
        "full_sun", "medium", "Western Canada",
        "pioneer,pollinator,biomass,medicine",
        0.3, 1.5,
        "Iconic native pioneer — first to colonize burned or disturbed land. "
        "Tall magenta spikes July-August. Edible young shoots. Outstanding bee plant."
    ),
    (
        "Stinging Nettle", "Urtica dioica", "herb", 3, 9,
        "partial_shade", "medium", "North America/Europe",
        "dynamic_accumulator,biomass,medicine,wildlife_habitat",
        0.5, 1.5,
        "Excellent dynamic accumulator. Fermented leaf tea makes superb liquid fertiliser. "
        "Host plant for several butterfly species. Handle with gloves."
    ),
    (
        "Canada Goldenrod", "Solidago canadensis", "herb", 2, 8,
        "full_sun", "low", "Western Canada",
        "pollinator,dynamic_accumulator,wildlife_habitat,pioneer",
        0.4, 1.2,
        "Native prairie flower. Spectacular golden plumes late summer. Supports 100+ "
        "insect species. Spreads by rhizomes — give it space. Important late-season nectar."
    ),
    (
        "Blanketflower", "Gaillardia aristata", "herb", 3, 8,
        "full_sun", "low", "Western Canada",
        "pollinator,pioneer,wildlife_habitat",
        0.3, 0.6,
        "Bold native daisy with red-and-yellow petals. Blooms all summer. "
        "Very drought-tolerant. One of the longest-blooming native Alberta wildflowers."
    ),
    (
        "Harebell", "Campanula rotundifolia", "herb", 2, 8,
        "full_sun", "low", "Western Canada",
        "pollinator,pioneer",
        0.2, 0.4,
        "Dainty native wildflower with nodding blue-violet bells. Found in meadows "
        "and open woodlands. Blooms July-September. Long-lived once established."
    ),
    (
        "Wild Lupine", "Lupinus argenteus", "herb", 3, 7,
        "full_sun", "low", "Western Canada",
        "nitrogen_fixer,pollinator,pioneer,wildlife_habitat",
        0.3, 0.6,
        "Native nitrogen-fixing prairie wildflower. Blue-purple flower spikes June-July. "
        "Drought-tolerant. Note: seeds are toxic — do not ingest."
    ),

    # ── GROUNDCOVER ────────────────────────────────────────────────────────

    (
        "White Clover", "Trifolium repens", "groundcover", 3, 8,
        "full_sun", "medium", "Europe (naturalized)",
        "nitrogen_fixer,pollinator,groundcover,pioneer",
        0.2, 0.2,
        "Excellent nitrogen-fixing living mulch. A favourite of bees. "
        "Tolerates foot traffic. Ideal lawn alternative or orchard understorey."
    ),
    (
        "Creeping Thyme", "Thymus serpyllum", "groundcover", 3, 8,
        "full_sun", "low", "Europe",
        "pollinator,groundcover,medicine",
        0.2, 0.1,
        "Fragrant drought-tolerant groundcover. Tolerates light foot traffic. "
        "Wonderful between stepping stones. Blooms attract bees."
    ),
    (
        "Kinnikinnick (Bearberry)", "Arctostaphylos uva-ursi", "groundcover", 2, 6,
        "partial_shade", "low", "Western Canada",
        "groundcover,wildlife_habitat,medicine",
        0.3, 0.1,
        "Native evergreen groundcover. Excellent under trees on sandy soils. "
        "Red berries are wildlife food. Slow to establish but persistent."
    ),
    (
        "Wild Strawberry", "Fragaria virginiana", "groundcover", 2, 7,
        "partial_shade", "medium", "North America",
        "groundcover,food_forest,pollinator,wildlife_habitat",
        0.3, 0.15,
        "Native strawberry spreads by runners to form dense mat. "
        "Small, intensely flavoured fruit. Good under deciduous trees."
    ),
    (
        "Alfalfa", "Medicago sativa", "groundcover", 3, 8,
        "full_sun", "low", "Central Asia",
        "nitrogen_fixer,dynamic_accumulator,biomass,groundcover",
        0.2, 0.9,
        "Deep-rooting nitrogen-fixer. Mines minerals from deep soil layers. "
        "Excellent green manure crop. Chop-and-drop regularly."
    ),

    # ── VINES ──────────────────────────────────────────────────────────────

    (
        "Hops", "Humulus lupulus", "vine", 3, 8,
        "full_sun", "medium", "North America/Europe",
        "windbreak,food_forest,biomass",
        0.6, 6.0,
        "Fast-growing vine — up to 6 m in one season. Female plants produce hops. "
        "Provides quick summer shade and windbreak. Vigorous spreader."
    ),
    (
        "Virginia Creeper", "Parthenocissus quinquefolia", "vine", 3, 9,
        "partial_shade", "low", "North America",
        "wildlife_habitat,pioneer,windbreak",
        0.6, 15.0,
        "Native vine with spectacular crimson fall colour. Fast cover for fences "
        "and walls. Berries are important bird food in autumn."
    ),
    (
        "Hardy Kiwi", "Actinidia arguta", "vine", 3, 8,
        "full_sun", "medium", "East Asia",
        "food_forest,pollinator",
        2.0, 8.0,
        "Produces small grape-sized kiwi fruit. 'Issai' is self-fertile. "
        "Very vigorous — needs a strong pergola or trellis."
    ),

    # ── ROOT / BULB ────────────────────────────────────────────────────────

    (
        "Garlic", "Allium sativum", "root", 3, 8,
        "full_sun", "medium", "Central Asia",
        "pest_repellent,medicine,food_forest",
        0.15, 0.5,
        "Plant cloves in October, harvest in July. "
        "Natural pest repellent — great companion for roses and fruit trees."
    ),
    (
        "Jerusalem Artichoke", "Helianthus tuberosus", "root", 3, 9,
        "full_sun", "low", "North America",
        "food_forest,wildlife_habitat,biomass,pioneer",
        0.5, 3.0,
        "Productive edible tuber — very vigorous. Plant where it can spread freely. "
        "Tall stalks act as temporary windbreak. Flowers feed late-season bees."
    ),
]


# ── CLI entry point ────────────────────────────────────────────────────────────

def reseed() -> None:
    """Drop all plants and re-insert seed data. Resets the catalogue."""
    import sqlite3 as _sqlite3
    from src.db.plants import get_connection, _insert_plants, _DATA_DIR, _DB_PATH
    import os

    os.makedirs(_DATA_DIR, exist_ok=True)
    conn = get_connection()
    try:
        conn.execute("DELETE FROM plants")
        conn.commit()
        _insert_plants(conn, SEED_PLANTS)
        print(f"Seeded {len(SEED_PLANTS)} plants into {_DB_PATH}")
    finally:
        conn.close()


if __name__ == "__main__":
    # python -m src.db.seed_data
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from src.db.plants import init_db
    init_db()
    reseed()
