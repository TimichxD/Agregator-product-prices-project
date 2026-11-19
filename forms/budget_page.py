"""Контроллер страницы «Подбор корзины»."""

from pathlib import Path
from collections.abc import Callable

from PyQt6 import uic
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QGridLayout,
    QDialog,
    QHeaderView,
    QMessageBox,
    QTableWidgetItem,
    QWidget,
)

from forms.add_product_dialog import AddProductDialog
from models.product import Product
from repositories.catalog_repository import CatalogRepository
from services.basket_optimizer import BasketOptimizer, OptimizationResult, format_money


class BudgetPage(QWidget):
    """Страница, которую можно добавить в центральный QStackedWidget приложения."""

    def __init__(
        self,
        parent=None,
        repository: CatalogRepository | None = None,
        shared_basket: dict[str, int] | None = None,
        on_basket_changed: Callable[[], None] | None = None,
    ):
        super().__init__(parent)
        ui_path = Path(__file__).with_name("budget_page.ui")
        uic.loadUi(str(ui_path), self)

        self.repository = repository or CatalogRepository()
        self.products: list[Product] = self.repository.get_products()
        self.products_by_id = {product.product_id: product for product in self.products}
        self.optimizer = BasketOptimizer(self.products)
        # The page receives the same dictionary that catalog and cart use.
        self.basket: dict[str, int] = shared_basket if shared_basket is not None else {}
        self.on_basket_changed = on_basket_changed
        self._updating_basket_table = False
        self.last_result: OptimizationResult | None = None

        # Явно задаём идентификаторы режимов в UserRole, а не связываемся с текстом пункта.
        for index, percent in enumerate((2, 4, 6, 8, 10)):
            self.allowanceComboBox.setItemData(index, percent)
        self.allowanceComboBox.setCurrentIndex(4)

        self.modeComboBox.setItemData(0, "hybrid")
        self.modeComboBox.setItemData(1, "single_store")
        self.modeComboBox.setItemData(2, "within_budget")

        self._configure_page_layout()
        self._configure_tables()
        self._connect_signals()
        self._update_budget_limit()
        self._update_basket_summary()
        self.addProductButton.setEnabled(bool(self.products))
        self.runButton.setEnabled(bool(self.products) and bool(self.basket))

    def update_products(self, products: list[Product]) -> None:
        """Обновляет каталог после импорта CSV из главного окна."""
        self.products = list(products)
        self.products_by_id = {product.product_id: product for product in self.products}
        self.optimizer = BasketOptimizer(self.products)
        self._refresh_basket_table()
        self._clear_previous_result()
        self.addProductButton.setEnabled(bool(self.products))
        self.runButton.setEnabled(bool(self.products) and bool(self.basket))

    def _configure_page_layout(self) -> None:
        """Keep captions, fields and helper text readable at common window sizes."""
        self.setMinimumWidth(820)
        root_layout = self.layout()
        if root_layout is not None:
            root_layout.setContentsMargins(26, 22, 26, 22)
            root_layout.setSpacing(14)
        settings_layout = self.settingsFrame.layout()
        if isinstance(settings_layout, QGridLayout):
            settings_layout.setColumnStretch(0, 1)
            settings_layout.setColumnStretch(1, 1)
            settings_layout.setColumnStretch(2, 2)
        self.pageTitleLabel.setMinimumHeight(44)
        self.basketTitleLabel.setMinimumHeight(30)
        self.resultHeadingLabel.setMinimumHeight(30)
        self.pageSubtitleLabel.setWordWrap(True)
        self.basketHintLabel.setWordWrap(True)
        self.resultStatusLabel.setWordWrap(True)
        self.routeNoteTextLabel.setWordWrap(True)

    def _configure_tables(self) -> None:
        for table in (self.basketTable, self.resultTable):
            table.setAlternatingRowColors(True)
            table.setShowGrid(False)
            table.verticalHeader().setVisible(False)
            table.horizontalHeader().setMinimumSectionSize(90)
            table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
            table.horizontalHeader().setStretchLastSection(True)
            table.verticalHeader().setDefaultSectionSize(44)
            table.setWordWrap(False)
            table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
            table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.basketTable.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
        )
        self.resultTable.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.basketTable.setColumnWidth(0, 270)
        self.basketTable.setColumnWidth(1, 115)
        self.basketTable.setColumnWidth(2, 115)
        self.basketTable.setColumnWidth(3, 155)
        self.resultTable.setColumnWidth(0, 250)
        self.resultTable.setColumnWidth(1, 110)
        self.resultTable.setColumnWidth(2, 180)
        self.resultTable.setColumnWidth(3, 130)

    def _connect_signals(self) -> None:
        self.addProductButton.clicked.connect(self.add_product)
        self.removeProductButton.clicked.connect(self.remove_selected_product)
        self.runButton.clicked.connect(self.run_optimization)
        self.budgetSpinBox.valueChanged.connect(self._update_budget_limit)
        self.allowanceComboBox.currentIndexChanged.connect(self._update_budget_limit)
        self.basketTable.itemChanged.connect(self._basket_cell_changed)

    def _update_budget_limit(self, *_args) -> None:
        budget = self.budgetSpinBox.value()
        allowance = int(self.allowanceComboBox.currentData() or 10)
        maximum = budget * (1 + allowance / 100)
        self.maximumBudgetLabel.setText(f"Максимальная сумма с запасом: {format_money(maximum)}")

    def add_product(self) -> None:
        dialog = AddProductDialog(self.products, self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.selected_product is not None:
            product_id = dialog.selected_product.product_id
            current = self.basket.get(product_id, 0)
            requested = dialog.quantity
            if current + requested > 999:
                QMessageBox.warning(self, "Количество", "Для одной позиции нельзя указать больше 999 единиц.")
                return
            self.basket[product_id] = current + requested
            self._basket_was_changed()

    def remove_selected_product(self) -> None:
        row = self.basketTable.currentRow()
        if row < 0:
            QMessageBox.information(self, "Удаление товара", "Сначала выберите товар в таблице.")
            return
        item = self.basketTable.item(row, 0)
        if item is None:
            return
        product_id = item.data(Qt.ItemDataRole.UserRole)
        self.basket.pop(product_id, None)
        self._basket_was_changed()

    def _basket_was_changed(self) -> None:
        """Refresh this page and notify the main window about shared basket changes."""
        self._refresh_basket_table()
        self._clear_previous_result()
        self.runButton.setEnabled(bool(self.products) and bool(self.basket))
        if self.on_basket_changed is not None:
            self.on_basket_changed()

    def refresh_from_shared_basket(self) -> None:
        """Refresh the view after the basket was changed on another page."""
        self._refresh_basket_table()
        self._clear_previous_result()
        self.runButton.setEnabled(bool(self.products) and bool(self.basket))

    def _refresh_basket_table(self) -> None:
        self._updating_basket_table = True
        self.basketTable.setRowCount(0)
        for product_id, quantity in self.basket.items():
            product = self.products_by_id.get(product_id)
            if product is None:
                continue
            row = self.basketTable.rowCount()
            self.basketTable.insertRow(row)

            name_item = self._table_item(product.name)
            name_item.setData(Qt.ItemDataRole.UserRole, product_id)
            self.basketTable.setItem(row, 0, name_item)
            self.basketTable.setItem(row, 1, self._table_item(product.unit))

            quantity_item = self._table_item(str(quantity), editable=True, centered=True)
            quantity_item.setData(Qt.ItemDataRole.UserRole, product_id)
            self.basketTable.setItem(row, 2, quantity_item)

            best_price = product.minimum_price
            price_text = format_money(best_price) if best_price is not None else "Нет предложений"
            self.basketTable.setItem(row, 3, self._table_item(price_text, centered=True))
            line_total = best_price * quantity if best_price is not None else None
            total_text = format_money(line_total) if line_total is not None else "—"
            self.basketTable.setItem(row, 4, self._table_item(total_text, centered=True))
        self._updating_basket_table = False
        self._update_basket_summary()

    def _basket_cell_changed(self, item: QTableWidgetItem) -> None:
        if self._updating_basket_table or item.column() != 2:
            return
        product_id = item.data(Qt.ItemDataRole.UserRole)
        try:
            quantity = int(item.text().strip())
            if not 1 <= quantity <= 999:
                raise ValueError
        except (TypeError, ValueError):
            QMessageBox.warning(self, "Количество", "Введите целое число от 1 до 999.")
            self._refresh_basket_table()
            return
        if product_id not in self.basket:
            return
        self.basket[product_id] = quantity
        self._basket_was_changed()

    def _update_basket_summary(self) -> None:
        if not self.basket:
            if not self.products:
                self.basketHintLabel.setText("Сначала загрузите каталог товаров и ценовых предложений.")
            else:
                self.basketHintLabel.setText("Список пока пуст. Добавьте товары из каталога, затем запустите подбор.")
            return
        count = len(self.basket)
        units = sum(self.basket.values())
        self.basketHintLabel.setText(
            f"Позиций: {count} · Всего единиц: {units}. "
            "Количество можно изменить двойным нажатием на ячейку."
        )

    def _clear_previous_result(self) -> None:
        self.last_result = None
        self.resultTable.setRowCount(0)
        self.resultTotalLabel.setText("— ₽")
        self.resultStatusLabel.setText("Состав корзины изменён. Запустите подбор, чтобы пересчитать результат.")
        self.runButton.setEnabled(bool(self.products) and bool(self.basket))

    def run_optimization(self) -> None:
        mode = self.modeComboBox.currentData()
        if not mode:
            mode = "hybrid"
        try:
            result = self.optimizer.optimize(
                basket=self.basket,
                mode=mode,
                budget=self.budgetSpinBox.value(),
                allowance_percent=int(self.allowanceComboBox.currentData() or 10),
            )
        except ValueError as error:
            QMessageBox.warning(self, "Не удалось выполнить подбор", str(error))
            return
        self.last_result = result
        self._show_result(result)

    def _show_result(self, result: OptimizationResult) -> None:
        self.resultTable.setRowCount(0)
        for line in result.lines:
            row = self.resultTable.rowCount()
            self.resultTable.insertRow(row)
            values = (
                line.product.name,
                str(line.quantity),
                line.offer.store,
                format_money(line.offer.unit_price),
                format_money(line.line_total),
            )
            for column, value in enumerate(values):
                self.resultTable.setItem(row, column, self._table_item(value, centered=column != 0))

        self.resultTotalLabel.setText(format_money(result.total))
        details = result.message
        if result.store_totals:
            store_parts = [f"{store}: {format_money(total)}" for store, total in result.store_totals.items()]
            details += " Распределение: " + "; ".join(store_parts) + "."
        if result.missing_products:
            details += " Не найдены: " + ", ".join(result.missing_products) + "."
        if result.mode == "within_budget":
            details += (
                f" Бюджет: {format_money(result.budget)}; "
                f"лимит с допуском: {format_money(result.budget_limit)}."
            )
        self.resultStatusLabel.setText(details)

    @staticmethod
    def _table_item(text: str, editable: bool = False, centered: bool = False) -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        if not editable:
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        if centered:
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        else:
            item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        return item
