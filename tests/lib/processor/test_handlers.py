import pytest
from pathlib import Path

from lib.processor.handlers import (
    get_handler,
    PDFHandler,
    XLSXHandler,
    GenericHandler,
)


def test_get_handler_pdf():
    """Test que get_handler retorna PDFHandler para archivos .pdf"""
    handler = get_handler(Path("test.pdf"))
    assert isinstance(handler, PDFHandler)
    assert handler.format == "pdf"


def test_get_handler_xlsx():
    """Test que get_handler retorna XLSXHandler para archivos .xlsx"""
    handler = get_handler(Path("test.xlsx"))
    assert isinstance(handler, XLSXHandler)
    assert handler.format == "xlsx"


def test_get_handler_xls():
    """Test que get_handler retorna GenericHandler para archivos .xls"""
    handler = get_handler(Path("test.xls"))
    assert isinstance(handler, GenericHandler)
    assert handler.format == "xls"


def test_get_handler_unsupported_returns_generic():
    """Test que get_handler retorna GenericHandler para archivos no soportados"""
    unsupported_files = [
        ("document.txt", "txt"),
        ("image.jpg", "jpg"),
        ("data.json", "json"),
        ("script.py", "py"),
        ("archive.zip", "zip"),
    ]
    
    for filename, expected_format in unsupported_files:
        handler = get_handler(Path(filename))
        assert isinstance(handler, GenericHandler), f"Failed for {filename}"
        assert handler.format == expected_format, f"Format mismatch for {filename}"


def test_get_handler_case_insensitive():
    """Test que get_handler funciona con extensiones en mayúsculas"""
    handler_upper = get_handler(Path("test.PDF"))
    handler_lower = get_handler(Path("test.pdf"))
    
    assert type(handler_upper) == type(handler_lower)
    assert isinstance(handler_upper, PDFHandler)


def test_generic_handler_no_split():
    """Test que GenericHandler no divide el archivo en chunks"""
    handler = GenericHandler("txt")
    test_bytes = b"Test content that should not be split"
    
    result = handler.split(test_bytes)
    
    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0] == test_bytes
