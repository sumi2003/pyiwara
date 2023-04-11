from __future__ import annotations
from typing import Union, Iterator, TypeVar, Generic, Callable, Sequence
from urllib.parse import urlparse, parse_qs
from hashlib import sha1
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime
from tqdm import tqdm
import requests
import mimetypes
import cloudscraper
import re

IWARA_URL = "https://www.iwara.tv"
API_URL = "https://api.iwara.tv"
FILE_URL = "https://files.iwara.tv"
HASH_SANITYZE_KEY = "5nFp9kmbNnHdAFhaqMvt"


def get_hash_sanityze_key() -> str:
    session = cloudscraper.create_scraper()
    res = session.get(IWARA_URL)
    js_url = re.search(
        '<script defer="defer" src="(.+?)"></script>', res.text).group(1)
    res = session.get(f"{IWARA_URL}{js_url}")
    key = re.search('expires\+"_(.+?)"', res.text).group(1)
    return key


def update_hash_sanityze_key() -> None:
    global HASH_SANITYZE_KEY
    HASH_SANITYZE_KEY = get_hash_sanityze_key()


def string_to_datetime(s: str) -> datetime:
    if s == None:
        return None
    date_format = '%Y-%m-%dT%H:%M:%S.%fZ'
    datetime_object = datetime.strptime(s, date_format)
    return datetime_object


class My_dict(dict):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def __getitem__(self, key):
        res = self.get(key)
        if type(res) == dict:
            return My_dict(res)
        return res


class Auth(requests.auth.AuthBase):
    def __init__(self, token: str):
        self.token = token

    def __call__(self, r: requests.PreparedRequest) -> requests.PreparedRequest:
        r.headers["Authorization"] = f"Bearer {self.token}"
        return r


@dataclass
class Account:
    email: str
    password: str

    @property
    def dict(self) -> dict:
        return {"email": self.email, "password": self.password}

    def __str__(self) -> str:
        return f"<Account email:{self.email} password:{self.password}>"


class Client:
    def __init__(self, account: Account = None, timeout: int = 60) -> None:
        self.session = requests.Session()
        self.session.timeout = timeout
        self.account = account
        self.login = False
        if account != None:
            url = f"{API_URL}/user/login"
            res = self.session.post(url, json=account.dict).json()
            if not "token" in res:
                raise Exception("login failed")
            self.auth = Auth(res["token"])
            self.session.auth = self.auth
            self.login = True

        else:
            self.session = requests.Session()

        self.progress = tqdm

    def __str__(self) -> str:
        return f"<Client login:{self.login}>"

    def video(self, id: str) -> Video:
        return Video(id, self)

    def user(self, user_name: str) -> User:
        return User(user_name, self)

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


T = TypeVar("T")


class ListAPIiterator:
    def __init__(self, listapi: ListAPI) -> None:
        self.__listapi = listapi
        self.__max = len(listapi)
        self.__index = 0

    def __next__(self):
        if self.__index >= self.__max:
            raise StopIteration
        self.__index += 1
        return self.__listapi[self.__index - 1]


class ListAPI(Generic[T]):
    def __init__(self, client: Client, url: str, query: dict = {}, limit=32, func=None) -> None:
        self.client = client
        self.__query = query
        self.__limit = limit
        self.__query["limit"] = limit
        self.url = url
        self.__data = {}
        self.__func = func
        self.__len = None

    def __len__(self) -> int:
        if self.__len == None:
            self.load()
        return self.__len

    def load(self, page: int = 0) -> None:
        if page in self.__data:
            return None
        self.__query["page"] = page
        data = self.client.session.get(self.url, params=self.__query).json()
        self.__len = data["count"]
        self.__data[page] = data["results"]

    def __getitem__(self, index: Union[int, slice]) -> Union[T, list[T]]:
        if type(index) == slice:
            if index.start < 0:
                index.start = 0
            if index.stop > len(self):
                index.stop = len(self)
            return [self[i] for i in range(index.start, index.stop, index.step)]
        if index >= len(self):
            raise IndexError
        page = index // self.__limit
        self.load(page)
        if self.__func != None:
            return self.__func(self.__data[page][index % self.__limit])
        return self.__data[page][index % self.__limit]

    def __iter__(self) -> Iterator[T]:
        return ListAPIiterator(self)


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


class Files(list[File]):
    def __init__(self, *args, **kg) -> None:
        super().__init__(*args, **kg)

    def __getitem__(self, index: Union[int, slice, str]) -> Union[File, list[File]]:
        if type(index) == str or (type(index) == int and index > 100):
            name = str(index)
            for file in self:
                if file.name == name:
                    return file
            return None
        return super().__getitem__(index)


U = TypeVar("U")


class Video:
    def __init__(self, id: str, client: Client) -> None:
        self.__loaded = False
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
            url = f"{API_URL}/video/{self.id}"
            data = self.client.session.get(url).json()
            self.__loaded = True

        if "message" in data and "errors" in data["message"]:
            raise Exception(data["message"])

        data = My_dict(data)

        self.__description = data["body"]
        self.__title = data["title"]
        self.__created_at = string_to_datetime(data["createdAt"])
        self.__updated_at = string_to_datetime(data["updatedAt"])
        self.__file = data["file"]
        self.__file_url = data["fileUrl"]
        self.__num_comments = data["numComments"]
        self.__num_likes = data["numLikes"]
        self.__num_views = data["numViews"]
        self.__private = data["private"]
        self.__tags = [Tag(d["id"], d["type"]) for d in data["tags"]]
        self.__thumbnail_url = f"{FILE_URL}/image/original/{self.file['id']}/thumbnail-{data['thumbnail']:02d}.jpg"
        self.__user = User.init_from_user(data["user"], self.client)

    def __str__(self) -> str:
        return f"<Video id={self.id}>"

    @property
    def files(self) -> Files:
        if self.__files == None:
            expires = parse_qs(urlparse(self.file_url).query)["expires"][0]
            key = f"{self.file['id']}_{expires}_{HASH_SANITYZE_KEY}".encode(
                "utf-8")
            headers = {"X-Version": sha1(key).hexdigest()}
            data = self.client.session.get(
                self.file_url,
                headers=headers,
            ).json()
            self.__files = Files()
            for file_data in data:
                file = File(self.client, **file_data)
                file.src = Src(**file.src)
                file.createdAt = string_to_datetime(file.createdAt)
                file.updatedAt = string_to_datetime(file.updatedAt)
                self.__files.append(file)
        return self.__files

    def load_decorator(func: Callable[[Video], U]) -> Callable[[Video], U]:
        def wrapper(self: Video):
            if func(self) == None and self.__loaded == False:
                self.load()
            return func(self)
        return wrapper

    @property
    @load_decorator
    def description(self) -> str: return self.__description
    @description.setter
    def description(self, value): self.__description = value

    @property
    @load_decorator
    def title(self) -> str: return self.__title
    @title.setter
    def title(self, value): self.__title = value

    @property
    @load_decorator
    def created_at(self) -> datetime: return self.__created_at
    @created_at.setter
    def created_at(self, value): self.__created_at = value

    @property
    @load_decorator
    def updated_at(self) -> datetime: return self.__updated_at
    @updated_at.setter
    def updated_at(self, value): self.__updated_at = value

    @property
    @load_decorator
    def file(self) -> dict: return self.__file
    @file.setter
    def file(self, value): self.__file = value

    @property
    @load_decorator
    def file_url(self) -> str: return self.__file_url
    @file_url.setter
    def file_url(self, value): self.__file_url = value

    @property
    @load_decorator
    def num_comments(self) -> int: return self.__num_comments
    @num_comments.setter
    def num_comments(self, value): self.__num_comments = value

    @property
    @load_decorator
    def num_likes(self) -> int: return self.__num_likes
    @num_likes.setter
    def num_likes(self, value): self.__num_likes = value

    @property
    @load_decorator
    def num_views(self) -> int: return self.__num_views
    @num_views.setter
    def num_views(self, value): self.__num_views = value

    @property
    @load_decorator
    def private(self) -> bool: return self.__private
    @private.setter
    def private(self, value): self.__private = value

    @property
    @load_decorator
    def tags(self) -> list[Tag]: return self.__tags
    @tags.setter
    def tags(self, value): self.__tags = value

    @property
    @load_decorator
    def thumbnail_url(self) -> str: return self.__thumbnail_url
    @thumbnail_url.setter
    def thumbnail_url(self, value): self.__thumbnail_url = value

    @property
    @load_decorator
    def user(self) -> User: return self.__user
    @user.setter
    def user(self, value): self.__user = value


class Videos(ListAPI[Video]):
    def __init__(self, client: Client, query: dict = {}) -> None:
        url = f"{API_URL}/videos"
        limit = 32
        def func(x): return Video(client, data=x)
        super().__init__(client, url, query, limit, func)


S = TypeVar("S")


class User(Videos):
    def init_from_user(data: dict, client: Client) -> User:
        super.__init__
        user = User(data["username"], client)
        user.load(data)
        return user

    def __init__(self, user_name: str, client: Client) -> None:
        self.user_name = user_name
        self.client = client
        self.__loaded = False

        self.__id = None
        self.__body = None
        self.__created_at = None
        self.__updated_at = None
        self.__seen_at = None
        self.__name = None
        self.__thumbnail_url = None

        self.__followers = None
        self.__following = None

    def __str__(self) -> str:
        return f"<User {self.user_name}>"

    @property
    def following(self) -> Users:
        if self.__following == None:
            self.__following = Users(
                self.client,
                f"{API_URL}/user/{self.id}/following",
                "user"
            )
        return self.__following

    @property
    def followers(self) -> Users:
        if self.__followers == None:
            self.__followers = Users(
                self.client,
                f"{API_URL}/user/{self.id}/followers",
                "follower"
            )
        return self.__followers

    def load(self, data=None):
        if self.__loaded:
            return None

        if data == None:
            url = f"{API_URL}/users/{self.user_name}/profile"
            data = self.client.session.get(url).json()
            self.__body = data["body"]
            data = data["user"]
            self.__loaded = True

        if "message" in data and "errors" in data["message"]:
            raise Exception(data["message"])

        data = My_dict(data)

        self.__created_at = string_to_datetime(data["createdAt"])
        self.__updated_at = string_to_datetime(data["updatedAt"])
        self.__seen_at = string_to_datetime(data["seenAt"])
        self.__id = data["id"]
        self.__name = data["name"]
        if data["avatar"] != None:
            self.__thumbnail_url = f"https://i.iwara.tv/image/avatar/{data['avatar']['id']}/{data['avatar']['name']}"

    def load_decorator(func: Callable[[User], S]) -> Callable[[User], S]:
        def wrapper(self: User):
            if func(self) == None and self.__loaded == False:
                self.load()
            return func(self)
        return wrapper

    @property
    @load_decorator
    def id(self) -> str: return self.__id
    @id.setter
    def id(self, value): self.__id = value

    @property
    @load_decorator
    def body(self) -> str: return self.__body
    @body.setter
    def body(self, value): self.__body = value

    @property
    @load_decorator
    def created_at(self) -> datetime: return self.__created_at
    @created_at.setter
    def created_at(self, value): self.__created_at = value

    @property
    @load_decorator
    def updated_at(self) -> datetime: return self.__updated_at
    @updated_at.setter
    def updated_at(self, value): self.__updated_at = value

    @property
    @load_decorator
    def seen_at(self) -> datetime: return self.__seen_at
    @seen_at.setter
    def seen_at(self, value): self.__seen_at = value

    @property
    @load_decorator
    def name(self) -> str: return self.__name
    @name.setter
    def name(self, value): self.__name = value

    @property
    @load_decorator
    def thumbnail_url(self) -> str: return self.__thumbnail_url
    @thumbnail_url.setter
    def thumbnail_url(self, value): self.__thumbnail_url = value


class Users(ListAPI[User]):
    def __init__(self, client: Client, url: str, key) -> None:
        super().__init__(
            client,
            url,
            func=lambda x: User.init_from_user(x[key], client)
        )
