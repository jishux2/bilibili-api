"""
bilibili_api.utils.initial_state

用于获取页面初始化信息的模块。支持直连和代理两种访问方式，
代理模式通过环境变量 USE_PROXY 控制。
"""
import re
import json
import time
import os
from enum import Enum
from typing import Union, List, Dict, Optional

import httpx
from httpx import Response

from ..exceptions import ApiException
from .credential import Credential
from .network import get_session


class InitialDataType(Enum):
    """用于标识返回数据类型的枚举类"""
    # 哔哩哔哩主站使用的数据标识
    INITIAL_STATE = "window.__INITIAL_STATE__"
    # 新版页面使用的数据标识
    NEXT_DATA = "__NEXT_DATA__"


async def get_free_proxies() -> List[str]:
    """
    异步获取免费代理列表
    
    从 proxyscrape.com 获取免费代理列表，将每个代理格式化为标准格式
    
    Returns:
        List[str]: 代理地址列表，格式如 ['http://ip:port', ...]
    """
    proxy_api = (
        "https://api.proxyscrape.com/v2/?"
        "request=displayproxies&"
        "protocol=http&"
        "timeout=10000&"
        "country=all&"
        "ssl=all&"
        "anonymity=all"
    )
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(proxy_api)
            if response.status_code == 200:
                # 将响应文本按行分割并过滤空行
                proxies = response.text.strip().split("\r\n")
                return [f"http://{proxy}" for proxy in proxies if proxy]
    except Exception as e:
        print(f"获取代理列表失败：{e}")
    
    return []


async def fetch_with_proxy(
    url: str,
    headers: Dict[str, str],
    cookies: Dict[str, str]
) -> Response:
    """
    使用代理池按顺序尝试请求，直到成功或所有代理都失败
    
    Args:
        url: 目标URL
        headers: 请求头
        cookies: Cookie信息
    
    Returns:
        Response: httpx响应对象
    
    Raises:
        Exception: 当所有代理都失败时抛出异常
    """
    proxies = await get_free_proxies()
    if not proxies:
        raise Exception("无法获取可用代理")

    print(f"已获取 {len(proxies)} 个代理")

    for i, proxy in enumerate(proxies, 1):
        print(f"\n尝试第 {i} 个代理：{proxy}")
        try:
            # 创建异步客户端，设置代理和超时
            async with httpx.AsyncClient(
                proxies={"http://": proxy, "https://": proxy},
                timeout=30.0,
                verify=False  # 禁用SSL验证以提高成功率
            ) as client:
                print(f"使用代理 {proxy} 请求：{url}")
                response = await client.get(
                    url,
                    headers=headers,
                    cookies=cookies,
                    follow_redirects=True
                )
                
                if response.status_code == 200:
                    print(f"代理 {proxy} 请求成功")
                    return response
                
                print(f"代理 {proxy} 失败，状态码：{response.status_code}")
                
        except Exception as e:
            print(f"代理 {proxy} 出错：{e}")
            continue

    raise Exception("所有代理均请求失败")


def get_free_proxies_sync() -> List[str]:
    """
    同步版本的代理获取函数，实现逻辑与异步版本相同
    
    Returns:
        List[str]: 代理地址列表
    """
    proxy_api = (
        "https://api.proxyscrape.com/v2/?"
        "request=displayproxies&"
        "protocol=http&"
        "timeout=10000&"
        "country=all&"
        "ssl=all&"
        "anonymity=all"
    )
    
    try:
        with httpx.Client() as client:
            response = client.get(proxy_api)
            if response.status_code == 200:
                proxies = response.text.strip().split("\r\n")
                return [f"http://{proxy}" for proxy in proxies if proxy]
    except Exception as e:
        print(f"获取代理列表失败：{e}")
    
    return []


def fetch_with_proxy_sync(
    url: str,
    headers: Dict[str, str],
    cookies: Dict[str, str]
) -> Response:
    """
    同步版本的代理请求函数，实现逻辑与异步版本相同
    
    Args:
        url: 目标URL
        headers: 请求头
        cookies: Cookie信息
    
    Returns:
        Response: httpx响应对象
    
    Raises:
        Exception: 当所有代理都失败时抛出异常
    """
    proxies = get_free_proxies_sync()
    if not proxies:
        raise Exception("无法获取可用代理")

    print(f"已获取 {len(proxies)} 个代理")

    for i, proxy in enumerate(proxies, 1):
        print(f"\n尝试第 {i} 个代理：{proxy}")
        try:
            transport = httpx.HTTPTransport(verify=False)
            with httpx.Client(
                proxies={"http://": proxy, "https://": proxy},
                timeout=30.0,
                transport=transport
            ) as client:
                print(f"使用代理 {proxy} 请求：{url}")
                response = client.get(
                    url,
                    headers=headers,
                    cookies=cookies,
                    follow_redirects=True
                )
                
                if response.status_code == 200:
                    print(f"代理 {proxy} 请求成功")
                    return response
                
                print(f"代理 {proxy} 失败，状态码：{response.status_code}")
                time.sleep(1)  # 请求失败后短暂延迟
                
        except Exception as e:
            print(f"代理 {proxy} 出错：{e}")
            time.sleep(1)
            continue

    raise Exception("所有代理均请求失败")


def _process_content(content: str) -> tuple[dict, InitialDataType]:
    """
    处理页面响应内容，提取并解析初始化数据
    
    Args:
        content: 页面HTML内容
    
    Returns:
        tuple: (解析后的JSON数据, 数据类型枚举)
    
    Raises:
        ApiException: 当无法找到或解析数据时抛出异常
    """
    # 首先尝试匹配旧版格式
    pattern = re.compile(r"window.__INITIAL_STATE__=(\{.*?\});")
    match = re.search(pattern, content)
    
    if match is None:
        # 旧版匹配失败，尝试匹配新版格式
        pattern = re.compile(
            r'<script id="__NEXT_DATA__" type="application/json">\s*(.*?)\s*</script>'
        )
        match = re.search(pattern, content)
        content_type = InitialDataType.NEXT_DATA
        
        if match is None:
            raise ApiException("页面中未找到初始化数据")
    else:
        content_type = InitialDataType.INITIAL_STATE
    
    try:
        # 解析提取的JSON数据
        content = json.loads(match.group(1))
    except json.JSONDecodeError:
        raise ApiException("初始化数据解析失败")

    return content, content_type


async def get_initial_state(
    url: str,
    credential: Optional[Credential] = None
) -> tuple[dict, InitialDataType]:
    """
    异步获取页面初始化数据
    
    Args:
        url: 目标页面URL
        credential: 用户凭证对象，默认为None
    
    Returns:
        tuple: (解析后的JSON数据, 数据类型枚举)
    """
    if credential is None:
        credential = Credential()
        
    headers = {"User-Agent": "Mozilla/5.0"}
    cookies = credential.get_cookies()
    print("\n当前使用的cookies:", cookies)
    
    try:
        if os.environ.get("USE_PROXY", "").lower() == "true":
            # 使用代理模式
            response = await fetch_with_proxy(url, headers, cookies)
        else:
            # 直连模式
            session = get_session()
            response = await session.get(
                url,
                cookies=cookies,
                headers=headers,
                follow_redirects=True,
            )
        
        return _process_content(response.text)
        
    except Exception as e:
        raise ApiException(f"请求失败：{e}")


def get_initial_state_sync(
    url: str,
    credential: Optional[Credential] = None
) -> tuple[dict, InitialDataType]:
    """
    同步版本的初始化数据获取函数
    
    Args:
        url: 目标页面URL
        credential: 用户凭证对象，默认为None
    
    Returns:
        tuple: (解析后的JSON数据, 数据类型枚举)
    """
    if credential is None:
        credential = Credential()
        
    headers = {"User-Agent": "Mozilla/5.0"}
    cookies = credential.get_cookies()
    print("\n当前使用的cookies:", cookies)
    
    try:
        if os.environ.get("USE_PROXY", "").lower() == "true":
            # 使用代理模式
            response = fetch_with_proxy_sync(url, headers, cookies)
        else:
            # 直连模式
            response = httpx.get(
                url,
                cookies=cookies,
                headers=headers,
                follow_redirects=True,
            )
        
        return _process_content(response.text)
        
    except Exception as e:
        raise ApiException(f"请求失败：{e}")
