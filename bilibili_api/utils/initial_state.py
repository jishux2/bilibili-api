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
import httpx

async def get_free_proxies():
    """获取免费代理列表"""
    proxy_api = "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=10000&country=all&ssl=all&anonymity=all"
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(proxy_api)
            if response.status_code == 200:
                proxies = response.text.strip().split('\r\n')
                return [f"http://{proxy}" for proxy in proxies if proxy]
    except Exception as e:
        print(f"获取代理列表失败：{e}")
    return []

async def fetch_with_proxy(url, headers, cookies):
    """按顺序使用代理进行请求"""
    proxies = await get_free_proxies()
    if not proxies:
        raise Exception("没有获取到可用的代理")
    
    print(f"获取到 {len(proxies)} 个代理")
    
    for i, proxy in enumerate(proxies, 1):
        print(f"\n尝试第 {i} 个代理：{proxy}")
        try:
            async with httpx.AsyncClient(
                proxies={"http://": proxy, "https://": proxy},
                timeout=30,
                verify=False  # 关闭SSL验证
            ) as client:
                print(f"正在使用代理 {proxy} 请求URL：{url}")
                response = await client.get(
                    url,
                    headers=headers,
                    cookies=cookies,
                    follow_redirects=True
                )
                print(f"代理 {proxy} 请求状态码：{response.status_code}")
                
                if response.status_code == 200:
                    print(f"代理 {proxy} 请求成功！")
                    return response
                else:
                    print(f"代理 {proxy} 请求失败，状态码：{response.status_code}")
        except Exception as e:
            print(f"代理 {proxy} 发生错误：{e}")
    
    raise Exception("所有代理都尝试失败")

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
        headers={"User-Agent": "Mozilla/5.0"}
        response = await fetch_with_proxy(url, headers, credential.get_cookies())
        content = response.text
    except Exception as e:
        raise e
    else:
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
    print(credential.get_cookies())
    """
    同步获取初始化信息

    Args:
        url (str): 链接

        credential (Credential, optional): 用户凭证. Defaults to Credential().
    """
    try:
        resp = httpx.get(
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
