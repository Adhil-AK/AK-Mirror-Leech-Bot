from re import match as re_match, findall as re_findall
from threading import Thread, Event
from time import time
from math import ceil
from html import escape
from psutil import virtual_memory, cpu_percent, disk_usage
from requests import head as rhead
from urllib.request import urlopen
from telegram import InlineKeyboardMarkup
from bot import download_dict, download_dict_lock, STATUS_LIMIT, botStartTime, DOWNLOAD_DIR
from bot.helper.telegram_helper.bot_commands import BotCommands
from bot.helper.telegram_helper.button_build import ButtonMaker
import shutil
import psutil
from telegram.error import RetryAfter
from telegram.ext import CallbackQueryHandler
from telegram.message import Message
from telegram.update import Update
from bot import *

MAGNET_REGEX = r"magnet:\?xt=urn:btih:[a-zA-Z0-9]*"

URL_REGEX = r"(?:(?:https?|ftp):\/\/)?[\w/\-?=%.]+\.[\w/\-?=%.]+"

COUNT = 0
PAGE_NO = 1

class MirrorStatus:
    STATUS_UPLOADING = "Uploading...⬘"
    STATUS_DOWNLOADING = "Downloading...⬙"
    STATUS_CLONING = "Cloning...♻️"
    STATUS_WAITING = "Queued...💤"
    STATUS_PAUSE = "Paused...⛔️"
    STATUS_ARCHIVING = "Archiving...🔐"
    STATUS_EXTRACTING = "Extracting...📂"
    STATUS_SPLITTING = "Splitting...✂️"
    STATUS_CHECKING = "CheckingUp...📝"
    STATUS_SEEDING = "Seeding...🌧"

class EngineStatus:
    STATUS_ARIA = "Aria2c v1.35.0"
    STATUS_GD = "Google Api v2.51.0"
    STATUS_MEGA = "Mega Api v3.12.0"
    STATUS_QB = "qBittorrent v4.4.2"
    STATUS_TG = "Pyrogram v2.0.27"
    STATUS_YT = "YT-dlp v22.5.18"
    STATUS_EXT = "pExtract"
    STATUS_SPLIT = "FFmpeg v2.9.1"
    STATUS_ZIP = "p7zip v16.02"

# PROGRESS_MAX_SIZE = 100 // 9
PROGRESS_MAX_SIZE = 9
PROGRESS_INCOMPLETE = ['◔', '◔', '◔', '◑', '◑', '◑', '◕', '◕', '◕']

SIZE_UNITS = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']


class setInterval:
    def __init__(self, interval, action):
        self.interval = interval
        self.action = action
        self.stopEvent = Event()
        thread = Thread(target=self.__setInterval)
        thread.start()

    def __setInterval(self):
        nextTime = time() + self.interval
        while not self.stopEvent.wait(nextTime - time()):
            nextTime += self.interval
            self.action()

    def cancel(self):
        self.stopEvent.set()

def get_readable_file_size(size_in_bytes) -> str:
    if size_in_bytes is None:
        return '0B'
    index = 0
    while size_in_bytes >= 1024:
        size_in_bytes /= 1024
        index += 1
    try:
        return f'{round(size_in_bytes, 2)}{SIZE_UNITS[index]}'
    except IndexError:
        return 'File too large'

def getDownloadByGid(gid):
    with download_dict_lock:
        for dl in list(download_dict.values()):
            status = dl.status()
            if dl.gid() == gid:
                return dl
    return None

def getAllDownload(req_status: str):
    with download_dict_lock:
        for dl in list(download_dict.values()):
            if dl:
                status = dl.status()
                if req_status == 'all':
                    return dl
                if req_status == 'down' and status in [MirrorStatus.STATUS_DOWNLOADING,
                                                         MirrorStatus.STATUS_WAITING,
                                                         MirrorStatus.STATUS_PAUSE]:
                    return dl
                if req_status == 'up' and status == MirrorStatus.STATUS_UPLOADING:
                    return dl
                if req_status == 'clone' and status == MirrorStatus.STATUS_CLONING:
                    return dl
                if req_status == 'seed' and status == MirrorStatus.STATUS_SEEDING:
                    return dl
                if req_status == 'split' and status == MirrorStatus.STATUS_SPLITTING:
                    return dl
                if req_status == 'extract' and status == MirrorStatus.STATUS_EXTRACTING:
                    return dl
                if req_status == 'archive' and status == MirrorStatus.STATUS_ARCHIVING:
                    return dl
    return None

def get_progress_bar_string(status):
    completed = status.processed_bytes() / 8
    total = status.size_raw() / 8
    p = 0 if total == 0 else round(completed * 100 / total)
    p = min(max(p, 0), 100)
    cFull = p // 10
    cPart = p % 10 - 1
    p_str = '⬤' * cFull
    if cPart >= 0:
        p_str += PROGRESS_INCOMPLETE[cPart]
    p_str += '○' * (PROGRESS_MAX_SIZE - cFull)
    p_str = f"「{p_str}」"
    return p_str

def get_readable_message():
    with download_dict_lock:
        msg = ""
        if STATUS_LIMIT is not None:
            tasks = len(download_dict)
            global pages
            pages = ceil(tasks/STATUS_LIMIT)
            if PAGE_NO > pages and pages != 0:
                globals()['COUNT'] -= STATUS_LIMIT
                globals()['PAGE_NO'] -= 1
        for index, download in enumerate(list(download_dict.values())[COUNT:], start=1):
            msg += f"\n <code>{escape(str(download.name()))}</code>"
            msg += f"\n<b>┌ Status:</b> <i>{download.status()}</i>"
            if download.status() not in [MirrorStatus.STATUS_SEEDING]:
                msg += f"\n<b>├</b>{get_progress_bar_string(download)}\n<b>├ Progress:</b> {download.progress()}"
                if download.status() in [MirrorStatus.STATUS_DOWNLOADING,
                                         MirrorStatus.STATUS_WAITING,
                                         MirrorStatus.STATUS_PAUSE]:
                    msg += f"\n<b>├ Downloaded:</b> {get_readable_file_size(download.processed_bytes())}\n<b>├ Total Size: </b>{download.size()}"
                elif download.status() == MirrorStatus.STATUS_UPLOADING:
                    msg += f"\n<b>├ Uploaded:</b> {get_readable_file_size(download.processed_bytes())}\n<b>├ Total Size: </b>{download.size()}"
                elif download.status() == MirrorStatus.STATUS_CLONING:
                    msg += f"\n<b>├ Cloned:</b> {get_readable_file_size(download.processed_bytes())}\n<b>├ Total Size: </b>{download.size()}"
                elif download.status() == MirrorStatus.STATUS_ARCHIVING:
                    msg += f"\n<b>├ Archived:</b> {get_readable_file_size(download.processed_bytes())}\n<b>├ Total Size: </b>{download.size()}"
                elif download.status() == MirrorStatus.STATUS_EXTRACTING:
                    msg += f"\n<b>├ Extracted:</b> {get_readable_file_size(download.processed_bytes())}\n<b>├ Total Size: </b>{download.size()}"
                elif download.status() == MirrorStatus.STATUS_SPLITTING:
                    msg += f"\n<b>├ Splitted:</b> {get_readable_file_size(download.processed_bytes())}\n<b>├ Total Size: </b>{download.size()}"
                msg += f"\n<b>├ Speed:</b> {download.speed()}\n<b>├ ETA:</b> {download.eta()}"
                msg += f"\n<b>├ Elapsed: </b>{get_readable_time(time() - download.message.date.timestamp())}"
                msg += f'\n<b>├ Req By:</b> <a href="https://t.me/c/{str(download.message.chat.id)[4:]}/{download.message.message_id}">{download.message.from_user.first_name}</a>'
                msg += f"\n<b>├ Engine:</b> {download.eng()}"
                try:
                    msg += f"\n<b>├ Seeders:</b> {download.aria_download().num_seeders}" \
                           f"\n<b>├ Peers:</b> {download.aria_download().connections}"
#                     msg += f'\n<b>├ TEngine: </b><a href="https://aria2.github.io">Aria2</a>'
                except:
                    pass
                try:
                    msg += f"\n<b>├ Seeders:</b> {download.torrent_info().num_seeds}" \
                           f"\n<b>├ Leechers:</b> {download.torrent_info().num_leechs}"
#                     msg += f'\n<b>├ TEngine: </b><a href="https://www.qbittorrent.org">qBittorrent</a>'
                except:
                    pass

            elif download.status() == MirrorStatus.STATUS_SEEDING:
                msg += f"\n<b>├ Size: </b>{download.size()}"
                msg += f"\n<b>├ Engine:</b> qBittorrent v4.4.2"
                msg += f"\n<b>├ Speed: </b>{get_readable_file_size(download.torrent_info().upspeed)}/s"
                msg += f"\n<b>├ Uploaded: </b>{get_readable_file_size(download.torrent_info().uploaded)}"
                msg += f"\n<b>├ Ratio: </b>{round(download.torrent_info().ratio, 3)}"
                msg += f"\n<b>├ Time: </b>{get_readable_time(download.torrent_info().seeding_time)}"
                msg += f"\n<b>├ Elapsed: </b>{get_readable_time(time() - download.message.date.timestamp())}"
#                 msg += f'\n<b>├ TEngine: </b><a href="https://www.qbittorrent.org">qBittorrent</a>'
                msg += f'\n<b>├ Added by:</b> <a href="https://t.me/c/{str(download.message.chat.id)[4:]}/{download.message.message_id}">{download.message.from_user.first_name}</a>'
            else:
                msg += f"\n<b>├ Size: </b>{download.size()}"
                msg += f"\n<b>├ Engine :</b> {download.eng()}"
            msg += f"\n<b>└ Stop:</b> <code>/{BotCommands.CancelMirror} {download.gid()}</code>"
            msg += "\n"
            if STATUS_LIMIT is not None and index == STATUS_LIMIT:
                break
        if len(msg) == 0:
            return None, None
        bmsg = f"\n▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n<b>CPU:</b> {cpu_percent()}% | <b>FREE:</b> {get_readable_file_size(disk_usage(DOWNLOAD_DIR).free)}"
        bmsg += f"\n<b>RAM:</b> {virtual_memory().percent}% | <b>UPTM:</b> {get_readable_time(time() - botStartTime)}"
        dlspeed_bytes = 0
        upspeed_bytes = 0
        for download in list(download_dict.values()):
            spd = download.speed()
            if download.status() == MirrorStatus.STATUS_DOWNLOADING:
                if 'K' in spd:
                    dlspeed_bytes += float(spd.split('K')[0]) * 1024
                elif 'M' in spd:
                    dlspeed_bytes += float(spd.split('M')[0]) * 1048576
            elif download.status() == MirrorStatus.STATUS_UPLOADING:
                if 'KB/s' in spd:
                    upspeed_bytes += float(spd.split('K')[0]) * 1024
                elif 'MB/s' in spd:
                    upspeed_bytes += float(spd.split('M')[0]) * 1048576
        bmsg += f"\n<b>DL:</b> {get_readable_file_size(dlspeed_bytes)}/s | <b>UL:</b> {get_readable_file_size(upspeed_bytes)}/s"
        
        buttons = ButtonMaker()
        buttons.sbutton("Stats", str(THREE))
        sbutton = InlineKeyboardMarkup(buttons.build_menu(1))

        if STATUS_LIMIT is not None and tasks > STATUS_LIMIT:
            msg += f"\n<b>Total Tasks:</b> {tasks}"
            buttons = ButtonMaker()
            buttons.sbutton("Prev", "status pre")
            buttons.sbutton(f"{PAGE_NO}/{pages}", str(THREE))
            buttons.sbutton("Next", "status nex")
            button = InlineKeyboardMarkup(buttons.build_menu(3))
            return msg + bmsg, button
        return msg + bmsg, sbutton

def turn(data):
    try:
        with download_dict_lock:
            global COUNT, PAGE_NO
            if data[1] == "nex":
                if PAGE_NO == pages:
                    COUNT = 0
                    PAGE_NO = 1
                else:
                    COUNT += STATUS_LIMIT
                    PAGE_NO += 1
            elif data[1] == "pre":
                if PAGE_NO == 1:
                    COUNT = STATUS_LIMIT * (pages - 1)
                    PAGE_NO = pages
                else:
                    COUNT -= STATUS_LIMIT
                    PAGE_NO -= 1
        return True
    except:
        return False

def get_readable_time(seconds: int) -> str:
    result = ''
    (days, remainder) = divmod(seconds, 86400)
    days = int(days)
    if days != 0:
        result += f'{days}d'
    (hours, remainder) = divmod(remainder, 3600)
    hours = int(hours)
    if hours != 0:
        result += f'{hours}h'
    (minutes, seconds) = divmod(remainder, 60)
    minutes = int(minutes)
    if minutes != 0:
        result += f'{minutes}m'
    seconds = int(seconds)
    result += f'{seconds}s'
    return result

def is_url(url: str):
    url = re_findall(URL_REGEX, url)
    return bool(url)

def is_gdrive_link(url: str):
    return "drive.google.com" in url

def is_gdtot_link(url: str):
    url = re_match(r'https?://.+\.gdtot\.\S+', url)
    return bool(url)

def is_appdrive_link(url: str):
    url = re_match(r'https?://(?:\S*\.)?(?:appdrive|driveapp)\.in/\S+', url)
    return bool(url)

def is_mega_link(url: str):
    return "mega.nz" in url or "mega.co.nz" in url

def get_mega_link_type(url: str):
    if "folder" in url:
        return "folder"
    elif "file" in url:
        return "file"
    elif "/#F!" in url:
        return "folder"
    return "file"

def is_magnet(url: str):
    magnet = re_findall(MAGNET_REGEX, url)
    return bool(magnet)

def new_thread(fn):
    """To use as decorator to make a function call threaded.
    Needs import
    from threading import Thread"""

    def wrapper(*args, **kwargs):
        thread = Thread(target=fn, args=args, kwargs=kwargs)
        thread.start()
        return thread

    return wrapper

def get_content_type(link: str) -> str:
    try:
        res = rhead(link, allow_redirects=True, timeout=5, headers = {'user-agent': 'Wget/1.12'})
        content_type = res.headers.get('content-type')
    except:
        try:
            res = urlopen(link, timeout=5)
            info = res.info()
            content_type = info.get_content_type()
        except:
            content_type = None
    return content_type

ONE, TWO, THREE = range(3)
def pop_up_stats(update, context):
    query = update.callback_query
    stats = bot_sys_stats()
    query.answer(text=stats, show_alert=True)
def bot_sys_stats():
    currentTime = get_readable_time(time() - botStartTime)
    cpu = psutil.cpu_percent()
    mem = psutil.virtual_memory().percent
    disk = psutil.disk_usage(DOWNLOAD_DIR).percent
    total, used, free = shutil.disk_usage(DOWNLOAD_DIR)
    total = get_readable_file_size(total)
    used = get_readable_file_size(used)
    free = get_readable_file_size(free)
    recv = get_readable_file_size(psutil.net_io_counters().bytes_recv)
    sent = get_readable_file_size(psutil.net_io_counters().bytes_sent)
    num_active = 0
    num_upload = 0
    num_split = 0
    num_extract = 0
    num_archi = 0
    tasks = len(download_dict)
    for stats in list(download_dict.values()):
       if stats.status() == MirrorStatus.STATUS_DOWNLOADING:
                num_active += 1
       if stats.status() == MirrorStatus.STATUS_UPLOADING:
                num_upload += 1
       if stats.status() == MirrorStatus.STATUS_ARCHIVING:
                num_archi += 1
       if stats.status() == MirrorStatus.STATUS_EXTRACTING:
                num_extract += 1
       if stats.status() == MirrorStatus.STATUS_SPLITTING:
                num_split += 1
    stats = f"""
BOT UPTIME: {currentTime}

CPU : {cpu}% || RAM : {mem}%

USED : {used} || FREE : {free}
T-DL : {recv} || T-UP : {sent}

ONGOING TASKS : {tasks}
DL : {num_active} || UP : {num_upload}
ZIP : {num_archi} || UNZIP : {num_extract} || SPLIT : {num_split}
"""
    return stats
dispatcher.add_handler(
    CallbackQueryHandler(pop_up_stats, pattern=f"^{str(THREE)}$")
)
