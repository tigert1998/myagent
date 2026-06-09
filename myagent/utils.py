import os.path as osp


def shorten(s: str, width: int) -> str:
    if len(s) <= width:
        return s
    return s[:width] + "..."


def project_path() -> str:
    return osp.abspath(osp.join(osp.dirname(__file__), ".."))
