# Card selection flows: hand vs draw pile

## Overview

This note documents how to build two user-driven card selection flows while reusing Slay the Spire's built-in selection screens:

* **ChooseFromHand** – prompt the player to pick one or more cards currently in hand and then run arbitrary follow-up code on the chosen set.
* **ChooseFromDrawPile** – display the draw pile in a grid selector, let the player pick card(s), and act on the result.

Both patterns rely entirely on existing screen classes (`HandCardSelectScreen` and `GridCardSelectScreen`) and the thin StSLib helper actions that already orchestrate them. Because the Python wrapper ships first-class bindings to those actions, the flows can be triggered directly from Python without writing new Java glue code.

## Prerequisites

* Import the unified wrapper facade and action queue helpers:
  ```python
  from modules.basemod_wrapper import spire
  from modules.basemod_wrapper.cards import _enqueue_action  # or use your own queue helper
  ```
* Every action created below must be enqueued (e.g. via `AbstractDungeon.actionManager.addToBottom`). The `_enqueue_action` helper shown above is a thin wrapper around that queue.【F:modules/basemod_wrapper/cards.py†L188-L198】

## ChooseFromHand via `SelectCardsInHandAction`

`SelectCardsInHandAction` opens the vanilla hand-selection screen (`AbstractDungeon.handCardSelectScreen`), filters the hand using a predicate, and feeds the selected cards back to a callback once the player confirms.【F:research/stslib_SelectCardsInHandAction.java†L1-L99】

### Key behaviours

* Filters out cards that fail the predicate before opening the screen and restores them afterwards.【F:research/stslib_SelectCardsInHandAction.java†L55-L93】
* Supports exact or "any number" picks and optional skip (`canPickZero`).【F:research/stslib_SelectCardsInHandAction.java†L37-L66】
* Short-circuits when the filtered hand already satisfies the requested amount (e.g. only one eligible card).【F:research/stslib_SelectCardsInHandAction.java†L63-L84】

### Python usage

```python
from modules.basemod_wrapper import spire
from modules.basemod_wrapper.cards import _enqueue_action

SelectCardsInHandAction = spire.action("select_cards_in_hand")  # Unified facade lookup.【F:modules/basemod_wrapper/__init__.py†L134-L182】【F:modules/basemod_wrapper/__init__.py†L215-L224】

def handle_selection(chosen):
    for card in chosen:
        card.upgrade()

action = SelectCardsInHandAction(
    1,                                # amount to pick
    "upgrade",                        # text appended to the base "Select X card(s) to" banner
    False,                            # anyNumber – force exact picks
    True,                             # canPickZero – allow skipping
    lambda c: c.type.name() == "SKILL",  # predicate (skills only)
    handle_selection                  # callback invoked with a java.util.List<AbstractCard>
)
_enqueue_action(action)
```

### Tips

* The callback runs once and receives the `selectedCards` list exactly as returned by the screen. Make sure to copy cards if you intend to queue additional actions that might reuse the list reference later.
* Call `AbstractDungeon.player.hand.refreshHandLayout()` or rely on the action's built-in `finish()` to restore ordering – the helper already refreshes layout and reapplies powers when the action ends.【F:research/stslib_SelectCardsInHandAction.java†L95-L101】

## ChooseFromDrawPile via `SelectCardsAction`

`SelectCardsAction` wraps the base grid selector (`AbstractDungeon.gridSelectScreen`) and works with any `CardGroup`, making it ideal for draw pile selection.【F:research/stslib_SelectCardsAction.java†L1-L90】

### Key behaviours

* Accepts an `ArrayList<AbstractCard>` source (e.g. `AbstractDungeon.player.drawPile.group`) and clones it into an internal `CardGroup` to avoid double-render "jiggle" issues.【F:research/stslib_SelectCardsAction.java†L22-L52】
* Applies an optional predicate before the screen opens so ineligible cards never appear.【F:research/stslib_SelectCardsAction.java†L42-L52】
* Automatically short-circuits when the filtered group size is below or equal to the required amount (and `anyNumber` is false).【F:research/stslib_SelectCardsAction.java†L60-L76】
* Opens the familiar grid screen with your custom prompt and respects `anyNumber`/`amount` constraints.【F:research/stslib_SelectCardsAction.java†L67-L74】

### Python usage

```python
from modules.basemod_wrapper import spire
from modules.basemod_wrapper.cards import _enqueue_action

SelectCardsAction = spire.action("select_cards")  # Uses the same action lookup table as above.【F:modules/basemod_wrapper/__init__.py†L134-L182】【F:modules/basemod_wrapper/__init__.py†L215-L224】

def move_to_hand(chosen):
    for card in list(chosen):
        AbstractDungeon.player.drawPile.removeCard(card)
        AbstractDungeon.actionManager.addToBottom(
            spire.cardcrawl.actions.common.MakeTempCardInHandAction(card)
        )

draw_pile = AbstractDungeon.player.drawPile.group

action = SelectCardsAction(
    draw_pile,
    2,                                 # pick up to 2 cards
    "move to your hand",              # bottom prompt string
    True,                              # anyNumber – allow selecting fewer than 2
    lambda c: not c.isCurse(),         # optional filter
    move_to_hand                       # callback handles the results
)
_enqueue_action(action)
```

### Tips

* Because the action returns the actual `selectedCards` list from the grid screen, always clear or copy it after use if you plan to mutate it later.
* The helper automatically clears `gridSelectScreen.selectedCards` and refreshes the player's hand after completion, so the queue stays in a clean state.【F:research/stslib_SelectCardsAction.java†L76-L89】
* For "select exactly N" behaviour, pass `anyNumber=False`; for optional picks (including zero) set it to `True`.

## Integration advice

* Both helpers are exposed via the global plugin manager (`PLUGIN_MANAGER.expose("spire", spire)`), so plugins can discover and call them without extra wiring.【F:modules/basemod_wrapper/__init__.py†L341-L371】
* When embedding the flows into existing card actions, always queue your follow-up work inside the callback (or queue a new action from within) to maintain the game's asynchronous action pipeline.
* If you need to interleave multiple selection flows in a single turn, guard against reusing the grid or hand screen while it's already open – the helper actions do this automatically by ticking until `selectedCards` is populated.
