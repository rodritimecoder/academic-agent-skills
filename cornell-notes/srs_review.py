#!/usr/bin/env python3
"""
srs_review.py - Spaced Repetition (SM-2) engine for Cornell Notes.

Manages review scheduling for cue-note pairs using a sidecar `.srs.json` file.
Implements the classic SM-2 algorithm:
- Fail (Again): resets interval to 1 day.
- Hard: 1-2 days.
- Good: 3 days (then scaled by ease factor: 3d -> 7d -> 18d...).
- Easy: 4+ days with bonus.

Usage:
  # Check review status / due cards across notes
  python3 srs_review.py status <notes.json>

  # Start an interactive CLI review session for cards due today
  python3 srs_review.py review <notes.json>

  # Synchronize / initialize SRS state from notes JSON
  python3 srs_review.py init <notes.json>
"""

import sys
import os
import json
import hashlib
from datetime import datetime, date, timedelta
from pathlib import Path
import argparse


def card_id(heading: str, cue: str) -> str:
    """Generate a stable, human-readable hash key for a cue."""
    content = f"{heading.strip()}||{cue.strip()}".encode("utf-8")
    return hashlib.sha256(content).hexdigest()[:12]


def load_srs_state(srs_path: Path) -> dict:
    if srs_path.exists():
        try:
            with open(srs_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_srs_state(srs_path: Path, state: dict):
    srs_path.parent.mkdir(parents=True, exist_ok=True)
    with open(srs_path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def extract_cards(notes_data: dict) -> list[dict]:
    cards = []
    for section in notes_data.get("sections", []):
        heading = section.get("heading", "General")
        for entry in section.get("entries", []):
            cue = entry.get("cue", "").strip()
            notes = entry.get("notes", "").strip()
            cid = card_id(heading, cue)
            cards.append({
                "id": cid,
                "heading": heading,
                "cue": cue,
                "notes": notes,
                "type": entry.get("type", "concept")
            })
    return cards


def calculate_sm2(quality: int, reps: int, interval_days: int, ease_factor: float) -> tuple[int, int, float, str]:
    """
    Quality ratings:
      0: Total blackout (Again / Fail)
      1: Incorrect answer
      2: Hard (Correct with hesitation)
      3: Good (Correct with normal effort) -> 1d -> 3d -> (prev * ease)
      4: Easy (Flawless recall)
    """
    today = date.today()

    if quality < 2:
        # Failed / Again
        reps = 0
        interval_days = 1
    elif quality == 2:
        # Hard: short interval, ease penalty
        if reps == 0:
            interval_days = 1
        elif reps == 1:
            interval_days = 2
        else:
            interval_days = max(2, int(interval_days * 1.2))
        reps += 1
    elif quality == 3:
        # Good: Standard SM-2 interval progression (1 -> 3 -> prev * ease)
        if reps == 0:
            interval_days = 1
        elif reps == 1:
            interval_days = 3
        else:
            interval_days = int(round(interval_days * ease_factor))
        reps += 1
    else:
        # Easy (quality >= 4): Accelerated interval
        if reps == 0:
            interval_days = 2
        elif reps == 1:
            interval_days = 4
        else:
            interval_days = int(round(interval_days * ease_factor * 1.3))
        reps += 1

    # Adjust ease factor (minimum 1.3)
    ease_factor = max(1.3, ease_factor + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)))
    due_date = (today + timedelta(days=interval_days)).isoformat()

    return reps, interval_days, round(ease_factor, 2), due_date


def cmd_status(notes_path: Path):
    srs_path = notes_path.with_suffix(".srs.json")
    with open(notes_path, "r", encoding="utf-8") as f:
        notes_data = json.load(f)

    cards = extract_cards(notes_data)
    state = load_srs_state(srs_path)

    today = date.today().isoformat()
    due_cards = []
    unreviewed_cards = []
    future_cards = []

    for card in cards:
        cid = card["id"]
        c_state = state.get(cid)
        if not c_state:
            unreviewed_cards.append(card)
        else:
            due_date = c_state.get("due_date", today)
            if due_date <= today:
                due_cards.append((card, c_state))
            else:
                future_cards.append((card, c_state))

    print(f"\n=======================================================")
    print(f"SRS Status: {notes_data.get('title', notes_path.stem)}")
    print(f"State file: {srs_path.name}")
    print(f"Total cards: {len(cards)}")
    print(f"  - New / Unreviewed: {len(unreviewed_cards)}")
    print(f"  - Due Today:        {len(due_cards)}")
    print(f"  - Future / Learned: {len(future_cards)}")
    print(f"=======================================================\n")

    if due_cards:
        print("Cards Due Today:")
        for card, c_state in due_cards[:5]:
            print(f"  * [{card['heading']}] {card['cue'][:60]}... (Interval: {c_state.get('interval_days', 1)}d)")
        if len(due_cards) > 5:
            print(f"  ... and {len(due_cards) - 5} more.")
    elif unreviewed_cards:
        print("Ready to start! Run 'srs_review.py review' to study new cards.")
    else:
        print("🎉 All caught up for today! Come back tomorrow.")


def cmd_review(notes_path: Path):
    srs_path = notes_path.with_suffix(".srs.json")
    with open(notes_path, "r", encoding="utf-8") as f:
        notes_data = json.load(f)

    cards = extract_cards(notes_data)
    state = load_srs_state(srs_path)
    today = date.today().isoformat()

    # Prioritize cards due today, then new cards
    due_queue = []
    new_queue = []

    for card in cards:
        cid = card["id"]
        if cid in state:
            if state[cid].get("due_date", today) <= today:
                due_queue.append(card)
        else:
            new_queue.append(card)

    deck = due_queue + new_queue

    if not deck:
        print("\n🎉 Excellent! No cards are due for review right now.")
        return

    print(f"\n🧠 Starting Spaced-Repetition Session: {len(deck)} card(s) ready")
    print(f"Instructions: Press ENTER to reveal the answer, then rate your recall (1-4). Type 'q' to quit.\n")

    reviewed_count = 0

    for idx, card in enumerate(deck, 1):
        cid = card["id"]
        c_state = state.get(cid, {
            "reps": 0,
            "interval_days": 1,
            "ease_factor": 2.5,
            "due_date": today
        })

        print(f"-------------------------------------------------------")
        print(f"Card {idx}/{len(deck)} [{card['heading']}]")
        print(f"PROMPT (Cue): \033[1;36m{card['cue']}\033[0m")
        print("-------------------------------------------------------")

        user_input = input("\n[Press Enter to reveal answer, or 'q' to quit]: ")
        if user_input.strip().lower() == 'q':
            break

        print("\n\033[1;32mANSWER (Notes):\033[0m")
        print(card["notes"])
        print("\nRate recall:")
        print("  1 = Again/Fail  (1 day reset)")
        print("  2 = Hard        (1-2 days)")
        print("  3 = Good/Pass   (3 days / interval * ease)")
        print("  4 = Easy        (Accelerated interval)")

        while True:
            choice = input("Your rating [1-4, default=3]: ").strip()
            if choice == "":
                quality = 3
                break
            if choice in ["1", "2", "3", "4"]:
                quality = int(choice)
                break
            if choice.lower() == "q":
                break
            print("Please enter 1, 2, 3, or 4.")

        if choice.lower() == "q":
            break

        # Compute next SM-2 schedule
        reps, interval, ease, next_due = calculate_sm2(
            quality,
            c_state.get("reps", 0),
            c_state.get("interval_days", 1),
            c_state.get("ease_factor", 2.5)
        )

        state[cid] = {
            "heading": card["heading"],
            "cue": card["cue"],
            "reps": reps,
            "interval_days": interval,
            "ease_factor": ease,
            "due_date": next_due,
            "last_reviewed": today
        }

        # Persist immediately so progress isn't lost
        save_srs_state(srs_path, state)
        reviewed_count += 1
        print(f"✓ Scheduled: next review in \033[1m{interval} day(s)\033[0m on {next_due}\n")

    print(f"\nSession finished! Reviewed {reviewed_count} card(s). State saved to {srs_path.name}")


def discover_notes_files(target: Path) -> list[Path]:
    if target.is_file():
        return [target]
    elif target.is_dir():
        return sorted(list(target.rglob("*_cornell.json")))
    return []


def cmd_status_all(target: Path):
    notes_files = discover_notes_files(target)
    if not notes_files:
        print(f"No '*_cornell.json' notes found in {target}")
        return

    today = date.today().isoformat()
    total_cards = 0
    total_due = 0
    total_new = 0

    print(f"\n=======================================================")
    print(f"📚 Spaced Repetition Status across {len(notes_files)} note document(s)")
    print(f"=======================================================")

    for nf in notes_files:
        srs_path = nf.with_suffix(".srs.json")
        try:
            with open(nf, "r", encoding="utf-8") as f:
                data = json.load(f)
            cards = extract_cards(data)
            state = load_srs_state(srs_path)
            due_count = sum(1 for c in cards if c["id"] in state and state[c["id"]].get("due_date", today) <= today)
            new_count = sum(1 for c in cards if c["id"] not in state)

            total_cards += len(cards)
            total_due += due_count
            total_new += new_count

            title = data.get("title", nf.stem)
            print(f"• {title}")
            print(f"    Cards: {len(cards)} | Due Today: \033[1;33m{due_count}\033[0m | New: {new_count}")
        except Exception as e:
            print(f"• {nf.name}: Error reading ({e})")

    print(f"-------------------------------------------------------")
    print(f"Total across all subjects: {total_cards} cards")
    print(f"  - Due for review today: \033[1;32m{total_due}\033[0m")
    print(f"  - Unreviewed / New:     \033[1;36m{total_new}\033[0m")
    print(f"=======================================================\n")


def cmd_review_all(target: Path):
    notes_files = discover_notes_files(target)
    if not notes_files:
        print(f"No '*_cornell.json' notes found in {target}")
        return

    today = date.today().isoformat()
    due_cards = []
    new_cards = []

    for nf in notes_files:
        srs_path = nf.with_suffix(".srs.json")
        try:
            with open(nf, "r", encoding="utf-8") as f:
                data = json.load(f)
            cards = extract_cards(data)
            state = load_srs_state(srs_path)
            for c in cards:
                c["_srs_path"] = srs_path
                c["_doc_title"] = data.get("title", nf.stem)
                cid = c["id"]
                if cid in state:
                    if state[cid].get("due_date", today) <= today:
                        due_cards.append((c, state))
                else:
                    new_cards.append((c, state))
        except Exception:
            continue

    deck = due_cards + new_cards

    if not deck:
        print("\n🎉 Excellent! No cards are due for review across your notes right now.")
        return

    print(f"\n🧠 Cross-Subject Review Deck: {len(deck)} card(s) ready")
    print(f"Instructions: Press ENTER to reveal the answer, then rate your recall (1-4). Type 'q' to quit.\n")

    reviewed_count = 0

    for idx, (card, state) in enumerate(deck, 1):
        cid = card["id"]
        c_state = state.get(cid, {
            "reps": 0,
            "interval_days": 1,
            "ease_factor": 2.5,
            "due_date": today
        })

        print(f"-------------------------------------------------------")
        print(f"Card {idx}/{len(deck)} [{card['_doc_title']} / {card['heading']}]")
        print(f"PROMPT (Cue): \033[1;36m{card['cue']}\033[0m")
        print("-------------------------------------------------------")

        user_input = input("\n[Press Enter to reveal answer, or 'q' to quit]: ")
        if user_input.strip().lower() == 'q':
            break

        print("\n\033[1;32mANSWER (Notes):\033[0m")
        print(card["notes"])
        print("\nRate recall:")
        print("  1 = Again/Fail  (1 day reset)")
        print("  2 = Hard        (1-2 days)")
        print("  3 = Good/Pass   (3 days / interval * ease)")
        print("  4 = Easy        (Accelerated interval)")

        while True:
            choice = input("Your rating [1-4, default=3]: ").strip()
            if choice == "":
                quality = 3
                break
            if choice in ["1", "2", "3", "4"]:
                quality = int(choice)
                break
            if choice.lower() == "q":
                break
            print("Please enter 1, 2, 3, or 4.")

        if choice.lower() == "q":
            break

        reps, interval, ease, next_due = calculate_sm2(
            quality,
            c_state.get("reps", 0),
            c_state.get("interval_days", 1),
            c_state.get("ease_factor", 2.5)
        )

        state[cid] = {
            "heading": card["heading"],
            "cue": card["cue"],
            "reps": reps,
            "interval_days": interval,
            "ease_factor": ease,
            "due_date": next_due,
            "last_reviewed": today
        }

        save_srs_state(card["_srs_path"], state)
        reviewed_count += 1
        print(f"✓ Scheduled: next review in \033[1m{interval} day(s)\033[0m on {next_due}\n")

    print(f"\nSession finished! Reviewed {reviewed_count} card(s).")


def main():
    parser = argparse.ArgumentParser(description="Spaced Repetition (SM-2) Engine for Cornell Notes")
    subparsers = parser.add_subparsers(dest="command", required=True)

    status_parser = subparsers.add_parser("status", help="Show review stats and due cards (file or folder)")
    status_parser.add_argument("notes_target", help="Path to Cornell JSON file or folder containing Cornell notes")

    review_parser = subparsers.add_parser("review", help="Launch interactive CLI review session (file or folder)")
    review_parser.add_argument("notes_target", help="Path to Cornell JSON file or folder containing Cornell notes")

    args = parser.parse_args()
    target = Path(args.notes_target)

    if not target.exists():
        print(f"Error: Target '{target}' does not exist.", file=sys.stderr)
        sys.exit(1)

    if args.command == "status":
        cmd_status_all(target)
    elif args.command == "review":
        cmd_review_all(target)


if __name__ == "__main__":
    main()
