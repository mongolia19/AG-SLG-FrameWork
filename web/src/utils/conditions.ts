import { PlayerState } from '../types';

export function compareConditionValue(actual: any, expected: any): boolean {
  if (expected && typeof expected === 'object' && !Array.isArray(expected)) {
    const numActual = typeof actual === 'number' ? actual : 0;
    if ('lt' in expected && !(numActual < expected.lt)) return false;
    if ('lte' in expected && !(numActual <= expected.lte)) return false;
    if ('gt' in expected && !(numActual > expected.gt)) return false;
    if ('gte' in expected && !(numActual >= expected.gte)) return false;
    if ('ne' in expected && !(actual !== expected.ne)) return false;
    if ('in' in expected && !expected.in.includes(actual)) return false;
    if ('not_in' in expected && expected.not_in.includes(actual)) return false;
    return true;
  }
  return actual === expected;
}

export function evaluateActionCondition(
  condition: Record<string, any> | undefined,
  state: PlayerState | null
): boolean {
  if (!condition || !state) return true;
  const invIds = new Set((state.inventory || []).map((item) => item.id));

  if ('has_item' in condition) {
    const reqs = Array.isArray(condition.has_item) ? condition.has_item : [condition.has_item];
    if (!reqs.every((id: string) => invIds.has(id))) return false;
  }
  if ('has_any_item' in condition) {
    const anyReqs: string[] = condition.has_any_item || [];
    if (!anyReqs.some((id: string) => invIds.has(id))) return false;
  }
  if ('not_has_item' in condition) {
    const forbs = Array.isArray(condition.not_has_item)
      ? condition.not_has_item
      : [condition.not_has_item];
    if (forbs.some((id: string) => invIds.has(id))) return false;
  }

  const outfitMap = state.outfit || {};
  const equippedIds = new Set<string>();
  const equippedSlots = new Set<string>();
  for (const [slot, piece] of Object.entries(outfitMap)) {
    if (piece && typeof piece === 'object' && (piece.id || piece.name)) {
      equippedSlots.add(slot);
      if (piece.id) equippedIds.add(String(piece.id));
    }
  }
  if ('has_outfit' in condition) {
    const reqs = Array.isArray(condition.has_outfit) ? condition.has_outfit : [condition.has_outfit];
    if (!reqs.every((id: string) => equippedIds.has(id))) return false;
  }
  if ('not_has_outfit' in condition) {
    const forbs = Array.isArray(condition.not_has_outfit)
      ? condition.not_has_outfit
      : [condition.not_has_outfit];
    if (forbs.some((id: string) => equippedIds.has(id))) return false;
  }
  if ('has_outfit_slot' in condition) {
    const reqs = Array.isArray(condition.has_outfit_slot)
      ? condition.has_outfit_slot
      : [condition.has_outfit_slot];
    if (!reqs.every((s: string) => equippedSlots.has(s))) return false;
  }
  if ('not_has_outfit_slot' in condition) {
    const forbs = Array.isArray(condition.not_has_outfit_slot)
      ? condition.not_has_outfit_slot
      : [condition.not_has_outfit_slot];
    if (forbs.some((s: string) => equippedSlots.has(s))) return false;
  }

  const skillKeys = new Set<string>();
  for (const sk of state.skills || []) {
    if (sk?.id) skillKeys.add(String(sk.id));
    if (sk?.name) skillKeys.add(String(sk.name));
  }
  if ('has_skill' in condition) {
    const reqs = Array.isArray(condition.has_skill) ? condition.has_skill : [condition.has_skill];
    if (!reqs.every((id: string) => skillKeys.has(id))) return false;
  }
  if ('not_has_skill' in condition) {
    const forbs = Array.isArray(condition.not_has_skill)
      ? condition.not_has_skill
      : [condition.not_has_skill];
    if (forbs.some((id: string) => skillKeys.has(id))) return false;
  }

  if (condition.variables && typeof condition.variables === 'object') {
    for (const [k, expected] of Object.entries(condition.variables)) {
      if (!compareConditionValue(state.variables?.[k], expected)) return false;
    }
  }
  if (condition.attributes && typeof condition.attributes === 'object') {
    for (const [k, expected] of Object.entries(condition.attributes)) {
      if (!compareConditionValue(state.attributes?.[k], expected)) return false;
    }
  }

  const timeSlot = state.variables?.time_slot;
  if ('time_slot_in' in condition && !condition.time_slot_in.includes(timeSlot)) {
    return false;
  }
  if ('time_slot_not_in' in condition && condition.time_slot_not_in.includes(timeSlot)) {
    return false;
  }

  const matchWeatherTargets = (targets: string[]): boolean => {
    const wStr = String(state.variables?.weather || '').trim();
    const wType = String(state.variables?.weather_type || '').trim().toLowerCase();
    if (!wStr && !wType) return false;
    const aliasMap: Record<string, string[]> = {
      晴天: ['clear'],
      晴朗: ['clear'],
      clear: ['clear'],
      阴天: ['cloudy'],
      多云: ['cloudy'],
      cloudy: ['cloudy'],
      overcast: ['cloudy'],
      刮风: ['windy', 'storm'],
      大风: ['windy', 'storm'],
      狂风: ['windy', 'storm'],
      windy: ['windy', 'storm'],
      wind: ['windy', 'storm'],
      雨天: ['rain', 'storm'],
      下雨: ['rain', 'storm'],
      小雨: ['rain'],
      阵雨: ['rain'],
      rain: ['rain', 'storm'],
      暴雨: ['storm'],
      雷暴: ['storm'],
      storm: ['storm'],
      海雾: ['foggy'],
      雾天: ['foggy'],
      foggy: ['foggy'],
      fog: ['foggy'],
    };
    return targets.some((raw) => {
      const t = String(raw).trim();
      if (!t) return false;
      if (t === wStr || t.toLowerCase() === wType) return true;
      if (wStr.includes(t)) return true;
      const mapped = aliasMap[t.toLowerCase()] || aliasMap[t];
      return Boolean(mapped && mapped.includes(wType));
    });
  };

  if ('weather_in' in condition) {
    const list = Array.isArray(condition.weather_in) ? condition.weather_in : [condition.weather_in];
    if (!matchWeatherTargets(list)) return false;
  }
  if ('weather_not_in' in condition) {
    const list = Array.isArray(condition.weather_not_in)
      ? condition.weather_not_in
      : [condition.weather_not_in];
    if (matchWeatherTargets(list)) return false;
  }
  if ('min_day' in condition) {
    const day = Number(state.variables?.day ?? 1);
    if (day < Number(condition.min_day)) return false;
  }
  if ('min_hp' in condition) {
    if (Number(state.hp ?? 0) < Number(condition.min_hp)) return false;
  }
  if ('hp_lte' in condition) {
    if (Number(state.hp ?? 0) > Number(condition.hp_lte)) return false;
  }
  if ('min_mp' in condition) {
    const currMp = Number(state.mp ?? state.variables?.mp ?? 0);
    if (currMp < Number(condition.min_mp)) return false;
  }
  if ('max_mp' in condition) {
    const currMp = Number(state.mp ?? state.variables?.mp ?? 0);
    if (currMp > Number(condition.max_mp)) return false;
  }
  if ('min_gold' in condition) {
    if (Number(state.gold ?? 0) < Number(condition.min_gold)) return false;
  }
  return true;
}

export function resolveStateRef(ref: string | undefined, state: PlayerState | null): any {
  if (!ref || !state) return undefined;
  const parts = ref.split('.');
  let cur: any = state;
  for (const p of parts) {
    if (cur == null || typeof cur !== 'object') return undefined;
    cur = cur[p];
  }
  return cur;
}

export function interpolateStateText(template: string | undefined, state: PlayerState | null): string {
  if (!template) return '';
  return template.replace(/\{([a-zA-Z0-9_.]+)\}/g, (_, path) => {
    const val = resolveStateRef(path, state);
    return val !== undefined && val !== null ? String(val) : '';
  });
}
