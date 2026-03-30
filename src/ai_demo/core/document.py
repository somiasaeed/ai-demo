"""Strands-compatible file I/O tools for agent use."""

import os

from strands import tool


@tool
def read_pdf_tool(file_path: str) -> str:
    """Read a PDF file and return its text content.

    Args:
        file_path: Path to the PDF file.

    Returns:
        Extracted text from all pages.
    """
    import pymupdf

    if not os.path.exists(file_path):
        return f"Error: File not found: {file_path}"

    doc = pymupdf.open(file_path)
    pages = []
    for page in doc:
        pages.append(page.get_text())
    doc.close()
    return "\n\n".join(pages)


@tool
def read_file_tool(file_path: str) -> str:
    """Read a plain text file and return its content.

    Args:
        file_path: Path to the text file.

    Returns:
        File content as a string.
    """
    if not os.path.exists(file_path):
        return f"Error: File not found: {file_path}"

    with open(file_path, encoding="utf-8") as f:
        return f.read()


@tool
def write_file_tool(file_path: str, content: str) -> str:
    """Write content to a file, creating parent directories if needed.

    Args:
        file_path: Path to the output file.
        content: Text content to write.

    Returns:
        Confirmation message with character count.
    """
    os.makedirs(os.path.dirname(file_path) or ".", exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    return f"Written {len(content)} chars to {file_path}"
