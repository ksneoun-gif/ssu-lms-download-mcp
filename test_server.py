from server import trusted


def test_download_origin_allowlist():
    assert trusted("https://commons.ssu.ac.kr/file.pdf")
    assert trusted("https://canvas.ssu.ac.kr/learningx/api/v1/courses")
    assert not trusted("http://commons.ssu.ac.kr/file.pdf")
    assert not trusted("https://commons.ssu.ac.kr.evil.example/file.pdf")
    assert not trusted("https://attacker@commons.ssu.ac.kr/file.pdf")


if __name__ == "__main__":
    test_download_origin_allowlist()
