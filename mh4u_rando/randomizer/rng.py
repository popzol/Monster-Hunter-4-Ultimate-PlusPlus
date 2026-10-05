"""Deterministic random streams.

Every quest and every aspect of it (monsters, rewards, ...) gets its own
`random.Random`, derived from the seed. Results are therefore reproducible,
independent of the order in which quests are processed, and toggling one
option (e.g. rewards) does not change the outcome of the others.
"""

import hashlib
import random
import secrets


def new_seed() -> str:
    return secrets.token_hex(5).upper()


def stream(seed: str, quest_id: int, purpose: str) -> random.Random:
    digest = hashlib.sha256(f"{seed}|{quest_id}|{purpose}".encode("utf-8")).digest()
    return random.Random(int.from_bytes(digest[:8], "little"))


def weighted_choice(rng: random.Random, weights: dict):
    """Pick a key of `weights` with probability proportional to its value."""
    keys = [k for k, w in weights.items() if w > 0]
    if not keys:
        raise ValueError("no candidate has a positive weight")
    return rng.choices(keys, weights=[weights[k] for k in keys], k=1)[0]
