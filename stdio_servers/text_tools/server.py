"""Text utility MCP server for Axiolex stdio discovery.

Run with:
    python stdio_servers/text_tools/server.py

Register in mcp_providers.yaml:
    - id: text_tools
      name: Text Utilities
      transport: stdio
      command: python
      args: ["stdio_servers/text_tools/server.py"]
      auth:
        type: none
      enabled: true
"""

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("text-tools")


@mcp.tool()
def count_words(text: str) -> dict:
    """Count words, characters, and sentences in a text string."""
    words = text.split()
    sentences = text.count(".") + text.count("!") + text.count("?")
    return {
        "words": len(words),
        "characters": len(text),
        "characters_no_spaces": len(text.replace(" ", "")),
        "sentences": sentences,
    }


@mcp.tool()
def generate_slug(text: str, separator: str = "-") -> str:
    """Convert a text string into a URL-friendly slug."""
    import re

    slug = text.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", separator, slug)
    slug = re.sub(f"{re.escape(separator)}+", separator, slug)
    return slug.strip(separator)


@mcp.tool()
def extract_keywords(text: str, max_keywords: int = 10) -> list:
    """Extract the most frequent meaningful words from text as keywords."""
    import re
    from collections import Counter

    stop_words = {
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to",
        "for", "of", "with", "by", "from", "is", "are", "was", "were",
        "be", "been", "being", "have", "has", "had", "do", "does", "did",
        "will", "would", "could", "should", "may", "might", "shall", "can",
        "this", "that", "these", "those", "i", "you", "he", "she", "it",
        "we", "they", "what", "which", "who", "when", "where", "why", "how",
    }

    words = re.findall(r"\b[a-z]{3,}\b", text.lower())
    meaningful = [w for w in words if w not in stop_words]
    counter = Counter(meaningful)
    return [word for word, _ in counter.most_common(max_keywords)]


@mcp.tool()
def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """Truncate text to a maximum length, appending a suffix if truncated."""
    if len(text) <= max_length:
        return text
    return text[: max_length - len(suffix)] + suffix


if __name__ == "__main__":
    mcp.run()
