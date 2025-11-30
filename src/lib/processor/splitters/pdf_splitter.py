import io
import logging
import re
from pathlib import Path
from typing import List

import fitz

logger = logging.getLogger(__name__)


class PDFSplitError(Exception):
    pass


def split_pdf(file_bytes: bytes) -> List[bytes]:
    """
    Splits a binary PDF blob into a list of valid PDF blobs,
    where each one has an approximate size < 4MB.

    The split is done by complete pages, preserving the validity
    of the PDF structure (XREF table, dictionaries, etc.).
    """
    TARGET_LIMIT_BYTES = 4 * 1024 * 1024  # 4 MB hard limit
    # We use a "soft" target to leave room for headers and metadata
    SOFT_TARGET_BYTES = int(TARGET_LIMIT_BYTES * 0.90)

    # 1. Fast-path: If it already fits, return as is
    if len(file_bytes) < TARGET_LIMIT_BYTES:
        return [file_bytes]

    chunks = []

    try:
        # Open from memory without touching disk
        with fitz.open(stream=file_bytes, filetype="pdf") as src_doc:
            total_pages = src_doc.page_count

            if total_pages == 0:
                return []

            current_page = 0

            # Initial estimate: pages that would theoretically fit
            avg_bytes_page = len(file_bytes) / total_pages
            batch_size = max(1, int(SOFT_TARGET_BYTES / avg_bytes_page))

            while current_page < total_pages:
                # Retry loop for fine-tuning the size
                while True:
                    # Define tentative range
                    end_page = min(current_page + batch_size, total_pages)

                    # Create temporary document in memory
                    with fitz.open() as new_doc:
                        new_doc.insert_pdf(src_doc, from_page=current_page, to_page=end_page - 1, annots=False,
                                           links=False)

                        # Save to memory buffer
                        # garbage=4: removes unused resources from the chunk
                        # deflate=True: compresses streams for maximum savings
                        out_buffer = io.BytesIO()
                        new_doc.save(out_buffer, garbage=4, deflate=True)
                        chunk_data = out_buffer.getvalue()

                        current_size = len(chunk_data)

                        # CASE 1: The chunk is valid (below the limit) OR it's a single page (cannot be split further)
                        if current_size <= TARGET_LIMIT_BYTES or batch_size == 1:
                            chunks.append(chunk_data)
                            current_page = end_page

                            # Heuristic: Adjust batch_size for the next loop
                            # If we have a lot of space left, try to take more pages next time
                            if current_size < (SOFT_TARGET_BYTES * 0.5):
                                batch_size = int(batch_size * 1.5)
                            # If we're very tight, maintain or reduce slightly
                            elif current_size > (SOFT_TARGET_BYTES * 0.95):
                                batch_size = max(1, int(batch_size * 0.9))

                            break  # Exit the retry loop and advance pages

                        # CASE 2: The chunk is too large -> Reduce and retry
                        else:
                            # Aggressive reduction factor (0.7) to converge quickly
                            new_batch_size = int(batch_size * 0.7)
                            # Avoid infinite loops if batch_size doesn't change
                            if new_batch_size >= batch_size:
                                new_batch_size = batch_size - 1

                            batch_size = max(1, new_batch_size)
                            # (The 'while True' loop repeats with the new smaller batch_size)

    except Exception as e:
        # In production, log this appropriately
        logger.exception(e)
        # Fallback: return empty list or re-raise according to error policy
        raise PDFSplitError(f"Critical error processing PDF: {e}") from e

    return chunks


def sanitize_filename(name: str) -> str:
    name = name.replace('_', ' ').replace('.', ' ')
    name = re.sub(r'[^a-zA-Z0-9\s\-\(\)\[\]]', '', name)
    name = re.sub(r'\s+', ' ', name)
    return name.strip()


def get_type_from_file_name(file_name):
    return Path(file_name).suffix.lower().lstrip(".")
