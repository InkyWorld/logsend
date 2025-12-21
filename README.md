# LogSend

Python logger для отправки логов в [Vector](https://vector.dev/) через HTTP с хранением в SQLite.

## Особенности

- 📤 Отправка логов в Vector через HTTP
- 💾 Хранение логов в SQLite (надёжная очередь)
- ⏱️ Отправка в фоне по таймеру или по количеству
- 🔄 Автоматические retry при ошибках
- 📦 Буферизация логов
- 🔗 Интеграция со стандартным `logging` модулем Python
- 💪 Persistence: неотправленные логи сохраняются в SQLite

## Установка

### С GitHub

```bash
pip install git+https://github.com/yourusername/logsend.git
```

### Локальная установка для разработки

```bash
git clone https://github.com/yourusername/logsend.git
cd logsend
pip install -e .
```

## Использование

### Основной API

```python
from logsend import LogSend, LogLevel

# Создание логера (project и table обязательны!)
logger = LogSend(
    vector_url="http://localhost:8080",  # URL Vector HTTP source
    project="my-project",                 # Обязательно! Имя проекта
    table="application_logs",             # Обязательно! Имя таблицы
    db_path="./logs/queue.db",            # Путь к SQLite базе
    batch_size=100,                       # Отправлять после 100 записей
    flush_interval=5.0,                   # Или каждые 5 секунд
    level=LogLevel.DEBUG,                 # Минимальный уровень логирования
    extra_fields={                        # Дополнительные поля для всех логов
        "environment": "production",
        "version": "1.0.0"
    }
)

# Логирование
logger.debug("Debug message")
logger.info("User logged in", extra={"user_id": 123, "ip": "192.168.1.1"})
logger.warning("High memory usage", extra={"memory_percent": 85})
logger.error("Database connection failed", extra={"host": "db.example.com"})
logger.critical("System shutdown required")

# Проверить количество неотправленных логов
print(f"Pending: {logger.pending_count()}")

# Принудительная отправка
logger.flush()

# Закрытие (важно для отправки оставшихся логов)
logger.close()
```

### Context Manager

```python
from logsend import LogSend

with LogSend(
    vector_url="http://localhost:8080",
    project="my-project",
    table="app_logs",
) as logger:
    logger.info("Application started")
    # ... ваш код ...
    logger.info("Application finished")
# Логи автоматически отправляются при выходе
```

### Интеграция со стандартным logging

```python
import logging
from logsend import VectorHandler

# Создание handler (project и table обязательны!)
handler = VectorHandler(
    vector_url="http://localhost:8080",
    project="my-project",
    table="app_logs",
    db_path="./logs/queue.db",
    batch_size=50,
    flush_interval=10.0,
)

# Добавление к logger
logger = logging.getLogger("my_app")
logger.addHandler(handler)
logger.setLevel(logging.DEBUG)

# Использование как обычно
logger.info("Hello from standard logging!")
logger.error("Something went wrong", extra={"details": "error details"})

# Закрытие при завершении
handler.close()
```

## Конфигурация Vector

Пример конфигурации Vector для приёма логов:

```toml
# vector.toml

[sources.http_logs]
type = "http_server"
address = "0.0.0.0:8080"
encoding = "json"

[sinks.console]
type = "console"
inputs = ["http_logs"]
encoding.codec = "json"

[sinks.file]
type = "file"
inputs = ["http_logs"]
path = "/var/log/vector/logs-%Y-%m-%d.json"
encoding.codec = "json"
```

Запуск Vector:

```bash
vector --config vector.toml
```

## Параметры

### LogSend

| Параметр | Тип | По умолчанию | Описание |
|----------|-----|--------------|----------|
| `vector_url` | str | обязательный | URL Vector HTTP endpoint |
| `project` | str | обязательный | Имя проекта (включается в каждый лог) |
| `table` | str | обязательный | Имя таблицы (включается в каждый лог) |
| `db_path` | str | `"./logs/queue.db"` | Путь к SQLite базе для очереди |
| `batch_size` | int | `100` | Количество логов для буферизации перед отправкой |
| `flush_interval` | float | `5.0` | Интервал автоматической отправки (секунды) |
| `max_retries` | int | `3` | Максимальное количество попыток при ошибке |
| `retry_delay` | float | `1.0` | Задержка между попытками (секунды) |
| `level` | LogLevel | `DEBUG` | Минимальный уровень логирования |
| `extra_fields` | dict | `None` | Дополнительные поля для всех логов |

### VectorHandler

| Параметр | Тип | По умолчанию | Описание |
|----------|-----|--------------|----------|
| `vector_url` | str | обязательный | URL Vector HTTP endpoint |
| `project` | str | обязательный | Имя проекта |
| `table` | str | обязательный | Имя таблицы |
| `db_path` | str | `"./logs/queue.db"` | Путь к SQLite базе |
| `batch_size` | int | `100` | Количество логов для буферизации |
| `flush_interval` | float | `5.0` | Интервал автоматической отправки |
| `max_retries` | int | `3` | Максимальное количество попыток |
| `retry_delay` | float | `1.0` | Задержка между попытками |
| `extra_fields` | dict | `None` | Дополнительные поля |
| `level` | int | `NOTSET` | Минимальный уровень |

## Формат логов

Логи отправляются в формате JSON (NDJSON):

```json
{
  "timestamp": "2024-01-15T10:30:00.123Z",
  "level": "INFO",
  "level_num": 20,
  "message": "User logged in",
  "project": "my-project",
  "table": "application_logs",
  "extra": {
    "user_id": 123,
    "ip": "192.168.1.1"
  },
  "environment": "production",
  "version": "1.0.0"
}
```

## Лицензия

MIT
