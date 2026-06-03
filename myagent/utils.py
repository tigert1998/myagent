def shorten(s: str, width: int) -> str:
    if len(s) <= width:
        return s
    return s[:width] + "..."
