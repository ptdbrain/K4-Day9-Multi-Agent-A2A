import os
import pandas as pd

class OlistDatabase:
    def __init__(self, data_dir="data"):
        self.data_dir = data_dir
        self.load_data()

    def load_data(self):
        print("Loading Olist datasets...")
        self.orders = pd.read_csv(os.path.join(self.data_dir, "olist_orders_dataset.csv"))
        self.order_items = pd.read_csv(os.path.join(self.data_dir, "olist_order_items_dataset.csv"))
        self.order_payments = pd.read_csv(os.path.join(self.data_dir, "olist_order_payments_dataset.csv"))
        self.customers = pd.read_csv(os.path.join(self.data_dir, "olist_customers_dataset.csv"))
        self.products = pd.read_csv(os.path.join(self.data_dir, "olist_products_dataset.csv"))
        self.sellers = pd.read_csv(os.path.join(self.data_dir, "olist_sellers_dataset.csv"))
        
        # Load category translation
        translation_path = os.path.join(self.data_dir, "product_category_name_translation.csv")
        self.cat_translation = {}
        if os.path.exists(translation_path):
            translation_df = pd.read_csv(translation_path, encoding="utf-8-sig")
            translation_df.columns = [c.strip() for c in translation_df.columns]
            for _, row in translation_df.iterrows():
                self.cat_translation[row["product_category_name"]] = row["product_category_name_english"]

        # Tạo index để query nhanh
        self.orders_indexed = self.orders.set_index("order_id")
        self.customers_indexed = self.customers.set_index("customer_id")
        print("Datasets loaded successfully.")

    def get_order_details(self, order_id):
        """Lấy thông tin chung của đơn hàng"""
        if order_id not in self.orders_indexed.index:
            return None
        order = self.orders_indexed.loc[order_id]
        if isinstance(order, pd.DataFrame):
            order = order.iloc[0]
        return order.to_dict()

    def get_customer_by_id(self, customer_id):
        """Lấy thông tin khách hàng bằng customer_id"""
        if customer_id not in self.customers_indexed.index:
            return None
        cust = self.customers_indexed.loc[customer_id]
        if isinstance(cust, pd.DataFrame):
            cust = cust.iloc[0]
        return cust.to_dict()

    def get_customer_history(self, customer_unique_id, current_order_id):
        """Lấy lịch sử mua hàng của khách hàng (loại trừ order hiện tại)"""
        # Tìm tất cả customer_id của customer_unique_id này
        cust_ids = self.customers[self.customers["customer_unique_id"] == customer_unique_id]["customer_id"].tolist()
        # Tìm các order tương ứng và giữ thứ tự ổn định theo dữ liệu nguồn (không sort theo timestamp)
        cust_orders = self.orders[self.orders["customer_id"].isin(cust_ids)].copy()
        related_orders = cust_orders[(cust_orders["order_id"] != current_order_id) & (~cust_orders["order_status"].isin(["canceled", "unavailable"]))]
        return related_orders["order_id"].tolist()

    def get_order_items(self, order_id):
        """Lấy danh sách các mặt hàng trong đơn hàng kèm category name"""
        items_df = self.order_items[self.order_items["order_id"] == order_id]
        if items_df.empty:
            return []
        
        # Join với products để lấy category name
        items_joined = items_df.merge(self.products, on="product_id", how="left")
        return items_joined.to_dict(orient="records")

    def get_order_payments(self, order_id):
        """Lấy danh sách các khoản thanh toán cho đơn hàng"""
        payments_df = self.order_payments[self.order_payments["order_id"] == order_id]
        if payments_df.empty:
            return []
        # Giữ thứ tự ổn định theo dữ liệu nguồn (không sort_values theo payment_sequential)
        return payments_df.to_dict(orient="records")
