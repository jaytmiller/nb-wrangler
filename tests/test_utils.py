"""Tests for nb_wrangler/utils.py."""

import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch  # noqa: F401,F811

import pytest
from ruamel.yaml import YAML

from nb_wrangler.utils import (  # noqa: F401
    get_yaml,
    yaml_dumps,
    yaml_block,
    remove_common_prefix,
    create_divider,
    elapsed_time,
    hex_time,
    DataHandlingError,
    DataIntegrityError,
    DataDownloadError,
    robust_get,
    uri_to_local_path,
    HeadInfo,
    get_head_info,
    once,
    files_to_map,
    writelines,
    sha256_bytes,
    sha256_str,
    sha256_file,
    sha256_verify_file,
    sha256_verify_data,
    sha256_verify_str,
    clear_directory,
    copy_shared_modules,
    resolve_vars,
    resolve_env,
)


class TestGetYaml:
    def test_returns_yaml_instance(self):
        yaml = get_yaml()
        assert isinstance(yaml, YAML)

    def test_preserve_quotes_is_true(self):
        yaml = get_yaml()
        assert yaml.preserve_quotes is True

    def test_indent_defaults(self):
        yaml_str = yaml_dumps({"a": 1})
        assert yaml_str is not None and "a" in yaml_str


class TestYamlDumps:
    def test_basic_roundtrip(self):
        obj = {"key": "value", "num": 42}
        result = yaml_dumps(obj)
        yaml = get_yaml()
        parsed = yaml.load(result)
        assert parsed["key"] == "value"
        assert parsed["num"] == 42

    def test_nested_preserved(self):
        obj = {"a": {"b": [1, 2, 3]}}
        result = yaml_dumps(obj)
        yaml = get_yaml()
        parsed = yaml.load(result)
        assert parsed["a"]["b"] == [1, 2, 3]


class TestYamlBlock:
    def test_literal_scalar_string_creation(self):
        s = "line1\nline2"
        result = yaml_block(s)
        assert isinstance(result, str)

    def test_multiline_in_yaml(self):
        obj = {"body": yaml_block("first\nsecond")}
        dumped = yaml_dumps(obj)
        # Literal block should start with |
        assert "|" in dumped


class TestRemoveCommonPrefix:
    def test_empty_list(self):
        assert remove_common_prefix([]) == []

    def test_single_string(self):
        result = remove_common_prefix(["hello"])
        assert result == [""]

    def test_shortest_string(self):
        result = remove_common_prefix(["short", "shorter", "shortest"])
        assert len(result[0]) < len("short")

    def test_no_common_prefix(self):
        result = remove_common_prefix(["abc", "def"])
        assert result == ["abc", "def"]

    def test_all_same_strings(self):
        result = remove_common_prefix(["hello", "hello"])
        assert result == ["", ""]


class TestCreateDivider:
    def test_centered_title(self):
        result = create_divider("TEST")
        assert " TEST " in result

    def test_custom_char(self):
        result = create_divider("X", char="#")
        assert "# X #" in result or "--- X ---" in result.replace("-", "#")

    def test_ends_with_newline(self):
        result = create_divider("test")
        assert result.endswith("\n")


class TestElapsedTime:
    def test_returns_tuple(self):
        start = datetime.datetime.now() - datetime.timedelta(hours=1)
        now, formatted = elapsed_time(start)
        assert isinstance(now, datetime.datetime)
        assert isinstance(formatted, str)

    def test_format_shape_for_hours(self):
        start = datetime.datetime.now() - datetime.timedelta(minutes=10)
        _, formatted = elapsed_time(start)
        # Should contain colons: HH:MM:SS.mmm pattern
        import re

        matches = re.search(r"\d{2}:\d{2}:\d{2}", formatted)
        assert matches is not None

    def test_format_includes_microseconds_fraction(self):
        start = datetime.datetime.now() - datetime.timedelta(minutes=5)
        _, formatted = elapsed_time(start)
        # Should end with .mmm
        assert "." in formatted


class TestHexTime:
    def test_returns_string(self):
        result = hex_time()
        assert isinstance(result, str)

    def test_no_0x_prefix(self):
        result = hex_time()
        assert not result.startswith("0x")


class TestDataHandlingErrorsHierarchy:
    def test_data_integrity_is_subclass_of_handling(self):
        assert issubclass(DataIntegrityError, DataHandlingError)

    def test_data_download_is_subclass_of_handling(self):
        assert issubclass(DataDownloadError, DataHandlingError)

    def test_error_chain(self):
        err = DataDownloadError("test")
        assert isinstance(err, RuntimeError)


class TestRobustGet:
    def test_missing_wget_raises_runtime_error(self):
        with patch("nb_wrangler.utils.shutil.which", return_value=None):
            with pytest.raises(RuntimeError, match="wget is not installed"):
                robust_get("http://example.com/file.txt")

    def test_returns_path_when_wget_available(self, tmp_path):
        with patch("nb_wrangler.utils.shutil.which", return_value="/usr/bin/wget"):
            with patch("nb_wrangler.utils.subprocess.run") as mock_run:
                mock_process = MagicMock()
                mock_process.returncode = 0
                mock_run.return_value = mock_process
                with patch("os.path.exists", return_value=False):
                    with patch.object(Path, "home", return_value=tmp_path):
                        import nb_wrangler.utils as utils_mod

                        original_wget_dir = getattr(utils_mod, "_cache_dir", None)
                        utils_mod._CACHE_DIR = str(tmp_path)
                        try:
                            result = robust_get("http://example.com/file.txt")
                            assert isinstance(result, Path)
                            assert mock_run.called
                            # Check that wget was invoked (positional args are tuples)
                            for call in mock_run.call_args_list:
                                args_tuple = call[0] if call[0] else ()
                                assert any(
                                    "wget" in str(a) for a in args_tuple
                                ), f"Expected wget call but got {args_tuple}"
                        finally:
                            if original_wget_dir is not None:
                                utils_mod._CACHE_DIR = original_wget_dir


class TestUriToLocalPath:
    def test_local_file_returns_abspath(self, tmp_path):
        fpath = tmp_path / "existing_file.txt"
        fpath.write_text("data")
        result = uri_to_local_path(str(fpath))
        assert result == str(fpath.resolve())

    def test_nonexistent_local_file_raises(self):
        with pytest.raises(FileNotFoundError, match="Local file not found"):
            uri_to_local_path("/nonexistent/path/file.txt")

    def test_file_uri_returns_abspath(self, tmp_path):
        fpath = tmp_path / "uri_file.txt"
        fpath.write_text("data")
        result = uri_to_local_path(f"file://{fpath}")
        assert result == str(fpath.resolve())

    def test_unsupported_scheme_raises_value_error(self):
        with pytest.raises(ValueError, match="Unsupported URI scheme"):
            uri_to_local_path("ftp://example.com/file.txt")


class TestHeadInfo:
    def test_tdict_returns_dict(self):
        info = HeadInfo(
            size=100, etag="abc", last_modified="Mon, 01 Jan 2026 00:00:00 GMT"
        )
        d = info.todict()
        assert isinstance(d, dict)
        assert d["size"] == 100
        assert d["etag"] == "abc"


class TestOnceDecorator:
    def test_runs_only_once(self):
        call_count = [0]

        @once
        def inc():
            call_count[0] += 1
            return call_count[0]

        inc()
        first = inc()
        assert first == 1
        assert call_count[0] == 1


class TestFilesToMap:
    def test_creates_mapping_from_files(self, tmp_path):
        f1 = tmp_path / "file1.txt"
        f1.write_text("hello\nworld")
        f2 = tmp_path / "file2.txt"
        f2.write_text("foo\nbar")
        result = files_to_map([str(f1), str(f2)])
        assert str(f1) in result
        assert str(f2) in result
        assert result[str(f1)] == ["hello", "world"]


class TestWritelines:
    def test_creates_file_and_returns_str_path(self, tmp_path):
        lines = ["a", "b", "c"]
        target = tmp_path / "sub" / "out.txt"
        result = writelines(lines, target)
        assert result == str(target)
        assert target.exists()
        content = target.read_text()
        assert "a\n" in content

    def test_parent_dir_created(self, tmp_path):
        target = tmp_path / "deep" / "nested" / "file.txt"
        writelines(["x"], target)
        assert target.exists()


class TestSha256Roundtrip:
    def test_bytes_and_str_match(self):
        data = b"hello world"
        assert sha256_bytes(data) == sha256_str("hello world")

    def test_verify_data_works(self):
        data = b"test data"
        h = sha256_bytes(data)
        assert sha256_verify_data(data, h) is True

    def test_verify_data_mismatch(self):
        assert sha256_verify_data(b"wrong", sha256_bytes(b"different")) is False

    def test_file_and_bytes_match(self, tmp_path):
        fpath = tmp_path / "data.bin"
        content = b"file content here"
        fpath.write_bytes(content)
        assert sha256_file(fpath) == sha256_bytes(content)

    def test_verify_file_mismatch(self, tmp_path):
        fpath = tmp_path / "data.bin"
        fpath.write_bytes(b"data")
        assert sha256_verify_file(str(fpath), sha256_bytes(b"different")) is False


class TestClearDirectory:
    def test_removes_contents_keeps_dir(self, tmp_path):
        (tmp_path / "file1.txt").write_text("x")
        (tmp_path / "subdir").mkdir()
        (tmp_path / "subdir" / "nested.txt").write_text("y")
        clear_directory(str(tmp_path))
        files = list(tmp_path.iterdir())
        assert len(files) == 0

    def test_raises_on_nonexistent_dir(self):
        import tempfile

        nonexistent = Path(tempfile.mkdtemp()) / "does_not_exist"
        with pytest.raises(OSError, match="does not exist"):
            clear_directory(str(nonexistent))


class TestCopySharedModules:
    def test_copies_py_files(self, tmp_path):
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "mod.py").write_text("code")
        target = tmp_path / "dst"
        target.mkdir()
        copy_shared_modules(str(src_dir / "*.py"), target)
        assert (target / "mod.py").exists()

    def test_copies_packages_with_init(self, tmp_path):
        src_dir = tmp_path / "src"
        pkg_dir = src_dir / "mypkg"
        pkg_dir.mkdir(parents=True)
        (pkg_dir / "__init__.py").write_text("package")
        target = tmp_path / "dst"
        target.mkdir()
        copy_shared_modules(str(src_dir), target)
        assert (target / "mypkg" / "__init__.py").exists()


class TestResolveVars:
    def test_dollar_var(self):
        result = resolve_vars("$HOME/project", {"HOME": "/home/alice"})
        assert result == "/home/alice/project"

    def test_braced_var(self):
        result = resolve_vars("${USER}/dir", {"USER": "bob"})
        assert result == "bob/dir"

    def test_curly_brace_var(self):
        result = resolve_vars("{VAR}/path", {"VAR": "val"})
        assert result == "val/path"

    def test_default_value_unset(self):
        result = resolve_vars("${UNSET:-fallback}", {})
        assert result == "fallback"

    def test_default_value_empty(self):
        result = resolve_vars("${EMPTY:-fallback}", {"EMPTY": ""})
        assert result == "fallback"

    def test_existing_value_skips_default(self):
        result = resolve_vars("${X:-fallback}", {"X": "actual"})
        assert result == "actual"


class TestResolveEnv:
    def test_resolves_in_dict_values(self):
        env = {"BASE": "/opt", "PATH": "$BASE/lib"}
        extra = {"BASE": "/usr/local"}
        result = resolve_env(env, extra)
        assert result["PATH"] == "/usr/local/lib"
