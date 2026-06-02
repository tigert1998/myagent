def shorten(s: str, width: int):
    if len(s) <= width:
        return s
    return s[:width] + "..."
