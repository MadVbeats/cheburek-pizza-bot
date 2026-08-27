from collections import defaultdict

from menu_data import get_item

_carts: dict = defaultdict(dict)
_order_counter = 100


def add_item(user_id: int, ci: int, ii: int):
    key = (ci, ii)
    _carts[user_id][key] = _carts[user_id].get(key, 0) + 1


def set_qty(user_id: int, ci: int, ii: int, qty: int):
    key = (ci, ii)
    if qty <= 0:
        _carts[user_id].pop(key, None)
        if not _carts[user_id]:
            _carts.pop(user_id, None)
    else:
        _carts[user_id][key] = qty


def change_qty(user_id: int, ci: int, ii: int, delta: int):
    key = (ci, ii)
    set_qty(user_id, ci, ii, _carts.get(user_id, {}).get(key, 0) + delta)


def clear_cart(user_id: int):
    _carts.pop(user_id, None)


def cart_lines(user_id: int) -> list[dict]:
    lines = []
    for (ci, ii), qty in _carts.get(user_id, {}).items():
        _, item = get_item(ci, ii)
        lines.append(
            {
                "ci": ci,
                "ii": ii,
                "name": item["name"],
                "price": item["price"],
                "qty": qty,
                "sum": item["price"] * qty,
            }
        )
    return lines


def cart_total(user_id: int) -> int:
    return sum(line["sum"] for line in cart_lines(user_id))


def next_order_id() -> int:
    global _order_counter
    _order_counter += 1
    return _order_counter
