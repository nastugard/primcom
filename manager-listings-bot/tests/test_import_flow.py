import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage

import main


EXAMPLE_CAPTION = """
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


class FakeMessage:
    def __init__(self, text: str | None = None) -> None:
        self.text = text
        self.answers: list[str] = []
        self.from_user = SimpleNamespace(id=123)
        self.chat = SimpleNamespace(id=123)

    async def answer(self, text: str, reply_markup=None) -> None:
        self.answers.append(text)


def album_message(message_id: int, file_id: str, caption: str = "") -> SimpleNamespace:
    return SimpleNamespace(
        message_id=message_id,
        caption=caption,
        text=None,
        photo=[SimpleNamespace(file_id=file_id)],
        document=None,
        sticker=None,
        animation=None,
    )


class ForwardedListingFlowTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.storage = MemoryStorage()
        self.state = FSMContext(
            storage=self.storage,
            key=StorageKey(bot_id=1, chat_id=123, user_id=123),
        )
        self.previous_config = main.CONFIG
        main.CONFIG = main.BotConfig(
            token="test",
            api_base_url="https://example.invalid",
            manager_api_key="test",
            allowed_ids=set(),
        )

    async def asyncTearDown(self) -> None:
        main.CONFIG = self.previous_config
        await self.storage.close()

    async def test_import_confirms_without_asking_for_missing_power(self) -> None:
        first_message = FakeMessage()
        await main.process_forwarded_listing(
            first_message,
            self.state,
            caption=EXAMPLE_CAPTION,
            photo_file_ids=["photo-1", "photo-2"],
        )

        self.assertEqual(await self.state.get_state(), main.ListingFlow.confirm.state)
        imported = await self.state.get_data()
        self.assertEqual(imported["photo_file_ids"], ["photo-1", "photo-2"])
        self.assertEqual(imported["price"], "1710000")
        self.assertNotIn("power_hp", imported)
        self.assertTrue(any("только данные из публикации" in answer for answer in first_message.answers))
        self.assertTrue(any("Проверьте карточку" in answer for answer in first_message.answers))

    async def test_album_is_sorted_and_uses_its_caption(self) -> None:
        key = (123, "album-1")
        first = album_message(10, "photo-1", EXAMPLE_CAPTION)
        second = album_message(11, "photo-2")
        main.ALBUM_BUFFERS[key] = main.AlbumBuffer(messages=[second, first])

        previous_wait = main.ALBUM_WAIT_SECONDS
        previous_processor = main.process_forwarded_listing
        processor = AsyncMock()
        main.ALBUM_WAIT_SECONDS = 0
        main.process_forwarded_listing = processor
        try:
            await main._finish_album(key, self.state)
        finally:
            main.ALBUM_WAIT_SECONDS = previous_wait
            main.process_forwarded_listing = previous_processor
            main.ALBUM_BUFFERS.pop(key, None)

        processor.assert_awaited_once_with(
            first,
            self.state,
            caption=EXAMPLE_CAPTION.strip(),
            photo_file_ids=["photo-1", "photo-2"],
        )


if __name__ == "__main__":
    unittest.main()
