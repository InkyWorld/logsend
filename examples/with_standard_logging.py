"""
Example of using LogSend with Python's standard logging module.
"""

import logging

from logsend import VectorHandler


def main():
    # Create Vector handler with required project and table
    handler = VectorHandler(
        vector_url="http://localhost:8080",
        project="my-project",  # Required!
        table="app_logs",  # Required!
        db_path="./logs/handler_queue.db",
        batch_size=5,
        flush_interval=3.0,
        extra_fields={"environment": "development"},
    )

    # Set formatter
    formatter = logging.Formatter("%(message)s")
    handler.setFormatter(formatter)

    # Create logger
    logger = logging.getLogger("my_app")
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)

    try:
        # Use standard logging API
        logger.debug("Debug message")
        logger.info("Info message with extra", extra={"user_id": 42})
        logger.warning("Warning message")
        logger.error("Error message")

        try:
            raise ValueError("Something went wrong!")
        except ValueError:
            logger.exception("Caught an exception")

        # Log multiple messages
        for i in range(10):
            logger.info(f"Processing step {i}")

    finally:
        # Close handler
        handler.close()


if __name__ == "__main__":
    main()
