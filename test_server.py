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


def test_transcript_id_confined():
    from lecture import job_path
    for bad in ('../session', '/tmp/x', 'x?token=secret'):
        try:
            job_path(bad)
        except ValueError:
            pass
        else:
            raise AssertionError('transcript path traversal accepted')


def test_live_auth_rejects_stale_cookie():
    from server import auth_status
    with patch('server.list_courses', side_effect=RuntimeError('expired')):
        assert auth_status()['authenticated'] is False


test_transcript_id_confined()
test_live_auth_rejects_stale_cookie()

def test_media_origins():
    from lecture import trusted_media
    assert trusted_media('https://ssuin-object.commonscdn.com/ssu-contents/contents/x.mp4')
    assert trusted_media('https://ssuin-object.commonscdn.com/ssu-contents/contents31/ssu1000001/x.mp4')
    assert trusted_media('https://ssu-toast.commonscdn.com/contents31/ssu1000001/x.mp4')
    for url in ('http://ssu-toast.commonscdn.com/contents31/ssu1000001/x.mp4',
                'https://ssu-toast.commonscdn.com.evil.test/contents31/ssu1000001/x.mp4',
                'https://user@ssu-toast.commonscdn.com/contents31/ssu1000001/x.mp4',
                'https://ssu-toast.commonscdn.com:8443/contents31/ssu1000001/x.mp4',
                'https://ssu-toast.commonscdn.com/other/x.mp4',
                'https://ssuin-object.commonscdn.com/ssu-contents/contents31/ssu1000002/x.mp4',
                'https://ssuin-object.commonscdn.com/ssu-contents/contents31/ssu1000001-evil/x.mp4',
                'http://ssuin-object.commonscdn.com/ssu-contents/contents31/ssu1000001/x.mp4',
                'https://ssuin-object.commonscdn.com.evil.test/ssu-contents/contents31/ssu1000001/x.mp4'):
        assert not trusted_media(url)

test_media_origins()
