"""
Publica um job de scraping manualmente na fila scraping.jobs.
Útil para testar o worker sem o scheduler.

Uso:
  python scripts/publish_job.py --job-id test_job_1 --protocol-id <ID> --stakeholder-id <ID>
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from src.queues.publisher import publish_message
from src.shared.logger import get_logger

logger = get_logger("publish_job")


def main():
    parser = argparse.ArgumentParser(description="Publica job na fila scraping.jobs")
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--protocol-id", required=True)
    parser.add_argument("--stakeholder-id", required=True)
    args = parser.parse_args()

    payload = {
        "job_id": args.job_id,
        "protocol_id": args.protocol_id,
        "stakeholder_id": args.stakeholder_id,
    }

    publish_message("scraping.jobs", payload)
    print(f"✅ Job publicado em scraping.jobs: {payload}")
    print()
    print("Agora rode o worker para processar:")
    print("  python -m src.main scraping")


if __name__ == "__main__":
    main()
