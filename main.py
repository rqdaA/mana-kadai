import requests
import re
import discord
import logging
import os
import traceback
from datetime import datetime, timedelta
from html import unescape

TOKEN = os.getenv("BOT_TOKEN", "")
CHANNEL = int(os.getenv("CHANNEL", ""))
MANADA_USER = os.getenv("MANADA_USER", "")
MANADA_PWD = os.getenv("MANADA_PWD", "")
AUTH_URL = os.getenv("AUTH_URL", "")
MANADA_URL = os.getenv("MANADA_URL", "")

if not all(
    [e for e in (TOKEN, CHANNEL, MANADA_USER, MANADA_PWD, AUTH_URL, MANADA_URL)]
):
    print("Not all variables are set")
    exit(1)

HIGH_PRI = 0xFF0000
MEDIUM_PRI = 0xF58216
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


def get_messages() -> list[discord.Embed]:
    headers = {"User-Agent": UA}

    cookies = get_shib()

    r = requests.get(
        f"{MANADA_URL}/ct/home_library_query",
        cookies=cookies,
        headers=headers,
    )

    res = []
    for e in r.text.split("myassignments-title")[1:]:
        due = re.findall(r'td-period">(.*)</td>', e)
        priority = 0
        if due and len(due) >= 2 and due[1].startswith("202"):
            today = datetime.today()
            tomorrow = today + timedelta(days=1)
            if due[1].startswith(today.strftime("%Y-%m-%d")):
                priority = 1
            elif due[1].startswith(tomorrow.strftime("%Y-%m-%d")):
                priority = 2
            else:
                continue
        else:
            continue

        url_name = re.search(r'<a href="(.+)">(.+?)</a>', e)
        course = re.search(r'class="mycourse-title"><.*>(.*)</a>', e)
        if not url_name or not course:
            continue

        url = f"{MANADA_URL}/ct/" + url_name.group(1)
        name = url_name.group(2).replace("amp;", "")
        description = "コース: " + course.group(1).replace("amp;", "")
        description += "\n締切: " + due[1]
        color = [0x000000, HIGH_PRI, MEDIUM_PRI][priority]
        embed = discord.Embed(title=name, url=url, color=color)
        embed.add_field(
            name="コース", value=course.group(1).replace("amp;", ""), inline=False
        )
        embed.add_field(name="締切", value=due[1], inline=False)
        res.append(embed)
    return res


def send_msg(msgs: list[discord.Embed] | str):
    client = discord.Client(intents=discord.Intents.default())

    @client.event
    async def on_ready():
        if type(msgs) is str:
            await client.get_channel(CHANNEL).send(f'```\n{msgs}\n```')
        else:
            for msg in msgs:
                await client.get_channel(CHANNEL).send(embed=msg)
        await client.close()

    client.run(TOKEN)


if __name__ == "__main__":
    try:
        msg = get_messages()
        send_msg(msg)
    except Exception:
        send_msg(traceback.format_exc())
