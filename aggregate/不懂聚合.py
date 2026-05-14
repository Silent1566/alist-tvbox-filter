# coding=utf-8
import json
import types
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen


DEFAULT_TMDB_SOURCE = "https://gh-proxy.org/raw.githubusercontent.com/Silent1566/alist-tvbox-filter/main/detail/tmdb-scraper.py"
DEFAULT_LOGVAR_SOURCE = "https://gh-proxy.org/raw.githubusercontent.com/Silent1566/alist-tvbox-filter/main/player/logvar-danmaku.py"

FILTER_CONFIG_SCHEMA = {
    "source": "declared",
    "description": "组合 TMDB 元数据刮削与 LogVar 弹幕能力的聚合过滤器，可统一在一个过滤器中完成详情与弹幕增强。",
    "allowAdditional": True,
    "example": {
        "enable_tmdb": True,
        "enable_danmaku": True,
        "load_timeout": 10,
        "tmdb": {
            "tmdb_api_key": "your_tmdb_key"
        },
        "danmaku": {
            "api_url": "http://127.0.0.1:9321",
            "token": "your_logvar_key"
        }
    },
    "fields": [
        {
            "key": "enable_tmdb",
            "label": "启用 TMDB",
            "type": "boolean",
            "required": False,
            "description": "是否启用 TMDB 详情刮削子过滤器，默认开启。",
            "aliases": ["enableTmdb"],
            "defaultValue": True
        },
        {
            "key": "enable_danmaku",
            "label": "启用弹幕",
            "type": "boolean",
            "required": False,
            "description": "是否启用 LogVar 弹幕子过滤器，默认开启。",
            "aliases": ["enableDanmaku"],
            "defaultValue": True
        },
        {
            "key": "load_timeout",
            "label": "加载超时",
            "type": "number",
            "required": False,
            "description": "下载并加载子过滤器脚本时的超时秒数，默认 10 秒。",
            "aliases": ["loadTimeout"],
            "defaultValue": 10
        },
        {
            "key": "tmdb_source",
            "label": "TMDB 来源",
            "type": "string",
            "required": False,
            "description": "可覆盖默认的 TMDB 子过滤器脚本地址或本地路径。",
            "aliases": ["tmdbSource"]
        },
        {
            "key": "logvar_source",
            "label": "弹幕来源",
            "type": "string",
            "required": False,
            "description": "可覆盖默认的 LogVar 子过滤器脚本地址或本地路径。",
            "aliases": ["logvarSource", "danmaku_source", "danmakuSource"]
        },
        {
            "key": "tmdb",
            "label": "TMDB 配置",
            "type": "object",
            "required": False,
            "description": "传递给 TMDB 子过滤器的嵌套配置对象。",
            "children": [
                {
                    "key": "tmdb_api_key",
                    "label": "TMDB Key",
                    "type": "string",
                    "required": True,
                    "description": "TMDB API 密钥。",
                    "aliases": ["api_key", "key"]
                },
                {
                    "key": "language",
                    "label": "语言",
                    "type": "string",
                    "required": False,
                    "defaultValue": "zh-CN"
                },
                {
                    "key": "fallback_language",
                    "label": "备用语言",
                    "type": "string",
                    "required": False,
                    "defaultValue": "en-US"
                },
                {
                    "key": "type",
                    "label": "类型",
                    "type": "string",
                    "required": False,
                    "defaultValue": "auto"
                },
                {
                    "key": "season",
                    "label": "季",
                    "type": "number",
                    "required": False
                },
                {
                    "key": "overwrite_episode_title",
                    "label": "覆盖剧集标题",
                    "type": "boolean",
                    "required": False,
                    "defaultValue": True
                },
                {
                    "key": "timeout",
                    "label": "超时秒数",
                    "type": "number",
                    "required": False,
                    "defaultValue": 8
                },
                {
                    "key": "debug",
                    "label": "调试日志",
                    "type": "boolean",
                    "required": False,
                    "defaultValue": True
                }
            ]
        },
        {
            "key": "danmaku",
            "label": "弹幕配置",
            "type": "object",
            "required": False,
            "description": "传递给 LogVar 弹幕子过滤器的嵌套配置对象。",
            "children": [
                {
                    "key": "api_url",
                    "label": "接口地址",
                    "type": "string",
                    "required": True,
                    "description": "LogVar 服务入口地址。",
                    "aliases": ["apiUrl", "base_url", "baseUrl", "danmu_api", "danmuApi"]
                },
                {
                    "key": "token",
                    "label": "令牌",
                    "type": "string",
                    "required": False,
                    "aliases": ["key", "api_key", "apiKey"]
                },
                {
                    "key": "timeout",
                    "label": "超时秒数",
                    "type": "number",
                    "required": False,
                    "defaultValue": 8
                },
                {
                    "key": "format",
                    "label": "弹幕格式",
                    "type": "string",
                    "required": False,
                    "defaultValue": "xml"
                },
                {
                    "key": "max_results",
                    "label": "最大结果数",
                    "type": "number",
                    "required": False,
                    "aliases": ["maxResults"],
                    "defaultValue": 1
                },
                {
                    "key": "search_fallback",
                    "label": "搜索回退",
                    "type": "boolean",
                    "required": False,
                    "aliases": ["searchFallback"],
                    "defaultValue": True
                },
                {
                    "key": "platform",
                    "label": "平台",
                    "type": "string",
                    "required": False
                },
                {
                    "key": "replace",
                    "label": "替换原播放项",
                    "type": "boolean",
                    "required": False,
                    "defaultValue": False
                }
            ]
        }
    ]
}


class Filter:
    """不懂聚合：组合 TMDB 详情刮削和 LogVar 弹幕。

    推荐阶段：detail、player、danmaku。
    可选阶段：parse、play。当已经选择 detail/player 时，它们会直接透传，
    避免重复运行。

    扩展配置：
    {
      "tmdb": {
        "tmdb_api_key": "你的_TMDB_密钥"
      },
      "danmaku": {
        "api_url": "http://127.0.0.1:9321",
        "token": "你的_LOGVAR_密钥"
      }
    }
    """

    def __init__(self):
        self._tmdb = None
        self._logvar = None
        self._tmdb_enabled = True
        self._logvar_enabled = True
        self._load_timeout = 10

    def init(self, extend="", context=None):
        config = self._parse_config(extend)
        self._load_timeout = self._to_int(config.get("load_timeout") or config.get("loadTimeout"), 10, 1, 30)
        self._tmdb_enabled = self._to_bool(config.get("enable_tmdb", config.get("enableTmdb", True)))
        self._logvar_enabled = self._to_bool(config.get("enable_danmaku", config.get("enableDanmaku", True)))

        tmdb_source = self._pick(config, "tmdb_source", "tmdbSource") or self._nested_pick(config, "sources", "tmdb")
        logvar_source = (
            self._pick(config, "logvar_source", "logvarSource", "danmaku_source", "danmakuSource")
            or self._nested_pick(config, "sources", "logvar")
            or self._nested_pick(config, "sources", "danmaku")
        )

        if self._tmdb_enabled:
            self._tmdb = self._load_filter(tmdb_source or DEFAULT_TMDB_SOURCE, "tmdb")
            if self._tmdb is not None:
                self._init_child(self._tmdb, self._child_config(config, "tmdb", extend), context)

        if self._logvar_enabled:
            self._logvar = self._load_filter(logvar_source or DEFAULT_LOGVAR_SOURCE, "logvar")
            if self._logvar is not None:
                self._init_child(self._logvar, self._child_config(config, "danmaku", extend, "logvar"), context)

        self._log("初始化完成 tmdb=%s logvar=%s" % (bool(self._tmdb), bool(self._logvar)))

    def detail(self, result, context=None):
        return self._call_child(self._tmdb, "detail", result, context)

    def parse(self, result, context=None):
        # Atvp 会在 parse 之后继续对已解析的分享详情运行 detail。
        # 如果也选择了 detail，parse 只做轻量透传，避免常见多阶段配置下重复请求 TMDB。
        stages = self._configured_stages(context)
        if "all" in stages or "detail" in stages:
            return result
        return self._call_child(self._tmdb, "detail", result, context)

    def player(self, result, context=None):
        return self._call_child(self._logvar, "player", result, context)

    def play(self, result, context=None):
        # 对后端播放结果来说，playerContent 之后仍会运行 player 阶段。
        # 只有用户选择了 play 但没有选择 player 时，才在这里执行。
        stages = self._configured_stages(context)
        if "all" in stages or "player" in stages:
            return result
        return self._call_child(self._logvar, "player", result, context)

    def danmaku(self, context=None):
        if self._logvar is None:
            return False
        method = getattr(self._logvar, "danmaku", None)
        if not callable(method):
            return True
        try:
            value = method(context)
            return True if value is None else bool(value)
        except Exception as error:
            self._log("logvar.danmaku 调用失败：%s" % error)
            return False

    def _child_config(self, config, key, original_extend, alias=None):
        child = config.get(key)
        if child is None and alias:
            child = config.get(alias)
        if isinstance(child, dict):
            return json.dumps(child, ensure_ascii=False)
        if not isinstance(config, dict) or not config:
            return original_extend

        if key == "tmdb":
            keys = (
                "tmdb_api_key", "tmdbApiKey", "api_key", "apiKey", "language",
                "fallback_language", "fallbackLanguage", "type", "season",
                "overwrite_episode_title", "overwriteEpisodeTitle", "timeout",
            )
        else:
            keys = (
                "api_url", "apiUrl", "base_url", "baseUrl", "danmu_api",
                "danmuApi", "token", "key", "api_key", "apiKey", "timeout",
                "format", "max_results", "maxResults", "search_fallback",
                "searchFallback", "platform", "replace",
            )
        payload = {name: config.get(name) for name in keys if name in config}
        return json.dumps(payload, ensure_ascii=False)

    def _load_filter(self, source, label):
        try:
            source_text = self._load_source(source)
            module = types.ModuleType("budong_%s_filter" % label)
            exec(compile(source_text, "<budong-%s>" % label, "exec"), module.__dict__)
            filter_cls = getattr(module, "Filter", None) or getattr(module, "Decorator", None)
            if filter_cls is None:
                self._log("%s 来源中没有 Filter/Decorator 类" % label)
                return None
            return filter_cls()
        except Exception as error:
            self._log("加载 %s 失败：%s" % (label, error))
            return None

    def _load_source(self, source):
        target = self._normalize_source(source)
        if target.startswith(("http://", "https://")):
            request = Request(target, headers={"User-Agent": "AList-TvBox-Filter/1.0"})
            with urlopen(request, timeout=self._load_timeout) as response:
                return response.read().decode("utf-8", "ignore")

        path = Path(target)
        if not path.is_file():
            raise FileNotFoundError(target)
        return path.read_text(encoding="utf-8")

    def _normalize_source(self, source):
        value = str(source or "").strip()
        if "github.com" in value and "/blob/" in value:
            parsed = urlparse(value)
            path = parsed.path.strip("/")
            parts = path.split("/")
            if len(parts) >= 5 and parts[2] == "blob":
                owner, repo, branch = parts[0], parts[1], parts[3]
                file_path = "/".join(parts[4:])
                return "https://gh-proxy.org/raw.githubusercontent.com/%s/%s/%s/%s" % (owner, repo, branch, file_path)
        return value

    def _init_child(self, child, extend, context):
        method = getattr(child, "init", None)
        if callable(method):
            method(extend, context)

    def _call_child(self, child, method_name, result, context):
        if child is None:
            return result
        method = getattr(child, method_name, None)
        if not callable(method):
            return result
        try:
            value = method(result, context)
            return result if value is None else value
        except Exception as error:
            self._log("%s.%s 调用失败：%s" % (child.__class__.__name__, method_name, error))
            return result

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
            return {"tmdb_api_key": text}

    def _configured_stages(self, context):
        filter_info = (context or {}).get("filter")
        stages = filter_info.get("stages") if isinstance(filter_info, dict) else []
        if isinstance(stages, str):
            stages = stages.split(",")
        if not isinstance(stages, (list, tuple)):
            return []
        return [str(stage or "").strip() for stage in stages]

    def _pick(self, data, *keys):
        for key in keys:
            value = data.get(key)
            if value not in (None, ""):
                return str(value).strip()
        return ""

    def _nested_pick(self, data, parent, key):
        value = data.get(parent)
        if not isinstance(value, dict):
            return ""
        item = value.get(key)
        return str(item).strip() if item not in (None, "") else ""

    def _to_bool(self, value):
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() not in ("0", "false", "no", "off")

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

    def _log(self, message):
        print("[不懂聚合] " + str(message))
