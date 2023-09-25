# bilibiliTools

Python 爬取B站（bilibili.com）UP主的所有视频链接及详细信息

博客：[https://blog.xieqiaokang.com/posts/36033.html](https://blog.xieqiaokang.com/posts/36033.html)

## 功能

根据UID查询该UP的视频并以json格式保存

查找BVJS中的BV号和URL

通过URL将视频保存到指定收藏夹



## 环境准备

根据requirements.txt下载依赖就好

主体功能参照原主链接

https://github.com/xieqk/Bilibili_Spider_by_UserID

本人对原主的功能进行了一定修改

### 特别是本人使用的是chrome浏览器和而原作者使用的是Firefox

chromedriver安装参照[chromedriver安装教程(windows版)_喜欢听歌的二哥的博客-CSDN博客](https://blog.csdn.net/qq_27472133/article/details/128569296)

高版本或者说最新版本的chromedriver下载[Chrome for Testing availability (googlechromelabs.github.io)](https://googlechromelabs.github.io/chrome-for-testing/#stable)

对原主读取逻辑进行了一定的优化，减少了一部分bug



##### 查找BVJS中的BV号和URL

就是简单正则表达式的查询json文本

##### 通过URL将视频保存到指定收藏夹

通过cookie获取登录信息，然后依次点击罢了。



有人问了那下载功能呢？

这就不得不提https://github.com/leiurayer/downkyi 了



说句实话直接下载https://github.com/leiurayer/downkyi 就好。这个下载器支持网页直接获取下载链接所以我费了一整天做好的东西其实人家早搞好了。
