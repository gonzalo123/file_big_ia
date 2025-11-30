import pytest
from unittest.mock import AsyncMock, MagicMock, patch, ANY
from pathlib import Path
import asyncio

from lib.processor.processor import DocumentProcessor, DocumentFile, BYTES_THRESHOLD
from lib.processor.events import ProcessingEventListener

# Mock data
MOCK_FILE_CONTENT = b"fake content"
MOCK_LARGE_FILE_CONTENT = b"fake content" * (BYTES_THRESHOLD // len(b"fake content") + 10)

@pytest.fixture
def mock_agent():
    agent = MagicMock()
    agent.stream_async = MagicMock()
    agent.invoke_async = AsyncMock()
    return agent

@pytest.fixture
def processor(mock_agent):
    return DocumentProcessor(agent=mock_agent)

@pytest.fixture
def mock_listener():
    listener = MagicMock(spec=ProcessingEventListener)
    listener.on_processing_start = AsyncMock()
    listener.on_chunk_start = AsyncMock()
    listener.on_chunk_end = AsyncMock()
    listener.on_processing_end = AsyncMock()
    listener.on_error = AsyncMock()
    listener.on_summary_start = AsyncMock()
    listener.on_summary_end = AsyncMock()
    return listener

@pytest.mark.asyncio
async def test_initialization(processor, mock_agent):
    assert processor.agent == mock_agent
    assert processor.listeners == []

@pytest.mark.asyncio
async def test_add_listener(processor, mock_listener):
    processor.add_listener(mock_listener)
    assert mock_listener in processor.listeners

@pytest.mark.asyncio
async def test_notify_processing_start(processor, mock_listener):
    processor.add_listener(mock_listener)
    await processor._notify_processing_start("test.txt", 5)
    mock_listener.on_processing_start.assert_called_once_with("test.txt", 5)

@pytest.mark.asyncio
async def test_process_small_file(processor, mock_agent, mock_listener):
    processor.add_listener(mock_listener)
    
    file = DocumentFile(path=Path("test.txt"), name="test.txt")
    question = "What is this?"
    
    # Mock handlers and file reading
    with patch("lib.processor.processor.get_handler") as mock_get_handler, \
         patch("pathlib.Path.read_bytes", return_value=MOCK_FILE_CONTENT), \
         patch.object(processor, '_create_agent', return_value=mock_agent):
        
        mock_handler = MagicMock()
        mock_handler.format = "txt"
        mock_get_handler.return_value = mock_handler
        
        # Mock agent stream response
        async def async_gen():
            yield {"data": "response chunk"}
        mock_agent.stream_async.return_value = async_gen()
        
        # Run process
        results = []
        async for chunk in processor._process(MOCK_FILE_CONTENT, file, question):
            results.append(chunk)
            
        assert results == ["response chunk"]
        mock_listener.on_processing_start.assert_called_once()
        mock_listener.on_processing_end.assert_called_once()

@pytest.mark.asyncio
async def test_process_big_file(processor, mock_agent, mock_listener):
    processor.add_listener(mock_listener)
    
    file = DocumentFile(path=Path("large.txt"), name="large.txt")
    question = "Summary please"
    
    # Mock handlers and file reading
    with patch("lib.processor.processor.get_handler") as mock_get_handler:
        
        mock_handler = MagicMock()
        mock_handler.format = "txt"
        # Split into 2 chunks
        mock_handler.split.return_value = [b"chunk1", b"chunk2"]
        mock_get_handler.return_value = mock_handler
        
        # Mock agent responses
        # invoke_async for chunks
        mock_agent.invoke_async.side_effect = ["analysis 1", "analysis 2"]
        
        # stream_async for final summary
        # We need to mock _create_agent to return our mock_agent because _process_big creates new agents
        with patch.object(processor, '_create_agent', return_value=mock_agent):
             async def async_gen():
                 yield {"data": "final summary"}
             mock_agent.stream_async.return_value = async_gen()

             results = []
             async for chunk in processor._process_big(MOCK_LARGE_FILE_CONTENT, file, question):
                 results.append(chunk)

             assert results == ["final summary"]
             
             # Verify chunk processing
             assert mock_agent.invoke_async.call_count == 2
             mock_listener.on_chunk_start.assert_called()
             mock_listener.on_chunk_end.assert_called()
             mock_listener.on_processing_end.assert_called()

@pytest.mark.asyncio
async def test_process_delegation(processor):
    file = DocumentFile(path=Path("test.txt"), name="test.txt")
    question = "Q"
    
    with patch.object(processor, '_process') as mock_process, \
         patch.object(processor, '_process_big') as mock_process_big, \
         patch("pathlib.Path.read_bytes") as mock_read_bytes:
        
        # Case 1: Small file
        mock_read_bytes.return_value = b"small"
        # We need to mock the async generator behavior
        async def async_gen(*args, **kwargs):
            yield "result"
            
        mock_process.return_value = async_gen()
        
        async for _ in processor._process_file(file, question):
            pass
            
        mock_process.assert_called_once()
        mock_process_big.assert_not_called()
        
        # Reset
        mock_process.reset_mock()
        mock_read_bytes.reset_mock()
        
        # Case 2: Large file
        mock_read_bytes.return_value = b"a" * (BYTES_THRESHOLD + 1)
        mock_process_big.return_value = async_gen()
        
        async for _ in processor._process_file(file, question):
            pass
            
        mock_process_big.assert_called_once()
        mock_process.assert_not_called()

@pytest.mark.asyncio
async def test_process_multiple_files(processor, mock_agent):
    files = [
        DocumentFile(path=Path("f1.txt"), name="f1.txt"),
        DocumentFile(path=Path("f2.txt"), name="f2.txt")
    ]
    question = "Compare"
    
    # Define async generator function
    async def mock_file_gen(file, q, **kwargs):
        yield f"content of {file.name}"

    with patch.object(processor, '_process_file', side_effect=mock_file_gen) as mock_process_file:
        
        # Mock final summary stream
        async def async_gen(*args, **kwargs):
            yield {"data": "comparison"}
        mock_agent.stream_async.side_effect = async_gen
        
        results = []
        async for chunk in processor.process(files, question):
            results.append(chunk)
            
        assert "comparison" in results
        assert mock_process_file.call_count == 2
