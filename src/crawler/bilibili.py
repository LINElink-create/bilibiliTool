from __future__ import annotations

from contextlib import suppress

from src.models.entities import VideoItem
from utils.bilibili_spider import Bilibili_Spider


class BilibiliCrawler:
    def __init__(self, save_dir: str = "json", wait_seconds: int = 2, save_by_page: bool = False) -> None:
        self.save_dir = save_dir
        self.wait_seconds = wait_seconds
        self.save_by_page = save_by_page

    def crawl_uid(self, uid: str, include_detail: bool = False) -> list[VideoItem]:
        spider = Bilibili_Spider(uid, self.save_dir, self.save_by_page, self.wait_seconds)
        try:
            page_num, user_name = spider.get_page_num()
            while page_num == 0:
                page_num, user_name = spider.get_page_num()

            videos: list[VideoItem] = []
            for idx in range(page_num):
                urls, titles, plays, dates, durations = spider.get_videos_by_page(idx)
                while not urls:
                    urls, titles, plays, dates, durations = spider.get_videos_by_page(idx)

                for item_index, url in enumerate(urls):
                    video = VideoItem(
                        uid=uid,
                        user_name=user_name,
                        bv=url.rstrip("/").split("/")[-1],
                        url=url,
                        title=titles[item_index],
                        play=plays[item_index],
                        duration=durations[item_index],
                        pub_date=dates[item_index][0],
                        collected_at=dates[item_index][1],
                    )
                    if include_detail:
                        play_count, danmu, pub_date, video_type, page_count = spider.get_url(url)
                        video.play = str(play_count)
                        video.danmu = danmu
                        video.pub_date = pub_date
                        video.video_type = video_type
                        video.page_count = page_count
                    videos.append(video)

            return videos
        finally:
            with suppress(Exception):
                spider.close()
