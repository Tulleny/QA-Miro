"""Три API-теста операций со Sticky Note в Miro."""

from uuid import uuid4

import allure
import pytest
import requests

from conftest import MIRO_API_URL


def unique_text(prefix: str) -> str:
    """Добавляет уникальный фрагмент, чтобы тесты не путали свои объекты."""

    return f"{prefix} {uuid4()}"


def attach_response(response: requests.Response) -> None:
    """Прикладывает ответ Miro к Allure-отчёту для удобства разбора ошибок."""

    allure.attach(
        response.text or "Пустое тело ответа",
        name=f"HTTP {response.status_code}",
        attachment_type=allure.attachment_type.JSON,
    )


@allure.feature("Miro REST API")
@allure.story("Sticky Notes")
@allure.title("Создание и получение Sticky Note")
def test_create_and_get_sticky_note(
    miro_session: requests.Session,
    board_id: str,
    sticky_note_factory,
) -> None:
    """Создаёт объект, получает его по ID и сравнивает основные поля."""

    expected_text = unique_text("Создание через API")

    with allure.step("Создать Sticky Note"):
        # Фабрика сама проверит код 201 и запомнит ID для последующей очистки.
        created_item = sticky_note_factory(content=expected_text)
        item_id = created_item["id"]

    with allure.step("Получить созданный Sticky Note по его ID"):
        url = f"{MIRO_API_URL}/boards/{board_id}/sticky_notes/{item_id}"
        response = miro_session.get(url, timeout=20)
        attach_response(response)

        assert response.status_code == 200
        received_item = response.json()

    with allure.step("Проверить основные поля ответа"):
        assert received_item["id"] == item_id
        assert received_item["type"] == "sticky_note"

        # Miro может добавить к тексту HTML-теги, например <p>...</p>.
        # Поэтому проверяем наличие нашей строки, а не полное равенство.
        assert expected_text in received_item["data"]["content"]


@allure.feature("Miro REST API")
@allure.story("Sticky Notes")
@allure.title("Изменение Sticky Note и проверка результата")
def test_update_sticky_note(
    miro_session: requests.Session,
    board_id: str,
    sticky_note_factory,
) -> None:
    """Изменяет текст, цвет и положение, затем проверяет их через GET."""

    created_item = sticky_note_factory(content=unique_text("Исходный текст"))
    item_id = created_item["id"]
    updated_text = unique_text("Изменённый текст")
    expected_x = 250
    expected_y = 150

    url = f"{MIRO_API_URL}/boards/{board_id}/sticky_notes/{item_id}"
    payload = {
        "data": {"content": updated_text},
        "style": {"fillColor": "light_green"},
        "position": {"x": expected_x, "y": expected_y},
    }

    with allure.step("Изменить Sticky Note запросом PATCH"):
        update_response = miro_session.patch(url, json=payload, timeout=20)
        attach_response(update_response)
        assert update_response.status_code == 200

    with allure.step("Получить объект после изменения"):
        get_response = miro_session.get(url, timeout=20)
        attach_response(get_response)
        assert get_response.status_code == 200
        updated_item = get_response.json()

    with allure.step("Проверить сохранённые изменения"):
        assert updated_text in updated_item["data"]["content"]
        assert updated_item["style"]["fillColor"] == "light_green"

        # approx допускает незначительную разницу при работе с float.
        assert updated_item["position"]["x"] == pytest.approx(expected_x)
        assert updated_item["position"]["y"] == pytest.approx(expected_y)


@allure.feature("Miro REST API")
@allure.story("Sticky Notes")
@allure.title("Удаление Sticky Note и проверка отсутствия")
def test_delete_sticky_note(
    miro_session: requests.Session,
    board_id: str,
    sticky_note_factory,
) -> None:
    """Удаляет объект и убеждается, что получить его повторно нельзя."""

    created_item = sticky_note_factory(content=unique_text("Для удаления"))
    item_id = created_item["id"]
    url = f"{MIRO_API_URL}/boards/{board_id}/sticky_notes/{item_id}"

    with allure.step("Удалить Sticky Note"):
        delete_response = miro_session.delete(url, timeout=20)
        attach_response(delete_response)
        assert delete_response.status_code == 204

    with allure.step("Попытаться получить удалённый объект"):
        get_response = miro_session.get(url, timeout=20)
        attach_response(get_response)
        assert get_response.status_code == 404

    # После теста фабрика ещё раз попробует удалить этот ID. Она допускает
    # ответ 404, поэтому повторная очистка не приведёт к ошибке.
