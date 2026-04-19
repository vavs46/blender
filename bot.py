import asyncio
import logging
import os
import random
import sys

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
            
        if message.author.id not in config.TARGET_USERS:
            return
        
        if message.author.id == self.user.id:
            return

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
