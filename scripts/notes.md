### 注意点

对于 chicago 图片的自动爬取下载，需要注意QPS不得高于1，且需配置本地代理：
```shell
$env:HTTP_PROXY="http://127.0.0.1:7897" # TODO
$env:HTTPS_PROXY="http://127.0.0.1:7897" # TODO
```
```shell
python scripts/download_images.py --museum chicago --limit 10 --workers 1 --debug
```