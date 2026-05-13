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

