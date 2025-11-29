# -*- coding: utf-8 -*-
import os
import sys
import datetime
import requests
import xml.etree.ElementTree as ET
from google import genai

# ==== ENV ====
OWM_API_KEY = os.environ.get("OWM_API_KEY")
AQI_API_KEY = os.environ.get("AQI_API_KEY", OWM_API_KEY)
DISCORD_WEBHOOK = os.environ.get("DISCORD_WEBHOOK_URL")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

LAT = os.environ.get("LAT", "21.0535")
LON = os.environ.get("LON", "105.7446")

def require(name, val):
    if not val:
        sys.stderr.write("Missing environment variable: {}\n".format(name))
        sys.exit(1)


# Weather
def get_weather():
    require("OWM_API_KEY", OWM_API_KEY)

    url = "https://api.openweathermap.org/data/2.5/weather"
    params = {
        "lat": LAT,
        "lon": LON,
        "appid": OWM_API_KEY,
        "units": "metric",
        "lang": "vi",
    }

    r = requests.get(url, params=params, timeout=10)
    r.raise_for_status()
    data = r.json()

    # Trích xuất giống n8n
    desc = data["weather"][0]["description"].capitalize()
    temp = round(data["main"]["temp"])
    feels = round(data["main"]["feels_like"])
    hum = data["main"]["humidity"]
    wind = data["wind"]["speed"]
    name = data.get("name", "Không rõ địa điểm")

    return "Thời tiết hiện tại tại {}: {}, {}°C (cảm giác {}°C), độ ẩm {}%, gió {} m/s.".format(
        name, desc, temp, feels, hum, wind
    )


# AQI
def get_air_quality():
    url = "https://api.openweathermap.org/data/2.5/air_pollution"
    params = {
        "lat": LAT,
        "lon": LON,
        "appid": AQI_API_KEY,
    }

    r = requests.get(url, params=params, timeout=10)
    r.raise_for_status()
    data = r.json()

    aq = data["list"][0]
    aqi = aq["main"]["aqi"]

    aqi_map = {
        1: "Tot",
        2: "Trung binh",
        3: "Kem",
        4: "Xau",
        5: "Nguy hai"
    }

    return "Chi so AQI hien tai la {} ({}), muc do nay duoc danh gia la {}".format(
    aqi,
    aqi_map.get(aqi, "Khong ro"),
    "tot" if aqi == 1 else "trung binh" if aqi == 2 else "kem" if aqi == 3 else "xau" if aqi == 4 else "nguy hai"
)


# RSS
def get_hot_news_raw_xml():
    url = "https://vnexpress.net/rss/tin-moi-nhat.rss"
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    return r.text


def parse_rss_items(xml_text):
    root = ET.fromstring(xml_text)
    items = []
    for item in root.iter("item"):
        t = item.find("title").text if item.find("title") is not None else ""
        l = item.find("link").text if item.find("link") is not None else ""
        items.append({"title": t, "link": l})
    return items


def pick_top_news(items, limit=5):
    items = items[:limit]
    out = []
    i = 1
    for it in items:
        out.append("{}. {} ({})".format(i, it["title"], it["link"]))
        i += 1
    return "\n".join(out)

# GEMINI_API_KEY (sử dụng SDK google-genai)
from google import genai

def call_gemini(prompt):
    require("GEMINI_API_KEY", GEMINI_API_KEY)

    # Khởi tạo client
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

    # Gọi model Gemini chính thức
    response = client.models.generate_content(
        model="gemini-2.5-flash",     # hoặc "gemini-1.5-pro" nếu bạn có quyền
        contents=prompt
    )

    # Trích xuất text trả về
    return response.text


# Discord
def send_discord(content):
    require("DISCORD_WEBHOOK_URL", DISCORD_WEBHOOK)
    payload = {"content": content[:1900]}

    r = requests.post(DISCORD_WEBHOOK, json=payload, timeout=10)
    r.raise_for_status()


# MAIN
def main():
    now = datetime.datetime.now(datetime.UTC) + datetime.timedelta(hours=7)
    header = now.strftime("Ban tin tu dong - %d/%m/%Y %H:%M\n")

    try:
        weather = get_weather()
    except Exception as e:
        weather = "Loi thoi tiet: {}".format(e)

    try:
        aqi = get_air_quality()
    except Exception as e:
        aqi = "Loi AQI: {}".format(e)

    try:
        xml = get_hot_news_raw_xml()
        items = parse_rss_items(xml)
        top = pick_top_news(items)
    except Exception as e:
        top = "Loi tin tuc nong: {}".format(e)

    ai_input = "{}\n{}\n{}\n\nCac tin nong:\n{}\n\nHay tao ban tin ngan gon, de doc, van phong tu nhien, than thien. Ngoi xung la ban va toi.".format(
        header, weather, aqi, top
    )

    try:
        ai_output = call_gemini(ai_input)
    except Exception as e:
        ai_output = "Loi AI Agent: {}".format(e)

    try:
        send_discord(ai_output)
    except Exception as e:
        sys.stderr.write("Loi gui Discord: {}\n".format(e))
        sys.exit(1)


if __name__ == "__main__":
    main()