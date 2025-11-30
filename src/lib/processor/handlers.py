from abc import ABC, abstractmethod
from pathlib import Path
from typing import List

from .splitters.pdf_splitter import split_pdf
from .splitters.xlsx_splitter import split_xlsx


class BaseHandler(ABC):
    @property
    @abstractmethod
    def format(self) -> str:
        pass

    @abstractmethod
    def split(self, file_bytes: bytes) -> List[bytes]:
        pass


class PDFHandler(BaseHandler):
    @property
    def format(self) -> str:
        return 'pdf'

    def split(self, file_bytes: bytes) -> List[bytes]:
        return split_pdf(file_bytes)


class XLSXHandler(BaseHandler):
    @property
    def format(self) -> str:
        return 'xlsx'

    def split(self, file_bytes: bytes) -> List[bytes]:
        return split_xlsx(file_bytes)


class GenericHandler(BaseHandler):
    def __init__(self, format):
        self._format = format

    @property
    def format(self) -> str:
        return self._format

    def split(self, file_bytes: bytes) -> List[bytes]:
        return [file_bytes]


HANDLER_REGISTRY = {
    '.pdf': PDFHandler,
    '.xlsx': XLSXHandler,
}


def get_handler(file_path: Path) -> BaseHandler:
    suffix = file_path.suffix.lower()
    handler_class = HANDLER_REGISTRY.get(suffix)

    if handler_class is None:
        return GenericHandler(suffix[1:])

    return handler_class()
