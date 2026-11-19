"""Главное окно приложения «Выгодно»."""
from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

from PyQt6 import uic
from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, QRectF, Qt, QSize, QUrl
from PyQt6.QtGui import (
    QColor,
    QFont,
    QIcon,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QFileDialog,
    QFrame,
    QGraphicsOpacityEffect,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QScrollArea,
    QSizePolicy,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from forms.budget_page import BudgetPage
from forms.cart_window import CartWindow
from forms.compare_window import CompareWindow
from forms.map_page import MapPage
from models.product import Product
from repositories.catalog_repository import CatalogImportError, CatalogRepository
from services.basket_optimizer import format_money


class GradientBrandLabel(QLabel):
    """Светлый градиентный логотип на тёмно-зелёной шапке."""

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        font = self.font()
        font.setPointSize(19)
        font.setBold(True)
        painter.setFont(font)
        rect = self.contentsRect()
        gradient = QLinearGradient(rect.left(), rect.top(), rect.right(), rect.top())
        gradient.setColorAt(0.0, QColor("#FFFFFF"))
        gradient.setColorAt(0.55, QColor("#E2EDE2"))
        gradient.setColorAt(1.0, QColor("#BBD0BE"))
        painter.setPen(QPen(gradient, 0))
        painter.drawText(rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self.text())
        painter.end()


def _nav_icon(kind: str, color: str) -> QIcon:
    """Рисует линейные иконки навигации без внешних изображений."""
    pixmap = QPixmap(28, 28)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(color), 1.9, Qt.PenStyle.SolidLine,
               Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)

    if kind == "catalog":
        painter.drawRoundedRect(QRectF(4.5, 4.5, 19, 19), 3, 3)
        painter.drawLine(8, 10, 20, 10)
        painter.drawLine(8, 14, 20, 14)
        painter.drawLine(8, 18, 16, 18)
    elif kind == "cart":
        painter.drawLine(3, 5, 6, 5)
        painter.drawLine(6, 5, 9, 18)
        painter.drawLine(9, 18, 21, 18)
        painter.drawLine(10, 9, 23, 9)
        painter.drawLine(23, 9, 21, 16)
        painter.drawEllipse(9, 21, 3, 3)
        painter.drawEllipse(18, 21, 3, 3)
    elif kind == "compare":
        painter.drawLine(4, 23, 24, 23)
        painter.drawRoundedRect(6, 13, 4, 10, 1, 1)
        painter.drawRoundedRect(12, 8, 4, 15, 1, 1)
        painter.drawRoundedRect(18, 4, 4, 19, 1, 1)
    elif kind == "map":
        path = QPainterPath()
        path.moveTo(14, 24)
        path.cubicTo(12, 21, 5, 14, 5, 10)
        path.cubicTo(5, 5, 9, 3, 14, 3)
        path.cubicTo(19, 3, 23, 5, 23, 10)
        path.cubicTo(23, 14, 16, 21, 14, 24)
        painter.drawPath(path)
        painter.drawEllipse(11, 7, 6, 6)
    elif kind == "budget":
        painter.drawEllipse(4, 4, 20, 20)
        painter.drawLine(9, 18, 13, 14)
        painter.drawLine(13, 14, 16, 16)
        painter.drawLine(16, 16, 21, 9)
        painter.drawLine(18, 9, 21, 9)
        painter.drawLine(21, 9, 21, 13)

    painter.end()
    return QIcon(pixmap)


def _placeholder_product_icon(category: str = "") -> QIcon:
    """Аккуратная заглушка, если фотография товара не указана или недоступна."""
    pixmap = QPixmap(56, 56)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#E4EEE4"))
    painter.drawRoundedRect(QRectF(2, 2, 52, 52), 11, 11)
    painter.setPen(QPen(QColor("#52735A"), 1.8))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawEllipse(QRectF(17, 12, 22, 22))
    painter.drawArc(13, 22, 30, 25, 20 * 16, 140 * 16)
    label = (category[:2].upper() if category else "")
    if label:
        font = QFont("Segoe UI", 7)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor("#34543D"))
        painter.drawText(QRectF(3, 38, 50, 12), Qt.AlignmentFlag.AlignCenter, label)
    painter.end()
    return QIcon(pixmap)


class MainWindow(QMainWindow):
    """Одно окно приложения; все страницы используют общий каталог и корзину."""

    NAV_ITEMS = (
        ("catalog", "Каталог", "catalog"),
        ("cart", "Корзина", "cart"),
        ("compare", "Сравнение", "compare"),
        ("map", "Карта", "map"),
        ("budget", "Подбор", "budget"),
    )
    ICON_IDLE = "#849489"
    ICON_ACTIVE = "#17452F"

    def __init__(self):
        super().__init__()
        ui_path = Path(__file__).with_name("main_window.ui")
        uic.loadUi(str(ui_path), self)
        self.setMinimumSize(1040, 720)

        old_brand = self.findChild(QLabel, "brandLabel")
        self.brandLabel = GradientBrandLabel("Выгодно", self.brandHeaderFrame)
        self.brandLabel.setObjectName("brandLabel")
        self.brandLabel.setMinimumSize(126, 40)
        if old_brand is not None:
            self.brandHeaderLayout.replaceWidget(old_brand, self.brandLabel)
            old_brand.deleteLater()

        self.repository = CatalogRepository()
        self.products: list[Product] = self.repository.get_products()
        self.products_by_id: dict[str, Product] = {
            product.product_id: product for product in self.products
        }
        self.basket: dict[str, int] = {}
        self._page_animations: list[QPropertyAnimation] = []
        self._icon_animations: list[QPropertyAnimation] = []
        self._image_manager = QNetworkAccessManager(self)
        self._image_cache: dict[str, QIcon] = {}
        self._pending_images: dict[str, QNetworkReply] = {}

        self.pageStack.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._populate_category_filter()
        self._configure_catalog_table()
        self._build_catalog_metrics()
        self._build_pages()
        self._build_bottom_navigation()
        self._connect_signals()
        self.statusLabel.setWordWrap(True)
        self.update_catalog()
        self.update_cart_summary()
        self.show_catalog(animate=False)

    def _populate_category_filter(self) -> None:
        self.categoryCombo.blockSignals(True)
        self.categoryCombo.clear()
        self.categoryCombo.addItem("Все категории")
        self.categoryCombo.addItems(self.repository.get_categories())
        self.categoryCombo.blockSignals(False)

    def _configure_catalog_table(self) -> None:
        table = self.productsTable
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setAlternatingRowColors(True)
        table.setShowGrid(False)
        table.setFrameShape(QFrame.Shape.NoFrame)
        table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(72)
        table.horizontalHeader().setMinimumSectionSize(84)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for column in (2, 3, 4, 5):
            table.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        table.setColumnWidth(0, 74)
        table.setIconSize(QSize(58, 58))
        table.setWordWrap(False)
        table.setSortingEnabled(False)

    def _build_catalog_metrics(self) -> None:
        """Добавляет компактную сводку каталога над поиском."""
        self.catalogStatsFrame = QFrame(self.mainArea)
        self.catalogStatsFrame.setObjectName("catalogStatsFrame")
        stats_layout = QHBoxLayout(self.catalogStatsFrame)
        stats_layout.setContentsMargins(0, 0, 0, 0)
        stats_layout.setSpacing(12)

        self.catalogMetricValues: dict[str, QLabel] = {}
        metrics = (
            ("products", "ТОВАРЫ В КАТАЛОГЕ", "0"),
            ("offers", "ЦЕНОВЫЕ ПРЕДЛОЖЕНИЯ", "0"),
            ("stores", "МАГАЗИНЫ В ДАННЫХ", "0"),
        )
        for key, caption, initial_value in metrics:
            card = QFrame(self.catalogStatsFrame)
            card.setObjectName("catalogStatCard")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(16, 11, 16, 12)
            card_layout.setSpacing(3)

            caption_label = QLabel(caption, card)
            caption_label.setObjectName("catalogStatCaption")
            value_label = QLabel(initial_value, card)
            value_label.setObjectName("catalogStatValue")
            value_label.setMinimumHeight(28)
            card_layout.addWidget(caption_label)
            card_layout.addWidget(value_label)
            stats_layout.addWidget(card, 1)
            self.catalogMetricValues[key] = value_label

        self.mainLayout.insertWidget(1, self.catalogStatsFrame)
        self._update_catalog_metrics()

    def _update_catalog_metrics(self) -> None:
        if not hasattr(self, "catalogMetricValues"):
            return
        offer_count = sum(len(product.offers) for product in self.products)
        stores = {offer.store for product in self.products for offer in product.offers}
        self.catalogMetricValues["products"].setText(str(len(self.products)))
        self.catalogMetricValues["offers"].setText(str(offer_count))
        self.catalogMetricValues["stores"].setText(str(len(stores)))

    def _build_pages(self) -> None:
        self.cartPage = CartWindow(
            self.basket, self.products_by_id, self.update_cart_summary,
            on_compare=self.show_compare, parent=self.pageStack,
        )
        self.comparePage = CompareWindow(
            self.basket, self.products_by_id, on_back=self.show_catalog, parent=self.pageStack,
        )
        self.mapPage = MapPage(parent=self.pageStack)

        self.budgetScrollArea = QScrollArea(self.pageStack)
        self.budgetScrollArea.setObjectName("budgetScrollArea")
        self.budgetScrollArea.setWidgetResizable(True)
        self.budgetScrollArea.setFrameShape(QFrame.Shape.NoFrame)
        self.budgetScrollArea.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.budgetPage = BudgetPage(
            parent=self.budgetScrollArea,
            repository=self.repository,
            shared_basket=self.basket,
            on_basket_changed=self.update_cart_summary,
        )
        self.budgetPage.setMinimumHeight(740)
        self.budgetScrollArea.setWidget(self.budgetPage)

        self.pages = {
            "catalog": self.mainArea,
            "cart": self.cartPage,
            "compare": self.comparePage,
            "map": self.mapPage,
            "budget": self.budgetScrollArea,
        }
        self.pageStack.addWidget(self.cartPage)
        self.pageStack.addWidget(self.comparePage)
        self.pageStack.addWidget(self.mapPage)
        self.pageStack.addWidget(self.budgetScrollArea)

    def _build_bottom_navigation(self) -> None:
        self.navGroup = QButtonGroup(self)
        self.bottomNavLayout.addStretch(1)
        self.navGroup.setExclusive(True)
        self.navButtons: dict[str, QToolButton] = {}
        for key, title, icon_name in self.NAV_ITEMS:
            button = QToolButton(self.bottomNavFrame)
            button.setObjectName(f"nav_{key}")
            button.setText(title)
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            button.setIconSize(QSize(21, 21))
            button.setMinimumSize(104, 62)
            button.setMaximumHeight(64)
            button.setCheckable(True)
            button.setAutoRaise(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setIcon(_nav_icon(icon_name, self.ICON_IDLE))
            button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            self.bottomNavLayout.addWidget(button)
            self.navGroup.addButton(button)
            self.navButtons[key] = button
            button.clicked.connect(lambda checked=False, page_key=key: self.show_page(page_key))
            button.toggled.connect(
                lambda checked, b=button, icon=icon_name: b.setIcon(
                    _nav_icon(icon, self.ICON_ACTIVE if checked else self.ICON_IDLE)
                )
            )
        self.bottomNavLayout.addStretch(1)
        self.bottomNavFrame.setFixedHeight(80)

    def _connect_signals(self) -> None:
        self.searchEdit.textChanged.connect(self.update_catalog)
        self.categoryCombo.currentTextChanged.connect(self.update_catalog)
        self.resetSearchButton.clicked.connect(self.reset_search)
        self.importCatalogButton.clicked.connect(self.import_catalog)
        self.addToCartButton.clicked.connect(self.add_selected_to_cart)
        self.openCartButton.clicked.connect(self.show_cart)
        self.compareButton.clicked.connect(self.show_compare)

    def show_page(self, key: str, animate: bool = True) -> None:
        if key not in self.pages:
            return
        widget = self.pages[key]
        if self.pageStack.currentWidget() is widget:
            self.navButtons[key].setChecked(True)
            return

        self.pageStack.setCurrentWidget(widget)
        self.navButtons[key].setChecked(True)
        if key == "cart":
            self.cartPage.refresh_table()
        elif key == "compare":
            self.comparePage.fill_comparison()
        elif key == "budget":
            self.budgetPage.refresh_from_shared_basket()
        elif key == "map":
            self.mapPage.ensure_loaded()

        page_title = dict((item_key, title) for item_key, title, _ in self.NAV_ITEMS)[key]
        self.setWindowTitle(f"Выгодно — {page_title.lower()}")
        if animate:
            self._fade_in(widget)
            self._animate_nav_button(self.navButtons[key])

    def _fade_in(self, widget: QWidget) -> None:
        if widget.graphicsEffect() is not None:
            widget.setGraphicsEffect(None)
        effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)
        animation = QPropertyAnimation(effect, b"opacity", self)
        animation.setDuration(170)
        animation.setStartValue(0.68)
        animation.setEndValue(1.0)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        animation.finished.connect(lambda w=widget: w.setGraphicsEffect(None))
        animation.finished.connect(animation.deleteLater)
        self._page_animations.append(animation)
        animation.finished.connect(
            lambda a=animation: self._page_animations.remove(a)
            if a in self._page_animations else None
        )
        animation.start()

    def _animate_nav_button(self, button: QToolButton) -> None:
        animation = QPropertyAnimation(button, b"iconSize", self)
        animation.setDuration(190)
        animation.setKeyValueAt(0.0, QSize(21, 21))
        animation.setKeyValueAt(0.45, QSize(24, 24))
        animation.setKeyValueAt(1.0, QSize(21, 21))
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        animation.finished.connect(
            lambda a=animation: self._icon_animations.remove(a)
            if a in self._icon_animations else None
        )
        animation.finished.connect(animation.deleteLater)
        self._icon_animations.append(animation)
        animation.start()

    def show_catalog(self, animate: bool = True) -> None:
        self.show_page("catalog", animate=animate)

    def show_cart(self) -> None:
        self.show_page("cart")

    def show_compare(self) -> None:
        self.show_page("compare")

    def show_map(self) -> None:
        self.show_page("map")

    def show_budget(self) -> None:
        self.show_page("budget")

    def update_catalog(self, *_args) -> None:
        query = self.searchEdit.text().strip().casefold()
        category = self.categoryCombo.currentText()
        visible = [
            product for product in self.products
            if (query in product.name.casefold() or query in product.category.casefold())
            and (category == "Все категории" or product.category == category)
        ]

        table = self.productsTable
        table.setRowCount(0)
        table.setRowCount(len(visible))
        for row, product in enumerate(visible):
            image_item = self._table_item("")
            image_item.setData(Qt.ItemDataRole.UserRole, product.product_id)
            cached_icon = self._image_cache.get(product.product_id)
            image_item.setIcon(cached_icon or _placeholder_product_icon(product.category))
            image_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(row, 0, image_item)

            best_offer = min(
                product.offers,
                key=lambda offer: (offer.unit_price, offer.store.casefold()),
                default=None,
            )
            values = [
                product.name,
                product.category,
                product.unit,
                format_money(best_offer.unit_price) if best_offer else "Нет цены",
                best_offer.store if best_offer else "—",
            ]
            for column, value in enumerate(values, start=1):
                item = self._table_item(value)
                if column in (4, 5):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if column == 1:
                    name_font = item.font()
                    name_font.setBold(True)
                    item.setFont(name_font)
                    item.setForeground(QColor("#263D2E"))
                elif column == 2:
                    item.setForeground(QColor("#788579"))
                elif column == 3:
                    item.setForeground(QColor("#667568"))
                elif column == 4:
                    price_font = item.font()
                    price_font.setBold(True)
                    item.setFont(price_font)
                    item.setForeground(QColor("#1B6540" if best_offer else "#879187"))
                    if best_offer:
                        item.setBackground(QColor("#EEF5EC"))
                elif column == 5:
                    item.setForeground(QColor("#536B57" if best_offer else "#929B91"))
                table.setItem(row, column, item)
            self._load_product_image(product)

        has_products = bool(self.products)
        self._update_catalog_metrics()
        self.emptyCatalogLabel.setVisible(not has_products)
        table.setVisible(has_products)
        self.addToCartButton.setEnabled(has_products and bool(visible))
        self.compareButton.setEnabled(has_products)
        if not has_products:
            if self.repository.last_error:
                self.statusLabel.setText(
                    "Не удалось прочитать сохранённый каталог: " + self.repository.last_error
                    + " Нажмите «Загрузить каталог CSV», чтобы выбрать другой файл."
                )
            else:
                self.statusLabel.setText(
                    "Каталог пока пуст. Нажмите «Загрузить каталог CSV», чтобы добавить товары и цены магазинов."
                )
        else:
            priced_count = sum(bool(product.offers) for product in self.products)
            self.statusLabel.setText(
                f"Показано {len(visible)} из {len(self.products)} товаров · "
                f"цены есть у {priced_count} из {len(self.products)}."
            )

    def _load_product_image(self, product: Product) -> None:
        source = product.image_source
        if not source or product.product_id in self._image_cache or product.product_id in self._pending_images:
            return

        parsed = urlparse(source)
        if parsed.scheme in {"http", "https"} and parsed.netloc:
            request = QNetworkRequest(QUrl(source))
            request.setRawHeader(b"User-Agent", b"Vygodno/1.0")
            reply = self._image_manager.get(request)
            self._pending_images[product.product_id] = reply
            reply.finished.connect(
                lambda product_id=product.product_id, network_reply=reply:
                self._on_image_received(product_id, network_reply)
            )
            return

        image = QPixmap(source)
        if not image.isNull():
            self._store_product_image(product.product_id, image)

    def _on_image_received(self, product_id: str, reply: QNetworkReply) -> None:
        if self._pending_images.get(product_id) is reply:
            self._pending_images.pop(product_id, None)
        if reply.error() == QNetworkReply.NetworkError.NoError:
            image = QPixmap()
            image.loadFromData(bytes(reply.readAll()))
            if not image.isNull():
                self._store_product_image(product_id, image)
        reply.deleteLater()

    def _store_product_image(self, product_id: str, image: QPixmap) -> None:
        scaled = image.scaled(
            QSize(52, 52), Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        icon = QIcon(scaled)
        self._image_cache[product_id] = icon
        for row in range(self.productsTable.rowCount()):
            item = self.productsTable.item(row, 0)
            if item is not None and item.data(Qt.ItemDataRole.UserRole) == product_id:
                item.setIcon(icon)
                break

    def import_catalog(self) -> None:
        start_dir = str(self.repository.data_path.parent)
        path, _ = QFileDialog.getOpenFileName(
            self, "Загрузить каталог товаров", start_dir,
            "CSV-файлы (*.csv);;Все файлы (*.*)",
        )
        if not path:
            return
        try:
            products = self.repository.import_file(path, persist=True)
        except (OSError, CatalogImportError) as error:
            QMessageBox.critical(self, "Не удалось загрузить каталог", str(error))
            return

        self._replace_catalog(products)
        offer_count = sum(len(product.offers) for product in products)
        QMessageBox.information(
            self, "Каталог загружен",
            f"Товаров: {len(products)}\nЦеновых предложений: {offer_count}\n\n"
            f"Каталог сохранён в:\n{self.repository.data_path}",
        )

    def _replace_catalog(self, products: list[Product]) -> None:
        valid_ids = {product.product_id for product in products}
        removed_from_basket = [product_id for product_id in self.basket if product_id not in valid_ids]
        for product_id in removed_from_basket:
            self.basket.pop(product_id, None)

        self.products = products
        self.products_by_id.clear()
        self.products_by_id.update({product.product_id: product for product in products})
        self._image_cache.clear()
        for reply in self._pending_images.values():
            reply.abort()
        self._pending_images.clear()

        self._populate_category_filter()
        self.searchEdit.clear()

        self.budgetPage.update_products(products)
        self.update_catalog()
        self.update_cart_summary()
        if removed_from_basket:
            self.statusLabel.setText(
                f"Каталог обновлён. Удалено позиций корзины, отсутствующих в новом каталоге: {len(removed_from_basket)}."
            )

    def reset_search(self) -> None:
        self.searchEdit.clear()
        self.categoryCombo.setCurrentIndex(0)

    def add_selected_to_cart(self) -> None:
        row = self.productsTable.currentRow()
        if row < 0:
            QMessageBox.information(self, "Добавление товара", "Выберите товар в каталоге.")
            return
        item = self.productsTable.item(row, 0)
        product_id = item.data(Qt.ItemDataRole.UserRole) if item else None
        if product_id not in self.products_by_id:
            QMessageBox.warning(self, "Добавление товара", "Не удалось определить выбранный товар.")
            return
        self.basket[product_id] = min(999, self.basket.get(product_id, 0) + 1)
        product = self.products_by_id[product_id]
        self.statusLabel.setText(f"Добавлено: {product.name}. В корзине позиций: {len(self.basket)}.")
        self.update_cart_summary()

    def update_cart_summary(self) -> None:
        if hasattr(self, "cartPage"):
            self.cartPage.refresh_table()
        if hasattr(self, "budgetPage"):
            self.budgetPage.refresh_from_shared_basket()

    @staticmethod
    def _table_item(text: str) -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        return item
