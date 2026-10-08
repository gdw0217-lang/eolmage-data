"""참가격 원본 CSV를 퀴즈용 상품 목록(JSON)으로 가공한다.

원본은 판매처별 가격이 한 줄씩 들어 있다. 퀴즈에는 상품마다 '대표 가격' 하나가
필요하므로, 가장 최근 조사일의 정상가(세일·1+1 제외)를 모아 중간값을 쓴다.

사용법:
    python scripts/build_data.py <원본CSV> [--out 파일] [--file-id FILE_...]

매달 새 CSV 를 받아 돌리는 일은 scripts/update.py 가 한다 (GitHub Actions).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "products.json"
KST = dt.timezone(dt.timedelta(hours=9))
MIN_PRODUCTS = 150       # 이보다 적으면 원본 형식이 바뀐 것으로 보고 저장하지 않는다

MIN_STORES = 15          # 조사된 판매처가 이보다 적으면 대표 가격이 흔들려서 뺀다
MIN_KIND_STORES = 3      # 편의점·대형마트 비교는 각각 이만큼은 있어야 쓴다

KIND_PATTERNS = [
    ("cvs", r"GS25|CU|세븐일레븐|이마트24|미니스톱"),
    # 이마트24(편의점)·이마트에브리데이·홈플러스익스프레스(동네 슈퍼)는 대형마트가 아니다
    ("mart", r"이마트(?!24|에브리데이)|홈플러스(?!익스프레스)|롯데마트|코스트코|트레이더스"),
]

# 상품명 키워드 → 화면에 띄울 그림 문자. 위에서부터 먼저 맞는 것을 쓴다.
# 구체적인 키워드가 앞에 와야 한다 (예: '쌀 국물떡볶이'는 쌀이 아니라 떡볶이).
EMOJI_RULES = [
    (r"분유|이유식|아기밀|맘마밀|임페리얼", "🍼"),
    (r"기저귀|하기스|팸퍼스|마미포코", "🍼"),
    (r"생리대|좋은느낌|화이트 수퍼|라이너", "🩷"),
    (r"언더웨어|디펜드|라이프리|키퍼스", "🩲"),
    (r"마스크", "😷"),
    (r"밴드", "🩹"),
    (r"건전지|듀라셀|에너자이저", "🔋"),
    (r"부탄가스", "🔥"),
    (r"면도날|쉬크|PACE6|프로쉴드", "🪒"),
    (r"사료|펫|밥이보약", "🐾"),
    (r"샴푸|린스|트리트먼트|바디|비누|클렌징|로션|립|선크림|선 세럼|염색|새치|핸드워시|항균폼", "🧴"),
    (r"치약|칫솔|가그린|리스테린|페리오|2080|오랄비", "🪥"),
    (r"페브리즈|물먹는하마|습기제로|에프킬라|홈키파|컴배트|자연퐁|퍼실|액츠|프릴|홈스타|피죤|세제|섬유유연제|표백|락스", "🧽"),
    (r"물티슈|화장지|미용티슈|3겹|키친타[월올]|휴지|청소포|호일|랩$|크린랩|백$|지퍼백|고무장갑|순앤순|항균 트리오", "🧻"),
    (r"떡볶이", "🍢"),
    (r"너겟|돈까스|돈카츠|용가리|핫도그|후랑크|비엔나|베이컨|크래미|맛살|어묵|두부|햄|소시지|스팸|만두|왕교자", "🍢"),
    (r"훈제오리|토종닭|백숙|가슴살", "🍗"),
    (r"연어|명란|젓갈|젓$|액젓|미역|멸치|도시락김|참치", "🐟"),
    (r"라면|짜파|냉면|칼국수|국수|우동|쌀국수|너구리|안성탕면|왕뚜껑|소면|당면", "🍜"),
    (r"파스타|스파게티", "🍝"),
    (r"짜장|카레|곰탕|육개장|미역국|국밥|콩나물국|죽$|스프", "🍲"),
    (r"즉석밥|햇반|오뚜기밥|컵밥|유부초밥|볶음밥|김밥|쌀|현미|진미|진상미", "🍚"),
    (r"김치", "🥬"),
    (r"양파|^무$|배추|콩나물|마늘|단호박", "🥬"),
    (r"파인애플|황도|딸기잼|잼$", "🍑"),
    (r"계란|유정란|달걀|목초란", "🥚"),
    (r"버터|마가린", "🧈"),
    (r"우유|요구르트|요거트|두유|베지밀|치즈|불가리스|요플레|프로틴|셀렉스|하이뮨", "🥛"),
    (r"맥주|하이트|카스|테라|에일|막걸리|우국생", "🍺"),
    (r"소주|참이슬|처음처럼", "🍶"),
    (r"녹차|17차|티백", "🍵"),
    (r"커피|맥심|카누|맥스웰|네스프레소|돌체구스토|카페믹스|칸타타|콜드브루|바리스타", "☕"),
    (r"콜라|사이다|에이드|주스|음료|아이시스|삼다수|생수|워터|오로나민|박카스|게토레이|포카리|스프라이트|탄산수|레드불|몬스터|핫식스|컨디션|여명|헛개|이오|미닛메이드|오렌지", "🥤"),
    (r"아이스|메로나|돼지바|빵빠레|월드콘|누가바|투게더|싸만코", "🍦"),
    (r"과자|칩|스낵|쿠키|비스킷|크래커|새우깡|포카칩|초코|카카오|가나|자유시간|사탕|캔디|껌|자일리톨|후라보노|핫브레이크|젤리|마이구미|꿈틀이|오예스|보름달|만쥬|약과|호떡|아몬드|땅콩|깨수깡", "🍪"),
    (r"빵|식빵|케이크|모닝롤|버터롤", "🍞"),
    (r"스페셜K|시리얼|콘푸", "🥣"),
    (r"케찹|케첩|마요|소스|간장|된장|고추장|쌈장|토장|식초|설탕|소금|식용유|카놀라유|콩기름|포도씨유|올리브|참기름|들기름|조미료|다시다|맛선생|와사비|드레싱|고춧가루|참깨|밀가루|부침가루|올리고당|물엿|벌꿀|단무지", "🧂"),
]

SIZE_RE = re.compile(r"\(([^()]*)\)\s*$")


def kind_of(store: str) -> str | None:
    for kind, pat in KIND_PATTERNS:
        if re.search(pat, store):
            return kind
    return None


def emoji_of(name: str) -> str:
    for pat, emoji in EMOJI_RULES:
        if re.search(pat, name):
            return emoji
    return "🛒"


def nice(price: float) -> int:
    """화면에 띄울 가격은 10원 단위로 맞춘다."""
    return int(round(price / 10.0)) * 10


def split_name(raw: str) -> tuple[str, str]:
    m = SIZE_RE.search(raw)
    if not m:
        return raw.strip(), ""
    return raw[: m.start()].strip(), m.group(1).strip()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--file-id", default="")
    args = ap.parse_args(argv)
    csv, out_path = Path(args.csv), Path(args.out)
    if not csv.exists():
        print(f"원본 CSV가 없습니다: {csv}", file=sys.stderr)
        return 1

    df = pd.read_csv(csv, encoding="cp949")
    expected = {"상품명", "조사일", "판매가격", "판매업소", "제조사", "세일여부", "원플러스원"}
    missing = expected - set(df.columns)
    if missing:
        print(f"원본 형식이 바뀌었습니다. 없는 컬럼: {sorted(missing)}", file=sys.stderr)
        return 1

    latest = df["조사일"].max()
    df = df[df["조사일"] == latest]

    # 세일가·1+1 가격은 평소 가격이 아니라서 대표 가격 계산에서 뺀다.
    # 값은 빈칸·Y·N 세 가지라 'Y'만 걸러야 한다 (편의점 행은 'N'으로 채워져 있다)
    regular = df[(df["세일여부"] != "Y") & (df["원플러스원"] != "Y")].copy()
    regular = regular[regular["판매가격"] > 0]
    regular["kind"] = regular["판매업소"].astype(str).map(kind_of)

    products = []
    for raw_name, g in regular.groupby("상품명"):
        if g["판매업소"].nunique() < MIN_STORES:
            continue
        prices = g["판매가격"]
        name, size = split_name(str(raw_name))

        def kind_median(kind: str) -> int | None:
            k = g[g["kind"] == kind]["판매가격"]
            return nice(k.median()) if len(k) >= MIN_KIND_STORES else None

        products.append(
            {
                "name": name,
                "size": size,
                "maker": str(g["제조사"].mode().iat[0]) if g["제조사"].notna().any() else "",
                "price": nice(prices.median()),
                # 극단값 하나에 휘둘리지 않게 하위·상위 5%를 최저·최고로 쓴다
                "low": nice(prices.quantile(0.05)),
                "high": nice(prices.quantile(0.95)),
                "stores": int(g["판매업소"].nunique()),
                "cvs": kind_median("cvs"),
                "mart": kind_median("mart"),
                "emoji": emoji_of(name),
            }
        )

    products.sort(key=lambda p: p["name"])
    for i, p in enumerate(products):
        p["id"] = i

    if len(products) < MIN_PRODUCTS:
        print(f"상품이 {len(products)}개뿐이라 저장하지 않습니다 (원본 형식 확인 필요)", file=sys.stderr)
        return 1

    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "source": "한국소비자원 참가격",
        "surveyDate": latest,
        "fileId": args.file_id,
        "generatedAt": dt.datetime.now(KST).isoformat(timespec="minutes"),
        "products": products,
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    with_both = sum(1 for p in products if p["cvs"] and p["mart"])
    print(f"조사일 {latest} · 상품 {len(products)}개 저장 → {out_path} ({out_path.stat().st_size / 1024:.0f}KB)")
    print(f"편의점·대형마트 가격이 모두 있는 상품 {with_both}개")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
