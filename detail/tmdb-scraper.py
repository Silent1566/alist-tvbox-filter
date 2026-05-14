# coding=utf-8
"""
AList-TvBox Atvp.py 的 TMDB 详情刮削过滤器。

推荐阶段：detail

扩展配置示例：

1. 最小配置：
   {"tmdb_api_key":"你的_TMDB_密钥"}

2. 完整配置：
   {
     "tmdb_api_key": "你的_TMDB_密钥",
     "language": "zh-CN",
     "fallback_language": "en-US",
     "type": "auto",
     "season": 1,
     "overwrite_episode_title": true,
     "timeout": 8
   }

也可以直接把密钥本身填进扩展配置，例如：
   你的_TMDB_密钥
"""

import json
import re
import time
from datetime import datetime
from urllib.parse import quote

import requests

FILTER_CONFIG_SCHEMA = {
    "source": "declared",
    "description": "用于补充影视条目的 TMDB 元数据，例如封面、年份、简介、演员与导演信息。",
    "allowAdditional": True,
    "singleValueKey": "tmdb_api_key",
    "example": {
        "tmdb_api_key": "your_tmdb_key",
        "language": "zh-CN",
        "fallback_language": "en-US",
        "type": "auto",
        "season": 1,
        "overwrite_episode_title": True,
        "timeout": 8,
        "debug": True
    },
    "fields": [
        {
            "key": "tmdb_api_key",
            "label": "TMDB Key",
            "type": "string",
            "required": True,
            "description": "TMDB API 密钥",
            "aliases": ["api_key", "key"],
            "placeholder": "请输入 TMDB API Key"
        },
        {
            "key": "language",
            "label": "语言",
            "type": "string",
            "required": False,
            "description": "TMDB 主查询语言，默认使用中文 zh-CN。",
            "defaultValue": "zh-CN"
        },
        {
            "key": "fallback_language",
            "label": "备用语言",
            "type": "string",
            "required": False,
            "description": "主语言信息不完整时，用这个语言补齐缺失文本，默认 en-US。",
            "defaultValue": "en-US"
        },
        {
            "key": "type",
            "label": "类型",
            "type": "string",
            "required": False,
            "description": "可填 auto、movie 或 tv。auto 会自动判断影视类型。",
            "defaultValue": "auto"
        },
        {
            "key": "season",
            "label": "季",
            "type": "number",
            "required": False,
            "description": "电视剧场景下可手动指定季号，用于改写对应季的剧集标题。"
        },
        {
            "key": "overwrite_episode_title",
            "label": "覆盖剧集标题",
            "type": "boolean",
            "required": False,
            "description": "是否使用 TMDB 的剧集标题覆盖原始播放列表标题，默认开启。",
            "defaultValue": True
        },
        {
            "key": "timeout",
            "label": "超时秒数",
            "type": "number",
            "required": False,
            "description": "请求 TMDB API 的超时秒数，默认 8 秒。",
            "defaultValue": 8
        },
        {
            "key": "debug",
            "label": "调试日志",
            "type": "boolean",
            "required": False,
            "description": "是否在运行时输出调试日志，默认开启。",
            "defaultValue": True
        }
    ]
}


class Filter:
    TMDB_API = "https://api.themoviedb.org/3"
    POSTER_PREFIX = "https://media.themoviedb.org/t/p/w300_and_h450_bestv2"

    def __init__(self):
        self.api_key = ""
        self.language = "zh-CN"
        self.fallback_language = "en-US"
        self.media_type = "auto"
        self.season = None
        self.overwrite_episode_title = True
        self.timeout = 8
        self.debug = True
        self._cache = {}

    def init(self, extend="", context=None):
        """从过滤器的扩展字段读取用户配置。

        Atvp.py 只会把过滤器级别的扩展数据传给这个方法。alist-tvbox 中保存的
        系统 TMDB 密钥不会暴露给订阅客户端，所以这个过滤器会在这里显式读取密钥。
        """
        config = self._parse_extend(extend)
        self.api_key = (
            self._string(config.get("tmdb_api_key"))
            or self._string(config.get("api_key"))
            or self._string(config.get("key"))
        )
        self.language = self._string(config.get("language")) or self.language
        self.fallback_language = self._string(config.get("fallback_language")) or self.fallback_language
        self.media_type = (self._string(config.get("type")) or self.media_type).lower()
        self.season = self._to_int(config.get("season"))
        self.overwrite_episode_title = self._to_bool(config.get("overwrite_episode_title"), True)
        self.timeout = self._to_int(config.get("timeout")) or self.timeout
        self.debug = self._to_bool(config.get("debug"), True)

        if not self.api_key:
            self._log("初始化：缺少 tmdb_api_key；将保留原始详情")
        else:
            self._log(
                "初始化：语言=%s 备用语言=%s 类型=%s 季=%s 改写剧集标题=%s"
                % (self.language, self.fallback_language, self.media_type, self.season, self.overwrite_episode_title)
            )

    def detail(self, result, context=None):
        """刮削详情接口返回的每个视频条目。"""
        if not isinstance(result, dict):
            self._log("详情：result 不是字典；跳过")
            return result
        if not self.api_key:
            return result

        vod_list = result.get("list")
        if not isinstance(vod_list, list):
            self._log("详情：result.list 不是列表；跳过")
            return result

        for vod in vod_list:
            if not isinstance(vod, dict):
                continue
            try:
                self._scrape_vod(vod)
            except Exception as exc:
                # 元数据刮削失败时，不影响播放流程。
                self._log("详情：%r 刮削失败：%s" % (vod.get("vod_name"), exc))
        return result

    def _scrape_vod(self, vod):
        original_name = self._string(vod.get("vod_name"))
        query_name = self._clean_query_name(original_name)
        if not query_name:
            self._log("刮削：vod_name 为空；跳过")
            return

        year = self._extract_year(vod)
        media = self._find_best_media(query_name, year)
        if not media:
            self._log("刮削：没有匹配到 TMDB 条目 名称=%r 年份=%r" % (query_name, year))
            return

        details = self._get_details(media["type"], media["id"])
        if not details:
            self._log("刮削：%s/%s 缺少详情" % (media["type"], media["id"]))
            return

        self._apply_details(vod, media["type"], details)
        if media["type"] == "tv" and self.overwrite_episode_title:
            self._apply_episode_titles(vod, details)

        self._log(
            "刮削：已匹配 %r -> %s/%s %r"
            % (original_name, media["type"], media["id"], self._title(details))
        )

    def _find_best_media(self, name, year=None):
        """自动类型时优先搜索剧集，因为这个过滤器通常用于剧集列表。"""
        if self.media_type in ("tv", "movie"):
            order = [self.media_type]
        else:
            order = ["tv", "movie"]

        for media_type in order:
            candidates = self._search(media_type, name, year)
            if candidates:
                return candidates[0]
        return None

    def _search(self, media_type, name, year=None):
        params = {
            "api_key": self.api_key,
            "language": self.language,
            "query": name,
        }
        if year:
            params["year" if media_type == "movie" else "first_air_date_year"] = str(year)

        data = self._get_json("/search/" + media_type, params)
        results = data.get("results") if isinstance(data, dict) else None
        if not isinstance(results, list):
            return []

        ranked = []
        normalized_query = self._normalize_name(name)
        for item in results:
            if not isinstance(item, dict) or not item.get("id"):
                continue
            title = self._title(item)
            score = 0
            if self._normalize_name(title) == normalized_query:
                score += 100
            if year and self._extract_year_from_date(item.get("release_date") or item.get("first_air_date")) == year:
                score += 20
            score += float(item.get("popularity") or 0) / 100
            ranked.append((score, {"type": media_type, "id": item["id"], "title": title}))

        ranked.sort(key=lambda pair: pair[0], reverse=True)
        self._log("搜索：%s %r 年份=%r -> %d 个结果" % (media_type, name, year, len(ranked)))
        return [item for _, item in ranked]

    def _get_details(self, media_type, tmdb_id):
        cache_key = ("details", media_type, tmdb_id, self.language)
        if cache_key in self._cache:
            return self._cache[cache_key]

        params = {
            "api_key": self.api_key,
            "language": self.language,
            "append_to_response": "credits",
        }
        details = self._get_json("/%s/%s" % (media_type, tmdb_id), params)

        # 中文字段不完整时保留原结构，并用备用语言补齐缺失文本。
        if self.fallback_language and self.fallback_language != self.language:
            fallback = self._get_json(
                "/%s/%s" % (media_type, tmdb_id),
                {
                    "api_key": self.api_key,
                    "language": self.fallback_language,
                    "append_to_response": "credits",
                },
            )
            details = self._merge_missing_text(details, fallback)

        self._cache[cache_key] = details
        return details

    def _get_season(self, tv_id, season_number):
        cache_key = ("season", tv_id, season_number, self.language)
        if cache_key in self._cache:
            return self._cache[cache_key]

        season = self._get_json(
            "/tv/%s/season/%s" % (tv_id, season_number),
            {
                "api_key": self.api_key,
                "language": self.language,
            },
        )
        if self.fallback_language and self.fallback_language != self.language:
            fallback = self._get_json(
                "/tv/%s/season/%s" % (tv_id, season_number),
                {
                    "api_key": self.api_key,
                    "language": self.fallback_language,
                },
            )
            season = self._merge_episode_titles(season, fallback)

        self._cache[cache_key] = season
        return season

    def _apply_details(self, vod, media_type, details):
        title = self._title(details)
        if title:
            vod["vod_name"] = title

        poster = self._string(details.get("poster_path"))
        if poster:
            vod["vod_pic"] = self.POSTER_PREFIX + poster

        year = self._extract_year_from_date(details.get("release_date") or details.get("first_air_date"))
        if year:
            vod["vod_year"] = str(year)

        score = details.get("vote_average")
        if score not in (None, "", 0, "0.0"):
            vod["vod_remarks"] = self._trim_score(score)

        genres = self._join_names(details.get("genres"))
        if genres:
            vod["type_name"] = genres

        countries = self._join_names(details.get("production_countries"))
        if countries:
            vod["vod_area"] = countries

        languages = self._join_names(details.get("spoken_languages"))
        if languages:
            vod["vod_lang"] = languages

        overview = self._string(details.get("overview"))
        if overview:
            vod["vod_content"] = overview

        credits = details.get("credits") if isinstance(details.get("credits"), dict) else {}
        actors = self._join_people(credits.get("cast"), limit=6)
        if actors:
            vod["vod_actor"] = actors

        directors = self._directors(details, media_type, credits)
        if directors:
            vod["vod_director"] = directors

    def _apply_episode_titles(self, vod, details):
        play_url = self._string(vod.get("vod_play_url"))
        if not play_url:
            return

        season_number = self.season or self._guess_season_number(vod, details)
        season = self._get_season(details.get("id"), season_number)
        episodes = season.get("episodes") if isinstance(season, dict) else None
        if not isinstance(episodes, list):
            self._log("剧集：tv=%s 季=%s 没有季集数据" % (details.get("id"), season_number))
            return

        title_map = {}
        for episode in episodes:
            if not isinstance(episode, dict):
                continue
            number = self._to_int(episode.get("episode_number"))
            title = self._string(episode.get("name"))
            if number and title:
                title_map[number] = title

        if not title_map:
            self._log("剧集：季=%s 没有可用标题" % season_number)
            return

        vod["vod_play_url"] = self._rewrite_play_url(play_url, title_map)
        self._log("剧集：已改写 %d 个剧集标题，季=%s" % (len(title_map), season_number))

    def _rewrite_play_url(self, play_url, title_map):
        return "$$$".join(self._rewrite_group(group, title_map) for group in play_url.split("$$$"))

    def _rewrite_group(self, group, title_map):
        return "#".join(self._rewrite_item(index, item, title_map) for index, item in enumerate(group.split("#"), start=1))

    def _rewrite_item(self, fallback_index, item, title_map):
        old_label, separator, url = item.partition("$")
        if not separator:
            return item
        episode_number = self._episode_number(old_label) or fallback_index
        scraped_title = self._string(title_map.get(episode_number))
        if scraped_title and not self._is_generic_episode_title(scraped_title, episode_number):
            return "第%s集 %s$%s" % (episode_number, scraped_title, url)
        return "第%s集$%s" % (episode_number, url)

    def _is_generic_episode_title(self, title, episode_number):
        text = self._string(title)
        if not text:
            return True

        normalized = re.sub(r"\s+", "", text).lower()
        patterns = [
            r"^第0*%s[集话話章节回期]?$" % episode_number,
            r"^episode0*%s$" % episode_number,
            r"^ep0*%s$" % episode_number,
            r"^e0*%s$" % episode_number,
        ]
        for pattern in patterns:
            if re.match(pattern, normalized, re.I):
                return True
        return False

    def _directors(self, details, media_type, credits):
        if media_type == "tv":
            creators = self._join_people(details.get("created_by"), limit=3)
            if creators:
                return creators

        crew = credits.get("crew") if isinstance(credits, dict) else None
        if not isinstance(crew, list):
            return ""

        names = []
        for person in crew:
            if not isinstance(person, dict):
                continue
            department = self._string(person.get("department"))
            job = self._string(person.get("job"))
            if department == "Directing" or job in ("Director", "Series Director"):
                name = self._string(person.get("name"))
                if name and name not in names:
                    names.append(name)
            if len(names) >= 3:
                break
        return ",".join(names)

    def _get_json(self, path, params):
        query = "&".join("%s=%s" % (quote(str(k)), quote(str(v))) for k, v in params.items() if v not in (None, ""))
        url = self.TMDB_API + path + "?" + query
        safe_url = re.sub(r"api_key=[^&]+", "api_key=***", url)
        self._log("请求：" + safe_url)

        response = requests.get(url, timeout=self.timeout)
        if response.status_code != 200:
            raise RuntimeError("TMDB HTTP %s：%s" % (response.status_code, response.text[:160]))
        time.sleep(0.05)
        return response.json()

    def _parse_extend(self, extend):
        if isinstance(extend, dict):
            return dict(extend)
        text = self._string(extend)
        if not text:
            return {}
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass
        return {"tmdb_api_key": text}

    def _merge_missing_text(self, primary, fallback):
        if not isinstance(primary, dict):
            return fallback if isinstance(fallback, dict) else {}
        if not isinstance(fallback, dict):
            return primary
        merged = dict(primary)
        for key in ("overview", "poster_path", "release_date", "first_air_date"):
            if not merged.get(key) and fallback.get(key):
                merged[key] = fallback[key]
        if not merged.get("credits") and fallback.get("credits"):
            merged["credits"] = fallback["credits"]
        return merged

    def _merge_episode_titles(self, primary, fallback):
        if not isinstance(primary, dict) or not isinstance(fallback, dict):
            return primary if isinstance(primary, dict) else {}
        episodes = primary.get("episodes")
        fallback_episodes = fallback.get("episodes")
        if not isinstance(episodes, list) or not isinstance(fallback_episodes, list):
            return primary
        fallback_map = {
            item.get("episode_number"): item
            for item in fallback_episodes
            if isinstance(item, dict) and item.get("episode_number")
        }
        for episode in episodes:
            if not isinstance(episode, dict) or episode.get("name"):
                continue
            fallback_episode = fallback_map.get(episode.get("episode_number"))
            if isinstance(fallback_episode, dict) and fallback_episode.get("name"):
                episode["name"] = fallback_episode["name"]
        return primary

    def _guess_season_number(self, vod, details):
        for value in (vod.get("vod_name"), vod.get("vod_id"), vod.get("path")):
            match = re.search(r"(?:S|Season|第)\s*0*(\d{1,2})\s*(?:季)?", self._string(value), re.I)
            if match:
                return int(match.group(1))

        seasons = details.get("seasons") if isinstance(details, dict) else None
        if isinstance(seasons, list):
            for season in seasons:
                if isinstance(season, dict) and season.get("season_number") == 1:
                    return 1
        return 1

    def _clean_query_name(self, name):
        value = self._string(name)
        value = re.sub(r"\[[^\]]+]", " ", value)
        value = re.sub(r"\([^)]*(?:\d{4}|[Ss]\d{1,2}|第\s*\d+\s*季)[^)]*\)", " ", value)
        value = re.sub(r"(?:第\s*\d+\s*季|[Ss]\d{1,2}|Season\s*\d+)", " ", value, flags=re.I)
        value = re.sub(r"\b(4K|8K|1080P|2160P|720P|WEB[- ]?DL|BluRay|HDR|DV|HEVC|H265|H264)\b", " ", value, flags=re.I)
        value = re.sub(r"\s+", " ", value).strip(" -_.")
        return value

    def _extract_year(self, vod):
        year = self._to_int(vod.get("vod_year"))
        if year:
            return year
        for value in (vod.get("vod_name"), vod.get("vod_remarks"), vod.get("path")):
            match = re.search(r"(19\d{2}|20\d{2})", self._string(value))
            if match:
                return int(match.group(1))
        return None

    def _episode_number(self, label):
        value = self._string(label)
        patterns = [
            r"第\s*0*(\d{1,4})\s*[集话話]",
            r"\bEP?\s*0*(\d{1,4})\b",
            r"\b0*(\d{1,4})\b",
        ]
        for pattern in patterns:
            match = re.search(pattern, value, re.I)
            if match:
                return int(match.group(1))
        return None

    def _title(self, item):
        if not isinstance(item, dict):
            return ""
        return self._string(item.get("name") or item.get("title") or item.get("original_name") or item.get("original_title"))

    def _join_names(self, items):
        if not isinstance(items, list):
            return ""
        names = []
        for item in items:
            if not isinstance(item, dict):
                continue
            name = self._string(item.get("name") or item.get("english_name"))
            if name and name not in names:
                names.append(name)
        return ",".join(names)

    def _join_people(self, items, limit=3):
        if not isinstance(items, list):
            return ""
        names = []
        for item in items:
            if not isinstance(item, dict):
                continue
            name = self._string(item.get("name"))
            if name and name not in names:
                names.append(name)
            if len(names) >= limit:
                break
        return ",".join(names)

    def _normalize_name(self, value):
        return re.sub(r"\s+", "", self._string(value)).lower()

    def _trim_score(self, value):
        try:
            text = "%.1f" % float(value)
        except Exception:
            text = self._string(value)
        return "" if text == "0.0" else text[:3]

    def _extract_year_from_date(self, value):
        text = self._string(value)
        if not text:
            return None
        try:
            return datetime.strptime(text[:10], "%Y-%m-%d").year
        except Exception:
            match = re.search(r"(19\d{2}|20\d{2})", text)
            return int(match.group(1)) if match else None

    def _string(self, value):
        return "" if value is None else str(value).strip()

    def _to_int(self, value):
        try:
            return int(str(value).strip())
        except Exception:
            return None

    def _to_bool(self, value, default=False):
        if value is None or value == "":
            return default
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in ("1", "true", "yes", "on")

    def _log(self, message):
        if self.debug:
            print("[tmdb-scraper] " + self._string(message))
