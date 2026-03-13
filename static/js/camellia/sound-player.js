// sound-player.js - 卡牌音效播放器（完整调试版）
// 在 index.html 中通过 <script src="/static/js/sound-player.js"></script> 引入

(function() {
    // 音效配置
    const SOUND_CONFIG = {
        enabled: true,           // 是否启用音效
        volume: 0.5,             // 默认音量 0-1
        basePath: '/static/',    // 基础路径
        debug: true              // 是否显示调试信息
    };

    // 音效缓存，避免重复创建Audio对象
    const audioCache = new Map();

    // 最近播放的音效记录，避免重复播放
    const recentSounds = new Set();
    const RECENT_CLEANUP_TIME = 500; // 500ms内不重复播放相同音效

    // 测试音效文件是否可访问
    async function testSoundFile(url) {
        try {
            const response = await fetch(url, { method: 'HEAD' });
            console.log(`📁 音效文件检查 [${url}]:`, response.status, response.statusText);
            return response.ok;
        } catch (err) {
            console.error(`❌ 音效文件访问失败 [${url}]:`, err);
            return false;
        }
    }

    /**
     * 播放音效
     * @param {string} soundPath - 音效文件路径（如 "sounds/fire_blast.wav"）
     * @param {object} options - 可选参数 {volume, forcePlay}
     * @returns {Promise} 播放成功或失败的Promise
     */
    function playSound(soundPath, options = {}) {
        console.log('='.repeat(50));
        console.log('🎵 音效播放请求');
        console.log('📥 原始音效路径:', soundPath);
        console.log('⚙️ 当前配置:', JSON.stringify(SOUND_CONFIG, null, 2));
        
        if (!SOUND_CONFIG.enabled || !soundPath) {
            console.log('🔇 音效已禁用或无音效路径');
            console.log('='.repeat(50));
            return Promise.reject('音效已禁用');
        }

        // 避免短时间内重复播放相同音效
        if (recentSounds.has(soundPath)) {
            console.log(`⏭️ 跳过重复音效: ${soundPath}`);
            console.log('='.repeat(50));
            return Promise.reject('重复音效');
        }

        // 记录最近播放的音效
        recentSounds.add(soundPath);
        setTimeout(() => {
            recentSounds.delete(soundPath);
        }, RECENT_CLEANUP_TIME);

        // 构建完整URL - 智能路径处理
        let fullPath;
        
        // 情况1: 已经是完整URL (http:// 或 https://)
        if (soundPath.startsWith('http')) {
            fullPath = soundPath;
            console.log('🌐 使用完整URL:', fullPath);
        }
        // 情况2: 以 /static/ 开头
        else if (soundPath.startsWith('/static/')) {
            fullPath = soundPath;
            console.log('📂 已经是静态文件路径:', fullPath);
        }
        // 情况3: 以 /sounds/ 开头但缺少 static
        else if (soundPath.startsWith('/sounds/')) {
            fullPath = '/static' + soundPath;
            console.log('🔄 添加 static 前缀:', fullPath);
        }
        // 情况4: 以 / 开头但不是 /static/ 或 /sounds/
        else if (soundPath.startsWith('/')) {
            // 可能是其他路径，保持原样
            fullPath = soundPath;
            console.log('⚠️ 未知根路径:', fullPath);
        }
        // 情况5: 相对路径 (如 "sounds/xxx.wav")
        else {
            fullPath = SOUND_CONFIG.basePath + soundPath;
            console.log('🔗 拼接 basePath:', fullPath);
        }

        // 确保路径没有重复的 /static/static/
        fullPath = fullPath.replace(/\/static\/+/g, '/static/');
        
        // 构建完整浏览器URL
        const browserUrl = window.location.origin + fullPath;
        console.log('🌍 浏览器完整地址:', browserUrl);
        console.log('🔊 尝试播放音效:', fullPath);

        // 异步测试文件是否存在
        testSoundFile(fullPath).then(exists => {
            if (!exists) {
                console.warn('⚠️ 警告: 音效文件可能不存在:', fullPath);
                // 尝试其他可能的路径
                const alternativePaths = [
                    soundPath.replace('sounds/', '/static/sounds/'),
                    '/sounds/' + soundPath.split('/').pop(),
                    '/static/sounds/' + soundPath.split('/').pop()
                ];
                console.log('🔄 尝试备选路径:', alternativePaths);
            }
        });

        // 尝试从缓存获取
        let audio = audioCache.get(fullPath);
        if (!audio) {
            console.log('📦 创建新的Audio对象:', fullPath);
            try {
                audio = new Audio(fullPath);
                audio.volume = options.volume !== undefined ? options.volume : SOUND_CONFIG.volume;
                
                // 预加载
                audio.preload = 'auto';
                
                // 监听事件
                audio.addEventListener('canplaythrough', () => {
                    console.log('✅ 音效加载完成:', fullPath);
                });
                
                audio.addEventListener('error', (e) => {
                    console.error('❌ Audio加载错误:', fullPath, e);
                    console.error('错误代码:', audio.error ? audio.error.code : 'unknown');
                    console.error('错误信息:', audio.error ? audio.error.message : 'unknown');
                });
                
                // 缓存音效
                audioCache.set(fullPath, audio);
                console.log('💾 音效已缓存:', fullPath);
            } catch (e) {
                console.error('❌ 创建Audio对象失败:', e);
                console.log('='.repeat(50));
                return Promise.reject('创建Audio对象失败');
            }
        } else {
            console.log('♻️ 使用缓存的音效:', fullPath);
        }

        // 重置播放位置（如果正在播放）
        audio.currentTime = 0;
        
        console.log('▶️ 开始播放...');
        
        // 播放并处理可能的错误
        return audio.play()
            .then(() => {
                console.log('✅ 音效播放成功:', fullPath);
                console.log('='.repeat(50));
            })
            .catch(error => {
                console.warn(`⚠️ 音效播放失败: ${fullPath}`, error);
                console.warn('错误名称:', error.name);
                console.warn('错误消息:', error.message);
                
                // 如果是网络错误，尝试重新创建Audio对象
                if (error.name === 'NotSupportedError' || error.name === 'NetworkError') {
                    console.log('🔄 尝试重新创建Audio对象...');
                    audioCache.delete(fullPath);
                    try {
                        const newAudio = new Audio(fullPath);
                        newAudio.volume = options.volume !== undefined ? options.volume : SOUND_CONFIG.volume;
                        audioCache.set(fullPath, newAudio);
                        console.log('🔄 重试播放...');
                        return newAudio.play().catch(e => {
                            console.error('❌ 重试播放仍然失败:', e);
                            console.log('='.repeat(50));
                        });
                    } catch (e) {
                        console.error('❌ 重新创建Audio对象失败:', e);
                    }
                }
                console.log('='.repeat(50));
            });
    }

    /**
     * 设置音量
     * @param {number} volume - 音量 0-1
     */
    function setVolume(volume) {
        SOUND_CONFIG.volume = Math.max(0, Math.min(1, volume));
        // 更新所有缓存的音效音量
        audioCache.forEach(audio => {
            audio.volume = SOUND_CONFIG.volume;
        });
        if (SOUND_CONFIG.debug) console.log(`🔊 音量已设置为: ${SOUND_CONFIG.volume}`);
    }

    /**
     * 启用/禁用音效
     * @param {boolean} enabled 
     */
    function setEnabled(enabled) {
        SOUND_CONFIG.enabled = enabled;
        if (SOUND_CONFIG.debug) console.log(`🔇 音效${enabled ? '启用' : '禁用'}`);
    }

    /**
     * 预加载音效
     * @param {string[]} soundPaths - 音效路径数组
     */
    function preloadSounds(soundPaths) {
        if (!soundPaths || !soundPaths.length) return;
        
        console.log('📦 开始预加载音效:', soundPaths);
        soundPaths.forEach(path => {
            let fullPath = path.startsWith('/') ? path : `${SOUND_CONFIG.basePath}${path}`;
            // 确保路径正确
            if (fullPath.startsWith('/sounds/')) {
                fullPath = '/static' + fullPath;
            }
            fullPath = fullPath.replace(/\/static\/+/g, '/static/');
            
            if (!audioCache.has(fullPath)) {
                try {
                    const audio = new Audio(fullPath);
                    audio.preload = 'auto';
                    audio.volume = SOUND_CONFIG.volume;
                    audioCache.set(fullPath, audio);
                    console.log(`✅ 预加载音效: ${fullPath}`);
                } catch (e) {
                    console.error(`❌ 预加载失败: ${fullPath}`, e);
                }
            }
        });
    }

    /**
     * 停止所有音效
     */
    function stopAllSounds() {
        audioCache.forEach(audio => {
            audio.pause();
            audio.currentTime = 0;
        });
        if (SOUND_CONFIG.debug) console.log('⏹️ 停止所有音效');
    }

    /**
     * 测试音效系统
     */
    async function testSoundSystem() {
        console.log('🎵 开始测试音效系统...');
        console.log('浏览器信息:', navigator.userAgent);
        console.log('Audio支持:', typeof Audio !== 'undefined');
        
        // 测试音效文件
        const testSounds = [
            '/static/sounds/伪人.wav',
            '/sounds/伪人.wav',
            'sounds/伪人.wav',
            '/static/sounds/高机动.wav'
        ];
        
        for (const sound of testSounds) {
            const fullPath = sound.startsWith('http') ? sound : 
                           (sound.startsWith('/') ? sound : '/static/' + sound);
            console.log(`\n测试音效: ${sound}`);
            console.log('完整路径:', window.location.origin + fullPath);
            await testSoundFile(fullPath);
        }
        
        console.log('🎵 音效系统测试完成');
    }

    // 导出全局接口
    window.SoundPlayer = {
        play: playSound,
        setVolume: setVolume,
        setEnabled: setEnabled,
        preload: preloadSounds,
        stopAll: stopAllSounds,
        test: testSoundSystem,
        
        // 获取配置
        getConfig: () => ({ ...SOUND_CONFIG }),
        
        // 清空缓存
        clearCache: () => {
            audioCache.clear();
            recentSounds.clear();
            if (SOUND_CONFIG.debug) console.log('🗑️ 清空音效缓存');
        },
        
        // 获取缓存状态
        getCacheInfo: () => ({
            cacheSize: audioCache.size,
            recentSounds: Array.from(recentSounds),
            cachedPaths: Array.from(audioCache.keys())
        })
    };

    // 自动拦截游戏状态更新中的音效
    function setupGameStateInterceptor() {
        // 等待游戏状态更新函数加载完成
        const checkInterval = setInterval(() => {
            if (typeof window.updateGameState === 'function') {
                clearInterval(checkInterval);
                
                // 保存原始函数
                const originalUpdateGameState = window.updateGameState;
                
                // 重写updateGameState函数
                window.updateGameState = function() {
                    console.log('🔄 updateGameState 被调用');
                    // 调用原始函数
                    const result = originalUpdateGameState.apply(this, arguments);
                    
                    // 检查是否返回了Promise
                    if (result && result.then) {
                        return result.then(data => {
                            console.log('📦 updateGameState 返回数据:', data);
                            // 在Promise完成后检查音效
                            if (data && data.enemy_sound) {
                                console.log('🎵 拦截到敌方音效:', data.enemy_sound);
                                window.SoundPlayer.play(data.enemy_sound);
                            }
                            return data;
                        });
                    } else {
                        // 同步函数，延迟检查音效
                        setTimeout(() => {
                            if (window.lastGameState && window.lastGameState.enemy_sound) {
                                console.log('🎵 延迟检查到音效:', window.lastGameState.enemy_sound);
                                window.SoundPlayer.play(window.lastGameState.enemy_sound);
                            }
                        }, 100);
                        return result;
                    }
                };
                
                if (SOUND_CONFIG.debug) console.log('🎮 已拦截 updateGameState 函数');
            }
        }, 500);
    }

    // 自动拦截fetch响应
    function setupFetchInterceptor() {
        const originalFetch = window.fetch;
        
        window.fetch = function() {
            const url = arguments[0];
            console.log('🌐 Fetch请求:', url);
            
            return originalFetch.apply(this, arguments).then(response => {
                // 只克隆响应，不消耗原始响应
                const clonedResponse = response.clone();
                
                // 检查是否是game_state请求
                if (url && url.includes && url.includes('/game_state/')) {
                    console.log('🎮 拦截到游戏状态请求:', url);
                    clonedResponse.json().then(data => {
                        console.log('📦 游戏状态数据:', data);
                        if (data && data.enemy_sound) {
                            console.log('🎵 拦截到敌方音效:', data.enemy_sound);
                            window.SoundPlayer.play(data.enemy_sound);
                        }
                        // 保存最后的状态
                        window.lastGameState = data;
                    }).catch(err => {
                        console.error('❌ 解析响应失败:', err);
                    });
                }
                
                return response;
            });
        };
        
        if (SOUND_CONFIG.debug) console.log('🌐 已拦截 fetch 请求');
    }

    // 初始化
    document.addEventListener('DOMContentLoaded', () => {
        console.log('🎵 SoundPlayer 已加载');
        console.log('⏰ DOMContentLoaded 事件触发');
        
        // 检查Audio支持
        if (typeof Audio === 'undefined') {
            console.error('❌ 浏览器不支持Audio API');
        } else {
            console.log('✅ 浏览器支持Audio API');
        }
        
        // 可选：启用fetch拦截
        setupFetchInterceptor();
        
        // 可选：拦截updateGameState
        setupGameStateInterceptor();
        
        // 自动运行测试
        setTimeout(() => {
            console.log('🔍 自动运行音效系统测试...');
            testSoundSystem();
        }, 1000);
    });

    // 暴露调试接口到控制台
    window.debugSound = function() {
        console.log('🎵 SoundPlayer 调试信息:', {
            config: SOUND_CONFIG,
            cacheInfo: {
                size: audioCache.size,
                keys: Array.from(audioCache.keys())
            },
            recentSounds: Array.from(recentSounds),
            browserInfo: {
                userAgent: navigator.userAgent,
                audioSupported: typeof Audio !== 'undefined',
                baseUrl: window.location.origin
            }
        });
    };

    console.log('🎵 SoundPlayer 初始化完成，在控制台输入 debugSound() 查看状态');
})();