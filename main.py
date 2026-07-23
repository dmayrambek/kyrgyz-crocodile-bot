# -*- coding: utf-8 -*-
"""
Крокодил оюну — Telegram бот (кыргызча).
aiogram 3.x, polling режими.

Механикасы (классикалык, топто ойнолот):
  - /game — жетекчи болуп, оюнду баштоо
  - Жетекчи "Сөздү көрүү" баскычы аркылуу сөздү көрөт (аны башкалар көрбөйт)
  - Калгандары чатта сөздү жазып табышат
  - Туура тапкан адам жаңы жетекчи болот

Токен BOT_TOKEN курчап турган чөйрөдөн (environment variable) алынат.
"""

import asyncio
import logging
import os
import random

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

from words import WORDS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError(
        "BOT_TOKEN табылган жок. Railway -> Variables ичине BOT_TOKEN кошуңуз."
    )

# chat_id -> {"leader_id": int, "leader_name": str, "word": str}
games: dict[int, dict] = {}


# ---------------------------------------------------------------------------
# Сөздү салыштыруу (нормализация)
#   - чоң/кичине тамга маанилүү эмес
#   - ө/ү/ң тамгалары о/у/н катары да кабыл алынат
#   - дефис (-) менен боштук ( ) МААНИЛҮҮ: алар бири-бирине теңелбейт
# ---------------------------------------------------------------------------
_FOLD = str.maketrans({"ө": "о", "ү": "у", "ң": "н", "ё": "е"})


def normalize(text: str) -> str:
    text = text.strip().lower()
    # баш жана аяккы тыныш белгилерин алып салуу (ички дефис/боштук калат)
    text = text.strip(".,!?;:\"'«»()")
    text = text.translate(_FOLD)
    # катар келген боштуктарды бирге кыскартуу (бирок дефиске теңебейт)
    text = " ".join(text.split(" "))
    return text


def pick_word() -> str:
    return random.choice(WORDS)


def leader_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="👀 Сөздү көрүү", callback_data="see_word")],
            [
                InlineKeyboardButton(text="🔄 Башка сөз", callback_data="next_word"),
                InlineKeyboardButton(text="🏳️ Пас берүү", callback_data="give_up"),
            ],
        ]
    )


def start_round(chat_id: int, leader_id: int, leader_name: str) -> None:
    games[chat_id] = {
        "leader_id": leader_id,
        "leader_name": leader_name,
        "word": pick_word(),
    }


# ---------------------------------------------------------------------------
# Командалар
# ---------------------------------------------------------------------------
dp = Dispatcher()


@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "🐊 <b>Крокодил оюнуна кош келиңиз!</b>\n\n"
        "Бул — сөз түшүндүрүү оюну. Бир ойунчу (жетекчи) сөздү сүйлөбөй, "
        "жаңсоо же сүрөттөп түшүндүрөт, калгандары табышат.\n\n"
        "Оюнду баштоо үчүн: /game\n"
        "Эрежелер: /help",
        parse_mode="HTML",
    )


@dp.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "📖 <b>Кантип ойнойбуз?</b>\n\n"
        "1. Топтун бирөө /game деп жазат — ал <b>жетекчи</b> болот.\n"
        "2. Жетекчи «👀 Сөздү көрүү» баскычын басып, сөздү көрөт "
        "(башкалар аны көрбөйт).\n"
        "3. Жетекчи сөздү <b>айтпай</b>, түшүндүрөт.\n"
        "4. Калгандары чатка сөздү жазып табышат.\n"
        "5. Туура тапкан адам жаңы жетекчи болот!\n\n"
        "Баскычтар:\n"
        "• 🔄 Башка сөз — жаңы сөз алуу\n"
        "• 🏳️ Пас берүү — раундду токтотуу\n\n"
        "Командалар: /game — баштоо, /stop — токтотуу",
        parse_mode="HTML",
    )


@dp.message(Command("game"))
async def cmd_game(message: Message):
    chat_id = message.chat.id
    user = message.from_user

    game = games.get(chat_id)
    if game:
        await message.answer(
            f"⏳ Азыр раунд жүрүп жатат. Жетекчи: <b>{game['leader_name']}</b>.\n"
            f"Токтотуу үчүн /stop.",
            parse_mode="HTML",
        )
        return

    start_round(chat_id, user.id, user.full_name)
    await message.answer(
        f"🎬 <b>{user.full_name}</b> жетекчи болду!\n\n"
        f"Сөздү көрүү үчүн төмөнкү баскычты бас (сени гана көрөт 👇).",
        parse_mode="HTML",
        reply_markup=leader_keyboard(),
    )


@dp.message(Command("stop"))
async def cmd_stop(message: Message):
    chat_id = message.chat.id
    game = games.get(chat_id)
    if not game:
        await message.answer("Азыр активдүү оюн жок. Баштоо үчүн /game.")
        return

    word = game["word"]
    games.pop(chat_id, None)
    await message.answer(
        f"🛑 Оюн токтотулду. Сөз: <b>{word}</b> эле.\n"
        f"Кайра баштоо үчүн /game.",
        parse_mode="HTML",
    )


# ---------------------------------------------------------------------------
# Инлайн баскычтар (жетекчи гана баса алат)
# ---------------------------------------------------------------------------
@dp.callback_query(F.data == "see_word")
async def cb_see_word(callback: CallbackQuery):
    game = games.get(callback.message.chat.id)
    if not game:
        await callback.answer("Оюн жок. /game менен башта.", show_alert=True)
        return
    if callback.from_user.id != game["leader_id"]:
        await callback.answer("Сен азыр жетекчи эмессиң 🙂", show_alert=True)
        return
    await callback.answer(f"Сенин сөзүң: {game['word']}", show_alert=True)


@dp.callback_query(F.data == "next_word")
async def cb_next_word(callback: CallbackQuery):
    game = games.get(callback.message.chat.id)
    if not game:
        await callback.answer("Оюн жок. /game менен башта.", show_alert=True)
        return
    if callback.from_user.id != game["leader_id"]:
        await callback.answer("Сен азыр жетекчи эмессиң 🙂", show_alert=True)
        return
    game["word"] = pick_word()
    await callback.answer(f"Жаңы сөз: {game['word']}", show_alert=True)


@dp.callback_query(F.data == "give_up")
async def cb_give_up(callback: CallbackQuery):
    chat_id = callback.message.chat.id
    game = games.get(chat_id)
    if not game:
        await callback.answer("Оюн жок.", show_alert=True)
        return
    if callback.from_user.id != game["leader_id"]:
        await callback.answer("Сен азыр жетекчи эмессиң 🙂", show_alert=True)
        return
    word = game["word"]
    games.pop(chat_id, None)
    await callback.answer("Пас бердиң.")
    await callback.message.answer(
        f"🏳️ Жетекчи пас берди. Сөз: <b>{word}</b> эле.\n"
        f"Кайра баштоо үчүн /game.",
        parse_mode="HTML",
    )


# ---------------------------------------------------------------------------
# Табуу: чаттагы кадимки жазуулар
# ---------------------------------------------------------------------------
@dp.message(F.text & ~F.text.startswith("/"))
async def guess_handler(message: Message):
    chat_id = message.chat.id
    game = games.get(chat_id)
    if not game:
        return

    # Жетекчинин өз жазуусу текшерилбейт
    if message.from_user.id == game["leader_id"]:
        return

    if normalize(message.text) == normalize(game["word"]):
        word = game["word"]
        winner = message.from_user
        # Утуп алган адам жаңы жетекчи болот
        start_round(chat_id, winner.id, winner.full_name)
        await message.reply(
            f"🎉 <b>{winner.full_name}</b> тапты! Сөз: <b>{word}</b>.\n\n"
            f"Эми <b>{winner.full_name}</b> жетекчи. Сөздү көр 👇",
            parse_mode="HTML",
            reply_markup=leader_keyboard(),
        )


# ---------------------------------------------------------------------------
async def main():
    bot = Bot(token=BOT_TOKEN)
    logger.info("Бот иштеп баштады (polling)...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
