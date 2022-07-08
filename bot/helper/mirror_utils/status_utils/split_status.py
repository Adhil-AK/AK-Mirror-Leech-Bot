from bot.helper.ext_utils.bot_utils import get_readable_file_size, MirrorStatus, EngineStatus

class SplitStatus:
    def __init__(self, name, path, size, message):
        self.__name = name
        self.__path = path
        self.__size = size
        self.message = message

    def progress(self):
        return '0'

    def speed(self):
        return '0'

    def name(self):
        return self.__name

    def path(self):
        return self.__path

    def size(self):
        return get_readable_file_size(self.__size)

    def eta(self):
        return '0s'

    def status(self):
        return MirrorStatus.STATUS_SPLITTING

    def processed_bytes(self):
        return 0

    def eng(self):
        return EngineStatus.STATUS_SPLIT
