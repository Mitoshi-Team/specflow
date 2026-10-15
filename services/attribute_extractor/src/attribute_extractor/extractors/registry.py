"""Реестр экстракторов с упорядочиванием по приоритету."""

from collections.abc import Iterable, Iterator

from attribute_extractor.extractors.base import BaseExtractor


class ExtractorRegistry:
    """Хранит экстракторы и сортирует их по возрастанию ``priority``.

    Экстракторы с одинаковым приоритетом сохраняют порядок регистрации
    (сортировка стабильная), что делает каскад детерминированным.
    """

    def __init__(self, extractors: Iterable[BaseExtractor] | None = None) -> None:
        self._extractors: list[BaseExtractor] = []
        for extractor in extractors or ():
            self.register(extractor)

    def register(self, extractor: BaseExtractor) -> None:
        """Добавить экстрактор и пересортировать реестр по ``priority``."""
        self._extractors.append(extractor)
        self._extractors.sort(key=lambda item: item.priority)

    @property
    def extractors(self) -> tuple[BaseExtractor, ...]:
        """Экстракторы в порядке запуска каскада."""
        return tuple(self._extractors)

    def extractors_for(
        self, attribute_code: str, category: str | None = None
    ) -> list[BaseExtractor]:
        """Экстракторы, поддерживающие указанный атрибут/категорию."""
        return [item for item in self._extractors if item.supports(attribute_code, category)]

    def get(self, name: str) -> BaseExtractor | None:
        """Вернуть экстрактор по имени (или ``None``, если не найден)."""
        return next((item for item in self._extractors if item.name == name), None)

    def __iter__(self) -> Iterator[BaseExtractor]:
        return iter(self._extractors)

    def __len__(self) -> int:
        return len(self._extractors)
