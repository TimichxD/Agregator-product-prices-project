"""Окно сравнения полной стоимости корзины по магазинам."""

from pathlib import Path

from PyQt6 import uic
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QAbstractItemView, QWidget, QTableWidgetItem

from models.product import Product
from services.basket_optimizer import format_money


class ComparePage(QWidget):
    """Сравнивает наличие товаров и сумму корзины в каждом магазине."""

    def __init__(self, basket: dict[str, int], products_by_id: dict[str, Product], on_back=None, parent=None):
        super().__init__(parent)
        ui_path = Path(__file__).with_name("compare_window.ui")
        uic.loadUi(str(ui_path), self)
        self.basket = basket
        self.products_by_id = products_by_id
        self.on_back = on_back
        self.closeButton.setText("К каталогу")
        self.closeButton.clicked.connect(self._go_back)
        self.fill_comparison()


    def _go_back(self) -> None:
        if callable(self.on_back):
            self.on_back()

    def fill_comparison(self) -> None:
        table = self.comparisonTable
        table.setRowCount(0)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setAlternatingRowColors(True)
        table.setShowGrid(False)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(44)
        table.setWordWrap(False)
        table.horizontalHeader().setMinimumSectionSize(90)
        table.horizontalHeader().setStretchLastSection(True)

        if not self.basket:
            self.summaryLabel.setText("Корзина пуста. Добавьте товары из каталога, чтобы сравнить стоимость.")
            return

        stores = sorted({
            offer.store
            for product in self.products_by_id.values()
            for offer in product.offers
        }, key=str.casefold)
        if not stores:
            self.summaryLabel.setText("В каталоге пока нет ценовых предложений. Загрузите файл каталога с ценами магазинов.")
            return

        results = []
        for store in stores:
            total = 0.0
            found = 0
            for product_id, quantity in self.basket.items():
                product = self.products_by_id.get(product_id)
                if product is None:
                    continue
                offer = product.offer_for(store)
                if offer is not None:
                    total += offer.unit_price * quantity
                    found += 1
            results.append({"store": store, "total": total, "found": found})

        complete = [result for result in results if result["found"] == len(self.basket)]
        best_total = min((result["total"] for result in complete), default=None)
        results.sort(key=lambda result: (result["found"] != len(self.basket), result["total"], result["store"].casefold()))

        if best_total is None:
            self.summaryLabel.setText(
                "Нет магазина, где доступны все товары из корзины. "
                "В таблице показана сумма только найденных позиций."
            )
        else:
            best_store = next(
                result["store"] for result in results
                if result["found"] == len(self.basket) and result["total"] == best_total
            )
            self.summaryLabel.setText(
                f"Самый дешёвый полный вариант: {best_store} — {format_money(best_total)}."
            )

        table.setRowCount(len(results))
        for row, result in enumerate(results):
            is_complete = result["found"] == len(self.basket)
            difference = "—" if (not is_complete or best_total is None) else format_money(result["total"] - best_total)
            values = [
                result["store"],
                format_money(result["total"]),
                f"{result['found']} из {len(self.basket)} товаров" if is_complete
                else f"{result['found']} из {len(self.basket)} · неполная корзина",
                difference,
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if column == 1:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                table.setItem(row, column, item)
        table.setColumnWidth(0, 180)
        table.setColumnWidth(1, 170)
        table.setColumnWidth(2, 250)


# Совместимость со старыми импортами: CompareWindow теперь является встроенной страницей.
CompareWindow = ComparePage
