let twitchExt = null;

// Wait for Twitch extension to be ready
window.Twitch.ext.onAuthorized(function(auth) {
    console.log('Extension authorized for channel:', auth.channelId);
    loadConfiguration();
});

window.Twitch.ext.onContext(function(context) {
    console.log('Context:', context);
});

// Save configuration
document.getElementById('saveBtn').addEventListener('click', function() {
    const config = {
        apiKey: document.getElementById('apiKey').value,
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
        botPrefix: document.getElementById('botPrefix').value,
        responseStyle: document.getElementById('responseStyle').value,
        customPrompt: document.getElementById('customPrompt').value
    };
    
    saveConfiguration(config);
});

// Load existing configuration
function loadConfiguration() {
    // Listen for configuration changes [citation:2][citation:9]
    window.Twitch.ext.configuration.onChanged(function() {
        if (window.Twitch.ext.configuration.broadcaster &&
            window.Twitch.ext.configuration.broadcaster.content) {
            try {
                const config = JSON.parse(
                    window.Twitch.ext.configuration.broadcaster.content
                );
                applyConfiguration(config);
            } catch (e) {
                console.error('Failed to parse config:', e);
            }
        }
    });
}

// Apply loaded config to UI
function applyConfiguration(config) {
    if (config.apiKey) document.getElementById('apiKey').value = config.apiKey;
    if (config.model) document.getElementById('model').value = config.model;
    if (config.temperature) {
        document.getElementById('temperature').value = config.temperature;
        document.getElementById('tempValue').innerText = config.temperature;
    }
    if (config.maxLength) document.getElementById('maxLength').value = config.maxLength;
    if (config.commands) {
        document.getElementById('enableAsk').checked = config.commands.ask;
        document.getElementById('enableRoast').checked = config.commands.roast;
        document.getElementById('enableJoke').checked = config.commands.joke;
        document.getElementById('enableFact').checked = config.commands.fact;
    }
    if (config.cooldown) document.getElementById('cooldown').value = config.cooldown;
    if (config.botPrefix) document.getElementById('botPrefix').value = config.botPrefix;
    if (config.responseStyle) document.getElementById('responseStyle').value = config.responseStyle;
    if (config.customPrompt) document.getElementById('customPrompt').value = config.customPrompt;
}

// Save configuration to Twitch's service [citation:2]
function saveConfiguration(config) {
    try {
        const configString = JSON.stringify(config);
        
        // Use Twitch's Configuration Service [citation:5]
        window.Twitch.ext.configuration.set('broadcaster', '1.0', configString);
        
        showStatus('✅ Configuration saved successfully!', 'success');
    } catch (error) {
        console.error('Save error:', error);
        showStatus('❌ Failed to save configuration: ' + error.message, 'error');
    }
}

function showStatus(message, type) {
    const statusDiv = document.getElementById('status');
    statusDiv.className = 'status ' + type;
    statusDiv.innerHTML = message;
    setTimeout(() => {
        statusDiv.className = 'status';
    }, 3000);
}

// Temperature display
document.getElementById('temperature').addEventListener('input', function() {
    document.getElementById('tempValue').innerText = this.value;
});