import os
import socket
from aiohttp import web
from platform import uname
from abc import ABC


class BaseHost(ABC):
    name: str = ""
    display_name: str = ""
    emoji: str = ""
    emoji_document_id: int = 0
    multiple_sessions_per_acc: bool = False

    def __init__(self):
        if (
            not self.name
            or not self.display_name
            or not self.emoji
            or not self.emoji_document_id
        ):
            raise ValueError(
                "Host class must define name, display_name, emoji, and emoji_document_id."
            )

    async def handle_request(self, request):
        if self.is_eula_forbidden():
            return self.get_forbidden_response()

    def is_eula_forbidden(self):
        if not self.multiple_sessions_per_acc:
            return True
        return False

    def get_forbidden_response(self):
        return web.Response(status=403, body=f"Forbidden by {self.name} EULA")


class VDS(BaseHost):
    name = "VDS"
    display_name = "VDS"
    emoji = "💎"
    emoji_document_id = 5467541303938019154
    multiple_sessions_per_acc = True


class Railway(BaseHost):
    name = "RAILWAY"
    display_name = "Railway"
    emoji = "🚂"
    emoji_document_id = 5456525163795344370
    multiple_sessions_per_acc = True


class Userland(BaseHost):
    name = "USERLAND"
    display_name = "Userland"
    emoji = "🐧"
    emoji_document_id = 5458508523858062696
    multiple_sessions_per_acc = True


class Oracle(BaseHost):
    name = "ORACLE"
    display_name = "Oracle"
    emoji = "🧨"
    emoji_document_id = 5380110961090788815
    multiple_sessions_per_acc = True


class Aeza(BaseHost):
    name = "AEZA"
    display_name = "Aeza"
    emoji = "🛡"
    emoji_document_id = 5467637896789538823
    multiple_sessions_per_acc = True


class WSL(BaseHost):
    name = "WSL"
    display_name = "WSL"
    emoji = "🍀"
    emoji_document_id = 5467729112632330243
    multiple_sessions_per_acc = True


class Docker(BaseHost):
    name = "DOCKER"
    display_name = "Docker"
    emoji = "🐳"
    emoji_document_id = 5456574628933693253
    multiple_sessions_per_acc = True


class HikkaHost(BaseHost):
    name = "HIKKAHOST"
    display_name = "HikkaHost"
    emoji = "🌼"
    emoji_document_id = 5458807006905264299
    multiple_sessions_per_acc = False


class OrangePi(BaseHost):
    name = "ORANGEPI"
    display_name = "Orange Pi"
    emoji_document_id = 5467811234567890123
    emoji = "🍊"
    multiple_sessions_per_acc = True


class RaspberryPi(BaseHost):
    name = "RASPBERRYPI"
    display_name = "Raspberry Pi"
    emoji = "🍇"
    emoji_document_id = 5467892345678901234
    multiple_sessions_per_acc = True


class HostManager:
    def __init__(self):
        self._hosts = {}
        self._register_supported_hosts()

    def _register_supported_hosts(self):
        supported_hosts = [
            RaspberryPi,
            HikkaHost,
            Userland,
            OrangePi,
            Railway,
            Docker,
            Oracle,
            Aeza,
            VDS,
            WSL,
        ]

        for host in supported_hosts:
            try:
                host_class = host()
                self._hosts[host_class.name.lower()] = host_class
            except ValueError as e:
                print(f"Warning: Skipping invalid host {host_class.__name__}: {e}")

    def get_host(self, host_name):
        return self._hosts.get(host_name.lower())

    def _detect_by_uname(self):
        if "oracle" in uname().release:
            return self.get_host("oracle")
        if "microsoft-standard" in uname().release:
            return self.get_host("wsl")
        return None

    def _detect_by_device_tree(self):
        if os.path.isfile("/proc/device-tree/model"):
            with open("/proc/device-tree/model") as f:
                model = f.read()
                if "Orange" in model:
                    return self.get_host("orangepi")
                if "Raspberry" in model:
                    return self.get_host("raspberrypi")
        return None

    def _detect_by_hostname(self):
        if "aeza" in socket.gethostname().lower():
            return self.get_host("aeza")
        return None

    def _detect_by_env_vars(self):
        for host_name in self._hosts:
            if os.environ.get(host_name.upper()):
                return self.get_host(host_name)
            if os.environ.get(host_name.upper().lower()):
                return self.get_host(host_name)
        return None

    def _get_default_host(self):
        return self.get_host("vds")

    def get_current_hosting(self):
        detection_chain = [
            self._detect_by_uname,
            self._detect_by_device_tree,
            self._detect_by_hostname,
            self._detect_by_env_vars,
            self._get_default_host,
        ]
        for detect in detection_chain:
            host = detect()
            if host:
                return host
        return None

    def get_all_hosts(self):
        return list(self._hosts.values())

    def get_host_names(self):
        return list(self._hosts.keys())

    def get_emoji_document_id(self, host_name):
        host = self.get_host(host_name)
        if host:
            return host.emoji_document_id
        return None

    def host_exists(self, host_name):
        return host_name.lower() in self._hosts


host_manager = HostManager()
