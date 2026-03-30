"""Document tools for reading PDFs, text files, and writing output."""

import os

from strands import tool


@tool
def read_pdf_tool(file_path: str) -> str:
    """Read a PDF file and return its text content."""
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
    """Read a text file and return its contents."""
    if not os.path.exists(file_path):
        return f"Error: File not found: {file_path}"

    with open(file_path) as f:
        return f.read()


@tool
def write_file_tool(file_path: str, content: str) -> str:
    """Write content to a file."""
    os.makedirs(os.path.dirname(file_path) or ".", exist_ok=True)
    with open(file_path, "w") as f:
        f.write(content)
    return f"Written to {file_path} ({len(content)} chars)"
