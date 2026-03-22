import asyncio
import os

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from dotenv import load_dotenv

from db import init_db, add_expense, get_stats

from aiohttp import web

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("Не найден BOT_TOKEN")

WIFE_ID = 777714577
HUSBAND_ID = 1341630327

WIFE_NAME = "Кица"
HUSBAND_NAME = "Кит"

CATEGORIES = [
    "покушац и на быть",
    "дорога",
    "энергосики и сигаретки",
    "аптека",
    "кредитс",
    "обязательные платежи",
    "помощь родственникам",
    "доставки",
    "развлечения",
    "другое",
]

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())


# ===================== STATES =====================

class ExpenseState(StatesGroup):
    choosing_category = State()
    entering_amount = State()


class StatsState(StatesGroup):
    choosing_person = State()
    choosing_period = State()
    entering_custom_days = State()
    choosing_view = State()


# ===================== UTILS =====================

def is_allowed(user_id: int):
    return user_id in [WIFE_ID, HUSBAND_ID]


def get_main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Заполнить траты")],
            [KeyboardButton(text="Посмотреть статистику")],
        ],
        resize_keyboard=True
    )


def get_categories_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="покушац и на быть"), KeyboardButton(text="дорога")],
            [KeyboardButton(text="энергосики и сигаретки"), KeyboardButton(text="аптека")],
            [KeyboardButton(text="кредитс"), KeyboardButton(text="обязательные платежи")],
            [KeyboardButton(text="помощь родственникам"), KeyboardButton(text="доставки")],
            [KeyboardButton(text="развлечения"), KeyboardButton(text="другое")],
            [KeyboardButton(text="Назад")],
        ],
        resize_keyboard=True
    )


def get_stats_person_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Кит"), KeyboardButton(text="Кица")],
            [KeyboardButton(text="Общее")],
            [KeyboardButton(text="Назад")],
        ],
        resize_keyboard=True
    )


def get_stats_period_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="За день"), KeyboardButton(text="За неделю")],
            [KeyboardButton(text="За месяц"), KeyboardButton(text="За указанный период")],
            [KeyboardButton(text="Назад")],
        ],
        resize_keyboard=True
    )


def get_stats_view_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="По категориям")],
            [KeyboardButton(text="Общая сумма")],
            [KeyboardButton(text="Назад")],
        ],
        resize_keyboard=True
    )


def format_stats_text(title, total, stats, mode):
    text = f"📊 {title}\n\n"

    if mode == "total":
        return text + f"Итого: {total:.0f} ₸"

    if not stats:
        return text + "Нет данных"

    for cat, amt in stats.items():
        text += f"- {cat}: {amt:.0f} ₸\n"

    text += f"\nИтого: {total:.0f} ₸"
    return text


def get_person_ids(key):
    if key == "wife":
        return [WIFE_ID], WIFE_NAME
    if key == "husband":
        return [HUSBAND_ID], HUSBAND_NAME
    return [WIFE_ID, HUSBAND_ID], "Общее"


def get_period_days(key):
    if key == "day":
        return 1, "за день"
    if key == "week":
        return 7, "за неделю"
    if key == "month":
        return 30, "за месяц"


# ===================== COMMANDS =====================

@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    if not is_allowed(message.from_user.id):
        return await message.answer("кыш из бота")

    await state.clear()
    await message.answer("привет, бюджетики", reply_markup=get_main_menu())


@dp.message(Command("id"))
async def get_id(message: Message):
    await message.answer(f"ID: {message.from_user.id}")


# ===================== EXPENSE FLOW =====================

@dp.message(F.text == "Заполнить траты")
async def fill(message: Message, state: FSMContext):
    await state.set_state(ExpenseState.choosing_category)
    await message.answer("куда деньги дели?", reply_markup=get_categories_menu())


@dp.message(ExpenseState.choosing_category)
async def category(message: Message, state: FSMContext):
    if message.text == "Назад":
        await state.clear()
        return await message.answer("меню", reply_markup=get_main_menu())

    if message.text not in CATEGORIES:
        return await message.answer("жми кнопку нормально")

    await state.update_data(category=message.text)
    await state.set_state(ExpenseState.entering_amount)

    await message.answer("сколько потратили?")


@dp.message(ExpenseState.entering_amount)
async def amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text)
    except:
        return await message.answer("введи число")

    data = await state.get_data()

    await add_expense(
        message.from_user.id,
        message.from_user.full_name,
        amount,
        data["category"]
    )

    await state.clear()
    await message.answer("сохранила 💸", reply_markup=get_main_menu())


# ===================== STATS =====================

@dp.message(F.text == "Посмотреть статистику")
async def stats(message: Message, state: FSMContext):
    await state.set_state(StatsState.choosing_person)
    await message.answer("чья?", reply_markup=get_stats_person_menu())


@dp.message(StatsState.choosing_person)
async def stats_person(message: Message, state: FSMContext):
    if message.text == "Назад":
        await state.clear()
        return await message.answer("меню", reply_markup=get_main_menu())

    mapping = {
        "Кица": "wife",
        "Кит": "husband",
        "Общее": "common",
    }

    if message.text not in mapping:
        return await message.answer("жми кнопку")

    await state.update_data(person=mapping[message.text])
    await state.set_state(StatsState.choosing_period)

    await message.answer("за какой период?", reply_markup=get_stats_period_menu())


@dp.message(StatsState.choosing_period)
async def stats_period(message: Message, state: FSMContext):
    if message.text == "Назад":
        await state.set_state(StatsState.choosing_person)
        return await message.answer("чья?", reply_markup=get_stats_person_menu())

    mapping = {
        "За день": "day",
        "За неделю": "week",
        "За месяц": "month",
        "За указанный период": "custom",
    }

    if message.text not in mapping:
        return await message.answer("жми кнопку")

    if mapping[message.text] == "custom":
        await state.set_state(StatsState.entering_custom_days)
        return await message.answer("сколько дней?")

    await state.update_data(period=mapping[message.text])
    await state.set_state(StatsState.choosing_view)

    await message.answer("как показать?", reply_markup=get_stats_view_menu())


@dp.message(StatsState.entering_custom_days)
async def custom_days(message: Message, state: FSMContext):
    if not message.text.isdigit():
        return await message.answer("число введи")

    await state.update_data(period="custom", days=int(message.text))
    await state.set_state(StatsState.choosing_view)

    await message.answer("как показать?", reply_markup=get_stats_view_menu())


@dp.message(StatsState.choosing_view)
async def stats_view(message: Message, state: FSMContext):
    mapping = {
        "По категориям": "cat",
        "Общая сумма": "total",
    }

    if message.text not in mapping:
        return await message.answer("жми кнопку")

    data = await state.get_data()

    ids, name = get_person_ids(data["person"])

    if data["period"] == "custom":
        days = data["days"]
        period_text = f"{days} дней"
    else:
        days, period_text = get_period_days(data["period"])

    total, stats = await get_stats(ids, days)

    text = format_stats_text(f"{name}, {period_text}", total, stats, mapping[message.text])

    await state.clear()
    await message.answer(text, reply_markup=get_main_menu())


# ===================== WEB =====================

async def health(request):
    return web.Response(text="ok")


async def main():
    await init_db()

    asyncio.create_task(dp.start_polling(bot))

    app = web.Application()
    app.router.add_get("/", health)

    runner = web.AppRunner(app)
    await runner.setup()

    port = int(os.getenv("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

    while True:
        await asyncio.sleep(3600)


if __name__ == "__main__":
    asyncio.run(main())
