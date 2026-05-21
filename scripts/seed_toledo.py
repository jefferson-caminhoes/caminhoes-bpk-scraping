"""
Seed script: cria stakeholder Prefeitura de Toledo (Equiplano) + protocolo de teste.
Rode DEPOIS de `docker compose up -d`.

Uso:
  python scripts/seed_toledo.py

  Ou com protocolo e CNPJ reais:
  PROTOCOL_NUMBER=18047/2025 CNPJ=57.740.735/0001-79 python scripts/seed_toledo.py

Formato do PROTOCOL_NUMBER:
  "18047"       → usa ano atual como exercício
  "18047/2025"  → usa exercício 2025
"""
import os
from datetime import datetime, timezone
from pymongo import MongoClient

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017/caminhoes_bpk")

# URL base da REST API do portal Equiplano de Toledo
TOLEDO_API_BASE = os.getenv(
    "TOLEDO_API_BASE",
    "https://equiplano.toledo.pr.gov.br:7443/portalContribuinteRest",
)

PROTOCOL_NUMBER = os.getenv("PROTOCOL_NUMBER", "18047/2025")
CNPJ = os.getenv("CNPJ", "57.740.735/0001-79")


def seed():
    client = MongoClient(MONGODB_URI)
    db = client.get_default_database()

    # --- Projeto ---
    project = db["projects"].find_one({"name": "Projeto Teste BPK"})
    if not project:
        result = db["projects"].insert_one({
            "name": "Projeto Teste BPK",
            "description": "Projeto de teste para validação do pipeline",
            "active": True,
            "created_at": datetime.now(timezone.utc),
        })
        project_id = result.inserted_id
        print(f"✅ Projeto criado: {project_id}")
    else:
        project_id = project["_id"]
        print(f"ℹ️  Projeto já existe: {project_id}")

    # --- Stakeholder Toledo ---
    stakeholder = db["stakeholders"].find_one({"name": "Prefeitura de Toledo"})
    if not stakeholder:
        result = db["stakeholders"].insert_one({
            "name": "Prefeitura de Toledo",
            "type": "city_hall",
            "adapter_type": "equiplano_toledo",
            "base_url": "https://equiplano.toledo.pr.gov.br:7443",
            "query_url_template": TOLEDO_API_BASE,
            "requires_javascript": False,
            "has_captcha": False,  # captcha presente no front, mas backend não valida
            "active": True,
            "created_at": datetime.now(timezone.utc),
        })
        stakeholder_id = result.inserted_id
        print(f"✅ Stakeholder Toledo criado: {stakeholder_id}")
    else:
        stakeholder_id = stakeholder["_id"]
        print(f"ℹ️  Stakeholder Toledo já existe: {stakeholder_id}")

    # --- Protocolo ---
    protocol = db["protocols"].find_one({
        "protocol_number": PROTOCOL_NUMBER,
        "project_id": str(project_id),
    })
    if not protocol:
        result = db["protocols"].insert_one({
            "protocol_number": PROTOCOL_NUMBER,
            "cnpj": CNPJ,
            "project_id": str(project_id),
            "stakeholder_id": str(stakeholder_id),
            "manual_status": "Em andamento",
            "external_status": None,
            "monitoring_enabled": True,
            "active": True,
            "closed_manually": False,
            "found_in_last_search": None,
            "has_divergence": False,
            "created_at": datetime.now(timezone.utc),
        })
        protocol_id = result.inserted_id
        print(f"✅ Protocolo criado: {protocol_id}")
    else:
        protocol_id = protocol["_id"]
        print(f"ℹ️  Protocolo já existe: {protocol_id}")

    print()
    print("=" * 60)
    print("IDs para teste:")
    print(f"  protocol_id:    {protocol_id}")
    print(f"  stakeholder_id: {stakeholder_id}")
    print()
    print("Para rodar o pipeline manualmente:")
    print(f"""
python scripts/test_pipeline.py \\
  --protocol-id {protocol_id} \\
  --stakeholder-id {stakeholder_id}
""")

    job_id = f"test_job_{int(datetime.now(timezone.utc).timestamp())}"
    db["consultation_jobs"].insert_one({
        "_id": job_id,
        "protocol_id": str(protocol_id),
        "stakeholder_id": str(stakeholder_id),
        "status": "pending",
        "created_at": datetime.now(timezone.utc),
    })
    print(f"✅ Job de teste criado: {job_id}")
    print()
    print("Para publicar na fila:")
    print(f"""
python scripts/publish_job.py --job-id {job_id} --protocol-id {protocol_id} --stakeholder-id {stakeholder_id}
""")

    client.close()


if __name__ == "__main__":
    seed()
