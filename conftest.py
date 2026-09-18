"""Общие настройки и фикстуры для API-тестов Miro.

Pytest автоматически находит файл conftest.py. Поэтому импортировать фикстуры
из него в тестовый файл вручную не нужно: достаточно указать имя фикстуры
в аргументах тестовой функции.
"""

import os
from collections.abc import Callable

import pytest
import requests


# Адрес API одинаков для всех тестов, поэтому храним его в одном месте.
MIRO_API_URL = "https://api.miro.com/v2"


@pytest.fixture(scope="session")
def board_id() -> str:
    """Получает ID доски из переменной окружения.

    scope="session" означает, что фикстура выполнится один раз за весь запуск.
    Если переменная не задана, тесты сразу остановятся с понятным сообщением.
    """

    value = os.getenv("MIRO_BOARD_ID")
    if not value:
        pytest.fail("Не задана переменная окружения MIRO_BOARD_ID")
    return value


@pytest.fixture(scope="session")
def miro_session() -> requests.Session:
    """Создаёт настроенную HTTP-сессию для всех запросов к Miro.

    Session хранит общие заголовки, поэтому в каждом тесте не приходится
    заново передавать токен и Content-Type.
    """

    token = os.getenv("MIRO_ACCESS_TOKEN")
    if not token:
        pytest.fail("Не задана переменная окружения MIRO_ACCESS_TOKEN")

    session = requests.Session()
    session.headers.update(
        {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
    )

    # yield передаёт готовую сессию тестам.
    yield session

    # Этот код выполняется один раз после завершения всех тестов.
    session.close()


@pytest.fixture
def sticky_note_factory(
    miro_session: requests.Session,
    board_id: str,
) -> Callable[..., dict]:
    """Возвращает функцию для создания Sticky Note и очищает тестовые данные.

    Обычная фикстура могла бы создавать один заранее определённый объект.
    Фабрика удобнее: каждый тест сам передаёт нужный текст, цвет и координаты.

    scope не указан, поэтому используется значение "function": отдельный
    список созданных объектов формируется для каждого теста.
    """

    created_item_ids: list[str] = []

    def create_sticky_note(
        content: str,
        fill_color: str = "light_yellow",
        x: float = 0,
        y: float = 0,
    ) -> dict:
        """Создаёт Sticky Note и возвращает разобранный JSON-ответ."""

        url = f"{MIRO_API_URL}/boards/{board_id}/sticky_notes"
        payload = {
            "data": {
                "content": content,
                "shape": "square",
            },
            "style": {
                "fillColor": fill_color,
            },
            "position": {
                "x": x,
                "y": y,
            },
        }

        response = miro_session.post(url, json=payload, timeout=20)

        # Проверка находится в фикстуре, потому что без успешно созданного
        # объекта остальные шаги теста выполнять невозможно.
        assert response.status_code == 201, (
            f"Не удалось создать Sticky Note. "
            f"Код: {response.status_code}; ответ: {response.text}"
        )

        item = response.json()
        assert "id" in item, f"В ответе отсутствует id: {item}"

        # Запоминаем ID, чтобы удалить объект после теста даже при падении
        # одной из последующих проверок.
        created_item_ids.append(item["id"])
        return item

    # До yield выполнялась подготовка. Здесь фабрика передаётся тесту.
    yield create_sticky_note

    # Всё после yield — завершающая очистка. Если тест сам уже удалил объект,
    # API вернёт 404. Это ожидаемо и не должно ломать результат теста.
    for item_id in created_item_ids:
        cleanup_url = (
            f"{MIRO_API_URL}/boards/{board_id}/sticky_notes/{item_id}"
        )
        try:
            response = miro_session.delete(cleanup_url, timeout=20)
            if response.status_code not in (204, 404):
                print(
                    f"Не удалось очистить Sticky Note {item_id}: "
                    f"{response.status_code} {response.text}"
                )
        except requests.RequestException as error:
            # Ошибка очистки выводится отдельно и не скрывает результат теста.
            print(f"Ошибка при очистке Sticky Note {item_id}: {error}")
