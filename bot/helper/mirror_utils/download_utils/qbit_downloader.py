from os import path as ospath, listdir
from time import sleep, time
from re import search as re_search
from telegram import InlineKeyboardMarkup

from bot import TELEGRAPH_STYLE, download_dict, download_dict_lock, BASE_URL, get_client, TORRENT_DIRECT_LIMIT, ZIP_UNZIP_LIMIT, STOP_DUPLICATE, TORRENT_TIMEOUT, LOGGER, STORAGE_THRESHOLD, LEECH_LIMIT
from bot.helper.mirror_utils.status_utils.qbit_download_status import QbDownloadStatus
from bot.helper.mirror_utils.upload_utils.gdriveTools import GoogleDriveHelper
from bot.helper.telegram_helper.message_utils import sendMessage, sendMarkup, deleteMessage, sendStatusMessage, update_all_messages, sendFile
from bot.helper.ext_utils.bot_utils import get_readable_file_size, get_readable_time, setInterval, bt_selection_buttons
from bot.helper.ext_utils.fs_utils import clean_unwanted, get_base_name, check_storage_threshold
from bot.helper.telegram_helper import button_build


class QbDownloader:
    POLLING_INTERVAL = 3

    def __init__(self, listener):
        self.is_seeding = False
        self.ext_hash = ''
        self.client = get_client()
        self.__listener = listener
        self.__path = ''
        self.__name = ''
        self.__stalled_time = time()
        self.__uploaded = False
        self.__sizeChecked = False
        self.__dupChecked = False
        self.__rechecked = False
        self.__stopDup_check = False
        self.__select = False
        self.__periodic = None

    def add_qb_torrent(self, link, path, select, ratio, seed_time):
        self.__path = path
        self.__select = select
        try:
            op = self.client.torrents_add(link, save_path=path, tags=self.__listener.uid,
                                          ratio_limit=ratio, seeding_time_limit=seed_time,
                                          headers={'user-agent': 'Wget/1.12'})
            sleep(0.3)
            if op.lower() == "ok.":
                tor_info = self.client.torrents_info(tag=self.__listener.uid)
                if len(tor_info) == 0:
                    while True:
                        tor_info = self.client.torrents_info(tag=self.__listener.uid)
                        if len(tor_info) > 0:
                            break
                        elif time() - self.__stalled_time >= 12:
                            self.client.torrents_delete_tags(tags=self.__listener.uid)
                            msg = "This Torrent already added or not a torrent. If something wrong please report."
                            sendMessage(msg, self.__listener.bot, self.__listener.message)
                            self.client.auth_log_out()
                            return
            else:
                sendMessage("This is an unsupported/invalid link.", self.__listener.bot, self.__listener.message)
                self.client.auth_log_out()
                return
            tor_info = tor_info[0]
            self.__name = tor_info.name
            self.ext_hash = tor_info.hash
            with download_dict_lock:
                download_dict[self.__listener.uid] = QbDownloadStatus(self.__listener, self)
            self.__listener.onDownloadStart()
            LOGGER.info(f"QbitDownload started: {self.__name} - Hash: {self.ext_hash}")
            self.__periodic = setInterval(self.POLLING_INTERVAL, self.__qb_listener)
            if BASE_URL is not None and select:
                if link.startswith('magnet:'):
                    metamsg = "Downloading Metadata, wait then you can select files. Use torrent file to avoid this wait."
                    meta = sendMessage(metamsg, self.__listener.bot, self.__listener.message)
                    while True:
                        tor_info = self.client.torrents_info(torrent_hashes=self.ext_hash)
                        if len(tor_info) == 0:
                            deleteMessage(self.__listener.bot, meta)
                            return
                        try:
                            tor_info = tor_info[0]
                            if tor_info.state not in ["metaDL", "checkingResumeData", "pausedDL"]:
                                deleteMessage(self.__listener.bot, meta)
                                break
                        except:
                            return deleteMessage(self.__listener.bot, meta)
                self.client.torrents_pause(torrent_hashes=self.ext_hash)
                SBUTTONS = bt_selection_buttons(self.ext_hash)
                msg = "Your download paused. Choose files then press Done Selecting button to start downloading."
                sendMarkup(msg, self.__listener.bot, self.__listener.message, SBUTTONS)
            else:
                sendStatusMessage(self.__listener.message, self.__listener.bot)
        except Exception as e:
            sendMessage(str(e), self.__listener.bot, self.__listener.message)
            self.client.auth_log_out()

    def __qb_listener(self):
        try:
            tor_info = self.client.torrents_info(torrent_hashes=self.ext_hash)
            if len(tor_info) == 0:
                return
            tor_info = tor_info[0]
            if tor_info.state == "metaDL":
                self.__stalled_time = time()
                if TORRENT_TIMEOUT is not None and time() - tor_info.added_on >= TORRENT_TIMEOUT:
                    self.__onDownloadError("Dead Torrent!")
            elif tor_info.state == "downloading":
                self.__stalled_time = time()
                if not self.__stopDup_check and not self.__select and STOP_DUPLICATE and not self.__listener.isLeech:
                    LOGGER.info('Checking File/Folder if already in Drive')
                    qbname = tor_info.content_path.rsplit('/', 1)[-1].rsplit('.!qB', 1)[0]
                    if self.__listener.isZip:
                        qbname = f"{qbname}.zip"
                    elif self.__listener.extract:
                        try:
                            qbname = get_base_name(qbname)
                        except:
                            qbname = None
                    if qbname is not None:
                        if TELEGRAPH_STYLE is True:
                            qbmsg, button = GoogleDriveHelper().drive_list(qbname, True)
                            if qbmsg:
                                self.__onDownloadError("File/Folder is already available in Drive.")
                                sendMarkup("Here are the search results:", self.__listener.bot, self.__listener.message, button)
                        else:
                            cap, f_name = GoogleDriveHelper().drive_list(qbname, True)
                            if cap:
                                self.__onDownloadError("File/Folder is already available in Drive.")
                                cap = f"Here are the search results:\n\n{cap}"
                                sendFile(self.__listener.bot, self.__listener.message, f_name, cap)
                    self.__stopDup_check = True
                if not self.__sizeChecked:
                    size = tor_info.size
                    arch = any([self.__listener.isZip, self.__listener.extract])
                    if STORAGE_THRESHOLD is not None:
                        acpt = check_storage_threshold(size, arch)
                        if not acpt:
                            msg = f'You must leave {STORAGE_THRESHOLD}GB free storage.'
                            msg += f'\nYour File/Folder size is {get_readable_file_size(size)}'
                            self.__onDownloadError(msg)
                            return
                    limit = None
                    if ZIP_UNZIP_LIMIT is not None and arch:
                        mssg = f'Zip/Unzip limit is {ZIP_UNZIP_LIMIT}GB'
                        limit = ZIP_UNZIP_LIMIT
                    if LEECH_LIMIT is not None and self.__listener.isLeech:
                        mssg = f'Leech limit is {LEECH_LIMIT}GB'
                        limit = LEECH_LIMIT
                    elif TORRENT_DIRECT_LIMIT is not None:
                        mssg = f'Torrent limit is {TORRENT_DIRECT_LIMIT}GB'
                        limit = TORRENT_DIRECT_LIMIT
                    if limit is not None:
                        LOGGER.info('Checking File/Folder Size...')
                        if size > limit * 1024**3:
                            fmsg = f"{mssg}.\nYour File/Folder size is {get_readable_file_size(size)}"
                            self.__onDownloadError(fmsg)
                    self.__sizeChecked = True
            elif tor_info.state == "stalledDL":
                if not self.__rechecked and 0.99989999999999999 < tor_info.progress < 1:
                    msg = f"Force recheck - Name: {self.__name} Hash: "
                    msg += f"{self.ext_hash} Downloaded Bytes: {tor_info.downloaded} "
                    msg += f"Size: {tor_info.size} Total Size: {tor_info.total_size}"
                    LOGGER.info(msg)
                    self.client.torrents_recheck(torrent_hashes=self.ext_hash)
                    self.__rechecked = True
                elif TORRENT_TIMEOUT is not None and time() - self.__stalled_time >= TORRENT_TIMEOUT:
                    self.__onDownloadError("Dead Torrent!")
            elif tor_info.state == "missingFiles":
                self.client.torrents_recheck(torrent_hashes=self.ext_hash)
            elif tor_info.state == "error":
                self.__onDownloadError("No enough space for this torrent on device")
            elif (tor_info.state.lower().endswith("up") or tor_info.state == "uploading") and not self.__uploaded:
                self.__uploaded = True
                if not self.__listener.seed:
                    self.client.torrents_pause(torrent_hashes=self.ext_hash)
                if self.__select:
                    clean_unwanted(self.__path)
                self.__listener.onDownloadComplete()
                if self.__listener.seed:
                    with download_dict_lock:
                        if self.__listener.uid not in list(download_dict.keys()):
                            self.__remove_torrent()
                            return
                        download_dict[self.__listener.uid] = QbDownloadStatus(self.__listener, self)
                    self.is_seeding = True
                    update_all_messages()
                    LOGGER.info(f"Seeding started: {self.__name} - Hash: {self.ext_hash}")
                else:
                    self.__remove_torrent()
            elif tor_info.state == 'pausedUP' and self.__listener.seed:
                self.__listener.onUploadError(f"Seeding stopped with Ratio: {round(tor_info.ratio, 3)} and Time: {get_readable_time(tor_info.seeding_time)}")
                self.__remove_torrent()
            elif tor_info.state == 'pausedDL' and tor_info.completion_on != 0:
                # recheck torrent incase one of seed limits reached
                # sometimes it stuck on pausedDL from maxRatioAction but it should be pausedUP
                LOGGER.info("Recheck on complete manually! PausedDL")
                self.client.torrents_recheck(torrent_hashes=self.ext_hash)
        except Exception as e:
            LOGGER.error(str(e))

    def __onDownloadError(self, err):
        LOGGER.info(f"Cancelling Download: {self.__name}")
        self.client.torrents_pause(torrent_hashes=self.ext_hash)
        sleep(0.3)
        self.__listener.onDownloadError(err)
        self.__remove_torrent()

    def __remove_torrent(self):
        self.client.torrents_delete(torrent_hashes=self.ext_hash, delete_files=True)
        self.client.torrents_delete_tags(tags=self.__listener.uid)
        self.client.auth_log_out()
        self.__periodic.cancel()

    def cancel_download(self):
        if self.is_seeding:
            LOGGER.info(f"Cancelling Seed: {self.__name}")
            self.client.torrents_pause(torrent_hashes=self.ext_hash)
        else:
            self.__onDownloadError('Download stopped by user!')
