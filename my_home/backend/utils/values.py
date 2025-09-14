from typing import Dict, Any, Iterable, List, Optional

def _iter_items(values: Iterable[Dict[str, Any]]):
    """Итерирует по плоским items и по группам с key 'data'."""
    for it in values:
        if it.get("type") == "file_list":
            # пропускаем списки файлов / служебные разделы
            continue
        if isinstance(it, dict) and "data" in it and isinstance(it["data"], list):
            # Это группа: отдаём пару (item, group_meta)
            group_title = it.get("title")
            group_href = it.get("href")
            for sub in it["data"]:
                yield sub, {"group_title": group_title, "group_href": group_href}
        else:
            yield it, {"group_title": None, "group_href": None}

def _split_type(type_str: Optional[str]) -> (Optional[str], Optional[str]):
    if not type_str or "." not in type_str:
        return None, None
    a, b = type_str.split(".", 1)
    return a or None, b or None

def flatten_ports(values: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Превращает /values в расширенный список портов.
    Возвращаемый элемент (пример):
    {
      "code": "analog-34",
      "title": "temperature",       # если есть у item
      "direction": "in",            # из type
      "kind": "analog",             # из type
      "type_raw": "in.analog",
      "val": 3.10,
      "unit": "Ohm",                # если есть
      "mqtt": "m/home/room1/analog_test",
      "href": "/#rewriter-0-11:id=0",  # item.href или group.href
      "group_title": "NTC 0",
      "group_href": "/#rewriter-0-11:id=0",
      "raw": {...}                  # исходный узел
    }
    """
    out: List[Dict[str, Any]] = []
    for item, meta in _iter_items(values):
        if not isinstance(item, dict):
            continue

        type_raw = item.get("type")
        direction, kind = _split_type(type_raw)

        code = item.get("code")
        if not code or not direction:  # оставляем только настоящие порты in./out.
            continue

        # href может быть как у item, так и у группы
        href = item.get("href") or meta.get("group_href")

        rec = {
            "code": code,
            "title": item.get("title"),
            "direction": direction,       # "in" / "out"
            "kind": kind,                 # "analog" / "text" / "digital" ...
            "type_raw": type_raw,
            "val": item.get("val"),
            "unit": item.get("unit"),
            "mqtt": item.get("mqtt"),
            "href": href,
            "group_title": meta.get("group_title"),
            "group_href": meta.get("group_href"),
            "raw": item,
        }

        # На будущее: подтягиваем любые дополнительные нестандартные ключи в extra
        extra_keys = set(item.keys()) - {
            "code", "title", "type", "val", "unit", "mqtt", "href", "data"
        }
        if extra_keys:
            rec["extra"] = {k: item[k] for k in extra_keys}

        out.append(rec)

    return out