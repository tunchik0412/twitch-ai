"""
Gemini Stream Assistant - Flask Backend Service (EBS)
Handles Twitch Extension requests and Gemini AI integration

Deploy to Render.com:
1. Create a new Web Service
2. Connect your Git repository
3. Set environment variables:
   - TWITCH_EXTENSION_SECRET: Your extension secret (base64 encoded)
   - TWITCH_CLIENT_ID: Your Twitch extension client ID
4. Build command: pip install -r requirements.txt
5. Start command: gunicorn app:app
"""


import os
import base64
import json
import logging
from functools import wraps
from datetime import datetime, timedelta
import threading
import asyncio

from flask import Flask, request, jsonify
from flask_cors import CORS
import jwt
import google.generativeai as genai

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# CORS configuration - allow all origins for Twitch extensions
# Twitch extensions run from various CDN domains that are hard to predict
CORS(app, 
     origins="*",
     methods=["GET", "POST", "OPTIONS"],
     allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
     supports_credentials=False)

# Configuration
TWITCH_EXTENSION_SECRET = os.environ.get('TWITCH_EXTENSION_SECRET', '')
TWITCH_CLIENT_ID = os.environ.get('TWITCH_CLIENT_ID', '')

# Persistent storage files
DATA_DIR = os.environ.get('DATA_DIR', '/tmp')
CHANNEL_CONFIGS_FILE = os.path.join(DATA_DIR, 'channel_configs.json')
BOT_CONFIGS_FILE = os.path.join(DATA_DIR, 'bot_configs.json')


def load_configs():
    """Load saved configurations from files."""
    global channel_configs, bot_configs
    
    # Load channel configs
    try:
        if os.path.exists(CHANNEL_CONFIGS_FILE):
            with open(CHANNEL_CONFIGS_FILE, 'r') as f:
                channel_configs = json.load(f)
            logger.info(f"Loaded {len(channel_configs)} channel configs")
    except Exception as e:
        logger.error(f"Error loading channel configs: {e}")
        channel_configs = {}
    
    # Load bot configs
    try:
        if os.path.exists(BOT_CONFIGS_FILE):
            with open(BOT_CONFIGS_FILE, 'r') as f:
                bot_configs = json.load(f)
            logger.info(f"Loaded {len(bot_configs)} bot configs")
    except Exception as e:
        logger.error(f"Error loading bot configs: {e}")
        bot_configs = {}


def save_channel_configs():
    """Save channel configurations to file."""
    try:
        with open(CHANNEL_CONFIGS_FILE, 'w') as f:
            json.dump(channel_configs, f)
        logger.info(f"Saved {len(channel_configs)} channel configs")
    except Exception as e:
        logger.error(f"Error saving channel configs: {e}")


def save_bot_configs():
    """Save bot configurations to file."""
    try:
        with open(BOT_CONFIGS_FILE, 'w') as f:
            json.dump(bot_configs, f)
        logger.info(f"Saved {len(bot_configs)} bot configs")
    except Exception as e:
        logger.error(f"Error saving bot configs: {e}")




# In-memory storage for channel configurations
channel_configs = {}

# Bot configs storage
bot_configs = {}

# Rate limiting storage (per channel)
rate_limits = {}

# Per-channel Gemini model and system prompt cache
channel_gemini_models = {}  # {channel_id: {'model': model, 'system_prompt': str}}

# Active bot instances: { channel_id: {'thread': thread, 'bot': bot, 'loop': loop} }
active_bots = {}

# Cooldown tracking per channel: { "channel_id:user_id": datetime }
bot_user_cooldowns = {}

# Load saved configs on startup
load_configs()


# Ensure CORS headers are always set
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-Requested-With')
    response.headers.add('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
    return response


# Handle preflight OPTIONS requests
@app.route('/api/<path:path>', methods=['OPTIONS'])
def handle_options(path):
    return '', 204


def get_extension_secret():
    """Get and decode the Twitch extension secret."""
    if not TWITCH_EXTENSION_SECRET:
        logger.warning("[Secret] TWITCH_EXTENSION_SECRET is not set")
        return None
    try:
        logger.info(f"[Secret] Raw secret length: {len(TWITCH_EXTENSION_SECRET)}")
        # Twitch secrets are base64 encoded
        decoded = base64.b64decode(TWITCH_EXTENSION_SECRET)
        logger.info(f"[Secret] Decoded secret length: {len(decoded)} bytes")
        return decoded
    except Exception as e:
        logger.error(f"[Secret] Failed to decode extension secret: {e}")
        return None


def verify_twitch_jwt(f):
    """Decorator to verify Twitch extension JWT tokens."""
    @wraps(f)
    def decorated(*args, **kwargs):
        logger.info(f"[JWT Verify] {request.method} {request.path}")
        auth_header = request.headers.get('Authorization', '')
        logger.info(f"[JWT Verify] Auth header present: {bool(auth_header)}, starts with Bearer: {auth_header.startswith('Bearer ')}")
        
        if not auth_header.startswith('Bearer '):
            logger.warning("[JWT Verify] Missing or invalid Authorization header")
            return jsonify({'error': 'Missing or invalid Authorization header'}), 401
        
        token = auth_header[7:]  # Remove 'Bearer ' prefix
        logger.info(f"[JWT Verify] Token length: {len(token)}")
        
        # In development/testing, allow bypass if no secret configured
        if not TWITCH_EXTENSION_SECRET:
            logger.warning("No TWITCH_EXTENSION_SECRET set - skipping JWT verification")
            # Extract channel_id from request body for testing (POST) or query params (GET)
            if request.json:
                request.channel_id = request.json.get('channelId', 'test_channel')
            else:
                request.channel_id = request.args.get('channelId', 'test_channel')
            request.user_id = 'test_user'
            request.role = 'broadcaster'
            logger.info(f"[JWT Verify] Test mode - channel_id={request.channel_id}")
            return f(*args, **kwargs)
        
        try:
            secret = get_extension_secret()
            if not secret:
                logger.error("[JWT Verify] Failed to get extension secret")
                return jsonify({'error': 'Server configuration error'}), 500
            
            # Decode and verify JWT
            decoded = jwt.decode(
                token,
                secret,
                algorithms=['HS256'],
                options={'verify_exp': True}
            )
            
            # Extract relevant fields from JWT
            request.channel_id = decoded.get('channel_id')
            request.user_id = decoded.get('user_id', decoded.get('opaque_user_id'))
            request.role = decoded.get('role', 'viewer')
            
            logger.info(f"[JWT Verify] Success - channel_id={request.channel_id}, role={request.role}")
            
            if not request.channel_id:
                logger.warning("[JWT Verify] Token missing channel_id")
                return jsonify({'error': 'Invalid token: missing channel_id'}), 401
            
            return f(*args, **kwargs)
            
        except jwt.ExpiredSignatureError:
            logger.warning("[JWT Verify] Token expired")
            return jsonify({'error': 'Token has expired'}), 401
        except jwt.InvalidTokenError as e:
            logger.error(f"[JWT Verify] Invalid token error: {type(e).__name__}: {e}")
            # Log first/last few chars of token for debugging (not full token for security)
            if len(token) > 20:
                logger.error(f"[JWT Verify] Token preview: {token[:10]}...{token[-10:]}")
            return jsonify({'error': 'Invalid token'}), 401
        except Exception as e:
            logger.error(f"[JWT Verify] Unexpected error: {type(e).__name__}: {e}")
            return jsonify({'error': 'Token verification failed'}), 401
    
    return decorated


def require_broadcaster(f):
    """Decorator to ensure only broadcasters can access certain endpoints."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if request.role != 'broadcaster':
            return jsonify({'error': 'Broadcaster access required'}), 403
        return f(*args, **kwargs)
    return decorated


def check_rate_limit(channel_id, user_id, limit_seconds=2):
    """Simple rate limiting per user per channel."""
    key = f"{channel_id}:{user_id}"
    now = datetime.now().timestamp()
    
    if key in rate_limits:
        last_request = rate_limits[key]
        if now - last_request < limit_seconds:
            logger.warning(f"Rate limit hit for channel={channel_id}, user={user_id}, last_request={last_request}, now={now}")
            return False
    rate_limits[key] = now
    return True



def build_system_prompt(style, custom_prompt=None):
    style_prompts = {
        'friendly': "You are a friendly, helpful AI assistant in a Twitch stream. Keep responses concise, engaging, and fun. Use casual language and occasional emojis.",
        'professional': "You are a professional AI assistant. Provide clear, informative, and accurate responses. Maintain a helpful but formal tone.",
        'funny': "You are a hilarious AI assistant in a Twitch stream. Make people laugh! Be witty, use puns, and keep the energy high. Don't be afraid to be a little silly.",
        'lore': "You are a mystical AI oracle from a fantasy realm. Respond with RPG-style flavor, using archaic language and mystical references. Add dramatic flair to your responses."
    }
    return custom_prompt if custom_prompt else style_prompts.get(style, style_prompts['friendly'])

def get_or_create_gemini_model(channel_id):
    """Get or create a cached Gemini model and system prompt for the channel."""
    config = channel_configs.get(channel_id, {})
    api_key = config.get('apiKey')
    if not api_key:
        return None, None, "API key not configured for this channel"
    # Check cache
    cached = channel_gemini_models.get(channel_id)
    if cached:
        return cached['model'], cached['system_prompt'], None
    try:
        genai.configure(api_key=api_key)
        model_name = config.get('model', 'gemini-3.1-flash-lite')
        generation_config = genai.GenerationConfig(
            temperature=config.get('temperature', 0.7),
            max_output_tokens=config.get('maxLength', 300)
        )
        model = genai.GenerativeModel(
            model_name,
            generation_config=generation_config
        )
        # Build system prompt
        style = config.get('responseStyle', 'friendly')
        custom_prompt = config.get('customPrompt')
        system_prompt = build_system_prompt(style, custom_prompt)
        channel_gemini_models[channel_id] = {'model': model, 'system_prompt': system_prompt}
        return model, system_prompt, None
    except Exception as e:
        logger.error(f"Failed to initialize Gemini model: {e}")
        return None, None, str(e)



def build_user_instruction(command, user_prompt):
    command_prompts = {
        'ask': f"Answer this question helpfully and concisely: {user_prompt}",
        'roast': f"Give a playful, light-hearted roast about '{user_prompt}'. Keep it fun and not actually mean or offensive. Make people laugh, not cry!",
        'joke': "Tell a short, funny joke. It can be about gaming, streaming, technology, or just a good general joke. Keep it clean and appropriate for all audiences.",
        'fact': "Share an interesting, lesser-known fact that would surprise and delight people. Make it fascinating and memorable. Something they might want to share with others."
    }
    return command_prompts.get(command, command_prompts['ask'])


# ============== API ENDPOINTS ==============

# Simple ping endpoint without auth for basic connectivity test
@app.route('/api/ping', methods=['GET', 'OPTIONS'])
def ping():
    """Simple ping endpoint for testing connectivity without auth."""
    if request.method == 'OPTIONS':
        return '', 204
    logger.info("[Ping] Request received")
    return jsonify({'status': 'pong', 'timestamp': datetime.now().isoformat()})


@app.route('/api/health', methods=['GET'])
@verify_twitch_jwt
def health_check():
    """Health check endpoint - also returns if API key is configured."""
    logger.info(f"[Health Check] Request from channel_id={getattr(request, 'channel_id', 'unknown')}")
    channel_id = request.channel_id
    config = channel_configs.get(channel_id, {})
    
    result = {
        'status': 'ok',
        'hasApiKey': bool(config.get('apiKey')),
        'model': config.get('model', 'not set')
    }
    logger.info(f"[Health Check] Response: {result}")
    return jsonify(result)


@app.route('/api/config', methods=['POST'])
@verify_twitch_jwt
@require_broadcaster
def save_config():
    """Save channel configuration (broadcaster only)."""
    try:
        data = request.json
        channel_id = request.channel_id
        
        # Validate API key if provided
        api_key = data.get('apiKey')
        selected_model = 'gemini-3.1-flash-lite'
        
        if api_key:
            # Test the API key with the selected model
            try:
                genai.configure(api_key=api_key)
                test_model = genai.GenerativeModel(selected_model)
                # Quick test to verify the key works
                test_model.generate_content("Hi", generation_config=genai.GenerationConfig(max_output_tokens=10))
            except Exception as e:
                return jsonify({'error': f'Invalid API key or model: {str(e)}'}), 400
        
        # Store configuration
        if channel_id not in channel_configs:
            channel_configs[channel_id] = {}
        
        # Update config (only update provided fields)
        if api_key:
            channel_configs[channel_id]['apiKey'] = api_key
        if 'model' in data:
            channel_configs[channel_id]['model'] = data['model']
        if 'temperature' in data:
            channel_configs[channel_id]['temperature'] = data['temperature']
        if 'maxLength' in data:
            channel_configs[channel_id]['maxLength'] = data['maxLength']
        if 'responseStyle' in data:
            channel_configs[channel_id]['responseStyle'] = data['responseStyle']
        if 'customPrompt' in data:
            channel_configs[channel_id]['customPrompt'] = data['customPrompt']
        
        # Persist to file
        save_channel_configs()
        
        logger.info(f"Configuration saved for channel {channel_id}")
        
        return jsonify({
            'success': True,
            'message': 'Configuration saved successfully'
        })
        
    except Exception as e:
        logger.error(f"Error saving config: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/gemini', methods=['POST'])
@verify_twitch_jwt
def gemini_handler():
    """Main endpoint for Gemini AI requests."""
    try:
        data = request.json
        channel_id = getattr(request, 'channel_id', None)
        user_id = getattr(request, 'user_id', None)
        logger.info(f"[Gemini Handler] Incoming request: channel_id={channel_id}, user_id={user_id}, data={data}")

        prompt = data.get('prompt', '')
        command = data.get('command', 'ask')
        style = data.get('style', 'friendly')

        # Rate limiting
        if not check_rate_limit(channel_id, user_id):
            logger.error(f"429 Too Many Requests: channel={channel_id}, user={user_id}")
            return jsonify({'error': 'Too many requests. Please wait a moment.'}), 429


        # Get Gemini model and system prompt
        model, system_prompt, error = get_or_create_gemini_model(channel_id)
        if error:
            logger.error(f"Gemini model error: {error} for channel_id={channel_id}")
            return jsonify({'error': error}), 400

        # Only send user message as input, system prompt is pre-set
        user_instruction = build_user_instruction(command, prompt)
        logger.info(f"[Gemini Handler] Using system prompt: {system_prompt}")
        logger.info(f"[Gemini Handler] User instruction: {user_instruction}")

        # Generate response
        try:
            response = model.generate_content(user_instruction, system_instruction=system_prompt)
            reply = response.text.strip()
            logger.info(f"[Gemini Handler] Gemini reply: {reply}")
        except Exception as e:
            logger.error(f"Gemini API quota or error: {e}")
            return jsonify({'reply': "Sorry, the AI quota was exceeded or the service is unavailable. Please try again later! 😅"}), 503

        # Ensure response fits within max length
        config = channel_configs.get(channel_id, {})
        max_length = config.get('maxLength', 450)
        if len(reply) > max_length:
            truncated = reply[:max_length]
            last_period = truncated.rfind('.')
            last_question = truncated.rfind('?')
            last_exclaim = truncated.rfind('!')
            best_cut = max(last_period, last_question, last_exclaim)
            if best_cut > max_length * 0.6:
                reply = truncated[:best_cut + 1]
            else:
                reply = truncated.rsplit(' ', 1)[0] + '...'
            logger.info(f"[Gemini Handler] Truncated reply: {reply}")
        logger.info(f"[Gemini Handler] Sending response for channel_id={channel_id}, user_id={user_id}")
        return jsonify({'reply': reply})

    except Exception as e:
        logger.error(f"Gemini API error: {e}")
        return jsonify({
            'reply': "Sorry, I encountered an error. Please try again! 😅"
        }), 500
def save_config():
    """Save channel configuration (broadcaster only)."""
    try:
        data = request.json
        channel_id = request.channel_id

        # Validate API key if provided
        api_key = data.get('apiKey')
        selected_model = 'gemini-3.1-flash-lite'

        if api_key:
            # Test the API key with the selected model
            try:
                genai.configure(api_key=api_key)
                test_model = genai.GenerativeModel(selected_model)
                test_model.generate_content("Hi", generation_config=genai.GenerationConfig(max_output_tokens=10))
            except Exception as e:
                return jsonify({'error': f'Invalid API key or model: {str(e)}'}), 400

        # Store configuration
        if channel_id not in channel_configs:
            channel_configs[channel_id] = {}

        # Update config (only update provided fields)
        if api_key:
            channel_configs[channel_id]['apiKey'] = api_key
        if 'model' in data:
            channel_configs[channel_id]['model'] = data['model']
        if 'temperature' in data:
            channel_configs[channel_id]['temperature'] = data['temperature']
        if 'maxLength' in data:
            channel_configs[channel_id]['maxLength'] = data['maxLength']
        if 'responseStyle' in data:
            channel_configs[channel_id]['responseStyle'] = data['responseStyle']
        if 'customPrompt' in data:
            channel_configs[channel_id]['customPrompt'] = data['customPrompt']

        # Persist to file
        save_channel_configs()

        # Refresh Gemini model cache for this channel
        if channel_id in channel_gemini_models:
            del channel_gemini_models[channel_id]

        logger.info(f"Configuration saved for channel {channel_id}")

        return jsonify({
            'success': True,
            'message': 'Configuration saved successfully'
        })

    except Exception as e:
        logger.error(f"Error saving config: {e}")
        return jsonify({'error': str(e)}), 500
def save_bot_config():
    """Save bot configuration for a channel (broadcaster only)."""
    try:
        data = request.json
        channel_id = request.channel_id
        
        enabled = data.get('enabled', False)
        twitch_token = data.get('twitchToken', '')
        gemini_api_key = data.get('geminiApiKey', '')
        bot_prefix = data.get('botPrefix', '!')
        cooldown = data.get('cooldown', 5)
        
        if enabled:
            if not twitch_token:
                return jsonify({'error': 'Twitch OAuth token is required'}), 400
            if not gemini_api_key:
                return jsonify({'error': 'Gemini API key is required'}), 400
        
        # Store bot config
        bot_configs[channel_id] = {
            'enabled': enabled,
            'twitchToken': twitch_token,
            'geminiApiKey': gemini_api_key,
            'botPrefix': bot_prefix,
            'cooldown': cooldown
        }
        
        # Persist to file
        save_bot_configs()
        
        logger.info(f"Bot config saved for channel {channel_id}, enabled={enabled}")
        
        # Start or stop bot based on config
        if enabled:
            start_channel_bot(channel_id)
        else:
            stop_channel_bot(channel_id)
        
        return jsonify({
            'success': True,
            'message': 'Bot enabled!' if enabled else 'Bot disabled',
            'bot_running': channel_id in active_bots
        })
        
    except Exception as e:
        logger.error(f"Error saving bot config: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/bot/status', methods=['GET'])
@verify_twitch_jwt
def get_bot_status():
    """Get bot status for a channel."""
    channel_id = request.channel_id
    config = bot_configs.get(channel_id, {})
    
    return jsonify({
        'configured': bool(config),
        'enabled': config.get('enabled', False),
        'running': channel_id in active_bots
    })


def bot_check_cooldown(channel_id: str, user_id: str, cooldown_seconds: int) -> bool:
    """Check if user is on cooldown. Returns True if allowed to use command."""
    key = f"{channel_id}:{user_id}"
    now = datetime.now()
    if key in bot_user_cooldowns:
        if now < bot_user_cooldowns[key]:
            return False
    bot_user_cooldowns[key] = now + timedelta(seconds=cooldown_seconds)
    return True


def bot_get_remaining_cooldown(channel_id: str, user_id: str) -> int:
    """Get remaining cooldown seconds for a user."""
    key = f"{channel_id}:{user_id}"
    if key not in bot_user_cooldowns:
        return 0
    remaining = (bot_user_cooldowns[key] - datetime.now()).total_seconds()
    return max(0, int(remaining))


async def bot_generate_response(gemini_api_key: str, prompt: str, command: str, channel_id: str = None) -> str:
    """Generate a response using Gemini AI for the bot."""
    
    # Get custom config from channel if available
    custom_prompt = None
    response_style = 'friendly'
    if channel_id and channel_id in channel_configs:
        config = channel_configs[channel_id]
        custom_prompt = config.get('customPrompt')
        response_style = config.get('responseStyle', 'friendly')
    
    style_prompts = {
        'friendly': "You are a friendly, fun AI assistant in a Twitch chat. Keep responses SHORT (under 400 chars), engaging, and use casual language.",
        'professional': "You are a professional AI assistant in a Twitch chat. Provide clear, informative responses under 400 chars.",
        'funny': "You are a hilarious AI assistant in a Twitch chat. Make people laugh! Keep responses under 400 chars.",
        'lore': "You are an AI from a fantasy RPG world in a Twitch chat. Respond with epic flavor, under 400 chars."
    }
    
    style_prompt = style_prompts.get(response_style, style_prompts['friendly'])
    
    # Add custom prompt if set
    if custom_prompt:
        style_prompt = f"{style_prompt}\n\nAdditional instructions: {custom_prompt}"
    
    command_prompts = {
        'ask': f"Answer this concisely: {prompt}",
        'roast': f"Give a playful, light-hearted roast about '{prompt}'. Keep it fun, NOT mean. Make people laugh!",
        'joke': "Tell a short, funny joke. Gaming/streaming related is great, but any clean joke works.",
        'fact': "Share one interesting, surprising fact. Make it memorable!"
    }
    
    full_prompt = f"{style_prompt}\n\n{command_prompts.get(command, command_prompts['ask'])}"
    
    try:
        genai.configure(api_key=gemini_api_key)
        model = genai.GenerativeModel('gemini-3.1-flash-lite')
        
        response = await asyncio.to_thread(
            model.generate_content,
            full_prompt,
            generation_config=genai.GenerationConfig(
                max_output_tokens=200,
                temperature=0.8
            )
        )
        
        reply = response.text.strip()
        
        # Truncate if too long
        if len(reply) > 450:
            truncated = reply[:450]
            last_sentence = max(truncated.rfind('.'), truncated.rfind('!'), truncated.rfind('?'))
            if last_sentence > 225:
                reply = truncated[:last_sentence + 1]
            else:
                reply = truncated.rsplit(' ', 1)[0] + '...'
        
        return reply
        
    except Exception as e:
        logger.error(f"Bot Gemini error: {e}")
        return "Oops, my brain glitched! Try again? 🤖"


def run_channel_bot(channel_id: str, config: dict):
    """Run a bot for a specific channel."""
    try:
        from twitchio.ext import commands as twitch_commands
        
        twitch_token = config['twitchToken']
        gemini_api_key = config['geminiApiKey']
        bot_prefix = config.get('botPrefix', '!')
        cooldown = config.get('cooldown', 5)
        
        # We need to get the channel name from the token
        # For now, we'll use a simple approach - the streamer uses their own token
        # which will connect to their channel
        
        class ChannelBot(twitch_commands.Bot):
            def __init__(self):
                super().__init__(
                    token=twitch_token,
                    prefix=bot_prefix,
                    initial_channels=[]  # Will join on ready using nick
                )
                self.channel_id = channel_id
                self.gemini_key = gemini_api_key
                self.cooldown = cooldown
                self.target_channel = None
                self._should_stop = False
            
            async def event_ready(self):
                # Join the channel that matches the bot's username
                self.target_channel = self.nick.lower()
                await self.join_channels([self.target_channel])
                logger.info(f'Bot ready for channel {self.target_channel} (ID: {self.channel_id})')
            
            async def event_message(self, message):
                if message.echo or self._should_stop:
                    return
                await self.handle_commands(message)
            
            @twitch_commands.command(name='help')
            async def cmd_help(self, ctx):
                await ctx.reply(f"🤖 Commands: {bot_prefix}ask [question] | {bot_prefix}joke | {bot_prefix}fact | {bot_prefix}roast [@user]")
            
            @twitch_commands.command(name='ask')
            async def cmd_ask(self, ctx, *, question: str = None):
                if not question:
                    await ctx.reply(f"Ask me something! Example: {bot_prefix}ask What's the meaning of life?")
                    return
                if not bot_check_cooldown(self.channel_id, ctx.author.id, self.cooldown):
                    await ctx.reply(f"Cooldown! Wait {bot_get_remaining_cooldown(self.channel_id, ctx.author.id)}s ⏳")
                    return
                response = await bot_generate_response(self.gemini_key, question, 'ask', self.channel_id)
                await ctx.reply(response)
            
            @twitch_commands.command(name='joke')
            async def cmd_joke(self, ctx):
                if not bot_check_cooldown(self.channel_id, ctx.author.id, self.cooldown):
                    await ctx.reply(f"Cooldown! Wait {bot_get_remaining_cooldown(self.channel_id, ctx.author.id)}s ⏳")
                    return
                response = await bot_generate_response(self.gemini_key, '', 'joke', self.channel_id)
                await ctx.reply(f"😂 {response}")
            
            @twitch_commands.command(name='fact')
            async def cmd_fact(self, ctx):
                if not bot_check_cooldown(self.channel_id, ctx.author.id, self.cooldown):
                    await ctx.reply(f"Cooldown! Wait {bot_get_remaining_cooldown(self.channel_id, ctx.author.id)}s ⏳")
                    return
                response = await bot_generate_response(self.gemini_key, '', 'fact', self.channel_id)
                await ctx.reply(f"📊 {response}")
            
            @twitch_commands.command(name='roast')
            async def cmd_roast(self, ctx, *, target: str = None):
                if not bot_check_cooldown(self.channel_id, ctx.author.id, self.cooldown):
                    await ctx.reply(f"Cooldown! Wait {bot_get_remaining_cooldown(self.channel_id, ctx.author.id)}s ⏳")
                    return
                if not target:
                    target = ctx.author.name
                target = target.lstrip('@')
                response = await bot_generate_response(self.gemini_key, target, 'roast', self.channel_id)
                await ctx.reply(f"🔥 @{target} {response}")
        
        # Run the bot
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        bot = ChannelBot()
        
        # Store bot and loop references for proper cleanup
        active_bots[channel_id] = {'bot': bot, 'loop': loop}
        
        loop.run_until_complete(bot.start())
        
    except Exception as e:
        logger.error(f"Bot error for channel {channel_id}: {e}")
    finally:
        # Remove from active bots when done
        if channel_id in active_bots:
            del active_bots[channel_id]


def start_channel_bot(channel_id: str):
    """Start a bot for a specific channel."""
    # Stop existing bot first
    stop_channel_bot(channel_id)
    
    config = bot_configs.get(channel_id)
    if not config or not config.get('enabled'):
        return
    
    logger.info(f"Starting bot for channel {channel_id}...")
    thread = threading.Thread(target=run_channel_bot, args=(channel_id, config), daemon=True)
    thread.start()
    # Note: active_bots[channel_id] is set inside run_channel_bot with bot/loop references
    logger.info(f"Bot thread started for channel {channel_id}")


def stop_channel_bot(channel_id: str):
    """Stop a bot for a specific channel."""
    if channel_id in active_bots:
        logger.info(f"Stopping bot for channel {channel_id}")
        bot_info = active_bots[channel_id]
        
        # Properly close the bot
        if isinstance(bot_info, dict) and 'bot' in bot_info and 'loop' in bot_info:
            bot = bot_info['bot']
            loop = bot_info['loop']
            
            # Signal the bot to stop
            bot._should_stop = True
            
            # Schedule close on the bot's event loop
            try:
                loop.call_soon_threadsafe(lambda: asyncio.ensure_future(bot.close()))
            except Exception as e:
                logger.error(f"Error closing bot for {channel_id}: {e}")
        
        del active_bots[channel_id]
        logger.info(f"Bot stopped for channel {channel_id}")


def start_enabled_bots():
    """Start all bots that were enabled (called on server startup)."""
    enabled_count = 0
    for channel_id, config in bot_configs.items():
        if config.get('enabled') and config.get('twitchToken') and config.get('geminiApiKey'):
            logger.info(f"Auto-starting bot for channel {channel_id}...")
            start_channel_bot(channel_id)
            enabled_count += 1
    logger.info(f"Auto-started {enabled_count} bots")


# Auto-start enabled bots on server startup
start_enabled_bots()


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    
    logger.info(f"Starting Gemini Stream Assistant on port {port}")
    logger.info(f"TWITCH_EXTENSION_SECRET configured: {bool(TWITCH_EXTENSION_SECRET)}")
    
    app.run(host='0.0.0.0', port=port, debug=debug)
