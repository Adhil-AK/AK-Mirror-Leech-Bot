from psutil import cpu_percent, virtual_memory, disk_usage
from time import time, sleep
from threading import Thread
from telegram.ext import CommandHandler, CallbackQueryHandler

from bot import dispatcher, status_reply_dict, status_reply_dict_lock, download_dict, download_dict_lock, botStartTime, DOWNLOAD_DIR, OWNER_ID, Interval, DOWNLOAD_STATUS_UPDATE_INTERVAL
from bot.helper.telegram_helper.message_utils import sendMessage, deleteMessage, auto_delete_message, sendStatusMessage, update_all_messages, delete_all_messages, editMessage 
from bot.helper.ext_utils.bot_utils import get_readable_file_size, get_readable_time, turn, pop_up_stats, setInterval
from bot.helper.telegram_helper.filters import CustomFilters
from bot.helper.telegram_helper.bot_commands import BotCommands


def mirror_status(update, context):
    with download_dict_lock:
        count = len(download_dict)
    if count == 0:
        currentTime = get_readable_time(time() - botStartTime)
        free = get_readable_file_size(disk_usage(DOWNLOAD_DIR).free)
        message = 'No Active Downloads !\n___________________________'
        message += f"\n<b>CPU:</b> {cpu_percent()}% | <b>FREE:</b> {free}" \
                   f"\n<b>RAM:</b> {virtual_memory().percent}% | <b>UPTIME:</b> {currentTime}"
        reply_message = sendMessage(message, context.bot, update.message)
        Thread(target=auto_delete_message, args=(context.bot, update.message, reply_message)).start()
    else:
        index = update.effective_chat.id
        with status_reply_dict_lock:
            if index in status_reply_dict:
                deleteMessage(context.bot, status_reply_dict[index][0])
                del status_reply_dict[index]
            try:
                if Interval:
                    Interval[0].cancel()
                    Interval.clear()
            except:
                pass
            finally:
                Interval.append(setInterval(DOWNLOAD_STATUS_UPDATE_INTERVAL, update_all_messages))
        sendStatusMessage(update.message, context.bot)
        deleteMessage(context.bot, update.message)

def status_pages(update, context):
    query = update.callback_query
    msg = query.message
    user_id = query.from_user.id
    user_name = query.from_user.first_name
    chat_id = update.effective_chat.id
    admins = context.bot.get_chat_member(chat_id, user_id).status in ['creator', 'administrator'] or user_id in [OWNER_ID]
    data = query.data
    data = data.split()
    if data[1] == "refresh":
        editMessage(f"{user_name}, Refreshing Status...🔃", msg)
        sleep(2)
        update_all_messages()
        query.answer()
    if data[1] == "stats":
        stats = pop_up_stats()
        query.answer(text=stats, show_alert=True)
    if data[1] == "close":
        if admins:
            delete_all_messages()
            query.answer()
        else:
            query.answer(text=f"{user_name}, You Don't Have Rights To Close This!", show_alert=True)
    if data[1] == "pre" or "nex":
        done = turn(data)
    if done:
        update_all_messages(True)
        query.answer()
    else:
        msg.delete()


mirror_status_handler = CommandHandler(BotCommands.StatusCommand, mirror_status,
                                       filters=CustomFilters.authorized_chat | CustomFilters.authorized_user, run_async=True)

status_pages_handler = CallbackQueryHandler(status_pages, pattern="status", run_async=True)
dispatcher.add_handler(mirror_status_handler)
dispatcher.add_handler(status_pages_handler)
