# mvpeeker shop bot - версия для PythonAnywhere (Flask + webhook)
# Stars - автооплата через Telegram, DonationAlerts/СБП - ручное подтверждение продавцом.

import telebot
from telebot import types
from flask import Flask, request
import logging

telebot.logger.setLevel(logging.DEBUG)

# ====== НАСТРОЙКИ ======

BOT_TOKEN = "8655420363:AAHfNpLyQyhzHtBh3gODCH51OL0i1bvovOk"
ADMIN_ID = 8230465825  # твой Telegram ID - сюда приходят уведомления о заявках

# Адрес твоего приложения на PythonAnywhere (без слэша на конце)
WEBHOOK_HOST = "https://mvpeeker-bot.onrender.com"

DONATE_URL = "https://www.donationalerts.com/r/mvpeeker"
TELEGRAM_URL = "https://t.me/mvpeeker"
YOUTUBE_URL = "https://www.youtube.com/watch?v=_CIl7ZQm-c8"

SBP_PHONE = "+79902657221"
SBP_BANK = "ПромСвязь Банк (ПСБ)"

# Тарифы: (название, цена в рублях, цена в звёздах)
PLANS = [
    ("1 день", 15, 25),
    ("7 дней", 50, 80),
    ("14 дней", 100, 160),
    ("21 день", 150, 240),
    ("31 день", 250, 400),
    ("Безлимит", 900, 1400),
]

WELCOME_TEXT = (
    "\U0001F525 *mvpeeker \u2014 твой калькулятор для перекупа*\n\n"
    "Считай прибыль с каждой сделки, веди историю по дням, "
    "отслеживай доход с аренды тачек \u2014 всё в одном месте, удобно и быстро.\n\n"
    f"\U0001F4FA Обзор: [смотреть на YouTube]({YOUTUBE_URL})\n\n"
    "Выбери тариф ниже \U0001F447"
)

# ====== БОТ ======

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)


def plans_keyboard():
    kb = types.InlineKeyboardMarkup(row_width=1)
    for name, price_rub, price_stars in PLANS:
        kb.add(types.InlineKeyboardButton(
            text=f"{name} \u2014 {price_rub}\u20bd",
            callback_data=f"plan|{name}"
        ))
    return kb


def find_plan(name):
    for p in PLANS:
        if p[0] == name:
            return p
    return None


def payment_keyboard(name):
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(types.InlineKeyboardButton(text="\u2B50 Оплатить звёздами", callback_data=f"pay_stars|{name}"))
    kb.add(types.InlineKeyboardButton(text="\U0001F4B3 СБП / карта", callback_data=f"pay_sbp|{name}"))
    kb.add(types.InlineKeyboardButton(text="\U0001F49C DonationAlerts", callback_data=f"pay_donate|{name}"))
    kb.add(types.InlineKeyboardButton(text="\u2190 Назад к тарифам", callback_data="back"))
    return kb


@bot.message_handler(func=lambda message: True, content_types=['text'])
def debug_any_message(message):
    print("DEBUG HANDLER TRIGGERED:", message.text, flush=True)
    if message.text == "/start":
        bot.send_message(message.chat.id, WELCOME_TEXT, parse_mode="Markdown", reply_markup=plans_keyboard())
    else:
        bot.send_message(message.chat.id, f"Получено: {message.text}")


@bot.message_handler(commands=["start"])
def start(message):
    bot.send_message(message.chat.id, WELCOME_TEXT, parse_mode="Markdown", reply_markup=plans_keyboard())


@bot.callback_query_handler(func=lambda call: call.data == "back")
def on_back(call):
    bot.edit_message_text(
        WELCOME_TEXT, call.message.chat.id, call.message.message_id,
        parse_mode="Markdown", reply_markup=plans_keyboard()
    )
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data.startswith("plan|"))
def on_plan_chosen(call):
    _, name = call.data.split("|")
    plan = find_plan(name)
    if not plan:
        bot.answer_callback_query(call.id, "Тариф не найден")
        return

    _, price_rub, price_stars = plan

    text = (
        f"Тариф: *{name}*\n"
        f"Цена: *{price_rub}\u20bd* (\u2248{price_stars}\u2B50)\n\n"
        f"Выбери способ оплаты:"
    )

    bot.edit_message_text(
        text, call.message.chat.id, call.message.message_id,
        parse_mode="Markdown", reply_markup=payment_keyboard(name)
    )
    bot.answer_callback_query(call.id)


# ---------- Telegram Stars ----------

@bot.callback_query_handler(func=lambda call: call.data.startswith("pay_stars|"))
def on_pay_stars(call):
    _, name = call.data.split("|")
    plan = find_plan(name)
    if not plan:
        bot.answer_callback_query(call.id, "Тариф не найден")
        return

    _, price_rub, price_stars = plan

    prices = [types.LabeledPrice(label=f"mvpeeker \u2014 {name}", amount=price_stars)]

    bot.send_invoice(
        chat_id=call.message.chat.id,
        title=f"mvpeeker \u2014 {name}",
        description="Подписка на калькулятор перекупа и аренды mvpeeker",
        invoice_payload=f"sub|{name}",
        provider_token="",  # для Stars оставляем пустым
        currency="XTR",
        prices=prices
    )
    bot.answer_callback_query(call.id)


@bot.pre_checkout_query_handler(func=lambda query: True)
def checkout(pre_checkout_query):
    bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)


@bot.message_handler(content_types=["successful_payment"])
def got_payment(message):
    payload = message.successful_payment.invoice_payload
    name = payload.split("|")[1] if "|" in payload else "?"
    amount = message.successful_payment.total_amount
    user = message.from_user
    username = f"@{user.username}" if user.username else "(нет username)"
    full_name = f"{user.first_name or ''} {user.last_name or ''}".strip()

    admin_text = (
        f"\u2705 *Оплата звёздами получена*\n\n"
        f"Пользователь: {full_name} {username}\n"
        f"ID: `{user.id}`\n"
        f"Тариф: *{name}*\n"
        f"Сумма: {amount}\u2B50\n\n"
        f"Сгенерируй ключ и отправь клиенту."
    )
    bot.send_message(ADMIN_ID, admin_text, parse_mode="Markdown")

    bot.send_message(
        message.chat.id,
        "Оплата прошла успешно! \u2705\n"
        "Продавец сейчас сгенерирует ключ и пришлёт его тебе в этот чат."
    )


# ---------- СБП / карта ----------

@bot.callback_query_handler(func=lambda call: call.data.startswith("pay_sbp|"))
def on_pay_sbp(call):
    _, name = call.data.split("|")
    plan = find_plan(name)
    if not plan:
        bot.answer_callback_query(call.id, "Тариф не найден")
        return

    _, price_rub, _ = plan

    text = (
        f"Тариф: *{name}* \u2014 *{price_rub}\u20bd*\n\n"
        f"Переведи по СБП на номер:\n"
        f"`{SBP_PHONE}`\n"
        f"{SBP_BANK}\n\n"
        f"После оплаты нажми кнопку ниже \u2014 продавец проверит платёж и пришлёт ключ."
    )

    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(types.InlineKeyboardButton(text="\u2705 Я оплатил", callback_data=f"confirm|{name}|СБП/карта|{price_rub}"))
    kb.add(types.InlineKeyboardButton(text="\u2190 Назад", callback_data=f"plan|{name}"))

    bot.edit_message_text(
        text, call.message.chat.id, call.message.message_id,
        parse_mode="Markdown", reply_markup=kb
    )
    bot.answer_callback_query(call.id)


# ---------- DonationAlerts ----------

@bot.callback_query_handler(func=lambda call: call.data.startswith("pay_donate|"))
def on_pay_donate(call):
    _, name = call.data.split("|")
    plan = find_plan(name)
    if not plan:
        bot.answer_callback_query(call.id, "Тариф не найден")
        return

    _, price_rub, _ = plan

    text = (
        f"Тариф: *{name}* \u2014 *{price_rub}\u20bd*\n\n"
        f"1. Перейди по ссылке и оплати на DonationAlerts\n"
        f"2. Вернись и нажми «Я оплатил»\n"
        f"3. Продавец проверит платёж и пришлёт ключ"
    )

    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(types.InlineKeyboardButton(text="\U0001F49C Перейти на DonationAlerts", url=DONATE_URL))
    kb.add(types.InlineKeyboardButton(text="\u2705 Я оплатил", callback_data=f"confirm|{name}|DonationAlerts|{price_rub}"))
    kb.add(types.InlineKeyboardButton(text="\u2190 Назад", callback_data=f"plan|{name}"))

    bot.edit_message_text(
        text, call.message.chat.id, call.message.message_id,
        parse_mode="Markdown", reply_markup=kb
    )
    bot.answer_callback_query(call.id)


# ---------- Подтверждение оплаты (ручные способы) ----------

@bot.callback_query_handler(func=lambda call: call.data.startswith("confirm|"))
def on_confirm(call):
    _, name, method, price_rub = call.data.split("|")
    user = call.from_user
    username = f"@{user.username}" if user.username else "(нет username)"
    full_name = f"{user.first_name or ''} {user.last_name or ''}".strip()

    admin_text = (
        f"\U0001F514 *Новая заявка*\n\n"
        f"Пользователь: {full_name} {username}\n"
        f"ID: `{user.id}`\n"
        f"Тариф: *{name}* \u2014 {price_rub}\u20bd\n"
        f"Способ оплаты: {method}\n\n"
        f"Проверь оплату и пришли ключ клиенту в личные сообщения."
    )
    bot.send_message(ADMIN_ID, admin_text, parse_mode="Markdown")

    bot.send_message(
        call.message.chat.id,
        "Спасибо! Заявка отправлена продавцу.\n"
        "Дождись подтверждения \u2014 ключ доступа придёт в этот чат в течение некоторого времени.\n\n"
        f"Если есть вопросы \u2014 пиши в [Telegram]({TELEGRAM_URL}).",
        parse_mode="Markdown"
    )
    bot.answer_callback_query(call.id, text="Заявка отправлена!")


@bot.message_handler(commands=["help"])
def help_cmd(message):
    bot.send_message(
        message.chat.id,
        "/start \u2014 показать тарифы\n"
        f"Поддержка: {TELEGRAM_URL}"
    )


# ====== FLASK / WEBHOOK ======

@app.route("/" + BOT_TOKEN, methods=["POST"])
def webhook():
    json_string = request.get_data().decode("utf-8")
    print("INCOMING UPDATE:", json_string, flush=True)
    try:
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
    except Exception as e:
        import traceback
        print("ERROR IN WEBHOOK:", e, flush=True)
        traceback.print_exc()
    return "OK", 200


@app.route("/")
def index():
    return "mvpeeker bot is running", 200


@app.route("/set_webhook")
def set_webhook():
    bot.remove_webhook()
    bot.set_webhook(url=f"{WEBHOOK_HOST}/{BOT_TOKEN}")
    return "Webhook set!", 200


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
