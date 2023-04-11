# pyiwara

iwaraから動画やユーザーデータを取得しダウンロードします。
Download videos and get user data from iwara.


##　sample

```python
from pyiwara import Account, Client
from pathlib import Path


account = Account('username', 'password')
client = Client(account)

video = client.video("video_id") #Video object
print(video.title)

file = video.files[360] #File object
path = Path(f"{video.title}.{file.ext}")
file.download(path)
```

### Video(class)

##### __init__(self, id: str, client: Client) -> None:

| name          | type       |
| ------------- | ---------- |
| id            | str        |
| description   | str        |
| title         | TD         |
| created_at    | datetime   |
| updated_at    | datetime   |
| num_comments  | int        |
| num_likes     | int        |
| num_views     | int        |
| private       | bool       |
| tags          | list[Tag]  |
| thumbnail_url | str        |
| user          | User       |
| files         | list[File] |

### File(class)

##### download(self, path, progress=None):

| name      | type     |
| --------- | -------- |
| id        | str      |
| name      | str      |
| src       | Src      |
| type      | str      |
| createdAt | datetime |
| updatedAt | datetime |
| ext       | str      |

### User

#####  __init__(self, user_name: str, client: Client) -> None:

| name          | type       |
| ------------- | ---------- |
| id            | str        |
| body          | str        |
| created_at    | datetime   |
| updated_at    | datetime   |
| seen_at       | datetime   |
| name          | str        |
| thumbnail_url | str        |
| followers     | list[User] |
| following     | list[User] |

```python
user = video.user #client.user(video.user_id) #User object
for video in user:
    print(video.title)
```

