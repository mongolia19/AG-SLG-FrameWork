import { useState, useEffect } from 'react';
import { ScenarioSpec, SceneNode } from '../../types';
import { Network, CheckCircle2, MapPin, Sparkles } from 'lucide-react';

interface ScenarioTreeProps {
  scenario: ScenarioSpec;
  selectedSceneId: string;
  onSelectScene: (sceneId: string) => void;
  onSaveScene: (scene: SceneNode) => void;
  onRefresh: () => void;
}

export default function ScenarioTree({
  scenario,
  selectedSceneId,
  onSelectScene,
  onSaveScene,
  onRefresh,
}: ScenarioTreeProps) {
  const selectedScene = scenario.scenes[selectedSceneId] || scenario.scenes[scenario.world.initial_scene];

  const [editTitle, setEditTitle] = useState(selectedScene?.title || '');
  const [editDesc, setEditDesc] = useState(selectedScene?.description || '');
  const [editBg, setEditBg] = useState(selectedScene?.background || '');
  const [editHero, setEditHero] = useState(selectedScene?.hero_image || '');

  useEffect(() => {
    setEditTitle(selectedScene?.title || '');
    setEditDesc(selectedScene?.description || '');
    setEditBg(selectedScene?.background || '');
    setEditHero(selectedScene?.hero_image || '');
  }, [selectedScene?.id, selectedScene?.title, selectedScene?.description, selectedScene?.background, selectedScene?.hero_image]);

  // 场景列表
  const sceneList = Object.values(scenario.scenes);

  const handleSave = () => {
    if (!selectedScene) return;
    const updated: SceneNode = {
      ...selectedScene,
      title: editTitle,
      description: editDesc,
      background: editBg,
      hero_image: editHero,
    };
    onSaveScene(updated);
  };

  return (
    <div className="flex-1 flex h-full overflow-hidden bg-slate-950">
      {/* 左侧：场景树导航列表 */}
      <div className="w-72 bg-[#12151d] border-r border-slate-800 flex flex-col h-full">
        <div className="p-3.5 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Network className="w-4 h-4 text-indigo-400" />
            <span className="text-xs font-bold text-slate-200 tracking-wide uppercase">
              场景节点流向树
            </span>
          </div>
          <button
            onClick={onRefresh}
            className="text-[11px] text-slate-400 hover:text-slate-200 px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-700 transition"
          >
            刷新
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-2.5 space-y-1.5">
          {sceneList.map((sc) => {
            const isSelected = sc.id === selectedSceneId;
            const isInitial = sc.id === scenario.world.initial_scene;

            return (
              <div
                key={sc.id}
                onClick={() => {
                  onSelectScene(sc.id);
                  setEditTitle(sc.title);
                  setEditDesc(sc.description);
                  setEditBg(sc.background || '');
                  setEditHero(sc.hero_image || '');
                }}
                className={`p-3 rounded-lg cursor-pointer transition border ${
                  isSelected
                    ? 'bg-indigo-950/50 border-indigo-500/70 text-indigo-200 shadow'
                    : 'bg-slate-900/60 border-slate-800/80 hover:bg-slate-850 text-slate-300'
                }`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 font-medium text-xs">
                    <MapPin className={`w-3.5 h-3.5 ${isSelected ? 'text-indigo-400' : 'text-slate-500'}`} />
                    <span>{sc.title}</span>
                  </div>
                  {isInitial && (
                    <span className="text-[10px] font-mono uppercase bg-amber-500/20 text-amber-300 px-1.5 py-0.2 rounded border border-amber-500/30">
                      初始
                    </span>
                  )}
                </div>

                <div className="mt-1.5 flex items-center gap-3 text-[11px] text-slate-500">
                  <span>动作: {sc.actions?.length || 0}</span>
                  <span>人物: {sc.npcs?.length || 0}</span>
                  {sc.hero_image && <span className="text-amber-500/80">★焦点图</span>}
                </div>
              </div>
            );
          })}
        </div>

        {/* 世界初始设定简报 */}
        <div className="p-3 border-t border-slate-800 bg-[#0e1017] text-xs text-slate-400 space-y-1">
          <div className="text-[10px] uppercase font-mono tracking-wider text-slate-500">世界规则配置</div>
          <div className="text-slate-300 font-semibold text-xs">{scenario.world.title} (v{scenario.world.version})</div>
          <div className="text-[11px] text-slate-400">
            初始角色: {scenario.world.initial_player_state.name} (HP: {scenario.world.initial_player_state.hp} SAN: {scenario.world.initial_player_state.san})
          </div>
        </div>
      </div>

      {/* 右侧：单场景详情与视觉组织编辑 */}
      <div className="flex-1 flex flex-col h-full overflow-y-auto p-6 bg-slate-950">
        {selectedScene ? (
          <div className="max-w-3xl w-full mx-auto space-y-5">
            <div className="flex items-center justify-between border-b border-slate-800 pb-4">
              <div>
                <h2 className="text-lg font-bold text-slate-100 flex items-center gap-2">
                  <span>{selectedScene.title}</span>
                  <span className="text-xs font-mono text-slate-500 font-normal">({selectedScene.id}.yaml)</span>
                </h2>
                <p className="text-xs text-slate-400 mt-1">
                  管理本场景的故事流程、分支跳转、NPC 登场立绘与背景/焦点主图。
                </p>
              </div>

              <button
                onClick={handleSave}
                className="flex items-center gap-1.5 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-semibold shadow transition"
              >
                <CheckCircle2 className="w-4 h-4" />
                <span>保存场景修改</span>
              </button>
            </div>

            {/* 视觉图层配置 (Visual Layers) */}
            <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-4 space-y-3">
              <div className="text-xs font-semibold text-amber-400 uppercase tracking-wider flex items-center gap-1.5">
                <Sparkles className="w-3.5 h-3.5" />
                <span>视觉资产与图层组织 (Visual Assets)</span>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-[11px] text-slate-400 mb-1 font-medium">
                    背景底图 URL / 描述标签 (Background)
                  </label>
                  <input
                    type="text"
                    value={editBg}
                    onChange={(e) => setEditBg(e.target.value)}
                    placeholder="/assets/scenes/entrance.png 或 外部图床"
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-indigo-500"
                  />
                </div>

                <div>
                  <label className="block text-[11px] text-slate-400 mb-1 font-medium">
                    场景核心焦点图 / 关键证物插画 (Hero Image)
                  </label>
                  <input
                    type="text"
                    value={editHero}
                    onChange={(e) => setEditHero(e.target.value)}
                    placeholder="/assets/illustrations/clue_letter.png 或 描述标签"
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-indigo-500"
                  />
                </div>
              </div>

              {(selectedScene.visuals?.decorations || selectedScene.decorations || []).length > 0 && (
                <div className="pt-2 border-t border-slate-800/80">
                  <div className="text-[11px] text-slate-400 mb-2 font-medium">
                    左右两侧图像区物件 (环境道具 & 条件建造设施)
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    {(selectedScene.visuals?.decorations || selectedScene.decorations || []).map((dec, idx) => (
                      <div
                        key={dec.id || idx}
                        className="flex items-center gap-2.5 p-2 rounded-lg bg-slate-950/80 border border-slate-800 text-xs"
                      >
                        <img
                          src={dec.image}
                          alt={dec.name}
                          className="w-9 h-9 rounded object-cover border border-slate-800 shrink-0"
                        />
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-1.5">
                            <span className="text-slate-200 font-medium truncate">{dec.name}</span>
                            <span
                              className={`text-[9px] font-mono px-1 rounded border shrink-0 ${
                                dec.category === 'structure'
                                  ? 'text-emerald-300 bg-emerald-950/60 border-emerald-700/40'
                                  : 'text-amber-300 bg-amber-950/50 border-amber-800/40'
                              }`}
                            >
                              {dec.side === 'left' ? '左栏' : '右栏'} · {dec.tag || (dec.category === 'structure' ? '设施' : '环境')}
                            </span>
                          </div>
                          {dec.condition && (
                            <div className="text-[10px] text-slate-500 font-mono truncate mt-0.5">
                              显示条件: {JSON.stringify(dec.condition)}
                            </div>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* 场景环境描述 */}
            <div className="space-y-1.5">
              <label className="block text-xs font-semibold text-slate-300">场景环境叙事描述 (Description)</label>
              <textarea
                rows={4}
                value={editDesc}
                onChange={(e) => setEditDesc(e.target.value)}
                className="w-full bg-slate-900/90 border border-slate-800 rounded-xl p-3 text-xs sm:text-sm text-slate-100 font-serif leading-relaxed focus:outline-none focus:border-indigo-500 transition"
              />
            </div>

            {/* 可选动作分支 */}
            <div className="space-y-2">
              <label className="block text-xs font-semibold text-slate-300">分支行动列表 (Actions: {selectedScene.actions?.length || 0})</label>
              <div className="space-y-2">
                {selectedScene.actions?.map((act, idx) => (
                  <div
                    key={act.id || idx}
                    className="p-3 bg-slate-900/70 border border-slate-800 rounded-lg flex items-center justify-between text-xs text-slate-300"
                  >
                    <div>
                      <span className="font-medium text-slate-200">{act.label}</span>
                      <span className="text-[10px] text-slate-500 font-mono ml-2 uppercase">[{act.type}]</span>
                      {act.target_scene && (
                        <span className="text-cyan-400 text-[11px] ml-2">→ 跳转至 {act.target_scene}</span>
                      )}

                      {act.type === 'check' && (
                        <span className="text-amber-400 text-[11px] ml-2">({act.skill} DC: {act.difficulty})</span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* 登场人物卡 */}
            <div className="space-y-2">
              <label className="block text-xs font-semibold text-slate-300">场景登场 NPC (Characters: {selectedScene.npcs?.length || 0})</label>
              {selectedScene.npcs && selectedScene.npcs.length > 0 ? (
                selectedScene.npcs.map((npc) => (
                  <div
                    key={npc.id}
                    className="p-3 bg-slate-900/70 border border-slate-800 rounded-lg flex items-center gap-3 text-xs"
                  >
                    <div className="w-8 h-8 rounded-full bg-amber-500/20 border border-amber-500/40 flex items-center justify-center text-amber-300">
                      👤
                    </div>
                    <div>
                      <div className="font-semibold text-amber-300">{npc.name}</div>
                      <div className="text-slate-400 text-[11px] mt-0.5 italic">"{npc.greeting}"</div>
                    </div>
                  </div>
                ))
              ) : (
                <div className="text-xs text-slate-500 italic py-1">当前场景无常驻 NPC</div>
              )}
            </div>
          </div>
        ) : (
          <div className="flex-1 flex items-center justify-center text-slate-500 text-xs">
            请在左侧选择一个场景节点进行查阅与编辑
          </div>
        )}
      </div>
    </div>
  );
}
