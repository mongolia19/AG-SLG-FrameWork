export interface PlayerAttributeMap {
  [key: string]: number;
}

export interface InventoryItem {
  id: string;
  name: string;
  desc?: string;
  icon?: string;
}

export interface OutfitItem {
  id: string;
  name: string;
  desc?: string;
  icon?: string;
  tag?: string;
}

export interface SkillItem {
  id: string;
  name: string;
  desc?: string;
  effect?: string;
  cost?: string;
  cooldown?: string;
  level?: number;
  tag?: string;
}

export interface HUDMetricItem {
  id: string;
  label: string;
  value?: number;
  max?: number;
  value_ref?: string;
  max_ref?: string;
  unit?: string;
  icon?: string;
  color?: 'amber' | 'sky' | 'emerald' | 'teal' | 'rose' | 'violet' | 'indigo' | string;
  low_threshold?: number;
  warn_outside?: [number, number];
}

export interface HUDTrackerStep {
  label: string;
  status?: 'done' | 'active' | 'locked';
  done_when?: Record<string, any>;
  active_when?: Record<string, any>;
}

export interface HUDBadge {
  text?: string;
  text_ref?: string;
  tone?: 'danger' | 'amber' | 'emerald' | 'sky' | 'purple' | 'slate' | string;
  when?: Record<string, any>;
}

export interface HUDBar {
  label: string;
  value?: number;
  max?: number;
  value_ref?: string;
  max_ref?: string;
  color?: 'rose' | 'violet' | 'sky' | 'amber' | 'emerald' | string;
}

export interface HUDCard {
  title: string;
  desc: string;
  tone?: string;
}

export interface HUDWidget {
  id: string;
  type: 'metrics' | 'tracker' | 'panel' | string;
  title?: string;
  subtitle?: string;
  icon?: string;
  tone?: 'danger' | 'amber' | 'sky' | 'purple' | 'emerald' | string;
  when?: Record<string, any>;
  items?: HUDMetricItem[];
  steps?: HUDTrackerStep[];
  badges?: HUDBadge[];
  bars?: HUDBar[];
  cards_title?: string;
  cards?: HUDCard[];
  footer?: string;
}

export interface PlayerState {
  name: string;
  hp: number;
  max_hp?: number;
  mp?: number | null;
  max_mp?: number | null;
  san: number;
  gold: number;
  attributes: PlayerAttributeMap;
  inventory: InventoryItem[];
  outfit?: Record<string, OutfitItem | null>;
  skills?: SkillItem[];
  hud_widgets?: HUDWidget[];
  variables: Record<string, any>;
  current_scene: string;
}

export interface NPC {
  id: string;
  name: string;
  avatar?: string;
  greeting?: string;
}

export interface ActionOption {
  id: string;
  label: string;
  type: 'interact' | 'check' | 'transition' | 'custom' | string;
  target_npc?: string;
  target_scene?: string;
  skill?: string;
  difficulty?: number;
  condition?: Record<string, any>;
  effects?: Record<string, any>;
  source?: string;
  on_success?: Record<string, any>;
  on_failure?: Record<string, any>;
}

export interface PropDecoration {
  id: string;
  name: string;
  image: string;
  side: 'left' | 'right';
  caption?: string;
  tooltip?: string;
  category?: 'env' | 'structure' | string;
  tag?: string;
  condition?: Record<string, any>;
}

export interface VisualLayer {
  background?: string;      // 场景底图 / 背景图 URL
  foreground?: string;      // 前景叠加物 / 遮罩 / 局部贴图
  hero_image?: string;      // 场景焦点主图（事件插画、关键证物特写等）
  atmosphere?: string;      // 场景氛围描述（雨夜、雾气、昏黄）
  decorations?: PropDecoration[]; // 舞台边缘氛围装饰道具
}

export interface SceneNode {
  id: string;
  title: string;
  background?: string;      // 背景图片 URL
  foreground?: string;      // 前景立绘/道具图
  hero_image?: string;      // 场景核心插画/焦点图
  music?: string;
  description: string;
  visuals?: VisualLayer;
  decorations?: PropDecoration[];
  npcs?: NPC[];
  actions?: ActionOption[];
}

export interface WorldSpec {
  id: string;
  title: string;
  version: string;
  author: string;
  icon?: string;
  sort_order?: number;
  initial_scene: string;
  opening_narration?: string;
  attribute_labels?: Record<string, string>;
  initial_player_state: PlayerState;
}

export interface ScenarioSpec {
  world: WorldSpec;
  scenes: Record<string, SceneNode>;
}

export type MessageKind = 'narrator' | 'dialogue' | 'thought' | 'user' | 'system' | 'visual_card';

export interface StoryMessage {
  id: string;
  kind: MessageKind;
  speaker?: string;
  avatar?: string;
  content: string;
  timestamp: number;
  hero_image?: string;      // 本回合触发的情境插图或关键线索图
  foreground?: string;      // 登场特写立绘
}


export interface DiceCheckEvent {
  skill: string;
  difficulty: number;
  roll: number;
  modifier?: number;
  total: number;
  isSuccess: boolean;
  outcome?: 'critical_success' | 'success' | 'partial_success' | 'failure' | string;
  outcome_label?: string;
  reason?: string;
  message?: string;
}

export interface LintIssue {
  level: 'error' | 'warning' | 'info';
  scene_id: string;
  message: string;
  field: string;
}

export interface LintReport {
  scenario_id: string;
  valid: boolean;
  total_issues: number;
  errors: number;
  warnings: number;
  issues: LintIssue[];
}

export interface SaveSlotSummary {
  id: string;
  name: string;
  scenario_id: string;
  scene_id: string;
  scene_title: string;
  player_name: string;
  hp: number;
  max_hp: number;
  saved_at: number;
}


