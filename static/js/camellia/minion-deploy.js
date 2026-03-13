// static/js/camellia/minion-deploy.js - 随从部署从天而降动画

(function() {
    console.log('🐣 随从部署动画模块加载（从天而降）...');

    // 动画队列，避免同时多个动画冲突
    let animationQueue = [];
    let isAnimating = false;

    // 处理随从部署动画
    window.playMinionDeployAnimation = function(minionData, boardIndex) {
        console.log('🎬 播放随从部署动画:', minionData, '位置:', boardIndex);
        
        // 添加到队列
        animationQueue.push({
            minionData: minionData,
            boardIndex: boardIndex
        });
        
        // 开始处理队列
        processAnimationQueue();
    };

    // 处理动画队列
    function processAnimationQueue() {
        if (isAnimating || animationQueue.length === 0) {
            return;
        }
        
        isAnimating = true;
        const nextAnimation = animationQueue.shift();
        executeDeployAnimation(nextAnimation.minionData, nextAnimation.boardIndex);
    }

    // 执行部署动画（从天而降）
    function executeDeployAnimation(minionData, boardIndex) {
        const enemyBoard = document.getElementById('enemy-board');
        if (!enemyBoard) {
            console.error('找不到敌方战场区域');
            isAnimating = false;
            processAnimationQueue();
            return;
        }

        // 获取战场区域的中心位置作为动画起始点
        const boardRect = enemyBoard.getBoundingClientRect();
        const cardWidth = 100;
        const cardHeight = 140;
        
        // 目标位置：战场上的对应位置
        let targetX, targetY;
        
        if (boardIndex !== undefined && boardIndex !== null && enemyBoard.children[boardIndex]) {
            // 如果指定了位置且该位置已有卡片，就在那张卡片的位置播放动画
            const existingCard = enemyBoard.children[boardIndex];
            const rect = existingCard.getBoundingClientRect();
            targetX = rect.left;
            targetY = rect.top;
        } else {
            // 计算新卡片应该放置的位置
            const currentCards = enemyBoard.children.length;
            
            // 计算总宽度和起始位置
            const totalWidth = currentCards * (cardWidth + 15); // 15px 间距
            const startX_board = boardRect.left + (boardRect.width - totalWidth) / 2;
            
            targetX = startX_board + currentCards * (cardWidth + 15);
            targetY = boardRect.top + (boardRect.height - cardHeight) / 2;
        }

        // 创建动画容器 - 从屏幕上方开始
        const animContainer = document.createElement('div');
        animContainer.className = 'minion-deploy-animation';
        animContainer.style.position = 'fixed';
        animContainer.style.left = targetX + 'px';  // X坐标直接定在目标位置
        animContainer.style.top = '-200px';          // 从屏幕上方外面开始
        animContainer.style.width = cardWidth + 'px';
        animContainer.style.height = cardHeight + 'px';
        animContainer.style.zIndex = '10000';
        animContainer.style.pointerEvents = 'none';
        animContainer.style.transition = 'top 0.4s cubic-bezier(0.3, 0.8, 0.2, 1.2)'; // 弹性下落效果
        document.body.appendChild(animContainer);

        // 创建卡片（直接显示正面，不需要翻面）
        const card = document.createElement('div');
        card.className = 'card';
        card.style.width = '100%';
        card.style.height = '100%';
        card.style.background = 'linear-gradient(135deg, #2ecc71, #27ae60)';
        card.style.borderRadius = '10px';
        card.style.border = '2px solid #f1c40f';
        card.style.padding = '8px';
        card.style.boxSizing = 'border-box';
        card.style.display = 'flex';
        card.style.flexDirection = 'column';
        card.style.justifyContent = 'space-between';
        card.style.boxShadow = '0 5px 15px rgba(0, 0, 0, 0.5)';
        
        // 填充卡面内容
        const imageUrl = minionData.image ? 
            (minionData.image.startsWith('/') ? minionData.image : '/static/images/' + minionData.image) 
            : '/static/images/default.jpg';
        const attack = minionData.attack || 0;
        const health = minionData.health || 1;
        const cost = minionData.cost || 1;
        const name = minionData.name || '未知随从';

        card.innerHTML = `
            <div style="position: absolute; top: 5px; left: 5px; background: #f39c12; color: white; width: 25px; height: 25px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: bold; font-size: 14px; border: 1px solid white; z-index: 2;">${cost}</div>
            <div style="width: 100%; height: 60px; background-size: cover; background-position: center; border-radius: 5px; background-color: #34495e; background-image: url('${imageUrl}');"></div>
            <div style="font-size: 12px; font-weight: bold; text-align: center; color: white; text-shadow: 1px 1px 2px black; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${name}</div>
            <div style="display: flex; justify-content: space-between; font-size: 14px; font-weight: bold;">
                <span style="color: #e74c3c;">⚔️ ${attack}</span>
                <span style="color: #2ecc71;">❤️ ${health}</span>
            </div>
        `;
        
        animContainer.appendChild(card);

        // 添加一点旋转效果
        card.style.transform = 'rotate(5deg)';
        
        // 开始下落
        setTimeout(() => {
            animContainer.style.top = targetY + 'px';
            card.style.transform = 'rotate(0deg)';
        }, 50);

        // 落地时添加一点弹跳效果
        setTimeout(() => {
            animContainer.style.transition = 'top 0.15s ease-out';
            animContainer.style.top = (targetY - 10) + 'px'; // 轻微弹起
        }, 450);

        setTimeout(() => {
            animContainer.style.top = targetY + 'px'; // 落回原位
        }, 600);

        // 动画结束后移除
        setTimeout(() => {
            animContainer.remove();
            
            // 动画完成，处理下一个
            isAnimating = false;
            processAnimationQueue();
        }, 750);
    }

    // 监听游戏状态更新
    function observeGameState() {
        // 保存原始的 fetch
        const originalFetch = window.fetch;
        
        window.fetch = function() {
            const url = arguments[0];
            const options = arguments[1] || {};
            
            return originalFetch.apply(this, arguments).then(response => {
                // 检查是否是游戏状态请求
                if (typeof url === 'string' && url.includes('/game_state/')) {
                    response.clone().json().then(data => {
                        // 检查是否有敌方随从部署信息
                        if (data.enemy_minion_deployed) {
                            console.log('🎯 检测到敌方随从部署:', data.enemy_minion_deployed);
                            window.playMinionDeployAnimation(
                                data.enemy_minion_deployed,
                                data.enemy_minion_deployed.position
                            );
                        }
                    }).catch(() => {});
                }
                return response;
            });
        };
        
        console.log('👀 随从部署监控已启动');
    }

    // 页面加载完成后初始化
    document.addEventListener('DOMContentLoaded', function() {
        observeGameState();
    });

})();