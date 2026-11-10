import hashlib
import io

import pytest

from automacro import updater
from automacro.models.settings import AppSettings
from automacro.updater import (
    CHECKSUM_NAME,
    INSTALLER_NAME,
    UpdateError,
    check_for_update,
    download_installer,
    installer_command,
    is_newer,
    parse_release,
    parse_version,
)

PAYLOAD = b"conteudo-do-instalador" * 1000
SHA = hashlib.sha256(PAYLOAD).hexdigest()


def release(tag="v0.1.12", digest=f"sha256:{SHA}", extra_assets=(), installer=True):
    assets = list(extra_assets)
    if installer:
        a = {"name": INSTALLER_NAME, "size": len(PAYLOAD),
             "browser_download_url": f"https://github.com/x/y/releases/download/{tag}/{INSTALLER_NAME}"}
        if digest is not None:
            a["digest"] = digest
        assets.append(a)
    return {"tag_name": tag, "html_url": "https://github.com/x/y/releases/tag/" + tag,
            "body": "notas", "assets": assets}


# ---- versões ------------------------------------------------------------------------------

def test_version_parsing_and_comparison():
    assert parse_version("v0.1.12") == (0, 1, 12, 0)
    assert is_newer("0.1.12", "0.1.9")           # comparação numérica, não de texto
    assert is_newer("0.2.0", "0.1.99")
    assert not is_newer("0.1.12", "0.1.12")
    assert not is_newer("0.1.3", "0.1.12")
    for bad in ("latest", "v1.x", "", "1.2.3.4.5"):
        with pytest.raises(ValueError):
            parse_version(bad)


# ---- interpretação da release -----------------------------------------------------------------

def test_parse_release_picks_installer_and_digest():
    info = parse_release(release())
    assert info.version == "0.1.12" and info.tag == "v0.1.12"
    assert info.sha256 == SHA and info.size == len(PAYLOAD)
    assert info.installer_url.endswith(INSTALLER_NAME)


def test_parse_release_ignores_unusable_releases():
    assert parse_release(release(tag="latest")) is None         # tag sem número de versão
    assert parse_release(release(installer=False)) is None      # sem o instalador
    assert parse_release({"tag_name": "v1.0.0", "assets": "x"}) is None
    assert parse_release({}) is None


def test_parse_release_rejects_malformed_digest():
    assert parse_release(release(digest="sha256:zzz")).sha256 is None
    assert parse_release(release(digest="md5:abcd")).sha256 is None


def test_check_for_update_only_reports_newer_versions():
    assert check_for_update("0.1.11", fetch=lambda url: release("v0.1.12")).version == "0.1.12"
    assert check_for_update("0.1.12", fetch=lambda url: release("v0.1.12")) is None
    assert check_for_update("0.1.20", fetch=lambda url: release("v0.1.12")) is None
    assert check_for_update("0.1.0", fetch=lambda url: release(tag="latest")) is None


def test_check_uses_the_project_api_url():
    seen = []
    check_for_update("0.0.1", fetch=lambda url: seen.append(url) or release())
    assert seen == [updater.API_URL] and updater.API_URL.startswith("https://api.github.com/")


# ---- segurança de rede -----------------------------------------------------------------------------

@pytest.mark.parametrize("url", [
    "http://github.com/x",                         # sem HTTPS
    "https://evil.example.com/AutoMacro-Setup.exe",
    "https://github.com.evil.example/x",           # domínio parecido
    "ftp://github.com/x",
    "file:///etc/passwd",
])
def test_blocks_urls_outside_github(url):
    with pytest.raises(UpdateError):
        updater._check_url(url)


def test_allows_github_hosts():
    for host in ("api.github.com", "github.com", "objects.githubusercontent.com",
                 "release-assets.githubusercontent.com"):
        updater._check_url(f"https://{host}/x")


# ---- download e integridade -------------------------------------------------------------------------

class FakeResponse:
    def __init__(self, data: bytes, url="https://objects.githubusercontent.com/x"):
        self._buf = io.BytesIO(data)
        self.headers = {"Content-Length": str(len(data))}
        self._url = url

    def read(self, n=-1):
        return self._buf.read(n)

    def geturl(self):
        return self._url

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_download_verifies_sha256_and_reports_progress(monkeypatch, tmp_path):
    monkeypatch.setattr(updater, "_open", lambda url, accept="*/*": FakeResponse(PAYLOAD))
    seen = []
    path = download_installer(parse_release(release()), tmp_path, progress=lambda d, t: seen.append((d, t)))
    assert path.read_bytes() == PAYLOAD
    assert seen[-1] == (len(PAYLOAD), len(PAYLOAD))


def test_tampered_download_is_rejected_and_deleted(monkeypatch, tmp_path):
    monkeypatch.setattr(updater, "_open", lambda url, accept="*/*": FakeResponse(PAYLOAD + b"x"))
    with pytest.raises(UpdateError, match="corrompido"):
        download_installer(parse_release(release()), tmp_path)
    assert not (tmp_path / INSTALLER_NAME).exists()


def test_refuses_to_install_without_any_checksum(monkeypatch, tmp_path):
    monkeypatch.setattr(updater, "_open", lambda url, accept="*/*": FakeResponse(PAYLOAD))
    with pytest.raises(UpdateError, match="integridade"):
        download_installer(parse_release(release(digest=None)), tmp_path)


def test_checksum_file_is_used_when_digest_is_missing(monkeypatch, tmp_path):
    sums = {"name": CHECKSUM_NAME,
            "browser_download_url": "https://github.com/x/y/releases/download/v0.1.12/" + CHECKSUM_NAME}

    def fake_open(url, accept="*/*"):
        if url.endswith(CHECKSUM_NAME):
            return FakeResponse(f"{SHA}  {INSTALLER_NAME}\n".encode())
        return FakeResponse(PAYLOAD)

    monkeypatch.setattr(updater, "_open", fake_open)
    info = parse_release(release(digest=None, extra_assets=[sums]))
    assert download_installer(info, tmp_path).read_bytes() == PAYLOAD


def test_download_can_be_cancelled(monkeypatch, tmp_path):
    monkeypatch.setattr(updater, "_open", lambda url, accept="*/*": FakeResponse(PAYLOAD))
    with pytest.raises(UpdateError, match="cancelado"):
        download_installer(parse_release(release()), tmp_path, cancelled=lambda: True)
    assert not (tmp_path / INSTALLER_NAME).exists()


def test_redirect_to_foreign_host_is_blocked(monkeypatch):
    class Redirected(FakeResponse):
        pass

    monkeypatch.setattr(updater.urllib.request, "urlopen",
                        lambda req, timeout=0: Redirected(b"{}", url="https://evil.example.com/x"))
    with pytest.raises(UpdateError):
        updater._open("https://github.com/x")


def test_installer_runs_silently_and_relaunches(tmp_path):
    cmd = installer_command(tmp_path / INSTALLER_NAME)
    assert "/SILENT" in cmd and "/CLOSEAPPLICATIONS" in cmd and "/RELAUNCH=1" in cmd


def test_update_setting_defaults_and_roundtrip():
    s = AppSettings()
    assert s.updates.auto_check is True
    s.updates.auto_check = False
    assert AppSettings.from_dict(s.to_dict()).updates.auto_check is False
    assert AppSettings.from_dict({"updates": {"auto_check": "sim"}}).updates.auto_check is True
