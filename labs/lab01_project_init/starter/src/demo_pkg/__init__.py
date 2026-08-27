"""demo_pkg: minimal package for lab01 src-layout demo."""

__version__ = "0.1.0"

def hello(name: str = "World") -> str:
    return f"hello, {name}"
