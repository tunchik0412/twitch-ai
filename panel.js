/**
 * Gemini Stream Assistant - Panel Viewer JavaScript
 * Handles viewer interactions and secure communication with backend
 */

// State
let auth = null;
let config = {
    ebsUrl: 'https://twitch-ai.onrender.com',  // Default to your backend
    commands: { ask: true, roast: true, joke: true, fact: true },
    cooldown: 5,
    botPrefix: '🤖 Gemini',
    responseStyle: 'friendly'
};
let isConfigured = true;  // Default to true, let API errors guide the user
let isLoading = false;
let cooldowns = {}; // Per-command cooldowns
let messageCount = 0;
const MAX_MESSAGES = 50; // Limit chat history

// Initialize when Twitch extension is ready
window.Twitch.ext.onAuthorized(function(authData) {
    console.log('Panel authorized');
    auth = authData;
    updateStatusIndicator(true);
    loadBotConfig();
});

window.Twitch.ext.onContext(function(context) {
    // Context changes
});

// Load bot configuration from Twitch config service
function loadBotConfig() {
    window.Twitch.ext.configuration.onChanged(function() {
        if (window.Twitch.ext.configuration.broadcaster &&
            window.Twitch.ext.configuration.broadcaster.content) {
            try {
                const savedConfig = JSON.parse(
                    window.Twitch.ext.configuration.broadcaster.content
                );
                
                console.log('Loaded config from Twitch:', savedConfig);
                
                // Apply configuration (excluding sensitive data like API keys)
                if (savedConfig.ebsUrl) config.ebsUrl = savedConfig.ebsUrl;
                if (savedConfig.commands) config.commands = savedConfig.commands;
                if (savedConfig.cooldown) config.cooldown = savedConfig.cooldown;
                if (savedConfig.botPrefix) config.botPrefix = savedConfig.botPrefix;
                if (savedConfig.responseStyle) config.responseStyle = savedConfig.responseStyle;
                
                isConfigured = true;
                updateUI();
                
            } catch (e) {
                console.error('Failed to parse config:', e);
                // Still allow usage with default config
                isConfigured = true;
                updateUI();
            }
        } else {
            console.log('No broadcaster config found, using defaults');
            // Still allow usage with default config
            isConfigured = true;
            updateUI();
        }
    });
}

// Update UI based on configuration
function updateUI() {
    // Show/hide command buttons based on config
    document.getElementById('btnJoke').classList.toggle('hidden', !config.commands.joke);
    document.getElementById('btnFact').classList.toggle('hidden', !config.commands.fact);
    document.getElementById('btnRoast').classList.toggle('hidden', !config.commands.roast);
    
    // Update bot prefix in header if needed
    document.querySelector('.header h1').textContent = config.botPrefix;
    
    if (!isConfigured) {
        showNotConfigured();
    }
}

// Show not configured message
function showNotConfigured() {
    const chatWindow = document.getElementById('chatWindow');
    chatWindow.innerHTML = `
        <div class="not-configured">
            <h2>⚙️ Setup Required</h2>
            <p>The streamer needs to configure this extension.</p>
        </div>
    `;
}

// Update connection status indicator
function updateStatusIndicator(online) {
    const dot = document.getElementById('statusDot');
    dot.classList.toggle('online', online);
    dot.title = online ? 'Connected' : 'Disconnected';
}

// Send message to backend EBS
async function sendToGemini(command, userMessage) {
    try {
        console.log('Sending to:', config.ebsUrl + '/api/gemini');
        const response = await fetch(config.ebsUrl + '/api/gemini', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': 'Bearer ' + auth.token
            },
            body: JSON.stringify({
                prompt: userMessage,
                command: command,
                channelId: auth.channelId,
                style: config.responseStyle
            })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || 'Request failed');
        }
        
        const data = await response.json();
        return data.reply;
        
    } catch (error) {
        console.error('API error:', error);
        if (error.message.includes('API key')) {
            return "The streamer hasn't configured their API key yet. Please try again later! 🔧";
        }
        return "Sorry, I'm having trouble connecting right now. Please try again! 😅";
    }
}

// Add message to chat window
function addMessage(user, message, type = 'user') {
    const chatWindow = document.getElementById('chatWindow');
    
    // Remove welcome message if present
    const welcome = chatWindow.querySelector('.welcome-message');
    if (welcome) welcome.remove();
    
    // Create message element
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${type}-message`;
    messageDiv.id = `msg-${++messageCount}`;
    
    const headerDiv = document.createElement('div');
    headerDiv.className = 'message-header';
    
    const userSpan = document.createElement('span');
    userSpan.className = 'message-user';
    userSpan.textContent = user;
    userSpan.style.color = type === 'bot' ? '#00b0f0' : '#bf94ff';
    
    const timeSpan = document.createElement('span');
    timeSpan.className = 'message-time';
    timeSpan.textContent = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    
    headerDiv.appendChild(userSpan);
    headerDiv.appendChild(timeSpan);
    
    const textDiv = document.createElement('div');
    textDiv.className = 'message-text';
    textDiv.textContent = message;
    
    messageDiv.appendChild(headerDiv);
    messageDiv.appendChild(textDiv);
    chatWindow.appendChild(messageDiv);
    
    // Scroll to bottom
    chatWindow.scrollTop = chatWindow.scrollHeight;
    
    // Limit message history
    while (chatWindow.children.length > MAX_MESSAGES) {
        chatWindow.removeChild(chatWindow.firstChild);
    }
    
    return messageDiv.id;
}

// Show loading indicator
function showLoading() {
    const chatWindow = document.getElementById('chatWindow');
    
    const loadingDiv = document.createElement('div');
    loadingDiv.id = 'loadingIndicator';
    loadingDiv.className = 'message bot-message';
    loadingDiv.innerHTML = `
        <div class="message-header">
            <span class="message-user" style="color: #00b0f0;">${config.botPrefix}</span>
        </div>
        <div class="message-text">
            <span class="loading-indicator">
                <span class="loading-spinner"></span>
                <span>Thinking...</span>
            </span>
        </div>
    `;
    chatWindow.appendChild(loadingDiv);
    chatWindow.scrollTop = chatWindow.scrollHeight;
}

// Hide loading indicator
function hideLoading() {
    const loading = document.getElementById('loadingIndicator');
    if (loading) loading.remove();
}

// Check if command is on cooldown
function isOnCooldown(command) {
    const now = Date.now();
    const lastUsed = cooldowns[command] || 0;
    return (now - lastUsed) < (config.cooldown * 1000);
}

// Get remaining cooldown time
function getRemainingCooldown(command) {
    const now = Date.now();
    const lastUsed = cooldowns[command] || 0;
    const remaining = Math.ceil((config.cooldown * 1000 - (now - lastUsed)) / 1000);
    return Math.max(0, remaining);
}

// Set cooldown for command
function setCooldown(command) {
    cooldowns[command] = Date.now();
}

// Show cooldown notice
function showCooldownNotice(seconds) {
    const notice = document.getElementById('cooldownNotice');
    notice.textContent = `⏱️ Please wait ${seconds}s before sending another message`;
    notice.style.display = 'block';
    setTimeout(() => {
        notice.style.display = 'none';
    }, 2000);
}

// Set UI loading state
function setLoadingState(loading) {
    isLoading = loading;
    document.getElementById('sendBtn').disabled = loading;
    document.getElementById('messageInput').disabled = loading;
    document.querySelectorAll('.cmd-btn').forEach(btn => {
        btn.disabled = loading;
    });
}

// Split long responses for display
function splitResponse(text, maxLength = 450) {
    if (text.length <= maxLength) return [text];
    
    const parts = [];
    let remaining = text;
    
    while (remaining.length > 0) {
        if (remaining.length <= maxLength) {
            parts.push(remaining);
            break;
        }
        
        // Find a good break point
        let breakPoint = maxLength;
        const lastSentence = remaining.lastIndexOf('.', maxLength);
        const lastSpace = remaining.lastIndexOf(' ', maxLength);
        
        if (lastSentence > maxLength * 0.6) {
            breakPoint = lastSentence + 1;
        } else if (lastSpace > maxLength * 0.6) {
            breakPoint = lastSpace;
        }
        
        parts.push(remaining.substring(0, breakPoint).trim());
        remaining = remaining.substring(breakPoint).trim();
    }
    
    return parts;
}

// Handle sending message
async function sendMessage(command = null, customPrompt = null) {
    if (isLoading) return;
    
    const input = document.getElementById('messageInput');
    let message = customPrompt || input.value.trim();
    
    if (!message && !command) return;
    
    // Parse command from message if not provided
    if (!command && message.startsWith('!')) {
        const parts = message.slice(1).split(' ');
        const parsedCommand = parts[0].toLowerCase();
        const args = parts.slice(1).join(' ');
        
        if (['ask', 'roast', 'joke', 'fact', 'help'].includes(parsedCommand)) {
            command = parsedCommand;
            message = args || parsedCommand;
        }
    }
    
    // Default to ask command
    if (!command) command = 'ask';
    
    // Check if command is enabled
    if (command !== 'help' && !config.commands[command]) {
        addMessage(config.botPrefix, `The !${command} command is currently disabled.`, 'error');
        return;
    }
    
    // Check cooldown
    if (isOnCooldown(command)) {
        showCooldownNotice(getRemainingCooldown(command));
        return;
    }
    
    // Handle help command locally
    if (command === 'help') {
        let helpText = "Available commands: ";
        const cmds = [];
        if (config.commands.ask) cmds.push("!ask [question]");
        if (config.commands.roast) cmds.push("!roast [@user]");
        if (config.commands.joke) cmds.push("!joke");
        if (config.commands.fact) cmds.push("!fact");
        helpText += cmds.join(', ') || "No commands enabled";
        addMessage(config.botPrefix, helpText, 'bot');
        input.value = '';
        return;
    }
    
    // Clear input and show user message
    input.value = '';
    const displayMessage = command === 'ask' ? message : `!${command}` + (message && command === 'roast' ? ` ${message}` : '');
    addMessage('You', displayMessage, 'user');
    
    // Set loading state
    setLoadingState(true);
    showLoading();
    setCooldown(command);
    
    try {
        // Call backend
        const response = await sendToGemini(command, message);
        hideLoading();
        
        // Split and display long responses
        const parts = splitResponse(response);
        for (const part of parts) {
            addMessage(config.botPrefix, part, 'bot');
        }
        
    } catch (error) {
        hideLoading();
        addMessage(config.botPrefix, "Sorry, something went wrong. Please try again!", 'error');
    } finally {
        setLoadingState(false);
    }
}

// Event listeners
document.getElementById('sendBtn').addEventListener('click', () => sendMessage());

document.getElementById('messageInput').addEventListener('keypress', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});

// Command button handlers
document.querySelectorAll('.cmd-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        const command = btn.dataset.command;
        
        if (command === 'roast') {
            // Roast the user themselves
            sendMessage('roast', 'me');
        } else {
            sendMessage(command, command);
        }
    });
});