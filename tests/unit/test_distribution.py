import importlib.util
import io
import tarfile
import zipfile
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("beta_distribution", Path("tools/prepare_beta.py"))
assert spec and spec.loader
distribution = importlib.util.module_from_spec(spec)
spec.loader.exec_module(distribution)


@pytest.fixture
def archives(tmp_path):
    wheel = tmp_path / "package.whl"
    info = "lynvera_ragparity-0.2.0b1.dist-info/"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("lynvera_ragparity/py.typed", "")
        for name in ("LICENSE", "NOTICE"):
            archive.writestr(info + "licenses/" + name, Path(name).read_bytes())
        archive.writestr(info + "entry_points.txt", "ragparity = lynvera_ragparity.cli:app")
        archive.writestr(
            info + "METADATA",
            (
                "Name: lynvera-ragparity\nVersion: 0.2.0b1\nRequires-Python: >=3.12\n"
                "License-Expression: Apache-2.0\n"
            ),
        )
    source = tmp_path / "package.tar.gz"
    with tarfile.open(source, "w:gz") as archive:
        for name in ("LICENSE", "NOTICE", "README.md", "pyproject.toml"):
            data = Path(name).read_bytes()
            member = tarfile.TarInfo("lynvera_ragparity-0.2.0b1/" + name)
            member.size = len(data)
            archive.addfile(member, io.BytesIO(data))
    return wheel, source


def test_archive_contract_retains_notices_and_metadata(archives):
    inventory = distribution.inspect_archives(*archives, "0.2.0b1")
    assert "LICENSE" in inventory["source_files"]
    assert "lynvera_ragparity/py.typed" in inventory["wheel_files"]


@pytest.mark.parametrize("name", ["secrets.json", ".venv/token", "../escape", "examples/.env"])
def test_source_archive_rejects_private_or_unsafe_paths(archives, name):
    wheel, source = archives
    with tarfile.open(source, "r:gz") as archive:
        entries = [(m, archive.extractfile(m).read()) for m in archive.getmembers()]
    with tarfile.open(source, "w:gz") as archive:
        for member, data in entries:
            archive.addfile(member, io.BytesIO(data))
        archive.addfile(tarfile.TarInfo("lynvera_ragparity-0.2.0b1/" + name), io.BytesIO())
    with pytest.raises(ValueError, match="Unexpected source archive content"):
        distribution.inspect_archives(wheel, source, "0.2.0b1")


def test_wheel_rejects_unrelated_files(archives):
    wheel, source = archives
    with zipfile.ZipFile(wheel, "a") as archive:
        archive.writestr("private-runtime/login.txt", "fixture")
    with pytest.raises(ValueError, match="Unexpected wheel content"):
        distribution.inspect_archives(wheel, source, "0.2.0b1")


def test_wheel_rejects_changed_notice(archives):
    wheel, source = archives
    with zipfile.ZipFile(wheel) as archive:
        entries = {name: archive.read(name) for name in archive.namelist()}
    entries["lynvera_ragparity-0.2.0b1.dist-info/licenses/NOTICE"] = b"changed"
    with zipfile.ZipFile(wheel, "w") as archive:
        for name, data in entries.items():
            archive.writestr(name, data)
    with pytest.raises(ValueError, match="legal notices differ"):
        distribution.inspect_archives(wheel, source, "0.2.0b1")
