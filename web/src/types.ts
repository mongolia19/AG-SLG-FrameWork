export interface PlayerAttributeMap {
  [key: string]: number;
}

export interface InventoryItem {
  id: string;
  name: string;
  desc?: string;
  icon?: string;
}

export interface PlayerState {
  name: string;
  hp: number;
  san: number;
  gold: number;
  attributes: PlayerAttributeMap;
  inventory: InventoryItem[];
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
}

export interface VisualLayer {
  background?: string;      // 场景底图 / 背景图 URL
  foreground?: string;      // 前景叠加物 / 遮罩 / 局部贴图
  hero_image?: string;      // 场景焦点主图（事件插画、关键证物特写等）
  atmosphere?: string;      // 场景氛围描述（雨夜、雾气、昏黄）
  decorations?: PropDecoration[]; // 舞台边缘氛围装饰道具 (贝壳、螃蟹、椰树、藤蔓、石头等)
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
  initial_scene: string;
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
  total: number;
  isSuccess: boolean;
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


