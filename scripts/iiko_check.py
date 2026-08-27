import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import aiohttp

import config
from iiko_client import IikoClient


async def main():
    if not config.IIKO_API_LOGIN:
        print("IIKO_API_LOGIN не задан в .env")
        return

    c = IikoClient()
    timeout = aiohttp.ClientTimeout(total=60)
    async with aiohttp.ClientSession(timeout=timeout) as http:
        async with http.post(
            f"{config.IIKO_API_URL}/api/1/access_token",
            json={"apiLogin": config.IIKO_API_LOGIN},
        ) as resp:
            data = await resp.json()
            if resp.status != 200 or "token" not in data:
                print(f"ОШИБКА авторизации: {resp.status} {data}")
                return
            c._token = data["token"]
            c._token_time = time.time()
        print("Авторизация: OK")

        orgs = await c.get_organizations()
        print("\n=== Организации ===")
        for o in orgs:
            print(f"  {o['id']}  {o.get('name')}")

        if not orgs:
            return

        groups = await c.get_terminal_groups([o["id"] for o in orgs])
        print("\n=== Точки продаж (terminalGroups) ===")
        for og in groups.get("terminalGroups", []):
            org_name = next(
                (o.get("name") for o in orgs if o["id"] == og["organizationId"]), "?"
            )
            for g in og.get("terminalGroups", []):
                addr = g.get("address", {}).get("addressLine") or g.get("address")
                print(
                    f"  org={og['organizationId']}\n    tg={g['id']}  {g.get('name')}  ({org_name}; {addr})"
                )

        org_id = config.IIKO_ORGANIZATION_ID or orgs[0]["id"]
        print(f"\nВыгружаю номенклатуру организации {org_id}...")
        nom = await c.get_nomenclature(org_id)

        cats = {
            cat["id"]: cat.get("name")
            for cat in nom.get("productCategories", [])
        }
        products = []
        for p in nom.get("products", []):
            sizes = p.get("sizePrices") or [{}]
            price = (sizes[0].get("price") or {}).get("currentPrice")
            products.append(
                {
                    "id": p["id"],
                    "name": p.get("name"),
                    "category": cats.get(p.get("productCategoryId")),
                    "price": price,
                    "isDeleted": p.get("isDeleted", False),
                }
            )

        out = {"organizationId": org_id, "categories": list(cats.values()), "products": products}
        path = Path(__file__).parent.parent / "iiko_nomenclature.json"
        path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        active = sum(1 for p in products if not p["isDeleted"])
        print(f"Сохранено: {path}")
        print(f"Позиций всего: {len(products)}, активных: {active}")


if __name__ == "__main__":
    asyncio.run(main())
