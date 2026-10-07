"""Bounded local speech transcription; never sends attendance requests."""
import json
import os
import re
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlparse
import requests

ROOT = Path.home() / 'Library/Application Support/ssu-lms-download-mcp/transcripts'

def trusted_media(url):
    parsed = urlparse(url)
    prefixes = {'ssuin-object.commonscdn.com': '/ssu-contents/contents/',
                'ssu-toast.commonscdn.com': '/contents31/ssu1000001/'}
    return (parsed.scheme == 'https' and not parsed.username
            and parsed.port in (None, 443)
            and parsed.hostname in prefixes
            and parsed.path.startswith(prefixes[parsed.hostname]))

def job_path(content_id):
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', content_id):
        raise ValueError('Invalid content_id')
    ROOT.mkdir(parents=True, exist_ok=True, mode=0o700)
    return ROOT / (content_id + '.json')

def save(path, data):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False))
    os.chmod(temporary, 0o600)
    temporary.replace(path)

def transcribe(content_id):
    from server import get, session
    path = job_path(content_id)
    media = None
    try:
        save(path, {'status':'processing', 'phase':'metadata'})
        with get(session(), 'https://commons.ssu.ac.kr/viewer/ssplayer/uniplayer_support/content.php?content_id=' + content_id) as response:
            xml = response.text
        if '<!DOCTYPE' in xml.upper() or '<!ENTITY' in xml.upper():
            raise ValueError('Unsafe XML')
        root = ET.fromstring(xml)
        duration = float(root.findtext('.//content_duration') or 0)
        if not 0 < duration <= 10800:
            raise ValueError('영상 길이가 없거나 3시간을 초과합니다.')
        filename = root.findtext('.//main_media') or ''
        uri = root.findtext('.//media_uri[@method="progressive"]') or ''
        url = uri.replace('[MEDIA_FILE]', filename)
        if not trusted_media(url):
            raise ValueError('허용된 영상 주소가 아닙니다.')
        save(path, {'status':'processing', 'phase':'temporary_media', 'duration_seconds':duration})
        fd, name = tempfile.mkstemp(suffix='.mp4', prefix='ssu-speech-')
        media = Path(name)
        size = 0
        with os.fdopen(fd, 'wb') as output, requests.get(url, headers={'Referer': 'https://commons.ssu.ac.kr/', 'User-Agent': 'Mozilla/5.0'}, stream=True, timeout=60, allow_redirects=False) as response:
            response.raise_for_status()
            if response.is_redirect:
                raise ValueError('영상 리다이렉트는 허용하지 않습니다.')
            for chunk in response.iter_content(1024*1024):
                size += len(chunk)
                if size > 1024**3:
                    raise ValueError('영상이 임시 처리 제한 1GB를 초과합니다.')
                output.write(chunk)
        save(path, {'status':'processing', 'phase':'speech_recognition', 'duration_seconds':duration})
        from faster_whisper import WhisperModel
        model = WhisperModel('small', device='cpu', compute_type='int8', cpu_threads=4)
        segments, info = model.transcribe(str(media), language='ko', vad_filter=True, beam_size=5)
        rows = []
        for segment in segments:
            rows.append({'start':round(segment.start,2), 'end':round(segment.end,2), 'text':segment.text.strip()})
            if len(rows) % 20 == 0:
                save(path, {'status':'processing','phase':'speech_recognition','processed_seconds':segment.end,'duration_seconds':duration})
        if not rows:
            raise ValueError('인식된 음성이 없습니다.')
        save(path, {'status':'complete','source':'local_speech_recognition','title':root.findtext('.//content_metadata/title'), 'duration_seconds':duration,'segments':rows,'warning':'자동 음성 인식: 전문용어와 수식은 강의록으로 대조하세요.'})
    except Exception as error:
        save(path, {'status':'failed', 'error':type(error).__name__ + ': ' + str(error)[:500]})
    finally:
        if media:
            media.unlink(missing_ok=True)

if __name__ == '__main__':
    transcribe(sys.argv[1])
