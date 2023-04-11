from pyiwara import Account, Client
from pathlib import Path


account = Account('username', 'password')
client = Client(account)

video = client.video("video_id") #Video object
print(video.title)

file = video.files[360] #File object
path = Path(f"{video.title}.{file.ext}")
file.download(path)







