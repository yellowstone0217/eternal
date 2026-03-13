// camellia/spell-reveal.js（增强版，修复队列阻塞，增加详细日志）
const SpellReveal = (function() {
    let spellQueue = [];
    let isAnimating = false;

    const cardStyle = {
        container: `
            position: absolute;
            width: 100px;
            height: 140px;
            perspective: 1000px;
            z-index: 10000;
            pointer-events: none;
            transition: all 0.8s cubic-bezier(0.4, 0, 0.2, 1);
        `,
        cardInner: `
            position: relative;
            width: 100%;
            height: 100%;
            text-align: center;
            transition: transform 0.4s ease-out;
            transform-style: preserve-3d;
        `,
        cardFront: `
            position: absolute;
            width: 100%;
            height: 100%;
            backface-visibility: hidden;
            border-radius: 10px;
            overflow: hidden;
            box-shadow: 0 4px 8px rgba(0,0,0,0.3);
            transform: rotateY(180deg);
        `,
        cardBack: `
            position: absolute;
            width: 100%;
            height: 100%;
            backface-visibility: hidden;
            background: linear-gradient(45deg, #9b59b6, #3498db);
            border-radius: 10px;
            border: 2px solid #f1c40f;
            box-shadow: 0 4px 8px rgba(0,0,0,0.3);
            display: flex;
            align-items: center;
            justify-content: center;
        `
    };

    function showSpellReveal(spell) {
        console.log('🔮 showSpellReveal 被调用，数据:', spell);
        spellQueue.push({ ...spell, timestamp: Date.now() });
        if (!isAnimating) {
            processSpellQueue();
        }
    }

    function processSpellQueue() {
        console.log('processSpellQueue 被调用，队列长度:', spellQueue.length);
        if (spellQueue.length === 0) {
            isAnimating = false;
            console.log('队列为空，结束');
            return;
        }

        isAnimating = true;
        const spellData = spellQueue.shift();
        console.log('开始播放动画，剩余队列长度:', spellQueue.length);

        try {
            const enemyHand = document.getElementById('enemy-hand');
            if (!enemyHand) {
                throw new Error('找不到 enemy-hand 元素');
            }

            const enemyHandRect = enemyHand.getBoundingClientRect();
            const handCardCount = enemyHand.children.length;
            let startX, startY;

            if (handCardCount > 0) {
                const randomIndex = Math.floor(Math.random() * handCardCount);
                const handCard = enemyHand.children[randomIndex];
                const handCardRect = handCard.getBoundingClientRect();
                startX = handCardRect.left + handCardRect.width / 2 - 50;
                startY = handCardRect.top;
            } else {
                startX = enemyHandRect.left + enemyHandRect.width / 2 - 50;
                startY = enemyHandRect.top + enemyHandRect.height / 2 - 70;
            }

            const container = document.createElement('div');
            container.style.cssText = cardStyle.container;
            container.style.left = startX + 'px';
            container.style.top = startY + 'px';

            const cardInner = document.createElement('div');
            cardInner.style.cssText = cardStyle.cardInner;

            const cardBack = document.createElement('div');
            cardBack.style.cssText = cardStyle.cardBack;
            cardBack.innerHTML = '<span style="font-size: 40px; color: white; font-weight: bold;">?</span>';

            const cardFront = document.createElement('div');
            cardFront.style.cssText = cardStyle.cardFront;

            let imageUrl = spellData.image ? `/static/images/${spellData.image}` : '';
            const spellGradient = 'linear-gradient(135deg, #9b59b6, #8e44ad)';
            let effectsHtml = '';
            if (spellData.effect && spellData.effect.length > 0) {
                effectsHtml = '<div style="display:flex;gap:3px;margin-bottom:3px;justify-content:center;flex-wrap:wrap;">';
                spellData.effect.forEach(eff => {
                    if (!eff.startsWith('抽到时：')) {
                        effectsHtml += `<span style="background:rgba(241,196,15,0.3);border:1px solid #f1c40f;border-radius:8px;padding:2px 6px;font-size:9px;color:#f1c40f;">${eff}</span>`;
                    }
                });
                effectsHtml += '</div>';
            }

            cardFront.innerHTML = `
                <div style="position:relative;width:100%;height:100%;background:${spellGradient};border:2px solid #f1c40f;border-radius:10px;display:flex;flex-direction:column;">
                    <div style="position:absolute;top:5px;left:5px;background:#f39c12;color:white;width:25px;height:25px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:bold;font-size:14px;box-shadow:0 2px 5px rgba(0,0,0,0.3);z-index:2;">${spellData.cost || '?'}</div>
                    <div style="margin-top:30px;margin-left:5px;margin-right:5px;height:50px;background-image:url('${imageUrl}');background-size:cover;background-position:center;border-radius:5px;border:1px solid #f1c40f;background-color:#34495e;"></div>
                    <div style="margin-top:5px;text-align:center;font-size:12px;font-weight:bold;color:white;text-shadow:1px 1px 2px black;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;padding:0 5px;">${spellData.name || '未知法术'}</div>
                    <div style="margin-top:5px;text-align:center;">${effectsHtml}</div>
                    <div style="position:absolute;bottom:5px;left:5px;right:5px;display:flex;justify-content:center;font-size:10px;color:#ecf0f1;">法术牌</div>
                </div>
            `;

            cardInner.appendChild(cardBack);
            cardInner.appendChild(cardFront);
            container.appendChild(cardInner);
            document.body.appendChild(container);

            setTimeout(() => {
                cardInner.style.transform = 'rotateY(180deg)';
            }, 100);

            setTimeout(() => {
                const targetX = window.innerWidth / 2 - 200;
                const targetY = window.innerHeight * 0.4;
                container.style.transition = 'all 0.6s cubic-bezier(0.4, 0, 0.2, 1)';
                container.style.left = targetX + 'px';
                container.style.top = targetY + 'px';
                container.style.transform = 'scale(1.2)';
            }, 500);

            setTimeout(() => {
                container.style.transition = 'all 0.8s cubic-bezier(0.4, 0, 0.2, 1)';
                container.style.left = '-200px';
                container.style.top = startY - 80 + 'px';
                container.style.opacity = '0';
                container.style.transform = 'scale(0.8)';
            }, 1500);

            setTimeout(() => {
                if (container.parentNode) container.remove();
                isAnimating = false;
                console.log('动画结束，准备播放下一个');
                processSpellQueue();
            }, 2300);

            // 记录技能（如果存在）
            if (window.recordEnemySpell) {
                window.recordEnemySpell(spellData);
            }
        } catch (e) {
            console.error('动画执行出错:', e);
            isAnimating = false;
            processSpellQueue();
        }
    }

    return { showSpellReveal };
})();

if (typeof module !== 'undefined' && module.exports) {
    module.exports = SpellReveal;
} else {
    window.SpellReveal = SpellReveal;
}