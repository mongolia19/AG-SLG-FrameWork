#!/usr/bin/env python3
"""Deterministic turn resolver for the science card tower scenario."""

import json
import random
import sys
from typing import Any, Dict, List


DEFAULT_DECK = [
    "实验", "实验", "实验", "校验", "校验", "实验", "归纳法", "批判思维"
]
CARD_COST = {
    "实验": 1,
    "校验": 1,
    "归纳法": 2,
    "批判思维": 1,
    "假设检验": 1,
    "控制变量": 1,
    "精密测量": 1,
    "双倍校验": 2,
    "反证法": 2,
    "证伪重击": 1,
    "严密公理": 1,
    "奥卡姆剃刀": 2,
}
CARD_DAMAGE = {
    "实验": 6,
    "校验": 0,
    "归纳法": 0,
    "批判思维": 0,
    "假设检验": 8,
    "控制变量": 0,
    "精密测量": 5,
    "双倍校验": 0,
    "反证法": 12,
    "证伪重击": 7,
    "严密公理": 0,
    "奥卡姆剃刀": 9,
}
ENCOUNTERS: Dict[str, Dict[str, Any]] = {
    "encounter_layer1": {
        "tower_stage": "layer1",
        "enemies": [
            {
                "id": "unknown",
                "name": "未知",
                "max_hp": 36,
                "armor": 0,
                "base_counter": 6,
                "thorns": 0,
                "effect": "experiment_penalty",
            },
            {
                "id": "ignorance",
                "name": "无知",
                "max_hp": 44,
                "armor": 3,
                "base_counter": 4,
                "thorns": 0,
                "effect": "shield_bonus",
            },
        ],
    },
    "encounter_layer2": {
        "tower_stage": "layer2",
        "enemies": [
            {
                "id": "blind_obedience",
                "name": "盲从",
                "max_hp": 60,
                "armor": 0,
                "base_counter": 5,
                "thorns": 0,
                "effect": "copy_induction",
            },
            {
                "id": "fallacy",
                "name": "谬证",
                "max_hp": 68,
                "armor": 0,
                "base_counter": 7,
                "thorns": 0,
                "effect": "steal_hand",
            },
        ],
    },
    "encounter_theology": {
        "tower_stage": "boss",
        "enemies": [
            {
                "id": "theology",
                "name": "神学",
                "max_hp": 96,
                "armor": 1,
                "base_counter": 9,
                "thorns": 3,
                "effect": "spiked_shell",
            },
        ],
    },
}


def _build_enemies_from_spec(encounter_id: str) -> List[Dict[str, Any]]:
    spec = ENCOUNTERS[encounter_id]
    result: List[Dict[str, Any]] = []
    for e in spec["enemies"]:
        result.append(
            {
                "id": e["id"],
                "name": e["name"],
                "hp": e["max_hp"],
                "max_hp": e["max_hp"],
                "armor": e["armor"],
                "base_counter": e["base_counter"],
                "thorns": e.get("thorns", 0),
                "effect": e.get("effect", ""),
            }
        )
    return result


def _default_state(encounter_id: str, picked_cards: List[str] | None = None) -> Dict[str, Any]:
    spec = ENCOUNTERS[encounter_id]
    enemies = _build_enemies_from_spec(encounter_id)
    deck = list(DEFAULT_DECK)
    if picked_cards:
        for card in picked_cards:
            if card in CARD_COST:
                deck.append(card)
    return {
        "hp": 72,
        "max_hp": 72,
        "shield": 0,
        "energy": 5,
        "deck": deck,
        "hand": [],
        "discard": [],
        "induction_bonus": 0,
        "experiment_penalty": 0,
        "shield_bonus_next": 0,
        "enemies": enemies,
        "current_encounter": encounter_id,
        "tower_stage": spec["tower_stage"],
        "turn_count": 0,
    }


def _normalize_state(raw: Dict[str, Any], encounter_id: str) -> Dict[str, Any]:
    state = _default_state(encounter_id)
    for key, value in raw.items():
        if key != "enemies":
            state[key] = value
    state["hand"] = list(state.get("hand") or [])
    state["deck"] = list(state.get("deck") or [])
    state["discard"] = list(state.get("discard") or [])
    state["turn_count"] = max(0, int(state.get("turn_count", 0)))

    raw_enemies = raw.get("enemies")
    if isinstance(raw_enemies, list) and raw_enemies:
        normalized: List[Dict[str, Any]] = []
        default_enemies = _build_enemies_from_spec(encounter_id)
        for idx, re_item in enumerate(raw_enemies):
            if not isinstance(re_item, dict):
                continue
            fallback = default_enemies[idx] if idx < len(default_enemies) else default_enemies[0]
            normalized.append(
                {
                    "id": str(re_item.get("id", fallback["id"])),
                    "name": str(re_item.get("name", fallback["name"])),
                    "hp": max(0, int(re_item.get("hp", fallback["max_hp"]))),
                    "max_hp": max(1, int(re_item.get("max_hp", fallback["max_hp"]))),
                    "armor": max(0, int(re_item.get("armor", fallback["armor"]))),
                    "base_counter": max(0, int(re_item.get("base_counter", fallback["base_counter"]))),
                    "thorns": max(0, int(re_item.get("thorns", fallback.get("thorns", 0)))),
                    "effect": str(re_item.get("effect", fallback.get("effect", ""))),
                }
            )
        if normalized:
            state["enemies"] = normalized

    return state


def _clamp_int(value: Any, minimum: int, maximum: int) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError):
        result = minimum
    return max(minimum, min(maximum, result))


def _deterministic_seed(state: Dict[str, Any], extra: int = 0) -> str:
    return "|".join(
        str(x)
        for x in (
            state.get("current_encounter", "tower"),
            state.get("turn_count", 0),
            len(state.get("deck", [])),
            len(state.get("hand", [])),
            extra,
        )
    )


def _shuffle_deck(state: Dict[str, Any], extra: int = 0) -> None:
    random.Random(_deterministic_seed(state, extra)).shuffle(state["deck"])


def _draw_cards(state: Dict[str, Any], count: int) -> List[str]:
    drawn: List[str] = []
    for _ in range(count):
        if not state["deck"]:
            state["deck"] = state["discard"][:]
            state["discard"] = []
            _shuffle_deck(state, len(drawn) + len(state["hand"]))
        if not state["deck"]:
            break
        card = state["deck"].pop()
        state["hand"].append(card)
        drawn.append(card)
    return drawn


def _draw_to_full(state: Dict[str, Any]) -> None:
    while len(state["hand"]) < 5:
        if not _draw_cards(state, 1):
            break


def _select_target(state: Dict[str, Any], target_arg: Any) -> Dict[str, Any] | None:
    enemies = state.get("enemies", [])
    alive = [e for e in enemies if e["hp"] > 0]
    if not alive:
        return None
    if target_arg is not None:
        try:
            idx = int(target_arg) - 1
            if 0 <= idx < len(enemies) and enemies[idx]["hp"] > 0:
                return enemies[idx]
        except (TypeError, ValueError):
            for e in alive:
                if e["name"] == str(target_arg) or e["id"] == str(target_arg):
                    return e
    return alive[0]


def _apply_player_damage(state: Dict[str, Any], amount: int) -> Dict[str, int]:
    shield = _clamp_int(state.get("shield", 0), 0, 999)
    absorbed = min(shield, amount)
    hp_lost = amount - absorbed
    state["shield"] = shield - absorbed
    state["hp"] = max(0, _clamp_int(state.get("hp", 0), 0, 999) - hp_lost)
    return {"absorbed": absorbed, "hp_lost": hp_lost}


def _play_card(state: Dict[str, Any], action: Dict[str, Any]) -> Dict[str, Any]:
    if not state["hand"]:
        return {"error": "手牌为空", "slot": action.get("slot")}
    slot = _clamp_int(action.get("slot", 0), 1, len(state["hand"]))
    if slot == 0:
        return {"error": "无效手牌槽位", "slot": action.get("slot")}
    card = state["hand"][slot - 1]
    cost = CARD_COST.get(card, 0)
    if cost > state["energy"]:
        return {"error": "能量不足", "card": card, "required": cost, "available": state["energy"]}
    state["energy"] -= cost
    state["hand"].pop(slot - 1)
    state["discard"].append(card)

    target = _select_target(state, action.get("target"))
    raw_damage = 0
    ignore_armor = False
    armor_shred = 0
    shield_gain = 0
    notes: List[str] = []

    if card == "实验":
        penalty = _clamp_int(state.get("experiment_penalty", 0), 0, 2)
        raw_damage = max(0, 6 + _clamp_int(state.get("induction_bonus", 0), 0, 12) - penalty)
        state["induction_bonus"] = 0
        if penalty:
            notes.append(f"实验伤害受削弱 -{penalty}")
        state["experiment_penalty"] = 0
    elif card == "校验":
        bonus = _clamp_int(state.get("shield_bonus_next", 0), 0, 6)
        shield_gain = 5 + bonus
        if bonus:
            notes.append(f"校验护盾额外 +{bonus}")
        state["shield_bonus_next"] = 0
    elif card == "归纳法":
        state["induction_bonus"] = min(12, _clamp_int(state.get("induction_bonus", 0), 0, 12) + 4)
        notes.append(f"下一次实验伤害 +{state['induction_bonus']}")
    elif card == "批判思维":
        keep_index = _clamp_int(action.get("keep_index", 0), 0, 2)
        drawn: List[str] = []
        for _ in range(3):
            if not state["deck"]:
                state["deck"] = state["discard"][:]
                state["discard"] = []
                _shuffle_deck(state, len(drawn) + len(state["hand"]))
            if state["deck"]:
                drawn.append(state["deck"].pop())
        if drawn:
            keep_idx = min(keep_index, len(drawn) - 1)
            keep = drawn.pop(keep_idx)
            state["hand"].append(keep)
            state["discard"].extend(drawn)
            notes.append(f"抽 3 留 1（保留【{keep}】），弃 {len(drawn)} 张")
        else:
            notes.append("牌堆与弃牌堆均为空")
    elif card == "假设检验":
        raw_damage = 8
        if state.get("experiment_penalty", 0):
            state["experiment_penalty"] = 0
            notes.append("清除实验削弱效果")
    elif card == "控制变量":
        shield_gain = 7
        state["shield_bonus_next"] = min(6, _clamp_int(state.get("shield_bonus_next", 0), 0, 6) + 2)
        notes.append("获得 7 护盾，下一次校验护盾 +2")
    elif card == "精密测量":
        raw_damage = 5
        ignore_armor = True
        notes.append("穿甲攻击：无视敌方护甲")
    elif card == "双倍校验":
        shield_gain = 10
        state["shield_bonus_next"] = min(6, _clamp_int(state.get("shield_bonus_next", 0), 0, 6) + 3)
        notes.append("获得 10 护盾，下一次校验护盾 +3")
    elif card == "反证法":
        raw_damage = 12
        armor_shred = 2
    elif card == "证伪重击":
        raw_damage = 7
        if target and target["armor"] > 0:
            raw_damage += 4
            notes.append("目标带有护甲，额外 +4 破甲伤害")
    elif card == "严密公理":
        shield_gain = 6
        extra = _draw_cards(state, 1)
        notes.append(f"获得 6 护盾" + (f"，抽到【{extra[0]}】" if extra else ""))
    elif card == "奥卡姆剃刀":
        raw_damage = 9
        extra = _draw_cards(state, 1)
        if extra:
            notes.append(f"额外抽到【{extra[0]}】")

    if shield_gain:
        state["shield"] = _clamp_int(state.get("shield", 0), 0, 999) + shield_gain
        if not any("护盾" in n for n in notes):
            notes.append(f"获得 {shield_gain} 点护盾")

    effective_damage = 0
    thorns_taken = 0
    target_name = target["name"] if target else ""
    if raw_damage > 0 and target is not None:
        armor = 0 if ignore_armor else _clamp_int(target.get("armor", 0), 0, 20)
        effective_damage = max(0, raw_damage - armor)
        target["hp"] = max(0, target["hp"] - effective_damage)
        notes.append(f"对【{target['name']}】造成 {effective_damage} 点伤害")
        if armor_shred and target["armor"] > 0:
            target["armor"] = max(0, target["armor"] - armor_shred)
            notes.append(f"【{target['name']}】护甲降低至 {target['armor']}")
        thorns = _clamp_int(target.get("thorns", 0), 0, 20)
        if thorns > 0:
            thorns_res = _apply_player_damage(state, thorns)
            thorns_taken = thorns
            notes.append(
                f"触发【{target['name']} · 尖刺外壳】反伤 {thorns} 点（护盾抵挡 {thorns_res['absorbed']}，生命 -{thorns_res['hp_lost']}）"
            )

    return {
        "card": card,
        "slot": slot,
        "cost": cost,
        "target": target_name,
        "damage": raw_damage,
        "effective_damage": effective_damage,
        "shield_gain": shield_gain,
        "thorns_taken": thorns_taken,
        "notes": notes,
    }


def _enemy_counters(state: Dict[str, Any]) -> Dict[str, Any]:
    alive_enemies = [e for e in state["enemies"] if e["hp"] > 0]
    if not alive_enemies:
        return {"total_counter": 0, "absorbed": 0, "hp_damage": 0, "notes": ["场上所有敌人已被击溃，本回合不再反击"]}

    total_raw = 0
    total_absorbed = 0
    total_hp_damage = 0
    notes: List[str] = []

    for enemy in alive_enemies:
        base = int(enemy.get("base_counter", 6))
        effect = enemy.get("effect", "")
        effect_note = ""

        if effect == "experiment_penalty":
            state["experiment_penalty"] = min(2, _clamp_int(state.get("experiment_penalty", 0), 0, 2) + 1)
            effect_note = "，并使下一次「实验」伤害 -1"
        elif effect == "shield_bonus":
            state["shield_bonus_next"] = min(6, _clamp_int(state.get("shield_bonus_next", 0), 0, 6) + 1)
            effect_note = "，但使你下一次「校验」护盾 +1"
        elif effect == "copy_induction":
            if _clamp_int(state.get("induction_bonus", 0), 0, 12) > 0:
                enemy["armor"] = _clamp_int(enemy.get("armor", 0), 0, 20) + 2
                state["induction_bonus"] = 0
                effect_note = f"，复制归纳增益使自身护甲增至 {enemy['armor']} 并清空你的归纳增益"
        elif effect == "steal_hand":
            if state["hand"]:
                lost = state["hand"].pop(0)
                state["discard"].append(lost)
                effect_note = f"，并移除了最左侧手牌【{lost}】"
        elif effect == "spiked_shell":
            effect_note = "（尖刺外壳持续生效）"

        res = _apply_player_damage(state, base)
        total_raw += base
        total_absorbed += res["absorbed"]
        total_hp_damage += res["hp_lost"]
        notes.append(
            f"【{enemy['name']}】反击 {base} 点（护盾抵挡 {res['absorbed']}，生命 -{res['hp_lost']}）{effect_note}"
        )

    return {
        "total_counter": total_raw,
        "absorbed": total_absorbed,
        "hp_damage": total_hp_damage,
        "notes": notes,
    }


def _build_state_delta(
    state: Dict[str, Any],
    play_log: List[Dict[str, Any]],
    counter_log: Dict[str, Any],
    hp_start: int,
) -> Dict[str, Any]:
    enemies = state["enemies"]
    alive_enemies = [e for e in enemies if e["hp"] > 0]
    e1 = enemies[0] if len(enemies) > 0 else {"name": "无", "hp": 0, "max_hp": 0, "armor": 0}
    e2 = enemies[1] if len(enemies) > 1 else {"name": "", "hp": 0, "max_hp": 0, "armor": 0}

    damage_dealt = sum(int(x.get("effective_damage", 0)) for x in play_log)
    hp_delta = state["hp"] - hp_start
    total_enemy_hp = sum(e["hp"] for e in enemies)
    total_enemy_max_hp = sum(e["max_hp"] for e in enemies)
    alive_names = " & ".join(e["name"] for e in alive_enemies) if alive_enemies else "已全灭"

    variables = {
        "tower_stage": state.get("tower_stage", "entry"),
        "current_encounter": state.get("current_encounter", "tower_entry"),
        "enemy_count": len(enemies),
        "enemy_name": alive_names,
        "enemy_hp": total_enemy_hp,
        "enemy_max_hp": total_enemy_max_hp,
        "enemy_armor": sum(e["armor"] for e in alive_enemies),
        "enemy_alive": len(alive_enemies) > 0,
        "enemy1_name": e1["name"],
        "enemy1_hp": e1["hp"],
        "enemy1_max_hp": e1["max_hp"],
        "enemy1_armor": e1["armor"],
        "enemy2_name": e2["name"],
        "enemy2_hp": e2["hp"],
        "enemy2_max_hp": e2["max_hp"],
        "enemy2_armor": e2["armor"],
        "turn_count": state["turn_count"],
        "deck_count": len(state["deck"]),
        "hand_count": len(state["hand"]),
        "discard_count": len(state["discard"]),
        "energy": state["energy"],
        "shield": state["shield"],
        "induction_bonus": state["induction_bonus"],
        "experiment_penalty": state.get("experiment_penalty", 0),
        "shield_bonus_next": state.get("shield_bonus_next", 0),
        "hand_card_1": state["hand"][0] if len(state["hand"]) > 0 else "空",
        "hand_card_2": state["hand"][1] if len(state["hand"]) > 1 else "空",
        "hand_card_3": state["hand"][2] if len(state["hand"]) > 2 else "空",
        "hand_card_4": state["hand"][3] if len(state["hand"]) > 3 else "空",
        "hand_card_5": state["hand"][4] if len(state["hand"]) > 4 else "空",
    }

    available_actions = []
    if alive_enemies and state["hp"] > 0:
        for index, card in enumerate(state["hand"], start=1):
            cost = CARD_COST.get(card, 0)
            base_dmg = CARD_DAMAGE.get(card, 0)
            if card == "实验":
                dmg_display = max(
                    0,
                    base_dmg
                    + _clamp_int(state.get("induction_bonus", 0), 0, 12)
                    - _clamp_int(state.get("experiment_penalty", 0), 0, 2),
                )
            else:
                dmg_display = base_dmg

            if dmg_display > 0 and len(alive_enemies) > 1:
                for target_idx, enemy in enumerate(enemies, start=1):
                    if enemy["hp"] <= 0:
                        continue
                    eff_preview = dmg_display
                    if card == "证伪重击" and enemy["armor"] > 0:
                        eff_preview += 4
                    available_actions.append(
                        {
                            "id": f"play_slot_{index}_target_{target_idx}",
                            "label": f"打出第 {index} 张：{card} → {enemy['name']}（攻击{eff_preview} · 耗能{cost}）",
                            "type": "interact",
                        }
                    )
            else:
                available_actions.append(
                    {
                        "id": f"play_slot_{index}",
                        "label": f"打出第 {index} 张手牌：{card}（攻击{dmg_display} · 耗能{cost}）",
                        "type": "interact",
                    }
                )

    state_delta = {
        "hp_delta": hp_delta,
        "variables": variables,
        "visuals": {
            "foreground": "",
            "hero_image": "",
        },
        "available_actions": available_actions,
    }

    narration_lines = []
    for play in play_log:
        card = play.get("card", "")
        notes = play.get("notes", [])
        detail = "，".join(notes) if notes else "完成结算"
        narration_lines.append(f"打出【{card}】：{detail}")
    for note in counter_log.get("notes") or []:
        narration_lines.append(f"敌方行动：{note}")
    if damage_dealt:
        narration_lines.append(f"本回合总输出：{damage_dealt}")
    if not alive_enemies:
        narration_lines.append("当前层敌人已全部击溃，进入战后奖励阶段！")

    return {
        "state": state,
        "state_delta": state_delta,
        "narration": "\n".join(narration_lines),
        "play_log": play_log,
        "counter_log": counter_log,
    }


def init_state(data: Dict[str, Any]) -> Dict[str, Any]:
    encounter_id = data.get("encounter", "encounter_layer1")
    if encounter_id not in ENCOUNTERS:
        raise ValueError(f"未知遭遇：{encounter_id}")
    picked_cards = list(data.get("picked_cards") or [])
    state = _default_state(encounter_id, picked_cards=picked_cards)
    if isinstance(data.get("hp"), int):
        state["hp"] = max(1, min(72, data["hp"]))
    _shuffle_deck(state, len(picked_cards))
    _draw_to_full(state)
    return _build_state_delta(state, [], {"notes": [], "total_counter": 0, "hp_damage": 0}, state["hp"])


def resolve_turn(data: Dict[str, Any]) -> Dict[str, Any]:
    encounter_id = data.get("encounter") or data.get("current_encounter")
    if encounter_id not in ENCOUNTERS:
        raise ValueError(f"未知遭遇：{encounter_id}")
    state = _normalize_state(data.get("state", {}), encounter_id)
    hp_start = state["hp"]
    state["energy"] = 5
    state["turn_count"] = _clamp_int(state.get("turn_count", 0), 0, 99) + 1
    _draw_to_full(state)

    play_log: List[Dict[str, Any]] = []
    for action in data.get("plays", []):
        if isinstance(action, int):
            action = {"slot": action}
        if not any(e["hp"] > 0 for e in state["enemies"]) or state["hp"] <= 0:
            break
        result = _play_card(state, action)
        if "error" in result:
            return {"error": result["error"], "state": state, "play_log": play_log}
        play_log.append(result)

    if state["hp"] > 0:
        counter_log = _enemy_counters(state)
    else:
        counter_log = {"total_counter": 0, "absorbed": 0, "hp_damage": 0, "notes": ["物理学家生命归零"]}
    return _build_state_delta(state, play_log, counter_log, hp_start)


def main() -> int:
    raw = sys.argv[2] if len(sys.argv) >= 3 and sys.argv[1] == "--json" else sys.stdin.read()
    if not raw.strip():
        print(json.dumps({"error": "Pass JSON via --json '{...}' or stdin"}, ensure_ascii=False))
        return 1
    data = json.loads(raw)
    mode = data.get("mode", "turn")
    if mode == "init":
        result = init_state(data)
    elif mode in ("turn", "resolve", "new_round"):
        result = resolve_turn(data)
    else:
        result = {"error": f"Unknown mode: {mode}"}
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
