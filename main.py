import json
import sys
import textwrap
from typing import Any, Dict, List, Optional

import requests

BASE_URL = "https://api-seller.ozon.ru/"

COMMANDS = {
    "v1/analytics/stocks": {
        "method": "post",
        "summary": "Получить аналитику по остаткам",
        "schema": {
            "type": "object",
            "properties": {
                "cluster_ids": {"type": "array", "items": {"type": "string"}},
                "item_tags": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": [
                            "ITEM_ATTRIBUTE_NONE",
                            "ITEM_ATTRIBUTE_BEST_SELLER",
                            "ITEM_ATTRIBUTE_EXCLUSIVE",
                        ],
                    },
                },
                "skus": {"type": "array", "items": {"type": "string"}},
                "turnover_grades": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": [
                            "TURNOVER_GRADE_NONE",
                            "TURNOVER_GRADE_GREEN",
                            "TURNOVER_GRADE_YELLOW",
                            "TURNOVER_GRADE_RED",
                        ],
                    },
                },
                "warehouse_ids": {"type": "array", "items": {"type": "string"}},
            },
            "required": [],
        },
    },
    "v3/supply-order/get": {
        "method": "post",
        "summary": "Получить информацию о заявках на поставку",
        "schema": {
            "type": "object",
            "properties": {
                "order_ids": {"type": "array", "items": {"type": "integer"}},
            },
            "required": ["order_ids"],
        },
    },
    "v3/supply-order/list": {
        "method": "post",
        "summary": "Список заявок на поставку",
        "schema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "default": 100},
                "offset": {"type": "integer", "default": 0},
                "status": {"type": "string"},
            },
            "required": [],
        },
    },
}


def prompt_for_value(name: str, schema: Dict[str, Any]) -> Any:
    schema_type = schema.get("type")
    if schema_type == "object":
        return prompt_for_object(schema)
    if schema_type == "array":
        item_schema = schema.get("items", {})
        values: List[Any] = []
        print(f"Введите значения для массива {name} (пустая строка для завершения):")
        while True:
            raw = input("  ➜ элемент: ").strip()
            if raw == "":
                break
            values.append(convert_primitive(raw, item_schema))
        return values
    return convert_primitive(input(f"Введите {name}: ").strip(), schema)


def convert_primitive(raw: str, schema: Dict[str, Any]) -> Any:
    if raw == "" and schema.get("default") is not None:
        return schema["default"]
    if schema.get("enum"):
        options = ", ".join(schema["enum"])
        if raw == "":
            raw = input(f"  Возможные значения ({options}). Выберите: ").strip()
        return raw
    schema_type = schema.get("type")
    if schema_type == "integer":
        return int(raw)
    if schema_type == "number":
        return float(raw)
    if schema_type == "boolean":
        return raw.lower() in {"true", "1", "yes", "y", "да"}
    return raw


def prompt_for_object(schema: Dict[str, Any]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    properties = schema.get("properties", {})
    required = set(schema.get("required", []))
    for prop, prop_schema in properties.items():
        is_required = prop in required
        title = prop_schema.get("description") or prop
        if not is_required:
            choice = input(f"Заполнить необязательное поле '{title}'? [y/N]: ").strip().lower()
            if choice not in {"y", "yes", "д", "да"}:
                continue
        result[prop] = prompt_for_value(title, prop_schema)
    return result


def prompt_for_payload(schema: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not schema:
        raw = input("Введите тело запроса в формате JSON (или оставьте пустым): ")
        return json.loads(raw) if raw else {}
    if schema.get("type") == "object":
        print("Заполните поля запроса (оставьте пустым, если не хотите заполнять необязательные поля):")
        return prompt_for_object(schema)
    raw = input("Введите тело запроса в формате JSON: ")
    return json.loads(raw) if raw else {}


def pretty_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


def verify_credentials(client_id: str, api_key: str) -> bool:
    try:
        response = requests.post(
            BASE_URL + "v1/warehouse/list",
            headers={"Client-Id": client_id, "Api-Key": api_key},
            json={},
            timeout=15,
        )
        return response.status_code == 200
    except Exception:
        return False


def choose_command(commands: Dict[str, Dict[str, Any]]) -> Optional[str]:
    print("Доступные методы:")
    for idx, (name, meta) in enumerate(sorted(commands.items()), start=1):
        summary = meta.get("summary", "")
        print(f"  {idx}. {name} — {summary}")
    raw = input("Выберите номер команды (или Enter для выхода): ").strip()
    if not raw:
        return None
    try:
        idx = int(raw)
    except ValueError:
        print("Введите корректный номер.")
        return choose_command(commands)
    items = list(sorted(commands.items()))
    if not (1 <= idx <= len(items)):
        print("Неверный номер.")
        return choose_command(commands)
    return items[idx - 1][0]


def run_command(command: str, meta: Dict[str, Any], client_id: str, api_key: str) -> None:
    method = meta.get("method", "post").lower()
    schema = meta.get("schema")
    payload = prompt_for_payload(schema)
    url = BASE_URL + command
    print("\nСформированный запрос:")
    print(f"{method.upper()} {url}")
    print(pretty_json(payload))
    try:
        response = requests.request(
            method,
            url,
            headers={
                "Client-Id": client_id,
                "Api-Key": api_key,
                "Content-Type": "application/json",
            },
            json=payload if payload else None,
            timeout=30,
        )
        print("\nОтвет сервера:")
        try:
            print(pretty_json(response.json()))
        except Exception:
            print(response.text)
    except Exception as exc:
        print(f"Не удалось выполнить запрос: {exc}")


def main() -> None:
    print(
        textwrap.dedent(
            """
            ==============================
            Добро пожаловать в OZON API CLI
            ==============================
            Эта консоль содержит основные методы OZON API и позволяет запускать
            запросы с подсказками по вводу.
            """
        )
    )
    client_id = input("Введите Client-Id: ").strip()
    api_key = input("Введите Api-Key: ").strip()
    if not client_id or not api_key:
        print("Требуется указать Client-Id и Api-Key.")
        sys.exit(1)

    print("Проверяем ключи...")
    if not verify_credentials(client_id, api_key):
        print("Не удалось подтвердить ключ. Проверьте данные и попробуйте снова.")
        sys.exit(1)
    print("Ключ подтверждён. Загружаем список методов...")
    commands = COMMANDS

    if not commands:
        print("Не удалось собрать список команд. Завершение работы.")
        sys.exit(1)

    while True:
        selected = choose_command(commands)
        if not selected:
            print("До встречи!")
            break
        run_command(selected, commands[selected], client_id, api_key)


if __name__ == "__main__":
    main()
