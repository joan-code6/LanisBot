import logging
import os

from flask import Flask, request

from pywa import WhatsApp, filters, types
from pywa.error import WhatsAppError

logger = logging.getLogger(__name__)


class SPHWhatsAppBot:
    def __init__(self, agent, memory):
        self.agent = agent
        self.memory = memory
        self.wa = None
        self.phone_id = os.getenv("WHATSAPP_PHONE_ID")
        self.token = os.getenv("WHATSAPP_TOKEN")
        self.verify_token = os.getenv("WHATSAPP_VERIFY_TOKEN", "default_verify_token")
        self.callback_url = os.getenv("WHATSAPP_CALLBACK_URL")

    def _get_user_id(self, msg: types.Message) -> str:
        return msg.from_user.phone

    def _setup_handlers(self):
        if not self.wa:
            return

        @self.wa.on_message(filters.text)
        async def handle_text(client: WhatsApp, msg: types.Message):
            user_id = self._get_user_id(msg)
            response = await self.agent.handle_message(msg.text, user_id=user_id)
            try:
                await msg.reply_text(response)
            except Exception as e:
                logger.error(f"Failed to reply: {e}")
                await client.send_message(to=user_id, text=response)

        @self.wa.on_message(filters.document)
        async def handle_document(client: WhatsApp, msg: types.Message):
            user_id = self._get_user_id(msg)
            await msg.reply_text(
                text="Document received. I'm currently unable to process files. Please send your question as text.",
                buttons=[types.Button(title="Help", callback_data="help")],
            )

        @self.wa.on_message(filters.image)
        async def handle_image(client: WhatsApp, msg: types.Message):
            user_id = self._get_user_id(msg)
            await msg.reply_text(
                text="Image received. I'm currently unable to process images. Please send your question as text.",
                buttons=[types.Button(title="Help", callback_data="help")],
            )

        @self.wa.on_callback(filters.data)
        async def handle_callback(client: WhatsApp, clb: types.Callback):
            if clb.data == "help":
                await clb.msg.reply_text(
                    text="I can help you with:\n- Substitution plan (Vertretungsplan)\n- Messages from school\n- Homework\n- Calendar events\n- And more!\n\nJust ask me a question.",
                    buttons=[
                        types.Button(title="Substitution Plan", callback_data="sub"),
                        types.Button(title="Messages", callback_data="msgs"),
                    ],
                )

    async def start_webhook(self, app: Flask = None):
        if not self.phone_id or not self.token:
            logger.warning(
                "WhatsApp not configured - WHATSAPP_PHONE_ID and WHATSAPP_TOKEN required"
            )
            return

        if app is None:
            app = Flask(__name__)

        self.wa = WhatsApp(
            phone_id=self.phone_id,
            token=self.token,
            server=app,
            callback_url=self.callback_url,
            verify_token=self.verify_token,
        )

        self._setup_handlers()

        logger.info(f"WhatsApp bot started on {self.callback_url}")
        return app


def setup_whatsapp_bot(agent, memory):
    return SPHWhatsAppBot(agent, memory)
