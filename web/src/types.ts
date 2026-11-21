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
  on_success?: Record<string, any>;
  on_failure?: Record<string, any>;
}

export interface SceneNode {
  id: string;
  title: string;
  background?: string;
  music?: string;
  description: string;
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

export type MessageKind = 'narrator' | 'dialogue' | 'thought' | 'user' | 'system';

export interface StoryMessage {
  id: string;
  kind: MessageKind;
  speaker?: string;
  avatar?: string;
  content: string;
  timestamp: number;
}

export interface DiceCheckEvent {
  skill: string;
  difficulty: number;
  roll: number;
  total: number;
  isSuccess: boolean;
  message?: string;
}
