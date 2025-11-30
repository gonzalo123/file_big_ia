from abc import ABC


class ProcessingEventListener(ABC):
    """
    Base class for document processing event listeners.
    All methods are optional - override only the events you need to handle.
    """

    async def on_processing_start(self, file_name: str, total_chunks: int):
        """Called when processing of a file starts."""
        pass

    async def on_chunk_start(self, chunk_number: int, file_name: str):
        """Called when processing of a chunk starts."""
        pass

    async def on_chunk_end(self, chunk_number: int, file_name: str, response: str):
        """Called when processing of a chunk ends."""
        pass

    async def on_processing_end(self, file_name: str):
        """Called when processing of a file ends."""
        pass

    async def on_error(self, error: Exception):
        """Called when an error occurs during processing."""
        pass

    async def on_summary_start(self):
        """Called when summary generation starts."""
        pass

    async def on_summary_end(self):
        """Called when summary generation ends."""
        pass
