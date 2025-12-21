"""
Example of using LogSend as a context manager.
"""

from logsend import LogSend


def main():
    # Using context manager ensures proper cleanup
    with LogSend(
        vector_url="http://localhost:8080",
        project="my-project",  # Required!
        table="events",  # Required!
        db_path="./logs/queue.db",
        batch_size=50,
        flush_interval=2.0,
        extra_fields={"environment": "production"},
    ) as logger:
        logger.info("Application started")

        # Simulate some work
        for i in range(20):
            if i % 5 == 0:
                logger.debug(f"Checkpoint {i}")
            logger.info(f"Processing item {i}", extra={"item_id": i})

        logger.info("Application finished successfully")

    # Logger is automatically closed here
    print("Done! Logs have been sent and saved.")


if __name__ == "__main__":
    main()
