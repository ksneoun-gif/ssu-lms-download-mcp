from unittest.mock import patch
from tempfile import TemporaryDirectory
from pathlib import Path

from server import delete_staged_material, session, trusted


def test_download_origin_allowlist():
    assert trusted("https://commons.ssu.ac.kr/file.pdf")
    assert trusted("https://canvas.ssu.ac.kr/learningx/api/v1/courses")
    assert not trusted("http://commons.ssu.ac.kr/file.pdf")
    assert not trusted("https://commons.ssu.ac.kr.evil.example/file.pdf")
    assert not trusted("https://attacker@commons.ssu.ac.kr/file.pdf")


def test_session_cookie_does_not_expire_locally():
    with patch("server.STATE") as state, patch("server.time.time", return_value=10**10):
        state.exists.return_value = True
        state.read_text.return_value = '{"cookies":[{"name":"xn_api_token","value":"test","domain":"canvas.ssu.ac.kr","path":"/","expires":-1}]}'
        assert session().lms_token == "test"


def test_staged_file_cleanup_is_confined():
    with TemporaryDirectory() as directory, patch("server.STAGING", Path(directory)):
        tmp_path = Path(directory)
        staged = tmp_path / "lms-abcdefgh.pdf"
        staged.write_bytes(b"test")
        assert delete_staged_material(staged.name) == {"deleted": True}
        assert not staged.exists()
        try:
            delete_staged_material("../session.json")
        except ValueError:
            pass
        else:
            raise AssertionError("path traversal accepted")


if __name__ == "__main__":
    test_download_origin_allowlist()
    test_session_cookie_does_not_expire_locally()
    test_staged_file_cleanup_is_confined()
