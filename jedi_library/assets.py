"""Acesso a recursos empacotados via importlib.resources."""
import fnmatch
from importlib.resources import files
from importlib.resources.abc import Traversable


def read_text(package: str, resource: str, encoding: str = "utf-8") -> str:
    """Lê conteúdo de recurso empacotado."""
    return files(package).joinpath(resource).read_text(encoding=encoding)


def list_files(package: str, subdir: str, pattern: str = "*") -> list[Traversable]:
    """Lista arquivos de subdiretório em ordem lexicográfica, filtrados por padrão fnmatch."""
    container = files(package).joinpath(subdir)
    items = [
        item for item in container.iterdir()
        if item.is_file() and fnmatch.fnmatch(item.name, pattern)
    ]
    return sorted(items, key=lambda f: f.name)
