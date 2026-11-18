import sys
import os
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6 import uic
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QLabel,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QTableWidgetItem,
    QTableWidget,
    QStackedWidget,
    QPushButton,
    QLineEdit,
    QComboBox,
    QMessageBox,
)


class PriceCompareApp(QMainWindow):
    """Главное окно приложения с четырьмя страницами."""

    def __init__(self):
        super().__init__()

        self.project_dir = Path(__file__).resolve().parent

        #cписок продуктов в корзину
        self.products = [
            {
                "name": "Молоко 2,5%",
                "brand": "Простоквашино",
                "price": 89.00,
                "shop": "Магнит",
                "category": "Молочные продукты",
                "image": "1.png"
            },
            {
                "name": "Хлеб белый",
                "brand": "Каравай",
                "price": 45.00,
                "shop": "Пятёрочка",
                "category": "Выпечка",
                "image": "2.png"
            },
            {
                "name": "Сочень",
                "brand": "Пятерочка",
                "price": 20.00,
                "shop": "Пятерочка",
                "category": "Выпечка",
                "image": "3.png"
            },
            {
                "name": "Куриное филе",
                "brand": "Петелинка",
                "price": 320.00,
                "shop": "Магнит",
                "category": "Мясо и птица",
                "image": "4.png"
            }
        ]



        # Загружаем главное окно, созданное в Qt Designer.
        home_file = self.project_dir / "main.ui"
        if not home_file.exists():
            raise FileNotFoundError(f"Не найден файл интерфейса: {home_file.name}")

        uic.loadUi(str(home_file), self)

        # Находим главный layout и layout содержимого главной страницы.
        main_layout = self.findChild(QVBoxLayout, "mainLayout")
        home_layout = self.findChild(QVBoxLayout, "homeLayout")

        if main_layout is None or home_layout is None:
            raise RuntimeError(
                "В main.ui не найдены layout'ы mainLayout и homeLayout. "
                "Проверьте objectName в Qt Designer."
            )

        # Создаём область переключения страниц.
        home_index = main_layout.indexOf(home_layout)
        if home_index < 0:
            raise RuntimeError("homeLayout должен находиться внутри mainLayout.")

        main_layout.takeAt(home_index)
        home_layout.setParent(None)

        home_page = QWidget()
        home_page.setObjectName("homePage")
        home_page.setLayout(home_layout)

        #cоздаем контейнер для страниц (перемещаения в приложении)
        self.pages = QStackedWidget()
        self.pages.setObjectName("pagesStack")
        self.pages.addWidget(home_page)

        # Загружаем остальные три страницы из Qt Designer.
        self.catalog_page = self.load_page("catalog.ui")
        self.cart_page = self.load_page("korzina.ui")
        self.map_page = self.load_page("map.ui")

        self.pages.addWidget(self.catalog_page)
        self.pages.addWidget(self.cart_page)
        self.pages.addWidget(self.map_page)
        self.load_catalog()
        self.load_cart()

        # Вставляем стек на место homeLayout.
        main_layout.insertWidget(home_index, self.pages, 1)

        # Кнопки нижней панели навигации из главного UI.
        self.btn_home = self.required_button("btnHome")
        self.btn_catalog = self.required_button("btnCatalog")
        self.btn_cart = self.required_button("btnCart")
        self.btn_map = self.required_button("btnMap")

        #создаем связь между нажатием кнопки и перемещением страниц
        self.btn_home.clicked.connect(lambda: self.show_page(0))
        self.btn_catalog.clicked.connect(lambda: self.show_page(1))
        self.btn_cart.clicked.connect(lambda: self.show_page(2))
        self.btn_map.clicked.connect(lambda: self.show_page(3))

        #переходы с кнопок главной страницы.
        self.connect_if_exists("homeCompareButton", lambda: self.show_page(2))

        #кнопка сравнения магазинов находится в корзине.
        compare_button = self.cart_page.findChild(
            QPushButton, "cartCompareButton"
        )
        if compare_button is not None:
            compare_button.clicked.connect(lambda: self.show_page(3))

        #категории на главной открывают каталог с выбранной категорией.
        category_buttons = {
            "catDairy": "Молочные продукты",
            "catMeat": "Мясо и птица",
            "catFruit": "Овощи и фрукты",
            "catBakery": "Выпечка",
            "catGrocery": "Бакалея",
            "catDrinks": "Напитки",
        }
        for object_name, category in category_buttons.items():
            button = self.findChild(QPushButton, object_name)
            if button is not None:
                button.clicked.connect(
                    lambda checked=False, value=category:
                    self.open_catalog(value)
                )

        #поиск на главной переносит запрос в поле поиска каталога.
        search_button = self.findChild(QPushButton, "btnSearch")
        if search_button is not None:
            search_button.clicked.connect(self.search_from_home)

        global_search = self.findChild(QLineEdit, "globalSearch")
        if global_search is not None:
            global_search.returnPressed.connect(self.search_from_home)

        #enter в поле каталога просто оставляет пользователя в каталоге.
        catalog_search = self.catalog_page.findChild(
            QLineEdit, "catalogSearch"
        )
        if catalog_search is not None:
            catalog_search.returnPressed.connect(lambda: self.show_page(1))

        self.show_page(0)

    def load_page(self, filename):
        #загружает .ui-файл как отдельную страницу.
        path = self.project_dir / filename
        if not path.exists():
            raise FileNotFoundError(
                f"Не найден файл {filename}. "
                "Положите его в одну папку с main.py."
            )
        page = uic.loadUi(str(path))
        return page

    def required_button(self, object_name):
        button = self.findChild(QPushButton, object_name)
        if button is None:
            raise RuntimeError(
                f"В main.ui не найдена кнопка с objectName='{object_name}'."
            )
        return button

    def connect_if_exists(self, object_name, callback):
        button = self.findChild(QPushButton, object_name)
        if button is not None:
            button.clicked.connect(callback)

    def show_page(self, index):
        #функция переключения страниц, подсвечивает активную кнопку меню.
        self.pages.setCurrentIndex(index)

        buttons = [
            self.btn_home,
            self.btn_catalog,
            self.btn_cart,
            self.btn_map,
        ]
        buttons[index].setChecked(True)

    def open_catalog(self, category=None):
        #открывает каталог; при необходимости выбирает категорию
        if category:
            category_filter = self.catalog_page.findChild(
                QComboBox, "categoryFilter"
            )
            if category_filter is not None:
                category_filter.setCurrentText(category)

        self.show_page(1)

    def search_from_home(self):
        #передаёт текст общего поиска в поле поиска каталога."""
        global_search = self.findChild(QLineEdit, "globalSearch")
        catalog_search = self.catalog_page.findChild(
            QLineEdit, "catalogSearch"
        )

        if global_search is not None and catalog_search is not None:
            catalog_search.setText(global_search.text().strip())

        self.show_page(1)


    def load_catalog(self):
        table = self.catalog_page.findChild(
            QTableWidget, "catalogTable"
        )

        table.setRowCount(0)

        for product in self.products:
            row = table.rowCount()
            table.insertRow(row)

            table.setItem(
                row, 0,
                QTableWidgetItem(product["name"])
            )

            table.setItem(
                row, 1,
                QTableWidgetItem(product["brand"])
            )

            table.setItem(
                row, 2,
                QTableWidgetItem(f'{product["price"]:.2f} ₽')
            )

            table.setItem(
                row, 3,
                QTableWidgetItem(product["shop"])
            )

            button = QPushButton("В корзину")
            table.setCellWidget(row, 4, button)

            button.clicked.connect(
                lambda checked=False, p=product:
                self.add_to_cart(p)
            )

    def load_catalog(self):
        table = self.catalog_page.findChild(
            QTableWidget, "catalogTable"
        )

        table.setRowCount(0)

        for product in self.products:
            row = table.rowCount()
            table.insertRow(row)
            table.setRowHeight(row, 120)

            table.setItem(
                row, 1,
                QTableWidgetItem(product["name"])
            )

            table.setItem(
                row, 2,
                QTableWidgetItem(product["brand"])
            )

            table.setItem(
                row, 3,
                QTableWidgetItem(f'{product["price"]:.2f} ₽')
            )

            table.setItem(
                row, 4,
                QTableWidgetItem(product["shop"])
            )



            # Получаем путь к фотографии
            image_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "images",
                product["image"]
            )

            # Создаём ячейку с фотографией
            image_label = QLabel()
            image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

            pixmap = QPixmap(image_path)

            if not pixmap.isNull():
                image_label.setPixmap(
                    pixmap.scaled(
                        70, 70,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    )
                )

            table.setCellWidget(row, 0, image_label)

            button = QPushButton("Добавить в корзину")
            button.setFixedSize(450, 50)
            table.setCellWidget(row, 5, button)

            button.clicked.connect(
                lambda checked=False, p=product:
                self.add_to_cart(p)
            )



    def load_cart(self):
        table = self.cart_page.findChild(
            QTableWidget, "cartTable"
        )

        table.setRowCount(0)

        for product in self.products:
            row = table.rowCount()
            table.insertRow(row)
            table.setRowHeight(row, 120)

            table.setItem(
                row, 1,
                QTableWidgetItem(product["name"])
            )

            table.setItem(
                row, 2,
                QTableWidgetItem(product["brand"])
            )

            table.setItem(
                row, 3,
                QTableWidgetItem(f'{product["price"]:.2f} ₽')
            )

            table.setItem(
                row, 4,
                QTableWidgetItem(f'1')
            )

            table.setItem(
                row, 5,
                QTableWidgetItem(product["shop"])
            )

            table.setItem(
                row, 6,
                QTableWidgetItem(f'{product["price"]:.2f} ₽')
            )

            image_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "images",
                product["image"]
            )

            image_label = QLabel()
            image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

            pixmap = QPixmap(image_path)

            if not pixmap.isNull():
                image_label.setPixmap(
                    pixmap.scaled(
                        70, 70,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    )
                )

            table.setCellWidget(row, 0, image_label)


def main():
    app = QApplication(sys.argv)

    try:
        window = PriceCompareApp()
    except Exception as error:
        QMessageBox.critical(
            None,
            "Ошибка запуска",
            f"Не удалось запустить приложение:\n{error}",
        )
        return 1

    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
