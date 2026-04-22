import os
import time
import logging
import threading
import asyncio
from datetime import datetime, timedelta
from functools import wraps

import requests
import jwt
from cryptography.fernet import Fernet
from flask import Flask, request, jsonify
from flask_cors import CORS
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from models import Base, ChannelConfig, BotInstance
import ai_providers
import bot_manager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app, origins='*', methods=['GET', 'POST', 'OPTIONS'],
     allow_headers=['Content-Type', 'Authorization'])

# ── Config ────────────────────────────────────────────────────────────────────
TWITCH_CLIENT_ID     = os.environ['TWITCH_CLIENT_ID']
TWITCH_CLIENT_SECRET = os.environ['TWITCH_CLIENT_SECRET']
SECRET_KEY           = os.environ['SECRET_KEY']           # JWT signing
ENCRYPTION_KEY       = os.environ['ENCRYPTION_KEY'].encode()  # Fernet key
DATABASE_URL         = os.environ.get('DATABASE_URL', 'postgresql://postgres:postgres@db:5432/twitchai')

# ── Database ──────────────────────────────────────────────────────────────────
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

def init_db():
    Base.metadata.create_all(engine)
    logger.info('Database initialized')

# ── Encryption ────────────────────────────────────────────────────────────────
_fernet = Fernet(ENCRYPTION_KEY)

def encrypt(value: str) -> str:
    return _fernet.encrypt(value.encode()).decode()

def decrypt(value: str) -> str:
    return _fernet.decrypt(value.encode()).decode()

# ── Auth middleware ───────────────────────────────────────────────────────────
def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization', '').removeprefix('Bearer ').strip()
        if not token:
            return jsonify({'error': 'Unauthorized'}), 401
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
            request.channel_id = payload['channel_id']
            request.username   = payload['username']
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Invalid token'}), 401
        return f(*args, **kwargs)
    return decorated

# ── Helpers ───────────────────────────────────────────────────────────────────
def _make_jwt(channel_id: str, username: str) -> str:
    payload = {
        'channel_id': channel_id,
        'username': username,
        'exp': datetime.utcnow() + timedelta(days=30),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm='HS256')


def _build_ai_fn(config: ChannelConfig):
    """Return an async fn(prompt, command) -> str for the bot to call."""
    api_key       = decrypt(config.api_key_enc) if config.api_key_enc else ''
    provider      = config.ai_provider
    model_name    = config.ai_model
    system_prompt = config.system_prompt or ''
    temperature   = config.temperature
    max_tokens    = config.max_tokens
    channel_id    = config.channel_id

    command_templates = {
        'ask':   lambda p: f'Answer concisely: {p}',
        'roast': lambda p: f"Playful roast of '{p}'. Fun, not mean.",
        'joke':  lambda _: 'Tell a short funny joke.',
        'fact':  lambda _: 'Share one surprising fact.',
    }

    async def generate(prompt: str, command: str) -> str:
        user_msg = command_templates.get(command, command_templates['ask'])(prompt)
        return await ai_providers.generate(
            channel_id=channel_id,
            provider=provider,
            model_name=model_name,
            api_key=api_key,
            system_prompt=system_prompt,
            user_message=user_msg,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    return generate


def _update_activity(channel_id: str):
    with SessionLocal() as session:
        bot = session.get(BotInstance, channel_id)
        if bot:
            bot.last_activity = datetime.utcnow()
            bot.updated_at    = datetime.utcnow()
            session.commit()


def _start_bot_for_channel(channel_id: str, session: Session):
    config   = session.get(ChannelConfig, channel_id)
    bot_inst = session.get(BotInstance, channel_id)
    if not config or not bot_inst or not config.twitch_bot_token_enc:
        return

    bot_config = {
        'twitch_bot_token':    decrypt(config.twitch_bot_token_enc),
        'twitch_channel_name': config.twitch_channel_name or config.twitch_username,
        'bot_prefix':          config.bot_prefix,
        'cooldown':            config.cooldown,
    }
    bot_manager.start(
        channel_id=channel_id,
        config=bot_config,
        on_activity=_update_activity,
        ai_generate_fn=_build_ai_fn(config),
    )


# ── 5-hour inactivity monitor ─────────────────────────────────────────────────
def _inactivity_monitor():
    while True:
        time.sleep(300)
        try:
            with SessionLocal() as session:
                cutoff = datetime.utcnow() - timedelta(hours=5)
                stale = session.query(BotInstance).filter(
                    BotInstance.enabled == True,
                    BotInstance.last_activity < cutoff,
                ).all()
                for b in stale:
                    logger.info(f'Auto-stopping bot {b.channel_id} (5h inactivity)')
                    bot_manager.stop(b.channel_id)
                    b.enabled    = False
                    b.updated_at = datetime.utcnow()
                session.commit()
        except Exception as e:
            logger.error(f'Inactivity monitor error: {e}')


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route('/api/auth/twitch', methods=['POST'])
def auth_twitch():
    data         = request.json or {}
    code         = data.get('code')
    redirect_uri = data.get('redirect_uri')

    if not code or not redirect_uri:
        return jsonify({'error': 'Missing code or redirect_uri'}), 400

    # Exchange code for access token
    resp = requests.post('https://id.twitch.tv/oauth2/token', data={
        'client_id':     TWITCH_CLIENT_ID,
        'client_secret': TWITCH_CLIENT_SECRET,
        'code':          code,
        'grant_type':    'authorization_code',
        'redirect_uri':  redirect_uri,
    })
    if not resp.ok:
        return jsonify({'error': 'Failed to exchange token'}), 400

    access_token = resp.json().get('access_token')
    if not access_token:
        return jsonify({'error': 'No access token returned'}), 400

    # Get Twitch user info
    user_resp = requests.get('https://api.twitch.tv/helix/users', headers={
        'Authorization': f'Bearer {access_token}',
        'Client-Id':     TWITCH_CLIENT_ID,
    })
    if not user_resp.ok or not user_resp.json().get('data'):
        return jsonify({'error': 'Failed to fetch user info'}), 400

    twitch_user  = user_resp.json()['data'][0]
    channel_id   = twitch_user['id']
    username     = twitch_user['login']
    display_name = twitch_user.get('display_name', username)
    profile_img  = twitch_user.get('profile_image_url', '')

    with SessionLocal() as session:
        config = session.get(ChannelConfig, channel_id)
        if not config:
            config = ChannelConfig(
                channel_id=channel_id,
                twitch_username=username,
                twitch_channel_name=username,
            )
            session.add(config)

        bot_inst = session.get(BotInstance, channel_id)
        if not bot_inst:
            bot_inst = BotInstance(channel_id=channel_id)
            session.add(bot_inst)

        config.twitch_username = username
        config.updated_at      = datetime.utcnow()
        session.commit()

    token = _make_jwt(channel_id, username)
    return jsonify({
        'token': token,
        'user': {
            'channel_id':    channel_id,
            'username':      username,
            'display_name':  display_name,
            'profile_image': profile_img,
        },
    })


@app.route('/api/auth/me', methods=['GET'])
@require_auth
def auth_me():
    with SessionLocal() as session:
        config = session.get(ChannelConfig, request.channel_id)
        if not config:
            return jsonify({'error': 'User not found'}), 404
        return jsonify({
            'channel_id':   config.channel_id,
            'username':     config.twitch_username,
            'display_name': config.twitch_username,
        })


@app.route('/api/providers', methods=['GET'])
def get_providers():
    return jsonify(ai_providers.PROVIDERS)


@app.route('/api/config', methods=['GET'])
@require_auth
def get_config():
    with SessionLocal() as session:
        config = session.get(ChannelConfig, request.channel_id)
        if not config:
            return jsonify({'error': 'Not found'}), 404
        return jsonify({
            'ai_provider':          config.ai_provider,
            'ai_model':             config.ai_model,
            'has_api_key':          bool(config.api_key_enc),
            'system_prompt':        config.system_prompt,
            'temperature':          config.temperature,
            'max_tokens':           config.max_tokens,
            'bot_prefix':           config.bot_prefix,
            'cooldown':             config.cooldown,
            'has_bot_token':        bool(config.twitch_bot_token_enc),
            'twitch_channel_name':  config.twitch_channel_name,
        })


@app.route('/api/config', methods=['POST'])
@require_auth
def save_config():
    data = request.json or {}
    with SessionLocal() as session:
        config = session.get(ChannelConfig, request.channel_id)
        if not config:
            return jsonify({'error': 'Not found'}), 404

        if 'ai_provider' in data:
            config.ai_provider = data['ai_provider']
        if 'ai_model' in data:
            config.ai_model = data['ai_model']
        if data.get('api_key'):
            config.api_key_enc = encrypt(data['api_key'])
        if 'system_prompt' in data:
            config.system_prompt = data['system_prompt']
        if 'temperature' in data:
            config.temperature = float(data['temperature'])
        if 'max_tokens' in data:
            config.max_tokens = int(data['max_tokens'])
        if 'bot_prefix' in data:
            config.bot_prefix = data['bot_prefix'] or '!'
        if 'cooldown' in data:
            config.cooldown = int(data['cooldown'])
        if data.get('twitch_bot_token'):
            token = data['twitch_bot_token']
            if not token.startswith('oauth:'):
                token = 'oauth:' + token
            config.twitch_bot_token_enc = encrypt(token)
        if 'twitch_channel_name' in data:
            config.twitch_channel_name = data['twitch_channel_name'] or config.twitch_username

        config.updated_at = datetime.utcnow()
        session.commit()

        # Invalidate model cache so new settings take effect
        ai_providers.invalidate_cache(request.channel_id)

    return jsonify({'success': True})


@app.route('/api/bot/status', methods=['GET'])
@require_auth
def bot_status():
    with SessionLocal() as session:
        bot_inst = session.get(BotInstance, request.channel_id)
        running  = bot_manager.is_running(request.channel_id)
        return jsonify({
            'running':       running,
            'enabled':       bot_inst.enabled if bot_inst else False,
            'last_activity': bot_inst.last_activity.isoformat() if bot_inst and bot_inst.last_activity else None,
        })


@app.route('/api/bot/start', methods=['POST'])
@require_auth
def bot_start():
    with SessionLocal() as session:
        config   = session.get(ChannelConfig, request.channel_id)
        bot_inst = session.get(BotInstance, request.channel_id)

        if not config or not config.api_key_enc:
            return jsonify({'error': 'API key not configured'}), 400
        if not config.twitch_bot_token_enc:
            return jsonify({'error': 'Twitch bot token not configured'}), 400

        _start_bot_for_channel(request.channel_id, session)

        if bot_inst:
            bot_inst.enabled      = True
            bot_inst.last_activity = datetime.utcnow()
            bot_inst.updated_at   = datetime.utcnow()
        session.commit()

    return jsonify({'success': True, 'running': True})


@app.route('/api/bot/stop', methods=['POST'])
@require_auth
def bot_stop():
    bot_manager.stop(request.channel_id)
    with SessionLocal() as session:
        bot_inst = session.get(BotInstance, request.channel_id)
        if bot_inst:
            bot_inst.enabled    = False
            bot_inst.updated_at = datetime.utcnow()
            session.commit()
    return jsonify({'success': True, 'running': False})


@app.route('/api/generate', methods=['POST'])
@require_auth
def test_generate():
    """Quick test generation from the config page."""
    data = request.json or {}
    prompt = data.get('prompt', 'Say hello!')

    with SessionLocal() as session:
        config = session.get(ChannelConfig, request.channel_id)
        if not config or not config.api_key_enc:
            return jsonify({'error': 'API key not configured'}), 400

        api_key = decrypt(config.api_key_enc)

    async def _run():
        return await ai_providers.generate(
            channel_id=request.channel_id,
            provider=config.ai_provider,
            model_name=config.ai_model,
            api_key=api_key,
            system_prompt=config.system_prompt,
            user_message=prompt,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
        )

    try:
        reply = asyncio.run(_run())
        return jsonify({'reply': reply})
    except Exception as e:
        logger.error(f'Test generate error: {e}')
        return jsonify({'error': str(e)}), 500


@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})


# ── Startup ───────────────────────────────────────────────────────────────────
def _restore_active_bots():
    """On server restart, re-start bots that were enabled."""
    with SessionLocal() as session:
        enabled = session.query(BotInstance).filter(BotInstance.enabled == True).all()
        for b in enabled:
            try:
                _start_bot_for_channel(b.channel_id, session)
            except Exception as e:
                logger.error(f'Failed to restore bot {b.channel_id}: {e}')


if __name__ == '__main__' or True:
    init_db()
    threading.Thread(target=_inactivity_monitor, daemon=True).start()
    threading.Thread(target=_restore_active_bots, daemon=True).start()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=False)
