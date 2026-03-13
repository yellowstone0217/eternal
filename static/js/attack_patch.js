// attack_patch.js - 攻击动画同步补丁（自动注入）
(function() {
    console.log('攻击动画补丁加载中...');
    
    // 确保 socket.io 已加载
    if (typeof io === 'undefined') {
        console.error('Socket.IO 未加载，等待重试...');
        setTimeout(arguments.callee, 500);
        return;
    }
    
    const socket = io();
    
    // 获取当前用户
    function getCurrentUser() {
        return sessionStorage.getItem('user') || '';
    }
    
    // 获取游戏ID
    function getGameId() {
        return sessionStorage.getItem('game_id') || 
               (typeof window.gameId !== 'undefined' ? window.gameId : null);
    }
    
    // 播放攻击动画
    function playAttackAnimation(data) {
        const currentUser = getCurrentUser();
        
        console.log('收到攻击动画:', data, '当前用户:', currentUser);
        
        // 确定攻击者位置
        let attackerContainer;
        if (data.attacker_player === currentUser) {
            // 攻击者是己方，在我的视角中攻击者在敌方战场
            attackerContainer = document.querySelector('#enemy-board');
        } else {
            // 攻击者是敌方，在我的视角中攻击者在己方战场
            attackerContainer = document.querySelector('#player-board');
        }
        
        if (!attackerContainer) {
            console.error('找不到攻击者容器');
            return;
        }
        
        const attackerCardContainer = attackerContainer.children[data.attacker_index];
        if (!attackerCardContainer) {
            console.error('找不到攻击者卡牌');
            return;
        }
        
        const attackerCard = attackerCardContainer.querySelector('.card');
        if (!attackerCard) {
            console.error('找不到攻击者卡牌元素');
            return;
        }
        
        // 确定目标位置
        let targetElement;
        if (data.target_index === null || data.target_index === undefined) {
            // 攻击英雄
            targetElement = document.querySelector('.enemy-health-display');
        } else {
            // 攻击随从
            const targetContainer = (data.attacker_player === currentUser)
                ? document.querySelector('#player-board')   // 攻击者是己方，目标在敌方（己方战场）
                : document.querySelector('#enemy-board');   // 攻击者是敌方，目标在敌方（对手战场）
            
            if (!targetContainer) {
                console.error('找不到目标容器');
                return;
            }
            
            const targetCardContainer = targetContainer.children[data.target_index];
            if (!targetCardContainer) {
                console.error('找不到目标卡牌');
                return;
            }
            
            targetElement = targetCardContainer.querySelector('.card');
        }
        
        if (!targetElement) {
            console.error('找不到目标元素');
            return;
        }
        
        // 添加动画类
        attackerCard.classList.add('attacking');
        targetElement.classList.add('targeted');
        
        // 创建子弹特效
        createBullets(attackerCard, targetElement);
        
        // 动画结束后移除类
        setTimeout(() => {
            attackerCard.classList.remove('attacking');
            targetElement.classList.remove('targeted');
        }, 400);
    }
    
    // 创建子弹特效
    function createBullets(attackerEl, targetEl) {
        const bulletContainer = document.getElementById('attack-bullets');
        if (!bulletContainer) return;
        
        const attackerRect = attackerEl.getBoundingClientRect();
        const targetRect = targetEl.getBoundingClientRect();
        
        const startX = attackerRect.left + attackerRect.width / 2;
        const startY = attackerRect.top + attackerRect.height / 2;
        const endX = targetRect.left + targetRect.width / 2;
        const endY = targetRect.top + targetRect.height / 2;
        
        const angle = Math.atan2(endY - startY, endX - startX);
        const bulletCount = 4 + Math.floor(Math.random() * 2);
        
        for (let i = 0; i < bulletCount; i++) {
            const offsetX = (Math.random() - 0.5) * 40;
            const offsetY = (Math.random() - 0.5) * 40;
            const bulletStartX = startX + offsetX;
            const bulletStartY = startY + offsetY;
            const bulletEndX = endX + (Math.random() - 0.5) * 30;
            const bulletEndY = endY + (Math.random() - 0.5) * 30;
            
            const bullet = document.createElement('div');
            bullet.className = 'bullet';
            bullet.style.left = bulletStartX + 'px';
            bullet.style.top = bulletStartY + 'px';
            bullet.style.transform = `rotate(${angle}rad)`;
            bullet.style.setProperty('--target-x', (bulletEndX - bulletStartX) + 'px');
            bullet.style.setProperty('--target-y', (bulletEndY - bulletStartY) + 'px');
            bullet.style.animationDelay = (i * 0.05) + 's';
            
            bulletContainer.appendChild(bullet);
            
            setTimeout(() => {
                if (bullet.parentNode) bullet.remove();
            }, 350 + i * 50);
        }
    }
    
    // 监听攻击动画事件
    socket.on('attack_animation', playAttackAnimation);
    
    // 页面加载时自动请求加入房间
    function requestJoinRoom() {
        const gameId = getGameId();
        if (gameId) {
            // 通过连接事件自动加入，不需要额外请求
            console.log('游戏ID:', gameId, '将在连接时自动加入房间');
        }
    }
    
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', requestJoinRoom);
    } else {
        requestJoinRoom();
    }
    
    console.log('攻击动画补丁加载完成');
})();
