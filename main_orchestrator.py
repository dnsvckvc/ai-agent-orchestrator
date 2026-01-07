"""
Main entry point for Orchestrator service
"""

import asyncio
import os
import signal
import logging
from concurrent import futures
from http.server import HTTPServer, BaseHTTPRequestHandler

import grpc

from core.orchestrator import Orchestrator, TaskDefinition
from core.execution_engine import ExecutionMode
from monitoring.metrics import MetricsCollector

# Configure logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MetricsHandler(BaseHTTPRequestHandler):
    """HTTP handler for Prometheus metrics"""

    def do_GET(self):
        if self.path == "/metrics":
            metrics_text = orchestrator.metrics.export_prometheus_format()

            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(metrics_text.encode('utf-8'))

        elif self.path == "/health":
            health = {
                "healthy": True,
                "stats": orchestrator.get_stats()
            }

            import json
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(health).encode('utf-8'))

        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        """Suppress default logging"""
        pass


# Global orchestrator instance
orchestrator = None


async def main():
    """Main orchestrator service"""
    global orchestrator

    # Configuration from environment
    redis_host = os.getenv("REDIS_HOST", "localhost")
    redis_port = int(os.getenv("REDIS_PORT", "6379"))
    grpc_port = int(os.getenv("GRPC_PORT", "50051"))
    metrics_port = int(os.getenv("METRICS_PORT", "8000"))
    max_workers = int(os.getenv("MAX_WORKERS", "100"))

    logger.info(f"Starting Orchestrator service...")
    logger.info(f"Redis: {redis_host}:{redis_port}")
    logger.info(f"gRPC Port: {grpc_port}")
    logger.info(f"Metrics Port: {metrics_port}")

    # Create orchestrator
    orchestrator = Orchestrator(
        redis_host=redis_host,
        redis_port=redis_port,
        max_workers=max_workers
    )

    # Start orchestrator
    await orchestrator.start()

    # Start metrics server in separate thread
    import threading
    metrics_server = HTTPServer(("0.0.0.0", metrics_port), MetricsHandler)
    metrics_thread = threading.Thread(target=metrics_server.serve_forever, daemon=True)
    metrics_thread.start()
    logger.info(f"Metrics server started on port {metrics_port}")

    # TODO: Start gRPC server
    # For now, we'll just keep the orchestrator running

    logger.info("Orchestrator service is running...")

    # Wait for shutdown signal
    shutdown_event = asyncio.Event()

    def signal_handler(sig, frame):
        logger.info(f"Received signal {sig}, shutting down...")
        shutdown_event.set()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    await shutdown_event.wait()

    # Shutdown
    logger.info("Shutting down orchestrator...")
    await orchestrator.stop()
    metrics_server.shutdown()

    logger.info("Orchestrator service stopped")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Orchestrator interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
