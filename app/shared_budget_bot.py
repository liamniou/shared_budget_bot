# !/usr/bin/python3
# -*- coding: utf-8 -*-
import configparser
import time
import logging as log
import os.path
import pickle
import telebot
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request


class Config():
    config = configparser.ConfigParser()
    config_file_path = None

    def __init__(self):
        self.config_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config')
        self.load_config()

    def load_config(self):
        '''Load configuration parameters'''
        if os.path.exists(self.config_file_path):
            self.config.read(self.config_file_path)
        else:
            self.set_default_config()

    def set_default_config(self):
        '''Set default configuration'''
        self.config['telegram'] = {}
        self.config['telegram']['token'] = 'TELEGRAM_BOT_TOKEN'
        self.config['telegram']['person_1_tg_id'] = 'TG_ID_OF_FIRST_PERSON'
        self.config['telegram']['person_2_tg_id'] = 'TG_ID_OF_SECOND_PERSON'
        self.config['sheets'] = {}
        self.config['sheets']['scope'] = ' https://www.googleapis.com/auth/spreadsheets'
        self.config['sheets']['spreadsheet_id'] = 'SPREADSHEET_ID'
        self.config['sheets']['sheet_id'] = 'SHEET_ID'

        with open(self.config_file_path, 'w') as config_file:
            self.config.write(config_file)

    def get(self):
        '''Obtain configuration'''
        return self.config


config = Config().get()
SCOPES = [config['sheets']['scope']]
SPREADSHEET_ID = config['sheets']['spreadsheet_id']
SHEET_ID = config['sheets']['sheet_id']
bot = telebot.TeleBot(config['telegram']['token'], threaded=False)


@bot.message_handler(commands=['start', 'help'])
def greet_new_user(message):
    bot.send_message(message.chat.id, "Привет! Я помогу тебе вести совместный бюджет! "
                                      "Ты прислыаешь мне сумму, я делю её пополам, "
                                      "спрашиваю тебя что была за покупка и заношу в табличку.")


@bot.message_handler(content_types=['text'])
def process_amount(message):
    if is_float(message.text):
        half_of_amount = str(float(message.text.replace(",", ".")) / 2)
        values = [time.strftime("%d-%m-%Y %H:%M"), "", "", ""]
        if str(message.chat.id) == config['telegram']['person_1_tg_id']:
            debtor = "Ани"
            values[2] = half_of_amount
        if str(message.chat.id) == config['telegram']['person_2_tg_id']:
            debtor = "Стаса"
            values[3] = half_of_amount
        msg = bot.reply_to(
            message, "Я запишу {} SEK на счет {}. Теперь введи описание".format(half_of_amount, debtor))
        bot.register_next_step_handler(
            msg, lambda m: process_description(m, values))
    else:
        msg = bot.reply_to(message, "Не получается преобразовать сообщение в число, попробуй еще раз")
        bot.register_next_step_handler(
            msg, lambda m: process_amount(m))


def is_float(string):
    try:
        float(string.replace(",", "."))
        return True
    except ValueError:
        return False


def process_description(message, *values):
    if values:
        values[0][1] = "\"{}\"".format(message.text)
        insert_raw(build_service(), values[0])
        bot.reply_to(message, "Готово!")


def build_service():
    creds = None
    # The file backup_token.pickle stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            log.info("Credentials are expired")
            creds.refresh(Request())
        else:
            log.info("Credentials don't exist")
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server()
        # Save the credentials for the next run
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)

    return build('sheets', 'v4', credentials=creds)


def insert_raw(service, values):
    requests = [{
        "insertRange": {
            "range": {
                "sheetId": SHEET_ID,
                "startRowIndex": 3,
                "endRowIndex": 4
            },
            "shiftDimension": "ROWS"
        }
    },
    {
        "pasteData": {
            "data": ", ".join(values),
            "type": "PASTE_NORMAL",
            "delimiter": ",",
            "coordinate": {
                "sheetId": SHEET_ID,
                "rowIndex": 3
            }
        }
    }]

    body = {
        'requests': requests
    }
    service.spreadsheets().batchUpdate(
        spreadsheetId=SPREADSHEET_ID,
        body=body).execute()
    return 0


if __name__ == '__main__':
    bot.polling()
