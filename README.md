# pyiwara
iwaraの情報を取得、ダウンロードができます。

## 必要なライブラリ
`pip install cloudscraper`

### 簡単な使用例

```python
from pyiwara import Account, Client, Video, User
from tqdm import tqdm


class myTqdm(tqdm):
    def __init__(self, total):
        super().__init__(total=total,  unit="B", unit_scale=True)


client = Client(Account("xxxxxxx@gmail.com", "password"))
client.progress = myTqdm  # init(total) , update(size) , close()

video = client.video("video id")  # == Video(id , client)
for user_video in video.user:  # user_video:Video , video.user:User
    for file in user_video.files:
        if file.name == "Source":
            path = user_video.title + file.ext
            file.download(path)
```
