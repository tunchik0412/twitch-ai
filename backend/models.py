from sqlalchemy import Column, String, Boolean, Float, Integer, Text, DateTime
from sqlalchemy.orm import declarative_base
from datetime import datetime

Base = declarative_base()


class ChannelConfig(Base):
    __tablename__ = 'channel_configs'

    channel_id = Column(String, primary_key=True)       # Twitch numeric user ID
    twitch_username = Column(String, nullable=False)
    ai_provider = Column(String, default='gemini')       # gemini | claude | openai
    ai_model = Column(String, default='gemini-2.0-flash')
    api_key_enc = Column(Text)                           # Fernet-encrypted
    system_prompt = Column(Text, default='You are a helpful AI assistant in a Twitch stream. Keep responses short and engaging.')
    temperature = Column(Float, default=0.7)
    max_tokens = Column(Integer, default=300)
    bot_prefix = Column(String, default='!')
    cooldown = Column(Integer, default=5)
    twitch_bot_token_enc = Column(Text)                  # Fernet-encrypted oauth:xxx
    twitch_channel_name = Column(String)                 # channel to join (usually same as username)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class BotInstance(Base):
    __tablename__ = 'bot_instances'

    channel_id = Column(String, primary_key=True)
    enabled = Column(Boolean, default=False)
    last_activity = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
