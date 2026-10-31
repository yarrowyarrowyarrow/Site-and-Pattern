// Part of the Site & Pattern 3D viewer. Loaded as an ordered CLASSIC
// script by the bootstrap in scene3d.html (the list is scene3d/chunks.js) —
// it shares the global scope with its siblings, so load ORDER is dependency
// order. Do not add ES `import`/`export` here.

// ── The cards (V3.39, F255) ─────────────────────────────────────────────────
// Design principle P3 (relationships matter more than components) — see
// docs/DESIGN_PHILOSOPHY.md.
//
// The owner, in the Learn walk: "This is this plant, here is what it does,
// here are creatures it supports (with photos for both the plant and the
// animal). Then if I click on an animal (from the list …) it tells a little
// bit about that animal, especially the plants it relies on, both on the
// design and not yet on the design. Relationality is key."
//
// So a plant's card leads with what it is recorded as food for, in sentences
// (src/scene_dossier.py `_does`), then the animals, eight at most, the ones a
// person can get to know first, the rest folded; everything else the card
// had waits under "More about this plant". An animal's card shows its plants
// here and the plants it uses that are not here yet; in the walk, Plant one
// puts one on the trowel (src/walk_cards.py). Every name is a link, and a
// back link leads to the card you came from.
//
// The picking, the threads and the host hook stay in 10-inspect.js; this file
// is what a card says. Nothing here runs from the animation loop except
// `labelWanted`, which 07-wildlife.js reaches through a typeof guard.

let cardTrail = [];          // the cards you came through: [{type, key}]
const CARD_ROWS = 8;         // animals listed before the rest are folded

const _GROUP_SIGN = { bee: '🐝', lepidoptera: '🦋', bird: '🐦',
  other_insect: '🐞', mammal: '🦇' };
const _GROUP_ONE = { bee: 'bee', lepidoptera: 'butterfly or moth',
  bird: 'bird', other_insect: 'other insect', mammal: 'mammal' };
const _GROUP_MANY = { bee: 'bees', lepidoptera: 'butterflies and moths',
  bird: 'birds', other_insect: 'other insects', mammal: 'mammals' };
const _GROUP_ORDER = ['bee', 'lepidoptera', 'bird', 'other_insect', 'mammal'];

function groupWords(taxon, n) {
  return n + ' ' + (n === 1 ? (_GROUP_ONE[taxon] || 'animal')
                            : (_GROUP_MANY[taxon] || 'animals'));
}

function resetCardTrail() { cardTrail = []; }

// The names of the creatures drawn in the scene now (07-wildlife.js).
function outNowNames() {
  const out = new Set();
  for (const c of (typeof WILDLIFE !== 'undefined' ? WILDLIFE : [])) {
    if (c && c.name) out.add(c.name);
  }
  return out;
}

function faunaPhoto(name) {
  const f = DOSSIER.fauna[name];
  return f && f.photo && f.photo.key && f.photo.credit ? f.photo : null;
}

// The animals a person can get to know first: an English name, a photograph,
// one that depends on this plant, one out in the scene now. Ties keep the
// order the dossier sent (group, then name).
function sortedUsers(users) {
  const out = outNowNames();
  const rank = (u) => [u.english ? 0 : 1, faunaPhoto(u.name) ? 0 : 1,
                       u.specialist ? 0 : 1, out.has(u.name) ? 0 : 1];
  return users.slice().sort((a, b) => {
    const ka = rank(a), kb = rank(b);
    for (let i = 0; i < ka.length; i++) if (ka[i] !== kb[i]) return ka[i] - kb[i];
    return 0;
  });
}

// A small photograph where the catalogue has one, with its credit on the row
// (an open licence is honoured only where the photographer is named), else
// the animal's group sign.
function animalThumb(name, taxon) {
  const p = faunaPhoto(name);
  if (p) {
    return '<span class="athumb"><img src="/__image?k=' + encodeURIComponent(p.key)
      + '" alt="" decoding="async" onerror="this.remove()"></span>';
  }
  return '<span class="athumb sign">' + (_GROUP_SIGN[taxon] || '•') + '</span>';
}

function animalRow(u) {
  const p = faunaPhoto(u.name);
  return '<li class="arow" data-open-fauna="' + esc(u.name) + '" tabindex="0">'
    + animalThumb(u.name, u.taxon) + '<span class="atext"><b>' + esc(u.name) + '</b>'
    + (u.specialist ? ' <span class="chip warn">depends on it</span>' : '')
    + '<span class="how">' + esc(u.words || u.how || '') + '</span>'
    + (p ? '<span class="cite">photo: ' + esc(p.credit) + '</span>' : '')
    + '</span></li>';
}

// "and 41 more: 22 bees, 12 butterflies and moths, 7 other insects, most
// known only by a Latin name", opening onto every one of them, each a link.
function foldedUsers(rest) {
  if (!rest.length) return '';
  const by = {};
  let latin = 0;
  for (const u of rest) {
    by[u.taxon] = (by[u.taxon] || 0) + 1;
    if (!u.english) latin++;
  }
  const parts = _GROUP_ORDER.filter((t) => by[t]).map((t) => groupWords(t, by[t]));
  let summary = 'and ' + rest.length + ' more: ' + parts.join(', ');
  if (latin * 2 > rest.length) summary += ', most known only by a Latin name';
  return '<details class="amore"><summary>' + esc(summary) + '</summary><ul class="ilist">'
    + rest.map(animalRow).join('') + '</ul></details>';
}

function cardHead(e, sub) {
  return '<div class="ihead"><div class="iname">' + esc(e.name) + '</div>'
    + '<div class="isci">' + esc(sub) + '</div></div>';
}

function backLink() {
  const prev = cardTrail[cardTrail.length - 1];
  if (!prev) return '';
  const entry = prev.type === 'fauna' ? DOSSIER.fauna[prev.key]
                                      : DOSSIER.plants[String(prev.key)];
  return '<button class="iback" data-card-back>← back to '
    + esc(entry ? entry.name : 'the last card') + '</button>';
}

// Who would lose the only plant here they are recorded with, if this one
// were pulled: a few by their English names, the rest counted. The first
// build listed all of them, which for an aspen was fifteen names, ten of them
// Latin, ahead of everything else on the card.
function onlyHere(names) {
  const english = names.filter((n) => !(DOSSIER.fauna[n] && DOSSIER.fauna[n].english === false));
  const shown = english.slice(0, 4);
  const rest = names.length - shown.length;
  const n = names.length;
  return '<div class="ionly"><b>Pull it, and ' + n + (n === 1 ? ' animal loses'
    : ' animals lose') + ' the only plant here ' + (n === 1 ? 'it is' : 'they are')
    + ' recorded with</b>' + (shown.length ? ': ' + esc(shown.join(', '))
      + (rest ? ' and ' + rest + ' more' : '') : '') + '.</div>';
}

function plantCardHtml(e) {
  let h = backLink() + photoBlock(e) + cardHead(e, e.scientific_name);
  if (e.does && e.does.length) {
    h += '<div class="does">' + e.does.map((l) => '<p>' + esc(l) + '</p>').join('') + '</div>';
  } else {
    h += '<div class="isec">no animal recorded with it yet</div>';
  }
  if (e.only_source && e.only_source.length) h += onlyHere(e.only_source);
  const users = sortedUsers(e.users || []);
  if (users.length) {
    h += '<div class="isec">who uses it</div><ul class="ilist">'
      + users.slice(0, CARD_ROWS).map(animalRow).join('') + '</ul>'
      + foldedUsers(users.slice(CARD_ROWS));
  }
  h += '<details class="more"><summary>More about this plant</summary>';
  h += chips(e.badges, 'good');
  const bits = [];
  if (e.plant_type) bits.push(esc(e.plant_type));
  if (e.sun) bits.push(esc(e.sun));
  if (e.water) bits.push(esc(e.water) + ' water');
  if (e.native) bits.push('native to ' + esc(e.native));
  if (bits.length) h += '<div class="ifacts">' + bits.join(' · ') + '</div>';
  if (e.morphology && e.morphology.length) {
    h += '<div class="ifacts">' + esc(e.morphology.join(' · ')) + '</div>';
  }
  h += seasonBar(e) + growthStrip(e);
  if (e.safety && e.safety.length) h += chips(e.safety, 'warn');
  if (e.sourcing && (e.sourcing.price || e.sourcing.availability)) {
    h += '<div class="isrc">' + esc([e.sourcing.price, e.sourcing.availability]
      .filter(Boolean).join(' · ')) + '</div>';
  }
  // F12 (V2.53): the works behind every row, once each. An unattributable
  // record is counted, never dressed up as a reference.
  if (e.sources && (e.sources.works || []).length) {
    h += '<div class="isec">where the records come from</div><ul class="ilist plain">';
    for (const w of e.sources.works) h += '<li>' + esc(w) + '</li>';
    if (e.sources.unattributed) {
      h += '<li class="dim">' + e.sources.unattributed + ' of these records were '
        + 'seeded without naming a specific work, and are not yet attributable.</li>';
    }
    h += '</ul>';
  }
  // No free-text notes (V3.38, L8, P12): scene_dossier does not send them.
  return h + '</details>';
}

function canPlant(pid) {
  return Array.isArray(DOSSIER.plantable) && DOSSIER.plantable.indexOf(pid) >= 0
    && typeof window.permaEditReady === 'function' && window.permaEditReady();
}

function faunaCardHtml(e) {
  let h = backLink() + photoBlock(e);
  if (!faunaPhoto(e.name)) {
    h += '<div class="asign">' + (_GROUP_SIGN[e.taxon] || '') + '</div>';
  }
  h += cardHead(e, e.scientific_name + (e.taxon_label ? ' · ' + e.taxon_label : ''));
  if (e.status) h += chips([e.status], 'warn');
  if (e.description) h += '<div class="idesc">' + esc(e.description) + '</div>';
  h += seasonBar(e);
  if (e.facts && e.facts.length) {
    h += '<ul class="ilist plain">' + e.facts.map((f) => '<li>' + esc(f) + '</li>').join('') + '</ul>';
  }
  if (e.uses && e.uses.length) {
    h += '<div class="isec">here</div><ul class="ilist">';
    for (const u of e.uses) {
      h += '<li class="prow" data-open-plant="' + esc(u.plant_id) + '" tabindex="0"><b>'
        + esc(u.plant) + '</b><span class="how">' + esc(u.does || u.how + ' it')
        + '</span></li>';
    }
    h += '</ul>';
  }
  const away = e.elsewhere || [];
  if (away.length) {
    h += '<div class="isec">not here yet</div><ul class="ilist">';
    for (const p of away) {
      h += '<li><b>' + esc(p.name) + '</b>'
        + (p.plantable && canPlant(p.plant_id)
          ? ' <button class="plant-one" data-plant-one="' + esc(p.plant_id)
            + '">Plant one</button>' : '')
        + '<span class="how">' + esc(p.does) + '</span></li>';
    }
    h += '</ul>';
    const more = (e.elsewhere_total || 0) - away.length;
    if (more > 0) {
      h += '<div class="isrc">and ' + more + ' more plant' + (more === 1 ? '' : 's')
        + ' it is recorded using</div>';
    }
  }
  if (e.range_notes) h += '<div class="isrc">' + esc(e.range_notes) + '</div>';
  return h;
}

function cardHtml(entry) {
  return entry.kind === 'fauna' ? faunaCardHtml(entry) : plantCardHtml(entry);
}

// Open a card from a link on another one: the card you were on goes onto the
// trail, so the next card can lead back to it.
function openCard(type, key, back) {
  const k = type === 'plant' ? Number(key) : String(key);
  const entry = type === 'fauna' ? DOSSIER.fauna[k] : DOSSIER.plants[String(k)];
  if (!entry) return;
  if (!back && selection) cardTrail.push({ type: selection.type, key: selection.key });
  selection = { type: type, key: k };
  showCard(entry);
  buildThreads();
  // The discovery ledger counts a card opened from a link as one opened from
  // the scene (16-editing.js reports scene clicks the same way).
  if (typeof _bridge !== 'undefined' && _bridge && _bridge.inspected) {
    _bridge.inspected(type, String(k));
  }
}

function onCardClick(ev) {
  const t = ev.target.closest('[data-open-fauna],[data-open-plant],[data-card-back],[data-plant-one]');
  if (!t) return;
  ev.preventDefault();
  if (t.hasAttribute('data-plant-one')) {
    const pid = Number(t.getAttribute('data-plant-one'));
    if (typeof _bridge !== 'undefined' && _bridge && _bridge.choosePlant) {
      _bridge.choosePlant(pid);
      t.textContent = 'On the trowel: click the ground';
      t.disabled = true;
    }
  } else if (t.hasAttribute('data-card-back')) {
    const prev = cardTrail.pop();
    if (prev) openCard(prev.type, prev.key, true);
  } else if (t.hasAttribute('data-open-fauna')) {
    openCard('fauna', t.getAttribute('data-open-fauna'));
  } else {
    openCard('plant', t.getAttribute('data-open-plant'));
  }
}

function onCardKey(ev) {
  if (ev.key === 'Enter' && ev.target.matches('[data-open-fauna],[data-open-plant]')) {
    onCardClick(ev);
  }
}

for (const id of ['inspect-card', 'wild-roster']) {
  const el = document.getElementById(id);
  if (el) { el.addEventListener('click', onCardClick); el.addEventListener('keydown', onCardKey); }
}

// Which creatures Identify names (07-wildlife.js asks, through a typeof
// guard): with a plant's card open, the ones using that plant; with an
// animal's, that animal; with none, only the few nearest you. Until V3.39 it
// named every creature within 13 m.
function labelWanted(info, d) {
  if (!info) return false;
  if (selection && selection.type === 'plant') return info.onId === selection.key;
  if (selection && selection.type === 'fauna') return info.name === selection.key;
  return d <= 6;
}
