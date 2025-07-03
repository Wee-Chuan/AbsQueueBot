import sys
import os

# Add the parent directory of barber_side to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import asyncio
import time
from telegram.error import TelegramError
from telegram import Bot

from client_side.utils.globals import *

class NotificationListener:
    def __init__(self, bot_token: str, db, check_interval: int = 300):
        self.bot_token = bot_token
        self.db = db
        self.check_interval = check_interval
        self.running = False
        self.loop = asyncio.new_event_loop()

    async def _async_send_notification(self, user_id: str, barber_data: dict):
        """Async version of notification sender"""
        try:
            bot = Bot(token=self.bot_token)
            
            # Verify chat exists
            try:
                chat = await bot.get_chat(user_id)
                print(f"Verified chat with {user_id} (type: {chat.type})")
            except TelegramError as e:
                print(f"Chat verification failed for {user_id}: {e}")
                return False

            # Send notification
            message = (
                f"🚨 New slots available with {barber_data.get('name', 'your barber')}!\n"
                f"📍 {barber_data.get('address', '')}\n\n"
                "Tap /menu to book now!"
            )
            
            await bot.send_message(
                chat_id=user_id,
                text=message,
                parse_mode="HTML"
            )
            print(f"Successfully notified {user_id}")
            return True
            
        except Exception as e:
            print(f"Error notifying {user_id}: {type(e).__name__} - {str(e)}")
            return False

    def _send_notification(self, user_id: str, barber_data: dict):
        """Synchronous wrapper for async notification"""
        return self.loop.run_until_complete(
            self._async_send_notification(user_id, barber_data)
        )

    def _check_barber_notifications(self):
        """Check all barbers for notifications"""
        barbers_ref = self.db.collection('barbers')
        notified_barbers = barbers_ref.where('notify', '==', True).stream()
        
        for barber_doc in notified_barbers:
            barber_id = barber_doc.id
            barber_data = barber_doc.to_dict()
            
            try:
                followers_ref = self.db.collection('followers').document(barber_id)
                users_ref = followers_ref.collection('users').stream()
                
                for user_doc in users_ref:
                    self._send_notification(user_doc.id, barber_data)
                
                barbers_ref.document(barber_id).update({'notify': False})
                print(f"Processed notifications for barber {barber_id}")
                
            except Exception as e:
                print(f"Error processing barber {barber_id}: {e}")

    def start(self):
        """Start the listener"""
        self.running = True
        asyncio.set_event_loop(self.loop)
        
        while self.running:
            try:
                self._check_barber_notifications()
            except Exception as e:
                print(f"Listener error: {e}")
            time.sleep(self.check_interval)

    def stop(self):
        """Stop the listener"""
        self.running = False
        self.loop.close()