"""
Gemini Twitch Chat Bot
Responds to chat commands using Google Gemini AI

Commands:
  !ask [question]  - Ask the AI anything
  !joke            - Get a random joke
  !fact            - Get an interesting fact
  !roast [@user]   - Get a playful roast
  !help            - Show available commands

Setup:
1. Get a Twitch OAuth token: https://twitchtokengenerator.com/
   - Select "Bot Chat Token" and authorize
2. Get a Gemini API key: https://aistudio.google.com/app/apikey
3. Set environment variables or create .env file
4. Run: python bot.py
"""

import os
import asyncio
import logging
from datetime import datetime, timedelta

from twitchio.ext import commands
import google.generativeai as genai

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables from .env file if it exists
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Configuration
TWITCH_TOKEN = os.environ.get('TWITCH_TOKEN', '')  # OAuth token (oauth:xxx)
TWITCH_CHANNEL = os.environ.get('TWITCH_CHANNEL', '')  # Your channel name
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')
BOT_PREFIX = os.environ.get('BOT_PREFIX', '!')
COOLDOWN_SECONDS = int(os.environ.get('COOLDOWN_SECONDS', '5'))
MAX_RESPONSE_LENGTH = 450  # Twitch chat limit is ~500 chars

# Validate configuration
if not TWITCH_TOKEN:
    raise ValueError("TWITCH_TOKEN environment variable is required")
if not TWITCH_CHANNEL:
    raise ValueError("TWITCH_CHANNEL environment variable is required")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY environment variable is required")

# Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-3.1-flash-lite-preview')

# Cooldown tracking
user_cooldowns = {}


def check_cooldown(user_id: str) -> bool:
    """Check if user is on cooldown. Returns True if allowed to use command."""
    now = datetime.now()
    if user_id in user_cooldowns:
        if now < user_cooldowns[user_id]:
            return False
    user_cooldowns[user_id] = now + timedelta(seconds=COOLDOWN_SECONDS)
    return True


def get_remaining_cooldown(user_id: str) -> int:
    """Get remaining cooldown seconds for a user."""
    if user_id not in user_cooldowns:
        return 0
    remaining = (user_cooldowns[user_id] - datetime.now()).total_seconds()
    return max(0, int(remaining))


async def generate_response(prompt: str, command: str, style: str = "friendly") -> str:
    """Generate a response using Gemini AI."""
    
    style_prompts = {
        'friendly': "You are a friendly, fun AI assistant in a Twitch chat. Keep responses SHORT (under 400 chars), engaging, and use casual language. You can use emotes like :) or emojis.",
        'funny': "You are a hilarious AI in Twitch chat. Be witty and make people laugh! Keep it SHORT (under 400 chars).",
    }
    
    command_prompts = {
        'ask': f"Answer this concisely: {prompt}",
        'roast': f"Give a playful, light-hearted roast about '{prompt}'. Keep it fun, NOT mean. Make people laugh!",
        'joke': "Tell a short, funny joke. Gaming/streaming related is great, but any clean joke works.",
        'fact': "Share one interesting, surprising fact. Make it memorable!"
    }
    
    system = style_prompts.get(style, style_prompts['friendly'])
    user_prompt = command_prompts.get(command, command_prompts['ask'])
    
    full_prompt = f"{system}\n\n{user_prompt}"
    
    try:
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
        if len(reply) > MAX_RESPONSE_LENGTH:
            # Try to cut at sentence boundary
            truncated = reply[:MAX_RESPONSE_LENGTH]
            last_sentence = max(
                truncated.rfind('.'),
                truncated.rfind('!'),
                truncated.rfind('?')
            )
            if last_sentence > MAX_RESPONSE_LENGTH * 0.5:
                reply = truncated[:last_sentence + 1]
            else:
                reply = truncated.rsplit(' ', 1)[0] + '...'
        
        return reply
        
    except Exception as e:
        logger.error(f"Gemini API error: {e}")
        return "Oops, my brain glitched! Try again? 🤖"


class GeminiBot(commands.Bot):
    """Twitch Chat Bot with Gemini AI integration."""
    
    def __init__(self):
        super().__init__(
            token=TWITCH_TOKEN,
            prefix=BOT_PREFIX,
            initial_channels=[TWITCH_CHANNEL]
        )
        logger.info(f"Bot initialized for channel: {TWITCH_CHANNEL}")
    
    async def event_ready(self):
        """Called when bot is ready and connected."""
        logger.info(f'Bot is ready! Logged in as: {self.nick}')
        logger.info(f'Connected to channel: {TWITCH_CHANNEL}')
        logger.info(f'Commands: {BOT_PREFIX}ask, {BOT_PREFIX}joke, {BOT_PREFIX}fact, {BOT_PREFIX}roast, {BOT_PREFIX}help')
    
    async def event_message(self, message):
        """Handle incoming messages."""
        # Ignore messages from the bot itself
        if message.echo:
            return
        
        # Process commands
        await self.handle_commands(message)
    
    @commands.command(name='help')
    async def cmd_help(self, ctx: commands.Context):
        """Show available commands."""
        help_text = (
            f"🤖 Gemini Bot Commands: "
            f"{BOT_PREFIX}ask [question] | "
            f"{BOT_PREFIX}joke | "
            f"{BOT_PREFIX}fact | "
            f"{BOT_PREFIX}roast [@user]"
        )
        await ctx.reply(help_text)
    
    @commands.command(name='ask')
    async def cmd_ask(self, ctx: commands.Context, *, question: str = None):
        """Ask the AI a question."""
        if not question:
            await ctx.reply(f"Ask me something! Example: {BOT_PREFIX}ask What's the meaning of life?")
            return
        
        if not check_cooldown(ctx.author.id):
            remaining = get_remaining_cooldown(ctx.author.id)
            await ctx.reply(f"Cooldown! Wait {remaining}s ⏳")
            return
        
        logger.info(f"[ASK] {ctx.author.name}: {question}")
        
        response = await generate_response(question, 'ask')
        await ctx.reply(response)
    
    @commands.command(name='joke')
    async def cmd_joke(self, ctx: commands.Context):
        """Get a random joke."""
        if not check_cooldown(ctx.author.id):
            remaining = get_remaining_cooldown(ctx.author.id)
            await ctx.reply(f"Cooldown! Wait {remaining}s ⏳")
            return
        
        logger.info(f"[JOKE] {ctx.author.name}")
        
        response = await generate_response('', 'joke')
        await ctx.reply(f"😂 {response}")
    
    @commands.command(name='fact')
    async def cmd_fact(self, ctx: commands.Context):
        """Get an interesting fact."""
        if not check_cooldown(ctx.author.id):
            remaining = get_remaining_cooldown(ctx.author.id)
            await ctx.reply(f"Cooldown! Wait {remaining}s ⏳")
            return
        
        logger.info(f"[FACT] {ctx.author.name}")
        
        response = await generate_response('', 'fact')
        await ctx.reply(f"📊 {response}")
    
    @commands.command(name='roast')
    async def cmd_roast(self, ctx: commands.Context, *, target: str = None):
        """Get a playful roast."""
        if not check_cooldown(ctx.author.id):
            remaining = get_remaining_cooldown(ctx.author.id)
            await ctx.reply(f"Cooldown! Wait {remaining}s ⏳")
            return
        
        # Default to roasting the person who asked
        if not target:
            target = ctx.author.name
        
        # Clean up @mentions
        target = target.lstrip('@')
        
        logger.info(f"[ROAST] {ctx.author.name} -> {target}")
        
        response = await generate_response(target, 'roast')
        await ctx.reply(f"🔥 @{target} {response}")


def main():
    """Main entry point."""
    print("""
    ╔═══════════════════════════════════════╗
    ║     🤖 Gemini Twitch Chat Bot 🤖      ║
    ╠═══════════════════════════════════════╣
    ║  Commands:                            ║
    ║    !ask [question] - Ask anything     ║
    ║    !joke          - Get a joke        ║
    ║    !fact          - Get a fact        ║
    ║    !roast [@user] - Playful roast     ║
    ║    !help          - Show commands     ║
    ╚═══════════════════════════════════════╝
    """)
    
    bot = GeminiBot()
    bot.run()


if __name__ == '__main__':
    main()
