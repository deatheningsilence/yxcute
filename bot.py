#!/usr/bin/env python3
"""
Cute Reddit Browser Bot for Telegram
Requirements:
    pip install python-telegram-bot aiohttp
"""
import asyncio
import random
import logging
from datetime import datetime
import aiohttp

from telegram import (
    Update,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    InputMediaPhoto
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes
)

# ---------------- CONFIG ----------------
import os

TOKEN = os.environ.get("BOT_TOKEN")

SUBREDDITS = [
    "aww","cuteanimals","cats","dogs","puppies","kittens","babyanimals","rarepuppers",
    "animalsbeingderps","AnimalsBeingBros","AnimalPhotography","corgi","hedgehog","tuckedinkitties",
    "rabbits","guineapigs","otters","babybeasts","foxes","cute","smallanimals","squirrels","hamsters",
    "chickens","parrots","ferrets","wildlife","bunnies","seal","penguins"
]

MAX_POSTS_PER_SUB = 50
# ----------------------------------------

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Cache
reddit_cache = {sub: [] for sub in SUBREDDITS}


# ---------------------------------------------------------
# FETCHING SUBREDDITS (WORKING VERSION)
# ---------------------------------------------------------
async def fetch_subreddit(sub: str):
    """
    Fetch image posts using PullPush API (WORKING VERSION).
    Forces type=link so we actually get media posts.
    """
    url = (
        f"https://api.pullpush.io/reddit/submission/search"
        f"?subreddit={sub}&size={MAX_POSTS_PER_SUB}&sort=new&type=link&over_18=false"
    )

    posts = []

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                data = await resp.json()

                for post in data.get("data", []):
                    img_url = post.get("url")
                    if not img_url:
                        continue

                    if any(img_url.lower().endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".gif"]):
                        posts.append({
                            "id": post.get("id"),
                            "title": post.get("title", "(no title)"),
                            "url": img_url
                        })

    except Exception as e:
        logger.warning(f"Failed to fetch {sub}: {e}")

    return posts


async def update_all_subreddits():
    """Refresh cache every 15 minutes."""
    for sub in SUBREDDITS:
        posts = await fetch_subreddit(sub)
        if posts:
            reddit_cache[sub] = posts
            logger.info(f"Fetched {len(posts)} posts from r/{sub}")
        else:
            logger.info(f"No posts found for r/{sub}")
    logger.info("Reddit cache updated.")


# ---------------------------------------------------------
# UI / KEYBOARD
# ---------------------------------------------------------
def navigation_keyboard():
    kb = [
        [
            InlineKeyboardButton("⬅️ Prev", callback_data="prev"),
            InlineKeyboardButton("🔁 Random", callback_data="random"),
            InlineKeyboardButton("➡️ Next", callback_data="next"),
        ]
    ]
    return InlineKeyboardMarkup(kb)


# ---------------------------------------------------------
# HANDLERS
# ---------------------------------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hey yx babe, Cheng is finding a random cute post…")
    await send_random_post(update, context)


async def send_random_post(update: Update, context: ContextTypes.DEFAULT_TYPE, message_id=None):
    sub = random.choice(SUBREDDITS)
    posts = reddit_cache.get(sub, [])

    if not posts:
        await update.effective_message.reply_text(f"Oops, something went wrong lol, try again later.")
        return

    post = random.choice(posts)

    context.user_data["last_sub"] = sub
    context.user_data["last_post"] = post

    caption = f"{post['title']}\n/r/{sub}"

    if message_id:
        await context.bot.edit_message_media(
            chat_id=update.effective_chat.id,
            message_id=message_id,
            media=InputMediaPhoto(media=post["url"], caption=caption),
            reply_markup=navigation_keyboard()
        )
    else:
        await update.effective_message.reply_photo(
            photo=post["url"],
            caption=caption,
            reply_markup=navigation_keyboard()
        )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    action = query.data
    sub = context.user_data.get("last_sub")
    posts = reddit_cache.get(sub, [])

    if not posts:
        await query.edit_message_caption(f"No cached posts for r/{sub}.")
        return

    if action == "random":
        await send_random_post(update, context, message_id=query.message.message_id)
        return

    # next/prev just choose another random post
    new_post = random.choice(posts)
    context.user_data["last_post"] = new_post

    caption = f"{new_post['title']}\n/r/{sub}"

    try:
        await query.edit_message_media(
            media=InputMediaPhoto(media=new_post["url"], caption=caption),
            reply_markup=navigation_keyboard()
        )
    except Exception as e:
        logger.warning(f"Failed to edit media: {e}")


# ---------------------------------------------------------
# MAIN LOOP
# ---------------------------------------------------------
async def periodic_reddit_update():
    while True:
        await update_all_subreddits()
        await asyncio.sleep(60 * 15)


def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))

    loop = asyncio.get_event_loop()
    loop.create_task(periodic_reddit_update())

    logger.info("Bot running...")
    app.run_polling()


if __name__ == "__main__":
    main()
