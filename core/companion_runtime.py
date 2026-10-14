"""Application lifecycle adapter; UI widgets are read only on the main thread."""
import logging
import threading
from companion_loop import CompanionLoop


def attach_companion(app, controller):
    try:
        loop = CompanionLoop()
    except Exception:
        logging.getLogger(__name__).warning('Companion initialization unavailable')
        return
    controller.companion_loop = loop
    running = threading.Event()

    def tick():
        conversation_id = controller.conversation_id
        busy = controller.request_in_progress or bool(app.chat_page.input_panel.get_text().strip())
        provider = controller.user_settings.text_provider
        if not running.is_set():
            running.set()
            def evaluate():
                try:
                    loop.tick(conversation_id, user_busy=busy, provider=provider)
                except Exception:
                    logging.getLogger(__name__).warning('Companion evaluation unavailable')
                finally:
                    running.clear()
            threading.Thread(target=evaluate, daemon=True).start()
        app.after(loop.config.tick_seconds * 1000, tick)

    app.after(loop.config.tick_seconds * 1000, tick)
