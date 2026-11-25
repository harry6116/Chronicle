"""Store Chronicle's provider tokens in the operating system credential store."""

import ctypes as c
from ctypes import wintypes as wt
from contextlib import contextmanager
import os
from pathlib import Path
import stat
import sys
from threading import RLock

from chronicle_app.services.security import register_sensitive_value


PROVIDERS = ("gemini", "claude", "openai")
SERVICE = "Chronicle Provider Credentials"
RESET_MARKER = ".credential-reset-v1"
RESET_NOTICE = (
    "For your security, this update removes API keys previously saved by Chronicle, "
    "including its system vault entries and older key files. To use online models again, "
    "enter the API keys you want to use."
)
_LOCK = RLock()
_LEGACY_FILES = (
    "api_keys.json", "api_key.txt", "api_key_gemini.txt", "api_key_openai.txt",
    "api_key_anthropic.txt", "api_key_claude.txt",
)


class CredentialError(RuntimeError):
    """A safe, user-displayable credential-store error."""


def _legacy_paths(directories):
    for directory in dict.fromkeys(Path(path).resolve() for path in directories):
        for name in _LEGACY_FILES:
            yield directory / name


def credential_reset_pending(marker, *directories):
    marker = Path(marker)
    return (not marker.is_file() or marker.is_symlink()
            or any(path.exists() or path.is_symlink() for path in _legacy_paths(directories)))


@contextmanager
def _reset_lock(marker):
    # Guard multiple installed copies so a second confirmation cannot clear new vault entries.
    lock = marker.with_name(marker.name + ".lock")
    if lock.is_symlink():
        raise CredentialError("Chronicle could not safely open the credential reset state.")
    flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
    with os.fdopen(os.open(lock, flags, 0o600), "r+b") as stream:
        if os.name == "nt":
            from msvcrt import LK_NBLCK, locking
            locking(stream.fileno(), LK_NBLCK, 1)
        else:
            from fcntl import LOCK_EX, LOCK_NB, flock
            flock(stream.fileno(), LOCK_EX | LOCK_NB)
        yield


def _bind(library, name, result, *args):
    function = getattr(library, name)
    function.argtypes = args
    function.restype = result
    return function


class MacKeychain:
    def __init__(self):
        security = c.CDLL("/System/Library/Frameworks/Security.framework/Security")
        core = c.CDLL("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
        ptr = c.c_void_p
        uint = c.c_uint32
        status = c.c_int32
        names = (uint, c.c_char_p, uint, c.c_char_p)
        self._find = _bind(security, "SecKeychainFindGenericPassword", status, ptr, *names,
                           c.POINTER(uint), c.POINTER(ptr), c.POINTER(ptr))
        self._add = _bind(security, "SecKeychainAddGenericPassword", status, ptr, *names,
                          uint, c.c_char_p, c.POINTER(ptr))
        self._modify = _bind(security, "SecKeychainItemModifyAttributesAndData", status,
                             ptr, ptr, uint, c.c_char_p)
        self._delete = _bind(security, "SecKeychainItemDelete", status, ptr)
        self._free = _bind(security, "SecKeychainItemFreeContent", status, ptr, ptr)
        self._release = _bind(core, "CFRelease", None, ptr)

    @staticmethod
    def _check(status):
        if status:
            raise CredentialError(f"macOS Keychain operation failed (status {status}).")

    @staticmethod
    def _names(service, account):
        service, account = service.encode("utf-8"), account.encode("utf-8")
        return len(service), service, len(account), account

    def read(self, service, account):
        size, data = c.c_uint32(), c.c_void_p()
        status = self._find(None, *self._names(service, account), c.byref(size), c.byref(data), None)
        if status == -25300:
            return ""
        self._check(status)
        try:
            return c.string_at(data, size.value).decode("utf-8")
        finally:
            self._free(None, data)

    def _item(self, service, account):
        item = c.c_void_p()
        status = self._find(None, *self._names(service, account), None, None, c.byref(item))
        if status == -25300:
            return None
        self._check(status)
        return item

    def write(self, service, account, value):
        data = value.encode("utf-8")
        item = self._item(service, account)
        if item is None:
            self._check(self._add(None, *self._names(service, account), len(data), data, None))
            return
        try:
            self._check(self._modify(item, None, len(data), data))
        finally:
            self._release(item)

    def delete(self, service, account):
        while (item := self._item(service, account)) is not None:
            try:
                self._check(self._delete(item))
            finally:
                self._release(item)


class _WindowsCredential(c.Structure):
    _fields_ = [
        ("Flags", wt.DWORD), ("Type", wt.DWORD), ("TargetName", wt.LPWSTR),
        ("Comment", wt.LPWSTR), ("LastWritten", wt.FILETIME),
        ("CredentialBlobSize", wt.DWORD), ("CredentialBlob", c.c_void_p),
        ("Persist", wt.DWORD), ("AttributeCount", wt.DWORD), ("Attributes", c.c_void_p),
        ("TargetAlias", wt.LPWSTR), ("UserName", wt.LPWSTR),
    ]


class WindowsCredentialManager:
    def __init__(self):
        api = c.WinDLL("advapi32", use_last_error=True)
        ptr = c.POINTER(_WindowsCredential)
        self._read = _bind(api, "CredReadW", wt.BOOL, wt.LPCWSTR, wt.DWORD, wt.DWORD, c.POINTER(ptr))
        self._write = _bind(api, "CredWriteW", wt.BOOL, ptr, wt.DWORD)
        self._delete = _bind(api, "CredDeleteW", wt.BOOL, wt.LPCWSTR, wt.DWORD, wt.DWORD)
        self._free = _bind(api, "CredFree", None, c.c_void_p)

    @staticmethod
    def _target(service, account):
        return f"{service}/{account}" if account else service

    @staticmethod
    def _error(status):
        return CredentialError(f"Windows Credential Manager operation failed (status {status}).")

    def read(self, service, account):
        entry = c.POINTER(_WindowsCredential)()
        if not self._read(self._target(service, account), 1, 0, c.byref(entry)):
            status = c.get_last_error()
            if status == 1168:
                return ""
            raise self._error(status)
        try:
            data = c.string_at(entry.contents.CredentialBlob, entry.contents.CredentialBlobSize)
            if b"\0" in data:  # Windows Credential Manager UI stores generic passwords as UTF-16.
                return data.decode("utf-16-le").rstrip("\0")
            return data.decode("utf-8")
        finally:
            self._free(entry)

    def write(self, service, account, value):
        data = value.encode("utf-8")
        buffer = c.create_string_buffer(data)
        entry = _WindowsCredential(
            Type=1, TargetName=self._target(service, account), UserName=account,
            CredentialBlobSize=len(data), CredentialBlob=c.cast(buffer, c.c_void_p), Persist=2,
        )
        if not self._write(c.byref(entry), 0):
            raise self._error(c.get_last_error())

    def delete(self, service, account):
        if not self._delete(self._target(service, account), 1, 0):
            status = c.get_last_error()
            if status != 1168:
                raise self._error(status)


class CredentialStore:
    def __init__(self, native=None, *, service=SERVICE):
        if native is None:
            if sys.platform == "darwin":
                native = MacKeychain()
            elif sys.platform == "win32":
                native = WindowsCredentialManager()
            else:
                raise CredentialError("Secure API-key storage is available on macOS and Windows.")
        self.native = native
        self.service = service

    def get(self, provider):
        if provider not in PROVIDERS:
            raise ValueError("Unknown credential provider.")
        try:
            value = self.native.read(self.service, provider)
        except UnicodeError:
            raise CredentialError("The stored credential does not contain a compatible text value.") from None
        register_sensitive_value(value)
        return value

    def load(self):
        return {provider: self.get(provider) for provider in PROVIDERS}

    def _set(self, provider, value):
        register_sensitive_value(value)
        if value:
            self.native.write(self.service, provider, value)
        else:
            self.native.delete(self.service, provider)
        if self.get(provider) != value:
            raise CredentialError("The operating system could not verify the credential change.")

    def save(self, changes):
        with _LOCK:
            originals = {provider: self.get(provider) for provider in changes}
            attempted = []
            try:
                for provider, old in originals.items():
                    if changes[provider] != old:
                        attempted.append(provider)
                        self._set(provider, changes[provider])
            except CredentialError:
                for provider in reversed(attempted):
                    try:
                        self._set(provider, originals[provider])
                    except CredentialError:
                        raise CredentialError(
                            "Credential changes could not be fully rolled back. Review the vault before retrying."
                        ) from None
                raise

    def read_external(self, service, account):
        try:
            value = self.native.read(service, account)
        except UnicodeError:
            raise CredentialError("The selected item does not contain a compatible text credential.") from None
        if not value:
            raise CredentialError("No accessible credential matched the supplied item name.")
        register_sensitive_value(value)
        return value

    def reset_for_upgrade(self, marker, *directories, only_if_empty=False):
        """Clear Chronicle's old provider credentials without reading legacy key files."""
        marker = Path(marker)
        try:
            with _LOCK, _reset_lock(marker):
                if marker.is_symlink() or (marker.exists() and not marker.is_file()):
                    raise CredentialError("Chronicle could not safely verify the credential reset state.")
                pending = []
                for path in _legacy_paths(directories):
                    try:
                        info = path.lstat()
                    except FileNotFoundError:
                        continue
                    if not stat.S_ISREG(info.st_mode):
                        raise CredentialError("An older credential path is not a regular file.")
                    pending.append((path, info))
                first_reset = not marker.is_file()
                if not first_reset and not pending:
                    return True
                if only_if_empty and (pending or any(self.load().values())):
                    return False
                if first_reset and not only_if_empty:
                    for provider in PROVIDERS:
                        self.native.delete(self.service, provider)
                    if any(self.load().values()):
                        raise CredentialError("Chronicle could not verify that its saved vault keys were removed.")
                for path, original in pending:
                    current = path.lstat()
                    if (current.st_dev, current.st_ino, current.st_size, current.st_mtime_ns) != (
                        original.st_dev, original.st_ino, original.st_size, original.st_mtime_ns
                    ):
                        raise CredentialError("An older key file changed during the reset. Try again.")
                    path.unlink()
                marker.touch(mode=0o600, exist_ok=True)
                return True
        except OSError:
            raise CredentialError("Chronicle could not finish removing its older API keys. Close other copies and try again.") from None
