#!/usr/bin/env python3
"""Deterministic combat damage, mitigation & Boss phase calculator for wow_elwynn_rpg."""

import json
import math
import sys
from typing import Any, Dict


def outcome_tier(roll: int, total: int, dc: int) -> tuple[str, float]:
    if roll == 20 or total >= dc + 5:
        return "critical_success", 1.35
    if total >= dc:
        return "success", 1.0
    if total >= dc - 3:
        return "partial_success", 0.65
    return "failure", 0.25 if roll > 1 else 0.0


def calc_skill_damage(
    base_power: float,
    attr_value: int,
    level: int,
    roll: int,
    dc: int,
    *,
    is_ally: bool = False,
    armor_hardened: bool = False,
    mark_active: bool = False,
    bonus_mod: int = 0,
) -> Dict[str, Any]:
    attr_mod = math.floor((attr_value - 10) / 2)
    total = roll + attr_mod + bonus_mod + (2 if mark_active else 0)
    tier, tier_mult = outcome_tier(roll, total, dc)
    armor_mult = 0.55 if armor_hardened else 1.0
    mark_mult = 1.15 if mark_active else 1.0
    attr_scale = 2.0 if is_ally else 2.5
    lvl_scale = 8 if is_ally else 10
    raw = (base_power + attr_value * attr_scale + level * lvl_scale) * armor_mult * mark_mult * tier_mult
    damage = math.ceil(raw) if raw > 0 else 0
    return {
        "roll": roll,
        "attr_mod": attr_mod,
        "total": total,
        "dc": dc,
        "outcome": tier,
        "tier_mult": tier_mult,
        "damage": damage,
    }


def calc_enemy_damage(
    base_damage: float,
    enemy_roll: int,
    enemy_atk_bonus: int,
    evade_dc: int,
    *,
    armor_dr: int = 0,
    antidote_active: bool = False,
    is_poison: bool = False,
    minions: int = 0,
    web_trapped: bool = False,
    player_crit_halved: bool = False,
) -> Dict[str, Any]:
    total = enemy_roll + enemy_atk_bonus
    if enemy_roll == 1 or total < evade_dc - 3:
        return {"hit": False, "outcome": "evaded", "total": total, "damage": 0}
    if enemy_roll == 20 or total >= evade_dc + 5:
        hit_mult, outcome = 1.3, "crit_hit"
    elif total >= evade_dc:
        hit_mult, outcome = 1.0, "hit"
    else:
        hit_mult, outcome = 0.5, "graze"

    scaled = math.ceil(base_damage * hit_mult)
    if player_crit_halved:
        scaled = math.ceil(scaled * 0.5)
    anti_dr = 6 if (is_poison and antidote_active) else 0
    minion_poison = max(0, minions) * 4
    web_bonus = 5 if web_trapped else 0
    final_dmg = max(1, scaled - armor_dr - anti_dr + minion_poison + web_bonus)
    return {"hit": True, "outcome": outcome, "total": total, "damage": final_dmg}


def evaluate_boss_state(boss_hp: int, boss_mp: int, boss_phase: int) -> Dict[str, Any]:
    if boss_hp <= 0:
        return {"boss_hp": 0, "boss_mp": 0, "boss_phase": boss_phase, "boss_defeated": True, "next_action": "击败结算"}
    new_phase = boss_phase
    armor_broken = True
    spawned_minions = 0
    if boss_hp <= 130 and boss_phase < 3:
        new_phase = 3
        boss_mp = max(0, boss_mp - 45)
        armor_broken = False
        next_action = "【阶段三 · 深渊狂暴】重铸甲壳 & 暗影毒液狂潮"
    elif boss_hp <= 240 and boss_phase < 2:
        new_phase = 2
        if boss_mp >= 35:
            boss_mp -= 35
            spawned_minions = 2
        next_action = "【阶段二 · 毒潮孵化】召唤毒囊幼蛛 & 剧毒新星"
    elif boss_mp < 30:
        boss_mp = min(180, boss_mp + 35)
        next_action = "魔力枯竭 · 螯肢普攻 (+35 MP 蓄力)"
    else:
        next_action = "正常技能循环"
    return {
        "boss_hp": boss_hp,
        "boss_mp": boss_mp,
        "boss_phase": new_phase,
        "armor_broken": armor_broken,
        "spawned_minions": spawned_minions,
        "boss_defeated": False,
        "next_action": next_action,
    }


def main() -> int:
    raw = sys.argv[2] if len(sys.argv) >= 3 and sys.argv[1] == "--json" else sys.stdin.read()
    if not raw.strip():
        print(json.dumps({"error": "Pass JSON via --json '{...}' or stdin"}, ensure_ascii=False))
        return 1
    data = json.loads(raw)
    mode = data.get("mode", "skill")
    if mode == "skill":
        res = calc_skill_damage(
            base_power=float(data["base_power"]),
            attr_value=int(data["attr_value"]),
            level=int(data.get("level", 1)),
            roll=int(data["roll"]),
            dc=int(data["dc"]),
            is_ally=bool(data.get("is_ally", False)),
            armor_hardened=bool(data.get("armor_hardened", False)),
            mark_active=bool(data.get("mark_active", False)),
            bonus_mod=int(data.get("bonus_mod", 0)),
        )
    elif mode == "enemy":
        res = calc_enemy_damage(
            base_damage=float(data["base_damage"]),
            enemy_roll=int(data["enemy_roll"]),
            enemy_atk_bonus=int(data.get("enemy_atk_bonus", 0)),
            evade_dc=int(data.get("evade_dc", 10)),
            armor_dr=int(data.get("armor_dr", 0)),
            antidote_active=bool(data.get("antidote_active", False)),
            is_poison=bool(data.get("is_poison", False)),
            minions=int(data.get("minions", 0)),
            web_trapped=bool(data.get("web_trapped", False)),
            player_crit_halved=bool(data.get("player_crit_halved", False)),
        )
    elif mode == "boss":
        res = evaluate_boss_state(
            boss_hp=int(data["boss_hp"]),
            boss_mp=int(data["boss_mp"]),
            boss_phase=int(data.get("boss_phase", 1)),
        )
    else:
        res = {"error": f"Unknown mode: {mode}"}
    print(json.dumps(res, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
