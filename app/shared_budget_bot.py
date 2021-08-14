# !/usr/bin/python3
# -*- coding: utf-8 -*-
import configparser
import time
import logging as log
import os.path
import pickle
import telebot
from datetime import date
from telebot import types
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request


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
        self.config["sheets"]["scope"] = " https://www.googleapis.com/auth/spreadsheets"
        self.config["sheets"]["spreadsheet_id"] = "SPREADSHEET_ID"
        self.config["sheets"]["sheet_id"] = "SHEET_ID"

        with open(self.config_file_path, "w") as config_file:
            self.config.write(config_file)

    def get(self):
        """Obtain configuration"""
        return self.config


config = Config().get()
SCOPES = [config["sheets"]["scope"]]
SPREADSHEET_ID = config["sheets"]["spreadsheet_id"]
SHEET_ID = config["sheets"]["sheet_id"]
bot = telebot.TeleBot(config["telegram"]["token"], threaded=False)


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
    if is_float(message.text):
        half_of_amount = str(float(message.text.replace(",", ".")) / 2)
        values = [time.strftime("%d-%m-%Y %H:%M"), "", "", ""]
        if str(message.chat.id) == config["telegram"]["person_1_tg_id"]:
            debtor = "Ани"
            values[2] = half_of_amount
        if str(message.chat.id) == config["telegram"]["person_2_tg_id"]:
            debtor = "Стаса"
            values[3] = half_of_amount
        markup = generate_markup()
        msg = bot.reply_to(
            message,
            f"Я запишу {half_of_amount} SEK на счет {debtor}. Теперь выбери категорию",
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
        float(string.replace(",", "."))
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


def process_category(message, *values):
    if values:
        category = message.text
        markup = types.ReplyKeyboardRemove(selective=False)
        message = bot.reply_to(message, "Теперь введи описание", reply_markup=markup)
        bot.register_next_step_handler(
            message, lambda m: process_description(category, m, values)
        )


def process_description(category, message, *values):
    if values:
        listed_values = list_it(values)[0][0]
        listed_values[1] = f'"{category}", "{message.text}"'
        insert_message = ", ".join(listed_values)
        log.info(insert_message)
        insert_raw(build_service(), insert_message)
        bot.reply_to(message, "Готово!")


def build_service():
    creds = None
    # The file backup_token.pickle stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists("token.pickle"):
        with open("token.pickle", "rb") as token:
            creds = pickle.load(token)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            log.info("Credentials are expired")
            creds.refresh(Request())
        else:
            log.info("Credentials don't exist")
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server()
        # Save the credentials for the next run
        with open("token.pickle", "wb") as token:
            pickle.dump(creds, token)

    return build("sheets", "v4", credentials=creds)


def insert_raw(service, insert_text):
    requests = [
        {
            "insertRange": {
                "range": {"sheetId": SHEET_ID, "startRowIndex": 3, "endRowIndex": 4},
                "shiftDimension": "ROWS",
            }
        },
        {
            "pasteData": {
                "data": insert_text,
                "type": "PASTE_NORMAL",
                "delimiter": ",",
                "coordinate": {"sheetId": SHEET_ID, "rowIndex": 3},
            }
        },
    ]

    body = {"requests": requests}
    service.spreadsheets().batchUpdate(
        spreadsheetId=SPREADSHEET_ID, body=body
    ).execute()
    return 0


def notify_about_balance():
    service = build_service()
    request = (
        service.spreadsheets()
        .values()
        .get(
            spreadsheetId=SPREADSHEET_ID,
            range="I2",
            valueRenderOption="UNFORMATTED_VALUE",
            dateTimeRenderOption="SERIAL_NUMBER",
        )
    )
    response = request.execute()
    cell_value = response["values"][0][0]
    if cell_value > 0:
        message = f"Доброе утро! На сегодняшний день Стас заплатил на {int(cell_value)} SEK больше, чем Аня"
    else:
        message = f"Доброе утро! На сегодняшний день Аня заплатила на {int(abs(cell_value))} SEK больше, чем Стас"
    bot.send_message(config["telegram"]["person_1_tg_id"], message)
    bot.send_message(config["telegram"]["person_2_tg_id"], message)


if __name__ == "__main__":
    bot.polling()
