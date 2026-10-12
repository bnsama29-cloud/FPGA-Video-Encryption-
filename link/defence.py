"""Attack-aware adaptive protection (runs on the sender = the board's ARM core).

What it can and cannot see
--------------------------
A passive eavesdropper sends nothing, so no system can observe it or learn "how
it steals data". That is why every policy has a floor (`min_mode`): the link is
never less protected than that, attack or no attack. What the sender CAN observe,
through the authenticated feedback channel and its own sockets, is evidence of
ACTIVE attacks: forged or modified frames (tag failures), replays, frames that
never arrive (suppression / jamming / loss), forged or replayed feedback, and
the feedback going silent (dead-man rule). The policy raises protection when
that evidence appears and lowers it again when it is gone, trading leakage
(how much an eavesdropper could reconstruct) against cost (encrypted bits).

Policies
--------
fixed      always `base` mode; no reaction (baseline for the paper)
threshold  hand-written rules: strong evidence -> max mode for hold_s, rekey on
           tag-failure bursts, dead-man -> max mode + rekey
bandit     contextual bandit (epsilon-greedy Q-table) over a small discrete
           context. Reward = -(evidence_next * leakage[mode] + w_cost * cost[mode]
           + w_switch * changed). The Q-table is saved to memory_file, so what it
           learned in one attack episode is used the next time the same context
           appears ("counteract next time"): measured as time-to-mitigate per episode.
All non-fixed policies share the safety layer (dead-man rule, rekey rate limit).
"""
import json
import math
import random
import time
from dataclasses import dataclass, field
from pathlib import Path

MODES = ["E0", "E1", "E2", "E3", "E4", "E5"]


def mode_index(m):
    return MODES.index(m)


@dataclass
class Window:
    """Evidence collected during one defence window (filled by the sender)."""
    ok: int = 0
    lost: int = 0
    tag_fail: int = 0
    replay: int = 0
    malformed: int = 0
    stale_epoch: int = 0
    fb_ok: int = 0
    fb_forged: int = 0
    fb_replay: int = 0
    hb_age: float = 0.0
    sent: int = 0                 # frames the sender transmitted in this window
    alerts: list = field(default_factory=list)

    def features(self, deadman_s):
        frames = self.ok + self.lost
        loss = self.lost / frames if frames else (1.0 if self.hb_age > deadman_s else 0.0)
        # video suppressed while heartbeats still arrive: the receiver cannot count
        # gaps it never sees the end of, but the sender knows what it sent
        if self.sent >= 3 and self.ok == 0 and self.fb_ok > 0 and self.hb_age <= deadman_s:
            loss = 1.0
        return dict(
            integrity=int(self.tag_fail + self.malformed + self.stale_epoch > 0),
            replay=int(self.replay > 0),
            loss_level=0 if loss < 0.05 else (1 if loss < 0.3 else 2),
            feedback_attack=int(self.fb_forged + self.fb_replay > 0),
            deadman=int(self.hb_age > deadman_s),
            loss=round(loss, 3),
        )


def threat_score(f):
    """0..1 evidence that an active attacker is present (shown on the dashboard)."""
    s = (1.0 * f["integrity"] + 1.0 * f["replay"] + 0.8 * f["feedback_attack"]
         + 1.0 * f["deadman"] + 0.25 * f["loss_level"])
    return min(1.0, s)


@dataclass
class Decision:
    mode: str
    rekey: bool = False
    reason: str = ""


class Policy:
    name = "base"

    def __init__(self, cfg, base_mode):
        d = cfg["defence"]
        self.d = d
        self.base = base_mode
        self.min_mode = base_mode
        self.max_mode = d["max_mode"]
        self.last_rekey = -1e9
        self.mode = base_mode

    def _clamp(self, m):
        i = max(mode_index(self.min_mode), min(mode_index(self.max_mode), mode_index(m)))
        return MODES[i]

    def _rekey_allowed(self, now):
        return now - self.last_rekey >= self.d["rekey_min_interval_s"]

    def safety(self, w, f, now, dec):
        """Dead-man rule and rekey triggers, shared by the adaptive policies."""
        if f["deadman"]:
            dec.mode = self.max_mode
            dec.reason = (dec.reason + "; " if dec.reason else "") + "dead-man: no valid heartbeat"
            if self._rekey_allowed(now):
                dec.rekey = True
        if w.tag_fail >= self.d["rekey_on_tag_fail"] and self._rekey_allowed(now):
            dec.rekey = True
            dec.reason = (dec.reason + "; " if dec.reason else "") + f"rekey: {w.tag_fail} tag failures"
        if dec.rekey:
            self.last_rekey = now
        return dec

    def decide(self, w, f, now):
        raise NotImplementedError

    def info(self):
        return {}


class FixedPolicy(Policy):
    name = "fixed"

    def decide(self, w, f, now):
        return Decision(self.base, False, "fixed")


class ThresholdPolicy(Policy):
    name = "threshold"

    def __init__(self, cfg, base_mode):
        super().__init__(cfg, base_mode)
        self.until = 0.0

    def decide(self, w, f, now):
        strong = f["integrity"] or f["replay"] or f["feedback_attack"]
        if strong:
            self.until = now + self.d["hold_s"]
            dec = Decision(self.max_mode, False, "active attack evidence")
        elif f["loss_level"] == 2:
            self.until = max(self.until, now + self.d["hold_s"] / 2)
            dec = Decision(self.max_mode, False, "heavy loss (possible jamming)")
        elif now < self.until:
            dec = Decision(self.mode, False, "holding after evidence")
        else:
            dec = Decision(self.base, False, "calm")
        dec = self.safety(w, f, now, dec)
        dec.mode = self._clamp(dec.mode)
        self.mode = dec.mode
        return dec


class BanditPolicy(Policy):
    name = "bandit"

    def __init__(self, cfg, base_mode, memory_file=None, seed=None):
        super().__init__(cfg, base_mode)
        self.actions = MODES[mode_index(self.min_mode):mode_index(self.max_mode) + 1]
        self.q, self.n, self.na = {}, {}, {}
        self.prev = None                 # (context, action)
        self.recent_attack = -1e9
        self.rng = random.Random(seed)
        self.memory_file = Path(memory_file) if memory_file else None
        self.updates = 0
        self.last_reward = None
        if self.memory_file and self.memory_file.exists():
            try:
                mem = json.loads(self.memory_file.read_text())
                self.q, self.n, self.na = mem.get("q", {}), mem.get("n", {}), mem.get("na", {})
            except ValueError:
                pass

    def context(self, f, now):
        recent = int(now - self.recent_attack < 30.0)
        return (f"i{f['integrity']}r{f['replay']}l{f['loss_level']}"
                f"b{f['feedback_attack']}d{f['deadman']}m{recent}")

    def loss(self, threat, action, changed):
        d = self.d
        return threat * d["leakage"][action] + d["w_cost"] * d["cost"][action] + d["w_switch"] * changed

    def decide(self, w, f, now):
        threat = threat_score(f)
        if threat >= 0.5:
            self.recent_attack = now
        # 1) learn from what happened in this window after the previous choice
        if self.prev is not None:
            ctx0, a0, changed = self.prev
            r = -self.loss(threat, a0, changed)
            q = self.q.setdefault(ctx0, {})
            na = self.na.setdefault(ctx0, {})
            na[a0] = na.get(a0, 0) + 1
            step = max(self.d["alpha"], 1.0 / na[a0])     # sample average, then a small floor
            q[a0] = q.get(a0, r) + step * (r - q.get(a0, r))
            self.n[ctx0] = self.n.get(ctx0, 0) + 1
            self.last_reward = r
            self.updates += 1
            if self.memory_file and self.updates % 10 == 0:
                self.save()
        # 2) choose the protection for the next window
        ctx = self.context(f, now)
        q = self.q.get(ctx, {})
        eps = self.d["epsilon"] / math.sqrt(1 + self.n.get(ctx, 0))
        untried = [a for a in self.actions if a not in q]
        if untried:
            # optimistic initial values: an untried action looks perfect (loss 0),
            # so every protection level is tried once in every new situation
            a = self.base if self.base in untried else untried[0]
            why = "try untested level"
        elif self.rng.random() < eps:
            a = self.rng.choice(self.actions)
            why = "explore"
        else:
            a = max(self.actions, key=lambda x: q[x])
            why = "learned best"
        dec = Decision(a, False, f"bandit {why} in {ctx}")
        dec = self.safety(w, f, now, dec)
        dec.mode = self._clamp(dec.mode)
        self.prev = (ctx, dec.mode, int(dec.mode != self.mode))
        self.mode = dec.mode
        return dec

    def save(self):
        self.memory_file.parent.mkdir(parents=True, exist_ok=True)
        self.memory_file.write_text(json.dumps({"q": self.q, "n": self.n, "na": self.na}, indent=1))

    def info(self):
        ctx = self.prev[0] if self.prev else None
        return {"context": ctx, "q": self.q.get(ctx, {}) if ctx else {},
                "contexts_known": len(self.q), "reward": self.last_reward}


def make_policy(name, cfg, base_mode, seed=None):
    if name == "fixed":
        return FixedPolicy(cfg, base_mode)
    if name == "threshold":
        return ThresholdPolicy(cfg, base_mode)
    if name == "bandit":
        return BanditPolicy(cfg, base_mode, cfg["defence"].get("memory_file"), seed)
    raise ValueError(f"unknown policy {name!r} (fixed | threshold | bandit)")


def now():
    return time.monotonic()
