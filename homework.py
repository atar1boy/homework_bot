import time
import os
import telegram
import requests
import logging
from dotenv import load_dotenv
from http import HTTPStatus
from functools import wraps

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


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

log_format = '%(asctime)s [%(levelname)s] %(message)s'
log_formatter = logging.Formatter(log_format, style='%')

stream_handler = logging.StreamHandler()
stream_handler.setFormatter(log_formatter)

logger.addHandler(stream_handler)


def cache_status(func):
    """Декоратор кэширующий статус домашней работы."""
    cache = {'date_updated': None}

    @wraps(func)
    def wrapper(args):

        if cache['date_updated'] != args.get('date_updated'):
            date_updated = args.get('date_updated')
            cache['date_updated'] = date_updated
            return func(args)
        logger.debug('Статус домашней работы не изменился')

    return wrapper


def cache_error_messages(func):
    """Декоратор кэширующий сообщения об ошибке."""
    сache = {'message': None}

    @wraps(func)
    def wrapper(bot, message):
        if message != сache['message']:
            сache['message'] = message
            return func(bot, message)
        if сache['message'] is not None:
            logger.error(message)

    return wrapper


def check_tokens():
    """Проверка доступности переменных окружения."""
    if (TELEGRAM_CHAT_ID and TELEGRAM_TOKEN and TELEGRAM_CHAT_ID) is None:
        logger.critical('Отсутствуют переменные окружения')
        raise ValueError

    response = requests.get(
        f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/getMe'
    )
    if response.status_code != HTTPStatus.OK:
        logger.critical('Недоступна переменная окружения: TELEGRAM_TOKEN')
        raise ValueError

    response = requests.get(
        f'https://api.telegram.org/bot{TELEGRAM_TOKEN}'
        f'/getChat?chat_id={TELEGRAM_CHAT_ID}'
    )
    if response.status_code != HTTPStatus.OK:
        logger.critical('Недоступна переменная окружения: TELEGRAM_CHAT_ID')
        raise ValueError

    response = requests.get(ENDPOINT, headers=HEADERS, params={'from_date': 0})
    if response.status_code != HTTPStatus.OK:
        logger.critical('Недоступна переменная окружения: ENDPOINT')
        raise ValueError


@cache_error_messages
def send_message(bot, message):
    """Отправка сообщения в телеграм чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug(f'Сообщение успешно отправлено: {message}')
    except Exception as error:
        logger.error(f'Неудалось отправить сообщение: {error}')


def get_api_answer(timestamp):
    """API запрос."""
    try:
        response = requests.get(
            ENDPOINT, headers=HEADERS, params={'from_date': timestamp}
        )
        if response.status_code != HTTPStatus.OK:
            logger.critical(f'Ошибка API запроса: {response.status_code}')
            raise ValueError
    except requests.RequestException:
        raise ValueError
    return response.json()


def check_response(response):
    """Проверка данных полученных из API."""
    if not isinstance(response, dict):
        logger.error(f'Получен неожиданный тип данных: {type(response)}')
        raise TypeError
    if 'homeworks' and 'current_date' not in response:
        logger.error(f'Получены неожиданные ключи словаря: {response.keys()}')
        raise KeyError
    homeworks = response.get('homeworks')
    if not isinstance(homeworks, list):
        logger.error(f'Получен неожиданный тип данных: {type(response)}')
        raise TypeError
    return homeworks[0]


@cache_status
def parse_status(homework):
    """Обработка полученных данных."""
    print(homework.keys())
    if 'homework_name' and 'status' not in homework.keys():
        logger.error(f'Получены неожиданные ключи словаря: {homework.keys()}')
        raise KeyError
    homework_name = homework.get('homework_name')
    status = homework.get('status')
    if status not in HOMEWORK_VERDICTS.keys():
        logger.error(f'Неожиданный статус работы: {status}')
        raise KeyError
    verdict = HOMEWORK_VERDICTS[status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    while True:
        timestamp = 0
        check_tokens()
        bot = telegram.Bot(token=TELEGRAM_TOKEN)
        try:
            response = get_api_answer(timestamp)
            homework = check_response(response)
            message = parse_status(homework)
            send_message(bot, message)

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            send_message(bot, message)

        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
