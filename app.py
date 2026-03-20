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
from datetime import datetime

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

# In-memory storage for channel configurations (MVP)
# For production, use a database (PostgreSQL, Redis, etc.)
channel_configs = {}

# Rate limiting storage (per channel)
rate_limits = {}


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
        return None
    try:
        # Twitch secrets are base64 encoded
        return base64.b64decode(TWITCH_EXTENSION_SECRET)
    except Exception as e:
        logger.error(f"Failed to decode extension secret: {e}")
        return None


def verify_twitch_jwt(f):
    """Decorator to verify Twitch extension JWT tokens."""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization', '')
        
        if not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Missing or invalid Authorization header'}), 401
        
        token = auth_header[7:]  # Remove 'Bearer ' prefix
        
        # In development/testing, allow bypass if no secret configured
        if not TWITCH_EXTENSION_SECRET:
            logger.warning("No TWITCH_EXTENSION_SECRET set - skipping JWT verification")
            # Extract channel_id from request body for testing
            request.channel_id = request.json.get('channelId', 'test_channel')
            request.user_id = 'test_user'
            request.role = 'broadcaster'
            return f(*args, **kwargs)
        
        try:
            secret = get_extension_secret()
            if not secret:
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
            
            if not request.channel_id:
                return jsonify({'error': 'Invalid token: missing channel_id'}), 401
            
            return f(*args, **kwargs)
            
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token has expired'}), 401
        except jwt.InvalidTokenError as e:
            logger.error(f"JWT validation error: {e}")
            return jsonify({'error': 'Invalid token'}), 401
    
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
            return False
    
    rate_limits[key] = now
    return True


def get_gemini_model(channel_id):
    """Get or create a Gemini model for the channel."""
    config = channel_configs.get(channel_id, {})
    api_key = config.get('apiKey')
    
    if not api_key:
        return None, "API key not configured for this channel"
    
    try:
        genai.configure(api_key=api_key)
        model_name = config.get('model', 'gemini-pro')
        
        # Configure generation settings
        generation_config = genai.GenerationConfig(
            temperature=config.get('temperature', 0.7),
            max_output_tokens=config.get('maxLength', 300)
        )
        
        model = genai.GenerativeModel(
            model_name,
            generation_config=generation_config
        )
        
        return model, None
        
    except Exception as e:
        logger.error(f"Failed to initialize Gemini model: {e}")
        return None, str(e)


def build_prompt(command, user_prompt, style, custom_prompt=None):
    """Build the full prompt for Gemini based on command type and style."""
    
    # Style-based system prompts
    style_prompts = {
        'friendly': "You are a friendly, helpful AI assistant in a Twitch stream. Keep responses concise, engaging, and fun. Use casual language and occasional emojis.",
        'professional': "You are a professional AI assistant. Provide clear, informative, and accurate responses. Maintain a helpful but formal tone.",
        'funny': "You are a hilarious AI assistant in a Twitch stream. Make people laugh! Be witty, use puns, and keep the energy high. Don't be afraid to be a little silly.",
        'lore': "You are a mystical AI oracle from a fantasy realm. Respond with RPG-style flavor, using archaic language and mystical references. Add dramatic flair to your responses."
    }
    
    # Command-specific prompts
    command_prompts = {
        'ask': f"Answer this question helpfully and concisely: {user_prompt}",
        'roast': f"Give a playful, light-hearted roast about '{user_prompt}'. Keep it fun and not actually mean or offensive. Make people laugh, not cry!",
        'joke': "Tell a short, funny joke. It can be about gaming, streaming, technology, or just a good general joke. Keep it clean and appropriate for all audiences.",
        'fact': "Share an interesting, lesser-known fact that would surprise and delight people. Make it fascinating and memorable. Something they might want to share with others."
    }
    
    # Build the full prompt
    system_prompt = custom_prompt if custom_prompt else style_prompts.get(style, style_prompts['friendly'])
    user_instruction = command_prompts.get(command, command_prompts['ask'])
    
    return f"{system_prompt}\n\n{user_instruction}"


# ============== API ENDPOINTS ==============

@app.route('/api/health', methods=['GET'])
@verify_twitch_jwt
def health_check():
    """Health check endpoint - also returns if API key is configured."""
    channel_id = request.channel_id
    config = channel_configs.get(channel_id, {})
    
    return jsonify({
        'status': 'ok',
        'hasApiKey': bool(config.get('apiKey')),
        'model': config.get('model', 'not set')
    })


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
        if api_key:
            # Test the API key
            try:
                genai.configure(api_key=api_key)
                test_model = genai.GenerativeModel('gemini-pro')
                # Quick test to verify the key works
                test_model.generate_content("Hi", generation_config=genai.GenerationConfig(max_output_tokens=10))
            except Exception as e:
                return jsonify({'error': f'Invalid API key: {str(e)}'}), 400
        
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
        channel_id = request.channel_id
        user_id = request.user_id
        
        prompt = data.get('prompt', '')
        command = data.get('command', 'ask')
        style = data.get('style', 'friendly')
        
        # Rate limiting
        if not check_rate_limit(channel_id, user_id):
            return jsonify({'error': 'Too many requests. Please wait a moment.'}), 429
        
        # Get channel configuration
        config = channel_configs.get(channel_id, {})
        custom_prompt = config.get('customPrompt')
        
        # Get Gemini model
        model, error = get_gemini_model(channel_id)
        if error:
            return jsonify({'error': error}), 400
        
        # Build prompt
        full_prompt = build_prompt(command, prompt, style, custom_prompt)
        
        # Generate response
        response = model.generate_content(full_prompt)
        
        # Extract and clean response text
        reply = response.text.strip()
        
        # Ensure response fits within max length
        max_length = config.get('maxLength', 450)
        if len(reply) > max_length:
            # Try to cut at a sentence boundary
            truncated = reply[:max_length]
            last_period = truncated.rfind('.')
            last_question = truncated.rfind('?')
            last_exclaim = truncated.rfind('!')
            
            best_cut = max(last_period, last_question, last_exclaim)
            if best_cut > max_length * 0.6:
                reply = truncated[:best_cut + 1]
            else:
                reply = truncated.rsplit(' ', 1)[0] + '...'
        
        return jsonify({'reply': reply})
        
    except Exception as e:
        logger.error(f"Gemini API error: {e}")
        return jsonify({
            'reply': "Sorry, I encountered an error. Please try again! 😅"
        }), 500


@app.route('/api/status', methods=['GET'])
def status():
    """Public status endpoint."""
    return jsonify({
        'status': 'online',
        'service': 'Gemini Stream Assistant',
        'version': '1.0.0'
    })


@app.route('/', methods=['GET'])
def root():
    """Root endpoint for health checks."""
    return jsonify({
        'status': 'online',
        'service': 'Gemini Stream Assistant',
        'endpoints': ['/api/status', '/api/health', '/api/config', '/api/gemini']
    })


# Error handlers
@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Endpoint not found'}), 404


@app.errorhandler(500)
def server_error(e):
    return jsonify({'error': 'Internal server error'}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    
    logger.info(f"Starting Gemini Stream Assistant on port {port}")
    logger.info(f"TWITCH_EXTENSION_SECRET configured: {bool(TWITCH_EXTENSION_SECRET)}")
    
    app.run(host='0.0.0.0', port=port, debug=debug)
