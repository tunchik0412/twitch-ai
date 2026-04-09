/**
 * Gemini Stream Assistant - Configuration Page JavaScript
 * Handles broadcaster configuration with secure API key storage
 */

let auth = null;
let ebsUrl = 'https://twitchgeminiaichatbot.duckdns.org';

// Wait for Twitch extension to be ready
window.Twitch.ext.onAuthorized(function(authData) {
    console.log('Extension authorized for channel:', authData.channelId);
    auth = authData;
    loadConfiguration();
    
    // Auto-fill channel name field if we can detect it
    // The channelId is numeric, but we can hint based on that
    const channelInput = document.getElementById('twitchChannel');
    if (channelInput && !channelInput.value) {
        channelInput.placeholder = 'your_channel_name';
    }
});

window.Twitch.ext.onContext(function(context) {
    console.log('Context:', context);
});

// Load existing configuration from Twitch Configuration Service
function loadConfiguration() {
    window.Twitch.ext.configuration.onChanged(function() {
        if (window.Twitch.ext.configuration.broadcaster &&
            window.Twitch.ext.configuration.broadcaster.content) {
            try {
                const config = JSON.parse(
                    window.Twitch.ext.configuration.broadcaster.content
                );
                applyConfiguration(config);
                console.log('Configuration loaded successfully');
            } catch (e) {
                console.error('Failed to parse config:', e);
                showStatus('⚠️ No existing configuration found. Please configure and save.', 'warning');
            }
        }
    });
}

// Apply loaded config to UI elements
function applyConfiguration(config) {
    if (config.ebsUrl) {
        document.getElementById('ebsUrl').value = config.ebsUrl;
        ebsUrl = config.ebsUrl;
    }
    // Note: API key is stored on the backend, not in Twitch config
    // We show a placeholder to indicate it's set
    if (config.hasApiKey) {
        document.getElementById('apiKey').placeholder = '••••••••••••••••••••••••••• (key saved)';
    }
    if (config.model) document.getElementById('model').value = config.model;
    if (config.temperature !== undefined) {
        document.getElementById('temperature').value = config.temperature;
        document.getElementById('tempValue').innerText = config.temperature;
    }
    if (config.maxLength) document.getElementById('maxLength').value = config.maxLength;
    if (config.commands) {
        document.getElementById('enableAsk').checked = config.commands.ask !== false;
        document.getElementById('enableRoast').checked = config.commands.roast !== false;
        document.getElementById('enableJoke').checked = config.commands.joke !== false;
        document.getElementById('enableFact').checked = config.commands.fact !== false;
    }
    if (config.cooldown) document.getElementById('cooldown').value = config.cooldown;
    if (config.botPrefix) document.getElementById('botPrefix').value = config.botPrefix;
    if (config.responseStyle) document.getElementById('responseStyle').value = config.responseStyle;
    if (config.customPrompt) document.getElementById('customPrompt').value = config.customPrompt;
}

// Gather configuration from form
function gatherConfig() {
    return {
        ebsUrl: ebsUrl,
        model: document.getElementById('model').value,
        temperature: parseFloat(document.getElementById('temperature').value),
        maxLength: parseInt(document.getElementById('maxLength').value),
        commands: {
            ask: document.getElementById('enableAsk').checked,
            roast: document.getElementById('enableRoast').checked,
            joke: document.getElementById('enableJoke').checked,
            fact: document.getElementById('enableFact').checked
        },
        cooldown: parseInt(document.getElementById('cooldown').value),
        botPrefix: document.getElementById('botPrefix').value.trim() || '🤖 Gemini',
        responseStyle: document.getElementById('responseStyle').value,
        customPrompt: document.getElementById('customPrompt').value.trim()
    };
}

// Save configuration
document.getElementById('saveBtn').addEventListener('click', async function() {
    const saveBtn = document.getElementById('saveBtn');
    saveBtn.disabled = true;
    saveBtn.textContent = '⏳ Saving...';
    
    try {
        const config = gatherConfig();
        const apiKey = document.getElementById('apiKey').value.trim();
        
        // Backend URL is set by default
        
        // Ensure URL doesn't have trailing slash
        config.ebsUrl = config.ebsUrl.replace(/\/+$/, '');
        
        // Store API key securely on the backend (if provided)
        if (apiKey) {
            console.log('Saving to backend:', config.ebsUrl + '/api/config');
            
            try {
                const response = await fetch(config.ebsUrl + '/api/config', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': 'Bearer ' + auth.token
                    },
                    body: JSON.stringify({
                        channelId: auth.channelId,
                        apiKey: apiKey,
                        model: config.model,
                        temperature: config.temperature,
                        maxLength: config.maxLength,
                        responseStyle: config.responseStyle,
                        customPrompt: config.customPrompt
                    })
                });
                
                if (!response.ok) {
                    const error = await response.json();
                    throw new Error(error.error || 'Failed to save API key to backend');
                }
                
                // Mark that API key is set (without storing the key itself)
                config.hasApiKey = true;
            } catch (fetchError) {
                console.error('Backend save failed:', fetchError);
                // Still save to Twitch config, just without hasApiKey
                // The panel will try to use the backend and get a proper error
                config.hasApiKey = false;
                
                // Save config to Twitch anyway so panel knows the URL
                const configString = JSON.stringify(config);
                window.Twitch.ext.configuration.set('broadcaster', '1.0', configString);
                
                showStatus(
                    '⚠️ Settings saved to Twitch, but backend connection failed.\n' +
                    'Add "' + config.ebsUrl + '" to Extension Allowlist in Twitch Dev Console, then try again.',
                    'warning'
                );
                return; // Exit early
            }
        }
        
        // Save non-sensitive config to Twitch Configuration Service
        const configString = JSON.stringify(config);
        window.Twitch.ext.configuration.set('broadcaster', '1.0', configString);
        
        showStatus('✅ Configuration saved successfully!', 'success');
        
        // Clear the API key field and update placeholder
        if (apiKey) {
            document.getElementById('apiKey').value = '';
            document.getElementById('apiKey').placeholder = '••••••••••••••••••••••••••• (key saved)';
        }
        
    } catch (error) {
        console.error('Save error:', error);
        showStatus('❌ ' + error.message, 'error');
    } finally {
        saveBtn.disabled = false;
        saveBtn.textContent = '💾 Save Configuration';
    }
});

// Test connection to backend
document.getElementById('testBtn').addEventListener('click', async function() {
    const testBtn = document.getElementById('testBtn');
    testBtn.disabled = true;
    testBtn.textContent = '⏳ Testing...';
    
    try {
        const url = document.getElementById('ebsUrl').value.trim();
        if (!url) {
            throw new Error('Please enter the Backend Server URL first');
        }
        
        const healthUrl = url + '/api/health';
        console.log('[Test Connection] URL:', healthUrl);
        console.log('[Test Connection] Auth token present:', !!auth?.token);
        console.log('[Test Connection] Channel ID:', auth?.channelId);
        
        const response = await fetch(healthUrl, {
            method: 'GET',
            headers: {
                'Authorization': 'Bearer ' + auth.token
            }
        });
        
        console.log('[Test Connection] Response status:', response.status);
        console.log('[Test Connection] Response headers:', Object.fromEntries(response.headers.entries()));
        
        if (response.ok) {
            const data = await response.json();
            console.log('[Test Connection] Response data:', data);
            if (data.hasApiKey) {
                showStatus('✅ Connected! API key is configured for this channel.', 'success');
            } else {
                showStatus('⚠️ Connected, but no API key configured yet. Save your configuration.', 'warning');
            }
        } else {
            const errorText = await response.text();
            console.error('[Test Connection] Error response:', errorText);
            throw new Error('Backend returned status ' + response.status + ': ' + errorText);
        }
    } catch (error) {
        console.error('[Test Connection] Error:', error);
        console.error('[Test Connection] Error name:', error.name);
        console.error('[Test Connection] Error message:', error.message);
        
        // Provide more helpful error messages
        let errorMsg = error.message;
        if (error.message === 'Failed to fetch') {
            errorMsg = 'Failed to fetch - This usually means the URL is not in the Twitch Extension Allowlist. ' +
                'Go to Twitch Developer Console → Extension → Capabilities → Add "' + 
                document.getElementById('ebsUrl').value.trim() + '" to the Extension Backend Service allowlist.';
        }
        showStatus('❌ Connection failed: ' + errorMsg, 'error');
    } finally {
        testBtn.disabled = false;
        testBtn.textContent = '🧪 Test Connection';
    }
});

// Show status message
function showStatus(message, type) {
    const statusDiv = document.getElementById('status');
    statusDiv.className = 'status ' + type;
    statusDiv.innerHTML = message;
    
    // Auto-hide success messages
    if (type === 'success') {
        setTimeout(() => {
            statusDiv.className = 'status';
        }, 5000);
    }
}

// Temperature slider display
document.getElementById('temperature').addEventListener('input', function() {
    document.getElementById('tempValue').innerText = this.value;
});

// Show bot status message
function showBotStatus(message, type) {
    const statusDiv = document.getElementById('botStatus');
    statusDiv.className = 'status ' + type;
    statusDiv.innerHTML = message;
    
    if (type === 'success') {
        setTimeout(() => {
            statusDiv.className = 'status';
        }, 5000);
    }
}

// Save & Enable Chat Bot
document.getElementById('saveBotBtn').addEventListener('click', async function() {
    const btn = document.getElementById('saveBotBtn');
    btn.disabled = true;
    btn.textContent = '⏳ Saving...';
    
    try {
        const twitchToken = document.getElementById('twitchToken').value.trim();
        const apiKey = document.getElementById('apiKey').value.trim();
        const botPrefix = document.getElementById('botCmdPrefix').value.trim() || '!';
        const cooldown = document.getElementById('cooldown').value || '5';
        const enableBot = document.getElementById('enableBot').checked;
        const ebsUrl = document.getElementById('ebsUrl').value.trim();
        
        if (!ebsUrl) {
            throw new Error('Please enter the Backend Server URL first');
        }
        
        if (enableBot) {
            if (!twitchToken) {
                throw new Error('Please enter your Twitch Bot OAuth Token');
            }
            if (!apiKey) {
                throw new Error('Please enter your Gemini API key (in the AI Configuration section above)');
            }
        }
        
        // Format token properly
        let token = twitchToken;
        if (token && !token.startsWith('oauth:')) {
            token = 'oauth:' + token;
        }
        
        const response = await fetch(ebsUrl + '/api/bot/config', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': 'Bearer ' + auth.token
            },
            body: JSON.stringify({
                channelId: auth.channelId,
                enabled: enableBot,
                twitchToken: token,
                geminiApiKey: apiKey,
                botPrefix: botPrefix,
                cooldown: parseInt(cooldown)
            })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || 'Failed to save bot configuration');
        }
        
        const data = await response.json();
        
        if (enableBot) {
            showBotStatus('✅ Bot enabled! It will join your channel shortly.', 'success');
        } else {
            showBotStatus('✅ Bot disabled for your channel.', 'success');
        }
        
        // Clear token field after save
        document.getElementById('twitchToken').value = '';
        document.getElementById('twitchToken').placeholder = '••••••••••••••••••• (token saved)';
        
    } catch (error) {
        console.error('Bot config error:', error);
        showBotStatus('❌ ' + error.message, 'error');
    } finally {
        btn.disabled = false;
        btn.textContent = '🤖 Save & Enable Chat Bot';
    }
});

// Download .env file for local bot
document.getElementById('downloadEnvBtn').addEventListener('click', function() {
    const twitchToken = document.getElementById('twitchToken').value.trim();
    const apiKey = document.getElementById('apiKey').value.trim();
    const botPrefix = document.getElementById('botCmdPrefix').value.trim() || '!';
    const cooldown = document.getElementById('cooldown').value || '5';
    
    // We need to ask for channel name since we can't easily get it from Twitch API
    const twitchChannel = prompt('Enter your Twitch channel name (username):');
    
    // Validate required fields
    if (!twitchToken) {
        showStatus('❌ Please enter your Twitch Bot OAuth Token', 'error');
        return;
    }
    if (!twitchChannel) {
        showStatus('❌ Channel name is required', 'error');
        return;
    }
    if (!apiKey) {
        showStatus('❌ Please enter your Gemini API key (in the AI Configuration section above)', 'error');
        return;
    }
    
    // Format token properly
    let token = twitchToken;
    if (!token.startsWith('oauth:')) {
        token = 'oauth:' + token;
    }
    
    // Generate .env content
    const envContent = `# Gemini Twitch Chat Bot Configuration
# Generated from Twitch Extension Config

# Twitch OAuth Token
TWITCH_TOKEN=${token}

# Twitch channel to join
TWITCH_CHANNEL=${twitchChannel.toLowerCase().replace('#', '')}

# Gemini API Key
GEMINI_API_KEY=${apiKey}

# Command prefix
BOT_PREFIX=${botPrefix}

# Cooldown between commands in seconds
COOLDOWN_SECONDS=${cooldown}
`;
    
    // Create and download the file
    const blob = new Blob([envContent], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = '.env';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    
    showStatus('✅ .env file downloaded! Place it in your bot folder and run: python bot.py', 'success');
    
    // Clear sensitive fields after download
    document.getElementById('twitchToken').value = '';
});