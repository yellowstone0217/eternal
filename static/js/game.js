// game.js - 最终修复版（完整支持选择目标法术）

// 导入模块（如果需要）
//import { SpellReveal } from './camellia/spell-reveal.js';

let currentGameId = null;
let selectedCardIndex = null;
let selectedCardType = null;
let attackMode = false;
let selectedAttackerIndex = null;
let gameStateData = null;
let commanderSlot = 0;
let maxCommanderSlot = 12;
let roundCount = 1;

// ===== 新增：目标选择模式相关变量 =====
let targetMode = false;              // 是否处于目标选择模式
let targetType = null;               // 目标类型: 'minion', 'hero', 'any'
let pendingSpellCard = null;         // 待释放的法术卡牌
let pendingSpellIndex = null;        // 待释放的法术在手牌中的索引
let targetCallback = null;           // 选择目标后的回调函数
// ====================================

// DOM元素
const cardModal = document.getElementById('card-modal');
const modalCardName = document.getElementById('modal-card-name');
const modalCardImage = document.getElementById('modal-card-image');
const modalCardDescription = document.getElementById('modal-card-description');
const modalCardAttack = document.getElementById('modal-card-attack');
const modalCardHealth = document.getElementById('modal-card-health');
const modalCardCost = document.getElementById('modal-card-cost');
const modalCardEffects = document.getElementById('modal-card-effects');
const modalCardWarning = document.getElementById('modal-card-warning');
const closeModal = document.querySelector('.close');
const modalPlayBtn = document.getElementById('modal-play-btn');
const modalAttackBtn = document.getElementById('modal-attack-btn');
const modalAttackHeroBtn = document.getElementById('modal-attack-hero-btn');
const playSelectedBtn = document.getElementById('play-selected-btn');
const endTurnBtn = document.getElementById('end-turn-btn');
const surrenderBtn = document.getElementById('surrender-btn');
const playerHealthEl = document.getElementById('player-health');
const enemyHealthEl = document.getElementById('enemy-health');
const gameMessage = document.getElementById('game-message');
const commanderSlotDisplay = document.getElementById('commander-slot-display');

// 消息提示元素
const gameTip = document.getElementById('game-tip') || (() => {
    const tip = document.createElement('div');
    tip.id = 'game-tip';
    tip.style.position = 'fixed';
    tip.style.bottom = '20px';
    tip.style.left = '50%';
    tip.style.transform = 'translateX(-50%)';
    tip.style.backgroundColor = 'rgba(0,0,0,0.8)';
    tip.style.color = '#f1c40f';
    tip.style.padding = '10px 20px';
    tip.style.borderRadius = '5px';
    tip.style.zIndex = '1000';
    tip.style.display = 'none';
    document.body.appendChild(tip);
    return tip;
})();


// 获取游戏ID
function getGameId() {
    const storedId = sessionStorage.getItem('game_id');
    if (storedId) return storedId;
    if (typeof window.gameId !== 'undefined') return window.gameId;
    const pathParts = window.location.pathname.split('/');
    if (pathParts.length > 2 && pathParts[1] === 'game') return pathParts[2];
    return null;
}

// 从服务器获取当前用户名并存入 sessionStorage
async function fetchCurrentUser() {
    try {
        const response = await fetch('/current_user');
        if (response.ok) {
            const data = await response.json();
            if (data.username) {
                sessionStorage.setItem('user', data.username);
                console.log('已获取用户名:', data.username);
                return data.username;
            }
        }
    } catch (err) {
        console.error('获取用户名失败:', err);
    }
    return '';
}

// 关闭模态框
closeModal.addEventListener('click', () => {
    cardModal.style.display = 'none';
});

window.addEventListener('click', (e) => {
    if (e.target === cardModal) cardModal.style.display = 'none';
});

// 模态框按钮事件
modalPlayBtn.addEventListener('click', () => {
    if (selectedCardType === 'hand' && selectedCardIndex !== null) {
        playCard(selectedCardIndex);
    }
    cardModal.style.display = 'none';
});

modalAttackBtn.addEventListener('click', () => {
    if (selectedCardType === 'board' && selectedCardIndex !== null) {
        enterAttackMode(selectedCardIndex);
    }
    cardModal.style.display = 'none';
});

modalAttackHeroBtn.addEventListener('click', () => {
    if (selectedCardType === 'board' && selectedCardIndex !== null) {
        executeAttack(selectedCardIndex, null, 'hero');
    }
    cardModal.style.display = 'none';
});

// 主界面按钮事件
playSelectedBtn.addEventListener('click', () => {
    if (selectedCardType === 'hand' && selectedCardIndex !== null) {
        playCard(selectedCardIndex);
    }
});

endTurnBtn.addEventListener('click', () => {
    if (!currentGameId) return;
    fetch(`/end_turn/${currentGameId}`, { method: 'POST' })
        .then(response => response.json())
        .then(() => {
            resetAttackMode();
            // ===== 新增：结束回合时清除目标选择模式 =====
            cancelTargetMode();
            // ========================================
            updateGameState();
        })
        .catch(err => {
            console.error('结束回合失败:', err);
            showTip('网络错误，请重试', 'error');
        });
});

surrenderBtn.addEventListener('click', () => {
    if (!currentGameId) return;
    if (confirm('确定要投降吗？')) {
        fetch(`/surrender/${currentGameId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ player: 'player' })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                gameMessage.textContent = '你已投降，游戏结束！';
                showTip('投降成功', 'info');
                sessionStorage.removeItem('game_id');
                setTimeout(() => { window.location.href = '/main'; }, 2000);
            }
        })
        .catch(err => {
            console.error('投降失败:', err);
            showTip('网络错误，请重试', 'error');
        });
    }
});

// 页面加载初始化
document.addEventListener('DOMContentLoaded', async () => {
    // 先获取用户名
    await fetchCurrentUser();

    currentGameId = getGameId();
    if (!currentGameId) {
        console.error('无法获取游戏ID');
        showTip('游戏ID不存在，返回主界面', 'error');
        setTimeout(() => { window.location.href = '/main'; }, 2000);
        return;
    }
    console.log('游戏ID:', currentGameId);
    updateGameState();
    setInterval(() => updateGameState(), 3000); // 每3秒轮询一次
});

// ===== 新增：取消目标选择模式 =====
function cancelTargetMode() {
    if (targetMode) {
        targetMode = false;
        targetType = null;
        pendingSpellCard = null;
        pendingSpellIndex = null;
        targetCallback = null;
        showTip('目标选择已取消', 'info');
        updateGameState(); // 刷新界面，移除高亮
    }
}

// ===== 新增：设置目标选择模式 =====
function setTargetMode(type, spellCard, spellIndex, callback) {
    targetMode = true;
    targetType = type;
    pendingSpellCard = spellCard;
    pendingSpellIndex = spellIndex;
    targetCallback = callback;
    
    // 显示提示信息
    let targetDesc = '';
    if (type === 'minion') {
        targetDesc = '请点击一个敌方随从作为目标';
    } else if (type === 'hero') {
        targetDesc = '请点击敌方英雄作为目标';
    } else {
        targetDesc = '请选择一个目标';
    }
    
    showTip(targetDesc, 'info');
    gameMessage.textContent = `选择目标: ${pendingSpellCard.name}`;
    
    // 刷新界面，应用目标选择高亮
    updateGameState();
}
// =================================

// 完整的 updateGameState 函数 - 修复目标选择模式下的单位显示问题

function updateGameState() {
    if (!currentGameId) return;

    fetch(`/game_state/${currentGameId}`)
        .then(response => {
            if (!response.ok) {
                if (response.status === 404) {
                    sessionStorage.removeItem('game_id');
                    window.location.href = '/main';
                    return null;
                }
                throw new Error('网络响应错误');
            }
            return response.json();
        })
        .then(state => {
            if (!state) return;
            
            // 保存上一次的状态，用于比较
            const prevState = gameStateData;
            gameStateData = state;

            // ===== 检查服务器返回的 pending_spell 状态 =====
            if (state.pending_spell && !targetMode) {
                console.log('检测到服务器待释放法术状态，等待选择目标');
            }

            // 处理敌方音效
            if (state.enemy_sound) {
                console.log('🔊 收到敌方音效:', state.enemy_sound);
                
                const soundId = typeof state.enemy_sound === 'object' ? state.enemy_sound.id : state.enemy_sound;
                const soundPath = typeof state.enemy_sound === 'object' ? state.enemy_sound.path : state.enemy_sound;
                
                const playedSounds = JSON.parse(sessionStorage.getItem('played_sounds') || '{}');
                const now = Date.now();
                
                for (let id in playedSounds) {
                    if (now - playedSounds[id] > 5000) {
                        delete playedSounds[id];
                    }
                }
                
                if (!playedSounds[soundId]) {
                    playedSounds[soundId] = now;
                    sessionStorage.setItem('played_sounds', JSON.stringify(playedSounds));
                    
                    if (window.SoundPlayer) {
                        window.SoundPlayer.play(soundPath)
                            .then(() => {
                                console.log('✅ 敌方音效播放成功');
                            })
                            .catch(err => console.warn('⚠️ 敌方音效播放失败:', err));
                    } else {
                        console.error('❌ SoundPlayer 未定义！请检查脚本加载顺序');
                    }
                } else {
                    console.log('⏭️ 跳过重复音效:', soundId);
                }
            }
            
            // 处理自己播放的音效
            if (state.my_sound) {
                console.log('🔊 收到自己的音效:', state.my_sound);
                
                const soundId = typeof state.my_sound === 'object' ? state.my_sound.id : state.my_sound;
                const soundPath = typeof state.my_sound === 'object' ? state.my_sound.path : state.my_sound;
                
                const playedSounds = JSON.parse(sessionStorage.getItem('played_sounds') || '{}');
                const now = Date.now();
                
                if (!playedSounds[soundId]) {
                    playedSounds[soundId] = now;
                    sessionStorage.setItem('played_sounds', JSON.stringify(playedSounds));
                    
                    if (window.SoundPlayer) {
                        window.SoundPlayer.play(soundPath)
                            .then(() => {
                                console.log('✅ 自己的音效播放成功');
                            })
                            .catch(err => console.warn('⚠️ 自己的音效播放失败:', err));
                    }
                } else {
                    console.log('⏭️ 跳过重复的自有音效:', soundId);
                }
            }

            // 处理敌方使用的法术（翻面动画）
            if (state.enemy_spell_used) {
                console.log('🎬 收到 enemy_spell_used:', state.enemy_spell_used);
                
                const spellId = state.enemy_spell_used.name + '_' + Date.now();
                const playedSpells = JSON.parse(sessionStorage.getItem('played_spells') || '{}');
                const now = Date.now();
                
                for (let id in playedSpells) {
                    if (now - playedSpells[id] > 3000) {
                        delete playedSpells[id];
                    }
                }
                
                if (!playedSpells[spellId]) {
                    playedSpells[spellId] = now;
                    sessionStorage.setItem('played_spells', JSON.stringify(playedSpells));
                    
                    if (window.SpellReveal) {
                        console.log('✅ SpellReveal 存在，准备播放动画');
                        window.SpellReveal.showSpellReveal(state.enemy_spell_used);
                        
                        recordEnemySpell(state.enemy_spell_used);
                    } else {
                        console.error('❌ SpellReveal 未定义！请检查脚本加载');
                    }
                } else {
                    console.log('⏭️ 跳过重复法术动画:', spellId);
                }
            }

            // 更新生命值
            playerHealthEl.textContent = Math.max(0, state.player_health);
            enemyHealthEl.textContent = Math.max(0, state.enemy_health);

            // 显示提示消息
            if (state.message && state.message !== prevState?.message) {
                showTip(state.message, 'info');
            }

            // 更新牌库数量
            const playerDeckEl = document.getElementById('player-deck-count');
            if (playerDeckEl) playerDeckEl.textContent = state.player_deck_count;
            const enemyDeckEl = document.getElementById('enemy-deck-count');
            if (enemyDeckEl) enemyDeckEl.textContent = state.enemy_deck_count;

            // 更新指挥槽
            commanderSlot = state.commander_slot;
            maxCommanderSlot = state.max_commander_slot;
            roundCount = state.round_count;
            updateCommanderSlotDisplay();

            // 游戏结束处理
            if (state.game_over) {
                const currentUser = sessionStorage.getItem('user') || '';
                const message = state.winner === currentUser ? '恭喜你获胜了！' : '你输了！';
                gameMessage.textContent = message;
                showTip(message, state.winner === currentUser ? 'success' : 'error');
                sessionStorage.removeItem('game_id');
                setTimeout(() => { window.location.href = '/main'; }, 5000);
                resetAttackMode();
                cancelTargetMode();
                return;
            }

            // 回合判断
            const currentUser = sessionStorage.getItem('user') || '';
            const currentPlayer = (state.current_player || '').trim();
            console.log('当前用户:', currentUser, '当前回合玩家:', currentPlayer, '是否我的回合:', currentPlayer === currentUser);

            const isMyTurn = (currentPlayer === currentUser);
            
            // 根据目标选择状态显示不同的游戏消息
            if (targetMode) {
                let targetDesc = '';
                if (targetType === 'friendly_minion') {
                    targetDesc = '点击你的一个随从';
                } else if (targetType === 'enemy_minion') {
                    targetDesc = '点击一个敌方随从';
                } else if (targetType === 'hero') {
                    targetDesc = '点击敌方英雄';
                } else {
                    targetDesc = '选择一个目标';
                }
                gameMessage.textContent = `选择目标: ${pendingSpellCard?.name || '法术'} - ${targetDesc}`;
            } else {
                gameMessage.textContent = isMyTurn ? `你的回合 (第${roundCount}回合)` : '敌方回合...';
            }

            // ==================== 更新敌方手牌 ====================
            const enemyHand = document.getElementById('enemy-hand');
            if (enemyHand) {
                enemyHand.innerHTML = '';
                for (let i = 0; i < state.enemy_hand_count; i++) {
                    const cardBack = createCardElement(null, true);
                    const container = document.createElement('div');
                    container.className = 'card-container';
                    container.appendChild(cardBack);
                    enemyHand.appendChild(container);
                }
            }

            // ==================== 更新敌方场上 ====================
            const enemyBoard = document.getElementById('enemy-board');
            if (enemyBoard) {
                enemyBoard.innerHTML = '';
                state.enemy_board.forEach((card, index) => {
                    const container = document.createElement('div');
                    container.className = 'card-container';
                    const cardEl = createCardElement(card, true);
                    cardEl.dataset.index = index;
                    cardEl.dataset.type = 'enemy_minion';
                    
                    // ===== 目标选择模式下的敌方随从处理 =====
                    if (targetMode) {
                        // 判断敌方随从是否可作为目标
                        if (targetType === 'enemy_minion') {
                            // 敌方随从目标：高亮蓝色，可点击
                            cardEl.classList.add('targetable');
                            cardEl.style.cursor = 'pointer';
                            cardEl.style.boxShadow = '0 0 0 3px #3498db, 0 0 15px #3498db';
                            cardEl.style.opacity = '1';
                            cardEl.style.pointerEvents = 'auto';
                            
                            cardEl.addEventListener('click', (e) => {
                                e.stopPropagation();
                                if (targetCallback) {
                                    targetCallback(index);
                                    cancelTargetMode();
                                }
                            });
                        } else if (targetType === 'friendly_minion') {
                            // 友方目标模式：敌方随从置灰不可点
                            cardEl.style.opacity = '0.3';
                            cardEl.style.pointerEvents = 'none';
                        } else if (targetType === 'hero') {
                            // 英雄目标模式：敌方随从置灰不可点
                            cardEl.style.opacity = '0.3';
                            cardEl.style.pointerEvents = 'none';
                        } else {
                            // 其他情况：默认置灰
                            cardEl.style.opacity = '0.3';
                            cardEl.style.pointerEvents = 'none';
                        }
                    } 
                    // ===== 攻击模式下的敌方随从处理 =====
                    else if (attackMode && selectedAttackerIndex !== null) {
                        // 攻击模式：所有敌方随从都可作为攻击目标
                        cardEl.classList.add('targetable');
                        cardEl.style.cursor = 'pointer';
                        
                        cardEl.addEventListener('click', (e) => {
                            e.stopPropagation();
                            if (attackMode && selectedAttackerIndex !== null) {
                                executeAttack(selectedAttackerIndex, index, 'minion');
                            }
                        });
                    } else {
                        // 普通模式：点击显示详情
                        cardEl.addEventListener('click', (e) => {
                            e.stopPropagation();
                            showCardDetails(card, true, 'enemy_minion', index);
                        });
                    }
                    
                    container.appendChild(cardEl);
                    enemyBoard.appendChild(container);
                });
            }

            // ==================== 更新玩家手牌 ====================
            const playerHand = document.getElementById('player-hand');
            if (playerHand) {
                playerHand.innerHTML = '';
                state.player_hand.forEach((card, index) => {
                    const container = document.createElement('div');
                    container.className = 'card-container';
                    container.dataset.index = index;
                    container.dataset.type = 'hand';
                    const cardEl = createCardElement(card, false);
                    cardEl.dataset.index = index;
                    cardEl.dataset.type = 'hand';
                    
                    // ===== 目标选择模式下手牌的处理 =====
                    if (targetMode) {
                        // 目标选择模式下，所有手牌置灰不可点击
                        cardEl.style.opacity = '0.3';
                        cardEl.style.pointerEvents = 'none';
                    } else {
                        // 非目标选择模式：手牌可点击
                        cardEl.addEventListener('click', (e) => {
                            e.stopPropagation();
                            selectCard(index, 'hand', card);
                            showCardDetails(card, false, 'hand', index);
                        });
                    }
                    
                    container.appendChild(cardEl);
                    playerHand.appendChild(container);
                });
            }

            // ==================== 更新玩家场上 ====================
            const playerBoard = document.getElementById('player-board');
            if (playerBoard) {
                playerBoard.innerHTML = '';
                state.player_board.forEach((card, index) => {
                    const container = document.createElement('div');
                    container.className = 'card-container';
                    const cardEl = createCardElement(card, false);
                    cardEl.dataset.index = index;
                    cardEl.dataset.type = 'player_minion';

                    // 显示不能攻击标记
                    if (!card.can_attack) {
                        const mark = document.createElement('div');
                        mark.className = 'cant-attack-mark';
                        mark.textContent = 'Z';
                        container.appendChild(mark);
                    }

                    // ===== 目标选择模式下玩家随从的处理 =====
                    if (targetMode) {
                        // 判断玩家随从是否可作为目标
                        if (targetType === 'friendly_minion') {
                            // 友方随从目标：高亮绿色，可点击
                            cardEl.classList.add('targetable');
                            cardEl.style.cursor = 'pointer';
                            cardEl.style.boxShadow = '0 0 0 3px #2ecc71, 0 0 15px #2ecc71';
                            cardEl.style.opacity = '1';
                            cardEl.style.pointerEvents = 'auto';
                            
                            cardEl.addEventListener('click', (e) => {
                                e.stopPropagation();
                                if (targetCallback) {
                                    targetCallback(index);
                                    cancelTargetMode();
                                }
                            });
                        } else if (targetType === 'enemy_minion') {
                            // 敌方目标模式：玩家随从置灰不可点
                            cardEl.style.opacity = '0.3';
                            cardEl.style.pointerEvents = 'none';
                        } else if (targetType === 'hero') {
                            // 英雄目标模式：玩家随从置灰不可点
                            cardEl.style.opacity = '0.3';
                            cardEl.style.pointerEvents = 'none';
                        } else {
                            // 其他情况：默认置灰
                            cardEl.style.opacity = '0.3';
                            cardEl.style.pointerEvents = 'none';
                        }
                    } 
                    // ===== 攻击模式下玩家随从的处理 =====
                    else if (attackMode) {
                        // 攻击模式：玩家随从可作为攻击者选择
                        cardEl.classList.add('targetable');
                        if (selectedAttackerIndex === index) {
                            cardEl.classList.add('selected');
                        }
                        
                        cardEl.addEventListener('click', (e) => {
                            e.stopPropagation();
                            if (attackMode) {
                                selectAttacker(index);
                            }
                        });
                    } else {
                        // 普通模式：点击显示详情
                        cardEl.addEventListener('click', (e) => {
                            e.stopPropagation();
                            selectCard(index, 'board', card);
                            showCardDetails(card, false, 'board', index);
                        });
                    }
                    
                    container.appendChild(cardEl);
                    playerBoard.appendChild(container);
                });
            }

            // ==================== 敌方英雄目标处理 ====================
            const enemyHealthDisplay = document.querySelector('.enemy-health-display');
            if (enemyHealthDisplay) {
                // 移除旧的点击事件
                const oldHandler = enemyHealthDisplay._clickHandler;
                if (oldHandler) {
                    enemyHealthDisplay.removeEventListener('click', oldHandler);
                    enemyHealthDisplay._clickHandler = null;
                }
                
                // 目标选择模式下，判断敌方英雄是否可作为目标
                if (targetMode && targetType === 'hero') {
                    // 英雄目标模式：高亮橙色，可点击
                    enemyHealthDisplay.style.cursor = 'pointer';
                    enemyHealthDisplay.style.boxShadow = '0 0 0 3px #f39c12, 0 0 15px #f39c12';
                    enemyHealthDisplay.style.borderRadius = '10px';
                    enemyHealthDisplay.style.transition = 'all 0.3s';
                    
                    const handler = (e) => {
                        e.stopPropagation();
                        if (targetCallback) {
                            targetCallback(null); // null 表示目标是英雄
                            cancelTargetMode();
                        }
                    };
                    
                    enemyHealthDisplay._clickHandler = handler;
                    enemyHealthDisplay.addEventListener('click', handler);
                } else {
                    // 非英雄目标模式：恢复默认样式
                    enemyHealthDisplay.style.cursor = 'default';
                    enemyHealthDisplay.style.boxShadow = 'none';
                }
            }

            // 攻击模式样式
            if (attackMode) {
                document.body.classList.add('attack-mode');
            } else {
                document.body.classList.remove('attack-mode');
            }

            // 按钮状态
            playSelectedBtn.disabled = !(selectedCardType === 'hand' && selectedCardIndex !== null) || targetMode;
            endTurnBtn.disabled = !isMyTurn || state.game_over || targetMode;

            // 如果不是自己的回合，重置攻击模式和目标选择模式
            if (!isMyTurn) {
                resetAttackMode();
                cancelTargetMode();
            }
        })
        .catch(err => {
            console.error('更新游戏状态失败:', err);
            showTip('连接服务器失败，请刷新页面', 'error');
        });
}

// 更新指挥槽显示
function updateCommanderSlotDisplay() {
    if (!commanderSlotDisplay) return;
    commanderSlotDisplay.innerHTML = '';

    const roundInfo = document.createElement('div');
    roundInfo.style.marginBottom = '5px';
    roundInfo.style.color = '#3498db';
    roundInfo.style.fontWeight = 'bold';
    roundInfo.textContent = `第${roundCount}回合`;
    commanderSlotDisplay.appendChild(roundInfo);

    const label = document.createElement('span');
    label.textContent = `指挥槽: ${commanderSlot}/${maxCommanderSlot}`;
    label.style.marginRight = '10px';
    label.style.fontWeight = 'bold';
    label.style.color = '#f1c40f';
    commanderSlotDisplay.appendChild(label);

    for (let i = 0; i < maxCommanderSlot; i++) {
        const slotPoint = document.createElement('div');
        slotPoint.className = `slot-point ${i < commanderSlot ? '' : 'empty'}`;
        commanderSlotDisplay.appendChild(slotPoint);
    }
}

// 选择卡牌
function selectCard(index, type, card) {
    selectedCardIndex = index;
    selectedCardType = type;
    playSelectedBtn.disabled = !(type === 'hand');
}

// 选择攻击者
function selectAttacker(index) {
    if (attackMode) {
        selectedAttackerIndex = (selectedAttackerIndex === index) ? null : index;
    } else {
        attackMode = true;
        selectedAttackerIndex = index;
    }
    updateGameState();
}

// 进入攻击模式
function enterAttackMode(index) {
    attackMode = true;
    selectedAttackerIndex = index;
    updateGameState();
}

// 执行攻击
function executeAttack(attackerIndex, targetIndex, targetType) {
    if (attackerIndex === null) return;

    const attackerElement = document.querySelector(`#player-board .card-container:nth-child(${attackerIndex + 1}) .card`);
    if (attackerElement) attackerElement.classList.add('attacking');

    let targetElement = null;
    if (targetType === 'minion') {
        targetElement = document.querySelector(`#enemy-board .card-container:nth-child(${targetIndex + 1}) .card`);
    } else if (targetType === 'hero') {
        targetElement = document.querySelector('.hero-portrait.enemy') || document.querySelector('.enemy-health-display');
    }
    if (targetElement) targetElement.classList.add('targeted');

    // 获取攻击者信息
    const attackerCard = gameStateData.player_board[attackerIndex];
    
    // 检查是否有奋战效果
    const hasValor = attackerCard && attackerCard.effect && attackerCard.effect.includes('奋战');
    
    // 如果是奋战，先不减攻击次数，等攻击完成后再判断
    if (!hasValor) {
        // 没有奋战，正常消耗攻击
        attackMode = false;
        selectedAttackerIndex = null;
    }

    let targetIndexParam = (targetType === 'minion') ? targetIndex : null;

    fetch(`/attack/${currentGameId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            attacker_index: attackerIndex,
            target_index: targetIndexParam
        })
    })
    .then(response => response.json())
    .then(data => {
        setTimeout(() => {
            if (attackerElement) attackerElement.classList.remove('attacking');
            if (targetElement) targetElement.classList.remove('targeted');
            
            if (data.result === true || data.result === 'player_win' || data.result === 'enemy_win') {
                // 如果有奋战效果，允许再次攻击
                if (hasValor) {
                    console.log('💪 奋战效果：可以再次攻击');
                    // 保持攻击模式，不清除 selectedAttackerIndex
                    // 但需要更新游戏状态
                    updateGameState();
                } else {
                    resetAttackMode();
                    updateGameState();
                }
            } else {
                // 攻击失败，无论如何都重置
                resetAttackMode();
                updateGameState();
            }
        }, 300);
    })
    .catch(err => {
        console.error('攻击失败:', err);
        showTip('攻击失败，请重试', 'error');
        if (attackerElement) attackerElement.classList.remove('attacking');
        if (targetElement) targetElement.classList.remove('targeted');
        resetAttackMode();
    });
}

// 完整的 playCard 函数 - 修复目标选择问题

function playCard(cardIndex) {
    if (!currentGameId) {
        console.error('游戏ID不存在');
        showTip('游戏ID不存在', 'error');
        return;
    }
    
    console.log('🎮 打出卡牌，索引:', cardIndex);
    
    // 如果处于目标选择模式，不能打出新卡
    if (targetMode) {
        console.log('⛔ 当前处于目标选择模式，不能打出新卡');
        showTip('请先完成当前法术的目标选择', 'warning');
        return;
    }
    
    // 检查是否有游戏状态数据
    if (!gameStateData) {
        console.error('游戏状态数据不存在');
        showTip('游戏状态异常，请刷新', 'error');
        return;
    }
    
    // 检查手牌是否存在
    if (!gameStateData.player_hand || cardIndex >= gameStateData.player_hand.length) {
        console.error('卡牌索引无效');
        showTip('卡牌不存在', 'error');
        return;
    }
    
    // 获取卡牌信息用于日志
    const card = gameStateData.player_hand[cardIndex];
    console.log('🎮 正在打出的卡牌:', card.name, '费用:', card.cost);
    
    // 发送请求
    fetch(`/play_card/${currentGameId}`, {
        method: 'POST',
        headers: { 
            'Content-Type': 'application/json',
            'X-Requested-With': 'XMLHttpRequest'
        },
        body: JSON.stringify({ card_index: cardIndex })
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.json();
    })
    .then(data => {
        console.log('🎮 出牌响应:', data);
        
        if (data.success) {
            // 出牌成功
            console.log('✅ 出牌成功');
            resetAttackMode();
            selectedCardIndex = null;
            
            // 播放音效（如果有）
            if (data.sound && window.SoundPlayer) {
                window.SoundPlayer.play(data.sound).catch(err => {
                    console.warn('音效播放失败:', err);
                });
            }
            
            // 如果有返回的敌方法术信息，播放翻面动画
            if (data.used_card && window.SpellReveal) {
                console.log('🎬 敌方使用法术，播放翻面动画:', data.used_card);
                window.SpellReveal.showSpellReveal(data.used_card);
                recordEnemySpell(data.used_card);
            }
            
            showTip('出牌成功', 'success');
            
            // 立即更新游戏状态
            updateGameState();
            
        } else if (data.need_target) {
            // ===== 需要选择目标的法术：进入目标选择模式 =====
            console.log('🎯 需要选择目标，进入目标选择模式');
            
            // 获取当前选中的卡牌信息
            const handCards = gameStateData?.player_hand || [];
            const spellCard = handCards[cardIndex];
            
            if (!spellCard) {
                console.error('❌ 找不到法术卡牌信息');
                showTip('卡牌信息错误', 'error');
                return;
            }
            
            console.log('🎯 法术卡牌详情:', {
                name: spellCard.name,
                type: spellCard.type,
                cost: spellCard.cost,
                description: spellCard.description
            });
            
            // ===== 根据卡牌名称确定目标类型 =====
            let targetType = 'enemy_minion'; // 默认敌方随从
            
            // 坚固防线 - 目标是友方随从
            if (spellCard.name === '坚固防线') {
                targetType = 'friendly_minion';
                console.log('🎯 坚固防线: 目标类型设置为 friendly_minion (友方随从)');
            }
            // 治疗类法术 - 目标是友方随从
            else if (spellCard.name.includes('治疗') || 
                     spellCard.name.includes('回血') || 
                     spellCard.name.includes('恢复')) {
                targetType = 'friendly_minion';
                console.log('🎯 治疗法术: 目标类型设置为 friendly_minion');
            }
            // 对敌方英雄造成伤害的法术
            else if (spellCard.name.includes('敌方英雄') || 
                     spellCard.name.includes('英雄打') ||
                     spellCard.name === '对敌方英雄打2') {
                targetType = 'hero';
                console.log('🎯 英雄伤害法术: 目标类型设置为 hero');
            }
            // 对己方英雄回血的法术
            else if (spellCard.name.includes('己方英雄') || 
                     spellCard.name.includes('友方英雄')) {
                targetType = 'friendly_hero';
                console.log('🎯 友方英雄法术: 目标类型设置为 friendly_hero');
            }
            // 其他默认敌方随从的法术
            else {
                console.log('🎯 默认目标类型: enemy_minion (敌方随从)');
            }
            
            console.log('🎯 最终目标类型:', targetType);
            
            // 设置目标选择模式
            setTargetMode(targetType, spellCard, cardIndex, (targetIndex) => {
                // 目标选择后的回调函数
                console.log('🎯 目标已选择:', targetIndex);
                playSpellWithTarget(cardIndex, targetIndex);
            });
            
            // 显示提示信息
            let targetMessage = '';
            if (targetType === 'friendly_minion') {
                targetMessage = '请点击你的一个随从使其获得 +1/+1';
            } else if (targetType === 'enemy_minion') {
                targetMessage = '请点击一个敌方随从作为目标';
            } else if (targetType === 'hero') {
                targetMessage = '请点击敌方英雄作为目标';
            } else if (targetType === 'friendly_hero') {
                targetMessage = '请点击你的英雄作为目标';
            } else {
                targetMessage = '请选择一个目标';
            }
            
            showTip(targetMessage, 'info');
            gameMessage.textContent = `选择目标: ${spellCard.name} - ${targetMessage}`;
            
            // 强制刷新界面，应用目标选择高亮
            setTimeout(() => {
                updateGameState();
            }, 50);
            
        } else {
            // 出牌失败，显示错误信息
            const errorMsg = data.message || '无法打出这张卡牌！';
            console.error('❌ 出牌失败:', errorMsg);
            gameMessage.textContent = errorMsg;
            showTip(errorMsg, 'error');
            
            // 3秒后清除错误消息
            setTimeout(() => {
                if (gameMessage.textContent === errorMsg) {
                    gameMessage.textContent = '';
                }
            }, 3000);
        }
    })
    .catch(err => {
        console.error('❌ 出牌请求失败:', err);
        showTip('网络错误，请重试', 'error');
    });
}

// ===== 新增：带目标的法术释放 =====
function playSpellWithTarget(cardIndex, targetIndex) {
    if (!currentGameId) return;
    
    console.log('释放带目标的法术，卡牌索引:', cardIndex, '目标索引:', targetIndex);
    
    fetch(`/play_spell_target/${currentGameId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ target_index: targetIndex })
    })
    .then(response => response.json())
    .then(data => {
        console.log('法术释放响应:', data);
        
        if (data.success) {
            resetAttackMode();
            selectedCardIndex = null;
            updateGameState();
            showTip('法术释放成功', 'success');
            
            // 清除目标选择模式
            cancelTargetMode();
        } else {
            showTip('法术释放失败', 'error');
            cancelTargetMode();
        }
    })
    .catch(err => {
        console.error('法术释放失败:', err);
        showTip('法术释放失败，请重试', 'error');
        cancelTargetMode();
    });
}

// 重置攻击模式
function resetAttackMode() {
    attackMode = false;
    selectedAttackerIndex = null;
    
    // 重置所有随从的奋战计数
    if (gameStateData && gameStateData.player_board) {
        gameStateData.player_board.forEach(card => {
            if (card.attacks_this_turn !== undefined) {
                card.attacks_this_turn = 0;
            }
        });
    }
}

// 显示卡牌详情
function showCardDetails(card, isEnemy, type, index) {
    if (!card) return;

    modalCardName.textContent = card.name || '未知卡牌';
    modalCardDescription.textContent = card.description || '暂无描述';

    // 攻击力颜色
    const curAtk = card.attack || 0;
    let atkColor = '#ffffff';
    if (card.original_attack !== undefined) {
        const origAtk = card.original_attack;
        if (curAtk < origAtk) atkColor = '#e74c3c';
        else if (curAtk > origAtk) atkColor = '#2ecc71';
        else atkColor = '#ffffff';
    }
    modalCardAttack.innerHTML = `<span style="color: ${atkColor};">${curAtk}</span>`;
    if (card.original_attack !== undefined && curAtk !== card.original_attack) {
        modalCardAttack.innerHTML += ` <span style="color: #7f8c8d; font-size: 14px;">(${card.original_attack})</span>`;
    }

    // 血量颜色
    const curHp = card.health;
    let hpColor = '#ffffff';
    if (card.original_health !== undefined) {
        const origHp = card.original_health;
        if (curHp < origHp) hpColor = '#e74c3c';
        else if (curHp > origHp) hpColor = '#2ecc71';
        else hpColor = '#ffffff';
    }
    modalCardHealth.innerHTML = `<span style="color: ${hpColor};">${curHp}</span>`;
    if (card.original_health !== undefined && curHp !== card.original_health) {
        modalCardHealth.innerHTML += ` <span style="color: #7f8c8d; font-size: 14px;">(${card.original_health})</span>`;
    }

    modalCardCost.textContent = card.cost || 0;

    if (card.image) {
        modalCardImage.style.backgroundImage = `url('/static/images/${card.image}')`;
    } else {
        modalCardImage.style.backgroundImage = '';
        modalCardImage.style.backgroundColor = '#34495e';
    }

    // 过滤效果标签
    modalCardEffects.innerHTML = '';
    if (card.type !== 'spell' && card.effect && card.effect.length > 0) {
        let effectsToShow = card.effect.filter(eff => !eff.startsWith('抽到时：'));
        if (card.hiddeneffect && Array.isArray(card.hiddeneffect)) {
            effectsToShow = effectsToShow.filter(eff => !card.hiddeneffect.includes(eff));
        }
        effectsToShow.forEach(eff => {
            const tag = document.createElement('div');
            tag.className = 'modal-effect-tag';
            tag.textContent = eff;
            modalCardEffects.appendChild(tag);
        });
    }

    if (type === 'hand') {
        modalPlayBtn.style.display = 'block';
        modalAttackBtn.style.display = 'none';
        modalAttackHeroBtn.style.display = 'none';
        modalPlayBtn.disabled = (card.cost || 0) > commanderSlot;
        modalCardWarning.textContent = modalPlayBtn.disabled ? '指挥槽不足！' : '';
    } else if (type === 'board') {
        modalPlayBtn.style.display = 'none';
        modalAttackBtn.style.display = 'block';
        modalAttackHeroBtn.style.display = 'block';
        modalAttackBtn.disabled = !card.can_attack;
        modalAttackHeroBtn.disabled = !card.can_attack;
    } else {
        modalPlayBtn.style.display = 'none';
        modalAttackBtn.style.display = 'none';
        modalAttackHeroBtn.style.display = 'none';
    }

    selectedCardIndex = index;
    selectedCardType = type;

    cardModal.style.display = 'block';
}

// 创建卡牌元素
function createCardElement(card, isEnemy) {
    const cardEl = document.createElement('div');
    cardEl.className = `card ${isEnemy ? 'enemy' : 'player'}`;

    if (!card) {
        cardEl.classList.add('card-back');
        return cardEl;
    }

    let imageUrl = '';
    if (card.image) {
        imageUrl = `/static/images/${card.image}`;
    }

    const curAtk = card.attack || 0;
    let atkColor = '#ffffff';
    if (card.original_attack !== undefined) {
        const origAtk = card.original_attack;
        if (curAtk < origAtk) atkColor = '#e74c3c';
        else if (curAtk > origAtk) atkColor = '#2ecc71';
        else atkColor = '#ffffff';
    }

    const curHp = card.health;
    let hpColor = '#ffffff';
    if (card.original_health !== undefined) {
        const origHp = card.original_health;
        if (curHp < origHp) hpColor = '#e74c3c';
        else if (curHp > origHp) hpColor = '#2ecc71';
        else hpColor = '#ffffff';
    }

    // 过滤效果
    // 过滤效果 - 让所有卡牌都能显示效果
    let effectsToShow = [];
    if (card.effect && card.effect.length > 0) {
        effectsToShow = card.effect.filter(eff => !eff.startsWith('抽到时：'));
        if (card.hiddeneffect && Array.isArray(card.hiddeneffect)) {
            effectsToShow = effectsToShow.filter(eff => !card.hiddeneffect.includes(eff));
        }
    }
    
    let effectsHtml = '';
    if (effectsToShow.length > 0) {
        effectsHtml = '<div class="card-effects">';
        effectsToShow.forEach(eff => {
            effectsHtml += `<div class="effect-tag">${eff}</div>`;
        });
        effectsHtml += '</div>';
    }

    cardEl.innerHTML = `
        <div class="card-cost">${card.cost || 0}</div>
        <div class="card-image" style="background-image: url('${imageUrl}')"></div>
        ${effectsHtml}
        <div class="card-name">${card.name || '未知卡牌'}</div>
        <div class="card-stats">
            <span class="attack" style="color: ${atkColor};">⚔️ ${curAtk}</span>
            <span class="health" style="color: ${hpColor};">❤️ ${curHp}</span>
        </div>
    `;

    return cardEl;
}

// 显示提示消息
function showTip(msg, type = 'info') {
    gameTip.textContent = msg;
    gameTip.style.display = 'block';
    if (type === 'error') {
        gameTip.style.backgroundColor = 'rgba(231, 76, 60, 0.9)';
        gameTip.style.color = 'white';
    } else if (type === 'success') {
        gameTip.style.backgroundColor = 'rgba(46, 204, 113, 0.9)';
        gameTip.style.color = 'white';
    } else if (type === 'warning') {
        gameTip.style.backgroundColor = 'rgba(241, 196, 15, 0.9)';
        gameTip.style.color = 'black';
    } else {
        gameTip.style.backgroundColor = 'rgba(0, 0, 0, 0.8)';
        gameTip.style.color = '#f1c40f';
    }
    setTimeout(() => { gameTip.style.display = 'none'; }, 3000);
}

// ========== 技能查看面板 ==========
let skillRecords = [];

// 记录敌方使用的技能
function recordEnemySpell(card) {
    if (!card) return;
    
    const record = {
        name: card.name || '未知技能',
        description: card.description || '暂无描述',
        round: roundCount,
        timestamp: Date.now()
    };
    
    skillRecords.unshift(record);
    
    if (skillRecords.length > 20) {
        skillRecords.pop();
    }
    
    updateSkillList();
}

// 更新技能列表显示
function updateSkillList() {
    const skillList = document.getElementById('skill-list');
    if (!skillList) return;
    
    if (skillRecords.length === 0) {
        skillList.innerHTML = '<div class="skill-empty">暂无技能记录</div>';
        return;
    }
    
    skillList.innerHTML = '';
    skillRecords.forEach(record => {
        const item = document.createElement('div');
        item.className = 'skill-item';
        item.innerHTML = `
            <div class="skill-item-header">
                <span class="skill-name">${record.name}</span>
                <span class="skill-round">第${record.round}回合</span>
            </div>
            <div class="skill-description">${record.description}</div>
        `;
        skillList.appendChild(item);
    });
}

// 初始化技能面板
document.addEventListener('DOMContentLoaded', function() {
    const toggleBtn = document.getElementById('skill-panel-toggle');
    const panel = document.getElementById('skill-panel');
    const closeBtn = document.getElementById('close-skill-panel');
    
    if (toggleBtn && panel) {
        toggleBtn.addEventListener('click', () => {
            panel.classList.toggle('open');
        });
    }
    
    if (closeBtn && panel) {
        closeBtn.addEventListener('click', () => {
            panel.classList.remove('open');
        });
    }
    
    document.addEventListener('click', (e) => {
        if (panel && panel.classList.contains('open')) {
            if (!panel.contains(e.target) && !toggleBtn.contains(e.target)) {
                panel.classList.remove('open');
            }
        }
    });
    
    // ===== 新增：ESC键取消目标选择 =====
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && targetMode) {
            cancelTargetMode();
        }
    });
});




// ========== 消耗战动画 ==========
function playConsumeAnimation(cardElement, unitName, owner, index) {
    if (!cardElement) return;
    
    console.log(`🎬 播放消耗战动画: ${unitName}`);
    
    // 1. 震屏效果
    document.body.classList.add('screen-shake');
    setTimeout(() => {
        document.body.classList.remove('screen-shake');
    }, 500);
    
    // 2. 添加闪光效果
    cardElement.classList.add('consume-flash');
    
    // 3. 创建残影
    for (let i = 0; i < 3; i++) {
        setTimeout(() => {
            const afterimage = document.createElement('div');
            afterimage.className = 'consume-afterimage';
            
            // 复制卡片样式
            const styles = window.getComputedStyle(cardElement);
            afterimage.style.background = styles.background;
            afterimage.style.width = styles.width;
            afterimage.style.height = styles.height;
            afterimage.style.left = cardElement.offsetLeft + 'px';
            afterimage.style.top = cardElement.offsetTop + 'px';
            afterimage.style.position = 'absolute';
            
            cardElement.parentNode.appendChild(afterimage);
            
            // 残影飞走
            setTimeout(() => {
                afterimage.remove();
            }, 500);
        }, i * 100);
    }
    
    // 4. 创建粒子效果
    const rect = cardElement.getBoundingClientRect();
    const centerX = rect.left + rect.width / 2;
    const centerY = rect.top + rect.height / 2;
    
    for (let i = 0; i < 12; i++) {
        setTimeout(() => {
            const particle = document.createElement('div');
            particle.className = 'consume-particle';
            
            // 随机方向
            const angle = (i / 12) * Math.PI * 2 + Math.random() * 0.5;
            const distance = 100 + Math.random() * 100;
            const tx = Math.cos(angle) * distance;
            const ty = Math.sin(angle) * distance - 50;
            
            particle.style.setProperty('--tx', `${tx}px`);
            particle.style.setProperty('--ty', `${ty}px`);
            particle.style.left = centerX + 'px';
            particle.style.top = centerY + 'px';
            particle.style.animation = `particle-explode 1s ease-out forwards`;
            
            document.body.appendChild(particle);
            
            setTimeout(() => {
                particle.remove();
            }, 1000);
        }, i * 50);
    }
    
    // 5. 主卡片动画（变大、左移、消失）
    cardElement.classList.add('consume-remove-animation');
    
    // 6. 播放音效
    playSound('/static/sounds/消耗战.wav');
    
    // 7. 动画结束后移除卡片
    setTimeout(() => {
        if (cardElement.parentNode) {
            cardElement.remove();
        }
    }, 1200);
}

// ========== 返场动画 ==========
function playReturnAnimation(container, cardData, position) {
    console.log(`🎬 播放返场动画: ${cardData.name}`);
    
    // 创建卡片元素
    const cardElement = document.createElement('div');
    cardElement.className = 'card consume-return-animation';
    cardElement.dataset.name = cardData.name;
    
    // 构建卡片HTML
    let effectHtml = '';
    if (cardData.effect) {
        if (Array.isArray(cardData.effect)) {
            effectHtml = cardData.effect.join(' ');
        } else {
            effectHtml = cardData.effect;
        }
    }
    
    // 图片路径
    const imageUrl = cardData.image ? `/static/images/${cardData.image}` : '';
    
    cardElement.innerHTML = `
        <div class="card-cost">${cardData.cost || '?'}</div>
        <div class="card-name">${cardData.name}</div>
        <div class="card-image" style="background-image: url('${imageUrl}')"></div>
        <div class="card-stats">
            <span class="attack">⚔️${cardData.attack !== undefined ? cardData.attack : '-'}</span>
            <span class="health">❤️${cardData.health !== undefined ? cardData.health : '-'}</span>
        </div>
        ${effectHtml ? `<div class="card-effect">${effectHtml}</div>` : ''}
    `;
    
    // 添加到容器（指定位置）
    const children = container.children;
    if (position < children.length) {
        container.insertBefore(cardElement, children[position]);
    } else {
        container.appendChild(cardElement);
    }
    
    // 播放音效
    playSound('/static/sounds/返场.wav');
    
    // 动画结束后恢复正常
    setTimeout(() => {
        cardElement.classList.remove('consume-return-animation');
    }, 1000);
    
    return cardElement;
}

// ========== 播放音效 ==========
function playSound(soundPath) {
    const audio = new Audio(soundPath);
    audio.volume = 0.5;
    audio.play().catch(e => console.log('音效播放失败:', e));
}

// ========== Socket.io 监听消耗战动画 ==========
// 确保 socket 对象存在
if (typeof socket !== 'undefined') {
    socket.on('consume_animation', function(data) {
        console.log('🎬 收到消耗战动画:', data);
        
        const owner = data.owner; // 'player' 或 'enemy'
        const index = data.index;
        const unitName = data.unit;
        
        let container;
        if (owner === 'player') {
            container = document.querySelector('.player-board');
        } else {
            container = document.querySelector('.enemy-board');
        }
        
        if (container) {
            const cards = container.querySelectorAll('.card');
            if (cards[index]) {
                playConsumeAnimation(cards[index], unitName, owner, index);
            }
        }
    });

    socket.on('return_animation', function(data) {
        console.log('🎬 收到返场动画:', data);
        
        const owner = data.owner;
        const cardData = data.card;
        const position = data.position;
        
        let container;
        if (owner === 'player') {
            container = document.querySelector('.player-board');
        } else {
            container = document.querySelector('.enemy-board');
        }
        
        if (container) {
            playReturnAnimation(container, cardData, position);
        }
    });
} else {
    console.warn('⚠️ Socket.io 未初始化，无法监听动画');
    
    // 如果 socket 未定义，尝试等待它初始化
    const checkSocket = setInterval(() => {
        if (typeof socket !== 'undefined') {
            clearInterval(checkSocket);
            console.log('✅ Socket.io 已初始化，重新绑定动画监听');
            
            socket.on('consume_animation', function(data) {
                console.log('🎬 收到消耗战动画:', data);
                const owner = data.owner;
                const index = data.index;
                const unitName = data.unit;
                
                let container;
                if (owner === 'player') {
                    container = document.querySelector('.player-board');
                } else {
                    container = document.querySelector('.enemy-board');
                }
                
                if (container) {
                    const cards = container.querySelectorAll('.card');
                    if (cards[index]) {
                        playConsumeAnimation(cards[index], unitName, owner, index);
                    }
                }
            });

            socket.on('return_animation', function(data) {
                console.log('🎬 收到返场动画:', data);
                const owner = data.owner;
                const cardData = data.card;
                const position = data.position;
                
                let container;
                if (owner === 'player') {
                    container = document.querySelector('.player-board');
                } else {
                    container = document.querySelector('.enemy-board');
                }
                
                if (container) {
                    playReturnAnimation(container, cardData, position);
                }
            });
        }
    }, 500);
}