// static/js/monkey_patch_skills.js
// 技能记录猴子补丁 - 拦截攻击动画并记录技能

(function() {
    console.log('技能记录猴子补丁已加载...');
    
    // 等待 game.js 加载完成
    let checkCount = 0;
    const maxChecks = 50; // 最多等待10秒
    
    function initPatch() {
        // 检查游戏相关变量是否已定义
        if (typeof window.recordEnemySpell === 'function') {
            console.log('找到 recordEnemySpell 函数，开始注入技能记录');
            setupSkillRecording();
        } else {
            // 如果还没加载好，继续等待
            if (checkCount < maxChecks) {
                checkCount++;
                setTimeout(initPatch, 200);
            } else {
                console.log('等待超时，尝试手动创建技能记录函数');
                createFallbackFunctions();
            }
        }
    }
    
    // 设置技能记录
    function setupSkillRecording() {
        console.log('设置技能记录拦截器...');
        
        // 方法1: 拦截 play_card 请求
        const originalFetch = window.fetch;
        window.fetch = function() {
            const url = arguments[0];
            const options = arguments[1] || {};
            
            // 检查是否是打出卡牌的请求
            if (typeof url === 'string' && url.includes('/play_card/') && options.method === 'POST') {
                return originalFetch.apply(this, arguments).then(response => {
                    // 克隆响应以便多次读取
                    const clonedResponse = response.clone();
                    
                    // 解析响应
                    clonedResponse.json().then(data => {
                        // 如果成功打出卡牌，并且需要目标（法术牌）
                        if (data.success && data.need_target) {
                            console.log('检测到法术牌需要目标');
                            // 稍后会在 play_spell_target 中记录
                        } else if (data.success) {
                            // 立即生效的法术牌
                            console.log('检测到立即生效的法术牌');
                            
                            // 尝试从卡牌信息中获取法术名称
                            setTimeout(() => {
                                // 这里无法直接获取卡牌名称，需要其他方式
                                // 通过游戏状态更新间接记录
                            }, 500);
                        }
                    }).catch(() => {});
                    
                    return response;
                });
            }
            
            // 拦截 play_spell_target 请求（法术选择目标后）
            if (typeof url === 'string' && url.includes('/play_spell_target/') && options.method === 'POST') {
                return originalFetch.apply(this, arguments).then(response => {
                    const clonedResponse = response.clone();
                    
                    clonedResponse.json().then(data => {
                        if (data.success) {
                            console.log('法术成功释放，准备记录');
                            
                            // 从请求体中获取法术信息（如果有）
                            try {
                                const body = JSON.parse(options.body);
                                // 这里没有卡牌信息，只能从游戏状态推断
                                // 所以我们使用替代方法：监听游戏状态更新
                            } catch (e) {}
                        }
                    }).catch(() => {});
                    
                    return response;
                });
            }
            
            return originalFetch.apply(this, arguments);
        };
        
        // 方法2: 拦截游戏状态更新，检测敌方新出现的法术
        const originalUpdateGameState = window.updateGameState;
        if (typeof originalUpdateGameState === 'function') {
            window.updateGameState = function() {
                // 保存旧的状态
                const oldState = window.gameStateData;
                
                // 调用原始函数
                const result = originalUpdateGameState.apply(this, arguments);
                
                // 在新状态更新后，检查是否有敌方使用法术的线索
                setTimeout(() => {
                    const newState = window.gameStateData;
                    if (newState && oldState) {
                        // 检查敌方手牌数量变化（如果减少了，可能是使用了法术）
                        if (newState.enemy_hand_count < oldState.enemy_hand_count) {
                            console.log('检测到敌方手牌减少，可能是使用了法术');
                            // 记录一个通用法术（因为不知道具体名称）
                            window.recordEnemySpell({
                                name: '敌方技能',
                                description: '敌方使用了法术牌',
                                effect: ['法术']
                            });
                        }
                    }
                }, 500);
                
                return result;
            };
            console.log('已拦截 updateGameState');
        }
        
        // 方法3: 在攻击动画时检查法术（更可靠的方法）
        // 添加一个定时器，定期检查游戏状态中的新法术线索
        setInterval(() => {
            const gameState = window.gameStateData;
            if (!gameState) return;
            
            // 从游戏消息中提取法术信息
            const message = gameState.message || '';
            if (message.includes('技能') || message.includes('法术') || message.includes('使用')) {
                console.log('从游戏消息检测到技能:', message);
                
                // 提取技能名称（简单提取）
                let spellName = '未知技能';
                const match = message.match(/使用技能?\s*([^，。]+)/);
                if (match && match[1]) {
                    spellName = match[1].trim();
                } else if (message.includes('打出')) {
                    const match2 = message.match(/打出\s*([^，。]+)/);
                    if (match2 && match2[1]) {
                        spellName = match2[1].trim();
                    }
                }
                
                // 如果消息包含技能信息且不是玩家自己使用的（根据当前回合判断）
                const currentUser = sessionStorage.getItem('user') || '';
                const isMyTurn = (gameState.current_player === currentUser);
                
                // 如果不是我的回合，说明是敌方使用的技能
                if (!isMyTurn && window.recordEnemySpell) {
                    window.recordEnemySpell({
                        name: spellName,
                        description: message,
                        effect: ['法术']
                    });
                }
            }
        }, 1000);
        
        // 方法4: 添加一些测试数据以便验证功能
        setTimeout(() => {
            console.log('添加测试数据以便验证技能记录功能...');
            if (window.recordEnemySpell) {
                // 添加几条测试记录
                window.recordEnemySpell({
                    name: '测试技能1',
                    description: '这是一个测试技能',
                    effect: ['测试']
                });
                
                window.recordEnemySpell({
                    name: '测试技能2',
                    description: '另一个测试技能',
                    effect: ['测试']
                });
                
                console.log('已添加测试数据，技能面板应该能看到记录');
            }
        }, 2000);
    }
    
    // 如果找不到函数，创建回退函数
    function createFallbackFunctions() {
        console.log('创建回退技能记录函数');
        
        // 创建技能记录数组
        window.skillRecords = window.skillRecords || [];
        
        // 创建记录函数
        window.recordEnemySpell = function(card) {
            if (!card) return;
            
            const record = {
                name: card.name || '未知技能',
                description: card.description || '暂无描述',
                round: window.roundCount || 1,
                timestamp: Date.now()
            };
            
            window.skillRecords.unshift(record);
            
            // 只保留最近20条记录
            if (window.skillRecords.length > 20) {
                window.skillRecords.pop();
            }
            
            // 更新显示
            if (typeof window.updateSkillList === 'function') {
                window.updateSkillList();
            } else {
                // 手动更新显示
                updateSkillListFallback();
            }
        };
        
        // 创建更新函数
        window.updateSkillList = function() {
            const skillList = document.getElementById('skill-list');
            if (!skillList) return;
            
            if (window.skillRecords.length === 0) {
                skillList.innerHTML = '<div class="skill-empty">暂无技能记录</div>';
                return;
            }
            
            skillList.innerHTML = '';
            window.skillRecords.forEach(record => {
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
        };
        
        // 回退更新函数
        function updateSkillListFallback() {
            const skillList = document.getElementById('skill-list');
            if (!skillList) return;
            
            if (window.skillRecords.length === 0) {
                skillList.innerHTML = '<div class="skill-empty">暂无技能记录</div>';
                return;
            }
            
            skillList.innerHTML = '';
            window.skillRecords.forEach(record => {
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
        
        // 添加测试数据
        setTimeout(() => {
            window.recordEnemySpell({
                name: '测试技能1',
                description: '猴子补丁添加的测试技能',
                effect: ['测试']
            });
            window.recordEnemySpell({
                name: '测试技能2',
                description: '另一个测试技能',
                effect: ['测试']
            });
        }, 1000);
    }
    
    // 启动初始化
    initPatch();
})();