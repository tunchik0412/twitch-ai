"""Per-channel Twitch bot management."""
import asyncio
import threading
import logging
from datetime import datetime, timedelta
from typing import Callable, Optional

from twitchio.ext import commands as twitch_commands

logger = logging.getLogger(__name__)

# {channel_id: {'thread': Thread, 'bot': Bot, 'loop': EventLoop}}
active_bots: dict = {}


def is_running(channel_id: str) -> bool:
    return channel_id in active_bots


def start(channel_id: str, config: dict, on_activity: Callable[[str], None],
          ai_generate_fn: Callable):
    if channel_id in active_bots:
        logger.info(f'Bot already running for {channel_id}')
        return

    t = threading.Thread(
        target=_run_bot_thread,
        args=(channel_id, config, on_activity, ai_generate_fn),
        daemon=True,
    )
    active_bots[channel_id] = {'thread': t, 'bot': None, 'loop': None}
    t.start()
    logger.info(f'Started bot thread for channel {channel_id}')


def stop(channel_id: str):
    if channel_id not in active_bots:
        return
    info = active_bots[channel_id]
    loop = info.get('loop')
    bot = info.get('bot')
    if loop and bot:
        asyncio.run_coroutine_threadsafe(bot.close(), loop)
    active_bots.pop(channel_id, None)
    logger.info(f'Stopped bot for channel {channel_id}')


def _run_bot_thread(channel_id: str, config: dict,
                    on_activity: Callable[[str], None],
                    ai_generate_fn: Callable):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    if channel_id in active_bots:
        active_bots[channel_id]['loop'] = loop

    try:
        bot = ChannelBot(
            channel_id=channel_id,
            config=config,
            on_activity=on_activity,
            ai_generate_fn=ai_generate_fn,
        )
        if channel_id in active_bots:
            active_bots[channel_id]['bot'] = bot
        loop.run_until_complete(bot.start())
    except Exception as e:
        logger.error(f'Bot error for {channel_id}: {e}')
    finally:
        active_bots.pop(channel_id, None)
        loop.close()


class ChannelBot(twitch_commands.Bot):
    def __init__(self, channel_id: str, config: dict,
                 on_activity: Callable[[str], None],
                 ai_generate_fn: Callable):
        token = config['twitch_bot_token']
        if not token.startswith('oauth:'):
            token = 'oauth:' + token

        super().__init__(
            token=token,
            prefix=config.get('bot_prefix', '!'),
            initial_channels=[config.get('twitch_channel_name', '')],
        )
        self.channel_id = channel_id
        self.config = config
        self.on_activity = on_activity
        self.ai_generate_fn = ai_generate_fn
        self._cooldowns: dict = {}

    async def event_ready(self):
        logger.info(f'Bot ready for channel {self.channel_id} as {self.nick}')

    async def event_message(self, message):
        if message.echo:
            return
        await self.handle_commands(message)

    def _check_cooldown(self, user_id: str) -> bool:
        now = datetime.now()
        cooldown = self.config.get('cooldown', 5)
        if user_id in self._cooldowns and now < self._cooldowns[user_id]:
            return False
        self._cooldowns[user_id] = now + timedelta(seconds=cooldown)
        return True

    async def _ai_reply(self, ctx, prompt: str, command: str):
        if not self._check_cooldown(ctx.author.id):
            await ctx.reply('Cooldown! ⏳')
            return
        if self.on_activity:
            self.on_activity(self.channel_id)
        try:
            reply = await self.ai_generate_fn(prompt, command)
            await ctx.reply(reply[:450])
        except Exception as e:
            logger.error(f'AI error in bot: {e}')
            await ctx.reply('AI glitched, try again 🤖')

    @twitch_commands.command(name='ask')
    async def cmd_ask(self, ctx, *, question: str = None):
        if not question:
            await ctx.reply(f'Usage: {self._prefix}ask [question]')
            return
        await self._ai_reply(ctx, question, 'ask')

    @twitch_commands.command(name='joke')
    async def cmd_joke(self, ctx):
        await self._ai_reply(ctx, '', 'joke')

    @twitch_commands.command(name='fact')
    async def cmd_fact(self, ctx):
        await self._ai_reply(ctx, '', 'fact')

    @twitch_commands.command(name='roast')
    async def cmd_roast(self, ctx, *, target: str = None):
        target = (target or ctx.author.name).lstrip('@')
        await self._ai_reply(ctx, target, 'roast')

    @twitch_commands.command(name='help')
    async def cmd_help(self, ctx):
        p = self._prefix
        await ctx.reply(
            f'🤖 Commands: {p}ask [q] | {p}joke | {p}fact | {p}roast [@user]'
        )
