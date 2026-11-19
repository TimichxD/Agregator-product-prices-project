"""Контроллер формы добавления товара."""

from pathlib import Path

from PyQt6 import uic
from PyQt6.QtWidgets import QDialog

from models.product import Product
from services.basket_optimizer import format_money


class AddProductDialog(QDialog):
    def __init__(self, products: list[Product], parent=None):
        super().__init__(parent)
        ui_path = Path(__file__).with_name("add_product_dialog.ui")
        uic.loadUi(str(ui_path), self)
        self.products = products
        self.selected_product: Product | None = None
        self.quantity = 1

        self.productComboBox.clear()
        for product in products:
            self.productComboBox.addItem(
                f"{product.name} · {product.unit}",
                product.product_id,
            )

        self.productComboBox.currentIndexChanged.connect(self._update_details)
        self.cancelButton.clicked.connect(self.reject)
        self.addButton.clicked.connect(self._accept_selection)
        self._update_details()

    def _update_details(self, *_args) -> None:
        product_id = self.productComboBox.currentData()
        product = next((p for p in self.products if p.product_id == product_id), None)
        if product is None:
            self.productDetailsLabel.setText("Нет доступных товаров.")
            self.addButton.setEnabled(False)
            return
        self.addButton.setEnabled(True)
        if product.minimum_price is None:
            details = "Для товара пока не загружены ценовые предложения."
        else:
            details = f"Лучшая цена: {format_money(product.minimum_price)} за {product.unit}."
        self.productDetailsLabel.setText(details)

    def _accept_selection(self) -> None:
        product_id = self.productComboBox.currentData()
        self.selected_product = next((p for p in self.products if p.product_id == product_id), None)
        self.quantity = self.quantitySpinBox.value()
        if self.selected_product is not None:
            self.accept()
