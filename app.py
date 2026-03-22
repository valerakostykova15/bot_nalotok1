import asyncio
import os

from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from dotenv import load_dotenv

from db import init_db, add_expense, get_stats

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


class ExpenseState(StatesGroup):
    choosing_category = State()
    entering_amount = State()


class StatsState(StatesGroup):
    choosing_person = State()
    choosing_period = State()
    entering_custom_days = State()
    choosing_view = State()


def is_allowed(user_id: int) -> bool:
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


def format_stats_text(title: str, total: float, stats: dict, mode: str) -> str:
    text = f"📊 {title}\n\n"

    if mode == "total":
        text += f"Итого: {total:.0f} ₸"
        return text

    if not stats:
        text += "Нет данных"
        return text

    for cat, amt in stats.items():
        text += f"- {cat}: {amt:.0f} ₸\n"

    text += f"\nИтого: {total:.0f} ₸"
    return text


def get_person_ids(key: str):
    if key == "wife":
        return [WIFE_ID], WIFE_NAME
    if key == "husband":
        return [HUSBAND_ID], HUSBAND_NAME
    return [WIFE_ID, HUSBAND_ID], "Общее"


def get_period_days(key: str):
    if key == "day":
        return 1, "за день"
    if key == "week":
        return 7, "за неделю"
    if key == "month":
        return 30, "за месяц"
    return None, ""


@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    if not is_allowed(message.from_user.id):
        await message.answer("кыш из бота")
        return

    await state.clear()
    await message.answer("привет, бюджетики", reply_markup=get_main_menu())


@dp.message(Command("id"))
async def get_id(message: Message):
    await message.answer(
        f"ID: {message.from_user.id}\n"
        f"Имя: {message.from_user.full_name}"
    )


@dp.message(F.text == "Заполнить траты")
async def fill(message: Message, state: FSMContext):
    if not is_allowed(message.from_user.id):
        await message.answer("кыш из бота")
        return

    await state.clear()
    await state.set_state(ExpenseState.choosing_category)
    await message.answer("куда деньги дели?", reply_markup=get_categories_menu())


@dp.message(ExpenseState.choosing_category)
async def category(message: Message, state: FSMContext):
    if message.text == "Назад":
        await state.clear()
        await message.answer("меню", reply_markup=get_main_menu())
        return

    if message.text not in CATEGORIES:
        await message.answer("жми кнопку нормально")
        return

    await state.update_data(category=message.text)
    await state.set_state(ExpenseState.entering_amount)
    await message.answer("сколько потратили?")


@dp.message(ExpenseState.entering_amount)
async def amount(message: Message, state: FSMContext):
    if message.text == "Назад":
        await state.set_state(ExpenseState.choosing_category)
        await message.answer("выбери категорию", reply_markup=get_categories_menu())
        return

    try:
        amount_value = float(message.text.replace(",", "."))
    except ValueError:
        await message.answer("введи число")
        return

    data = await state.get_data()
    category_name = data.get("category")

    if not category_name:
        await state.clear()
        await message.answer("что-то сбилось, начни заново", reply_markup=get_main_menu())
        return

    await add_expense(
        message.from_user.id,
        message.from_user.full_name,
        amount_value,
        category_name
    )

    await state.clear()
    await message.answer("сохранила 💸", reply_markup=get_main_menu())


@dp.message(F.text == "Посмотреть статистику")
async def stats(message: Message, state: FSMContext):
    if not is_allowed(message.from_user.id):
        await message.answer("кыш из бота")
        return

    await state.clear()
    await state.set_state(StatsState.choosing_person)
    await message.answer("чья?", reply_markup=get_stats_person_menu())


@dp.message(StatsState.choosing_person)
async def stats_person(message: Message, state: FSMContext):
    if message.text == "Назад":
        await state.clear()
        await message.answer("меню", reply_markup=get_main_menu())
        return

    mapping = {
        "Кица": "wife",
        "Кит": "husband",
        "Общее": "common",
    }

    if message.text not in mapping:
        await message.answer("жми кнопку")
        return

    await state.update_data(person=mapping[message.text])
    await state.set_state(StatsState.choosing_period)
    await message.answer("за какой период?", reply_markup=get_stats_period_menu())


@dp.message(StatsState.choosing_period)
async def stats_period(message: Message, state: FSMContext):
    if message.text == "Назад":
        await state.set_state(StatsState.choosing_person)
        await message.answer("чья?", reply_markup=get_stats_person_menu())
        return

    mapping = {
        "За день": "day",
        "За неделю": "week",
        "За месяц": "month",
        "За указанный период": "custom",
    }

    if message.text not in mapping:
        await message.answer("жми кнопку")
        return

    period_value = mapping[message.text]

    if period_value == "custom":
        await state.set_state(StatsState.entering_custom_days)
        await message.answer("сколько дней?")
        return

    await state.update_data(period=period_value)
    await state.set_state(StatsState.choosing_view)
    await message.answer("как показать?", reply_markup=get_stats_view_menu())


@dp.message(StatsState.entering_custom_days)
async def custom_days(message: Message, state: FSMContext):
    if message.text == "Назад":
        await state.set_state(StatsState.choosing_period)
        await message.answer("за какой период?", reply_markup=get_stats_period_menu())
        return

    if not message.text.isdigit():
        await message.answer("число введи")
        return

    days = int(message.text)

    if days <= 0:
        await message.answer("дней должно быть больше нуля")
        return

    await state.update_data(period="custom", days=days)
    await state.set_state(StatsState.choosing_view)
    await message.answer("как показать?", reply_markup=get_stats_view_menu())


@dp.message(StatsState.choosing_view)
async def stats_view(message: Message, state: FSMContext):
    if message.text == "Назад":
        data = await state.get_data()
        if data.get("period") == "custom":
            await state.set_state(StatsState.entering_custom_days)
            await message.answer("сколько дней?")
        else:
            await state.set_state(StatsState.choosing_period)
            await message.answer("за какой период?", reply_markup=get_stats_period_menu())
        return

    view_mapping = {
        "По категориям": "cat",
        "Общая сумма": "total",
    }

    if message.text not in view_mapping:
        await message.answer("жми кнопку")
        return

    data = await state.get_data()

    person_key = data.get("person")
    period_key = data.get("period")

    if not person_key or not period_key:
        await state.clear()
        await message.answer("что-то сбилось, начни заново", reply_markup=get_main_menu())
        return

    ids, name = get_person_ids(person_key)

    if period_key == "custom":
        days = data.get("days")
        if not days:
            await state.clear()
            await message.answer("что-то сбилось, начни заново", reply_markup=get_main_menu())
            return
        period_text = f"за {days} дней"
    else:
        days, period_text = get_period_days(period_key)

    total, stats_data = await get_stats(ids, days)

    text = format_stats_text(
        f"{name}, {period_text}",
        total,
        stats_data,
        view_mapping[message.text]
    )

    await state.clear()
    await message.answer(text, reply_markup=get_main_menu())


@dp.message()
async def fallback(message: Message, state: FSMContext):
    if not is_allowed(message.from_user.id):
        await message.answer("кыш из бота")
        return

    current_state = await state.get_state()
    if current_state:
        await message.answer("используй кнопки или введи то, что бот ждёт")
        return

    await message.answer("выбери действие из меню", reply_markup=get_main_menu())


async def health(request):
    return web.Response(text="ok")


async def main():
    await init_db()

    # запускаем бота
    asyncio.create_task(dp.start_polling(bot))

    # простой веб-сервер (чтобы Render не убил)
    app = web.Application()
    app.router.add_get("/", health)

    runner = web.AppRunner(app)
    await runner.setup()

    port = int(os.getenv("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

    print(f"Server started on port {port}")

    # держим процесс живым
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
