# alist-tvbox-filter

Filter examples for AList-TvBox `Atvp.py`.

Each filter can export a `Filter` class. The runtime calls methods by stage:

- `detail(result, context)` for detail data such as `vod_play_from` and `vod_play_url`
- `parse(result, context)` for parsed detail data
- `player(result, context)` for player content
- `play(result, context)` for backend play results
- `danmaku(context)` for danmaku capability

Return the modified result. Return `None` to keep the previous result unchanged.

## Test Filter

Use `detail/append-text.py` with the `detail` stage. It appends ` - text` to each episode label in `vod_play_url` without changing the playback URL.

## TMDB Detail Scraper

Use `detail/tmdb-scraper.py` with the `detail` stage. It searches TMDB by `vod_name`, then replaces detail fields such as `vod_name`, `vod_pic`, `vod_year`, `vod_actor`, `vod_director`, `vod_area`, `vod_lang`, `type_name`, `vod_content`, and `vod_remarks`.

For TV results it also loads season episode data and rewrites episode labels to:

```text
第X集 TMDB集标题$播放地址
```

Extend config can be a JSON object:

```json
{
  "tmdb_api_key": "YOUR_TMDB_KEY",
  "language": "zh-CN",
  "fallback_language": "en-US",
  "type": "auto",
  "season": 1,
  "overwrite_episode_title": true,
  "timeout": 8
}
```

For quick testing, Extend config can also be just the TMDB key string.
