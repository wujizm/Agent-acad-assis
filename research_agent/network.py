import ipaddress
import json
import socket
import ssl
from urllib.parse import urljoin, urlsplit

import requests
import urllib3


class RemoteError(ValueError):
    pass


def _url_parts(url):
    parts = urlsplit(url)
    if (parts.scheme not in ("http", "https") or not parts.hostname
            or parts.username is not None or parts.password is not None or "%" in parts.hostname):
        raise ValueError("请输入有效的公开 http/https 网址")
    if parts.port not in (None, 80, 443):
        raise ValueError("资料网址只支持标准 HTTP/HTTPS 端口")
    return parts


def _public_destination(url):
    parts = _url_parts(url)
    try:
        addresses = socket.getaddrinfo(parts.hostname, parts.port or (443 if parts.scheme == "https" else 80),
                                       type=socket.SOCK_STREAM)
    except OSError as exc:
        raise RemoteError("无法解析资料网址的域名") from exc
    public = []
    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        check = getattr(ip, "ipv4_mapped", None) or ip
        if check.is_global and not check.is_multicast and not check.is_reserved and "%" not in str(ip):
            if str(ip) not in public:
                public.append(str(ip))
    if not public:
        raise ValueError("资料抓取不允许访问本机或内网地址")
    return parts, public


def public_url(url):
    _public_destination(url)
    return url


class Network:
    def __init__(self, contact=""):
        self.agent = "MaterialsResearchLibrary/0.1" + (f" (mailto:{contact})" if contact else "")

    def get(self, url, params=None, headers=None, limit=20_000_000):
        headers = {"User-Agent": self.agent, **(headers or {})}
        current = url
        for _ in range(6):
            _url_parts(current)
            request = requests.Request("GET", current, params=params, headers=headers).prepare()
            parts, addresses = _public_destination(request.url)
            request.headers["Host"] = parts.netloc
            request.headers.setdefault("Accept-Encoding", "gzip, deflate")
            location = None
            try:
                for index, address in enumerate(addresses):
                    # Numeric pool hosts pin the connection to an already validated address.
                    # Direct pools do not inherit environment/system proxies or netrc credentials.
                    options = {"timeout": urllib3.Timeout(connect=10, read=35), "retries": False}
                    if parts.scheme == "https":
                        pool = urllib3.HTTPSConnectionPool(address, port=parts.port or 443, **options,
                            server_hostname=parts.hostname, assert_hostname=parts.hostname,
                            cert_reqs=ssl.CERT_REQUIRED, ca_certs=requests.certs.where())
                    else:
                        pool = urllib3.HTTPConnectionPool(address, port=parts.port or 80, **options)
                    with pool:
                        try:
                            response = pool.urlopen("GET", request.path_url, headers=request.headers,
                                                    redirect=False, retries=False, preload_content=False)
                        except (urllib3.exceptions.NewConnectionError, urllib3.exceptions.ConnectTimeoutError):
                            if index + 1 == len(addresses):
                                raise
                            continue  # Fall back only to another address from this validated set.
                        with response:
                            if response.status in (301, 302, 303, 307, 308) and "Location" in response.headers:
                                location = response.headers["Location"]
                                break
                            if response.status >= 400:
                                raise RemoteError(f"{parts.hostname} 返回 HTTP {response.status}")
                            payload = bytearray()
                            for part in response.stream(65536, decode_content=True):
                                payload.extend(part)
                                if len(payload) > limit:
                                    raise RemoteError("资料超过大小限制（默认 20 MB），请下载后按章节导入")
                            return bytes(payload), response.headers.get("Content-Type", ""), request.url
            except urllib3.exceptions.HTTPError as exc:
                raise RemoteError(f"{parts.hostname} 连接失败、证书校验失败或超时") from exc
            if location is not None:
                current = urljoin(request.url, location)
                params = None
                headers = {"User-Agent": self.agent}  # Never forward credentials to a redirect target.
        raise RemoteError("网页重定向次数过多")

    def json(self, url, params=None, headers=None):
        body, _, _ = self.get(url, params, headers)
        try:
            return json.loads(body)
        except (ValueError, UnicodeDecodeError) as exc:
            raise RemoteError("远程服务未返回有效 JSON") from exc
