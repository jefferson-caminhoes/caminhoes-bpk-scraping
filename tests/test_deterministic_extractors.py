from src.ai.deterministic_extractors import try_extract_deterministic


def test_extracts_copel_orders_without_ollama():
    clean_text = """
Protocolo: 20245757138534
Stakeholder: Copel

Ordens do protocolo:
  Sequencia: 1
  Descricao: APROVAÇÃO DO ORÇAMENTO PELO CLIENTE
  Status: Concluída
  Observacao: Essa ordem de serviço está concluída.

  Sequencia: 2
  Descricao: OBRAS NA REDE
  Status: Concluída
  Observacao: Essa ordem de serviço está concluída.
"""

    result = try_extract_deterministic(
        stakeholder={"name": "copel"},
        clean_text=clean_text,
        protocol_number="20245757138534",
        cnpj="57740735000179",
    )

    assert result is not None
    assert result["found"] is True
    assert result["protocol_number"] == "20245757138534"
    assert result["cnpj"] == "57740735000179"
    assert result["external_status"] == "Concluída"
    assert result["confidence"] == 0.95
    assert result["orders"] == [
        {
            "sequence": 1,
            "description": "APROVAÇÃO DO ORÇAMENTO PELO CLIENTE",
            "status": "Concluída",
            "observation": "Essa ordem de serviço está concluída.",
        },
        {
            "sequence": 2,
            "description": "OBRAS NA REDE",
            "status": "Concluída",
            "observation": "Essa ordem de serviço está concluída.",
        },
    ]


def test_does_not_extract_unknown_stakeholder_text():
    result = try_extract_deterministic(
        stakeholder={"name": "Prefeitura"},
        clean_text="Protocolo 123 em andamento",
        protocol_number="123",
        cnpj=None,
    )

    assert result is None
