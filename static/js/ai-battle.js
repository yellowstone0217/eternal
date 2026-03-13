// static/js/ai-battle.js
(function() {
    'use strict';
    
    console.log('🤖 AI对战模块加载中...');
    
    // 配置
    const CONFIG = {
        tipDuration: 3000,
        gameEnterDelay: 500
    };
    
    // 显示提示消息
    function showTip(msg, type = 'info') {
        // 尝试使用 main.html 中的 showStatus 函数
        if (typeof window.showStatus === 'function') {
            window.showStatus(msg, type);
            return;
        }
        
        // 如果没有，创建临时提示
        let tip = document.getElementById('ai-tip');
        if (!tip) {
            tip = document.createElement('div');
            tip.id = 'ai-tip';
            tip.style.position = 'fixed';
            tip.style.top = '20px';
            tip.style.left = '50%';
            tip.style.transform = 'translateX(-50%)';
            tip.style.padding = '10px 20px';
            tip.style.borderRadius = '5px';
            tip.style.zIndex = '10000';
            tip.style.fontWeight = 'bold';
            tip.style.boxShadow = '0 4px 15px rgba(0,0,0,0.3)';
            tip.style.transition = 'all 0.3s ease';
            document.body.appendChild(tip);
        }
        
        tip.textContent = msg;
        tip.style.backgroundColor = type === 'error' ? 'rgba(231, 76, 60, 0.9)' : 
                                  type === 'success' ? 'rgba(46, 204, 113, 0.9)' : 
                                  'rgba(0, 0, 0, 0.8)';
        tip.style.color = type === 'warning' ? 'black' : 'white';
        tip.style.display = 'block';
        
        setTimeout(() => {
            tip.style.display = 'none';
        }, CONFIG.tipDuration);
    }
    
    // AI对战类
    class AIBattle {
        constructor() {
            this.socket = null;
            this.initialized = false;
            this.pendingGameId = null;
            this.init();
        }
        
        init() {
            console.log('🤖 初始化AI对战模块');
            
            // 等待socket连接
            this.waitForSocket();
            
            // 设置UI监听
            this.setupUIListener();
        }
        
        waitForSocket() {
            if (window.socket && window.socket.connected) {
                this.socket = window.socket;
                this.setupEventListeners();
                console.log('✅ AI模块已连接socket');
            } else {
                console.log('⏳ 等待socket连接...');
                setTimeout(() => this.waitForSocket(), 500);
            }
        }
        
        setupEventListeners() {
            if (!this.socket) return;
            
            // AI游戏创建成功
            this.socket.on('ai_game_created', (data) => {
                console.log('✅ AI游戏创建成功:', data);
                showTip(data.message || 'AI对战创建成功', 'success');
                
                if (data.game_id) {
                    this.pendingGameId = data.game_id;
                    
                    // 延迟一点进入游戏
                    setTimeout(() => {
                        this.enterGame(data.game_id);
                    }, CONFIG.gameEnterDelay);
                }
            });
            
            // AI思考提示
            this.socket.on('ai_thinking', (data) => {
                console.log('🤔 AI正在思考');
                showTip(data.message || 'AI正在思考...', 'info');
            });
            
            // AI回合结束
            this.socket.on('ai_turn_end', (data) => {
                console.log('✅ AI回合结束');
                showTip(data.message || 'AI回合结束', 'info');
            });
            
            // AI错误
            this.socket.on('ai_error', (data) => {
                console.error('❌ AI错误:', data);
                showTip(data.message || 'AI对战出错', 'error');
            });
        }
        
        setupUIListener() {
            // 等待对手输入框出现
            const checkInterval = setInterval(() => {
                const opponentInput = document.getElementById('opponentName');
                if (opponentInput) {
                    clearInterval(checkInterval);
                    this.createDifficultySelector(opponentInput);
                    
                    // 监听输入变化
                    opponentInput.addEventListener('input', () => {
                        this.handleOpponentInput(opponentInput);
                    });
                }
            }, 500);
        }
        
        createDifficultySelector(input) {
            if (document.getElementById('ai-difficulty-select')) return;
            
            const parentDiv = input.closest('.invite-input') || input.parentElement;
            if (!parentDiv) return;
            
            const selectorDiv = document.createElement('div');
            selectorDiv.id = 'ai-difficulty-select';
            selectorDiv.style.marginTop = '10px';
            selectorDiv.style.padding = '10px';
            selectorDiv.style.backgroundColor = 'rgba(52, 73, 94, 0.8)';
            selectorDiv.style.borderRadius = '50px';
            selectorDiv.style.border = '1px solid #f1c40f';
            selectorDiv.style.display = 'none';
            
            selectorDiv.innerHTML = `
                <div style="display: flex; align-items: center; gap: 10px;">
                    <span style="color: #f1c40f; font-size: 14px;">🤖 AI难度:</span>
                    <select id="ai-difficulty" style="
                        flex: 1;
                        padding: 5px 10px;
                        background: #2c3e50;
                        color: white;
                        border: 1px solid #3498db;
                        border-radius: 20px;
                        font-size: 14px;
                    ">
                        <option value="简单AI">简单AI</option>
                        <option value="普通AI" selected>普通AI</option>
                        <option value="困难AI">困难AI</option>
                        <option value="自定义AI">自定义AI</option>
                    </select>
                </div>
            `;
            
            parentDiv.appendChild(selectorDiv);
        }
        
        handleOpponentInput(input) {
            const val = input.value.trim();
            const selector = document.getElementById('ai-difficulty-select');
            
            if (selector) {
                selector.style.display = val === 'AI' ? 'block' : 'none';
            }
        }
        
        sendInvite(deckName) {
            const opponentInput = document.getElementById('opponentName');
            if (!opponentInput) {
                showTip('找不到对手输入框', 'error');
                return false;
            }
            
            const opponent = opponentInput.value.trim();
            
            if (opponent !== 'AI') {
                return false; // 不是AI对战
            }
            
            if (!deckName) {
                showTip('请选择卡组', 'error');
                return false;
            }
            
            const difficultySelect = document.getElementById('ai-difficulty');
            const aiDifficulty = difficultySelect ? difficultySelect.value : '普通AI';
            
            console.log('🤖 发送AI对战请求:', { opponent: 'AI', deckName, aiDifficulty });
            
            if (!this.socket) {
                this.socket = window.socket;
                if (!this.socket) {
                    showTip('连接服务器失败', 'error');
                    return false;
                }
                this.setupEventListeners();
            }
            
            this.socket.emit('invite', {
                opponent: 'AI',
                deck_name: deckName,
                ai_difficulty: aiDifficulty
            });
            
            showTip(`正在创建 ${aiDifficulty} 对战...`, 'info');
            return true;
        }
        
        enterGame(gameId) {
            console.log('🎮 尝试进入游戏:', gameId);
            
            // 保存到 sessionStorage
            sessionStorage.setItem('game_id', gameId);
            
            // 使用 main.html 中的 enterGame 函数
            if (typeof window.enterGame === 'function') {
                window.enterGame(gameId);
            } else {
                // 如果没有，直接跳转
                fetch(`/set_game_session/${gameId}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                })
                .then(res => res.json())
                .then(result => {
                    if (result.success) {
                        window.location.href = '/';
                    } else {
                        showTip('进入游戏失败', 'error');
                    }
                })
                .catch(err => {
                    console.error('进入游戏失败:', err);
                    showTip('网络错误', 'error');
                });
            }
        }
    }
    
    // 等待DOM加载完成
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
    
    function init() {
        console.log('🤖 启动AI对战模块');
        
        // 创建AI实例
        window.aiBattle = new AIBattle();
        
        // 挂载到全局
        window.sendAIBattle = function(deckName) {
            return window.aiBattle.sendInvite(deckName);
        };
    }
    
})();