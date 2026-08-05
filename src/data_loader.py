"""
Data Loader — singleton that loads and indexes all 9 Olist CSV files.
Agents call this once; subsequent calls return cached data.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import pandas as pd

DATA_DIR = Path(__file__).parent.parent / "data"


class DataLoader:
    """Singleton data loader for all Olist CSV datasets."""

    _instance: Optional["DataLoader"] = None

    def __new__(cls) -> "DataLoader":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._loaded = False
        return cls._instance

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------
    def load_all(self) -> None:
        if self._loaded:
            return

        print("[DataLoader] Loading CSV datasets …")

        self.orders = pd.read_csv(DATA_DIR / "olist_orders_dataset.csv")
        self.customers = pd.read_csv(DATA_DIR / "olist_customers_dataset.csv")
        self.order_items = pd.read_csv(DATA_DIR / "olist_order_items_dataset.csv")
        self.order_payments = pd.read_csv(DATA_DIR / "olist_order_payments_dataset.csv")
        self.products = pd.read_csv(DATA_DIR / "olist_products_dataset.csv")
        self.sellers = pd.read_csv(DATA_DIR / "olist_sellers_dataset.csv")
        self.category_translation = pd.read_csv(
            DATA_DIR / "product_category_name_translation.csv"
        )

        # Parse timestamps in orders
        _ts_cols = [
            "order_purchase_timestamp",
            "order_approved_at",
            "order_delivered_carrier_date",
            "order_delivered_customer_date",
            "order_estimated_delivery_date",
        ]
        for col in _ts_cols:
            self.orders[col] = pd.to_datetime(self.orders[col], errors="coerce")

        # Parse shipping_limit_date in order_items
        self.order_items["shipping_limit_date"] = pd.to_datetime(
            self.order_items["shipping_limit_date"], errors="coerce"
        )

        # Build category translation dict (pt → en)
        self._cat_map: dict[str, str] = dict(
            zip(
                self.category_translation["product_category_name"],
                self.category_translation["product_category_name_english"],
            )
        )

        self._loaded = True
        print("[DataLoader] All datasets loaded successfully.")

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------
    def get_order(self, order_id: str) -> Optional[dict]:
        rows = self.orders[self.orders["order_id"] == order_id]
        if rows.empty:
            return None
        return rows.iloc[0].to_dict()

    def get_customer(self, customer_id: str) -> Optional[dict]:
        rows = self.customers[self.customers["customer_id"] == customer_id]
        if rows.empty:
            return None
        return rows.iloc[0].to_dict()

    def get_customer_by_unique_id(self, customer_unique_id: str) -> list[dict]:
        rows = self.customers[
            self.customers["customer_unique_id"] == customer_unique_id
        ]
        return rows.to_dict("records")

    def get_order_items(self, order_id: str) -> list[dict]:
        rows = self.order_items[self.order_items["order_id"] == order_id]
        return rows.to_dict("records")

    def get_order_payments(self, order_id: str) -> list[dict]:
        rows = self.order_payments[self.order_payments["order_id"] == order_id]
        return rows.to_dict("records")

    def get_product(self, product_id: str) -> Optional[dict]:
        rows = self.products[self.products["product_id"] == product_id]
        if rows.empty:
            return None
        return rows.iloc[0].to_dict()

    def get_seller(self, seller_id: str) -> Optional[dict]:
        rows = self.sellers[self.sellers["seller_id"] == seller_id]
        if rows.empty:
            return None
        return rows.iloc[0].to_dict()

    def get_orders_by_customer_ids(self, customer_ids: list[str]) -> list[str]:
        rows = self.orders[self.orders["customer_id"].isin(customer_ids)]
        return rows["order_id"].tolist()

    def translate_category(self, name_pt: Optional[str]) -> Optional[str]:
        if name_pt is None or (isinstance(name_pt, float)):
            return None
        return self._cat_map.get(str(name_pt), str(name_pt))
