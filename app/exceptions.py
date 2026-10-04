class ClipScoutError(Exception):
    pass

class DiskQuotaExceeded(ClipScoutError):
    pass

class DuplicateVideoError(ClipScoutError):
    pass

class QualityRejected(ClipScoutError):
    def __init__(self, reason: str, title: str | None = None, channel: str | None = None):
        self.reason = reason
        self.title = title
        self.channel = channel
        super().__init__(reason)

class DownloadFailed(ClipScoutError):
    pass

class ScoutFailed(ClipScoutError):
    pass
