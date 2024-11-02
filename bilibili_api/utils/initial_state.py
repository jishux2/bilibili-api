"""
bilibili_api.utils.initial_state

用于获取页码的初始化信息
"""
import re
import json
import httpx
from enum import Enum
from typing import Union

from ..exceptions import *
from .short import get_real_url
from .credential import Credential
from .network import get_session


class InitialDataType(Enum):
    """
    识别返回类型
    """

    INITIAL_STATE = "window.__INITIAL_STATE__"
    NEXT_DATA = "__NEXT_DATA__"


async def get_initial_state(
    url: str, credential: Credential = Credential()
) -> Union[dict, InitialDataType]:
    """
    异步获取初始化信息

    Args:
        url (str): 链接

        credential (Credential, optional): 用户凭证. Defaults to Credential().
    """
    try:
        session = get_session()
        resp = await session.get(
            url,
            cookies=credential.get_cookies(),
            headers={"User-Agent": "Mozilla/5.0"},
            follow_redirects=True,
        )
    except Exception as e:
        raise e
    else:
        content = resp.text
        pattern = re.compile(r"window.__INITIAL_STATE__=(\{.*?\});")
        match = re.search(pattern, content)
        if match is None:
            pattern = re.compile(
                pattern=r'<script id="__NEXT_DATA__" type="application/json">\s*(.*?)\s*</script>'
            )
            match = re.search(pattern, content)
            content_type = InitialDataType.NEXT_DATA
            if match is None:
                raise ApiException("未找到相关信息")
        else:
            content_type = InitialDataType.INITIAL_STATE
        try:
            content = json.loads(match.group(1))
        except json.JSONDecodeError:
            raise ApiException("信息解析错误")

        return content, content_type


def get_initial_state_sync(
    url: str, credential: Credential = Credential()
) -> Union[dict, InitialDataType]:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Cache-Control": "max-age=0",
        "Sec-Ch-Ua": '"Google Chrome";v="119", "Chromium";v="119", "Not?A_Brand";v="24"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1"
    }
    try:
        resp = httpx.get(
            url,
            cookies=credential.get_cookies(),
            headers=headers,
            follow_redirects=True,
            timeout=30
        )
        if resp.status_code == 412:
            raise ApiException("请求被拦截，疑似触发反爬虫机制")
        resp.raise_for_status()
    except Exception as e:
        raise e
    else:
        content = resp.text
        pattern = re.compile(r"window.__INITIAL_STATE__=(\{.*?\});")
        match = re.search(pattern, content)
        if match is None:
            pattern = re.compile(
                pattern=r'<script id="__NEXT_DATA__" type="application/json">\s*(.*?)\s*</script>'
            )
            match = re.search(pattern, content)
            content_type = InitialDataType.NEXT_DATA
            if match is None:
                raise ApiException("未找到相关信息")
        else:
            content_type = InitialDataType.INITIAL_STATE
        try:
            content = json.loads(match.group(1))
        except json.JSONDecodeError:
            raise ApiException("信息解析错误")

        return content, content_type
