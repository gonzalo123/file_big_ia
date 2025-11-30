import asyncio
import logging

from lib.processor import DocumentProcessor
from lib.processor import ProcessingEventListener
from lib.processor.processor import DocumentFile
from settings import BASE_DIR, Models
from tools.main import get_agent

logging.basicConfig(
    format='%(asctime)s [%(levelname)s] %(message)s',
    level='INFO',
    datefmt='%d/%m/%Y %X')

logger = logging.getLogger(__name__)

MAX_CONCURRENT_WORKERS = 5
MODEL = Models.CLAUDE_45


class DocumentProcessorEventListener(ProcessingEventListener):
    async def on_processing_start(self, file_name: str, total_chunks: int):
        if total_chunks > 1:
            logger.info(f"Starting async processing of {total_chunks} chunks for file {file_name}")
        else:
            logger.info(f"Starting processing for file {file_name}")

    async def on_chunk_start(self, chunk_number: int, file_name: str):
        logger.info(f"[Worker {chunk_number}] Processing chunk for file {file_name}")

    async def on_chunk_end(self, chunk_number: int, file_name: str, response: str):
        logger.info(f"[Worker {chunk_number}] Completed chunk for file {file_name}")

    async def on_processing_end(self, file_name: str):
        logger.info(f"File {file_name} successfully processed")

    async def on_error(self, error: Exception):
        logger.error(f"An error occurred: {error}")

    async def on_summary_start(self):
        logger.info("Starting summary generation")

    async def on_summary_end(self):
        logger.info("Summary generation completed")


async def main():
    question = "Summarize this."
    agent = get_agent(
        system_prompt="You are a helpful assistant that helps summarize long documents.",
        model=Models.CLAUDE_45
    )

    processor = DocumentProcessor(agent=agent)
    processor.add_listener(DocumentProcessorEventListener())

    async for chunk in processor.process([
        DocumentFile(path=BASE_DIR / "docs" / "progit.pdf", name="progit.pdf"),
    ], question):
        print(chunk, end="", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
