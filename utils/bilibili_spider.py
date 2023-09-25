import re
import os
import os.path as osp
import sys
import json
import time
import argparse
from datetime import datetime, timedelta
from selenium import webdriver
from bs4 import BeautifulSoup
from urllib import parse as url_parse
import random
import kdl
import requests
from selenium.webdriver.support.wait import WebDriverWait

from .tools import mkdir_if_missing, write_json, read_json


class Bilibili_Spider():

    def __init__(self, uid, save_dir_json='json', save_by_page=False, t=2):
        self.t = t
        self.uid = uid
        self.user_url = 'https://space.bilibili.com/{}'.format(uid)
        self.save_dir_json = save_dir_json
        self.save_by_page = save_by_page
        # 创建Chrome WebDriver
        options = webdriver.ChromeOptions()
        # options = webdriver.FirefoxOptions()
        # options.add_argument('--headless')
        # # 代理服务器的IP和端口
        # # proxy_ip = '58.220.95.55'
        # # proxy_port = '9400'
        # # 设置代理
        # # options.add_argument('--proxy-server=http://{}:{}'.format(proxy_ip, proxy_port)
        # proxy_ip = ips[0]
        # options.add_argument('--proxy-server=http://{}'.format(proxy_ip))
        user_agent = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/117.0.0.0 Safari/537.36')
        options.add_argument(f'user-agent={user_agent}')
        self.driver = webdriver.Chrome(options=options)
        self.driver.maximize_window()
        print('spider init done.')

    def close(self):
        # 关闭浏览器驱动
        self.driver.quit()

    def time_convert(self, time_str):
        time_item = time_str.split(':')
        assert 1 <= len(time_item) <= 3, 'time format error: {}, x:x expected!'.format(time_str)
        if len(time_item) == 1:
            seconds = int(time_item[1])
        elif len(time_item) == 2:
            seconds = int(time_item[0]) * 60 + int(time_item[1])
        else:
            seconds = int(time_item[0]) * 60 * 60 + int(time_item[1]) * 60 + int(time_item[2])
        return seconds

    def date_convert(self, date_str):
        if date_str.endswith("小时前"):
            # 提取小时数
            hours_ago = int(date_str.split("小时前")[0])
            # 获取当前日期时间
            current_datetime = datetime.now()
            # 计算视频发出的日期
            publish_date = current_datetime - timedelta(hours=hours_ago)
            # 将日期格式化为字符串
            date_str = publish_date.strftime('%Y-%m-%d')
        elif date_str == "昨天":
            # 获取当前日期时间
            current_datetime = datetime.now()
            # 计算视频发出的日期
            publish_date = current_datetime - timedelta(days=1)
            # 将日期格式化为字符串
            date_str = publish_date.strftime('%Y-%m-%d')
        else:
            # 默认情况，返回原始发布日期
            date_str = date_str

        date_item = date_str.split('-')
        assert len(date_item) == 2 or len(date_item) == 3, 'date format error: {}, x-x or x-x-x expected!'.format(
            date_str)
        if len(date_item) == 2:
            year = datetime.now().strftime('%Y')
            date_str = '{}-{:>02d}-{:>02d}'.format(year, int(date_item[0]), int(date_item[1]))
        else:
            date_str = '{}-{:>02d}-{:>02d}'.format(date_item[0], int(date_item[1]), int(date_item[2]))
        return date_str

    def get_page_num(self):
        page_url = self.user_url + '/search/video?tid=0&pn={}&keyword=.&order=pubdate'.format(1)
        # page_url = self.user_url + '/video?tid=0&page={}&keyword=&order=pubdate'.format(1)
        #       '/search/video?tid=0&pn={}&keyword=.&order=pubdate'
        self.driver.get(page_url)
        time.sleep(self.t + 2 * random.random())
        html = BeautifulSoup(self.driver.page_source, features="html.parser")

        page_number = html.find('span', attrs={'class': 'be-pager-total'}).text
        # be-pager-total
        user_name = html.find('span', id='h-name').text

        return int(page_number.split(' ')[1]), user_name

    def get_videos_by_page(self, idx):
        # 获取第 page_idx 页的视频信息
        urls_page, titles_page, plays_page, dates_page, durations_page = [], [], [], [], []
        page_url = self.user_url + '/search/video?tid=0&pn={}&keyword=.&order=pubdate'.format(idx + 1)
        # page_url = self.user_url + '/video?tid=0&page={}&keyword=&order=pubdate'.format(idx + 1)
        # '/search/video?tid=0&pn={}&keyword=.&order=pubdate'
        self.driver.get(page_url)
        # # 设置等待
        # wait = WebDriverWait(driver, 10, 0.5)
        # # 使用匿名函数
        # wait.until(lambda diver: driver.find_element_by_id('kw'))

        time.sleep(self.t + 2 * random.random())
        html = BeautifulSoup(self.driver.page_source, features="html.parser")

        ul_data = html.find('div', id='submit-video-list').find('ul', attrs={'class': 'clearfix cube-list'})

        for li in ul_data.find_all('li'):
            # url & title
            a = li.find('a', attrs={'target': '_blank', 'class': 'title'})
            a_url = 'https:{}'.format(a['href'])
            a_title = a.text
            # pub_date & play
            date_str = li.find('span', attrs={'class': 'time'}).text.strip()
            pub_date = self.date_convert(date_str)
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            play = li.find('span', attrs={'class': 'play'}).text.strip()
            time_str = li.find('span', attrs={'class': 'length'}).text
            # duration = self.time_convert(time_str)
            # append
            urls_page.append(a_url)
            titles_page.append(a_title)
            dates_page.append((pub_date, now))
            plays_page.append(play)
            durations_page.append(time_str)

        return urls_page, titles_page, plays_page, dates_page, durations_page

    def save(self, json_path, bvs, urls, titles, plays, durations, dates):
        data_list = []
        for i in range(len(urls)):
            result = {}
            result['user_name'] = self.user_name
            result['bv'] = bvs[i]
            result['url'] = urls[i]
            result['title'] = titles[i]
            result['play'] = plays[i]
            result['duration'] = durations[i]
            result['pub_date'] = dates[i][0]
            result['now'] = dates[i][1]
            data_list.append(result)

        print('write json to {}'.format(json_path))
        dir_name = osp.dirname(json_path)
        mkdir_if_missing(dir_name)
        write_json(data_list, json_path)
        print('dump json file done. total {} urls. \n'.format(len(urls)))

    def get(self):
        # 获取该 up 主的所有基础视频信息
        print('Start ... \n')
        self.page_num, self.user_name = self.get_page_num()
        while self.page_num == 0:
            print('Failed to get user page num, poor network condition, retrying ... ')
            self.page_num, self.user_name = self.get_page_num()
        print('Pages Num {}, User Name: {}'.format(self.page_num, self.user_name))

        bvs = []
        urls = []
        titles = []
        plays = []
        dates = []
        durations = []  # by seconds

        for idx in range(self.page_num):
            print('>>>> page {}/{}'.format(idx + 1, self.page_num))
            urls_page, titles_page, plays_page, dates_page, durations_page = self.get_videos_by_page(idx)
            while len(urls_page) == 0:
                print('failed, try again page {}/{}'.format(idx + 1, self.page_num))
                urls_page, titles_page, plays_page, dates_page, durations_page = self.get_videos_by_page(idx)
            bvs_page = [x.split('/')[-1] for x in urls_page]
            assert len(urls_page) == len(titles_page), '{} != {}'.format(len(urls_page), len(titles_page))
            assert len(urls_page) == len(plays_page), '{} != {}'.format(len(urls_page), len(titles_page))
            assert len(urls_page) == len(dates_page), '{} != {}'.format(len(urls_page), len(dates_page))
            assert len(urls_page) == len(durations_page), '{} != {}'.format(len(urls_page), len(durations_page))
            print('result:')
            print('{}_{}: '.format(self.user_name, self.uid), bvs_page, ', {} in total'.format(len(urls_page)))
            sys.stdout.flush()
            bvs.extend(bvs_page)
            urls.extend(urls_page)
            titles.extend(titles_page)
            plays.extend(plays_page)
            dates.extend(dates_page)
            durations.extend(durations_page)
            if self.save_by_page:
                json_path_page = osp.join(self.save_dir_json, '{}_{}'.format(self.user_name, self.uid), 'primary',
                                          'page_{}.json'.format(idx + 1))
                self.save(json_path_page, bvs_page, urls_page, titles_page, plays_page, durations_page, dates_page)

        json_path = osp.join(self.save_dir_json, '{}_{}'.format(self.user_name, self.uid), 'primary', 'full.json')
        self.save(json_path, bvs, urls, titles, plays, durations, dates)

    def get_url(self, url):
        self.driver.get(url)
        time.sleep(self.t + 2 * random.random())
        html = BeautifulSoup(self.driver.page_source, features="html.parser")

        video_data = html.find('div', id='viewbox_report').find_all('span')
        # print(video_data)
        play = int(video_data[1]['title'][4:])
        danmu = int(video_data[2]['title'][7:])
        date = video_data[3].text

        multi_page = html.find('div', id='multi_page')
        if multi_page is not None:
            url_type = 'playlist'
            pages = multi_page.find('span', attrs={'class': 'cur-page'}).text
            # print(pages)
            page_total = int(pages[1:-1].split('/')[-1])
        else:
            url_type = 'video'
            page_total = 1

        return play, danmu, date, url_type, page_total

    def get_detail(self):
        print('Start to get detailed information for each url.')
        if self.save_by_page:
            data = []
            for idx in range(self.page_num):
                json_path = osp.join(self.save_dir_json, '{}_{}'.format(self.user_name, self.uid), 'primary',
                                     'page_{}.json'.format(idx + 1))
                data_page = read_json(json_path)
                for j, item in enumerate(data_page):
                    url = item['url']
                    print('>>>> page {}/{}, No. {}/{}'.format(idx + 1, self.page_num, j + 1, len(data_page)))
                    play, danmu, date, url_type, page_total = self.get_url(url)
                    # print(play, danmu, date, url_type, page_total)
                    assert page_total > 0, page_total
                    if page_total == 1:
                        assert url_type == 'video', (url_type, page_total)
                        data_page[j]['play'] = play
                        data_page[j]['danmu'] = danmu
                        data_page[j]['pub_date'] = date
                        data_page[j]['type'] = url_type
                        data_page[j]['num'] = page_total
                    else:
                        assert url_type == 'playlist', (url_type, page_total)
                        data_page[j]['play'] = play
                        data_page[j]['danmu'] = danmu
                        data_page[j]['pub_date'] = date
                        data_page[j]['type'] = url_type
                        data_page[j]['num'] = page_total

                json_path_save = osp.join(self.save_dir_json, '{}_{}'.format(self.user_name, self.uid), 'detailed',
                                          'page_{}.json'.format(idx + 1))
                print('write json to {}'.format(json_path_save))
                write_json(data_page, json_path_save)
                print('dump json file done. total {} urls. \n'.format(len(data_page)))
                data.extend(data_page)

            json_path_save = osp.join(self.save_dir_json, '{}_{}'.format(self.user_name, self.uid), 'detailed',
                                      'full.json')
            print('write json to {}'.format(json_path_save))
            write_json(data, json_path_save)
            print('dump json file done. total {} urls. \n'.format(len(data)))
        else:
            json_path = osp.join(self.save_dir_json, '{}_{}'.format(self.user_name, self.uid), 'primary', 'full.json')
            data = read_json(json_path)
            for j, item in enumerate(data):
                url = item['url']
                print('>>>> No. {}/{}'.format(j + 1, len(data)))
                play, danmu, date, url_type, page_total = self.get_url(url)
                assert page_total > 0, page_total
                if page_total == 1:
                    assert url_type == 'video', (url_type, page_total)
                    data[j]['play'] = play
                    data[j]['danmu'] = danmu
                    data[j]['pub_date'] = date
                    data[j]['type'] = url_type
                    data[j]['num'] = page_total
                else:
                    assert url_type == 'playlist', (url_type, page_total)
                    data[j]['play'] = play
                    data[j]['danmu'] = danmu
                    data[j]['pub_date'] = date
                    data[j]['type'] = url_type
                    data[j]['num'] = page_total

            json_path_save = osp.join(self.save_dir_json, '{}_{}'.format(self.user_name, self.uid), 'detailed',
                                      'full.json')
            print('write json to {}'.format(json_path_save))
            write_json(data, json_path_save)
            print('dump json file done. total {} urls. \n'.format(len(data)))
