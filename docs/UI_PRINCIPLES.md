# UI principles

*Steve Krug, applied to this app.*

[`DESIGN_PHILOSOPHY.md`](DESIGN_PHILOSOPHY.md) is about what the app should
*mean*. This is about whether a person can use it. The two are not in tension,
but they fail differently, and this project has been much better at the first
than the second. A screen can be philosophically immaculate and still make
somebody stop and think.

The source is *Don't Make Me Think* (Steve Krug, 2000; *Revisited*, 3rd edition,
2014). It is short, it is about the web, and almost all of it transfers to a
desktop panel without modification. Added to [`REFERENCES.md`](REFERENCES.md).

---

## The three laws

**1. Don't make me think.** Every screen should be self-evident. Failing that,
self-explanatory. The measure is not "could a person work this out" but "does
anything make them pause, even briefly, to work it out". A question mark that
appears over somebody's head is a bug.

**2. It doesn't matter how many times I have to click, as long as each click is
a mindless, unambiguous choice.** Consolidating three obvious clicks into one
ambiguous one is a loss. This is the answer whenever someone proposes a screen
with fewer steps and more thinking per step.

**3. Get rid of half the words on each page. Then get rid of half of what's
left.** Krug is not exaggerating for effect. The V2.41 start screen lost about
60% of its words and got better at every one of its jobs.

## How people actually use software

Three findings, and all three are uncomfortable:

- **They scan, they don't read.** Nobody reads a screen. They glance at it
  looking for something that resembles what they want.
- **They satisfice.** They pick the first reasonable option, not the best one.
  Optimising is slow and guessing is cheap, so the *order* of your options
  matters more than their completeness.
- **They muddle through.** They do not work out how a thing works. They form a
  rough idea that is often wrong, and if it happens to work they keep it
  forever. So a control that works by accident will be used by accident.

Design for glancing, satisficing and muddling, not for the careful reader who
does not exist.

## Billboard Design 101

Krug's checklist for a screen, all of which apply to a Qt panel:

1. **Create a clear visual hierarchy.** More important means more prominent.
   Related things look related. Nested things look nested. If every element is
   the same weight, the screen is telling the user that everything matters
   equally, which is never true.
2. **Take advantage of conventions.** Do the boring, expected thing. `File >
   Open`, a magnifying glass for search, a checkbox for a preference. Inventing
   is a cost paid by every user; borrowing is free.
3. **Break the screen into clearly defined areas.** Areas let people ignore the
   parts they do not need, which is most of the screen most of the time.
4. **Make it obvious what's clickable.** Buttons look like buttons, links look
   like links, and anything you can click has a hover state and a hand cursor.
5. **Eliminate distractions.** Visual noise, competing emphasis, three things
   shouting at once.
6. **Format content to support scanning.** Headings that describe, short
   paragraphs, lists, key terms carrying meaning rather than decoration.

## Two things that must die

**Happy talk.** The introductory sentence that welcomes people and describes the
product's mission. Nobody reads it twice, it delays every visit forever, and it
is usually there because somebody felt the screen looked bare. Krug: "Happy talk
must die."

**Instructions.** If a screen needs a paragraph explaining how to use it, the
paragraph is a bandage. Fix the screen. The only surviving instructions should
be so short they do not look like instructions. Krug: "Instructions must die."

Both were on the first cut of the start screen. Both are gone.

## The reservoir of goodwill

Every user arrives with a limited reserve of patience. Things that drain it:

- Hiding what I want behind something you want me to see first.
- Punishing me for not doing things your way.
- Asking me for information you do not need.
- Putting sizzle in my way.
- Looking amateurish.

Things that refill it:

- Knowing the main things people want and making them obvious.
- Saving me steps.
- Answering the questions you know I will have.
- Making errors easy to recover from, and apologising when you cannot fix one.
- Putting visible effort into it.

This app has a specific version of the first drain: it is full of genuinely
excellent ecological reasoning that it wants to show you, and that reasoning is
frequently standing in front of the control you came for.

## Testing, cheaply

Krug's other book is *Rocket Surgery Made Easy*, and the argument in both is that
usability testing does not need a lab. **Three users, once a month, one morning.**
Watching one person use it is enormously better than watching none. You will
learn more in twenty minutes of silence while somebody tries to draw a boundary
than in a week of reasoning about it.

The rule while watching: do not help, do not explain, do not defend. Ask them to
think out loud. Write down where they pause.

The outside tester who produced [`USER_FEEDBACK.md`](USER_FEEDBACK.md) is exactly
this, and it has been the single highest-yield input the project has had. Every
round has found working features with a dead control in front of them.

---

## Applied: what the V2.41 start screen changed

The first cut of `src/start_screen.py` failed six of these at once. It is worth
recording precisely, because none of the failures felt like failures while
writing it. Each one felt like being helpful.

| What it did | Which rule | What replaced it |
|---|---|---|
| Opened with "Turn lawn into habitat for the plants, birds, bees and butterflies that already belong here." | Happy talk | Nothing. The name and the tagline already answer "what is this". |
| Closed with "Whichever you pick, the path is the same: 1. Drop a property pin, 2. Draw your boundary, 3. ..." | Instructions | Nothing. That belongs on the step bar, inside the app, where it is actionable. |
| Every row carried a sentence of description, most of it restating the title | Half the words, twice | A **fact about the user's own situation**: "3 saved", "434 native species", "Back Yard Meadow". Shorter, more useful, and only sayable once. |
| Six rows, identical boxes, identical weight, 74px each | Visual hierarchy | Resume rows grouped above a rule; three doors at 52px; one primary. |
| Secondary actions styled as dim text | Make it obvious what's clickable | Underlined, link-coloured, hand cursor. |
| Row title plus subtitle stacked in two lines | Scanning | Title left, fact right-aligned. The changing part is in a fixed place the eye can return to. |

The general lesson, which is the one worth keeping: **every single one of those
was added in good faith to make the screen more helpful.** Explaining is the
default failure mode of someone who knows the system well. The discipline is to
notice that an explanation is a confession that the thing being explained is not
self-evident, and to fix that instead.

## A checklist before shipping a screen

- [ ] Can a stranger tell what this is, and what they can do here, without
      reading a sentence?
- [ ] Is there one obvious place to start, and only one?
- [ ] Does anything on it explain rather than do? Can that be deleted by making
      the thing clearer?
- [ ] Halve the words. Now halve them again. What actually broke?
- [ ] Does every clickable thing look clickable, and nothing else does?
- [ ] Is anything the same visual weight as something more important?
- [ ] Does it follow the convention, or did we invent something?
- [ ] Does every control do something? (This project has shipped three dead
      controls: the sun slider connected to nothing, the never-applied quiz
      colouring, and a checkbox that could switch the start screen off but
      never on.)
- [ ] Would you be comfortable watching somebody use this without helping them?

## Where this is enforced

Nowhere automatically, and that is honest: usability is not a property a test
suite can assert. What `tests/test_start_menu.py` does hold is the parts that
have a shape:

- no prose block longer than eight words outside a control;
- every row's note is five words or fewer;
- at most one primary action on the screen;
- every offered choice is acted on by the flow module.

Those are proxies. The real check is the checklist above and somebody's face.
