import requests

# url = 'http://localhost:8080/data/111/chapter1.txt'
# #url = 'http://localhost:8080/data/111/faust.txt'
# urlc = 'http://localhost:8080/data/111/chapter1.txt?chunked=1'

# #response = requests.get(url)

# headers = {'Range': 'bytes=200-300'}
# response = requests.get(url, headers=headers)

# print("----header----")
# print(response.headers)
# print("----content----")
# print(response.content.decode())

#----------------------------------------------------

# #url = 'http://127.0.0.1:8080/alice.txt?chunked=1'
# url = 'http://127.0.0.1:8080/unity-lab-course.mp4'

# data={}
# #headers={"Authorization": "Basic Y2xpZW50MToxMjM=", "Range": "152000-"}
# headers={"Authorization": "Basic Y2xpZW50MToxMjM="}

# r=requests.get(url=url, data=data, headers=headers)

# print(r)

# print(r.headers)
# print(r.content.decode())

data={}
headers={"Authorization": "Basic Y2xpZW50MToxMjM="}
r=requests.post(url='http://127.0.0.1:8080/alice.txt',headers=headers)

print(r.headers)
print(r.content.decode())