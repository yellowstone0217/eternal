// deck-indicator.js
(function() {
    'use strict';

    // 更新牌库计数
    function updateDeckCounts(data) {
        const playerDeckCount = data.player_deck_count || 0;
        const enemyDeckCount = data.enemy_deck_count || 0;
        const playerEl = document.getElementById('player-deck-count');
        const enemyEl = document.getElementById('enemy-deck-count');
        if (playerEl) playerEl.textContent = playerDeckCount;
        if (enemyEl) enemyEl.textContent = enemyDeckCount;
    }

    // 点击事件
    function bindDeckClicks() {
        const enemyDeck = document.querySelector('.enemy-deck');
        const playerDeck = document.querySelector('.player-deck');
        if (enemyDeck) {
            enemyDeck.addEventListener('click', function() {
                const count = document.getElementById('enemy-deck-count').textContent;
                alert(`敌方牌库剩余 ${count} 张牌`);
            });
        }
        if (playerDeck) {
            playerDeck.addEventListener('click', function() {
                const count = document.getElementById('player-deck-count').textContent;
                alert(`我方牌库剩余 ${count} 张牌`);
            });
        }
    }

    // 拦截fetch，自动更新
    function setupFetchInterceptor() {
        const originalFetch = window.fetch;
        window.fetch = function() {
            return originalFetch.apply(this, arguments).then(response => {
                const url = arguments[0];
                if (typeof url === 'string' && url.includes('/game_state/')) {
                    const cloned = response.clone();
                    cloned.json().then(data => {
                        if (data && !data.error) {
                            updateDeckCounts(data);
                        }
                    }).catch(() => {});
                }
                return response;
            });
        };
    }

    // 如果游戏状态已存在，也可以设置定时器兜底
    function startPolling() {
        setInterval(() => {
            if (window.gameStateData) {
                updateDeckCounts(window.gameStateData);
            }
        }, 2000);
    }

    // 初始化
    function init() {
        bindDeckClicks();
        setupFetchInterceptor();
        startPolling(); // 可选，作为备用
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();