"""
Testa o pipeline completo de forma síncrona (sem RabbitMQ).
Útil para validar que scraping + cleaner + IA funcionam.

Uso:
  python scripts/test_pipeline.py --protocol-id <ID> --stakeholder-id <ID>

  Ou teste com URL direta:
  python scripts/test_pipeline.py --url "https://exemplo.com/consulta?prot=12345"
"""
import argparse
import json
import sys
import os

# Adiciona a raiz do projeto ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.scraping.http_scraper import scrape_url
from src.cleaner.html_cleaner import clean_html
from src.cleaner.sufficiency_checker import is_sufficient
from src.shared.logger import get_logger

logger = get_logger("test_pipeline")


def separator(title: str):
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print('=' * 60)


def test_with_scrape_result(scrape_result, protocol_number: str = "TESTE", cnpj: str = None):
    """Continua o pipeline a partir de um ScrapeResult já obtido."""
    if not scrape_result.success:
        print(f"❌ Scraping falhou: {scrape_result.error_type} — {scrape_result.error_message}")
        return False

    print(f"✅ HTTP {scrape_result.http_status} — {len(scrape_result.raw_html)} chars de HTML")
    print(f"\nPrimeiros 500 chars do HTML:")
    print(scrape_result.raw_html[:500])

    separator("PASSO 2: LIMPEZA HTML")
    clean_text = clean_html(scrape_result.raw_html)
    print(f"Texto limpo ({len(clean_text)} chars):")
    print(clean_text[:1000])

    separator("PASSO 3: VERIFICAÇÃO DE SUFICIÊNCIA")
    sufficient = is_sufficient(clean_text)
    if sufficient:
        print("✅ Texto é suficiente para extração pela IA")
    else:
        print("⚠️  Texto pode ser insuficiente — tentando extração mesmo assim")

    separator("PASSO 4: EXTRAÇÃO IA (OLLAMA)")
    try:
        from src.ai.prompts import build_extraction_prompt
        from src.ai.ollama_client import call_ollama
        from src.ai.json_validator import extract_json_from_text, validate_extraction_result

        prompt = build_extraction_prompt(
            clean_text=clean_text,
            protocol_number=protocol_number,
            cnpj=cnpj,
            stakeholder_name="Copel",
        )
        print(f"Enviando para Ollama ({os.getenv('OLLAMA_MODEL', 'phi3:mini')})...")
        raw = call_ollama(prompt)
        print(f"\nResposta bruta da IA:")
        print(raw[:500])

        separator("PASSO 5: VALIDAÇÃO DO JSON")
        data = extract_json_from_text(raw)
        result_obj = validate_extraction_result(data)
        print("✅ JSON válido extraído:")
        print(json.dumps(result_obj.model_dump(), indent=2, ensure_ascii=False))
        return True

    except Exception as e:
        print(f"❌ Erro na extração IA: {e}")
        print("(Certifique-se que o Ollama está rodando e o modelo foi baixado)")
        return False


def test_with_url(url: str, protocol_number: str = "TESTE", cnpj: str = None):
    """Testa o pipeline completo a partir de uma URL (GET direto)."""
    separator("PASSO 1: SCRAPING")
    print(f"URL: {url}")
    result = scrape_url(url)
    return test_with_scrape_result(result, protocol_number, cnpj)


def test_with_db(protocol_id: str, stakeholder_id: str):
    """Testa usando dados reais do MongoDB."""
    from pymongo import MongoClient
    from src.scraping.fetcher import fetch_scraping_target

    separator("BUSCANDO DADOS NO MONGODB")
    client = MongoClient(os.getenv("MONGODB_URI", "mongodb://localhost:27017/caminhoes_bpk"))
    db = client.get_default_database()

    try:
        from bson import ObjectId
        try:
            pid = ObjectId(protocol_id)
            sid = ObjectId(stakeholder_id)
        except Exception:
            pid = protocol_id
            sid = stakeholder_id

        target = fetch_scraping_target(db, pid, sid, job_id="test_manual")
        print(f"✅ Protocolo: {target.protocol_number}")
        print(f"   CNPJ: {target.cnpj}")
        print(f"   Stakeholder: {target.stakeholder_name}")
        print(f"   Adapter: {target.adapter_type}")
        print(f"   URL resolvida: {target.resolved_url}")

        from src.scraping.adapters.registry import get_adapter
        from src.scraping.http_scraper import scrape_url as _scrape_url

        adapter = get_adapter(target.adapter_type)
        scrape_result = adapter.scrape(target) or _scrape_url(target.resolved_url)

        return test_with_scrape_result(
            scrape_result=scrape_result,
            protocol_number=target.protocol_number,
            cnpj=target.cnpj,
        )
    finally:
        client.close()


def main():
    parser = argparse.ArgumentParser(description="Testa o pipeline scraping → cleaner → IA")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--url", help="URL direta para testar")
    group.add_argument("--protocol-id", help="ID do protocolo no MongoDB")
    parser.add_argument("--stakeholder-id", help="ID do stakeholder (obrigatório com --protocol-id)")
    parser.add_argument("--protocol-number", default="TESTE", help="Número do protocolo (com --url)")
    parser.add_argument("--cnpj", default=None, help="CNPJ (com --url)")
    args = parser.parse_args()

    if args.url:
        success = test_with_url(args.url, args.protocol_number, args.cnpj)
    else:
        if not args.stakeholder_id:
            parser.error("--stakeholder-id é obrigatório com --protocol-id")
        success = test_with_db(args.protocol_id, args.stakeholder_id)

    separator("RESULTADO FINAL")
    if success:
        print("✅ Pipeline funcionando!")
    else:
        print("❌ Pipeline com problemas — veja os logs acima")
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    # Carrega .env se existir
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    main()
