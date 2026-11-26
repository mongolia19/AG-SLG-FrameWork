---
name: science-tower-cards-dm-skill
description: 实验之塔 · 自然科学卡牌试炼的确定性推演 Skill，用于精确结算多敌遭遇、四选二掉落卡、尖刺外壳反伤、能量、抽牌、护盾与敌方反击。
---

# 实验之塔 · 卡牌推演 Skill

所有卡牌回合都必须先运行 `scripts/science_tower_cards/scripts/card_engine.py`，再把返回的
`state_delta` 原样写入叙事末尾。不要凭记忆调整 HP、能量、牌堆、手牌、护甲或敌方血量。

## 快速初始化

```bash
python3 scripts/science_tower_cards/scripts/card_engine.py --json '{"mode":"init","encounter":"encounter_layer1"}'
```

可替换遭遇：
- `encounter_layer1`（第一层：未知 + 无知同时出场）
- `encounter_layer2`（第二层：盲从 + 谬证同时出场）
- `encounter_theology`（最终 Boss：神学，带有尖刺外壳：每次被攻击反伤 3 点）

进入第二层或 Boss 战时，可通过 `picked_cards` 把玩家战后四选二获得的卡牌带入新卡组，例如：

```bash
python3 scripts/science_tower_cards/scripts/card_engine.py --json '{"mode":"init","encounter":"encounter_layer2","hp":64,"picked_cards":["假设检验","精密测量"]}'
```

## 回合结算

`state` 从上一次脚本结果复制。`plays` 支持 1 基手牌槽位数组，也可通过 `{"slot": 1, "target": 2}` 指定攻击第 2 个敌人：

```bash
python3 scripts/science_tower_cards/scripts/card_engine.py --json '{"mode":"turn","encounter":"encounter_layer1","state":{...},"plays":[{"slot":3,"target":1},{"slot":4}]}'
```

脚本会自动：
1. 重置能量为 5 并补抽至 5 张手牌；
2. 按顺序结算每张出牌（含 8 张掉落新卡效果及「神学」的尖刺外壳反伤 3 点）；
3. 让场上仍存活的敌人依次执行确定性反击；
4. 返回下一回合可选的 `available_actions`（双敌存活时会自动展开目标选项）。

## 结算纪律

- 只把脚本输出的 `state_delta` 应用到游戏状态；
- 当遭遇中所有敌人生命归零（`enemy_alive: false`）后，进入战后「四选二」选牌或步入下一层；
- 若脚本返回错误，应向玩家解释原因并停止本回合，不要强行结算；
- 每次换场景必须把 `visuals.foreground` 清空为 `""`。
