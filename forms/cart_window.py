"""Окно корзины: изменение количества и обмен данными через CSV."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Callable

from PyQt6 import uic
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QWidget,
    QFileDialog,
    QMessageBox,
    QTableWidgetItem,
)

from models.product import Product
from services.basket_optimizer import format_money


class CartPage(QWidget):
    """Форма корзины, работающая с общей корзиной главного окна."""

    def __init__(
        self,
        basket: dict[str, int],
        products_by_id: dict[str, Product],
        on_change: Callable[[], None],
        parent=None,
        on_compare: Callable[[], None] | None = None,
    ):
        super().__init__(parent)
        ui_path = Path(__file__).with_name("cart_window.ui")
        uic.loadUi(str(ui_path), self)
        self.basket = basket
        self.products_by_id = products_by_id
        self.on_change = on_change
        self.on_compare = on_compare
        self._updating_table = False

        self.cartTable.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.cartTable.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.cartTable.setAlternatingRowColors(True)
        self.cartTable.setShowGrid(False)
        self.cartTable.verticalHeader().setVisible(False)
        self.cartTable.verticalHeader().setDefaultSectionSize(44)
        self.cartTable.horizontalHeader().setMinimumSectionSize(86)
        self.cartTable.setWordWrap(False)
        self.cartTable.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
        )
        self.cartTable.horizontalHeader().setStretchLastSection(True)
        self.cartTable.itemChanged.connect(self.quantity_changed)

        self.removeItemButton.clicked.connect(self.remove_selected)
        self.importCSVButton.clicked.connect(self.import_csv)
        self.exportCSVButton.clicked.connect(self.export_csv)
        self.compareCartButton.clicked.connect(self.open_comparison)
        self.refresh_table()

    def refresh_table(self) -> None:
        self._updating_table = True
        self.cartTable.setRowCount(0)
        quantity_sum = 0
        total_sum = 0.0
        unpriced_count = 0
        for product_id, quantity in self.basket.items():
            product = self.products_by_id.get(product_id)
            if product is None:
                continue
            row = self.cartTable.rowCount()
            self.cartTable.insertRow(row)

            id_item = QTableWidgetItem(product_id)
            id_item.setData(Qt.ItemDataRole.UserRole, product_id)
            self._lock_item(id_item)
            self.cartTable.setItem(row, 0, id_item)
            self.cartTable.setItem(row, 1, self._item(product.name))
            self.cartTable.setItem(row, 2, self._item(product.unit))

            quantity_item = self._item(str(quantity), editable=True, centered=True)
            self.cartTable.setItem(row, 3, quantity_item)

            best_price = product.minimum_price
            price_text = format_money(best_price) if best_price is not None else "Нет предложений"
            self.cartTable.setItem(row, 4, self._item(price_text, centered=True))
            quantity_sum += quantity
            if best_price is not None:
                total_sum += best_price * quantity
            else:
                unpriced_count += 1

        count_text = f"Позиций: {len(self.basket)} · Единиц товара: {quantity_sum}"
        if unpriced_count:
            count_text += f" · Без цены: {unpriced_count}"
        self.itemsCountLabel.setText(count_text)
        self.totalCaption.setText("Сумма по товарам с ценой:" if unpriced_count else "Итого:")
        self.totalValueLabel.setText(format_money(total_sum))
        self.cartTable.setColumnWidth(0, 88)
        self.cartTable.setColumnWidth(1, 270)
        self.cartTable.setColumnWidth(2, 130)
        self.cartTable.setColumnWidth(3, 120)
        self.cartTable.horizontalHeader().setStretchLastSection(True)
        self._updating_table = False

    def quantity_changed(self, item: QTableWidgetItem) -> None:
        if self._updating_table or item.column() != 3:
            return
        id_item = self.cartTable.item(item.row(), 0)
        product_id = id_item.data(Qt.ItemDataRole.UserRole) if id_item else None
        try:
            quantity = int(item.text().strip())
            if not 1 <= quantity <= 999:
                raise ValueError
        except ValueError:
            QMessageBox.warning(self, "Некорректное количество", "Введите целое число от 1 до 999.")
            self.refresh_table()
            return
        if product_id in self.basket:
            self.basket[product_id] = quantity
            self.refresh_table()
            self.on_change()

    def remove_selected(self) -> None:
        row = self.cartTable.currentRow()
        if row < 0:
            QMessageBox.information(self, "Удаление товара", "Сначала выберите строку в таблице корзины.")
            return
        id_item = self.cartTable.item(row, 0)
        product_id = id_item.data(Qt.ItemDataRole.UserRole) if id_item else None
        if product_id in self.basket:
            del self.basket[product_id]
            self.refresh_table()
            self.on_change()

    def export_csv(self) -> None:
        if not self.basket:
            QMessageBox.information(self, "Экспорт CSV", "Корзина пуста — экспортировать нечего.")
            return
        default_path = Path(__file__).resolve().parents[1] / "data" / "my_cart.csv"
        path, _ = QFileDialog.getSaveFileName(
            self, "Сохранить корзину", str(default_path), "CSV-файлы (*.csv)"
        )
        if not path:
            return
        if not path.lower().endswith(".csv"):
            path += ".csv"
        try:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", newline="", encoding="utf-8-sig") as file:
                writer = csv.DictWriter(
                    file,
                    fieldnames=["product_id", "name", "unit", "quantity", "unit_price"],
                    delimiter=";",
                )
                writer.writeheader()
                for product_id, quantity in self.basket.items():
                    product = self.products_by_id[product_id]
                    writer.writerow({
                        "product_id": product_id,
                        "name": product.name,
                        "unit": product.unit,
                        "quantity": quantity,
                        "unit_price": "" if product.minimum_price is None else product.minimum_price,
                    })
            QMessageBox.information(self, "Экспорт CSV", f"Корзина сохранена в файл:\n{path}")
        except OSError as error:
            QMessageBox.critical(self, "Ошибка экспорта", f"Не удалось записать CSV-файл:\n{error}")

    def import_csv(self) -> None:
        data_dir = Path(__file__).resolve().parents[1] / "data"
        path, _ = QFileDialog.getOpenFileName(
            self, "Импортировать корзину", str(data_dir), "CSV-файлы (*.csv)"
        )
        if not path:
            return
        try:
            imported: dict[str, int] = {}
            with open(path, "r", newline="", encoding="utf-8-sig") as file:
                sample = file.read(2048)
                file.seek(0)
                delimiter = ";" if sample.count(";") >= sample.count(",") else ","
                reader = csv.DictReader(file, delimiter=delimiter)
                if not reader.fieldnames:
                    raise ValueError("Файл пуст или в нём отсутствует строка заголовков.")
                headers = {header.strip().lower() for header in reader.fieldnames if header}
                if "quantity" not in headers or not (
                    {"product_id", "id"} & headers or {"name", "product_name"} & headers
                ):
                    raise ValueError(
                        "Неверный формат. Нужны столбцы product_id (или name) и quantity."
                    )
                for line_number, row in enumerate(reader, start=2):
                    normalized = {
                        (key or "").strip().lower(): (value or "").strip()
                        for key, value in row.items()
                    }
                    product_id = normalized.get("product_id") or normalized.get("id") or ""
                    product_name = normalized.get("name") or normalized.get("product_name") or ""
                    product = self.products_by_id.get(product_id)
                    if product is None and product_name:
                        product = next(
                            (p for p in self.products_by_id.values()
                             if p.name.casefold() == product_name.casefold()),
                            None,
                        )
                    if product is None:
                        raise ValueError(
                            f"Строка {line_number}: товар '{product_id or product_name}' не найден в каталоге."
                        )
                    try:
                        quantity = int(normalized.get("quantity", ""))
                    except ValueError as error:
                        raise ValueError(
                            f"Строка {line_number}: количество должно быть целым числом."
                        ) from error
                    if not 1 <= quantity <= 999:
                        raise ValueError(
                            f"Строка {line_number}: количество должно быть от 1 до 999."
                        )
                    imported[product.product_id] = imported.get(product.product_id, 0) + quantity

            if not imported:
                raise ValueError("В CSV-файле нет товарных строк для импорта.")
            for product_id, quantity in imported.items():
                self.basket[product_id] = min(999, self.basket.get(product_id, 0) + quantity)
            self.refresh_table()
            self.on_change()
            QMessageBox.information(
                self, "Импорт CSV", f"Загружено позиций: {len(imported)}. Корзина обновлена."
            )
        except (OSError, csv.Error, ValueError) as error:
            QMessageBox.critical(self, "Ошибка импорта", f"Не удалось импортировать файл:\n{error}")

    def open_comparison(self) -> None:
        """Переключает основное окно на страницу сравнения."""
        if self.on_compare is not None:
            self.on_compare()

    @staticmethod
    def _lock_item(item: QTableWidgetItem) -> None:
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)

    @classmethod
    def _item(cls, text: str, editable: bool = False, centered: bool = False) -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        if not editable:
            cls._lock_item(item)
        if centered:
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        else:
            item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        return item


# Совместимость со старыми импортами: CartWindow теперь является встроенной страницей.
CartWindow = CartPage
