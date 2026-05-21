"""
Seed script: cria stakeholder Copel + protocolo de teste no MongoDB.
Rode DEPOIS de `docker compose up -d`.

Uso:
  python scripts/seed_copel.py

  Ou com número de protocolo e CNPJ reais:
  PROTOCOL_NUMBER=12345678 CNPJ=12.345.678/0001-99 python scripts/seed_copel.py
"""
import os
import sys
from datetime import datetime, timezone
from pymongo import MongoClient

# -------------------------------------------------------------------
# CONFIGURAÇÃO — ajuste conforme necessário
# -------------------------------------------------------------------

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017/caminhoes_bpk")

# URL de consulta da Copel para protocolos de ligação nova / obra
# Ajuste conforme o portal da Copel que você usa.
# Exemplo: pode ser a URL direta do formulário ou de uma API REST.
# Placeholder: preencha com a URL real antes de rodar.
COPEL_QUERY_URL_TEMPLATE = os.getenv(
    "COPEL_QUERY_URL",
    # URL do portal JSF de acompanhamento de solicitações da Copel
    # O CopelAdapter faz GET + POST para submeter o protocolo
    "https://www.copel.com/slwweb/publico/acompanhamento/inicio.jsf",
)

PROTOCOL_NUMBER = os.getenv("PROTOCOL_NUMBER", "20245757138534")
CNPJ = os.getenv("CNPJ", "00.000.000/0001-00")

# -------------------------------------------------------------------

def seed():
    client = MongoClient(MONGODB_URI)
    db = client.get_default_database()

    # --- Projeto de teste ---
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

    # --- Stakeholder Copel ---
    stakeholder = db["stakeholders"].find_one({"name": "Copel"})
    if not stakeholder:
        result = db["stakeholders"].insert_one({
            "name": "Copel",
            "type": "energy_company",
            "adapter_type": "copel",
            "base_url": "https://www.copel.com",
            "query_url_template": COPEL_QUERY_URL_TEMPLATE,
            "requires_javascript": False,
            "has_captcha": False,
            "active": True,
            "created_at": datetime.now(timezone.utc),
        })
        stakeholder_id = result.inserted_id
        print(f"✅ Stakeholder Copel criado: {stakeholder_id}")
    else:
        stakeholder_id = stakeholder["_id"]
        print(f"ℹ️  Stakeholder Copel já existe: {stakeholder_id}")

    # --- Protocolo de teste ---
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

    # Também cria um job de teste na coleção consultation_jobs
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
    print("Para publicar na fila e rodar via worker:")
    print(f"""
python scripts/publish_job.py --job-id {job_id} --protocol-id {protocol_id} --stakeholder-id {stakeholder_id}
""")

    client.close()


if __name__ == "__main__":
    seed()
