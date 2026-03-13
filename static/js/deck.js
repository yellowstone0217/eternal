// deck.js - 组卡界面完整逻辑（含搜索、导入导出、合法性验证）
(function() {
    'use strict';

    // ========== 从window对象获取后端传递的数据 ==========
    const userCards = window.USER_CARDS || {};
    const cardDetails = window.CARD_DETAILS || {};
    const DECK_SIZE = window.DECK_SIZE || 40;
    const userDecks = window.USER_DECKS || [];

    // ========== 常量定义 ==========
    const QUALITY_LIMIT = {
        '普通': 4,
        '限定': 3,
        '特殊': 2,
        '精英': 1
    };

    // ========== 状态变量 ==========
    let currentDeck = [];              // 当前卡组中的卡牌列表
    let currentDeckName = '';           // 当前选中的卡组名称
    let currentSelectedCard = null;     // 当前选中的卡牌（用于模态框）

    // ========== DOM 元素 ==========
    const deckNameInput = document.getElementById('deck-name');
    const deckSelect = document.getElementById('deck-select');
    const loadBtn = document.getElementById('load-deck-btn');
    const deleteBtn = document.getElementById('delete-deck-btn');
    const cardGrid = document.getElementById('card-grid');
    const deckList = document.getElementById('deck-list');
    const deckCountSpan = document.getElementById('deck-count');
    const deckStatsDiv = document.getElementById('deck-stats');
    const messageDiv = document.getElementById('message');
    const saveBtn = document.getElementById('save-deck-btn');
    const deckSizeSpan = document.getElementById('deck-size');
    const clearBtn = document.getElementById('clear-deck-btn');

    // ========== 模态框元素 ==========
    const modal = document.getElementById('card-modal');
    const modalClose = document.querySelector('.close');
    const modalCardName = document.getElementById('modal-card-name');
    const modalCardCost = document.getElementById('modal-card-cost');
    const modalCardQuality = document.getElementById('modal-card-quality');
    const modalCardAttack = document.getElementById('modal-card-attack');
    const modalCardHealth = document.getElementById('modal-card-health');
    const modalCardDescription = document.getElementById('modal-card-description');
    const modalCardEffects = document.getElementById('modal-card-effects');
    const modalCardOwned = document.getElementById('modal-card-owned');
    const modalAddBtn = document.getElementById('modal-add-btn');
    const modalCardImage = document.getElementById('modal-card-image');

    // ========== 初始化 ==========
    function init() {
        // 更新显示的卡组上限
        if (deckSizeSpan) {
            deckSizeSpan.textContent = DECK_SIZE;
        }

        // 填充下拉框选项
        updateDeckSelectOptions();

        renderAvailableCards();
        updateDeckUI();
        initEventListeners();
        
        // 添加导入模态框
        addImportModal();
    }

    // ========== 更新下拉框选项 ==========
    function updateDeckSelectOptions() {
        if (!deckSelect) return;
        
        // 清空现有选项（保留第一个提示选项）
        while (deckSelect.options.length > 1) {
            deckSelect.remove(1);
        }
        
        // 添加用户卡组
        if (userDecks.length > 0) {
            userDecks.forEach(deck => {
                const option = document.createElement('option');
                option.value = deck.name;
                option.textContent = deck.name;
                deckSelect.appendChild(option);
            });
        }
    }

    // ========== 事件监听初始化 ==========
    function initEventListeners() {
        // 下拉框变化时启用/禁用按钮
        deckSelect.addEventListener('change', function() {
            const val = this.value;
            loadBtn.disabled = !val;
            deleteBtn.disabled = !val;
            if (val) {
                deckNameInput.value = val; // 自动填充名称
            } else {
                deckNameInput.value = '';
            }
        });

        // 加载按钮点击
        loadBtn.addEventListener('click', function() {
            const deckName = deckSelect.value;
            if (deckName) {
                loadDeck(deckName);
            }
        });

        // 删除按钮点击
        deleteBtn.addEventListener('click', function() {
            const deckName = deckSelect.value;
            if (deckName) {
                showDeleteConfirm(deckName);
            }
        });

        // 清空按钮点击
        if (clearBtn) {
            clearBtn.addEventListener('click', function() {
                if (currentDeck.length > 0) {
                    if (confirm('确定要清空当前卡组吗？')) {
                        currentDeck = [];
                        currentDeckName = '';
                        deckNameInput.value = '';
                        updateDeckUI();
                        renderAvailableCards();
                        showMessage('卡组已清空', 'info');
                    }
                }
            });
        }

        // 保存按钮点击
        saveBtn.addEventListener('click', saveDeck);

        // ========== 新增：搜索和导入导出事件 ==========
        
        // 搜索框事件
        const searchInput = document.getElementById('card-search');
        const clearSearchBtn = document.getElementById('clear-search');

        if (searchInput) {
            searchInput.addEventListener('input', function() {
                filterCards(this.value);
                clearSearchBtn.style.display = this.value ? 'block' : 'none';
            });
        }

        if (clearSearchBtn) {
            clearSearchBtn.addEventListener('click', function() {
                searchInput.value = '';
                filterCards('');
                clearSearchBtn.style.display = 'none';
            });
        }

        // 导出按钮
        const exportBtn = document.getElementById('export-deck-btn');
        if (exportBtn) {
            exportBtn.addEventListener('click', exportDeck);
        }

        // 导入按钮
        const importBtn = document.getElementById('import-deck-btn');
        if (importBtn) {
            importBtn.addEventListener('click', showImportModal);
        }

        // 复制代码按钮
        const copyCodeBtn = document.getElementById('copy-deck-code-btn');
        if (copyCodeBtn) {
            copyCodeBtn.addEventListener('click', copyDeckCode);
        }

        // ========== 原有模态框事件 ==========
        
        // 模态框关闭事件
        modalClose.addEventListener('click', () => {
            modal.style.display = 'none';
        });

        window.addEventListener('click', (e) => {
            if (e.target === modal) {
                modal.style.display = 'none';
            }
        });

        // 模态框添加按钮
        modalAddBtn.addEventListener('click', addCardFromModal);

        // ESC键关闭模态框
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && modal.style.display === 'block') {
                modal.style.display = 'none';
            }
        });
    }

    // ========== 显示删除确认 ==========
    function showDeleteConfirm(deckName) {
        if (confirm(`确定要删除卡组 "${deckName}" 吗？此操作不可恢复！`)) {
            deleteDeck(deckName);
        }
    }

    // ========== 删除卡组 ==========
    function deleteDeck(deckName) {
        showMessage('删除中...', 'info');
        
        fetch('/delete_deck', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ deck_name: deckName })
        })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                showMessage('卡组删除成功！', 'info');
                
                // 从下拉框中移除
                for (let i = deckSelect.options.length - 1; i >= 0; i--) {
                    if (deckSelect.options[i].value === deckName) {
                        deckSelect.remove(i);
                        break;
                    }
                }
                
                // 如果当前卡组是被删除的卡组，清空当前卡组
                if (currentDeckName === deckName) {
                    currentDeck = [];
                    currentDeckName = '';
                    deckNameInput.value = '';
                    updateDeckUI();
                    renderAvailableCards();
                }
                
                // 重置下拉框
                deckSelect.value = '';
                loadBtn.disabled = true;
                deleteBtn.disabled = true;
                
                // 刷新页面以更新用户卡组列表
                setTimeout(() => location.reload(), 1500);
            } else {
                showMessage('删除失败: ' + data.error, 'error');
            }
        })
        .catch(err => {
            showMessage('网络错误', 'error');
            console.error(err);
        });
    }

    // ========== 渲染可用卡牌（带搜索高亮） ==========
    function renderAvailableCards() {
        let html = '';
        
        // 将卡牌按费用排序
        const sortedCardNames = Object.keys(cardDetails).sort((a, b) => {
            const costA = cardDetails[a].cost || 0;
            const costB = cardDetails[b].cost || 0;
            return costA - costB || a.localeCompare(b);
        });

        for (let cardName of sortedCardNames) {
            const detail = cardDetails[cardName];
            if (!detail) continue;
            
            const owned = userCards[cardName] || 0;
            const selectedCount = currentDeck.filter(c => c === cardName).length;
            const quality = detail.quality || '普通';
            const maxPerDeck = QUALITY_LIMIT[quality] || 4;
            
            // 严格检查是否可以添加
            const canAdd = (selectedCount < maxPerDeck) && 
                           (selectedCount < owned) && 
                           (currentDeck.length < DECK_SIZE);
            
            const insufficient = owned === 0;

            // 构建效果标签
            let effectHtml = '';
            if (detail.effect) {
                if (Array.isArray(detail.effect)) {
                    detail.effect.forEach(eff => {
                        effectHtml += `<span class="effect-tag">${eff}</span>`;
                    });
                } else if (typeof detail.effect === 'string') {
                    effectHtml += `<span class="effect-tag">${detail.effect}</span>`;
                }
            }

            // 根据品质设置边框颜色
            const qualityClass = `quality-${quality}`;

            // 添加隐藏卡标记（但不禁用，因为可以通过指令获取）
            const hiddenMark = detail.hidden ? '<span class="hidden-mark" title="隐藏卡（可通过指令获取）">👻</span>' : '';

            html += `
                <div class="card-item ${qualityClass} ${owned === 0 ? 'insufficient' : ''}" data-name="${cardName}">
                    <div class="card-cost">${detail.cost !== undefined ? detail.cost : '?'}</div>
                    <div class="card-name" title="${cardName}">${cardName} ${hiddenMark}</div>
                    <div class="card-stats">
                        <span class="attack">⚔️${detail.attack !== undefined ? detail.attack : '-'}</span>
                        <span class="health">❤️${detail.health !== undefined ? detail.health : '-'}</span>
                    </div>
                    ${effectHtml ? `<div class="effect-tags">${effectHtml}</div>` : ''}
                    <div class="card-footer">
                        <span class="owned">拥有: ${owned}</span>
                        <span class="selected">已选: ${selectedCount}</span>
                        <button class="add-btn" 
                            ${!canAdd ? 'disabled' : ''} 
                            data-name="${cardName}"
                            ${owned === 0 ? 'disabled' : ''}>+</button>
                    </div>
                </div>
            `;
        }
        
        cardGrid.innerHTML = html;

        // 为所有卡牌添加点击事件
        document.querySelectorAll('.card-item').forEach(cardEl => {
            cardEl.addEventListener('click', (e) => {
                if (e.target.classList.contains('add-btn')) {
                    return;
                }
                const cardName = cardEl.dataset.name;
                showCardDetails(cardName);
            });
        });

        // 为所有添加按钮绑定事件
        document.querySelectorAll('.add-btn:not([disabled])').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const cardName = btn.dataset.name;
                addCardToDeck(cardName);
                
                // 添加高亮效果
                const cardEl = btn.closest('.card-item');
                cardEl.classList.add('highlight-card');
                setTimeout(() => {
                    cardEl.classList.remove('highlight-card');
                }, 1000);
            });
        });
        
        // 重新应用搜索过滤
        const searchInput = document.getElementById('card-search');
        if (searchInput && searchInput.value) {
            filterCards(searchInput.value);
        }
    }

    // ========== 显示卡牌详情模态框 ==========
    function showCardDetails(cardName) {
        const detail = cardDetails[cardName];
        if (!detail) return;

        currentSelectedCard = cardName;

        // 基本信息
        modalCardName.textContent = cardName;
        modalCardCost.textContent = detail.cost !== undefined ? detail.cost : '?';
        modalCardQuality.textContent = detail.quality || '普通';
        modalCardAttack.textContent = detail.attack !== undefined ? detail.attack : '-';
        modalCardHealth.textContent = detail.health !== undefined ? detail.health : '-';
        modalCardDescription.textContent = detail.description || '暂无描述';

        // 拥有数量
        const owned = userCards[cardName] || 0;
        const selectedCount = currentDeck.filter(c => c === cardName).length;
        modalCardOwned.textContent = `拥有: ${owned}  已选: ${selectedCount}`;

        // 效果标签
        let effectsHtml = '';
        if (detail.effect) {
            if (Array.isArray(detail.effect)) {
                detail.effect.forEach(eff => {
                    effectsHtml += `<span class="modal-effect-tag">${eff}</span>`;
                });
            } else if (typeof detail.effect === 'string') {
                effectsHtml += `<span class="modal-effect-tag">${detail.effect}</span>`;
            }
        }
        modalCardEffects.innerHTML = effectsHtml || '<span class="modal-effect-tag">无效果</span>';

        // 设置添加按钮状态
        const quality = detail.quality || '普通';
        const maxPerDeck = QUALITY_LIMIT[quality] || 4;
        const canAdd = (selectedCount < maxPerDeck) && 
                       (selectedCount < owned) && 
                       (currentDeck.length < DECK_SIZE);
        
        modalAddBtn.disabled = !canAdd;
        modalAddBtn.textContent = canAdd ? '➕ 加入卡组' : '❌ 无法加入';

        // 设置卡片图片
        setCardImage(detail, cardName);

        // 显示模态框
        modal.style.display = 'block';
    }

    // ========== 设置卡片图片 ==========
    function setCardImage(detail, cardName) {
        // 清除之前的内容
        modalCardImage.textContent = '';
        modalCardImage.style.display = 'flex';
        modalCardImage.style.alignItems = 'center';
        modalCardImage.style.justifyContent = 'center';
        
        if (detail.image) {
            // 构建图片URL
            let imageUrl = detail.image;
            
            // 检查图片路径是否已经是完整URL
            if (!imageUrl.startsWith('http') && !imageUrl.startsWith('/')) {
                // 相对路径，加上静态文件目录
                imageUrl = `/static/images/${imageUrl}`;
            }
            
            // 设置背景图片
            modalCardImage.style.backgroundImage = `url('${imageUrl}')`;
            modalCardImage.style.backgroundSize = 'contain';
            modalCardImage.style.backgroundPosition = 'center';
            modalCardImage.style.backgroundRepeat = 'no-repeat';
            modalCardImage.style.backgroundColor = '#34495e';
            
            // 添加图片加载错误处理
            const img = new Image();
            img.onload = function() {
                // 图片加载成功，保持原样
            };
            img.onerror = function() {
                // 图片加载失败，使用渐变色
                useGradientBackground(detail, cardName);
            };
            img.src = imageUrl;
        } else {
            // 没有图片字段，使用渐变色
            useGradientBackground(detail, cardName);
        }
    }

    // ========== 使用渐变色背景 ==========
    function useGradientBackground(detail, cardName) {
        // 根据品质生成渐变色背景
        const qualityColors = {
            '普通': 'linear-gradient(135deg, #95a5a6, #7f8c8d)',
            '限定': 'linear-gradient(135deg, #f1c40f, #e67e22)',
            '特殊': 'linear-gradient(135deg, #9b59b6, #8e44ad)',
            '精英': 'linear-gradient(135deg, #e74c3c, #c0392b)'
        };
        
        modalCardImage.style.backgroundImage = qualityColors[detail.quality] || 'linear-gradient(135deg, #3498db, #2980b9)';
        modalCardImage.style.backgroundSize = 'cover';
        modalCardImage.style.backgroundPosition = 'center';
        
        // 在背景上显示卡牌名称首字母作为占位符
        modalCardImage.style.fontSize = '48px';
        modalCardImage.style.fontWeight = 'bold';
        modalCardImage.style.color = 'rgba(255,255,255,0.3)';
        modalCardImage.textContent = cardName.charAt(0).toUpperCase();
    }

    // ========== 从模态框添加卡牌 ==========
    function addCardFromModal() {
        if (!currentSelectedCard) return;
        addCardToDeck(currentSelectedCard);
        
        // 更新模态框中的按钮状态
        const selectedCount = currentDeck.filter(c => c === currentSelectedCard).length;
        const detail = cardDetails[currentSelectedCard];
        const owned = userCards[currentSelectedCard] || 0;
        const quality = detail.quality || '普通';
        const maxPerDeck = QUALITY_LIMIT[quality] || 4;
        const canAdd = (selectedCount < maxPerDeck) && 
                       (selectedCount < owned) && 
                       (currentDeck.length < DECK_SIZE);
        
        modalAddBtn.disabled = !canAdd;
        modalAddBtn.textContent = canAdd ? '➕ 加入卡组' : '❌ 无法加入';
        modalCardOwned.textContent = `拥有: ${owned}  已选: ${selectedCount}`;
    }

    // ========== 添加卡牌到卡组 ==========
    function addCardToDeck(cardName) {
        // 严格检查卡组是否已满
        if (currentDeck.length >= DECK_SIZE) {
            showMessage(`卡组已满 (最多${DECK_SIZE}张)`, 'error');
            return;
        }
        
        const detail = cardDetails[cardName];
        if (!detail) return;
        
        const quality = detail.quality || '普通';
        const maxPerDeck = QUALITY_LIMIT[quality] || 4;
        const selectedCount = currentDeck.filter(c => c === cardName).length;
        const owned = userCards[cardName] || 0;

        // 检查品质上限
        if (selectedCount >= maxPerDeck) {
            showMessage(`已达品质上限 (最多${maxPerDeck}张)`, 'warning');
            return;
        }
        
        // 检查拥有数量
        if (selectedCount >= owned) {
            showMessage('你没有更多这张卡了', 'warning');
            return;
        }

        // 再次检查卡组上限（防止在异步操作中卡组被填满）
        if (currentDeck.length >= DECK_SIZE) {
            showMessage(`卡组已满 (最多${DECK_SIZE}张)`, 'error');
            return;
        }

        // 添加到卡组
        currentDeck.push(cardName);
        
        // 更新UI
        updateDeckUI();
        renderAvailableCards();
        showMessage(`已添加: ${cardName}`, 'info');
    }

    // ========== 从卡组移除卡牌 ==========
    function removeFromDeck(index) {
        if (index < 0 || index >= currentDeck.length) return;
        
        const removedCard = currentDeck[index];
        currentDeck.splice(index, 1);
        updateDeckUI();
        renderAvailableCards();
        showMessage(`已移除: ${removedCard}`, 'info');
    }

    // ========== 更新卡组列表UI ==========
    function updateDeckUI() {
        // 按名称排序
        const sorted = [...currentDeck].sort();
        let html = '';
        
        // 统计每张卡的数量
        const countMap = {};
        sorted.forEach(card => {
            countMap[card] = (countMap[card] || 0) + 1;
        });
        
        // 合并显示相同卡牌
        const uniqueCards = [...new Set(sorted)];
        for (let card of uniqueCards) {
            const count = countMap[card];
            // 找到第一个出现的索引用于移除
            const firstIndex = currentDeck.findIndex(c => c === card);
            
            html += `
                <li onclick="window.showCardDetailsFromList('${card.replace(/'/g, "\\'")}')">
                    <span class="deck-card-name">${card} <span style="color:#f1c40f;">x${count}</span></span>
                    <button class="remove-btn" onclick="event.stopPropagation(); window.removeDeckCard(${firstIndex})">✕</button>
                </li>
            `;
        }
        
        deckList.innerHTML = html;
        deckCountSpan.innerText = currentDeck.length;

        // 如果卡组已满，显示红色提示
        if (currentDeck.length >= DECK_SIZE) {
            deckCountSpan.style.color = '#e74c3c';
            deckCountSpan.style.fontWeight = 'bold';
        } else {
            deckCountSpan.style.color = '';
            deckCountSpan.style.fontWeight = '';
        }

        // 更新统计信息
        updateStats();
    }

    // ========== 更新卡组统计 ==========
    function updateStats() {
        const totalCards = currentDeck.length;
        let totalCost = 0;
        let qualityCount = { '普通': 0, '限定': 0, '特殊': 0, '精英': 0 };
        let typeCount = { 'minion': 0, 'spell': 0 };
        
        currentDeck.forEach(card => {
            const detail = cardDetails[card];
            if (detail) {
                totalCost += detail.cost || 0;
                const quality = detail.quality || '普通';
                qualityCount[quality] = (qualityCount[quality] || 0) + 1;
                
                const type = detail.type || 'minion';
                typeCount[type] = (typeCount[type] || 0) + 1;
            }
        });
        
        const avgCost = totalCards ? (totalCost / totalCards).toFixed(1) : 0;
        
        // 显示卡组状态，如果已满用红色提示
        const statusColor = totalCards >= DECK_SIZE ? 'color: #e74c3c; font-weight: bold;' : '';
        let statsHtml = `<span style="${statusColor}">总卡牌: ${totalCards}/${DECK_SIZE}</span> | 平均费用: ${avgCost}<br>`;
        statsHtml += `📊 品质: `;
        for (let [q, count] of Object.entries(qualityCount)) {
            if (count > 0) {
                statsHtml += `${q}:${count} `;
            }
        }
        statsHtml += `<br>🎴 类型: 单位:${typeCount.minion || 0} 指令:${typeCount.spell || 0}`;
        
        deckStatsDiv.innerHTML = statsHtml;
    }

    // ========== 显示消息 ==========
    function showMessage(msg, type = 'info') {
        messageDiv.innerText = msg;
        messageDiv.className = `message ${type}`;
        
        // 3秒后自动清除
        setTimeout(() => {
            if (messageDiv.innerText === msg) {
                messageDiv.innerText = '';
            }
        }, 3000);
    }

    // ========== 加载卡组 ==========
    function loadDeck(deckName) {
        showMessage('加载中...', 'info');
        
        fetch(`/get_deck/${encodeURIComponent(deckName)}`)
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    currentDeck = data.cards || [];
                    
                    // 验证合法性
                    const invalidCards = [];
                    const tempDeck = [];
                    
                    for (let card of currentDeck) {
                        if (!cardDetails[card]) {
                            invalidCards.push(card);
                            continue;
                        }
                        
                        const owned = userCards[card] || 0;
                        const quality = cardDetails[card].quality || '普通';
                        const limit = QUALITY_LIMIT[quality] || 4;
                        const countInDeck = tempDeck.filter(c => c === card).length + 1;
                        
                        if (countInDeck > limit) {
                            invalidCards.push(card + '(超限)');
                            continue;
                        }
                        
                        if (countInDeck > owned) {
                            invalidCards.push(card + '(不足)');
                            continue;
                        }
                        
                        tempDeck.push(card);
                    }
                    
                    if (invalidCards.length > 0) {
                        showMessage('卡组中存在非法卡牌: ' + invalidCards.join(', '), 'warning');
                        currentDeck = tempDeck;
                    } else {
                        showMessage('卡组加载成功', 'info');
                    }
                    
                    deckNameInput.value = deckName;
                    currentDeckName = deckName;
                    updateDeckUI();
                    renderAvailableCards();
                } else {
                    showMessage('加载失败: ' + data.error, 'error');
                }
            })
            .catch(err => {
                showMessage('网络错误', 'error');
                console.error(err);
            });
    }

    // ========== 保存卡组 ==========
    function saveDeck() {
        const name = deckNameInput.value.trim();
        
        if (!name) {
            showMessage('请输入卡组名称', 'warning');
            return;
        }
        
        if (currentDeck.length === 0) {
            showMessage('卡组不能为空', 'warning');
            return;
        }
        
        if (currentDeck.length > DECK_SIZE) {
            showMessage(`卡组不能超过 ${DECK_SIZE} 张 (当前${currentDeck.length}张)`, 'error');
            return;
        }

        // 前端检查限制
        const counts = {};
        let valid = true;
        
        for (let card of currentDeck) {
            counts[card] = (counts[card] || 0) + 1;
        }
        
        for (let card in counts) {
            const cnt = counts[card];
            const detail = cardDetails[card];
            
            if (!detail) {
                showMessage(`卡牌 ${card} 不存在`, 'error');
                return;
            }
            
            const quality = detail.quality || '普通';
            const limit = QUALITY_LIMIT[quality] || 4;
            
            if (cnt > limit) {
                showMessage(`${card} 最多携带 ${limit} 张`, 'error');
                valid = false;
                break;
            }
            
            const owned = userCards[card] || 0;
            if (cnt > owned) {
                showMessage(`你没有足够的 ${card} (拥有${owned}张)`, 'error');
                valid = false;
                break;
            }
        }
        
        if (!valid) return;

        // 发送保存请求
        showMessage('保存中...', 'info');
        
        fetch('/save_deck', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: name, cards: currentDeck })
        })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                showMessage('卡组保存成功！', 'info');
                
                // 更新下拉框选项
                updateDeckSelectAfterSave(name);
                
                // 刷新页面
                setTimeout(() => location.reload(), 1500);
            } else {
                showMessage('保存失败: ' + data.error, 'error');
            }
        })
        .catch(err => {
            showMessage('网络错误', 'error');
            console.error(err);
        });
    }

    // ========== 保存后更新下拉框 ==========
    function updateDeckSelectAfterSave(newDeckName) {
        // 检查是否已存在
        let exists = false;
        for (let i = 0; i < deckSelect.options.length; i++) {
            if (deckSelect.options[i].value === newDeckName) {
                exists = true;
                break;
            }
        }
        
        // 如果不存在，添加新选项
        if (!exists && newDeckName) {
            const option = document.createElement('option');
            option.value = newDeckName;
            option.textContent = newDeckName;
            deckSelect.appendChild(option);
        }
        
        // 选中当前保存的卡组
        deckSelect.value = newDeckName;
        loadBtn.disabled = false;
        deleteBtn.disabled = false;
    }

    // ========== 暴露全局函数供HTML调用 ==========
    window.showCardDetailsFromList = function(cardName) {
        showCardDetails(cardName);
    };

    window.removeDeckCard = function(index) {
        removeFromDeck(index);
    };

    // ========== 新增功能函数 ==========

    // 过滤卡牌
    function filterCards(searchTerm) {
        const cards = document.querySelectorAll('.card-item');
        searchTerm = searchTerm.toLowerCase().trim();
        
        cards.forEach(card => {
            const cardName = card.dataset.name.toLowerCase();
            if (searchTerm === '' || cardName.includes(searchTerm)) {
                card.style.display = 'block';
            } else {
                card.style.display = 'none';
            }
        });
    }

    // 导出卡组
    function exportDeck() {
        if (currentDeck.length === 0) {
            showMessage('卡组为空，无法导出', 'warning');
            return;
        }
        
        // 统计卡牌数量
        const cardCounts = {};
        currentDeck.forEach(card => {
            cardCounts[card] = (cardCounts[card] || 0) + 1;
        });
        
        // 生成导出数据
        const exportData = {
            name: currentDeckName || '未命名卡组',
            cards: cardCounts,
            total: currentDeck.length,
            version: '1.0',
            timestamp: new Date().toISOString()
        };
        
        // 转换为JSON字符串
        const jsonStr = JSON.stringify(exportData, null, 2);
        
        // 创建下载链接
        const blob = new Blob([jsonStr], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${exportData.name}.deck.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        
        showMessage('卡组已导出', 'info');
    }

    // 添加导入模态框
    function addImportModal() {
        const modalHtml = `
            <div id="import-modal" class="import-modal">
                <div class="import-modal-content">
                    <h3>📥 导入卡组</h3>
                    <p>粘贴卡组代码 (JSON格式)：</p>
                    <textarea id="import-code" placeholder='例如：{"name":"我的卡组","cards":{"探察者":4,"激光防御装置":3}}'></textarea>
                    <div class="import-modal-btns">
                        <button class="import-confirm-btn" id="import-confirm">确认导入</button>
                        <button class="import-cancel-btn" id="import-cancel">取消</button>
                    </div>
                </div>
            </div>
        `;
        document.body.insertAdjacentHTML('beforeend', modalHtml);
        
        // 绑定事件
        const importModal = document.getElementById('import-modal');
        const importConfirm = document.getElementById('import-confirm');
        const importCancel = document.getElementById('import-cancel');
        
        importConfirm.addEventListener('click', function() {
            const code = document.getElementById('import-code').value;
            importDeck(code);
            importModal.style.display = 'none';
        });
        
        importCancel.addEventListener('click', function() {
            importModal.style.display = 'none';
        });
        
        window.addEventListener('click', function(e) {
            if (e.target === importModal) {
                importModal.style.display = 'none';
            }
        });
    }

    // 显示导入模态框
    function showImportModal() {
        document.getElementById('import-modal').style.display = 'block';
        document.getElementById('import-code').value = '';
    }

    // 导入卡组（带严格验证）
    function importDeck(code) {
        try {
            const importData = JSON.parse(code);
            
            // 验证格式
            if (!importData.cards || typeof importData.cards !== 'object') {
                showMessage('无效的卡组格式：缺少 cards 字段', 'error');
                return;
            }
            
            // 清空当前卡组
            const newDeck = [];
            const missingCards = [];
            const overLimitCards = [];
            const notOwnedCards = [];
            const hiddenCards = [];
            
            // 逐卡添加
            for (let [cardName, count] of Object.entries(importData.cards)) {
                // 检查卡牌是否存在
                if (!cardDetails[cardName]) {
                    missingCards.push(cardName);
                    continue;
                }
                
                // 检查是否是隐藏卡（但可以通过指令获取，所以只记录不阻止）
                const detail = cardDetails[cardName];
                if (detail.hidden) {
                    hiddenCards.push(cardName);
                }
                
                // 检查品质上限
                const quality = detail.quality || '普通';
                const limit = QUALITY_LIMIT[quality] || 4;
                
                let validCount = count;
                if (count > limit) {
                    overLimitCards.push(`${cardName}(${count}/${limit})`);
                    validCount = limit; // 截断到上限
                }
                
                // 检查拥有数量
                const owned = userCards[cardName] || 0;
                if (validCount > owned) {
                    notOwnedCards.push(`${cardName}(${validCount}/${owned})`);
                    validCount = owned; // 截断到拥有数量
                }
                
                // 添加到卡组
                for (let i = 0; i < validCount; i++) {
                    if (newDeck.length < DECK_SIZE) {
                        newDeck.push(cardName);
                    }
                }
            }
            
            // 检查卡组大小
            if (newDeck.length > DECK_SIZE) {
                newDeck.length = DECK_SIZE; // 截断
                showMessage(`卡组超过${DECK_SIZE}张，已截断`, 'warning');
            }
            
            // 更新卡组
            currentDeck = newDeck;
            currentDeckName = importData.name || '导入卡组';
            deckNameInput.value = currentDeckName;
            
            // 更新UI
            updateDeckUI();
            renderAvailableCards();
            
            // 显示导入结果
            let message = `✅ 导入成功！共${newDeck.length}张卡`;
            if (missingCards.length > 0) {
                message += `\n❌ 忽略未知卡牌：${missingCards.join(', ')}`;
            }
            if (hiddenCards.length > 0) {
                message += `\n👻 包含隐藏卡：${hiddenCards.join(', ')}（可通过指令获取）`;
            }
            if (overLimitCards.length > 0) {
                message += `\n⚠️ 超限卡牌已调整：${overLimitCards.join(', ')}`;
            }
            if (notOwnedCards.length > 0) {
                message += `\n⚠️ 拥有数量不足：${notOwnedCards.join(', ')}`;
            }
            showMessage(message, 'info');
            
            // 高亮新导入的卡组名称
            deckNameInput.style.border = '2px solid #f1c40f';
            setTimeout(() => {
                deckNameInput.style.border = '';
            }, 2000);
            
        } catch (e) {
            showMessage('❌ 导入失败：无效的JSON格式', 'error');
            console.error(e);
        }
    }

    // 复制卡组代码到剪贴板
    function copyDeckCode() {
        if (currentDeck.length === 0) {
            showMessage('卡组为空，无法复制', 'warning');
            return;
        }
        
        // 统计卡牌数量
        const cardCounts = {};
        currentDeck.forEach(card => {
            cardCounts[card] = (cardCounts[card] || 0) + 1;
        });
        
        // 生成导出数据
        const exportData = {
            name: currentDeckName || '未命名卡组',
            cards: cardCounts,
            total: currentDeck.length,
            version: '1.0'
        };
        
        const jsonStr = JSON.stringify(exportData, null, 2);
        
        // 复制到剪贴板
        navigator.clipboard.writeText(jsonStr).then(() => {
            showMessage('✅ 卡组代码已复制到剪贴板！', 'info');
            
            // 复制按钮动画
            const btn = document.getElementById('copy-deck-code-btn');
            btn.textContent = '✅ 已复制';
            setTimeout(() => {
                btn.textContent = '📋 复制代码';
            }, 2000);
        }).catch(err => {
            showMessage('❌ 复制失败', 'error');
            console.error(err);
        });
    }

    // ========== 启动初始化 ==========
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function() {
            init();
        });
    } else {
        init();
    }
})();