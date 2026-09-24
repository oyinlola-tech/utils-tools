"""Shared PDF page-selection parsing."""

_ALL_TOKENS = {"", "all", "*"}


def _parse_page_number(raw: str, token: str) -> int:
    raw = raw.strip()
    if not raw.isdigit():
        raise ValueError(
            f"Invalid page selection '{token}'. "
            "Use page numbers and ranges such as 1,3-5."
        )
    return int(raw)


def parse_page_selection(spec: str, page_count: int) -> list[int]:
    """Parse a page selection like '1,3-5' into 1-based page numbers.

    ``all`` (or an empty selection) selects every page. Range ends past
    the last page are clamped to the document length so a default such
    as ``1-3`` still works for shorter PDFs; open ranges (``3-``, ``-2``)
    are also accepted. Ranges that start after the last page and single
    page numbers outside the document are rejected.
    """
    if page_count < 1:
        raise ValueError("The PDF has no pages.")
    if (spec or "").strip().lower() in _ALL_TOKENS:
        return list(range(1, page_count + 1))

    selection: set[int] = set()
    for token in spec.split(","):
        token = token.strip()
        if not token:
            continue
        if "-" in token:
            start_raw, end_raw = token.split("-", 1)
            start = (
                _parse_page_number(start_raw, token)
                if start_raw.strip()
                else 1
            )
            end = (
                _parse_page_number(end_raw, token)
                if end_raw.strip()
                else page_count
            )
            if start < 1 or start > end:
                raise ValueError(f"Invalid page range: {token}")
            if start > page_count:
                raise ValueError(
                    f"Invalid page range: {token} "
                    f"(the PDF has {page_count} page"
                    f"{'' if page_count == 1 else 's'})."
                )
            selection.update(range(start, min(end, page_count) + 1))
        else:
            page = _parse_page_number(token, token)
            if page < 1 or page > page_count:
                raise ValueError(
                    f"Invalid page number: {token} "
                    f"(the PDF has {page_count} page"
                    f"{'' if page_count == 1 else 's'})."
                )
            selection.add(page)
    if not selection:
        raise ValueError("Page selection is empty.")
    return sorted(selection)
