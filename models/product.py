"""Модели товара и ценового предложения."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Offer:
    store: str
    unit_price: float


@dataclass(frozen=True, slots=True)
class Product:
    product_id: str
    name: str
    unit: str
    category: str
    offers: tuple[Offer, ...]
    image_source: str | None = None

    def offer_for(self, store: str) -> Offer | None:
        return next((offer for offer in self.offers if offer.store == store), None)

    @property
    def available_offers(self) -> tuple[Offer, ...]:
        return self.offers

    @property
    def minimum_price(self) -> float | None:
        if not self.offers:
            return None
        return min(offer.unit_price for offer in self.offers)
