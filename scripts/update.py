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
INFO = "https://www.data.go.kr/tcs/dss/selectFileDataDownload.do"   # 다운로드 버튼이 부르는 곳(2026-10 개편 뒤)
DOWNLOAD = "https://www.data.go.kr/cmm/cmm/fileDownload.do"
OUT = HERE.parent / "docs" / "products.json"
UA = {"User-Agent": "Mozilla/5.0 (eolmage-data updater)"}


def current_file(s: requests.Session) -> tuple[str, str]:
    html = s.get(PAGE, headers=UA, timeout=30).text
    ids = list(dict.fromkeys(re.findall(r"atchFileId=(FILE_\d+)", html)))      # 옛 화면: 링크에 파일 ID
    if len(ids) == 1:
        sns = re.findall(r"fileDetailSn=(\d+)", html)
        return ids[0], (sns[0] if sns else "1")
    # 새 화면(2026-10~): 버튼 onclick 의 상세 키(uddi:…)로 파일 정보를 물어봄
    pk = re.search(r'id="publicDataDetailPk"[^>]*value="([^"]+)"', html)
    if not pk:
        raise SystemExit("데이터 페이지에서 파일 키(publicDataDetailPk)를 못 찾았어요 — 화면이 또 바뀐 듯")
    r = s.post(INFO, data={"publicDataDetailPk": pk.group(1), "publicDataPk": "15083256", "atchFileId": "",
                           "fileDetailSn": "1", "publicDataTyCode": "PR0051"},
               headers={**UA, "Referer": PAGE, "X-Requested-With": "XMLHttpRequest"}, timeout=30)
    j = r.json()
    if not j.get("status") or not str(j.get("atchFileId", "")).startswith("FILE_"):
        raise SystemExit(f"파일 정보 응답이 이상해요: {str(j)[:200]}")
    return j["atchFileId"], str(j.get("fileDetailSn") or "1")


def main() -> int:
    s = requests.Session()
    file_id, sn = current_file(s)
    have = json.loads(OUT.read_text(encoding="utf-8")).get("fileId") if OUT.exists() else None
    print("포털 파일:", file_id, "| 지금 데이터:", have)
    if file_id == have:
        print("새 파일 없음")
        return 0

    with tempfile.TemporaryDirectory() as tmp:
        csv = Path(tmp) / "prices.csv"
        with s.get(DOWNLOAD, params={"atchFileId": file_id, "fileDetailSn": sn},
                          headers={**UA, "Referer": PAGE}, timeout=300, stream=True) as r:
            r.raise_for_status()
            with open(csv, "wb") as f:
                for chunk in r.iter_content(1 << 20):
                    f.write(chunk)
        print(f"받음: {csv.stat().st_size / 1e6:.1f}MB")
        return build_data.main([str(csv), "--out", str(OUT), "--file-id", file_id])


if __name__ == "__main__":
    raise SystemExit(main())
