import unittest

from main import format_seo_publish_message, parse_forwarded_listing


class ForwardedListingParserTests(unittest.TestCase):
    def test_parses_example_card(self) -> None:
        text = """
        BMW X1

        Китай🇨🇳

        характеристики
        Год → 2019
        Двигатель → 1.5
        Пробег → 46000км
        Привод → передний
        Кузов → кроссовер

        ЦЕНА: 1 710 000₽
        """

        self.assertEqual(
            parse_forwarded_listing(text),
            {
                "market": "china",
                "brand": "BMW",
                "model": "X1",
                "year": 2019,
                "mileage_km": 46000,
                "engine_volume_l": "1.5",
                "drive_type": "Передний",
                "body_type": "Кроссовер",
                "price": "1710000",
            },
        )

    def test_supports_colons_and_optional_fields(self) -> None:
        text = """
        Mercedes-Benz GLC 300
        Корея
        Год: 2021
        Объём двигателя: 2,0 л
        Пробег: 35 500 км
        Привод: AWD
        Кузов: SUV
        Мощность: 258 л.с.
        Комплектация: AMG Line
        Цена: 4 850 000 руб.
        """

        parsed = parse_forwarded_listing(text)
        self.assertEqual(parsed["market"], "korea")
        self.assertEqual(parsed["brand"], "Mercedes-Benz")
        self.assertEqual(parsed["model"], "GLC 300")
        self.assertEqual(parsed["engine_volume_l"], "2")
        self.assertEqual(parsed["drive_type"], "Полный")
        self.assertEqual(parsed["body_type"], "Кроссовер")
        self.assertEqual(parsed["power_hp"], 258)
        self.assertEqual(parsed["trim"], "AMG Line")
        self.assertEqual(parsed["price"], "4850000")

    def test_empty_text_returns_empty_payload(self) -> None:
        self.assertEqual(parse_forwarded_listing(""), {})

    def test_formats_published_seo_page(self) -> None:
        text = format_seo_publish_message(
            {"seo_status": "published", "seo_url": "/cars/japan/toyota/raize/"}
        )
        self.assertIn("SEO-страница опубликована", text)
        self.assertIn("https://primcom.ru/cars/japan/toyota/raize/", text)

    def test_formats_catalog_only_reason(self) -> None:
        text = format_seo_publish_message(
            {"seo_status": "catalog_only", "seo_reason": "Для SEO-страницы не хватает: цена."}
        )
        self.assertIn("карточка каталога сохранена", text)
        self.assertIn("не хватает: цена", text)

    def test_silences_unconfigured_publisher(self) -> None:
        """Не настроенный публикатор — состояние сервера, а не проблема карточки."""
        for reason in (
            "Автопубликация SEO не настроена на сервере.",
            "Команда SEO-публикации пуста.",
        ):
            with self.subTest(reason=reason):
                text = format_seo_publish_message(
                    {"seo_status": "catalog_only", "seo_reason": reason}
                )
                self.assertEqual(text, "")

    def test_still_reports_real_build_failure(self) -> None:
        """Сбой сборки менеджер видеть должен: страницы не обновились."""
        text = format_seo_publish_message(
            {
                "seo_status": "catalog_only",
                "seo_reason": "SEO-сборка завершилась ошибкой; рабочие страницы не изменены.",
            }
        )
        self.assertIn("карточка каталога сохранена", text)
        self.assertIn("завершилась ошибкой", text)


if __name__ == "__main__":
    unittest.main()
