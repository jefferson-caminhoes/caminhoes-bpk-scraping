import sys
from src.shared.logger import get_logger

logger = get_logger("main")

WORKERS = {
    "scraping": "src.scraping.worker",
    "ai": "src.ai.worker",
    "scheduler": "src.scheduler.scheduler",
    "probe": "src.workers.probe_worker",
}


def main():
    if len(sys.argv) < 2:
        print(f"Usage: python -m src.main <worker>")
        print(f"Available workers: {', '.join(WORKERS.keys())}")
        sys.exit(1)

    worker_name = sys.argv[1]
    if worker_name not in WORKERS:
        print(f"Unknown worker: {worker_name}. Available: {', '.join(WORKERS.keys())}")
        sys.exit(1)

    import importlib
    module = importlib.import_module(WORKERS[worker_name])
    logger.info(f"Starting worker: {worker_name}")
    module.run()


if __name__ == "__main__":
    main()
