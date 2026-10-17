"""Run with python test_windows.py; never signals a Windows process."""
import ctypes
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch
import runtime
from lecture import save

assert runtime.process_running(os.getpid())
assert not runtime.process_running(-1)
for exit_code, expected in ((259, True), (0, False)):
    kernel = MagicMock()
    kernel.OpenProcess.return_value = 123
    def get_code(handle, pointer):
        ctypes.cast(pointer, ctypes.POINTER(ctypes.c_ulong))[0] = exit_code
        return 1
    kernel.GetExitCodeProcess.side_effect = get_code
    with patch('runtime.sys.platform', 'win32'), patch('ctypes.WinDLL', return_value=kernel, create=True), patch('runtime.os.kill') as kill:
        assert runtime.process_running(1234) is expected
        kill.assert_not_called()
        kernel.CloseHandle.assert_called_once_with(123)
with TemporaryDirectory() as directory:
    path = Path(directory) / 'transcript.json'
    save(path, {'text': '경제학과 가격의 신호'})
    assert json.loads(path.read_text(encoding='utf-8'))['text'] == '경제학과 가격의 신호'
print('Windows process-status branch and UTF-8 roundtrip passed')

from lecture import trusted_media
assert trusted_media("https://ssuin-object.commonscdn.com/ssu-contents/contents31/ssu1000001/video.mp4")
assert not trusted_media("https://ssuin-object.commonscdn.com/other/video.mp4")
assert not trusted_media("http://ssuin-object.commonscdn.com/ssu-contents/contents31/ssu1000001/video.mp4")
