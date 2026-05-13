# coding=utf-8


class Filter:
    def __init__(self):
        self.suffix = " - text"

    def init(self, extend="", env=None):
        if isinstance(extend, str) and extend.strip():
            self.suffix = extend.strip()

    def detail(self, result, context=None):
        if not isinstance(result, dict):
            return result

        vod_list = result.get("list")
        if not isinstance(vod_list, list):
            return result

        for vod in vod_list:
            if not isinstance(vod, dict):
                continue
            play_url = vod.get("vod_play_url")
            if isinstance(play_url, str):
                vod["vod_play_url"] = self._rewrite_play_url(play_url)
        return result

    def _rewrite_play_url(self, play_url):
        return "$$$".join(self._rewrite_group(group) for group in play_url.split("$$$"))

    def _rewrite_group(self, group):
        return "#".join(self._rewrite_item(item) for item in group.split("#"))

    def _rewrite_item(self, item):
        name, separator, url = item.partition("$")
        if not separator or name.endswith(self.suffix):
            return item
        return f"{name}{self.suffix}${url}"

