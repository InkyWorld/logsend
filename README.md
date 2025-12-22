# LogSend

A Python logger with SQLite storage for sending logs to Vector via HTTP.

## Description

**LogSend** is an asynchronous Python logger that stores logs in a local SQLite database and sends them to a Vector server via HTTP. Perfect for applications that require reliable log storage with guaranteed delivery.

## Key Features

- ✅ Asynchronous log delivery to Vector
- ✅ Local disk-based log storage (SQLite)
- ✅ Batch sending for network traffic optimization
- ✅ Support for different log levels (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- ✅ Additional fields and context in each log
- ✅ Automatic log queue management

## Installation

### From Source

```bash
pip install -e .
```

### With Development Dependencies

```bash
pip install -e ".[dev]"
```

## Requirements

- Python 3.8+
- requests >= 2.25.0

## Quick Start

```python
from logsend import LogSend, LogLevel

# Create a logger instance
logger = LogSend(
    vector_url="http://localhost:8080",
    project="my-project",           # Required!
    table="application_logs",       # Required!
    db_path="./logs/queue.db",
    batch_size=1000,
    level=LogLevel.DEBUG,
    extra_fields={"environment": "production", "version": "1.0.0"},
)

# Log messages
logger.debug("Debug message")
logger.info("Informational message")
logger.warning("Warning message")
logger.error("Error occurred", extra={"error_code": "E001"})

# Send remaining logs
logger.flush()
```

## Usage

### Basic Methods

```python
# Log at different levels
logger.debug(message, extra=None)
logger.info(message, extra=None)
logger.warning(message, extra=None)
logger.error(message, extra=None)
logger.critical(message, extra=None)

# Get count of pending logs
pending = logger.pending_count()

# Force send all logs
logger.flush()
```

### Initialization Parameters

| Parameter      | Type     | Description                    | Default         |
|----------------|----------|--------------------------------|-----------------|
| `vector_url`   |   str    | Vector server URL              |         -       |
| `project`      |   str    | Project name (required)        |         -       |
| `table`        |   str    | Table name (required)          |         -       |
| `db_path`      |   str    | Path to database file          | `./logs.db`     |
| `batch_size`   |   int    | Batch size for sending         | `1000`          |
| `level`        | LogLevel | Logging level                  | `LogLevel.INFO` |
| `extra_fields` |   dict   | Additional fields for all logs | `{}`            |

## Examples

### Example 1: Logging with Context

```python
from logsend import LogSend

logger = LogSend(
    vector_url="http://localhost:8080",
    project="ecommerce",
    table="events",
)

# Log event with additional information
logger.info(
    "User login successful",
    extra={
        "user_id": 12345,
        "username": "john_doe",
        "ip_address": "192.168.1.1",
        "login_method": "oauth"
    }
)
```

### Example 2: Error Handling

```python
try:
    # Some code
    result = perform_operation()
except Exception as e:
    logger.error(
        "Operation failed",
        extra={
            "error_type": type(e).__name__,
            "error_message": str(e),
            "operation": "perform_operation"
        }
    )
```

## Project Structure

```
logsend/
├── src/logsend/
│   ├── __init__.py           # Main class exports
│   ├── logger.py             # LogSend main class
│   ├── sender.py             # Vector log sender
│   └── disk_queue.py         # SQLite storage management
├── examples/
│   ├── basic_usage.py        # Usage example
│   └── vector.toml           # Vector configuration
├── pyproject.toml            # Project configuration
└── README.md                 # This file
```

## License

MIT License

## Author

Alex

## Links

- [GitHub Repository](https://github.com/ink404dot/logsend)
- [Vector Documentation](https://vector.dev/docs/)
