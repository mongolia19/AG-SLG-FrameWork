---
name: wow-elwynn-rpg-dm-skill
description: 艾泽拉斯传说：法戈第矿洞之影 剧本专属 DM 计算与裁决 Skill，用于精确执行技能伤害、敌方承伤与蜘蛛领主三阶段流转。
---

# 艾泽拉斯 RPG DM 推演 Skill

在需要严格四阶判定、Boss 三阶段转换或同伴艾莲娜协同结算的战斗回合中，优先调用 `scripts/wow_elwynn_rpg/scripts/combat_calc.py` 计算精确数值，再将结果写入叙事与 `state_delta`：

- **计算主角或艾莲娜技能伤害**：
  ```bash
  python scripts/wow_elwynn_rpg/scripts/combat_calc.py --json '{"mode":"skill","base_power":28,"attr_value":16,"level":3,"roll":15,"dc":12,"armor_hardened":false,"mark_active":true}'
  ```
  - 随行同伴艾莲娜传 `"is_ally": true`（按 `base + attr*2.0 + level*8` 计算）。
- **计算敌方反击承伤**：
  ```bash
  python scripts/wow_elwynn_rpg/scripts/combat_calc.py --json '{"mode":"enemy","base_damage":34,"enemy_roll":14,"enemy_atk_bonus":5,"evade_dc":13,"armor_dr":4,"antidote_active":true,"is_poison":true,"minions":2}'
  ```
- **判定蜘蛛领主阶段流转与枯竭回蓝**：
  ```bash
  python scripts/wow_elwynn_rpg/scripts/combat_calc.py --json '{"mode":"boss","boss_hp":220,"boss_mp":110,"boss_phase":1}'
  ```
