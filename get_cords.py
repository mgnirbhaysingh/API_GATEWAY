import requests

cookies = {
    'cf_clearance': '',
}

headers = {
    'accept': 'application/json, text/javascript, */*; q=0.01',
    'accept-language': 'en-GB,en;q=0.7',
    'priority': 'u=1, i',
    'referer': 'https://www.gps-coordinates.net/',
    'sec-ch-ua': '"Chromium";v="142", "Brave";v="142", "Not_A Brand";v="99"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"macOS"',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'same-origin',
    'sec-gpc': '1',
    'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36',
    'x-requested-with': 'XMLHttpRequest',
    # 'cookie': 'cf_clearance=OMq.8l7uMZ_Ua0CRsLkqZmfi.2lmv3m48VsMYXSRgAY-1764232911-1.2.1.1-Xys.1LuQ3ogXqczX4S.JyU6zdgYlJHMKCV59Wqr3ytoB9asvv7P8q_aq9RZmwn59IjPyhcj9OAMwfZSkd3THV9__OGpiZPHuBlta2S2Wle8Etmb35J2oi0z0OnftTCsjIxFMndZbQDIA8239uG2AC2qe9e6pO8Su8rr4t3M0pQffdtOfcBZz3l8LAhYwEqcJb5RoLAiXIiSFp0a.eHTIqxppOr950.yhDXkMVmVztQ0',
}

params = {
    'q': 'Neelmatha Lucknow',
    'key': '',
    'no_annotations': '1',
    'language': 'en',
}

response = requests.get('https://www.gps-coordinates.net/geoproxy', params=params, cookies=cookies, headers=headers)
print(response.json())