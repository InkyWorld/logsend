"""
Basic usage example for LogSend.
"""

from logsend import LogSend, LogLevel


def main():
    # Create logger with required project and table
    logger = LogSend(
        vector_url="http://localhost:8080",
        project="my-project",          # Required!
        table="application_logs",       # Required!
        db_path="./logs/queue.db",
        batch_size=10,                  # Send after 10 logs
        flush_interval=5.0,             # Or every 5 seconds
        level=LogLevel.DEBUG,
        extra_fields={
            "environment": "development",
            "version": "1.0.0"
        }
    )
    
    try:
        # Log some messages
        logger.debug("Application starting...")
        logger.info("Configuration loaded", extra={"config_file": "config.yaml"})
        logger.info("User logged in", extra={"user_id": 123, "username": "john"})
        logger.warning("High memory usage detected", extra={"memory_percent": 85})
        logger.error("Failed to connect to external service", extra={
            "service": "payment-api",
            "error_code": "CONNECTION_TIMEOUT"
        })
        
        # Simulate some work
        for i in range(15):
            logger.info(f"Processing item {i}", extra={"item_id": i})
        
        # Check pending logs
        print(f"Pending logs: {logger.pending_count()}")
        
        # Force flush remaining logs
        logger.flush()
        
    finally:
        # Always close the logger
        logger.close()


if __name__ == "__main__":
    main()
