class SendMessageError(Exception):
    """Ошибка при неотправленном сообщении."""


class CheckTokenError(Exception):
    """Ошибка недоступности переменных окружения.."""


class ApiAnswerError(Exception):
    """Ошибка API запроса."""


class NoUpdatesError(Exception):
    """Отсутствуют изменения статуса работы."""
