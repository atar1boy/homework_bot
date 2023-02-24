import time
import os
import sys
import telegram
import requests
import logging
from dotenv import load_dotenv
from http import HTTPStatus
import custom_exceptions


load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """Проверка доступности переменных окружения."""
    if (TELEGRAM_CHAT_ID and TELEGRAM_TOKEN and TELEGRAM_CHAT_ID) is None:
        logging.critical('Отсутсвуют переменные окружения.')
        raise custom_exceptions.CheckTokenError

    response = requests.get(
        f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/getMe'
    )
    if response.status_code != HTTPStatus.OK:
        logging.critical('Недоступна переменная окружения: TELEGRAM_TOKEN.')
        raise custom_exceptions.CheckTokenError

    response = requests.get(
        f'https://api.telegram.org/bot{TELEGRAM_TOKEN}'
        f'/getChat?chat_id={TELEGRAM_CHAT_ID}'
    )
    if response.status_code != HTTPStatus.OK:
        logging.critical('Недоступна переменная окружения: TELEGRAM_CHAT_ID.')
        raise custom_exceptions.CheckTokenError

    response = requests.get(ENDPOINT, headers=HEADERS, params={'from_date': 0})
    if response.status_code != HTTPStatus.OK:
        logging.critical('Недоступна переменная окружения: PRACTICUM_TOKEN.')
        raise custom_exceptions.CheckTokenError


def send_message(bot, message):
    """Отправка сообщения в телеграм чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)

    except Exception as error:
        logging.error('Ошибка отправки сообщения')
        raise custom_exceptions.SendMessageError(
            f'Ошибка отправки сообщения: {error}')

    else:
        logging.debug(f'Сообщение отправлено: {message}')


def get_api_answer(timestamp):
    """API запрос."""
    try:
        response = requests.get(
            ENDPOINT, headers=HEADERS, params={'from_date': timestamp}
        )
        if response.status_code != HTTPStatus.OK:
            raise custom_exceptions.ApiAnswerError

    except requests.RequestException:
        raise custom_exceptions.ApiAnswerError

    return response.json()


def check_response(response):
    """Проверка данных полученных из API."""
    if not isinstance(response, dict):
        raise TypeError

    if 'homeworks' and 'current_date' not in response:
        raise KeyError

    homeworks = response.get('homeworks')

    if not isinstance(homeworks, list):
        raise TypeError

    if not homeworks:
        raise custom_exceptions.NoUpdatesError

    return homeworks[0]


def parse_status(homework):
    """Обработка полученных данных."""
    if 'homework_name' not in homework.keys():
        raise KeyError

    if 'status' not in homework.keys():
        raise KeyError

    homework_name = homework.get('homework_name')
    status = homework.get('status')

    if status not in HOMEWORK_VERDICTS.keys():
        raise KeyError

    verdict = HOMEWORK_VERDICTS[status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    check_tokens()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    message_cache = 'None'
    homework_cache = 'None'

    while True:
        try:
            response = get_api_answer(timestamp)
            homework = check_response(response)
            if homework == homework_cache:
                raise custom_exceptions.NoUpdatesError
            homework_cache = homework
            message = parse_status(homework)
            send_message(bot, message)
            timestamp = response.get('current_date', timestamp)

        except custom_exceptions.NoUpdatesError:
            logging.debug('Отсутствуют изменения статуса работы')

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            if message != message_cache:
                message_cache = message
                logging.error(message)
                send_message(bot, message)

            else:
                logging.error(message)

        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format=('%(asctime)s [%(levelname)s] %(name)s,'
                ' line %(lineno)d, %(message)s'),
        handlers=[logging.StreamHandler(stream=sys.stdout)]
    )
    main()
