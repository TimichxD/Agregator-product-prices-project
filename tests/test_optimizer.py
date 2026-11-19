"""Проверки алгоритма подбора без запуска графического интерфейса."""

import unittest

from models.product import Offer, Product
from services.basket_optimizer import BasketOptimizer


class BasketOptimizerTests(unittest.TestCase):
    def setUp(self):
        self.products = [
            Product("SKU-1", "Товар один", "1 шт.", "Категория", (
                Offer("Магазин А", 100.0), Offer("Магазин Б", 95.0),
            )),
            Product("SKU-2", "Товар два", "500 г", "Категория", (
                Offer("Магазин А", 50.0), Offer("Магазин Б", 60.0),
            )),
        ]
        self.optimizer = BasketOptimizer(self.products)

    def test_hybrid_chooses_cheapest_offer_per_product(self):
        result = self.optimizer.optimize({"SKU-1": 2, "SKU-2": 1}, "hybrid", 500, 10)
        self.assertEqual(result.status, "complete")
        self.assertEqual(len(result.lines), 2)
        self.assertEqual(result.lines[0].offer.unit_price, 95.0)
        self.assertAlmostEqual(result.total, 240.0)

    def test_single_store_uses_one_store_for_the_whole_basket(self):
        result = self.optimizer.optimize({"SKU-1": 1, "SKU-2": 1}, "single_store", 500, 10)
        self.assertEqual(result.status, "complete")
        self.assertEqual(len(result.store_totals), 1)
        self.assertEqual(result.total, 150.0)

    def test_budget_allowance_is_applied(self):
        result = self.optimizer.optimize({"SKU-1": 1}, "within_budget", 90, 10)
        self.assertEqual(result.status, "within_allowance")
        self.assertAlmostEqual(result.budget_limit, 99.0)

    def test_missing_prices_are_not_removed_from_the_basket(self):
        product = Product("SKU-3", "Без цены", "1 шт.", "Категория", ())
        optimizer = BasketOptimizer([product])
        result = optimizer.optimize({"SKU-3": 1}, "single_store", 100, 10)
        self.assertEqual(result.status, "incomplete")
        self.assertEqual(result.missing_products, ["Без цены"])
        self.assertEqual(result.total, 0.0)

    def test_unknown_mode_is_rejected(self):
        with self.assertRaises(ValueError):
            self.optimizer.optimize({}, "other", 100, 10)


if __name__ == "__main__":
    unittest.main()
