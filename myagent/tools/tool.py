import inspect
from typing import Optional


class Tool:
    name: str
    desc: str
    pin: bool

    def invoke(self, *args, **kwargs) -> str:
        raise NotImplementedError()

    def inject(self) -> Optional[str]:
        return None

    def signature(self) -> str:
        return f'def {self.name}{inspect.signature(self.invoke)}\n\t"""{self.desc}"""\n\tpass\n'
