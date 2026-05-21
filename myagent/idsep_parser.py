from typing import Optional
import random
import string


class IDSepParser:
    def __init__(self, sepid: Optional[str]):
        if sepid is None:
            char_set = string.ascii_uppercase + string.ascii_lowercase + string.digits
            self.sepid = "[" + "".join(random.sample(char_set * 6, 6)) + "]"
        else:
            self.sepid = sepid

    def parse(self, s: str):
        parts = s.split(self.sepid)[1:-1]
        if len(parts) % 2 != 0:
            raise ValueError(f'IDSep key value pairs are not matched: "{s}"')

        ans = {}
        for i in range(0, len(parts), 2):
            ans[parts[i]] = parts[i + 1]

        return ans

    def build(self, kvs: dict) -> str:
        return (
            self.sepid
            + self.sepid.join([f"{k}{self.sepid}{v}" for k, v in kvs.items()])
            + self.sepid
        )
