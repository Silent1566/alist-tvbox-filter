# coding=utf-8
"""tmdb-scraper C16 生产者合同的本地回归测试（不访问真实 TMDB）。"""

import copy
import importlib.util
import json
import os
import unittest
from urllib.parse import parse_qs, urlparse


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPEC = importlib.util.spec_from_file_location("tmdb_scraper", os.path.join(ROOT, "tmdb-scraper.py"))
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class FakeResponse:
    status_code = 200
    text = "ok"

    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


def movie_detail():
    return {
        "id": 550,
        "title": "Fight Club",
        "original_title": "Fight Club",
        "overview": "Overview",
        "tagline": "Tag",
        "status": "Released",
        "poster_path": "/poster.jpg",
        "backdrop_path": "/backdrop.jpg",
        "release_date": "1999-10-15",
        "vote_average": 8.4,
        "vote_count": 28000,
        "genres": [{"id": 18, "name": "Drama"}],
        "origin_country": ["US"],
        "original_language": "en",
        "runtime": 139,
        "images": {"backdrops": [{"file_path": "/b2.jpg"}], "posters": [{"file_path": "/p2.jpg"}]},
        "credits": {
            "cast": [{"id": 1, "name": "Actor", "character": "Role", "profile_path": "/a.jpg"}],
            "crew": [{"id": 2, "name": "Director", "job": "Director", "department": "Directing"}],
        },
        "external_ids": {"imdb_id": "tt0137523"},
        "videos": {"results": [{"id": "v1", "key": "abc", "site": "YouTube", "type": "Trailer", "name": "Trailer"}]},
        "recommendations": {"page": 1, "results": [{"id": 11, "title": "Rec", "media_type": "movie", "release_date": "2000-01-01", "vote_average": 7.0}]},
        "similar": {"page": 1, "results": []},
        "translations": {"translations": []},
        "release_dates": {"results": []},
    }


def tv_detail():
    return {
        "id": 1399,
        "name": "Game of Thrones",
        "original_name": "Game of Thrones",
        "overview": "TV overview",
        "poster_path": "/tv-poster.jpg",
        "backdrop_path": "/tv-backdrop.jpg",
        "first_air_date": "2011-04-17",
        "vote_average": 8.4,
        "vote_count": 20000,
        "genres": [{"id": 10765, "name": "Sci-Fi"}],
        "origin_country": ["US"],
        "original_language": "en",
        "number_of_seasons": 8,
        "number_of_episodes": 73,
        "episode_run_time": [57],
        "images": {"backdrops": [{"file_path": "/tv-b2.jpg"}], "posters": [{"file_path": "/tv-p2.jpg"}]},
        "credits": {"cast": [{"id": 1, "name": "Movie Cast", "character": "X"}], "crew": []},
        "aggregate_credits": {
            "cast": [{"id": 3, "name": "TV Cast", "roles": [{"character": "Lead"}]}],
            "crew": [{"id": 4, "name": "Show Runner", "jobs": [{"job": "Executive Producer"}]}],
        },
        "external_ids": {"imdb_id": "tt0944947"},
        "videos": {"results": [{"id": "tv-v1", "key": "tvt", "site": "YouTube", "type": "Trailer", "name": "TV Trailer"}]},
        "recommendations": {"page": 1, "results": []},
        "similar": {"page": 1, "results": []},
        "translations": {"translations": []},
        "content_ratings": {"results": []},
        "seasons": [
            {
                "id": 3624,
                "season_number": 1,
                "episode_count": 10,
                "name": "Season 1",
                "poster_path": "/season1.jpg",
                "images": {"backdrops": [{"file_path": "/s-b.jpg"}], "posters": [{"file_path": "/s-p.jpg"}]},
                "credits": {"cast": [{"id": 3, "name": "TV Cast", "character": "Lead"}], "crew": []},
                "videos": {"results": [{"id": "s-v1", "key": "sv", "site": "YouTube", "type": "Trailer", "name": "Season 1 Trailer"}]},
                "episodes": [
                    {
                        "id": 63056,
                        "episode_number": 1,
                        "name": "Winter Is Coming",
                        "overview": "Episode overview",
                        "still_path": "/e1.jpg",
                        "air_date": "2011-04-17",
                        "vote_average": 8.0,
                        "runtime": 62,
                        "videos": {"results": []},
                    }
                ],
            }
        ],
    }


def payload_size(payload):
    return len(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


class FakeRequests:
    def __init__(self, detail, season=None):
        self.detail = detail
        self.season = season
        self.calls = []

    def get(self, url, timeout=None):
        self.calls.append(url)
        if "/search/" in url:
            payload = copy.deepcopy(self.detail)
            payload["id"] = self.detail.get("id", 550)
            payload["media_type"] = "tv" if payload.get("name") else "movie"
            return FakeResponse({"results": [payload]})
        if "/episode/" in url and url.endswith("/videos"):
            return FakeResponse({"results": []})
        if "/season/" in url:
            return FakeResponse(self.season if self.season is not None else {})
        return FakeResponse(self.detail)


class TmdbScraperC16Test(unittest.TestCase):

    def make_filter(self, media_type="movie", detail=None, season=None):
        scraper = MODULE.Filter()
        scraper.debug = False
        scraper.api_key = "test"
        scraper.media_type = media_type
        scraper.fallback_language = ""
        scraper._requests = FakeRequests(detail if detail is not None else movie_detail(), season)
        return scraper

    def test_movie_payload_contains_identity_and_capabilities(self):
        scraper = self.make_filter()
        vod = {"vod_name": "Fight Club", "vod_year": "1999", "vod_play_url": "正片$http://example/movie.m3u8"}
        scraper.detail({"list": [vod]})
        payload = vod.get("tmdb")
        self.assertIsNotNone(payload)
        self.assertEqual(payload["schema"], 1)
        self.assertEqual(payload["id"], 550)
        self.assertEqual(payload["media_type"], "movie")
        self.assertEqual(payload["season_number"], 0)
        self.assertTrue(payload["complete"])
        for group in ("core", "credits", "images", "external_ids", "videos", "recommendations", "similar"):
            self.assertIn(group, payload["complete"])
        self.assertEqual(payload["detail"]["id"], 550)
        self.assertEqual(payload["detail"]["credits"]["cast"][0]["name"], "Actor")
        self.assertTrue(payload["fetched_at"].endswith("Z"))

    def test_tv_payload_embeds_selected_season_and_episode(self):
        detail = tv_detail()
        season = copy.deepcopy(detail["seasons"][0])
        season["season_number"] = 1
        scraper = self.make_filter(media_type="tv", detail=detail, season=season)
        vod = {"vod_name": "Game of Thrones S01", "vod_year": "2011", "vod_play_url": "第1集$http://example/1.m3u8"}
        scraper.detail({"list": [vod]})
        payload = vod["tmdb"]
        self.assertEqual(payload["media_type"], "tv")
        self.assertEqual(payload["season_number"], 1)
        self.assertIn("season:1", payload["complete"])
        self.assertIn("season_videos:1", payload["complete"])
        embedded = payload["detail"]["seasons"][0]
        self.assertEqual(embedded["season_number"], 1)
        self.assertEqual(embedded["episodes"][0]["name"], "Winter Is Coming")
        self.assertEqual(embedded["credits"]["cast"][0]["name"], "TV Cast")

    def test_gap_fill_only_requests_missing_detail_groups(self):
        detail = copy.deepcopy(movie_detail())
        detail.pop("external_ids")
        detail.pop("recommendations")
        scraper = self.make_filter(detail=detail)
        scraper._requests = FakeRequests(detail)
        original = scraper._get_json

        def fake_get(path, params):
            scraper._requests.calls.append(path)
            if path.endswith("/external_ids"):
                return {"imdb_id": "tt0137523"}
            if path.endswith("/recommendations"):
                return {"page": 1, "results": []}
            return original(path, params)

        scraper._get_json = fake_get
        vod = {"vod_name": "Fight Club", "vod_year": "1999", "vod_play_url": "正片$http://example/movie.m3u8"}
        scraper.detail({"list": [vod]})
        payload = vod["tmdb"]
        self.assertIn("external_ids", payload["complete"])
        self.assertIn("recommendations", payload["complete"])
        self.assertEqual(payload["detail"]["external_ids"]["imdb_id"], "tt0137523")
        requested = [url for url in scraper._requests.calls if url.endswith(("/external_ids", "/recommendations"))]
        self.assertEqual(len(requested), 2)

    def test_failed_group_is_not_declared_complete(self):
        detail = copy.deepcopy(movie_detail())
        detail.pop("external_ids")
        scraper = self.make_filter(detail=detail)
        original = scraper._get_json

        def fake_get(path, params):
            if path.endswith("/external_ids"):
                raise RuntimeError("boom")
            return original(path, params)

        scraper._get_json = fake_get
        vod = {"vod_name": "Fight Club", "vod_year": "1999", "vod_play_url": "正片$http://example/movie.m3u8"}
        scraper.detail({"list": [vod]})
        payload = vod["tmdb"]
        self.assertNotIn("external_ids", payload["complete"])
        self.assertNotIn("external_ids", payload["detail"])

    def test_payload_can_be_disabled(self):
        scraper = self.make_filter()
        scraper.include_tmdb_payload = False
        vod = {"vod_name": "Fight Club", "vod_year": "1999", "vod_play_url": "正片$http://example/movie.m3u8"}
        scraper.detail({"list": [vod]})
        self.assertNotIn("tmdb", vod)
        self.assertEqual(vod["vod_name"], "Fight Club")

    def test_disabled_payload_keeps_flat_fields_and_skips_c16_requests(self):
        scraper = self.make_filter()
        scraper.include_tmdb_payload = False
        original = scraper._get_json

        def fake_get(path, params):
            scraper._requests.calls.append(path)
            if path.endswith(("/external_ids", "/recommendations", "/similar")):
                raise AssertionError("C16 disabled should not request optional groups")
            return original(path, params)

        scraper._get_json = fake_get
        vod = {
            "vod_name": "Fight Club",
            "vod_year": "1999",
            "vod_play_url": "正片$http://example/movie.m3u8",
        }
        scraper.detail({"list": [vod]})
        self.assertEqual(vod["vod_name"], "Fight Club")
        self.assertEqual(vod["vod_actor"], "Actor")
        self.assertNotIn("tmdb", vod)
        detail_urls = [
            url for url in scraper._requests.calls
            if url.startswith("http") and "/movie/550" in url and "/search/" not in url
        ]
        self.assertEqual(len(detail_urls), 1)
        query = parse_qs(urlparse(detail_urls[0]).query)
        self.assertEqual(query.get("append_to_response"), ["credits"])

    def test_disabled_payload_uses_lightweight_tv_season_request(self):
        detail = tv_detail()
        season = copy.deepcopy(detail["seasons"][0])
        scraper = self.make_filter(media_type="tv", detail=detail, season=season)
        scraper.include_tmdb_payload = False
        vod = {"vod_name": "Game of Thrones S01", "vod_year": "2011", "vod_play_url": "第1集$http://example/1.m3u8"}
        scraper.detail({"list": [vod]})

        season_urls = [url for url in scraper._requests.calls if "/season/1" in url and "/episode/" not in url]
        self.assertEqual(len(season_urls), 1)
        query = parse_qs(urlparse(season_urls[0]).query)
        self.assertNotIn("append_to_response", query)
        self.assertNotIn("tmdb", vod)

    def test_detail_fallback_failure_keeps_primary_result(self):
        scraper = self.make_filter()
        scraper.fallback_language = "en-US"
        original_get = scraper._requests.get

        def fake_get(url, timeout=None):
            if "/movie/550" in url and "language=en-US" in url:
                raise RuntimeError("fallback down")
            return original_get(url, timeout)

        scraper._requests.get = fake_get
        vod = {"vod_name": "Fight Club", "vod_year": "1999", "vod_play_url": "正片$http://example/movie.m3u8"}
        scraper.detail({"list": [vod]})

        self.assertEqual(vod["vod_name"], "Fight Club")
        self.assertEqual(vod["vod_actor"], "Actor")
        self.assertEqual(vod["tmdb"]["id"], 550)

    def test_season_fallback_failure_keeps_primary_season(self):
        detail = tv_detail()
        season = copy.deepcopy(detail["seasons"][0])
        scraper = self.make_filter(media_type="tv", detail=detail, season=season)
        scraper.fallback_language = "en-US"
        original_get = scraper._requests.get

        def fake_get(url, timeout=None):
            if "/season/1" in url and "/episode/" not in url and "language=en-US" in url:
                raise RuntimeError("season fallback down")
            return original_get(url, timeout)

        scraper._requests.get = fake_get
        vod = {"vod_name": "Game of Thrones S01", "vod_year": "2011", "vod_play_url": "第1集$http://example/1.m3u8"}
        scraper.detail({"list": [vod]})

        payload = vod["tmdb"]
        self.assertIn("season:1", payload["complete"])
        self.assertEqual(payload["detail"]["seasons"][0]["episodes"][0]["name"], "Winter Is Coming")
        self.assertEqual(vod["vod_play_url"], "第1集 Winter Is Coming$http://example/1.m3u8")

    def test_poster_paths_do_not_claim_images_without_images_payload(self):
        detail = movie_detail()
        detail.pop("images")
        scraper = self.make_filter(detail=detail)
        vod = {"vod_name": "Fight Club", "vod_year": "1999", "vod_play_url": "正片$http://example/movie.m3u8"}
        scraper.detail({"list": [vod]})

        self.assertTrue(any("/movie/550/images" in url for url in scraper._requests.calls))
        self.assertNotIn("images", vod["tmdb"]["complete"])

    def test_failed_season_is_not_declared_complete(self):
        detail = tv_detail()
        detail["seasons"][0].pop("episodes")
        detail["seasons"][0].pop("credits")
        detail["seasons"][0].pop("images")
        detail["seasons"][0].pop("videos")
        scraper = self.make_filter(media_type="tv", detail=detail, season=None)
        scraper._requests.season = {}
        original = scraper._get_json

        def boom(path, params):
            if "/season/" in path:
                raise RuntimeError("season down")
            return original(path, params)

        scraper._get_json = boom
        vod = {"vod_name": "Game of Thrones S01", "vod_year": "2011", "vod_play_url": "第1集$http://example/1.m3u8"}
        scraper.detail({"list": [vod]})
        payload = vod.get("tmdb")
        self.assertIsNotNone(payload)
        self.assertNotIn("season:1", payload.get("complete", []))
        self.assertNotIn("season_videos:1", payload.get("complete", []))

    def test_detail_failure_keeps_original_vod(self):
        scraper = self.make_filter()

        def boom(url, timeout=None):
            raise RuntimeError("network down")

        scraper._requests.get = boom
        vod = {"vod_name": "Fight Club", "vod_year": "1999", "vod_content": "source overview"}
        result = scraper.detail({"list": [vod]})
        self.assertEqual(result["list"][0]["vod_content"], "source overview")
        self.assertNotIn("tmdb", vod)

    def test_oversized_payload_trims_optional_groups_and_claims(self):
        scraper = self.make_filter()
        payload = {
            "schema": 1,
            "id": 550,
            "media_type": "movie",
            "season_number": 0,
            "language": "zh-CN",
            "fetched_at": "2026-09-19T00:00:00Z",
            "complete": ["core", "credits", "images", "similar", "recommendations", "videos"],
            "detail": {
                "id": 550,
                "title": "Large",
                "overview": "Overview",
                "release_date": "1999-10-15",
                "vote_average": 8.4,
                "genres": [],
                "poster_path": "/p.jpg",
                "backdrop_path": "/b.jpg",
                "similar": {"page": 1, "results": [{"blob": "x" * 300000}]},
                "recommendations": {"page": 1, "results": [{"blob": "x" * 300000}]},
                "videos": {"results": [{"blob": "x" * 300000}]},
                "images": {"backdrops": [], "posters": [{"blob": "x" * 300000}]},
            },
        }
        trimmed = scraper._trim_tmdb_payload(payload)
        self.assertIsNotNone(trimmed)
        self.assertLessEqual(payload_size(trimmed), 2 * 1024 * 1024)
        for field in ("similar", "recommendations", "videos", "images"):
            if field not in trimmed["detail"]:
                self.assertNotIn(field, trimmed["complete"])
        self.assertIn("core", trimmed["complete"])

    def test_oversized_multibyte_payload_uses_utf8_byte_limit(self):
        scraper = self.make_filter()
        payload = {
            "schema": 1,
            "id": 550,
            "media_type": "movie",
            "season_number": 0,
            "complete": ["core", "similar"],
            "detail": {
                "id": 550,
                "title": "大详情",
                "overview": "概览",
                "genres": [],
                "similar": {"page": 1, "results": [{"overview": "中" * 700000}]},
            },
        }
        trimmed = scraper._trim_tmdb_payload(payload)
        self.assertIsNotNone(trimmed)
        self.assertLessEqual(payload_size(trimmed), 2 * 1024 * 1024)
        self.assertNotIn("similar", trimmed["detail"])
        self.assertNotIn("similar", trimmed["complete"])

    def test_episode_video_limit_fetches_only_requested_count(self):
        detail = tv_detail()
        season = copy.deepcopy(detail["seasons"][0])
        season["episodes"].append({
            "episode_number": 2,
            "name": "Episode 2",
            "overview": "Second",
            "still_path": "/e2.jpg",
            "air_date": "2011-04-24",
        })
        scraper = self.make_filter(media_type="tv", detail=detail, season=season)
        scraper.episode_video_limit = 1
        original_get = scraper._requests.get

        def fake_get(url, timeout=None):
            if "/episode/1/videos" in url:
                return FakeResponse({"results": [{"id": "ev", "key": "evk", "site": "YouTube", "type": "Clip", "name": "Episode Clip"}]})
            if "/episode/2/videos" in url:
                raise AssertionError("episode video limit should stop at one episode")
            return original_get(url, timeout)

        scraper._requests.get = fake_get
        vod = {"vod_name": "Game of Thrones S01", "vod_year": "2011", "vod_play_url": "第1集$http://example/1.m3u8"}
        scraper.detail({"list": [vod]})
        payload = vod["tmdb"]
        self.assertIn("episode_videos:1:1", payload["complete"])
        self.assertNotIn("episode_videos:1:2", payload["complete"])
        embedded = payload["detail"]["seasons"][0]["episodes"][0]
        self.assertEqual(embedded["videos"]["results"][0]["id"], "ev")

    def test_episode_video_request_budget_counts_empty_results(self):
        detail = tv_detail()
        season = copy.deepcopy(detail["seasons"][0])
        season["episodes"].append({
            "episode_number": 2,
            "name": "Episode 2",
            "overview": "Second",
            "still_path": "/e2.jpg",
            "air_date": "2011-04-24",
        })
        scraper = self.make_filter(media_type="tv", detail=detail, season=season)
        scraper.episode_video_limit = 1
        original_get = scraper._requests.get

        def fake_get(url, timeout=None):
            if "/episode/1/videos" in url:
                scraper._requests.calls.append(url)
                return FakeResponse({"results": []})
            if "/episode/2/videos" in url:
                scraper._requests.calls.append(url)
                raise AssertionError("episode request budget should count empty results")
            return original_get(url, timeout)

        scraper._requests.get = fake_get
        vod = {"vod_name": "Game of Thrones S01", "vod_year": "2011", "vod_play_url": "第1集$http://example/1.m3u8"}
        scraper.detail({"list": [vod]})

        episode_urls = [url for url in scraper._requests.calls if url.startswith("http") and "/episode/" in url and "/videos?" in url]
        self.assertEqual(len(episode_urls), 1)
        self.assertIn("/episode/1/videos", episode_urls[0])


if __name__ == "__main__":
    unittest.main()
