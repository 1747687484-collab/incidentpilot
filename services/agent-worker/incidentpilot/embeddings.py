KEYWORDS = ("order", "payment", "inventory", "timeout", "cache", "database", "error", "latency")


def embedding_literal(text: str) -> str:
    lower = text.lower()
    values = [f"{(lower.count(keyword) + 1) / 10:.4f}" for keyword in KEYWORDS]
    return "[" + ",".join(values) + "]"

