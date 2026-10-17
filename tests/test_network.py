import gzip
import io
import os
import socket
import ssl
import unittest
from collections import namedtuple
from unittest.mock import Mock, patch

from research_agent.network import Network, RemoteError, public_url


def addresses(*ips):
    return [(socket.AF_INET6 if ":" in ip else socket.AF_INET, socket.SOCK_STREAM, 6, "",
             (ip, 443, 0, 0) if ":" in ip else (ip, 443)) for ip in ips]


def response_socket(body=b"public document", status="200 OK", headers=None):
    headers = {"Content-Length": str(len(body)), "Connection": "close", **(headers or {})}
    wire = (f"HTTP/1.1 {status}\r\n" + "".join(f"{k}: {v}\r\n" for k, v in headers.items()) + "\r\n").encode() + body
    sock = Mock()
    sock.makefile.side_effect = lambda *args, **kwargs: io.BytesIO(wire)
    return sock


class NetworkTests(unittest.TestCase):
    def setUp(self):
        self.net = Network()
        self.env = patch.dict(os.environ, {}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_non_public_addresses_and_unsupported_urls_are_rejected(self):
        for ip in ("127.0.0.1", "10.0.0.1", "169.254.169.254", "100.64.0.1", "0.0.0.0",
                   "224.0.0.1", "::1", "fd00::1", "fe80::1", "ff02::1", "::ffff:127.0.0.1"):
            with self.subTest(ip=ip), patch("socket.getaddrinfo", return_value=addresses(ip)):
                with self.assertRaises(ValueError):
                    public_url("https://example.test/document")
        for url in ("file:///tmp/notes", "ftp://example.test", "http://@example.test", "https://a:b@example.test",
                    "http://example.test:8080", "http://[2606:4700:4700::1111%eth0]/"):
            with self.subTest(url=url), patch("socket.getaddrinfo", return_value=addresses("1.1.1.1")):
                with self.assertRaises(ValueError):
                    public_url(url)

    def test_mixed_dns_only_connects_to_validated_public_ip(self):
        sock = response_socket()
        with patch("socket.getaddrinfo", return_value=addresses("127.0.0.1", "fd00::1", "1.1.1.1")), \
                patch("urllib3.util.connection.create_connection", return_value=sock) as connect:
            body, _, final = self.net.get("http://example.test/paper")
        self.assertEqual(body, b"public document")
        self.assertEqual(final, "http://example.test/paper")
        self.assertEqual(connect.call_args.args[0], ("1.1.1.1", 80))
        self.assertIn(b"Host: example.test\r\n", b"".join(c.args[0] for c in sock.sendall.call_args_list))

    def test_connection_does_not_resolve_the_hostname_again(self):
        with patch("socket.getaddrinfo", side_effect=[addresses("1.1.1.1"), addresses("127.0.0.1")]) as resolve, \
                patch("urllib3.util.connection.create_connection", return_value=response_socket()) as connect:
            self.net.get("http://rebind.test/")
        self.assertEqual(resolve.call_count, 1)
        self.assertEqual(connect.call_args.args[0], ("1.1.1.1", 80))

    def test_ipv6_and_connection_fallback_remain_pinned(self):
        with patch("socket.getaddrinfo", return_value=addresses("2606:4700:4700::1111", "127.0.0.1", "1.1.1.1")), \
                patch("urllib3.util.connection.create_connection", side_effect=[OSError("unreachable"), response_socket()]) as connect:
            self.assertEqual(self.net.get("http://example.test/")[0], b"public document")
        self.assertEqual([c.args[0] for c in connect.call_args_list],
                         [("2606:4700:4700::1111", 80), ("1.1.1.1", 80)])

    def test_https_keeps_original_hostname_and_certificate_validation(self):
        sock = response_socket()
        with patch("socket.getaddrinfo", return_value=addresses("1.1.1.1")), \
                patch("urllib3.util.connection.create_connection", return_value=sock) as connect, \
                patch("urllib3.connection._ssl_wrap_socket_and_match_hostname",
                      return_value=namedtuple("TLSResult", "socket is_verified")(sock, True)) as wrap:
            self.net.get("https://example.test/paper")
        self.assertEqual(connect.call_args.args[0], ("1.1.1.1", 443))
        self.assertEqual(wrap.call_args.kwargs["server_hostname"], "example.test")
        self.assertEqual(wrap.call_args.kwargs["assert_hostname"], "example.test")
        self.assertEqual(wrap.call_args.kwargs["cert_reqs"], ssl.CERT_REQUIRED)

    def test_bad_certificate_is_not_accepted(self):
        with patch("socket.getaddrinfo", return_value=addresses("1.1.1.1")), \
                patch("urllib3.util.connection.create_connection", return_value=response_socket()), \
                patch("urllib3.connection._ssl_wrap_socket_and_match_hostname",
                      side_effect=ssl.SSLCertVerificationError("wrong hostname")):
            with self.assertRaises(RemoteError):
                self.net.get("https://example.test/paper")

    def test_redirect_to_private_target_never_connects(self):
        redirect = response_socket(b"", "302 Found", {"Location": "http://internal.test/secret"})
        with patch("socket.getaddrinfo", side_effect=[addresses("1.1.1.1"), addresses("127.0.0.1")]), \
                patch("urllib3.util.connection.create_connection", return_value=redirect) as connect:
            with self.assertRaises(ValueError):
                self.net.get("http://example.test/paper")
        self.assertEqual(connect.call_count, 1)

    def test_public_redirect_preserves_query_and_drops_credentials(self):
        first = response_socket(b"", "302 Found", {"Location": "http://other.test/final?own=2"})
        second = response_socket()
        with patch("socket.getaddrinfo", side_effect=[addresses("1.1.1.1"), addresses("8.8.8.8")]), \
                patch("urllib3.util.connection.create_connection", side_effect=[first, second]) as connect:
            _, _, final = self.net.get("http://example.test/start", params={"q": "AI for Science"},
                                      headers={"Authorization": "Bearer test-only", "X-Api-Key": "test-only"})
        self.assertEqual(final, "http://other.test/final?own=2")
        self.assertEqual([c.args[0] for c in connect.call_args_list], [("1.1.1.1", 80), ("8.8.8.8", 80)])
        request1 = b"".join(c.args[0] for c in first.sendall.call_args_list)
        request2 = b"".join(c.args[0] for c in second.sendall.call_args_list)
        self.assertIn(b"q=AI+for+Science", request1)
        self.assertNotIn(b"test-only", request2)
        self.assertNotIn(b"q=", request2)
        self.assertIn(b"Host: other.test", request2)

    def test_environment_proxy_does_not_bypass_destination_check(self):
        with patch.dict(os.environ, {"HTTP_PROXY": "http://127.0.0.1:9999", "ALL_PROXY": "http://127.0.0.1:9999"}), \
                patch("socket.getaddrinfo", return_value=addresses("1.1.1.1")), \
                patch("urllib3.util.connection.create_connection", return_value=response_socket()) as connect:
            self.net.get("http://example.test/")
        self.assertEqual(connect.call_args.args[0], ("1.1.1.1", 80))

    def test_decompressed_size_limit_and_json(self):
        compressed = gzip.compress(b"x" * 100)
        with patch("socket.getaddrinfo", return_value=addresses("1.1.1.1")), \
                patch("urllib3.util.connection.create_connection",
                      return_value=response_socket(compressed, headers={"Content-Encoding": "gzip"})):
            with self.assertRaisesRegex(RemoteError, "超过"):
                self.net.get("http://example.test/", limit=50)
        with patch("socket.getaddrinfo", return_value=addresses("1.1.1.1")), \
                patch("urllib3.util.connection.create_connection", return_value=response_socket(b'{"ok": true}')):
            self.assertEqual(self.net.json("http://example.test/"), {"ok": True})

    def test_redirect_limit_and_http_errors(self):
        with patch("socket.getaddrinfo", return_value=addresses("1.1.1.1")), \
                patch("urllib3.util.connection.create_connection",
                      side_effect=lambda *a, **k: response_socket(b"", "302 Found", {"Location": "/again"})) as connect:
            with self.assertRaisesRegex(RemoteError, "重定向"):
                self.net.get("http://example.test/")
        self.assertEqual(connect.call_count, 6)
        with patch("socket.getaddrinfo", return_value=addresses("1.1.1.1")), \
                patch("urllib3.util.connection.create_connection", return_value=response_socket(b"", "429 Too Many Requests")):
            with self.assertRaisesRegex(RemoteError, "429"):
                self.net.get("http://example.test/")


if __name__ == "__main__":
    unittest.main()
