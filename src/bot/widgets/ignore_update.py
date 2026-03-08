from aiogram.types import Message
from aiogram_dialog import DialogManager, DialogProtocol, ShowMode
from aiogram_dialog.widgets.input import BaseInput


class IgnoreUpdate(BaseInput):
    async def process_message(
        self,
        message: Message,
        dialog_protocol: DialogProtocol,
        dialog_manager: DialogManager,
    ) -> bool:
        dialog_manager.show_mode = ShowMode.NO_UPDATE
        return True
