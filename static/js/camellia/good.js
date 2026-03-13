// good.js - 修复版本
(function() {
    'use strict';
    
    console.log('good.js 已加载');
    
    // 保存已经处理过的特殊动作，防止重复跳转
    const processedActions = new Set();
    
    // 检查特殊动作
    function checkSpecialActions(gameState) {
        // 添加空值检查
        if (!gameState) return false;
        
        // 检查是否有特殊动作需要执行
        if (gameState.special_action) {
            const action = gameState.special_action;
            
            // 创建唯一标识
            const actionId = `${action.type}_${action.redirect_url}_${Date.now()}`;
            
            // 检查是否已经处理过相同的动作（最近5秒内）
            const now = Date.now();
            for (const [key, timestamp] of processedActions.entries()) {
                if (now - timestamp > 5000) { // 5秒后过期
                    processedActions.delete(key);
                }
            }
            
            // 如果已经处理过，跳过
            if (processedActions.has(actionId)) {
                console.log('跳过已处理的特殊动作:', action);
                return false;
            }
            
            console.log('检测到特殊动作:', action);
            
            if (action.type === 'discover' && action.redirect_url && action.active !== false) {
                console.log('跳转到发现页面:', action.redirect_url);
                
                // 记录已处理
                processedActions.add(actionId);
                
                // 延迟跳转，避免多次触发
                setTimeout(() => {
                    window.location.href = action.redirect_url;
                }, 100);
                
                return true;
            }
        }
        return false;
    }
    
    // 保存原始的 updateGameState 函数
    const originalUpdateGameState = window.updateGameState;
    
    // 如果已经存在 updateGameState 函数，则包装它
    if (typeof originalUpdateGameState === 'function') {
        window.updateGameState = function() {
            // 先调用原始的 updateGameState
            const result = originalUpdateGameState.apply(this, arguments);
            
            // 获取最新的游戏状态（如果有）
            if (window.gameStateData) {
                checkSpecialActions(window.gameStateData);
            }
            
            return result;
        };
        console.log('已包装原始的 updateGameState 函数');
    }
    
    // 拦截 fetch 请求
    const originalFetch = window.fetch;
    if (originalFetch) {
        window.fetch = function() {
            return originalFetch.apply(this, arguments)
                .then(response => {
                    // 检查是否是游戏状态请求
                    const url = arguments[0];
                    if (typeof url === 'string' && url.includes('/game_state/')) {
                        return response.clone().json().then(data => {
                            // 在数据返回时检查特殊动作
                            checkSpecialActions(data);
                            return response;
                        }).catch(() => response);
                    }
                    return response;
                });
        };
    }
    
    // 页面加载完成时清除可能的历史记录
    document.addEventListener('DOMContentLoaded', function() {
        // 如果当前是发现页面，清除特殊动作标记
        if (window.location.pathname.includes('/discover/')) {
            console.log('在发现页面，清除可能的历史记录');
            sessionStorage.removeItem('pending_discover_redirect');
        }
    });
    
})();