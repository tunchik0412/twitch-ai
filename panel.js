let twitchExt = null;
let currentUser = null;
let botPrefix = "🤖 Gemini";
let commandsEnabled = { ask: true, roast: true, joke: true, fact: true };
let responseStyle = "friendly";

// Wait for Twitch extension to be ready
window.Twitch.ext.onAuthorized(function(auth) {
    console.log('Panel authorized');
    currentUser = auth.userId;
    loadBotConfig();
});

window.Twitch.ext.onContext(function(context) {
    if (context && context.role === 'broadcaster') {
        // Show a small indicator for streamer that they're in config mode
        console.log('Broadcaster viewing panel');
    }
});

// Load bot configuration from Twitch config service [citation:9]
function loadBotConfig() {
    window.Twitch.ext.configuration.onChanged(function() {
        if (window.Twitch.ext.configuration.broadcaster &&
            window.Twitch.ext.configuration.broadcaster.content) {
            try {
                const config = JSON.parse(
                    window.Twitch.ext.configuration.broadcaster.content
                );
                
                if (config.botPrefix) botPrefix = config.botPrefix;
                if (config.commands) commandsEnabled = config.commands;
                if (config.responseStyle) responseStyle = config.responseStyle;
                
                console.log('Bot config loaded:', config);
            } catch (e) {
                console.error('Failed to parse config:', e);
            }
        }
    });
}

// Send message to your backend/EBS
async function sendToGemini(command, userMessage, userName) {
    const prompt = command === 'ask' ? userMessage : command;
    
    try {
        // Call your Extension Backend Service (EBS) [citation:6]
        const response = await fetch('https://your-ebs-url.com/api/gemini', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': 'Bearer ' + getExtensionToken()
            },
            body: JSON.stringify({
                prompt: prompt,
                command: command,
                userName: userName,
                style: responseStyle
            })
        });
        
        const data = await response.json();
        return data.reply;
    } catch (error) {
        console.error('Gemini API error:', error);
        return "Sorry, I'm having trouble connecting to my brain right now. Try again! 😅";
    }
}

// Add message to chat window
function addMessage(user, message, isBot = false) {
    const chatWindow = document.getElementById('chatWindow');
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message ' + (isBot ? 'bot-message' : 'user-message');
    
    const userSpan = document.createElement('span');
    userSpan.className = 'message-user';
    userSpan.textContent = isBot ? botPrefix + ':' : (user + ':');
    
    const textSpan = document.createElement('span');
    textSpan.className = 'message-text';
    textSpan.textContent = message;
    
    messageDiv.appendChild(userSpan);
    messageDiv.appendChild(textSpan);
    chatWindow.appendChild(messageDiv);
    chatWindow.scrollTop = chatWindow.scrollHeight;
}

// Show loading indicator
function showLoading() {
    const chatWindow = document.getElementById('chatWindow');
    const loadingDiv = document.createElement('div');
    loadingDiv.id = 'loadingIndicator';
    loadingDiv.className = 'message bot-message';
    loadingDiv.innerHTML = '<span class="message-user">' + botPrefix + ':</span> <span class="message-text"><span class="loading"></span> Thinking...</span>';
    chatWindow.appendChild(loadingDiv);
    chatWindow.scrollTop = chatWindow.scrollHeight;
}

function hideLoading() {
    const loading = document.getElementById('loadingIndicator');
    if (loading) loading.remove();
}

// Handle sending message
async function sendMessage() {
    const input = document.getElementById('messageInput');
    const message = input.value.trim();
    
    if (!message) return;
    
    // Get viewer's display name (requires JWT)
    const userName = await getViewerName();
    
    addMessage(userName, message, false);
    input.value = '';
    
    // Check if it's a command
    if (message.startsWith('!')) {
        const parts = message.slice(1).split(' ');
        const command = parts[0].toLowerCase();
        const args = parts.slice(1).join(' ');
        
        if (command === 'ask' && commandsEnabled.ask) {
            showLoading();
            const response = await sendToGemini('ask', args, userName);
            hideLoading();
            addMessage(botPrefix, response, true);
        } else if (command === 'roast' && commandsEnabled.roast) {
            showLoading();
            const target = args || userName;
            const response = await sendToGemini('roast', target, userName);
            hideLoading();
            addMessage(botPrefix, response, true);
        } else if (command === 'joke' && commandsEnabled.joke) {
            showLoading();
            const response = await sendToGemini('joke', '', userName);
            hideLoading();
            addMessage(botPrefix, response, true);
        } else if (command === 'fact' && commandsEnabled.fact) {
            showLoading();
            const response = await sendToGemini('fact', '', userName);
            hideLoading();
            addMessage(botPrefix, response, true);
        } else if (command === 'help') {
            let helpText = "Available: ";
            if (commandsEnabled.ask) helpText += "!ask [question] ";
            if (commandsEnabled.roast) helpText += "!roast [@user] ";
            if (commandsEnabled.joke) helpText += "!joke ";
            if (commandsEnabled.fact) helpText += "!fact ";
            addMessage(botPrefix, helpText, true);
        }
    } else if (commandsEnabled.ask) {
        // Natural language query without !ask prefix
        showLoading();
        const response = await sendToGemini('ask', message, userName);
        hideLoading();
        addMessage(botPrefix, response, true);
    }
}

function handleKeyPress(event) {
    if (event.key === 'Enter') {
        sendMessage();
    }
}

async function getViewerName() {
    // This would require decoding the JWT from the extension context
    // For production, you'd parse the token or get from your EBS
    return "Viewer";
}

function getExtensionToken() {
    // Get the JWT token from Twitch extension context
    // This is handled automatically by the extension helper
    return window.Twitch.ext.getToken();
}

// Setup event listeners
document.getElementById('sendBtn').addEventListener('click', sendMessage);
document.querySelectorAll('.cmd-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        document.getElementById('messageInput').value = '!' + btn.dataset.command;
        sendMessage();
    });
});