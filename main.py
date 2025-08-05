import requests
import re
import discord
import os
import zoneinfo
import traceback
from datetime import datetime, timedelta
from html import unescape
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN", "")
VISUALIZER_TOKEN = os.getenv("VISUALIZER_TOKEN", "")
VISUALIZER_URL = os.getenv("VISUALIZER_URL", "")
CHANNELS = list(map(int, os.getenv("CHANNELS", "").split(' ')))
MANADA_USER = os.getenv("MANADA_USER", "")
MANADA_PWD = os.getenv("MANADA_PWD", "")
AUTH_URL = os.getenv("AUTH_URL", "")
MANADA_URL = os.getenv("MANADA_URL", "")
LOCK_FILE_PATH = "/tmp/manada.lock"

if not all(
    [
        e
        for e in (
            TOKEN,
            CHANNELS,
            MANADA_USER,
            MANADA_PWD,
            AUTH_URL,
            MANADA_URL,
            VISUALIZER_TOKEN,
            VISUALIZER_URL,
        )
    ]
):
    print("Not all variables are set")
    exit(1)

HIGH_PRI = 0xFF0000
MEDIUM_PRI = 0xF58216
LOW_PRI = 0x86DC3D
NO_TASK = 0x33C7FF
DUE_FORMAT = "%Y-%m-%d %H:%M"
COLOR_LIST = [0x000000, HIGH_PRI, MEDIUM_PRI, LOW_PRI]
UA = "Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/116.0"


def get_shib() -> dict[str, str]:
    s = requests.session()

    headers = {
        "User-Agent": UA,
    }

    r = s.get(f"{MANADA_URL}/ct/home", headers=headers)

    headers = {
        "User-Agent": UA,
        "Content-Type": "application/x-www-form-urlencoded",
    }

    data = {
        "shib_idp_ls_exception.shib_idp_session_ss": "",
        "shib_idp_ls_success.shib_idp_session_ss": "true",
        "shib_idp_ls_value.shib_idp_session_ss": "",
        "shib_idp_ls_exception.shib_idp_persistent_ss": "",
        "shib_idp_ls_success.shib_idp_persistent_ss": "true",
        "shib_idp_ls_value.shib_idp_persistent_ss": "",
        "shib_idp_ls_supported": "true",
        "_eventId_proceed": "",
    }

    r = s.post(
        f"{AUTH_URL}?execution=e1s1",
        headers=headers,
        data=data,
    )

    ######

    data = {
        "j_username": MANADA_USER,
        "j_password": MANADA_PWD,
        "_eventId_proceed": "",
    }

    r = s.post(
        f"{AUTH_URL}?execution=e1s2",
        headers=headers,
        data=data,
    )

    ######

    data = {
        "shib_idp_ls_exception.shib_idp_session_ss": "",
        "shib_idp_ls_success.shib_idp_session_ss": "true",
        "_eventId_proceed": "",
    }

    r = s.post(
        f"{AUTH_URL}?execution=e1s3",
        headers=headers,
        data=data,
    )

    relay_state, saml = map(lambda x: x[7:-3], re.findall(r'value=".*"/>', r.text)[:2])

    ######

    data = {"RelayState": unescape(relay_state), "SAMLResponse": saml}

    r = s.post(
        f"{MANADA_URL}/Shibboleth.sso/SAML2/POST",
        headers=headers,
        data=data,
    )
    shib_key = [
        k for k in s.cookies.get_dict().keys() if k.startswith("_shibsession_")
    ][0]
    return {f"{shib_key}": s.cookies.get_dict()[shib_key]}


def send_to_visualizer(dues):
    headers = {"Authorization": f"Bearer {VISUALIZER_TOKEN}"}
    requests.put(VISUALIZER_URL, headers=headers, json=dues)


def get_messages() -> list[discord.Embed]:
    headers = {"User-Agent": UA}

    cookies = get_shib()

    r = requests.get(
        f"{MANADA_URL}/ct/home_library_query",
        cookies=cookies,
        headers=headers,
    )

    res = []
    dues = []
    for e in r.text.split("myassignments-title")[1:]:
        due = re.findall(r'td-period">(.*)</td>', e)
        priority = 0
        if not (due and len(due) >= 2 and due[1].startswith("202")):
            continue
        due_iso = due[1].strip().replace(" ", "T")
        due_readable = datetime.strptime(f"{due[1].strip()} +09:00", f"{DUE_FORMAT} %z")
        due_remain = due_readable - datetime.now(tz=zoneinfo.ZoneInfo("Asia/Tokyo"))

        # overdue check
        if due_remain < timedelta(days=0):
            continue

        if due_remain < timedelta(days=1):
            priority = 1
        elif due_remain < timedelta(days=3):
            priority = 2
        elif due_remain < timedelta(days=7):
            priority = 3
        else:
            continue

        url_name = re.search(r'<a href="(.+)">(.+?)</a>', e)
        course = re.search(r'class="mycourse-title"><.*>(.*)</a>', e)
        if not url_name or not course:
            continue

        url = f"{MANADA_URL}/ct/" + url_name.group(1)
        title = url_name.group(2).replace("amp;", "")
        course = course.group(1).replace("amp;", "")
        color = COLOR_LIST[priority]
        embed = discord.Embed(title=title, url=url, color=color)
        embed.add_field(name="コース", value=course, inline=False)
        embed.add_field(
            name="締切", value=due_readable.strftime(DUE_FORMAT), inline=True
        )
        embed.add_field(
            name="残り時間",
            value=f"{due_remain.days}d {due_remain.seconds // (60 * 60)}h {due_remain.seconds // 60 % 60}m",
            inline=True,
        )
        res.append(embed)
        dues.append({"title": title, "deadline": due_iso, "course": course})
    if res:
        if os.path.isfile(LOCK_FILE_PATH):
            os.remove(LOCK_FILE_PATH)
    else:
        if not os.path.isfile(LOCK_FILE_PATH):
            embed = discord.Embed(title="直近の課題なし", color=NO_TASK)
            res.append(embed)
            open(LOCK_FILE_PATH, "r").close()
    send_to_visualizer(dues)
    return res


def send_msg(msgs: list[discord.Embed], channel: int):
    client = discord.Client(intents=discord.Intents.default())

    @client.event
    async def on_ready():
        for msg in msgs:
            await client.get_channel(channel).send(embed=msg)
        await client.close()

    client.run(TOKEN)


def send_err(msg: str):
    client = discord.Client(intents=discord.Intents.default())

    @client.event
    async def on_ready():
        for channel in CHANNELS:
            await client.get_channel(channel).send(f"```{msg}```")
        await client.close()

    client.run(TOKEN)


if __name__ == "__main__":
    try:
        msg = get_messages()
        for channel in CHANNELS:
            send_msg(msg, channel)
    except Exception:
        send_err(traceback.format_exc())
