from telegram import Update
from telegram.ext import CallbackContext, ConversationHandler
from functools import wraps

class HelperUtils:
    """Utility class for shared helper functions."""

    @staticmethod
    def set_user_data(context: CallbackContext, key: str, value):
        """Set a value in context.user_data."""
        context.user_data[key] = value

    @staticmethod
    def get_user_data(context: CallbackContext, key: str):
        """Get a value from context.user_data."""
        return context.user_data.get(key)

    @staticmethod
    def reset_conversation_state(context: CallbackContext):
        """Reset the conversation_active flag in user_data."""
        context.user_data.clear()
        HelperUtils.set_user_data(context, "conversation_active", False)
        return ConversationHandler.END

    @staticmethod
    def check_conversation_active(func):
        """Decorator to check if the conversation is active."""
        @wraps(func)
        async def wrapper(update: Update, context: CallbackContext, *args, **kwargs):
            if not HelperUtils.get_user_data(context, "conversation_active"):
                if update.message:
                    await update.message.reply_text("⚠️ There's no active operation to cancel.")
                elif update.callback_query:
                    await update.callback_query.answer()
                    await update.callback_query.edit_message_text("⚠️ There's no active operation to cancel.")
                return ConversationHandler.END
            return await func(update, context, *args, **kwargs)
        return wrapper

    @staticmethod
    def store_message_id(context: CallbackContext, message_id: int) -> None:
        """Store a message ID in user_data for later deletion."""
        if "message_ids" not in context.user_data:
            context.user_data["message_ids"] = []
        context.user_data["message_ids"].append(message_id)
    
    @staticmethod
    async def clear_previous_messages(context: CallbackContext, chat_id: int):
        """Delete all stored message IDs for this chat"""
        if 'message_ids' in context.user_data:
            # Create a set to avoid duplicate message IDs
            unique_message_ids = set(context.user_data["message_ids"])
            for msg_id in unique_message_ids:
                try:
                    print(f"Deleting message {msg_id} in chat {chat_id}")
                    await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
                except Exception as e:
                    print(f"Could not delete message {msg_id}: {e}")
            context.user_data['message_ids'] = []
    
    @staticmethod
    def clear_user_data(context: CallbackContext, keys: list):
        for key in keys:
            context.user_data.pop(key, None)
