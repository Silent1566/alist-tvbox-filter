# alist-tvbox-filter

AList-TvBox `Atvp.py` 的过滤器示例。

每个过滤器都可以导出一个 `Filter` 类。运行时会按阶段调用对应方法：

- `detail(result, context)`：处理详情数据，例如 `vod_play_from` 和 `vod_play_url`
- `parse(result, context)`：处理解析后的详情数据
- `player(result, context)`：处理播放器内容
- `play(result, context)`：处理后端播放结果
- `danmaku(context)`：声明弹幕能力

返回修改后的结果。返回 `None` 表示保持上一阶段结果不变。

## 测试过滤器

在 `detail` 阶段使用 `detail/append-text.py`。它会给 `vod_play_url` 里的每个剧集标题追加 ` - text`，但不改变播放地址。

## TMDB 详情刮削过滤器

在 `detail` 阶段使用 `detail/tmdb-scraper.py`。它会根据 `vod_name` 搜索 TMDB，然后替换 `vod_name`、`vod_pic`、`vod_year`、`vod_actor`、`vod_director`、`vod_area`、`vod_lang`、`type_name`、`vod_content`、`vod_remarks` 等详情字段。

对于剧集结果，它还会加载季集数据，并把剧集标题改写为：

```text
第X集 TMDB集标题$播放地址
```

扩展配置可以是 JSON 对象：

```json
{
  "tmdb_api_key": "你的_TMDB_密钥",
  "language": "zh-CN",
  "fallback_language": "en-US",
  "type": "auto",
  "season": 1,
  "overwrite_episode_title": true,
  "timeout": 8
}
```

快速测试时，扩展配置也可以只填写 TMDB 密钥字符串。

## LogVar 弹幕

在 `player` 阶段使用 `player/logvar-danmaku.py`。它会从 Atvp 播放器上下文读取当前的 `vod_name`、剧集标题和剧集序号，匹配 LogVar 弹幕，并追加：

```json
{
  "danmaku": [
    {
      "name": "标题 - 剧集",
      "url": "http://host/key/api/v2/comment/123?format=xml"
    }
  ]
}
```

扩展配置：

```json
{
  "api_url": "http://127.0.0.1:9321",
  "token": "你的_LOGVAR_密钥",
  "timeout": 8,
  "format": "xml",
  "max_results": 1,
  "search_fallback": true
}
```

如果 `api_url` 已经包含 LogVar 密钥，可以省略 `token`。

## 不懂聚合

使用 `aggregate/不懂聚合.py` 作为组合过滤器。它会组合：

- `detail/tmdb-scraper.py`：用于 TMDB 详情刮削
- `player/logvar-danmaku.py`：用于 LogVar 弹幕

推荐阶段：

```text
detail,player,danmaku
```

它也实现了 `parse` 和 `play`，用于测试多阶段场景。选择 `detail` 时，`parse` 会直接透传，避免重复调用 TMDB。选择 `player` 时，`play` 会直接透传，避免重复匹配 LogVar。

过滤器 URL：

```text
https://raw.githubusercontent.com/Silent1566/alist-tvbox-filter/main/aggregate/不懂聚合.py
```

扩展配置：

```json
{
  "tmdb": {
    "tmdb_api_key": "你的_TMDB_密钥",
    "language": "zh-CN",
    "fallback_language": "en-US",
    "type": "auto",
    "season": 1,
    "overwrite_episode_title": true,
    "timeout": 8
  },
  "danmaku": {
    "api_url": "http://127.0.0.1:9321",
    "token": "你的_LOGVAR_密钥",
    "timeout": 8,
    "format": "xml",
    "max_results": 1,
    "search_fallback": true
  }
}
```

默认情况下，它会通过 GitHub 原始文件 URL 复用本仓库里的两个独立过滤器。高级用户可以覆盖来源：

```json
{
  "sources": {
    "tmdb": "https://raw.githubusercontent.com/Silent1566/alist-tvbox-filter/main/detail/tmdb-scraper.py",
    "logvar": "https://raw.githubusercontent.com/Silent1566/alist-tvbox-filter/main/player/logvar-danmaku.py"
  }
}
```
