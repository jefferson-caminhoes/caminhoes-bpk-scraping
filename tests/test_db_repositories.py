from unittest.mock import MagicMock
from bson import ObjectId
from src.database.repositories.scraped_contents import ScrapedContentsRepository
from src.database.repositories.consultation_jobs import ConsultationJobsRepository


def test_save_raw_content_returns_inserted_id():
    mock_col = MagicMock()
    inserted_id = ObjectId()
    mock_col.insert_one.return_value = MagicMock(inserted_id=inserted_id)
    repo = ScrapedContentsRepository(mock_col)

    result = repo.save_raw_content(
        job_id="job_123",
        protocol_id="prot_123",
        stakeholder_id="stake_123",
        raw_html="<html><body>Protocolo 99</body></html>",
        http_status=200,
        request_url="https://example.com/consulta?prot=99",
    )

    assert result == str(inserted_id)
    mock_col.insert_one.assert_called_once()
    doc = mock_col.insert_one.call_args[0][0]
    assert doc["job_id"] == "job_123"
    assert doc["raw_html"] == "<html><body>Protocolo 99</body></html>"
    assert doc["http_status"] == 200
    assert doc["error"] is None


def test_get_by_id_returns_document():
    mock_col = MagicMock()
    mock_col.find_one.return_value = {"_id": "abc", "clean_text": "texto limpo"}
    repo = ScrapedContentsRepository(mock_col)

    doc = repo.get_by_id("abc")

    assert doc["clean_text"] == "texto limpo"
    mock_col.find_one.assert_called_once_with({"_id": "abc"})


def test_update_clean_text():
    mock_col = MagicMock()
    repo = ScrapedContentsRepository(mock_col)

    repo.update_clean_text("content_123", "Texto limpo aqui", "generic_html_text_extractor")

    mock_col.update_one.assert_called_once()
    args = mock_col.update_one.call_args
    assert args[0][0] == {"_id": "content_123"}
    update_doc = args[0][1]["$set"]
    assert update_doc["clean_text"] == "Texto limpo aqui"
    assert update_doc["cleaning_strategy"] == "generic_html_text_extractor"


def test_update_job_status():
    mock_col = MagicMock()
    repo = ConsultationJobsRepository(mock_col)

    repo.update_status("job_123", "scraping_running")

    mock_col.update_one.assert_called_once()
    args = mock_col.update_one.call_args[0]
    assert args[0] == {"_id": "job_123"}
    assert args[1]["$set"]["status"] == "scraping_running"
