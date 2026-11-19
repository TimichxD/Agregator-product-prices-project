"""Загрузка и хранение каталога из CSV без встроенных фиктивных записей."""

from __future__ import annotations

import csv
import hashlib
import io
import os
import shutil
import tempfile
from collections import OrderedDict
from pathlib import Path, PureWindowsPath
from urllib.parse import urlparse

from models.product import Offer, Product


REQUIRED_COLUMNS = {"product_id", "name", "unit", "category"}


class CatalogImportError(ValueError):
    """Ошибка структуры или содержимого импортируемого каталога."""


class CatalogRepository:
    """Читает каталог из data/products.csv. При отсутствии файла каталог пуст."""

    def __init__(self, data_path: str | Path | None = None):
        project_root = Path(__file__).resolve().parents[1]
        self.data_path = Path(data_path) if data_path else project_root / "data" / "products.csv"
        self._products: list[Product] = []
        self.last_error: str | None = None
        try:
            self.load()
        except CatalogImportError as error:
            self._products = []
            self.last_error = str(error)

    def get_products(self) -> list[Product]:
        return list(self._products)

    def get_stores(self) -> list[str]:
        return sorted(
            {offer.store for product in self._products for offer in product.offers},
            key=str.casefold,
        )

    def get_categories(self) -> list[str]:
        return sorted({p.category for p in self._products if p.category}, key=str.casefold)

    def load(self) -> list[Product]:
        if not self.data_path.is_file():
            self._products = []
            return []
        self._products = self.read_csv(self.data_path)
        self.last_error = None
        return self.get_products()

    def import_file(self, source_path: str | Path, persist: bool = True) -> list[Product]:
        source = Path(source_path).expanduser().resolve()
        products = self.read_csv(source)
        if persist:
            self._persist_products(products)
            products = self.read_csv(self.data_path)
        self._products = products
        self.last_error = None
        return self.get_products()

    def _persist_products(self, products: list[Product]) -> None:
        """Сохраняет нормализованный CSV и переносит локальные фото в data/images."""
        self.data_path.parent.mkdir(parents=True, exist_ok=True)
        image_folder = self.data_path.parent / "images"
        normalized_rows: list[dict[str, str]] = []

        for product in products:
            image_value = product.image_source or ""
            if image_value and urlparse(image_value).scheme not in {"http", "https"}:
                source_image = Path(image_value)
                if not source_image.is_file():
                    raise CatalogImportError(
                        f"Не найден файл изображения для товара «{product.name}»: {source_image}"
                    )
                image_folder.mkdir(parents=True, exist_ok=True)
                if source_image.parent.resolve() == image_folder.resolve():
                    # Повторный импорт уже сохранённого каталога не создаёт новые копии фото.
                    destination_name = source_image.name
                else:
                    digest = hashlib.sha256(str(source_image.resolve()).encode("utf-8")).hexdigest()[:12]
                    destination_name = f"{digest}_{source_image.name}"
                    destination_image = image_folder / destination_name
                    if source_image.resolve() != destination_image.resolve():
                        shutil.copy2(source_image, destination_image)
                image_value = f"images/{destination_name}"

            common = {
                "product_id": product.product_id,
                "name": product.name,
                "unit": product.unit,
                "category": product.category,
                "image": image_value,
            }
            if product.offers:
                for offer in product.offers:
                    normalized_rows.append({
                        **common,
                        "store": offer.store,
                        "price": f"{offer.unit_price:.2f}".replace(".", ","),
                    })
            else:
                normalized_rows.append({**common, "store": "", "price": ""})

        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", newline="", encoding="utf-8-sig",
                dir=self.data_path.parent, suffix=".tmp", delete=False,
            ) as file:
                temporary_path = Path(file.name)
                writer = csv.DictWriter(
                    file,
                    fieldnames=["product_id", "name", "unit", "category", "store", "price", "image"],
                    delimiter=";",
                )
                writer.writeheader()
                writer.writerows(normalized_rows)
            os.replace(temporary_path, self.data_path)
        except OSError:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
            raise

    @staticmethod
    def read_csv(path: str | Path) -> list[Product]:
        csv_path = Path(path).expanduser().resolve()
        if not csv_path.is_file():
            raise CatalogImportError(f"Файл не найден: {csv_path}")

        try:
            try:
                content = csv_path.read_text(encoding="utf-8-sig")
            except UnicodeDecodeError:
                content = csv_path.read_text(encoding="cp1251")
        except OSError as error:
            raise CatalogImportError(f"Не удалось прочитать файл: {error}") from error

        if not content.strip():
            raise CatalogImportError("CSV-файл пуст. Добавьте строку заголовков и данные товаров.")

        try:
            delimiter = csv.Sniffer().sniff(content[:4096], delimiters=";,\t").delimiter
        except csv.Error:
            delimiter = ";"

        reader = csv.DictReader(io.StringIO(content, newline=""), delimiter=delimiter)
        if not reader.fieldnames:
            raise CatalogImportError("В CSV-файле отсутствует строка заголовков.")

        headers = {
            (header or "").strip().lower(): header
            for header in reader.fieldnames
            if header and header.strip()
        }
        if "image" not in headers:
            image_alias = headers.get("image_url") or headers.get("image_path")
            if image_alias:
                headers["image"] = image_alias

        missing_headers = REQUIRED_COLUMNS - set(headers)
        if missing_headers:
            missing = ", ".join(sorted(missing_headers))
            raise CatalogImportError(
                "Не хватает обязательных столбцов: " + missing + ". Используйте шаблон каталога."
            )

        grouped: OrderedDict[str, dict] = OrderedDict()
        for line_number, row in enumerate(reader, start=2):
            normalized = {
                key: (row.get(original) or "").strip()
                for key, original in headers.items()
            }
            product_id = normalized.get("product_id", "")
            name = normalized.get("name", "")
            unit = normalized.get("unit", "")
            category = normalized.get("category", "")

            if not any(normalized.values()):
                continue
            if not all((product_id, name, unit, category)):
                raise CatalogImportError(
                    f"Строка {line_number}: заполните product_id, name, unit и category."
                )

            image_source = CatalogRepository._resolve_image(
                normalized.get("image", ""), csv_path.parent, line_number, product_id
            )
            entry = grouped.get(product_id)
            if entry is None:
                entry = {
                    "name": name,
                    "unit": unit,
                    "category": category,
                    "image_source": image_source,
                    "offers": OrderedDict(),
                }
                grouped[product_id] = entry
            else:
                if (entry["name"], entry["unit"], entry["category"]) != (name, unit, category):
                    raise CatalogImportError(
                        f"Строка {line_number}: у товара {product_id} отличаются название, фасовка или категория."
                    )
                if not entry["image_source"] and image_source:
                    entry["image_source"] = image_source

            store = normalized.get("store", "")
            price_text = normalized.get("price", "")
            if bool(store) != bool(price_text):
                raise CatalogImportError(
                    f"Строка {line_number}: поля store и price нужно заполнить вместе."
                )
            if store and price_text:
                price = CatalogRepository._parse_price(price_text, line_number)
                if store in entry["offers"]:
                    raise CatalogImportError(
                        f"Строка {line_number}: для товара {product_id} магазин {store} указан повторно."
                    )
                entry["offers"][store] = Offer(store=store, unit_price=price)

        products = [
            Product(
                product_id=product_id,
                name=entry["name"],
                unit=entry["unit"],
                category=entry["category"],
                offers=tuple(entry["offers"].values()),
                image_source=entry["image_source"],
            )
            for product_id, entry in grouped.items()
        ]
        if not products:
            raise CatalogImportError("В CSV-файле нет строк с товарами.")
        return products

    @staticmethod
    def _parse_price(value: str, line_number: int) -> float:
        normalized = value.replace("\u00a0", "").replace(" ", "").replace("₽", "")
        if "," in normalized and "." in normalized:
            if normalized.rfind(",") > normalized.rfind("."):
                normalized = normalized.replace(".", "").replace(",", ".")
            else:
                normalized = normalized.replace(",", "")
        else:
            normalized = normalized.replace(",", ".")
        try:
            price = float(normalized)
        except ValueError as error:
            raise CatalogImportError(f"Строка {line_number}: цена должна быть числом.") from error
        if price <= 0:
            raise CatalogImportError(f"Строка {line_number}: цена должна быть больше нуля.")
        return price

    @staticmethod
    def _resolve_image(
        value: str, csv_folder: Path, line_number: int, product_id: str
    ) -> str | None:
        if not value:
            image_folder = csv_folder / "images"
            for extension in (".jpg", ".jpeg", ".png", ".bmp"):
                candidate = image_folder / f"{product_id}{extension}"
                if candidate.is_file():
                    return str(candidate.resolve())
            return None
        parsed = urlparse(value)
        if parsed.scheme in {"http", "https"} and parsed.netloc:
            return value
        windows_path = PureWindowsPath(value)
        if windows_path.drive or Path(value).is_absolute():
            return value
        if parsed.scheme:
            raise CatalogImportError(
                f"Строка {line_number}: для изображения допустимы только http/https или путь к файлу."
            )
        return str((csv_folder / Path(value).expanduser()).resolve())
