import asyncio
import logging
import os
import random
import sys

import aiohttp
import discord
from flask import Flask

import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

reply_counter = 0
reply_lock = asyncio.Lock()
ai_lock = asyncio.Lock()

channel_context = {}


async def get_ai_response(context_messages: list, trigger: str, is_defending: bool) -> str:
    if is_defending:
        system_prompt = f"""You are a funny, sassy discord chat defender. The target users are: {config.TARGET_USERS}.
When someone tries to decrease/mock Attack or criticize these users, you must defend them with hilarious comebacks.
Make responses short, funny, and witty. Don't be too long.
Clan 'Jax' should be defended when referenced.
Respond in English."""
    else:
        system_prompt = f"""You are a funny, savage discord chatter. When someone says "{trigger}" in the chat,
you need to mock/decrease them in a funny way.
Make responses short, savage, and witty. Don't be too long.
Respond in English."""

    messages = [{"role": "SYSTEM", "text": system_prompt}]
    valid_messages = []
    for msg in context_messages[-20:]:
        if msg.content and msg.content.strip() and len(msg.content.strip()) > 0:
            if not msg.attachments and not msg.embeds:
                valid_messages.append(msg)
    for msg in valid_messages:
        messages.append({"role": "USER", "text": f"{msg.author.name}: {msg.content}"})

    logger.info(f"Sending {len(messages)} messages to AI (filtered from {len(context_messages[-20:])} total)")

    if len(messages) < 2:
        logger.warning("Not enough valid messages for AI response")
        return None

    if not config.COHERE_API_KEY:
        logger.error("COHERE_API_KEY not set!")
        return None

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.cohere.ai/v1/chat",
                headers={
                    "Authorization": f"Bearer {config.COHERE_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "command-r-plus",
                    "messages": messages,
                    "max_tokens": 150,
                    "temperature": 0.9
                },
                timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                result = await resp.json()
                logger.info(f"AI API response: {result}")
                if "text" in result and result["text"]:
                    return result["text"].strip()
                elif "message" in result:
                    return result["message"]
                elif "generations" in result and result["generations"]:
                    return result["generations"][0].get("text", "").strip()
                else:
                    logger.error(f"AI response error: {result}")
                    return None
    except Exception as e:
        logger.error(f"AI API error: {e}")
        return None


async def check_chat_context(channel: discord.TextChannel) -> list:
    try:
        messages = []
        async for msg in channel.history(limit=config.CONTEXT_MESSAGES):
            messages.append(msg)
        return list(reversed(messages))
    except Exception as e:
        logger.error(f"Failed to get channel history: {e}")
        return []


def is_target_user_being_attacked(messages: list) -> bool:
    negative_keywords = ["bad", "trash", "garbage", "suck", "worst", "hate", "loser", "fail", "noob", "clown", "dog", "shit", "fuck", "stupid", "idiot", "embarrassing"]
    
    for msg in messages[-10:]:
        content_lower = msg.content.lower()
        if any(user_id in content_lower for user_id in [str(uid) for uid in config.TARGET_USERS]):
            if any(neg in content_lower for neg in negative_keywords):
                return True
        if "jax" in content_lower and any(neg in content_lower for neg in negative_keywords):
            return True
    return False


def contains_trigger_keyword(content: str) -> str:
    content_lower = content.lower()
    for keyword in config.AI_TRIGGER_KEYWORDS:
        if keyword in content_lower:
            return keyword
    return None


@app.route("/")
def home():
    return "Auto Reacter Bot is running!"


@app.route("/health")
def health():
    return "OK", 200


class AutoReacterBot(discord.Client):
    def __init__(self, token: str, bot_id: int, bots_count: int):
        super().__init__()
        self.token = token
        self.bot_id = bot_id
        self.bots_count = bots_count
        self.ready = False

    async def on_ready(self):
        self.ready = True
        logger.info(f"Bot {self.user.id} ({self.user}) is ready!")
        logger.info(f"Guild: {config.TARGET_GUILD}")
        logger.info(f"Target users: {config.TARGET_USERS}")

    async def on_message(self, message: discord.Message):
        if not self.ready:
            return
        
        if message.guild is None or message.guild.id != config.TARGET_GUILD:
            return
        
        if message.author.id == self.user.id:
            return

        channel_key = f"{message.guild.id}-{message.channel.id}"
        if channel_key not in channel_context:
            channel_context[channel_key] = []
        channel_context[channel_key].append(message)
        
        if len(channel_context[channel_key]) > config.CONTEXT_MESSAGES:
            channel_context[channel_key] = channel_context[channel_key][-config.CONTEXT_MESSAGES:]

        if message.author.id in config.TARGET_USERS:
            delay = random.uniform(1.0, 2.0)
            await asyncio.sleep(delay)

            try:
                await message.add_reaction(config.REACTION_EMOJI)
                logger.info(f"Reacted to {message.author}'s message in #{message.channel}")

                if message.author.id == config.SPECIAL_USER:
                    for emoji in config.SPECIAL_REACTION_EMOJIS:
                        await message.add_reaction(emoji)
                    logger.info(f"Reacted with special emojis to {message.author}'s message in #{message.channel}")

                if "artist" in message.content.lower() or 744314482381160489 in [m.id for m in message.mentions]:
                    async with reply_lock:
                        global reply_counter
                        if self.bot_id == (reply_counter % len(bots)) + 1:
                            await asyncio.sleep(1.0)
                            await message.reply("artist is clown")
                            reply_counter += 1
                            logger.info(f"Replied to {message.author}'s message in #{message.channel}")
            except Exception as e:
                logger.error(f"Failed to react: {e}")

        if message.author.id in config.MOCK_USERS:
            async with ai_lock:
                context_msgs = await check_chat_context(message.channel)
                
                if len(context_msgs) >= 50:
                    ai_response = await get_ai_response(context_msgs, message.author.name, False)
                    if ai_response and self.bot_id == 1:
                        await asyncio.sleep(random.uniform(1.0, 2.0))
                        await message.channel.send(ai_response)
                        logger.info(f"AI mocked {message.author.name} in #{message.channel}")

    async def start_bot(self):
        try:
            await self.login(self.token)
            await self.connect()
        except Exception as e:
            logger.error(f"Bot {self.bot_id} error: {e}")
            await asyncio.sleep(5)


async def run_bots():
    tokens = [
        os.environ.get("TOKEN1", ""),
        os.environ.get("TOKEN2", ""),
    ]
    tokens = [t for t in tokens if t]
    
    if not tokens:
        logger.error("No tokens provided! Set TOKEN1 and TOKEN2 environment variables.")
        return
    
    bots = []
    
    for i, token in enumerate(tokens):
        logger.info(f"Starting bot {i + 1}/{len(tokens)} with token: {token[:20]}...")
        bot = AutoReacterBot(token, i + 1, len(tokens))
        bots.append(bot)
        asyncio.create_task(bot.start_bot())
        await asyncio.sleep(2)
    
    logger.info(f"All {len(bots)} bots started!")
    
    while True:
        await asyncio.sleep(3600)


def run_flask():
    app.run(host="0.0.0.0", port=10000)


async def main():
    bot_task = asyncio.create_task(run_bots())
    flask_task = asyncio.create_task(asyncio.to_thread(run_flask))
    
    await asyncio.gather(bot_task, flask_task)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutting down...")
