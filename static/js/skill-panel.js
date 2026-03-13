// static/js/skill-panel.js
// 技能面板控制脚本 - 独立文件，确保点击事件正常工作

(function() {
    console.log('📌 技能面板脚本加载成功');
    
    // 等待 DOM 加载完成
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initSkillPanel);
    } else {
        // DOM 已经加载完成
        initSkillPanel();
    }
    
    function initSkillPanel() {
        console.log('初始化技能面板...');
        
        const toggleBtn = document.getElementById('skill-panel-toggle');
        const panel = document.getElementById('skill-panel');
        const closeBtn = document.getElementById('close-skill-panel');
        
        console.log('toggleBtn:', toggleBtn);
        console.log('panel:', panel);
        console.log('closeBtn:', closeBtn);
        
        if (!toggleBtn) {
            console.error('❌ 找不到三条杠按钮 (skill-panel-toggle)');
            // 尝试重新查找（可能动态加载）
            setTimeout(initSkillPanel, 1000);
            return;
        }
        
        if (!panel) {
            console.error('❌ 找不到技能面板 (skill-panel)');
            return;
        }
        
        // 移除所有已有的事件监听器（避免重复绑定）
        const newToggleBtn = toggleBtn.cloneNode(true);
        toggleBtn.parentNode.replaceChild(newToggleBtn, toggleBtn);
        
        // 重新获取元素
        const newBtn = document.getElementById('skill-panel-toggle');
        const newPanel = document.getElementById('skill-panel');
        const newCloseBtn = document.getElementById('close-skill-panel');
        
        if (!newBtn || !newPanel) {
            console.error('❌ 重新获取元素失败');
            return;
        }
        
        console.log('✅ 找到所有元素，绑定事件...');
        
        // 绑定三条杠点击事件
        newBtn.addEventListener('click', function(e) {
            e.stopPropagation();
            e.preventDefault();
            console.log('🔘 三条杠被点击');
            newPanel.classList.toggle('open');
            console.log('面板状态:', newPanel.classList.contains('open') ? '打开' : '关闭');
        });
        
        // 绑定关闭按钮点击事件
        if (newCloseBtn) {
            newCloseBtn.addEventListener('click', function(e) {
                e.stopPropagation();
                e.preventDefault();
                console.log('❌ 关闭按钮被点击');
                newPanel.classList.remove('open');
            });
        }
        
        // 点击面板外部关闭
        document.addEventListener('click', function(e) {
            if (newPanel && newPanel.classList.contains('open')) {
                if (!newPanel.contains(e.target) && !newBtn.contains(e.target)) {
                    console.log('点击外部，关闭面板');
                    newPanel.classList.remove('open');
                }
            }
        });
        
        // 防止面板内部点击事件冒泡
        newPanel.addEventListener('click', function(e) {
            e.stopPropagation();
        });
        
        console.log('✅ 技能面板事件绑定完成');
    }
})();