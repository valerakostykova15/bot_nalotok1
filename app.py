#WIFE_ID = 777714577
#HUSBAND_ID = 1341630327
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

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("Не найден BOT_TOKEN в файле .env")

WIFE_ID = 777714577
HUSBAND_ID = 1341630327

WIFE_NAME = "Кица"
HUSBAND_NAME = "Кит"

CATEGORIES = [
    "покушац и на быть",
    "дорога",
    "энергосики и сиграетки",
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
            [KeyboardButton(text="покущац и быть"), KeyboardButton(text="дорога")],
            [KeyboardButton(text="вредные привычки"), KeyboardButton(text="аптека")],
            [KeyboardButton(text="кредитс"), KeyboardButton(text="обязательные платежи")],
            [KeyboardButton(text="помощь родственникам"), KeyboardButton(text="доставки")],
            [KeyboardButton(text="развлечения")],[KeyboardButton(text="другое")],
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


def format_stats_text(title: str, total: float, category_stats: dict, view_mode: str) -> str:
    text = f"📊 {title}\n\n"

    if view_mode == "total":
        text += f"Итого: {total:.0f} ₸"
        return text

    if not category_stats:
        text += "Нет данных"
        return text

    for category, amount in category_stats.items():
        text += f"- {category}: {amount:.0f} ₸\n"

    text += f"\nИтого: {total:.0f} ₸"
    return text


def get_person_data(person_key: str):
    if person_key == "wife":
        return [WIFE_ID], WIFE_NAME
    if person_key == "husband":
        return [HUSBAND_ID], HUSBAND_NAME
    return [WIFE_ID, HUSBAND_ID], "Общее"


def get_period_data(period_key: str):
    if period_key == "day":
        return 1, "за день"
    if period_key == "week":
        return 7, "за неделю"
    if period_key == "month":
        return 30, "за месяц"
    return None, ""


@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    if not is_allowed(message.from_user.id):
        await message.answer("кыш из бота")
        return

    await state.clear()
    await message.answer(
        "вводите сумму, расточители",
        reply_markup=get_main_menu()
    )


@dp.message(Command("id"))
async def cmd_id(message: Message):
    await message.answer(
        f"Ваш ID: {message.from_user.id}\n"
        f"Имя: {message.from_user.full_name}"
    )


@dp.message(F.text == "Заполнить траты")
async def fill_expenses(message: Message, state: FSMContext):
    if not is_allowed(message.from_user.id):
        await message.answer("кыш из бота")
        return

    await state.clear()
    await state.set_state(ExpenseState.choosing_category)
    await message.answer(
        "опять все на энергетики спустили?",
        reply_markup=get_categories_menu()
    )


@dp.message(ExpenseState.choosing_category)
async def choose_category(message: Message, state: FSMContext):
    if message.text == "Назад":
        await state.clear()
        await message.answer("Главное меню", reply_markup=get_main_menu())
        return

    if message.text not in CATEGORIES:
        await message.answer("Выберите категорию кнопкой ниже.")
        return

    await state.update_data(category=message.text)
    await state.set_state(ExpenseState.entering_amount)
    await message.answer(
        f"Категория: {message.text}\nВведите сумму числом:",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="Назад")]],
            resize_keyboard=True
        )
    )


@dp.message(ExpenseState.entering_amount)
async def enter_amount(message: Message, state: FSMContext):
    if message.text == "Назад":
        await state.set_state(ExpenseState.choosing_category)
        await message.answer(
            "Выберите категорию:",
            reply_markup=get_categories_menu()
        )
        return

    try:
        amount = float(message.text.replace(",", "."))
    except ValueError:
        await message.answer("Введите сумму числом, например: 2500")
        return

    data = await state.get_data()
    category = data["category"]

    user_id = message.from_user.id
    user_name = message.from_user.full_name if message.from_user else "Неизвестный"

    await add_expense(user_id, user_name, amount, category)

    await state.clear()
    await message.answer(
        f"✅ Сохранено: {amount:.0f} ₸\nКатегория: {category}",
        reply_markup=get_main_menu()
    )


@dp.message(F.text == "Посмотреть статистику")
async def stats_menu(message: Message, state: FSMContext):
    if not is_allowed(message.from_user.id):
        await message.answer("кыш из бота")
        return

    await state.clear()
    await state.set_state(StatsState.choosing_person)
    await message.answer(
        "Чью статистику показать?",
        reply_markup=get_stats_person_menu()
    )


@dp.message(StatsState.choosing_person)
async def choose_stats_person(message: Message, state: FSMContext):
    if message.text == "Назад":
        await state.clear()
        await message.answer("Главное меню", reply_markup=get_main_menu())
        return

    mapping = {
        "Жена": "wife",
        "Муж": "husband",
        "Общее": "common",
    }

    if message.text not in mapping:
        await message.answer("Выберите вариант кнопкой ниже.")
        return

    await state.update_data(person=mapping[message.text])
    await state.set_state(StatsState.choosing_period)
    await message.answer(
        "Выберите период:",
        reply_markup=get_stats_period_menu()
    )


@dp.message(StatsState.choosing_period)
async def choose_stats_period(message: Message, state: FSMContext):
    if message.text == "Назад":
        await state.set_state(StatsState.choosing_person)
        await message.answer(
            "Чью статистику показать?",
            reply_markup=get_stats_person_menu()
        )
        return

    mapping = {
        "За день": "day",
        "За неделю": "week",
        "За месяц": "month",
        "За указанный период": "custom",
    }

    if message.text not in mapping:
        await message.answer("Выберите период кнопкой ниже.")
        return

    period_value = mapping[message.text]

    if period_value == "custom":
        await state.set_state(StatsState.entering_custom_days)
        await message.answer(
            "Введите количество дней числом, например: 10",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="Назад")]],
                resize_keyboard=True
            )
        )
        return

    await state.update_data(period=period_value)
    await state.set_state(StatsState.choosing_view)
    await message.answer(
        "Как показать статистику?",
        reply_markup=get_stats_view_menu()
    )


@dp.message(StatsState.entering_custom_days)
async def enter_custom_days(message: Message, state: FSMContext):
    if message.text == "Назад":
        await state.set_state(StatsState.choosing_period)
        await message.answer(
            "Выберите период:",
            reply_markup=get_stats_period_menu()
        )
        return

    if not message.text.isdigit():
        await message.answer("Введите количество дней числом, например: 10")
        return

    days = int(message.text)

    if days <= 0:
        await message.answer("Количество дней должно быть больше нуля.")
        return

    await state.update_data(period="custom", custom_days=days)
    await state.set_state(StatsState.choosing_view)
    await message.answer(
        "Как показать статистику?",
        reply_markup=get_stats_view_menu()
    )


@dp.message(StatsState.choosing_view)
async def choose_stats_view(message: Message, state: FSMContext):
    if message.text == "Назад":
        data = await state.get_data()
        if data.get("period") == "custom":
            await state.set_state(StatsState.entering_custom_days)
            await message.answer(
                "Введите количество дней числом, например: 10",
                reply_markup=ReplyKeyboardMarkup(
                    keyboard=[[KeyboardButton(text="Назад")]],
                    resize_keyboard=True
                )
            )
        else:
            await state.set_state(StatsState.choosing_period)
            await message.answer(
                "Выберите период:",
                reply_markup=get_stats_period_menu()
            )
        return

    mapping = {
        "По категориям": "categories",
        "Общая сумма": "total",
    }

    if message.text not in mapping:
        await message.answer("Выберите вариант кнопкой ниже.")
        return

    view_mode = mapping[message.text]
    data = await state.get_data()

    person_key = data["person"]
    period_key = data["period"]

    user_ids, person_title = get_person_data(person_key)

    if period_key == "custom":
        days = data["custom_days"]
        period_title = f"за {days} дн."
    else:
        days, period_title = get_period_data(period_key)

    total, category_stats = await get_stats(user_ids, days)

    if total == 0:
        await state.clear()
        await message.answer(
            "За выбранный период данных нет.",
            reply_markup=get_main_menu()
        )
        return

    title = f"{person_title}, {period_title}"
    text = format_stats_text(title, total, category_stats, view_mode)

    await state.clear()
    await message.answer(text, reply_markup=get_main_menu())


@dp.message()
async def fallback_handler(message: Message):
    if not is_allowed(message.from_user.id):
        await message.answer("кыш из бота")
        return

    await message.answer(
        "Выберите действие из меню ниже.",
        reply_markup=get_main_menu()
    )


async def main():
    await init_db()
    print("Бот запущен...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
