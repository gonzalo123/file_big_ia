import asyncio
import logging
from pathlib import Path
from typing import List, AsyncIterator

from pydantic import BaseModel, Field, ConfigDict
from strands import Agent
from strands.handlers import PrintingCallbackHandler

from settings import Models, BYTES_THRESHOLD, MAX_CONTEXT_CHARS
from tools.main import get_agent
from .events import ProcessingEventListener
from .handlers import get_handler
from .prompts import SYSTEM_CHUNK_PROMPT, SYSTEM_PROMPT
from .splitters.pdf_splitter import sanitize_filename

logger = logging.getLogger(__name__)




class DocumentFile(BaseModel):
    path: Path
    name: str = Field(..., description="Real file name")

    model_config = ConfigDict(arbitrary_types_allowed=True)


class DocumentProcessor:
    """
    Handles the processing of documents using AI agents.
    It supports splitting large files into chunks and processing them in parallel (Map-Reduce pattern).
    """
    def __init__(
            self,
            agent: Agent,
            model: str = Models.CLAUDE_45,
            max_workers: int = 5,
    ):
        self.agent = agent
        self.model = model
        self.max_workers = max_workers
        self.listeners: List[ProcessingEventListener] = []

    def add_listener(self, listener: ProcessingEventListener):
        self.listeners.append(listener)

    async def _notify_processing_start(self, file_name: str, total_chunks: int):
        for listener in self.listeners:
            await listener.on_processing_start(file_name, total_chunks)

    async def _notify_chunk_start(self, chunk_number: int, file_name: str):
        for listener in self.listeners:
            await listener.on_chunk_start(chunk_number, file_name)

    async def _notify_chunk_end(self, chunk_number: int, file_name: str, response: str):
        for listener in self.listeners:
            await listener.on_chunk_end(chunk_number, file_name, response)

    async def _notify_processing_end(self, file_name: str):
        for listener in self.listeners:
            await listener.on_processing_end(file_name)

    async def _notify_error(self, error: Exception):
        for listener in self.listeners:
            await listener.on_error(error)

    async def _notify_summary_start(self):
        for listener in self.listeners:
            await listener.on_summary_start()

    async def _notify_summary_end(self):
        for listener in self.listeners:
            await listener.on_summary_end()

    def _create_agent(self, system_prompt: str, with_callback: bool = False):
        return get_agent(
            system_prompt=system_prompt,
            model=self.model,
            tools=[],
            callback_handler=PrintingCallbackHandler() if with_callback else None
        )

    def _create_document_message(self, file_format: str, file_name: str, file_bytes: bytes, text: str) -> list:
        return [
            {
                "role": "user",
                "content": [
                    {
                        "document": {
                            "format": file_format,
                            "name": file_name,
                            "source": {"bytes": file_bytes},
                        },
                    },
                    {"text": text},
                ],
            },
        ]

    async def _process_chunk(
            self, chunk: bytes,
            chunk_number: int, file_name: str,
            question: str,
            file_format: str,
            semaphore: asyncio.Semaphore
    ) -> tuple[int, str]:
        async with semaphore:
            await self._notify_chunk_start(chunk_number, file_name)

            try:
                agent = self._create_agent(SYSTEM_CHUNK_PROMPT)
                name = f"{file_name}_{chunk_number}"
                text = f"Este es un fragmento del archivo. La pregunta del usuario es: ```{question}```."
                messages = self._create_document_message(file_format, name, chunk, text)

                response = await agent.invoke_async(messages)
                await self._notify_chunk_end(chunk_number, file_name, str(response))
                return (chunk_number, str(response))
            except Exception as e:
                await self._notify_error(e)
                raise e

    def _consolidate_and_truncate(self, responses: list[str], num_chunks: int) -> str:
        consolidated = "\n\n".join(responses)
        logger.info(f"Consolidated context size: {len(consolidated)} characters")
        logger.info(f"Number of chunks: {num_chunks}")

        if len(consolidated) > MAX_CONTEXT_CHARS:
            logger.warning(
                f"Consolidated context is too large ({len(consolidated)} chars). "
                f"Truncating to {MAX_CONTEXT_CHARS} chars."
            )
            return consolidated[:MAX_CONTEXT_CHARS] + "\n... [TRUNCATED]"
        return consolidated

    async def _process_file(self, file: DocumentFile, question: str, with_callback=True):
        """
        Decides whether to process the file as a whole or split it based on size.
        """
        file_bytes = Path(file.path).read_bytes()
        processor = self._process_big if len(file_bytes) > BYTES_THRESHOLD else self._process
        async for chunk in processor(file_bytes, file, question, with_callback):  # type: ignore
            yield chunk

    async def _collect_file_content(self, file: DocumentFile, question: str) -> str:
        """Collect all content from a single file processing."""
        data = []
        async for chunk in self._process_file(file, question, with_callback=False):
            data.append(chunk)
        return "".join(data)

    async def process(self, files: List[DocumentFile], question: str) -> AsyncIterator[str]:
        """
        Main entry point for processing one or multiple files.
        """
        if len(files) == 1:
            async for chunk in self._process_file(files[0], question, with_callback=False):
                yield chunk
        else:
            # Process all files in parallel
            tasks = [
                self._collect_file_content(file, question)
                for file in files
            ]

            results = await asyncio.gather(*tasks)

            # Build content for final summary
            content = [{'text': result} for result in results]

            messages = [{"role": "user", "content": content}]
            await self._notify_summary_start()
            async for event in self.agent.stream_async(messages):  # type: ignore
                if "data" in event:
                    yield str(event["data"])
                elif "message" in event:
                    yield "\n"
            await self._notify_summary_end()

    async def _process(self, file_bytes: bytes, file: DocumentFile, question: str, with_callback=True) -> AsyncIterator[
        str]:
        file_path = file.path
        handler = get_handler(file_path)
        file_name = sanitize_filename(file.name)

        await self._notify_processing_start(file_name, 1)

        try:
            agent = self._create_agent(SYSTEM_PROMPT, with_callback=with_callback)
            text = f"La pregunta del usuario es: ```{question}```."
            messages = self._create_document_message(handler.format, file_name, file_bytes, text)

            async for event in agent.stream_async(messages):  # type: ignore
                if "data" in event:
                    yield str(event["data"])
                elif "message" in event:
                    yield "\n"

            await self._notify_processing_end(file_name)
        except Exception as e:
            await self._notify_error(e)
            raise e

    async def _process_big(self, file_bytes: bytes, file: DocumentFile, question: str, with_callback=True) -> \
    AsyncIterator[str]:
        file_path = file.path
        handler = get_handler(file_path)
        chunks = handler.split(file_bytes)
        file_name = sanitize_filename(file.name)

        await self._notify_processing_start(file_name, len(chunks))

        semaphore = asyncio.Semaphore(self.max_workers)

        tasks = [
            self._process_chunk(chunk, i, file_name, question, handler.format, semaphore)
            for i, chunk in enumerate(chunks, 1)
        ]

        results = await asyncio.gather(*tasks)
        results.sort(key=lambda x: x[0])
        responses_from_chunks = [response for _, response in results]

        await self._notify_processing_end(file_name)

        agent = self._create_agent(SYSTEM_PROMPT, with_callback=with_callback)

        consolidated_context = self._consolidate_and_truncate(responses_from_chunks, len(chunks))

        final_payload = [
            {
                "role": "user",
                "content": [
                    {
                        "text": f"""
            STATUS: {len(chunks)} fragments of the original file have been analyzed.
            Below are the partial analyses extracted from each fragment:

            {consolidated_context}

            ---------------------------------------------------------------------
            FINAL INSTRUCTION:
            Based EXCLUSIVELY on the consolidated information above, respond to the following user request.
            If information is repeated across multiple fragments, unify it.
            If there are contradictions, point out the discrepancy.

            USER REQUEST:
            "{question}"
            """
                    }
                ]
            }
        ]

        async for event in agent.stream_async(final_payload):  # type: ignore
            if "data" in event:
                yield str(event["data"])
            elif "message" in event:
                yield "\n"
