"""
OrderProductAgent — fetches order items, sellers, products, and categories.

Input:  order_id
Output: {
    order_status: str,
    item_ids: list[str],          # "<order_id>:<order_item_id>"
    seller_ids: list[str],        # up to 3 unique sellers
    product_ids: list[str],       # up to 5 unique products
    category_names: list[str],    # up to 5 unique EN category names
    raw_items: list[dict],        # full item rows for downstream agents
}
"""
from __future__ import annotations

from src.agents.base_agent import BaseAgent


class OrderProductAgent(BaseAgent):
    name = "OrderProductAgent"

    def run(self, case_id: str, order_id: str) -> dict:
        self.log(case_id, "start", {"order_id": order_id})

        order = self.db.get_order(order_id)
        if order is None:
            self.log(case_id, "error", {"reason": "order_not_found"})
            return {
                "order_status": None,
                "item_ids": [],
                "seller_ids": [],
                "product_ids": [],
                "category_names": [],
                "raw_items": [],
            }

        order_status = order.get("order_status")
        raw_items = self.db.get_order_items(order_id)

        # Build item_ids as "<order_id>:<order_item_id>"
        item_ids = [
            f"{order_id}:{row['order_item_id']}"
            for row in raw_items
        ][:5]

        # Unique sellers (preserve insertion order, cap at 3)
        seen_sellers: list[str] = []
        for row in raw_items:
            sid = row.get("seller_id")
            if sid and sid not in seen_sellers:
                seen_sellers.append(sid)
        seller_ids = seen_sellers[:3]

        # Unique products (cap at 5)
        seen_products: list[str] = []
        for row in raw_items:
            pid = row.get("product_id")
            if pid and pid not in seen_products:
                seen_products.append(pid)
        product_ids = seen_products[:5]

        # Category names (EN translation, cap at 5)
        seen_cats: list[str] = []
        for pid in product_ids:
            product = self.db.get_product(pid)
            if product:
                cat_pt = product.get("product_category_name")
                cat_en = self.db.translate_category(cat_pt)
                if cat_en and cat_en not in seen_cats:
                    seen_cats.append(cat_en)
        category_names = seen_cats[:5]

        result = {
            "order_status": order_status,
            "item_ids": item_ids,
            "seller_ids": seller_ids,
            "product_ids": product_ids,
            "category_names": category_names,
            "raw_items": raw_items,
        }
        self.log(case_id, "done", {
            "order_status": order_status,
            "num_items": len(raw_items),
            "num_sellers": len(seller_ids),
        })
        return result
