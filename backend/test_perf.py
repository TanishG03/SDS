import requests
print(requests.get('http://127.0.0.1:5000/query?cx=800&cy=800&zoom=1').json())
