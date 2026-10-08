"""공공데이터포털 '한국소비자원_생필품 가격 정보'에 새 달 파일이 올라왔으면 받아서 docs/products.json 을 다시 만든다.

    python scripts/update.py

- 데이터 페이지에서 현재 파일 ID(atchFileId)를 찾고, docs/products.json 의 fileId 와 같으면 아무것도 하지 않는다.
- 다르면 CSV(로그인 없이 받을 수 있는 공개 파일)를 받아 build_data.py 로 가공한다.
"""
import json
import re
import sys
import tempfile
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build_data  # noqa: E402

PAGE = "https://www.data.go.kr/data/15083256/fileData.do"
DOWNLOAD = "https://www.data.go.kr/cmm/cmm/fileDownload.do"
OUT = HERE.parent / "docs" / "products.json"
UA = {"User-Agent": "Mozilla/5.0 (eolmage-data updater)"}


def current_file() -> tuple[str, str]:
    html = requests.get(PAGE, headers=UA, timeout=30).text
    ids = list(dict.fromkeys(re.findall(r"atchFileId=(FILE_\d+)", html)))
    sns = list(dict.fromkeys(re.findall(r"fileDetailSn=(\d+)", html)))
    if len(ids) != 1:
        raise SystemExit(f"데이터 페이지에서 파일 ID 를 하나로 찾지 못했어요: {ids}")
    return ids[0], (sns[0] if sns else "1")


def main() -> int:
    file_id, sn = current_file()
    have = json.loads(OUT.read_text(encoding="utf-8")).get("fileId") if OUT.exists() else None
    print("포털 파일:", file_id, "| 지금 데이터:", have)
    if file_id == have:
        print("새 파일 없음")
        return 0

    with tempfile.TemporaryDirectory() as tmp:
        csv = Path(tmp) / "prices.csv"
        with requests.get(DOWNLOAD, params={"atchFileId": file_id, "fileDetailSn": sn},
                          headers={**UA, "Referer": PAGE}, timeout=300, stream=True) as r:
            r.raise_for_status()
            with open(csv, "wb") as f:
                for chunk in r.iter_content(1 << 20):
                    f.write(chunk)
        print(f"받음: {csv.stat().st_size / 1e6:.1f}MB")
        return build_data.main([str(csv), "--out", str(OUT), "--file-id", file_id])


if __name__ == "__main__":
    raise SystemExit(main())
