"""Проверки импорта CSV и хранения фотографий."""

import tempfile
import unittest
from pathlib import Path

from repositories.catalog_repository import CatalogImportError, CatalogRepository


class CatalogRepositoryTests(unittest.TestCase):
    def test_repository_starts_empty_without_catalog_file(self):
        with tempfile.TemporaryDirectory() as folder:
            repository = CatalogRepository(Path(folder) / "products.csv")
            self.assertEqual(repository.get_products(), [])
            self.assertEqual(repository.get_stores(), [])

    def test_reads_multiple_store_offers_and_decimal_comma(self):
        with tempfile.TemporaryDirectory() as folder:
            csv_path = Path(folder) / "catalog.csv"
            csv_path.write_text(
                "product_id;name;unit;category;store;price;image\n"
                "SKU-1;Молоко;1 л;Молочные;Магазин А;89,90;\n"
                "SKU-1;Молоко;1 л;Молочные;Магазин Б;92,50;\n",
                encoding="utf-8-sig",
            )
            products = CatalogRepository.read_csv(csv_path)
            self.assertEqual(len(products), 1)
            self.assertEqual(len(products[0].offers), 2)
            self.assertAlmostEqual(products[0].minimum_price, 89.90)

    def test_persists_local_image_next_to_catalog(self):
        with tempfile.TemporaryDirectory() as folder:
            source_folder = Path(folder) / "source"
            target_folder = Path(folder) / "app_data"
            source_folder.mkdir()
            photo = source_folder / "product.jpg"
            photo.write_bytes(b"image-bytes")
            csv_path = source_folder / "catalog.csv"
            csv_path.write_text(
                "product_id;name;unit;category;store;price;image\n"
                "SKU-1;Молоко;1 л;Молочные;Магазин А;89,90;product.jpg\n",
                encoding="utf-8-sig",
            )
            repository = CatalogRepository(target_folder / "products.csv")
            products = repository.import_file(csv_path, persist=True)
            self.assertEqual(len(products), 1)
            self.assertTrue(Path(products[0].image_source).is_file())
            self.assertTrue((target_folder / "products.csv").is_file())
            reloaded_repository = CatalogRepository(target_folder / "products.csv")
            reloaded = reloaded_repository.get_products()
            self.assertEqual(reloaded[0].product_id, "SKU-1")
            self.assertTrue(Path(reloaded[0].image_source).is_file())
            image_files_before = list((target_folder / "images").iterdir())
            reloaded_repository.import_file(target_folder / "products.csv", persist=True)
            image_files_after = list((target_folder / "images").iterdir())
            self.assertEqual(image_files_after, image_files_before)

    def test_discovers_product_image_by_product_id(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            image_folder = root / "images"
            image_folder.mkdir()
            photo = image_folder / "SKU-2.jpg"
            photo.write_bytes(b"image-bytes")
            csv_path = root / "catalog.csv"
            csv_path.write_text(
                "product_id;name;unit;category;store;price\n"
                "SKU-2;Хлеб;1 шт.;Выпечка;Магазин А;49,90\n",
                encoding="utf-8-sig",
            )
            product = CatalogRepository.read_csv(csv_path)[0]
            self.assertEqual(Path(product.image_source), photo.resolve())

    def test_rejects_rows_with_price_but_without_store(self):
        with tempfile.TemporaryDirectory() as folder:
            csv_path = Path(folder) / "catalog.csv"
            csv_path.write_text(
                "product_id;name;unit;category;store;price\n"
                "SKU-1;Молоко;1 л;Молочные;;89,90\n",
                encoding="utf-8-sig",
            )
            with self.assertRaises(CatalogImportError):
                CatalogRepository.read_csv(csv_path)


if __name__ == "__main__":
    unittest.main()
