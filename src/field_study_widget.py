"""
field_study_widget.py — the Field Study quiz runner UI (F48).

A small self-contained QWidget that walks the user through a
``src.field_study.generate_quiz`` set one question at a time: prompt (+ a cached
photo for identify questions), four choices, immediate right/wrong feedback with
the explanation, and a running score. All quiz logic is in the Qt-free
``field_study`` module; this only renders and tracks the flow.

Design principle P5 (retrieval practice builds the model) — see
docs/DESIGN_PHILOSOPHY.md.
"""

from __future__ import annotations

import random
from typing import Callable, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QComboBox, QFormLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)

#: The old quiz, a little of everything: photo names, the animals that depend
#: on a few plants, and the design's food-web gap (``field_study``). Kept as a
#: choice; the topics come first (V3.40, F208).
MIXED = "mixed"

_OK = "#a5d6a7"
_BAD = "#ef9a9a"
_OPT_STYLE = (
    "QPushButton { text-align: left; padding: 8px 10px; color: #e8f5e9; "
    "background: #1a2a1a; border: 1px solid #2e4a2e; border-radius: 4px; }"
    "QPushButton:hover:enabled { background: #24352420; border-color: #4a7a4a; }"
    "QPushButton:disabled { color: #c8e6c9; }"
)


class FieldStudyWidget(QWidget):
    """Quiz runner. ``plants_provider`` returns the current placed-plant list
    (so a new quiz is design-aware); pass ``None`` for a general quiz."""

    def __init__(self, plants_provider: Optional[Callable] = None, parent=None):
        super().__init__(parent)
        self._provider = plants_provider
        self._quiz: list[dict] = []
        self._i = 0
        self._score = 0
        self._answered = False
        # URLs already queued for warming this session, so pressing Restart ten
        # times doesn't re-request the same photos ten times.
        self._warmed: set[str] = set()
        # Stops the background photo warmer when this widget goes away. Owned
        # here (not created per-task) so a cancel that arrives before the task
        # starts is still honoured.
        import threading
        self._warm_cancel = threading.Event()
        # `destroyed` fires from C++ teardown, where `self` is already unusable,
        # so bind the flag itself rather than a method on the widget.
        self.destroyed.connect(lambda *_a, _c=self._warm_cancel: _c.set())
        self._build()

    def cancel_background_work(self):
        """Stop the photo warmer. Safe to call more than once.

        Called on `destroyed`, and worth calling explicitly from anything that
        tears this widget down deliberately — Qt's destruction ordering is not
        something to rely on for stopping a thread.
        """
        self._warm_cancel.set()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(8)

        intro = QLabel(
            "Practise one thing at a time: naming plants, who uses whom, and "
            "when and where plants grow.")
        intro.setWordWrap(True)
        intro.setStyleSheet("color: #90a4ae; font-size: 12px;")
        lay.addWidget(intro)

        # What to practise, about which plants, and how long (V3.40, F208).
        from src import quiz_topics
        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        self._topic = QComboBox()
        self._topic.setAccessibleName("What to practise")
        for _g, group_words, topics in quiz_topics.GROUPS:
            self._add_heading(group_words)
            for key, words in topics:
                self._topic.addItem(words, key)
        self._add_heading("Mixed")
        self._topic.addItem("A bit of everything", MIXED)
        self._topic.setCurrentIndex(self._topic.findData("any_plant"))
        form.addRow("Practise", self._topic)
        self._focus = QComboBox()
        self._focus.setAccessibleName("Which plants")
        for key, words in quiz_topics.focus_options():
            self._focus.addItem(words, key)
        form.addRow("Plants", self._focus)
        self._length = QComboBox()
        self._length.setAccessibleName("How many questions")
        for n in quiz_topics.LENGTHS:
            self._length.addItem(f"{n} questions", n)
        self._length.setCurrentIndex(self._length.findData(10))
        form.addRow("Length", self._length)
        lay.addLayout(form)
        self._status = QLabel("")
        self._status.setWordWrap(True)
        self._status.setStyleSheet("color: #9ccc9c; font-size: 12px;")
        lay.addWidget(self._status)
        for box in (self._topic, self._focus):
            box.currentIndexChanged.connect(lambda _i: self._update_status())

        self._start_btn = QPushButton("Start a quiz")
        self._start_btn.setStyleSheet(
            "QPushButton { background: #2e7d32; color: #e8f5e9; border: 1px solid "
            "#43a047; border-radius: 4px; padding: 6px; font-weight: bold; }"
            "QPushButton:hover { background: #388e3c; }")
        self._start_btn.clicked.connect(self.new_quiz)
        lay.addWidget(self._start_btn)

        self._progress = QLabel("")
        self._progress.setStyleSheet("color: #a5d6a7; font-size: 12px; font-weight: bold;")
        lay.addWidget(self._progress)

        self._photo = QLabel("")
        self._photo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._photo.setVisible(False)
        lay.addWidget(self._photo)

        self._prompt = QLabel("")
        self._prompt.setWordWrap(True)
        self._prompt.setStyleSheet("color: #e8f5e9; font-size: 13px; font-weight: bold;")
        self._prompt.setVisible(False)
        lay.addWidget(self._prompt)

        self._hint = QLabel("")
        self._hint.setWordWrap(True)
        self._hint.setStyleSheet("color: #9ccc9c; font-size: 12px; font-style: italic;")
        self._hint.setVisible(False)
        lay.addWidget(self._hint)

        self._opt_btns: list[QPushButton] = []
        for i in range(4):
            b = QPushButton("")
            # Its text is the answer, set with each question, and names it;
            # tests/test_app_smoke reads this to know (V3.02).
            b.setProperty("namedByContent", True)
            b.setStyleSheet(_OPT_STYLE)
            b.clicked.connect(lambda _=False, idx=i: self._answer(idx))
            b.setVisible(False)
            lay.addWidget(b)
            self._opt_btns.append(b)

        self._explain = QLabel("")
        self._explain.setWordWrap(True)
        self._explain.setVisible(False)
        self._explain.setStyleSheet(
            "color: #dcedc8; font-size: 12px; padding: 8px; background: #1a2a1a; "
            "border: 1px solid #2e4a2e; border-radius: 4px;")
        lay.addWidget(self._explain)

        self._next_btn = QPushButton("Next →")
        self._next_btn.setVisible(False)
        self._next_btn.clicked.connect(self._next)
        lay.addWidget(self._next_btn)

        lay.addStretch()
        self._update_status()

    def _add_heading(self, words: str):
        """A group's name in the topic list: bold, shown, not choosable."""
        self._topic.addItem(words, "")
        item = self._topic.model().item(self._topic.count() - 1)
        item.setEnabled(False)
        font = item.font()
        font.setBold(True)
        item.setFont(font)

    def set_landscape_words(self, words: str):
        """What the landscape topic calls the plants it asks about ("the
        landscape you walked" in the Learn window, "this design" in the main
        window's Learn tab)."""
        self._where = words

    def set_topic(self, key: str):
        """Choose a topic (``quiz_topics`` key, or ``MIXED``)."""
        i = self._topic.findData(key)
        if i >= 0:
            self._topic.setCurrentIndex(i)

    def _choice(self) -> tuple:
        return (self._topic.currentData() or MIXED,
                self._focus.currentData() or "all",
                int(self._length.currentData() or 10))

    def _update_status(self):
        """What the chosen topic has to work with, and the best so far: how
        many of its photographs are on this computer, or that it is about the
        landscape you walked."""
        from src import quiz_topics
        topic, focus, _n = self._choice()
        self._focus.setEnabled(topic not in ("landscape", MIXED))
        lines = []
        try:
            if topic in quiz_topics.PHOTO_TOPICS:
                from src.db.plants import get_all_plants
                have, total = quiz_topics.photo_status(
                    topic, focus, get_all_plants(),
                    quiz_topics._default_image_ok)
                lines.append(f"{have} of {total} photographs of these plants "
                             "are on this computer."
                             + (" The rest download while you play, when "
                                "you are connected." if have < total else ""))
            elif topic == "landscape":
                lines.append(f"About {getattr(self, '_where', '') or quiz_topics.WALKED}: "
                             "its plants, and who would lose the only plant "
                             "there they use.")
            score, out_of = quiz_topics.best(topic, focus)
            if out_of:
                lines.append(f"Your best: {score} of {out_of}.")
        except Exception:      # noqa: BLE001 — a status line is a nicety
            pass
        self._status.setText(" ".join(lines))

    # ── flow ──────────────────────────────────────────────────────────────

    def _make_quiz(self, plants) -> list:
        topic, focus, n = self._choice()
        seed = random.randrange(1 << 30)
        if topic == MIXED:
            from src.field_study import generate_quiz
            return generate_quiz(plants, seed=seed, n=n)
        from src.quiz_topics import WALKED, build_quiz
        return build_quiz(topic, focus=focus, n=n, seed=seed,
                          walk_plants=plants or [],
                          where=getattr(self, "_where", "") or WALKED)

    def _why_empty(self) -> str:
        """Why a topic made no questions, in words, rather than another
        topic's questions in its place."""
        from src import quiz_topics
        topic, _focus, _n = self._choice()
        if topic in quiz_topics.PHOTO_TOPICS:
            return ("No photographs of these plants are on this computer yet. "
                    "They download in the background while you are connected; "
                    "try again in a minute, or choose a topic without "
                    "photographs.")
        if topic == "landscape":
            return ("Walk a landscape and plant in it first: these questions "
                    "are about the plants you walked among.")
        return ("Too few plants for this topic in the chosen plants. Try "
                "Every plant.")

    def new_quiz(self):
        plants = None
        if self._provider is not None:
            try:
                plants = self._provider() or None
            except Exception:      # noqa: BLE001
                plants = None
        try:
            self._quiz = self._make_quiz(plants)
        except Exception:      # noqa: BLE001
            self._quiz = []
        # Name-the-plant questions only cover plants whose photo is already
        # cached, so warm the chosen topic's photos first (V3.40) — the pool
        # grows with every quiz, and works offline once cached.
        self._warm_photo_pool()
        self._i = 0
        self._score = 0
        self._answered = False
        self._start_btn.setText("Restart quiz")
        if not self._quiz:
            # Leaving the previous question's buttons live here was a crash:
            # the next click indexed an empty quiz, and an IndexError escaping a
            # Qt slot aborts the process rather than raising.
            self._clear_question()
            try:
                self._progress.setText(self._why_empty())
            except Exception:      # noqa: BLE001
                self._progress.setText("Quiz unavailable — the plant database "
                                       "couldn't be read.")
            return
        asked = self._choice()[2]
        if len(self._quiz) < asked:
            self._status.setText(f"Only {len(self._quiz)} questions could be "
                                 "made on this topic from these plants.")
        self._show()

    def _clear_question(self):
        """Take every question control off screen. Used when there is no
        question to show, so nothing clickable outlives the quiz behind it."""
        self._prompt.setVisible(False)
        self._hint.setVisible(False)
        self._photo.setVisible(False)
        self._explain.setVisible(False)
        self._next_btn.setVisible(False)
        for b in self._opt_btns:
            b.setEnabled(False)
            b.setVisible(False)

    def _warm_photo_pool(self, limit: int = 8):
        """Fetch+cache a few not-yet-cached photos in the background, so the
        identify pool grows with every quiz: the chosen topic's plants first,
        up to 40 of them (V3.40), else a few from the whole catalogue.

        Sequential, via the shared :class:`~src.photo_warm.PhotoWarmer`, rather
        than the eight parallel tasks this used to start on the global pool.
        That warmer is deliberately serial with a courtesy delay because ~380 of
        these requests go to one host, and being a single writer is also what
        keeps the shared metadata index consistent. Failures are silent — a
        missing photo just stays out of the pool.
        """
        try:
            from src import quiz_topics
            from src.db.plants import get_all_plants
            from src.image_cache import get_cached_image
            from src.photo_warm import photo_rows
            topic, focus, _n = self._choice()
            catalogue = get_all_plants()
            chosen = quiz_topics.photo_plants(topic, focus, catalogue)
            if chosen:
                limit = max(limit, 40)
            pending = [row for row in photo_rows(chosen or catalogue)
                       if row[0] not in self._warmed
                       and not get_cached_image(row[0])]
        except Exception:      # noqa: BLE001
            return
        if not pending:
            return
        batch = random.sample(pending, min(limit, len(pending)))
        # Remember before starting: a URL queued twice is wasted work, and the
        # user can press Restart faster than a fetch completes.
        self._warmed.update(url for url, _a, _l in batch)

        from PyQt6.QtCore import QRunnable, QThreadPool

        # The warmer is sequential with a courtesy delay, so it lives for a few
        # seconds — long enough to outlive the widget that started it if the
        # user closes the tab, and a task still running while Qt tears down
        # around it is how a background fetch turns into a crash. It takes a
        # cancel event for exactly this; `destroyed` sets it, and PhotoWarmer
        # checks it between items and waits on it instead of sleeping, so a
        # cancel lands immediately rather than after the current gap.
        cancel = self._warm_cancel

        class _WarmTask(QRunnable):
            def __init__(self, items):
                super().__init__()
                self._items = items

            def run(self):
                try:
                    from src.photo_warm import PhotoWarmer
                    PhotoWarmer(self._items, cancel_event=cancel).run()
                except Exception:      # noqa: BLE001
                    pass

        QThreadPool.globalInstance().start(_WarmTask(batch))

    def _show(self):
        if not self._quiz or not 0 <= self._i < len(self._quiz):
            self._clear_question()
            return
        q = self._quiz[self._i]
        self._answered = False
        self._progress.setText(f"Question {self._i + 1} of {len(self._quiz)}   "
                               f"·   score {self._score}")
        self._prompt.setText(q["prompt"]); self._prompt.setVisible(True)
        self._hint.setText(q.get("hint", "")); self._hint.setVisible(bool(q.get("hint")))
        self._set_photo(q.get("image_url", ""))
        for i, b in enumerate(self._opt_btns):
            if i < len(q["options"]):
                b.setText(q["options"][i])
                b.setStyleSheet(_OPT_STYLE)
                b.setEnabled(True)
                b.setVisible(True)
            else:
                b.setVisible(False)
        self._explain.setVisible(False)
        self._next_btn.setVisible(False)

    def _set_photo(self, url: str):
        pm = None
        if url:
            try:
                from src.image_cache import get_cached_image
                path = get_cached_image(url)
                if path:
                    pm = QPixmap(path)
            except Exception:      # noqa: BLE001
                pm = None
        if pm and not pm.isNull():
            self._photo.setPixmap(pm.scaledToHeight(
                150, Qt.TransformationMode.SmoothTransformation))
            self._photo.setVisible(True)
        else:
            self._photo.setVisible(False)

    def _answer(self, idx: int):
        # Guard the index as well as the answered flag: this is a slot, and a
        # click that arrives when the quiz is empty (a failed restart) or out of
        # range would take an IndexError straight out of Qt and abort the app.
        if self._answered or not self._quiz or not 0 <= self._i < len(self._quiz):
            return
        self._answered = True
        q = self._quiz[self._i]
        correct = q["answer_index"]
        if idx == correct:
            self._score += 1
        for i, b in enumerate(self._opt_btns[:len(q["options"])]):
            b.setEnabled(False)
            # NB: one closing brace. The doubled `}}` only escapes inside an
            # f-string, and these continuation lines are plain literals — so the
            # rule reached Qt unbalanced and the whole stylesheet was dropped,
            # silently costing the right/wrong colouring this method exists for.
            if i == correct:
                b.setStyleSheet(_OPT_STYLE + f"QPushButton {{ color: {_OK}; "
                                "border-color: #43a047; font-weight: bold; }")
            elif i == idx:
                b.setStyleSheet(_OPT_STYLE + f"QPushButton {{ color: {_BAD}; "
                                "border-color: #b04a4a; }")
        verdict = "✓ Correct. " if idx == correct else "✗ Not quite. "
        self._explain.setText(verdict + q.get("explanation", ""))
        self._explain.setVisible(True)
        self._progress.setText(f"Question {self._i + 1} of {len(self._quiz)}   "
                               f"·   score {self._score}")
        self._next_btn.setText("See results" if self._i + 1 >= len(self._quiz)
                               else "Next →")
        self._next_btn.setVisible(True)

    def _next(self):
        if self._i + 1 >= len(self._quiz):
            self._finish()
            return
        self._i += 1
        self._show()

    def _finish(self):
        total = len(self._quiz)
        for b in self._opt_btns:
            b.setVisible(False)
        self._photo.setVisible(False)
        self._hint.setVisible(False)
        self._next_btn.setVisible(False)
        pct = round(100 * self._score / total) if total else 0
        self._prompt.setText(f"Quiz complete — {self._score} / {total} ({pct}%)")
        self._prompt.setVisible(True)
        try:
            from src import quiz_topics
            topic, focus, _n = self._choice()
            if quiz_topics.record(topic, focus, self._score, total):
                self._prompt.setText(self._prompt.text() + "  ·  your best yet")
            self._update_status()
        except Exception:      # noqa: BLE001 — a best score is a nicety
            pass
        msg = ("Field-ready! You know your natives and their relationships."
               if pct >= 80 else
               "Good start — replay to lock it in, then go check outside."
               if pct >= 50 else
               "Every naturalist starts here. Replay and watch the patterns click.")
        self._explain.setText(msg)
        self._explain.setVisible(True)
        self._progress.setText("")
