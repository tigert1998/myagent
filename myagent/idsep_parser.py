import random
import string


class IDSepParser:
    def __init__(self):
        char_set = string.ascii_uppercase + string.ascii_lowercase + string.digits
        id = "".join(random.sample(char_set * 6, 6))
        self.sepidk = f"[{id}-k]"
        self.sepidv = f"[{id}-v]"
        self.sepide = f"[{id}-e]"

    def parse(self, s: str):
        ans = {}
        for part in s.split(self.sepide)[:-1]:
            for kv in part.split(self.sepidk)[1:]:
                k, v = kv.split(self.sepidv)
                ans[k] = v

        return ans

    def build(self, kvs: dict) -> str:
        return (
            "".join([f"{self.sepidk}{k}{self.sepidv}{v}" for k, v in kvs.items()])
            + self.sepide
        )
