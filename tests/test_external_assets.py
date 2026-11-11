import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def evaluate_assets(prelude=""):
    script = f"""
const fs = require('fs');
const vm = require('vm');
const context = {{ window: {{}}, URL }};
{prelude}
vm.runInNewContext(fs.readFileSync('js/assets.js', 'utf8'), context);
const assets = context.window.OV_ASSETS;
process.stdout.write(JSON.stringify({{
  baseUrl: assets.baseUrl,
  audio: assets.url('audio/genesis/1-m.mp3'),
  image: assets.url('images/example.webp')
}}));
"""
    result = subprocess.run(
        ["node", "-e", script],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def test_assets_have_one_general_production_base_url():
    values = evaluate_assets()

    assert values == {
        "baseUrl": "https://kleineark.com/assets/openvertaling/",
        "audio": "https://kleineark.com/assets/openvertaling/audio/genesis/1-m.mp3",
        "image": "https://kleineark.com/assets/openvertaling/images/example.webp",
    }


def test_assets_allow_one_preload_override_for_future_hosts():
    values = evaluate_assets(
        "context.window.OV_ASSET_BASE_URL = 'https://cdn.example.test/project';"
    )

    assert values["baseUrl"] == "https://cdn.example.test/project/"
    assert values["audio"] == "https://cdn.example.test/project/audio/genesis/1-m.mp3"


def test_reader_pages_load_assets_before_audio_modules():
    for name in ("index.html", "lees.html"):
        html = (ROOT / name).read_text(encoding="utf-8")
        assert html.index('src="js/assets.js"') < html.index('src="js/audio-available.js"')
        assert html.index('src="js/assets.js"') < html.index('src="js/chunked-audio.js"')


def test_every_runtime_audio_url_uses_the_general_asset_resolver():
    source = {
        name: (ROOT / name).read_text(encoding="utf-8")
        for name in (
            "js/audio-available.js",
            "js/chunked-audio.js",
            "js/app.js",
            "js/natuurgeluid.js",
        )
    }

    assert "OV_ASSETS.url" in source["js/audio-available.js"]
    assert "OV_ASSETS.url" in source["js/chunked-audio.js"]
    assert "OV_ASSETS.url" in source["js/app.js"]
    assert "OV_ASSETS.url" in source["js/natuurgeluid.js"]

    for text in source.values():
        assert "new Audio(`audio/" not in text
        assert "new Audio('audio/" not in text
        assert "return `audio/" not in text
        assert "var BASE = 'audio'" not in text


def test_service_worker_leaves_cross_origin_assets_to_the_network():
    source = (ROOT / "sw.js").read_text(encoding="utf-8")
    assert "url.origin !== self.location.origin" in source


def test_audio_publish_script_has_valid_shell_syntax():
    subprocess.run(
        ["bash", "-n", "scripts/publish_audio.sh"],
        cwd=ROOT,
        check=True,
    )


def test_binary_audio_is_ignored_but_manifests_remain_trackable():
    for path in (
        "audio/genesis/1-m.mp3",
        "audio/genesis/1/m/v1.opus",
        "audio/_pilot/sample.wav",
        "audio/_generation.log",
        "audio/genesis/1/m/generation.log",
    ):
        ignored = subprocess.run(
            ["git", "check-ignore", "-q", "--no-index", path],
            cwd=ROOT,
        )
        assert ignored.returncode == 0

    manifest = subprocess.run(
        ["git", "check-ignore", "-q", "--no-index", "audio/genesis/1/m/manifest.json"],
        cwd=ROOT,
    )
    assert manifest.returncode == 1


def test_normal_site_deploy_does_not_include_audio_tree():
    workflow = (ROOT / ".github/workflows/deploy.yml").read_text(encoding="utf-8")
    assert "        audio/\n" not in workflow
    assert "        audio/_pilot/\n" in workflow
    link = ROOT / "audio/higgs-20261109"
    assert link.is_symlink()
    assert str(link.readlink()) == "/srv/openvertaling/audio/higgs-20261109"
