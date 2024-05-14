import requests

url = 'http://localhost:8080/upload?path=/11912113/'

files = {'file': open('tmp/client1/a.txt', 'rb')}  # Specify the file you want to upload

response = requests.post(url, files=files)

print(response.status_code)
print(response.text)
