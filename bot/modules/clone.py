from random import SystemRandom
from string import ascii_letters, digits
from telegram.ext import CommandHandler
from threading import Thread
from time import sleep
from pyrogram import enums

from bot.helper.mirror_utils.upload_utils.gdriveTools import GoogleDriveHelper
from bot.helper.telegram_helper.message_utils import sendMessage, sendMarkup, deleteMessage, delete_all_messages, update_all_messages, sendStatusMessage, auto_delete_upload_message, auto_delete_message, sendFile
from bot.helper.telegram_helper.filters import CustomFilters
from bot.helper.telegram_helper.bot_commands import BotCommands
from bot.helper.mirror_utils.status_utils.clone_status import CloneStatus
from bot import *
from bot.helper.ext_utils.bot_utils import *
from bot.helper.mirror_utils.download_utils.direct_link_generator import *
from bot.helper.ext_utils.exceptions import DirectDownloadLinkException
from telegram import InlineKeyboardMarkup, ParseMode
from bot.helper.telegram_helper.button_build import ButtonMaker

def _clone(message, bot):
    if AUTO_DELETE_UPLOAD_MESSAGE_DURATION != -1:
        reply_to = message.reply_to_message
        if reply_to is not None:
            reply_to.delete()
        auto_delete_message = int(AUTO_DELETE_UPLOAD_MESSAGE_DURATION / 60)
        if message.chat.type == 'private':
            warnmsg = ''
        else:
            warnmsg = f'<b>This message will be deleted in <i>{auto_delete_message} minutes</i> from this group.</b>\n'
    else:
        warnmsg = ''
    if BOT_PM and message.chat.type != 'private':
        pmwarn = f"<b>I have sent files in PM.</b>\n"
    elif message.chat.type == 'private':
        pmwarn = ''
    else:
        pmwarn = ''
    if MIRROR_LOGS and message.chat.type != 'private':
        logwarn = f"<b>I have sent files in Mirror Log Channel.(Join Mirror Log channel) </b>\n"
    elif message.chat.type == 'private':
        logwarn = ''
    else:
        logwarn = ''
    buttons = ButtonMaker()	
    if FSUB:
        try:
            user = bot.get_chat_member(f"{FSUB_CHANNEL_ID}", message.from_user.id)
            LOGGER.info(user.status)
            if user.status not in ("member", "creator", "administrator", "supergroup"):
                if message.from_user.username:
                    uname = f'<a href="tg://user?id={message.from_user.id}">{message.from_user.username}</a>'
                else:
                    uname = f'<a href="tg://user?id={message.from_user.id}">{message.from_user.first_name}</a>'
                buttons = ButtonMaker()
                chat_u = CHANNEL_USERNAME.replace("@", "")
                buttons.buildbutton("Join Channel", f"https://t.me/{chat_u}")
                help_msg = f"Dear {uname},\nYou need to Join my Channel to use me.\n\n<b>Click on the Button Below and Join fast ASAP!</b>"
                reply_message = sendMarkup(help_msg, bot, message, InlineKeyboardMarkup(buttons.build_menu(2)))
                Thread(target=auto_delete_message, args=(bot, message, reply_message)).start()
                return reply_message
        except Exception:
            pass
            
    if BOT_PM and message.chat.type != 'private':
        try:
            msg1 = f'Added your Requested link to Download\n'
            send = bot.sendMessage(message.from_user.id, text=msg1)
            send.delete()
        except Exception as e:
            LOGGER.warning(e)
            bot_d = bot.get_me()
            b_uname = bot_d.username
            uname = f'<a href="tg://user?id={message.from_user.id}">{message.from_user.first_name}</a>'
            botstart = f"http://t.me/{b_uname}"
            buttons.buildbutton("Click Here to Start Me", f"{botstart}")
            startwarn = f"Dear {uname},\n\n<b>I found that you haven't started me in PM (Private Chat) yet.</b>\n\n" \
                        f"From now on i will send links and leeched files in PM and log channel only"
            message = sendMarkup(startwarn, bot, message, InlineKeyboardMarkup(buttons.build_menu(2)))
            return

    total_task = len(download_dict)
    user_id = message.from_user.id
    if user_id != OWNER_ID and user_id not in SUDO_USERS:
            if TOTAL_TASKS_LIMIT == total_task:
                return sendMessage(f"<b>Bro, My Total Task Limit is: {TOTAL_TASKS_LIMIT} Tasks at a Time.\nYou Guys Have Already Gave Me: {total_task} Tasks.\n\nNow Add Your Next Task on Other Bots or Just Wait For One of My Tasks to Complete!</b>", bot ,message)
            if USER_TASKS_LIMIT == get_user_task(user_id):
                return sendMessage(f"<b>Bro, Each of My Users Can Add: {USER_TASKS_LIMIT} Tasks at a Time.\nYou Have Already Added: {get_user_task(user_id)} Tasks.\n\nNow Add Your Next Task on Other Bots or Just Wait For One of Your Tasks to Complete!</b>", bot ,message)


    args = message.text.split()
    reply_to = message.reply_to_message
    link = ''
    multi=1

    if len(args) > 1:
        link = args[1].strip()
        if link.strip().isdigit():
            multi = int(link)
            link = ''
        elif message.from_user.username:
            tag = f"@{message.from_user.username}"
        else:
            tag = message.from_user.mention_html(message.from_user.first_name)
    if reply_to:
        if len(link) == 0:
            link = reply_to.text.split(maxsplit=1)[0].strip()
        if reply_to.from_user.username:
            tag = f"@{reply_to.from_user.username}"
        else:
            tag = reply_to.from_user.mention_html(reply_to.from_user.first_name)
    
    mesg = message.text.split('\n')
    message_args = mesg[0].split(' ', maxsplit=1)
    user_id = message.from_user.id
    tag = f"@{message.from_user.username}"
    slmsg = f"Added by: {tag} \nUser ID: <code>{user_id}</code>\n\n"
    if LINK_LOGS:
            try:
                source_link = f"<code>{message_args[1]}</code>"
                for link_log in LINK_LOGS:
                    bot.sendMessage(link_log, text=slmsg + source_link, parse_mode=ParseMode.HTML )
            except IndexError:
                pass
            if reply_to is not None:
                try:
                    reply_text = reply_to.text
                    if is_url(reply_text):
                        source_link = f"<code>{reply_text.strip()}</code>"
                        for link_log in LINK_LOGS:
                            bot.sendMessage(chat_id=link_log, text=slmsg + source_link, parse_mode=ParseMode.HTML )
                except TypeError:
                    pass  

    is_gdtot = is_gdtot_link(link)
    is_unified = is_unified_link(link)
    is_udrive = is_udrive_link(link)
    if (is_gdtot or is_unified or is_udrive):
        try:
            msg = sendMessage(f"Processing: <code>{link}</code>", bot, message)
            LOGGER.info(f"Processing: {link}")
            if is_unified:
                link = unified(link)
            if is_gdtot:
                link = gdtot(link)
            if is_udrive:
                link = udrive(link)
            LOGGER.info(f"Processing GDToT: {link}")
            deleteMessage(bot, msg)
        except DirectDownloadLinkException as e:
            deleteMessage(bot, msg)
            return sendMessage(str(e), bot, message)
    if is_gdrive_link(link):
        gd = GoogleDriveHelper()
        res, size, name, files = gd.helper(link)
        if res != "":
            return sendMessage(res, bot, message)
        if STOP_DUPLICATE:
            LOGGER.info('Checking File/Folder if already in Drive...')
            if TELEGRAPH_STYLE is True:
                smsg, button = gd.drive_list(name, True, True)
                if smsg:
                    msg3 = "File/Folder have been already mirrored by someone !\nHere you go:"
                    return sendMarkup(msg3, bot, message, button)
            else:
                cap, f_name = gd.drive_list(name, True, True)
                if cap:
                    cap = f"File/Folder have been already mirrored by someone! Here you go:\n\n{cap}"
                    sendFile(bot, message, f_name, cap)
                    return
        if CLONE_LIMIT is not None:
            LOGGER.info('Checking File/Folder Size...')
            if size > CLONE_LIMIT * 1024**3:
                msg2 = f'Failed, Clone limit is {CLONE_LIMIT}GB.\nYour File/Folder size is {get_readable_file_size(size)}.'
                return sendMessage(msg2, bot, message)
        if multi > 1:
            sleep(4)
            nextmsg = type('nextmsg', (object, ), {'chat_id': message.chat_id, 'message_id': message.reply_to_message.message_id + 1})
            nextmsg = sendMessage(message.text.replace(str(multi), str(multi - 1), 1), bot, nextmsg)
            nextmsg.from_user.id = message.from_user.id
            sleep(4)
            Thread(target=_clone, args=(nextmsg, bot)).start()
        if files <= 20:
            msg = sendMessage(f"Cloning: <code>{link}</code>", bot, message)
            result, button = gd.clone(link)
            deleteMessage(bot, msg)
        else:
            drive = GoogleDriveHelper(name)
            gid = ''.join(SystemRandom().choices(ascii_letters + digits, k=12))
            clone_status = CloneStatus(drive, size, message, gid)
            with download_dict_lock:
                download_dict[message.message_id] = clone_status
            sendStatusMessage(message, bot)
            result, button = drive.clone(link)
            with download_dict_lock:
                del download_dict[message.message_id]
                count = len(download_dict)
            try:
                if count == 0:
                    Interval[0].cancel()
                    del Interval[0]
                    delete_all_messages()
                else:
                    update_all_messages()
            except IndexError:
                pass
        cc = f'\n<b>└ Cc: </b>{tag}\n\n'
        if button in ["cancelled", ""]:
            sendMessage(f"{tag} {result}", bot, message)
        else:
            msg = sendMarkup(result + cc + pmwarn + logwarn + warnmsg, bot, message, button)
            LOGGER.info(f'Cloning Done: {name}')
            Thread(target=auto_delete_upload_message, args=(bot, message, msg)).start()
        if (is_gdtot or is_unified or is_udrive):
            gd.deletefile(link) 

        if MIRROR_LOGS:	
            try:	
                for chatid in MIRROR_LOGS:	
                    bot.sendMessage(chat_id=chatid, text=result + cc, reply_markup=button, parse_mode=ParseMode.HTML)	
            except Exception as e:	
                LOGGER.warning(e)	
        if BOT_PM and message.chat.type != 'private':	
            try:	
                bot.sendMessage(message.from_user.id, text=result, reply_markup=button,	
                                parse_mode=ParseMode.HTML)	
            except Exception as e:	
                LOGGER.warning(e)	
                return


    else:
        sendMessage('Send Gdrive or GDToT/AppDrive/DriveApp/GDFlix/DriveBit/DrivePro/DriveAce/DriveSharer/HubDrive/DriveHub/KatDrive/Kolop/DriveFire link along with command or by replying to the link by command', bot, message)

@new_thread
def cloneNode(update, context):
    _clone(update.message, context.bot)

if CLONE_ENABLED:
    clone_handler = CommandHandler(BotCommands.CloneCommand, cloneNode, filters=CustomFilters.authorized_chat | CustomFilters.authorized_user, run_async=True)
else:
    clone_handler = CommandHandler(BotCommands.CloneCommand, cloneNode, filters=CustomFilters.owner_filter | CustomFilters.authorized_user, run_async=True)

dispatcher.add_handler(clone_handler)
