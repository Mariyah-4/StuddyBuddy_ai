from services.syllabus_service import extract_text
from pathlib import Path

def test_txt_extraction(tmp_path):
    file = tmp_path / "sample.txt"
    file.write_text("Unit 1: Probability", encoding="utf-8")
    assert extract_text(file) == "Unit 1: Probability"
