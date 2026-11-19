"""Расчёт вариантов корзины по цене и доступности."""

from dataclasses import dataclass, field
from typing import Mapping

from models.product import Offer, Product


@dataclass(frozen=True, slots=True)
class PlannedLine:
    product: Product
    quantity: int
    offer: Offer

    @property
    def line_total(self) -> float:
        return self.quantity * self.offer.unit_price


@dataclass(slots=True)
class OptimizationResult:
    mode: str
    lines: list[PlannedLine]
    total: float
    status: str
    message: str
    missing_products: list[str] = field(default_factory=list)
    store_totals: dict[str, float] = field(default_factory=dict)
    budget: float = 0.0
    budget_limit: float = 0.0

    @property
    def stores(self) -> list[str]:
        return list(self.store_totals)


class BasketOptimizer:
    """Подбирает предложения; не заменяет и не удаляет позиции корзины."""

    VALID_MODES = {"hybrid", "single_store", "within_budget"}

    def __init__(self, products: list[Product]):
        self.products_by_id = {product.product_id: product for product in products}
        self.stores = sorted({offer.store for p in products for offer in p.offers})

    def optimize(
        self,
        basket: Mapping[str, int],
        mode: str,
        budget: float,
        allowance_percent: int,
    ) -> OptimizationResult:
        if mode not in self.VALID_MODES:
            raise ValueError("Неизвестный режим подбора.")
        if budget < 0 or allowance_percent < 0:
            raise ValueError("Бюджет и допустимое превышение не могут быть отрицательными.")
        if not basket:
            limit = budget * (1 + allowance_percent / 100)
            return OptimizationResult(
                mode, [], 0.0, "empty", "Список покупок пуст.",
                budget=budget, budget_limit=limit,
            )

        unknown = [product_id for product_id in basket if product_id not in self.products_by_id]
        if unknown:
            raise ValueError("В корзине есть товары, которых нет в каталоге: " + ", ".join(unknown))
        invalid = [quantity for quantity in basket.values() if not isinstance(quantity, int) or quantity < 1]
        if invalid:
            raise ValueError("Количество каждого товара должно быть целым числом больше нуля.")

        if mode == "single_store":
            result = self._single_store(basket, budget)
        else:
            result = self._hybrid(basket, mode, budget)

        result.budget_limit = budget * (1 + allowance_percent / 100)
        if mode == "within_budget":
            if result.missing_products:
                result.status = "incomplete"
                result.message = (
                    "Часть товаров отсутствует в загруженных ценовых предложениях. "
                    "Они оставлены в списке и не вошли в рассчитанную сумму."
                )
            elif result.total <= budget:
                result.status = "within_budget"
                result.message = "Корзина укладывается в заданный бюджет."
            elif result.total <= result.budget_limit:
                result.status = "within_allowance"
                result.message = (
                    f"До исходного бюджета не хватает {format_money(result.total - budget)}. "
                    "Вариант укладывается в разрешённое превышение."
                )
            else:
                result.status = "over_budget"
                result.message = (
                    f"Самый дешёвый доступный набор превышает допустимый лимит на "
                    f"{format_money(result.total - result.budget_limit)}. "
                    "Товары не исключены и не заменены автоматически."
                )
        return result

    def _hybrid(self, basket: Mapping[str, int], mode: str, budget: float) -> OptimizationResult:
        lines: list[PlannedLine] = []
        missing: list[str] = []
        for product_id, quantity in basket.items():
            product = self.products_by_id[product_id]
            if not product.offers:
                missing.append(product.name)
                continue
            best = min(product.offers, key=lambda offer: (offer.unit_price, offer.store.casefold()))
            lines.append(PlannedLine(product, quantity, best))
        total = sum(line.line_total for line in lines)
        store_totals = _sum_by_store(lines)
        complete = not missing
        if mode == "hybrid":
            message = (
                "Для каждой позиции выбрано самое дешёвое доступное предложение."
                if complete else
                "Некоторые товары отсутствуют в загруженных предложениях магазинов."
            )
        else:
            message = "Рассчитан самый дешёвый доступный набор без автоматической замены товаров."
        return OptimizationResult(
            mode=mode,
            lines=lines,
            total=total,
            status="complete" if complete else "incomplete",
            message=message,
            missing_products=missing,
            store_totals=store_totals,
            budget=budget,
        )

    def _single_store(self, basket: Mapping[str, int], budget: float) -> OptimizationResult:
        candidates: list[tuple[int, float, str, list[PlannedLine], list[str]]] = []
        if not self.stores:
            missing = [self.products_by_id[product_id].name for product_id in basket]
            return OptimizationResult(
                mode="single_store", lines=[], total=0.0, status="incomplete",
                message="В каталоге пока нет ценовых предложений магазинов.",
                missing_products=missing, store_totals={}, budget=budget,
            )
        for store in self.stores:
            lines: list[PlannedLine] = []
            missing: list[str] = []
            for product_id, quantity in basket.items():
                product = self.products_by_id[product_id]
                offer = product.offer_for(store)
                if offer is None:
                    missing.append(product.name)
                else:
                    lines.append(PlannedLine(product, quantity, offer))
            subtotal = sum(line.line_total for line in lines)
            candidates.append((len(lines), subtotal, store, lines, missing))

        # Приоритет: больше найденных товаров, затем меньшая сумма, затем название магазина.
        candidates.sort(key=lambda candidate: (-candidate[0], candidate[1], candidate[2].casefold()))
        found_count, total, store, lines, missing = candidates[0]
        complete = found_count == len(basket)
        message = (
            f"Вся корзина доступна в магазине «{store}»."
            if complete else
            f"В «{store}» найдено {found_count} из {len(basket)} позиций. Отсутствующие товары показаны отдельно."
        )
        totals = {store: total} if lines else {}
        return OptimizationResult(
            mode="single_store",
            lines=lines,
            total=total,
            status="complete" if complete else "incomplete",
            message=message,
            missing_products=missing,
            store_totals=totals,
            budget=budget,
        )


def _sum_by_store(lines: list[PlannedLine]) -> dict[str, float]:
    totals: dict[str, float] = {}
    for line in lines:
        totals[line.offer.store] = totals.get(line.offer.store, 0.0) + line.line_total
    return dict(sorted(totals.items(), key=lambda pair: pair[0].casefold()))


def format_money(value: float) -> str:
    rendered = f"{value:,.2f}".replace(",", " ").replace(".", ",")
    if rendered.endswith(",00"):
        rendered = rendered[:-3]
    return rendered + " ₽"
