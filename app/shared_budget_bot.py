# !/usr/bin/python3
# -*- coding: utf-8 -*-
import configparser
import logging as log
import os.path
import time

import gspread
import telebot
from telebot import types


class Config:
    config = configparser.ConfigParser()
    config_file_path = None

    def __init__(self):
        self.config_file_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "config"
        )
        self.load_config()

    def load_config(self):
        """Load configuration parameters"""
        if os.path.exists(self.config_file_path):
            self.config.read(self.config_file_path)
        else:
            self.set_default_config()

    def set_default_config(self):
        """Set default configuration"""
        self.config["telegram"] = {}
        self.config["telegram"]["token"] = "TELEGRAM_BOT_TOKEN"
        self.config["telegram"]["person_1_tg_id"] = "TG_ID_OF_FIRST_PERSON"
        self.config["telegram"]["person_2_tg_id"] = "TG_ID_OF_SECOND_PERSON"
        self.config["sheets"] = {}
        self.config["sheets"]["spreadsheet_id"] = "SPREADSHEET_ID"
        self.config["sheets"]["sheet_name"] = "Expenses"

        with open(self.config_file_path, "w") as config_file:
            self.config.write(config_file)

    def get(self):
        """Obtain configuration"""
        return self.config


config = Config().get()
bot = telebot.TeleBot(config["telegram"]["token"], threaded=False)
gc = gspread.service_account(
    filename=os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "service_account.json"
    )
)
spreadsheet = gc.open_by_key(config["sheets"]["spreadsheet_id"])
worksheet = spreadsheet.worksheet(config["sheets"]["sheet_name"])


@bot.message_handler(commands=["start", "help"])
def greet_new_user(message):
    bot.send_message(
        message.chat.id,
        "Привет! Я помогу тебе вести совместный бюджет! "
        "Ты присылаешь мне сумму, я делю её пополам, "
        "спрашиваю тебя что была за покупка и заношу в табличку.",
    )


@bot.message_handler(commands=["balance"])
def send_balance(message):
    log.info(message.text)
    notify_about_balance()


@bot.message_handler(content_types=["text"])
def process_amount(message):
    message_text = message.text.replace(",", ".")
    if is_float(eval(message_text)):
        half_of_amount = eval(message_text) / 2
        values = [time.strftime("%d-%m-%Y %H:%M"), "", "", "", ""]
        if (
            str(message.chat.id) == config["telegram"]["person_1_tg_id"]
            and half_of_amount > 0
        ):
            debtor = "Ани"
            values[3] = half_of_amount
        if (
            str(message.chat.id) == config["telegram"]["person_1_tg_id"]
            and half_of_amount < 0
        ):
            debtor = "Стаса"
            values[4] = half_of_amount * -1
        if (
            str(message.chat.id) == config["telegram"]["person_2_tg_id"]
            and half_of_amount > 0
        ):
            debtor = "Стаса"
            values[4] = half_of_amount
        if (
            str(message.chat.id) == config["telegram"]["person_2_tg_id"]
            and half_of_amount < 0
        ):
            debtor = "Ани"
            values[3] = half_of_amount * -1
        markup = generate_markup()
        msg = bot.reply_to(
            message,
            f"Я запишу {abs(half_of_amount)} SEK на счет {debtor}. Теперь выбери категорию",
            reply_markup=markup,
        )
        bot.register_next_step_handler(msg, lambda m: process_category(m, values))
    else:
        msg = bot.reply_to(
            message, "Не получается преобразовать сообщение в число, попробуй еще раз"
        )
        bot.register_next_step_handler(msg, lambda m: process_amount(m))


def is_float(string):
    try:
        float(string)
        return True
    except ValueError:
        return False


def list_it(t):
    return list(map(list_it, t)) if isinstance(t, (list, tuple)) else t


def generate_markup():
    markup = types.ReplyKeyboardMarkup()
    button_1 = types.KeyboardButton("🛒 Еда")
    button_2 = types.KeyboardButton("🛀 Для дома")
    button_3 = types.KeyboardButton("🦴 Зоя")
    button_4 = types.KeyboardButton("🍸 Отдых")
    button_5 = types.KeyboardButton("🏠 Аренда")
    button_6 = types.KeyboardButton("🚌 Транспорт")
    button_7 = types.KeyboardButton("💧 Платежи")
    button_8 = types.KeyboardButton("📦 Другое")
    button_9 = types.KeyboardButton("💸 Расчет")
    markup.add(button_1, button_2, button_3)
    markup.add(button_4, button_5, button_6)
    markup.add(button_7, button_8, button_9)

    return markup


def process_category(message, values):
    if values:
        category = message.text
        values[1] = category
        markup = types.ReplyKeyboardRemove(selective=False)
        message = bot.reply_to(message, "Теперь введи описание", reply_markup=markup)
        bot.register_next_step_handler(
            message, lambda m: process_description(m, values)
        )


def process_description(message, values):
    if values:
        description = message.text
        values[2] = description
        insert_raw(values)
        bot.reply_to(message, "Готово!")


def insert_raw(insert_text):
    print(f"Inserting {insert_text}")
    worksheet.insert_row(values=insert_text, index=4)

    return 0


def notify_about_balance():
    cell_value = float(worksheet.cell(2, 9).value)
    if cell_value > 0:
        message = f"Привет! На сегодняшний день Стас заплатил на {cell_value} SEK больше, чем Аня"
    else:
        message = f"Привет! На сегодняшний день Аня заплатила на {abs(cell_value)} SEK больше, чем Стас"
    bot.send_message(config["telegram"]["person_1_tg_id"], message)
    bot.send_message(config["telegram"]["person_2_tg_id"], message)

    return 0


if __name__ == "__main__":
    bot.polling()
