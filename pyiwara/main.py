from __future__ import annotations
from typing import Union
from urllib.parse import urlparse, parse_qs
from hashlib import sha1
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime
from tqdm import tqdm
import requests
import mimetypes
import cloudscraper


class Domain:
    Base = "https://www.iwara.tv"
    API = "https://api.iwara.tv"
    File = "https://files.iwara.tv"


def get_sub_key() -> str:
    scraper = cloudscraper.create_scraper()
    res = scraper.get(Domain.Base)
    js = res.text.split('<script defer="defer" src="', 1)[
        1].split('"></script>', 1)[0]
    url = f"{Domain.Base}{js}"
    res = scraper.get(url)
    sub_key = "_" + res.text.split('expires+"_', 1)[1].split('"', 1)[0]
    return sub_key


def string_to_datetime(s: str) -> datetime:
    if s == None:
        return None
    date_format = '%Y-%m-%dT%H:%M:%S.%fZ'
    datetime_object = datetime.strptime(s, date_format)
    return datetime_object


class Auth(requests.auth.AuthBase):
    def __init__(self, token):
        self.token = token

    def __call__(self, res: requests.Response):
        res.headers["Authorization"] = f"Bearer {self.token}"
        return res


@dataclass
class Account:
    email: str
    password: str

    def json(self):
        return {"email": self.email, "password": self.password}


class Iterator:
    def __init__(self, stlist: Union[Users, Videos, StreamList]):
        self.__stlist = stlist
        self.__count = -1
        self.__max = len(stlist)

    def __next__(self):
        self.__count += 1
        if self.__count == self.__max:
            raise StopIteration
        return self.__stlist[self.__count]


class StreamList:
    def __init__(self, client: Client, url: str, query: dict = {}, limit=32, func=None) -> None:
        self.__len = None
        self.__query = query
        self.__limit = limit
        self.__query["limit"] = limit
        self.url = url
        self.client = client
        self.__data = {}
        self.__func = func

    def load(self, page: int = 0):
        if page in self.__data:
            return None
        self.__query["page"] = page
        data = self.client.session.get(self.url, params=self.__query).json()
        self.__len = data["count"]
        self.__data[page] = data["results"]

    def __iter__(self):
        return Iterator(self)

    @property
    def len(self) -> int:
        if self.__len == None:
            self.load()
        return self.__len

    def __len__(self) -> int:
        return self.len

    def __getitem__(self, p) -> Union[list[dict], dict]:
        if type(p) == int:
            page = p//self.__limit
            position = p % self.__limit
            self.load(page)
            if p >= self.len:
                raise Exception("out of range")
            if self.__func != None:
                return self.__func(self.__data[page][position])
            return self.__data[page][position]
        elif type(p) == slice:
            start = max(p.start, 0)
            stop = max(p.stop, self.len)
            return [self[p] for p in range(start, stop, p.step)]
        return None


class Videos(StreamList):
    def __init__(self, client: Client, query: dict = {}, limit=32, user=None) -> None:
        url = f"{Domain.API}/videos"
        def func(v): return Video.init_from_videos_data(v, client, user)
        self.__query = query
        super().__init__(client, url, query, limit, func)

    def __getitem__(self, p) -> Union[list[Video], Video]:
        return super().__getitem__(p)


class Users(StreamList):
    def __init__(self, client: Client, url: str, key: str) -> None:
        super().__init__(client, url,
                         func=lambda u: User.init_from_user(u[key], client))

    def __getitem__(self, p) -> Union[list[User], User]:
        return super().__getitem__(p)


class PlayList(Videos):
    # 無くなった?
    pass


class User(Videos):
    def init_from_user_name(name: str, client: Client) -> User:
        url = f"{Domain.API}/profile/{name}"
        data = client.session.get(url).json()
        user = User(data["user"]["id"])
        user.load_profile(data)
        return user

    def init_from_user(data, client) -> User:
        user = User(data["id"], client)
        user.load_user(data)
        return user

    def __init__(self, id: str, client: Client) -> None:
        super().__init__(client, user=self, query={"user": id})
        self.id = id

        self.__body = None

        self.__created_at = None
        self.__updated_at = None
        self.__name = None
        self.__seen_at = None
        self.__user_name = None
        self.__thumbnail_url = None

        self.followers = Users(
            self.client, f"{Domain.API}/user/{id}/followers", "follower")
        self.following = Users(
            self.client, f"{Domain.API}/user/{id}/following", "user")

    def load_user(self, data=None):
        if data == None:
            # ApiのURLがわからん
            self.load_profile()
        else:
            self.__created_at = string_to_datetime(data["createdAt"])
            self.__updated_at = string_to_datetime(data["updatedAt"])
            self.__name = data["name"]
            self.__user_name = data["username"]
            self.__seen_at = string_to_datetime(data["seenAt"])
            if "avatar" in data and data["avatar"]:
                self.__thumbnail_url = f"https://i.iwara.tv/image/avatar/{data['avatar']['id']}/{data['avatar']['name']}"

    def load_profile(self, data=None):
        if data == None:
            if self.__user_name == None:
                raise Exception("user_name is None")
            url = f"{Domain.API}/profile/{self.__user_name}"
            data = self.client.session.get(url).json()
        self.__body = data["body"]
        self.load_user(data["user"])

    @property
    def body(self) -> str:
        if self.__body == None:
            self.load_profile()
        return self.__body

    @body.setter
    def body(self, v):
        self.__body = v

    @property
    def created_at(self) -> datetime:
        if self.__created_at == None:
            self.load_user()
        return self.__created_at

    @created_at.setter
    def created_at(self, v):
        self.__created_at = v

    @property
    def updated_at(self) -> datetime:
        if self.__updated_at == None:
            self.load_user()
        return self.__updated_at

    @updated_at.setter
    def updated_at(self, v):
        self.__updated_at = v

    @property
    def name(self) -> str:
        if self.__name == None:
            self.load_user()
        return self.__name

    @name.setter
    def name(self, v):
        self.__name = v

    @property
    def seen_at(self) -> datetime:
        if self.__seen_at == None:
            self.load_user()
        return self.__seen_at

    @seen_at.setter
    def seen_at(self, v):
        self.__seen_at = v

    @property
    def user_name(self) -> str:
        if self.__user_name == None:
            self.load_user()
        return self.__user_name

    @user_name.setter
    def user_name(self, v):
        self.__user_name = v

    @property
    def thumbnail_url(self) -> str:
        if self.__thumbnail_url == None:
            self.load_user()
        return self.__thumbnail_url

    @thumbnail_url.setter
    def thumbnail_url(self, v):
        self.__thumbnail_url = v


@dataclass
class Tag:
    id: str
    type: str


@dataclass
class Src:
    view: str
    download: str


@dataclass
class File:
    client: Client
    id: str
    name: str
    src: Src
    type: str
    createdAt: datetime
    updatedAt: datetime

    @property
    def ext(self) -> str:
        return mimetypes.guess_extension(self.type)

    @property
    def download_link(self) -> str:
        return f"https:{self.src.download}"

    def download(self, path, progress=None):
        self.client.download(self.download_link, progress, path)


class Video:
    def init_from_videos_data(data, client: Client, user=None) -> Video:
        video = Video(data["id"], client)
        video.created_at = string_to_datetime(data["createdAt"])
        video.updated_at = string_to_datetime(data["updatedAt"])
        video.title = data["title"]
        video.description = data["body"]
        video.num_comments = data["numComments"]
        video.num_likes = data["numLikes"]
        video.num_views = data["numViews"]
        video.tags = [Tag(d["id"], d["type"]) for d in data["tags"]]
        video.user = user if user else User.init_from_user(
            data["user"], client)
        return video

    def __init__(self, id: str, client: Client) -> None:
        self.id = id
        self.client = client

        self.__description = None
        self.__title = None
        self.__created_at = None
        self.__updated_at = None
        self.__file = None
        self.__file_url = None
        self.__num_comments = None
        self.__num_likes = None
        self.__num_views = None
        self.__private = None
        self.__tags = None
        self.__thumbnail_url = None
        self.__user = None

        self.__files = None

    def load(self, data=None):
        if data == None:
            url = f"{Domain.API}/video/{self.id}"
            data = self.client.session.get(url).json()
        self.__description = data["body"]
        self.__title = data["title"]
        self.__created_at = string_to_datetime(data["createdAt"])
        self.__updated_at = string_to_datetime(data["updatedAt"])
        self.__file = data["file"]
        self.__file_url = data["fileUrl"]
        self.__num_comments = data["numComments"]
        self.__num_likes = data["numLikes"]
        self.__num_views = data["numViews"]
        self.private = data["private"]
        self.__tags = [Tag(d["id"], d["type"]) for d in data["tags"]]

        self.__thumbnail_url = f"{Domain.File}/image/original/{self.file['id']}/thumbnail-{data['thumbnail']:02d}.jpg"
        self.__user = User.init_from_user(data["user"], self.client)

    @property
    def files(self) -> list[File]:
        if self.__files == None:
            expires = parse_qs(urlparse(self.file_url).query)["expires"][0]
            key = f"{self.file['id']}_{expires}{self.client.sub_key}".encode(
                "utf-8")
            headers = {"X-Version": sha1(key).hexdigest()}
            data = self.client.session.get(
                self.file_url,
                headers=headers,
            ).json()
            self.__files = []
            for file_data in data:
                file = File(self.client, **file_data)
                file.src = Src(**file.src)
                file.createdAt = string_to_datetime(file.createdAt)
                file.updatedAt = string_to_datetime(file.updatedAt)
                self.__files.append(file)
        return self.__files

    def thumbnail(self, path, progress=None):
        self.client.download(self.thumbnail_url, progress, path)

    @property
    def description(self) -> str:
        if self.__description == None:
            self.load()
        return self.__description

    @description.setter
    def description(self, v):
        self.__description = v

    @property
    def title(self) -> str:
        if self.__title == None:
            self.load()
        return self.__title

    @title.setter
    def title(self, v):
        self.__title = v

    @property
    def created_at(self) -> datetime:
        if self.__created_at == None:
            self.load()
        return self.__created_at

    @created_at.setter
    def created_at(self, v):
        self.__created_at = v

    @property
    def updated_at(self) -> datetime:
        if self.__updated_at == None:
            self.load()
        return self.__updated_at

    @updated_at.setter
    def updated_at(self, v):
        self.__updated_at = v

    @property
    def file(self) -> dict:
        if self.__file == None:
            self.load()
        return self.__file

    @file.setter
    def file(self, v):
        self.__file = v

    @property
    def file_url(self) -> str:
        if self.__file_url == None:
            self.load()
        return self.__file_url

    @file_url.setter
    def file_url(self, v):
        self.__file_url = v

    @property
    def num_comments(self) -> int:
        if self.__num_comments == None:
            self.load()
        return self.__num_comments

    @num_comments.setter
    def num_comments(self, v):
        self.__num_comments = v

    @property
    def num_likes(self) -> int:
        if self.__num_likes == None:
            self.load()
        return self.__num_likes

    @num_likes.setter
    def num_likes(self, v):
        self.__num_likes = v

    @property
    def num_views(self) -> int:
        if self.__num_views == None:
            self.load()
        return self.__num_views

    @num_views.setter
    def num_views(self, v):
        self.__num_views = v

    @property
    def private(self) -> bool:
        if self.__private == None:
            self.load()
        return self.__private

    @private.setter
    def private(self, v):
        self.__private = v

    @property
    def tags(self) -> list[Tag]:
        if self.__tags == None:
            self.load()
        return self.__tags

    @tags.setter
    def tags(self, v):
        self.__tags = v

    @property
    def thumbnail_url(self) -> str:
        if self.__thumbnail_url == None:
            self.load()
        return self.__thumbnail_url

    @thumbnail_url.setter
    def thumbnail_url(self, v):
        self.__thumbnail_url = v

    @property
    def user(self) -> User:
        if self.__user == None:
            self.load()
        return self.__user

    @user.setter
    def user(self, v):
        self.__user = v


class Client:
    def __init__(self, account: Account, timeout=60) -> None:
        self.account = account
        self.session = requests.Session()
        self.session.timeout = timeout
        url = f"{Domain.API}/user/login"
        res = self.session.post(url, json=account.json()).json()
        if not "token" in res:
            raise Exception("login error")
        self.auth = Auth(res["token"])
        self.session.auth = self.auth
        self.sub_key = get_sub_key()
        self.progress = tqdm

    def video(self, id: str) -> Video:
        return Video(id, self)

    def user(self, id: str) -> User:
        return User(id, self)

    def download(self, url: str, progress=None, path=None):
        progress = progress if progress else self.progress
        path = Path(path) if path else Path("file.mp4")
        path.parent.mkdir(exist_ok=True, parents=True)
        res = self.session.get(url, stream=True)
        file_size = int(res.headers["content-length"])
        pbar = progress(total=file_size)
        with path.open("wb") as file:
            for chunk in res.iter_content(chunk_size=1024):
                file.write(chunk)
                pbar.update(len(chunk))
            pbar.close()
