import random
import string


class IDSepParser:
    def __init__(self) -> None:
        char_set: str = string.ascii_uppercase + string.ascii_lowercase + string.digits
        rid: str = "".join(random.sample(char_set * 6, 6))
        self.sepidk: str = f"[{rid}-k]"
        self.sepidv: str = f"[{rid}-v]"
        self.sepide: str = f"[{rid}-e]"

    def parse(self, s: str) -> dict[str, str]:
        ans: dict[str, str] = {}
        for part in s.split(self.sepide)[:-1]:
            for kv in part.split(self.sepidk)[1:]:
                k, v = kv.split(self.sepidv)
                ans[k] = v

        return ans

    def build(self, kvs: dict[str, str]) -> str:
        return (
            "".join([f"{self.sepidk}{k}{self.sepidv}{v}" for k, v in kvs.items()])
            + self.sepide
        )
