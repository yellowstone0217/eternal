// attackAnimation.js - 攻击动画同步模块
(function() {
    // 确保 socket.io 已加载
    if (typeof io === 'undefined') {
        console.error('Socket.IO not loaded');
        return;
    }
    const socket = io();

    // 获取当前登录用户
    function getCurrentUser() {
        return sessionStorage.getItem('user') || '';
    }

    // 播放攻击动画
    function playAttackAnimation(attackerPlayer, attackerIndex, targetIndex) {
        const currentUser = getCurrentUser();
        if (!currentUser) return;

        // 确定攻击者所在容器（基于视角）
        const attackerContainer = (attackerPlayer === currentUser) 
            ? document.querySelector('#enemy-board')   // 攻击者是己方，在对手视角中位于敌方战场
            : document.querySelector('#player-board'); // 攻击者是对方，在己方战场
        if (!attackerContainer) return;
        const attackerCardContainer = attackerContainer.children[attackerIndex];
        if (!attackerCardContainer) return;
        const attackerCard = attackerCardContainer.querySelector('.card');
        if (!attackerCard) return;

        // 确定目标元素
        let targetElement;
        if (targetIndex === null || targetIndex === undefined) {
            // 攻击英雄
            targetElement = document.querySelector('.enemy-health-display');
        } else {
            // 攻击随从：目标容器与攻击者容器相反
            const targetContainer = (attackerPlayer === currentUser)
                ? document.querySelector('#player-board')   // 攻击者是己方，目标在敌方（即自己的战场）
                : document.querySelector('#enemy-board');   // 攻击者是对方，目标在敌方（即对手的战场）
            if (!targetContainer) return;
            const targetCardContainer = targetContainer.children[targetIndex];
            if (!targetCardContainer) return;
            targetElement = targetCardContainer.querySelector('.card');
        }
        if (!targetElement) return;

        // 添加高亮类触发动画
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

    // 创建子弹（复用原内联脚本逻辑）
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

    // 监听服务器广播的攻击动画事件
    socket.on('attack_animation', (data) => {
        // data: { attacker_index, target_index, attacker_player }
        playAttackAnimation(data.attacker_player, data.attacker_index, data.target_index);
    });

    console.log('Attack animation module loaded');
})();