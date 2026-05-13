# coding=utf-8
import json
import re
from urllib.parse import quote
from urllib.request import Request, urlopen


class Filter:
    """给 TvBox playerContent 结果追加 LogVar 弹幕条目。

    扩展配置可以是 JSON 对象：
    {
      "api_url": "http://127.0.0.1:9321",
      "token": "你的_LOGVAR_密钥",
      "timeout": 8,
      "format": "xml"
    }

    过滤器会从 Atvp 播放器上下文读取标题元数据。Atvp 会缓存
    detailContent 中的这些元数据，所以打开过详情页后，其他应用使用的
    订阅也能通过这个过滤器匹配弹幕。
    """

    def __init__(self):
        self.api_root = ""
        self.timeout = 8
        self.comment_format = "xml"
        self.max_results = 1
        self.search_fallback = True
        self.platform = ""
        self.replace = False

    def init(self, extend="", context=None):
        config = self._parse_config(extend)
        api_url = self._pick(config, "api_url", "apiUrl", "base_url", "baseUrl", "danmu_api", "danmuApi")
        token = self._pick(config, "token", "key", "api_key", "apiKey")
        if not api_url and isinstance(extend, str) and extend.strip().startswith(("http://", "https://")):
            api_url = extend.strip()

        self.api_root = self._build_api_root(api_url, token)
        self.timeout = self._to_int(config.get("timeout"), 8, 1, 30)
        self.comment_format = str(config.get("format") or "xml").strip() or "xml"
        self.max_results = self._to_int(config.get("max_results") or config.get("maxResults"), 1, 1, 5)
        self.search_fallback = self._to_bool(config.get("search_fallback", config.get("searchFallback", True)))
        self.platform = str(config.get("platform") or "").strip()
        self.replace = self._to_bool(config.get("replace", False))
        self._log("初始化完成 接口根地址=%s" % (self.api_root or "<空>"))

    def player(self, result, context=None):
        if not isinstance(result, dict):
            return result
        if not self.api_root:
            self._log("跳过：api_url 为空")
            return result

        meta = self._extract_meta(context or {})
        file_name = self._build_file_name(meta)
        if not file_name:
            self._log("跳过：播放器上下文中的 vod_name 为空")
            return result

        self._log("匹配 fileName=%s" % file_name)
        items = self._match(file_name)
        if not items and self.search_fallback:
            items = self._search(meta)
        if not items:
            self._log("没有匹配到弹幕")
            return result

        payload = dict(result)
        existing = payload.get("danmaku") if isinstance(payload.get("danmaku"), list) else []
        payload["danmaku"] = items if self.replace else self._merge_danmaku(existing, items)
        self._log("已添加弹幕数量=%s" % len(items))
        return payload

    def danmaku(self, context=None):
        return bool(self.api_root)

    def _parse_config(self, extend):
        if isinstance(extend, dict):
            return extend
        text = str(extend or "").strip()
        if not text:
            return {}
        try:
            parsed = json.loads(text)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}

    def _pick(self, data, *keys):
        for key in keys:
            value = data.get(key)
            if value not in (None, ""):
                return str(value).strip()
        return ""

    def _build_api_root(self, api_url, token):
        base = str(api_url or "").strip().rstrip("/")
        key = str(token or "").strip().strip("/")
        if not base:
            return ""

        suffix = "/api/v2"
        if base.endswith(suffix):
            prefix = base[:-len(suffix)].rstrip("/")
        else:
            prefix = base
        if key and not prefix.endswith("/" + key):
            prefix = prefix.rstrip("/") + "/" + key
        return prefix.rstrip("/") + suffix

    def _extract_meta(self, context):
        play = context.get("play") if isinstance(context.get("play"), dict) else {}
        merged = dict(play)
        merged.update({key: value for key, value in context.items() if key != "play"})
        return merged

    def _build_file_name(self, meta):
        vod_name = str(meta.get("vod_name") or meta.get("name") or "").strip()
        episode_name = str(meta.get("episode_name") or meta.get("episode") or "").strip()
        episode_index = self._to_int(meta.get("episode_index"), 0, 0, 9999)

        if not vod_name:
            return ""
        if not episode_name or episode_name in ("正片", "播放", "全集"):
            file_name = vod_name
        else:
            episode_number = self._extract_episode_number(episode_name) or episode_index
            if episode_number > 0:
                file_name = "%s S01E%s" % (vod_name, str(episode_number).zfill(2))
            else:
                file_name = "%s %s" % (vod_name, episode_name)

        if self.platform:
            file_name = "%s @%s" % (file_name, self.platform)
        return file_name.strip()

    def _extract_episode_number(self, title):
        text = str(title or "")
        match = re.search(r"第\s*([0-9]+)\s*[集话章节回期]", text)
        if match:
            return self._to_int(match.group(1), 0, 0, 9999)
        match = re.search(r"[Ss]\d{1,2}[-._\s]*[Ee](\d{1,4})", text)
        if match:
            return self._to_int(match.group(1), 0, 0, 9999)
        match = re.search(r"\b(?:EP|E)[-._\s]*(\d{1,4})\b", text, re.I)
        if match:
            return self._to_int(match.group(1), 0, 0, 9999)
        match = re.search(r"\b(\d{1,4})\b", text)
        if match:
            value = self._to_int(match.group(1), 0, 0, 9999)
            if value not in (480, 720, 1080, 2160):
                return value
        return 0

    def _match(self, file_name):
        data = self._request_json(
            self.api_root + "/match",
            method="POST",
            body={"fileName": file_name},
        )
        if not isinstance(data, dict) or not data.get("isMatched"):
            return []
        matches = data.get("matches")
        if not isinstance(matches, list):
            return []
        return self._items_from_matches(matches)

    def _search(self, meta):
        vod_name = str(meta.get("vod_name") or "").strip()
        episode_name = str(meta.get("episode_name") or "").strip()
        episode_number = self._extract_episode_number(episode_name)
        if not episode_number:
            episode_number = self._to_int(meta.get("episode_index"), 0, 0, 9999)
        if not vod_name:
            return []

        url = self.api_root + "/search/episodes?anime=" + quote(vod_name)
        if episode_number > 0:
            url += "&episode=" + quote(str(episode_number))
        data = self._request_json(url)
        matches = self._flatten_search_result(data)
        return self._items_from_matches(matches)

    def _flatten_search_result(self, data):
        if isinstance(data, list):
            return data
        if not isinstance(data, dict):
            return []
        if isinstance(data.get("episodes"), list):
            return data.get("episodes")
        animes = data.get("animes")
        if not isinstance(animes, list):
            return []
        episodes = []
        for anime in animes:
            if not isinstance(anime, dict):
                continue
            title = anime.get("animeTitle") or anime.get("title") or anime.get("name")
            for episode in anime.get("episodes") or []:
                if isinstance(episode, dict):
                    item = dict(episode)
                    item.setdefault("animeTitle", title)
                    episodes.append(item)
        return episodes

    def _items_from_matches(self, matches):
        items = []
        for match in matches:
            if not isinstance(match, dict):
                continue
            episode_id = match.get("episodeId") or match.get("epId") or match.get("id")
            if not episode_id:
                continue
            anime_title = match.get("animeTitle") or match.get("title") or match.get("name") or ""
            episode_title = match.get("episodeTitle") or match.get("epTitle") or ""
            name = self._danmaku_name(anime_title, episode_title)
            items.append({
                "name": name,
                "url": "%s/comment/%s?format=%s" % (self.api_root, episode_id, quote(self.comment_format)),
            })
            if len(items) >= self.max_results:
                break
        return items

    def _danmaku_name(self, anime_title, episode_title):
        anime = str(anime_title or "").strip()
        episode = str(episode_title or "").strip()
        if anime and episode:
            return "%s - %s" % (anime, episode)
        return anime or episode or "LogVar 弹幕"

    def _merge_danmaku(self, existing, additions):
        merged = list(existing)
        seen = set(str(item.get("url")) for item in merged if isinstance(item, dict))
        for item in additions:
            url = str(item.get("url") or "")
            if url and url not in seen:
                merged.append(item)
                seen.add(url)
        return merged

    def _request_json(self, url, method="GET", body=None):
        headers = {
            "Accept": "application/json",
            "User-Agent": "AList-TvBox-Filter/1.0",
        }
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        try:
            request = Request(url, data=data, headers=headers, method=method)
            with urlopen(request, timeout=self.timeout) as response:
                text = response.read().decode("utf-8", "ignore")
            return json.loads(text or "{}")
        except Exception as error:
            self._log("请求失败 url=%s 错误=%s" % (url, error))
            return None

    def _to_int(self, value, default, minimum, maximum):
        try:
            number = int(value)
        except Exception:
            number = default
        if number < minimum:
            return minimum
        if number > maximum:
            return maximum
        return number

    def _to_bool(self, value):
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in ("1", "true", "yes", "on")

    def _log(self, message):
        print("[logvar-danmaku] " + str(message))
