"""Collection types that add ``.filtered(**kwargs)`` on top of ``list``.

:class:`FilteredList` is a thin ``list`` subclass with one extra method —
``filtered`` — for chainable, attribute-based narrowing using keyword
arguments (so it works inside Jinja2 / Django templates, which cannot
define lambdas). The two named subclasses :class:`BlockList` and
:class:`SectionList` are what the public API actually returns; they exist
mostly to give nicer reprs and let ``isinstance(x, BlockList)`` discriminate
without poking at generic introspection.
"""

from __future__ import annotations

from typing import Any, Generic, List, Optional, Tuple, TypeVar, Union

T = TypeVar("T")


_MISSING = object()


# Operator table — ``attr__<op>=value`` maps to ``_OPS[op](attr_value, value)``.
# Adding a new operator is a one-line entry here.
_OPS = {
    "eq":         lambda a, b: a == b,
    "ne":         lambda a, b: a != b,
    "lt":         lambda a, b: a < b,
    "lte":        lambda a, b: a <= b,
    "gt":         lambda a, b: a > b,
    "gte":        lambda a, b: a >= b,
    "in":         lambda a, b: a in b,
    "contains":   lambda a, b: b in a,
    "startswith": lambda a, b: a.startswith(b),
    "endswith":   lambda a, b: a.endswith(b),
}


def _resolve_key(key: str) -> Tuple[str, str]:
    """Split ``"level__gte"`` into ``("level", "gte")``.

    Falls back to ``(key, "eq")`` if the suffix after the last ``__`` is
    not a known operator, so an attribute literally named ``foo__bar`` is
    still addressable via ``foo__bar=value``.
    """
    if "__" in key:
        attr, _, op = key.rpartition("__")
        if op in _OPS and attr:
            return attr, op
    return key, "eq"


class FilteredList(list, Generic[T]):
    """A ``list`` subclass with chainable, kwargs-based filtering.

    Examples::

        section.blocks.filtered(kind="paragraph")
        section.blocks.filtered(kind="code", info="python")
        e.headers().filtered(level__gte=2)
        e.headers().filtered(level__in=[2, 3])
        e.headers().filtered(title__startswith="Sub")

    Multiple kwargs are AND-combined. Each key is ``attr`` (implicit
    equality) or ``attr__<op>``. Supported operators: ``eq`` (default),
    ``ne``, ``lt``, ``lte``, ``gt``, ``gte``, ``in``, ``contains``,
    ``startswith``, ``endswith``.

    Items missing the requested attribute are treated as non-matches
    (no exception). Filtering and slicing both preserve the concrete
    subclass, so chains stay typed end-to-end.
    """

    def filtered(self, **conditions: Any) -> "FilteredList[T]":
        """Return a new collection of the same type containing only items
        matching every keyword condition.

        With no kwargs, returns a shallow copy.
        """
        if not conditions:
            return type(self)(self)
        checks = [(*_resolve_key(k), v) for k, v in conditions.items()]
        out: "FilteredList[T]" = type(self)()
        for item in self:
            keep = True
            for attr, op, expected in checks:
                value = getattr(item, attr, _MISSING)
                if value is _MISSING or not _OPS[op](value, expected):
                    keep = False
                    break
            if keep:
                out.append(item)
        return out

    def mapped(self, path: str) -> Union["FilteredList[Any]", List[Any]]:
        """Gather values from a dotted attribute path, flattening lists.

        Examples::

            section.children.mapped("title")            # list[str]
            section.children.mapped("blocks")           # BlockList
            section.children.mapped("blocks.inlines")   # BlockList

        Equivalent: ``c.mapped("x.y") == c.mapped("x").mapped("y")``.
        List-typed attributes (e.g. ``.blocks``) flatten into the result;
        scalar attributes append. The concrete subclass is preserved
        when every value came from the same :class:`FilteredList`
        subclass, so ``.mapped("blocks").filtered(kind="paragraph")``
        keeps working. Items missing the attribute are skipped (same
        as :meth:`filtered`). An empty path returns a shallow copy.
        """
        if not path:
            return type(self)(self)
        attr, _, rest = path.partition(".")

        gathered: List[Any] = []
        list_kind: Optional[type] = None
        mixed = False
        saw_scalar = False

        for item in self:
            value = getattr(item, attr, _MISSING)
            if value is _MISSING:
                continue
            if isinstance(value, list):
                if isinstance(value, FilteredList):
                    if list_kind is None:
                        list_kind = type(value)
                    elif list_kind is not type(value):
                        mixed = True
                gathered.extend(value)
            else:
                saw_scalar = True
                gathered.append(value)

        result: Union[FilteredList[Any], List[Any]]
        if list_kind is not None and not saw_scalar:
            result = (FilteredList if mixed else list_kind)(gathered)
        else:
            result = gathered  # plain list (scalars, or nothing matched)

        if rest:
            if isinstance(result, FilteredList):
                return result.mapped(rest)
            return []  # can't descend into scalars / missing attrs
        return result

    def __getitem__(self, key):
        result = super().__getitem__(key)
        if isinstance(key, slice):
            return type(self)(result)
        return result


class BlockList(FilteredList["Block"]):  # type: ignore[type-arg]
    """A :class:`FilteredList` of :class:`~markdown_extractor.blocks.Block`."""


class SectionList(FilteredList["Section"]):  # type: ignore[type-arg]
    """A :class:`FilteredList` of :class:`~markdown_extractor.section.Section`."""
