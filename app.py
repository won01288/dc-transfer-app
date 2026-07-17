# DB → DC 퇴직연금 제도전환 신청 - Flask 백엔드
# Google Apps Script를 대체합니다. 프론트엔드(index.html/admin.html)도
# 이 서버가 함께 서빙하므로 별도 CORS 설정이 필요 없습니다.
# 데이터는 로컬 SQLite 파일이 아니라 Turso(libSQL)에 저장합니다. 호스팅(Render 등)
# 무료 티어는 재배포/재시작마다 디스크가 초기화될 수 있어, DB를 앱과 분리해야
# 데이터가 안전합니다. 자세한 배포 방법은 README.md 참고.
import csv
import io
import json
import os
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory
from werkzeug.security import check_password_hash, generate_password_hash

import db_client

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_ADMIN_PASSWORD = "admin1234"
KST = timezone(timedelta(hours=9))  # 호스팅 서버가 UTC로 돌아가도 제출 시각은 항상 한국 시간으로 기록

# 중도인출 안내 페이지의 초기값. 근로자퇴직급여보장법 시행령 제14조 및
# 각 사유별 실무 안내(미래에셋증권 퇴직연금 중도인출 안내 페이지 참고)를 바탕으로 작성했으며,
# 관리자 페이지 > 중도인출 안내 관리에서 자유롭게 수정할 수 있습니다.
DEFAULT_WITHDRAWAL_INTRO = (
    "퇴직연금제도는 사용자가 퇴직하는 근로자에게 퇴직급여를 지급하기 위하여 설정하는 제도로, "
    "퇴직급여를 지급받을 권리는 원칙적으로 퇴직 이후에 발생합니다. 다만 주택구입 등 법령이 정하는 사유가 "
    "발생한 경우에 한하여 예외적으로 중도인출이 허용됩니다. (근로자퇴직급여보장법 시행령 제14조, 제18조 제2항 각호)\n"
    "DC(확정기여형)·IRP(개인형퇴직연금) 제도는 중도인출이 가능하며, DB(확정급여형) 제도는 중도인출이 허용되지 않습니다.\n"
    "실제 신청 시에는 재직 중인 회사(인사담당자) 또는 접수기관(교보생명)을 통해 최신 요건과 서류를 다시 한번 확인해주세요."
)

DEFAULT_WITHDRAWAL_REASONS = [
    {
        "reasonKey": "house_purchase",
        "sortOrder": 1,
        "title": "무주택자인 근로자가 본인명의로 주택을 구입하는 경우",
        "summary": (
            "■ 신청기준 : 신청일 기준 근로자 본인 명의로 소유한 주택이 없고(배우자 등 세대원의 주택 소유 여부는 무관), "
            "근로자 본인 명의 또는 부부공동명의로 주택을 구입하는 경우 신청 가능합니다. (증여·상속은 불가)\n"
            "■ 신청시기 : 주택매매계약 체결일로부터 소유권 이전 등기 후 1개월 이내\n"
            "■ 필요서류 : 공통서류 + 구입유형별 필수서류 + (상황에 따른 추가서류)\n"
            "  - 서류 구비 후 DC 중도인출은 재직 중인 회사에, IRP 중도인출은 가까운 지점에 제출\n"
            "  - 서류발급기한 : 주민등록등·초본 3개월, 건물등기사항증명서(건축물대장) 1개월"
        ),
        "sections": [
            {
                "heading": "공통서류",
                "items": [
                    "신청양식: DC·기업형IRP 중도인출신청서(회사 명판 및 등록인감 날인), 개인형IRP 중도인출신청서(실명확인증표 첨부)",
                    "무주택자 확인서류: 현거주지 주민등록등본 (외국인등록증 소지자는 외국인등록사실증명서, 국내거소신고증 소지자는 국내거소신고사실증명서)",
                    "무주택자 확인서류: 주민등록등본 주소지의 소유주가 확인되는 건물등기사항증명서 또는 건축물관리대장 (무허가건물인 경우 무허가건물확인원)",
                    "무주택자 확인서류: 지방세 세목별 과세증명서 (전국자치단체, 전년~당해년도, 세목: 재산세(주택))",
                ],
            },
            {
                "heading": "구입유형별 필수서류",
                "items": [
                    "주택매매: 주택 매매계약서 사본 (가족 간 거래는 소유권이전 등기 후 1개월 이내 신청 및 건물등기사항증명서 추가제출, 개인 간 직거래는 계약금 입금확인증 또는 영수증 사본 추가제출)",
                    "주택분양: 분양계약서 또는 공급계약서 사본(권리의무승계내역 포함 전체) / 분양권매매계약서 사본(잔금일 이전만 신청 가능)",
                    "주택조합: 조합공급계약서 사본 (동호수 미지정 시 계약금·중도금 입금증 추가제출)",
                    "주택신축: 공사계약서·건축허가서·착공신고필증 사본 중 1종 (본인 직접 신축 시 착공신고필증만 인정)",
                    "경매/공매: 입찰보증금 입금영수증 사본, 사건 검색 인터넷 발급본, (경매)대금지급기한통지서 또는 (공매)매각결정통지서 사본",
                ],
            },
            {
                "heading": "상황에 따른 추가서류 (해당 시에만 제출)",
                "items": [
                    "잔금일 이후 등기접수일로부터 1개월 이내 신청: 매수주택 건물등기사항증명서 등 등기접수일 확인서류",
                    "매수주택과 주민등록등본상 현거주지 주소가 동일한 경우: 주민등록초본, 초본상 직전주소 기준 건물등기사항증명서 또는 건축물관리대장",
                    "보유주택 매도 후 매수: 매도계약서 또는 소유권이전등기 확인서류 (보유주택 매도일이 신규주택 매수일보다 1일 이상 빨라야 함)",
                    "배우자명의 계약체결 후 공동명의 등기 예정: 서약서(당사 양식), 매수주택 건물등기사항증명서(사후제출)",
                    "계약서상 주거용도 확인 불가: 건축물관리대장 (필요 시 재산세(주택) 납부영수증 추가)",
                ],
            },
        ],
    },
    {
        "reasonKey": "jeonse_deposit",
        "sortOrder": 2,
        "title": "무주택자인 근로자가 주거목적의 전세보증금/임차보증금을 부담하는 경우",
        "summary": (
            "■ 신청기준 : 신청일 기준 근로자 본인 명의로 소유한 주택이 없고(배우자 등 세대원의 주택 소유 여부는 무관), "
            "근로자 본인 명의 또는 동거하는 가족 명의로 계약하는 경우 신청 가능합니다.\n"
            "■ 신청시기 : 주택임대차계약 체결일로부터 잔금지급일 이후 1개월 이내\n"
            "  - DC는 하나의 사업장에서 재직 중 1회에 한해 가능, 개인형IRP는 횟수 제한 없음\n"
            "■ 필요서류 : 공통서류 + 전월세 계약서류 + (상황에 따른 추가서류)\n"
            "  - 서류 구비 후 DC는 재직 중인 회사에, IRP는 가까운 지점에 제출\n"
            "  - 서류발급기한 : 주민등록등·초본 3개월, 건물등기사항증명서(건축물대장) 1개월"
        ),
        "sections": [
            {
                "heading": "공통서류",
                "items": [
                    "신청양식: DC·기업형IRP 중도인출신청서(회사 명판 및 등록인감 날인), 개인형IRP 중도인출신청서(실명확인증표 첨부)",
                    "무주택자 확인서류: 현거주지 주민등록등본",
                    "무주택자 확인서류: 주민등록등본 주소지의 소유주가 확인되는 건물등기사항증명서 또는 건축물관리대장 (무허가건물인 경우 무허가건물확인원)",
                    "무주택자 확인서류: 지방세 세목별 과세증명서 (전국자치단체, 전년~당해년도, 세목: 재산세(주택))",
                ],
            },
            {
                "heading": "전월세 계약서류",
                "items": [
                    "전월세계약: 주택 임대차계약서 또는 전월세계약서 사본 (신규·연장계약 모두 가능하나 연장계약은 보증금 인상분이 있어야 신청 가능, 월세금만 인상은 불가 / 임차보증금 없이 월세금만 있는 계약은 중도인출 불가 / 개인 간 직거래는 계약금 입금확인증 또는 영수증 사본 추가제출)",
                ],
            },
            {
                "heading": "상황에 따른 추가서류 (해당 시에만 제출)",
                "items": [
                    "잔금일 이후 1개월 이내 신청: 계약금 입금확인증 또는 영수증 사본 (전입신고 완료 시 불필요)",
                    "임차주택과 주민등록등본상 현거주지 주소가 동일한 경우: 주민등록초본, 직전주소 기준 건물등기부등본 또는 건축물관리대장 (신규계약이나 전입신고 1년 이상, 또는 연장계약인 경우 불필요)",
                    "계약서상 주거용도 확인 불가: 건축물관리대장 (주거용 확인 불가 시 전입신고 완료 확인 또는 전입신고 서약서 및 사후 주민등록등본 제출)",
                    "동거 중인 배우자·직계존비속·형제자매 명의 계약: 주민등록등본 및 서약서(당사 양식) (그 외 타인 명의 계약은 중도인출 불가)",
                ],
            },
        ],
    },
    {
        "reasonKey": "medical_care",
        "sortOrder": 3,
        "title": "근로자 본인 또는 배우자 등 부양가족의 6개월 이상 요양이 필요한 경우",
        "summary": (
            "■ 신청기준 : 신청일 기준 직전 1년 동안 근로자 본인이 부담한 의료비 총액이 직전년도 연간임금총액의 12.5%를 "
            "초과하는 경우 신청 가능합니다. (개인형IRP는 12.5% 초과 여부와 무관)\n"
            "■ 신청시기 : 요양사유 확인일로부터 요양종료일 이후 1개월 이내\n"
            "■ 필요서류 : 공통서류 + (상황에 따른 추가서류)\n"
            "  - 서류 구비 후 DC는 재직 중인 회사에, IRP는 가까운 지점에 제출\n"
            "  - 서류발급기한 : 주민등록등·초본 3개월, 가족관계증명서 3개월, 진단서 6개월, "
            "근로소득원천징수영수증·보수총액신고서 직전년도, 소득금액증명원 직전년도 3개월"
        ),
        "sections": [
            {
                "heading": "공통서류",
                "items": [
                    "신청양식: DC·기업형IRP 중도인출신청서(회사 명판 및 등록인감 날인), 개인형IRP 중도인출신청서(실명확인증표 첨부)",
                    "6개월이상 요양 증빙서류: 국내 의사·한의사 발급 진단서 또는 소견서(6개월 이상 요양 필요 명시, 건강보험산정특례대상자는 기간 명시 불필요) 또는 건강보험공단 장기요양확인서(인정서)",
                    "연간임금총액 확인서류(개인형IRP는 불필요) [재직 1년 이상]: 전년도 근로소득원천징수영수증, (산재·고용보험) 전년도 보수총액신고서, 또는 전년도 급여명세서 (의료비 총액이 12.5% 미만이면 불가, 직전 1년간 임금총액이 전년도보다 낮은 경우 직전 1년간 급여명세서 추가 제출)",
                    "연간임금총액 확인서류 [재직 1년 미만]: 재직 중 월별 급여명세서 또는 월평균 급여 확인 가능한 객관적 서류 (연간임금총액 = 월급여 평균액×12)",
                    "의료비지출 증빙 - 지출한 의료비: 의료기관 발행 진료비계산서·영수증, 간이 외래진료비계산서, 진료비(약제비)납입확인서, 진료비세부산정내역, 약제비계산서·영수증, 장기요양기관 발행 장기요양급여비용명세서·납부확인서 (신청일 기준 직전 1년간 지출액만 인정, 카드전표·현금영수증만으로는 불인정)",
                    "의료비지출 증빙 - 지출 예정이 확정된 의료비: 의료기관 발행 청구서, 의료기기 견적서 (향후의료비추정서는 불가, 의료기기는 장애인보장구 관련 진단서·처방전·검수확인서 추가 증빙, 신청일 기준 1개월 이내 발급자료만 인정) — 지출한 의료비 서류로 12.5% 초과 기준을 충족하면 필수 아님",
                ],
            },
            {
                "heading": "상황에 따른 추가서류 (해당 시에만 제출)",
                "items": [
                    "부양가족 요양: 가족관계증명서 또는 주민등록등본 (부양가족 범위: 배우자, 본인·배우자의 직계존속·직계비속·형제자매 / 연령요건: 배우자는 제한 없음, 직계존속·형제자매는 만60세 이상, 직계비속·형제자매는 만20세 이하)",
                    "장애인인 부양가족 요양: 장애인등록증(장애인복지카드 등) 또는 중증환자장애인증명서 (연령요건 미적용)",
                    "요양 종료일 이후 1개월 이내 신청: 요양비영수증(진료비영수증)",
                    "요양 종료일 이후 사망 1개월 이내 신청: 사망진단서, 요양비영수증(진료비영수증)",
                ],
            },
        ],
    },
    {
        "reasonKey": "recovery_bankruptcy",
        "sortOrder": 4,
        "title": "「채무자 회생 및 파산에 관한 법률」에 따라 개인회생절차개시결정 또는 파산선고를 받은 경우",
        "summary": (
            "■ 신청시기\n"
            "  - 개인회생: 개인회생절차개시 결정을 받은 날로부터 5년 이내 (신청 시점에 개시결정의 효력이 진행 중이어야 함)\n"
            "  - 파산선고: 파산선고를 받은 날로부터 5년 이내\n"
            "■ 필요서류\n"
            "  - 서류 구비 후 DC는 재직 중인 회사에, IRP는 가까운 지점에 제출\n"
            "  - 서류발급기한 : 나의 사건검색 출력물 1개월 이내"
        ),
        "sections": [
            {
                "heading": "제출서류",
                "items": [
                    "신청양식: DC·기업형IRP 중도인출신청서(회사 명판 및 등록인감 날인), 개인형IRP 중도인출신청서(실명확인증표 첨부)",
                    "개인회생절차: 최근 5년 이내 회생절차 개시결정문 사본 또는 개인회생절차변제인가 확정증명원 등 객관적 확인서류 (개인워크아웃·신용회복은 중도인출 불가), 대법원 홈페이지 '나의 사건검색' 출력물 (진행경과 '전체'로 출력, 폐지·면책 결정 시 효력 종료로 신청 불가)",
                    "파산선고: 최근 5년 이내 파산선고문 사본 (면책·복권 결정 여부 불문)",
                ],
            },
        ],
    },
    {
        "reasonKey": "disaster_damage",
        "sortOrder": 5,
        "title": "재난으로 피해를 입은 경우",
        "summary": (
            "■ 신청시기 : 피해발생일로부터 3개월 이내 (단, 3개월 경과 후에도 사유가 해소되지 않았음을 증명하면 "
            "그 사유가 해소되기 전까지 신청 가능)\n"
            "■ 필요서류\n"
            "  - 서류 구비 후 DC는 재직 중인 회사에, IRP는 가까운 지점에 제출\n"
            "  - 서류발급기한 : 주민등록등·초본 3개월, 가족관계증명서 3개월, 건물등기사항증명서(건축물대장) 1개월"
        ),
        "sections": [
            {
                "heading": "제출서류",
                "items": [
                    "신청양식: DC·기업형IRP 중도인출신청서(회사 명판 및 등록인감 날인), 개인형IRP 중도인출신청서(실명확인증표 첨부)",
                    "물적피해 (재난으로 주거시설이 유실·전파·반파된 경우): (자연재난) 건축물관리대장, 피해사실확인서 또는 자연재난 피해신고서에 따른 행정기관 피해조사(확인)자료 / (사회재난) 중앙재난안전대책본부의 특별재난지역 선포 확인자료 및 주거비 지원 내역 (임차의 경우 임대차계약서 추가, 주거시설은 가입자·배우자·생계를 같이하는 부양가족 거주시설로 한정)",
                    "인적피해: (자연재난) 피해사실확인서 또는 자연재난 피해신고서에 따른 행정기관 피해조사자료 / (사회재난) 특별재난지역 선포 확인자료 및 주거비 지원 내역",
                    "인적피해 - 가입자 본인 15일 이상 입원 치료: 진단서(소견서), 진료비 세부내역서 등 입원치료 증빙자료 (감염병은 입원·격리통지서, 진료확인서 등)",
                    "인적피해 - 배우자·부양가족 실종: 실종신고접수증, 사건사고사실확인원 등 및 가족관계증명서 또는 주민등록등본 (부양가족 연령요건: 만60세 이상 직계존속·형제자매, 만20세 이하 직계비속·형제자매, 본인·배우자는 연령 불문)",
                ],
            },
        ],
    },
]

app = Flask(__name__, static_folder=None)

# 요청마다 새 커넥션을 만들지 않고 프로세스 전체에서 하나만 재사용한다.
# (libsql은 커넥션마다 내부 Tokio 스레드풀을 새로 만드는데, 요청마다 만들고
# 닫기를 반복하면 리소스가 빠듯한 환경에서 스레드 정리 중 데드락 패닉이 나서
# 워커가 통째로 멈추는 문제가 있었음)
_db = None


def get_db():
    global _db
    if _db is None:
        _db = db_client.connect()
    return _db


def init_db():
    db = get_db()
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS employees (
            emp_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            dept TEXT,
            position TEXT
        );
        CREATE TABLE IF NOT EXISTS submissions (
            emp_id TEXT PRIMARY KEY,
            name TEXT,
            dept TEXT,
            position TEXT,
            company TEXT,
            company_other TEXT,
            round TEXT,
            submitted_at TEXT,
            prev_submitted_at TEXT
        );
        CREATE TABLE IF NOT EXISTS config (
            key TEXT PRIMARY KEY,
            value TEXT
        );
        CREATE TABLE IF NOT EXISTS withdrawal_reasons (
            reason_key TEXT PRIMARY KEY,
            sort_order INTEGER,
            title TEXT,
            summary TEXT,
            sections_json TEXT
        );
        """
    )
    # 최초 실행 시에만 기본 관리자 비밀번호를 심어둡니다. (배포 후 반드시 변경!)
    row = db.execute(
        "SELECT value FROM config WHERE key = 'admin_password_hash'"
    ).fetchone()
    if row is None:
        db.execute(
            "INSERT INTO config (key, value) VALUES ('admin_password_hash', ?)",
            (generate_password_hash(DEFAULT_ADMIN_PASSWORD),),
        )
        db.execute("INSERT OR IGNORE INTO config (key, value) VALUES ('round', '')")
        db.commit()

    db.execute(
        "INSERT OR IGNORE INTO config (key, value) VALUES ('withdrawal_intro', ?)",
        (DEFAULT_WITHDRAWAL_INTRO,),
    )

    # 중도인출 안내 사유는 5가지로 고정되어 있어(법령 근거), 최초 1회만 기본값을 심어두고
    # 이후에는 관리자 페이지에서 내용만 수정합니다.
    existing_count = db.execute(
        "SELECT COUNT(*) AS cnt FROM withdrawal_reasons"
    ).fetchone()
    if not existing_count or existing_count["cnt"] == 0:
        for reason in DEFAULT_WITHDRAWAL_REASONS:
            db.execute(
                """
                INSERT INTO withdrawal_reasons
                    (reason_key, sort_order, title, summary, sections_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    reason["reasonKey"],
                    reason["sortOrder"],
                    reason["title"],
                    reason["summary"],
                    json.dumps(reason["sections"], ensure_ascii=False),
                ),
            )
    db.commit()


# ------------------------------------------------------------------
# 설정(config) 관련
# ------------------------------------------------------------------
def get_config_map(db):
    rows = db.execute("SELECT key, value FROM config").fetchall()
    return {r["key"]: r["value"] for r in rows}


def get_config(db):
    m = get_config_map(db)
    return {"success": True, "round": m.get("round", "")}


def check_admin_password(db, password):
    stored_hash = get_config_map(db).get("admin_password_hash", "")
    return bool(stored_hash) and check_password_hash(stored_hash, password or "")


def admin_login(db, password):
    if check_admin_password(db, password):
        return {"success": True}
    return {"success": False, "message": "비밀번호가 올바르지 않습니다."}


def admin_config_update(db, body):
    if not check_admin_password(db, body.get("password")):
        return {"success": False, "message": "인증이 필요합니다. 다시 로그인해주세요."}

    if "round" in body:
        db.execute(
            """
            INSERT INTO config (key, value) VALUES ('round', ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (str(body.get("round") or "").strip(),),
        )

    if "withdrawalIntro" in body:
        db.execute(
            """
            INSERT INTO config (key, value) VALUES ('withdrawal_intro', ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (str(body.get("withdrawalIntro") or "").strip(),),
        )

    new_password = body.get("newPassword")
    if new_password:
        db.execute(
            """
            INSERT INTO config (key, value) VALUES ('admin_password_hash', ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (generate_password_hash(new_password),),
        )

    db.commit()
    return {"success": True}


# ------------------------------------------------------------------
# 신청자 검증 / 제출
# ------------------------------------------------------------------
REQUIRED_SUBMIT_FIELDS = ["empId", "name", "dept", "position", "company"]


def verify_employee(db, emp_id, name):
    emp_id = (emp_id or "").strip()
    name = (name or "").strip()

    if not emp_id or not name:
        return {"success": False, "message": "사번과 성명을 모두 입력해주세요."}

    row = db.execute(
        "SELECT * FROM employees WHERE emp_id = ? AND name = ?", (emp_id, name)
    ).fetchone()

    if row is None:
        return {
            "success": False,
            "message": "사번 또는 성명을 다시 확인해주세요. 계속 문제가 있으면 인사담당자에게 문의해주세요.",
        }

    return {
        "success": True,
        "employee": {
            "empId": row["emp_id"],
            "name": row["name"],
            "dept": row["dept"] or "",
            "position": row["position"] or "",
        },
    }


def submit_application(db, body):
    # 제출 시점에도 서버단에서 다시 한번 대조 (프런트엔드 우회 방지)
    verify = verify_employee(db, body.get("empId"), body.get("name"))
    if not verify["success"]:
        return verify

    for key in REQUIRED_SUBMIT_FIELDS:
        if not str(body.get(key) or "").strip():
            return {"success": False, "message": "필수 항목이 누락되었습니다."}

    company = body["company"]
    company_other = str(body.get("companyOther") or "").strip()
    if company == "기타" and not company_other:
        return {"success": False, "message": "기타 금융사명을 입력해주세요."}

    emp_id = body["empId"].strip()
    existing = db.execute(
        "SELECT submitted_at FROM submissions WHERE emp_id = ?", (emp_id,)
    ).fetchone()
    prev_submitted_at = existing["submitted_at"] if existing else ""

    now = datetime.now(KST).isoformat()
    round_value = get_config_map(db).get("round", "")

    db.execute(
        """
        INSERT INTO submissions
            (emp_id, name, dept, position, company, company_other, round, submitted_at, prev_submitted_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(emp_id) DO UPDATE SET
            name = excluded.name,
            dept = excluded.dept,
            position = excluded.position,
            company = excluded.company,
            company_other = excluded.company_other,
            round = excluded.round,
            submitted_at = excluded.submitted_at,
            prev_submitted_at = excluded.prev_submitted_at
        """,
        (
            emp_id,
            body["name"].strip(),
            body["dept"].strip(),
            body["position"].strip(),
            company,
            company_other if company == "기타" else "",
            round_value,
            now,
            prev_submitted_at,
        ),
    )
    db.commit()
    return {"success": True, "submittedAt": now}


def get_my_submission(db, body):
    # 여러 번 수정 제출했더라도 submissions 테이블에는 최신 값으로 덮어써서
    # 저장되므로(emp_id 기준 UPSERT), 그냥 조회만 하면 최종 제출 내용이 나온다.
    verify = verify_employee(db, body.get("empId"), body.get("name"))
    if not verify["success"]:
        return verify

    emp_id = verify["employee"]["empId"]
    row = db.execute(
        "SELECT * FROM submissions WHERE emp_id = ?", (emp_id,)
    ).fetchone()
    if row is None:
        return {"success": True, "submission": None}

    company = (
        f'{row["company"]} ({row["company_other"]})'
        if row["company_other"]
        else (row["company"] or "")
    )
    return {
        "success": True,
        "submission": {
            "empId": row["emp_id"],
            "name": row["name"] or "",
            "dept": row["dept"] or "",
            "position": row["position"] or "",
            "company": company,
            "round": row["round"] or "",
            "submittedAt": row["submitted_at"] or "",
        },
    }


# ------------------------------------------------------------------
# 관리자 - 제출 목록 조회
# ------------------------------------------------------------------
def admin_list(db, body):
    if not check_admin_password(db, body.get("password")):
        return {"success": False, "message": "인증이 필요합니다. 다시 로그인해주세요."}

    rows = db.execute(
        "SELECT * FROM submissions ORDER BY submitted_at DESC"
    ).fetchall()
    result = []
    for r in rows:
        company = (
            f'{r["company"]} ({r["company_other"]})'
            if r["company_other"]
            else (r["company"] or "")
        )
        result.append(
            {
                "empId": r["emp_id"],
                "name": r["name"] or "",
                "dept": r["dept"] or "",
                "position": r["position"] or "",
                "company": company,
                "round": r["round"] or "",
                "submittedAt": r["submitted_at"] or "",
            }
        )
    return {"success": True, "rows": result}


# ------------------------------------------------------------------
# 관리자 - 사번마스터 관리
# ------------------------------------------------------------------
def admin_master_list(db, body):
    if not check_admin_password(db, body.get("password")):
        return {"success": False, "message": "인증이 필요합니다. 다시 로그인해주세요."}

    rows = db.execute("SELECT * FROM employees ORDER BY emp_id").fetchall()
    return {
        "success": True,
        "rows": [
            {
                "empId": r["emp_id"],
                "name": r["name"],
                "dept": r["dept"] or "",
                "position": r["position"] or "",
            }
            for r in rows
        ],
    }


def _upsert_employee(db, emp_id, name, dept, position):
    db.execute(
        """
        INSERT INTO employees (emp_id, name, dept, position) VALUES (?, ?, ?, ?)
        ON CONFLICT(emp_id) DO UPDATE SET
            name = excluded.name, dept = excluded.dept, position = excluded.position
        """,
        (emp_id, name, dept, position),
    )


def admin_master_import_csv(db, body):
    if not check_admin_password(db, body.get("password")):
        return {"success": False, "message": "인증이 필요합니다. 다시 로그인해주세요."}

    csv_text = body.get("csv") or ""
    reader = csv.reader(io.StringIO(csv_text))
    count = 0
    for row in reader:
        if not row or not row[0].strip():
            continue
        emp_id = row[0].strip()
        name = row[1].strip() if len(row) > 1 else ""
        dept = row[2].strip() if len(row) > 2 else ""
        position = row[3].strip() if len(row) > 3 else ""
        if not name:
            continue
        _upsert_employee(db, emp_id, name, dept, position)
        count += 1

    db.commit()
    return {"success": True, "count": count}


def admin_master_delete_all(db, body):
    if not check_admin_password(db, body.get("password")):
        return {"success": False, "message": "인증이 필요합니다. 다시 로그인해주세요."}

    db.execute("DELETE FROM employees")
    db.execute("DELETE FROM submissions")
    db.commit()
    return {"success": True}


def admin_master_add(db, body):
    if not check_admin_password(db, body.get("password")):
        return {"success": False, "message": "인증이 필요합니다. 다시 로그인해주세요."}

    emp_id = str(body.get("empId") or "").strip()
    name = str(body.get("name") or "").strip()
    if not emp_id or not name:
        return {"success": False, "message": "사번과 성명은 필수입니다."}

    dept = str(body.get("dept") or "").strip()
    position = str(body.get("position") or "").strip()
    _upsert_employee(db, emp_id, name, dept, position)
    db.commit()
    return {"success": True}


def admin_master_delete(db, body):
    if not check_admin_password(db, body.get("password")):
        return {"success": False, "message": "인증이 필요합니다. 다시 로그인해주세요."}

    emp_id = str(body.get("empId") or "").strip()
    if not emp_id:
        return {"success": False, "message": "사번이 필요합니다."}

    db.execute("DELETE FROM employees WHERE emp_id = ?", (emp_id,))
    db.execute("DELETE FROM submissions WHERE emp_id = ?", (emp_id,))
    db.commit()
    return {"success": True}


# ------------------------------------------------------------------
# 중도인출 안내
# ------------------------------------------------------------------
def _row_to_withdrawal_reason(row):
    return {
        "reasonKey": row["reason_key"],
        "sortOrder": row["sort_order"],
        "title": row["title"] or "",
        "summary": row["summary"] or "",
        "sections": json.loads(row["sections_json"]) if row["sections_json"] else [],
    }


def get_withdrawal_info(db):
    rows = db.execute(
        "SELECT * FROM withdrawal_reasons ORDER BY sort_order"
    ).fetchall()
    intro = get_config_map(db).get("withdrawal_intro", DEFAULT_WITHDRAWAL_INTRO)
    return {
        "success": True,
        "intro": intro,
        "reasons": [_row_to_withdrawal_reason(r) for r in rows],
    }


def admin_withdrawal_list(db, body):
    if not check_admin_password(db, body.get("password")):
        return {"success": False, "message": "인증이 필요합니다. 다시 로그인해주세요."}
    return get_withdrawal_info(db)


def admin_withdrawal_update(db, body):
    if not check_admin_password(db, body.get("password")):
        return {"success": False, "message": "인증이 필요합니다. 다시 로그인해주세요."}

    reason_key = str(body.get("reasonKey") or "").strip()
    existing = db.execute(
        "SELECT reason_key FROM withdrawal_reasons WHERE reason_key = ?", (reason_key,)
    ).fetchone()
    if not reason_key or existing is None:
        return {"success": False, "message": "존재하지 않는 사유입니다."}

    title = str(body.get("title") or "").strip()
    summary = str(body.get("summary") or "").strip()
    sections = body.get("sections") or []
    if not title:
        return {"success": False, "message": "제목은 필수입니다."}

    # 프런트에서 넘어온 섹션 중 제목/항목이 비어있는 것은 저장에서 제외
    cleaned_sections = []
    for section in sections:
        heading = str((section or {}).get("heading") or "").strip()
        items = [str(i).strip() for i in (section or {}).get("items") or [] if str(i).strip()]
        if heading and items:
            cleaned_sections.append({"heading": heading, "items": items})

    db.execute(
        """
        UPDATE withdrawal_reasons
        SET title = ?, summary = ?, sections_json = ?
        WHERE reason_key = ?
        """,
        (title, summary, json.dumps(cleaned_sections, ensure_ascii=False), reason_key),
    )
    db.commit()
    return {"success": True}


# ------------------------------------------------------------------
# 라우트
# ------------------------------------------------------------------
ACTIONS = {
    "verify": lambda db, body: verify_employee(db, body.get("empId"), body.get("name")),
    "submit": submit_application,
    "mySubmission": get_my_submission,
    "config": lambda db, body: get_config(db),
    "adminLogin": lambda db, body: admin_login(db, body.get("password")),
    "adminList": admin_list,
    "adminConfigUpdate": admin_config_update,
    "adminMasterList": admin_master_list,
    "adminMasterImportCsv": admin_master_import_csv,
    "adminMasterDeleteAll": admin_master_delete_all,
    "adminMasterAdd": admin_master_add,
    "adminMasterDelete": admin_master_delete,
    "withdrawalInfo": lambda db, body: get_withdrawal_info(db),
    "adminWithdrawalList": admin_withdrawal_list,
    "adminWithdrawalUpdate": admin_withdrawal_update,
}


@app.route("/api", methods=["POST"])
def api():
    body = request.get_json(force=True, silent=True) or {}
    action = body.get("action")
    handler = ACTIONS.get(action)
    if handler is None:
        return jsonify({"success": False, "message": "알 수 없는 요청입니다."})
    try:
        db = get_db()
        return jsonify(handler(db, body))
    except Exception as err:  # 관리자 화면에서 원인 파악이 가능하도록 메시지를 그대로 전달
        return jsonify({"success": False, "message": f"서버 오류: {err}"})


@app.route("/")
def serve_index():
    return send_from_directory(BASE_DIR, "index.html")


@app.route("/admin.html")
def serve_admin():
    return send_from_directory(BASE_DIR, "admin.html")


@app.route("/withdrawal.html")
def serve_withdrawal():
    return send_from_directory(BASE_DIR, "withdrawal.html")


@app.route("/css/<path:filename>")
def serve_css(filename):
    return send_from_directory(os.path.join(BASE_DIR, "css"), filename)


@app.route("/js/<path:filename>")
def serve_js(filename):
    return send_from_directory(os.path.join(BASE_DIR, "js"), filename)


init_db()

if __name__ == "__main__":
    app.run(debug=True)
