# DB → DC 퇴직연금 제도전환 신청 - Flask 백엔드
# Google Apps Script를 대체합니다. 프론트엔드(index.html/admin.html)도
# 이 서버가 함께 서빙하므로 별도 CORS 설정이 필요 없습니다.
# 데이터는 로컬 SQLite 파일이 아니라 Turso(libSQL)에 저장합니다. 호스팅(Render 등)
# 무료 티어는 재배포/재시작마다 디스크가 초기화될 수 있어, DB를 앱과 분리해야
# 데이터가 안전합니다. 자세한 배포 방법은 README.md 참고.
import csv
import io
import os
from datetime import datetime

from dotenv import load_dotenv
from flask import Flask, g, jsonify, request, send_from_directory
from werkzeug.security import check_password_hash, generate_password_hash

import db_client

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_ADMIN_PASSWORD = "admin1234"

app = Flask(__name__, static_folder=None)


def get_db():
    if "db" not in g:
        g.db = db_client.connect()
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = db_client.connect()
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
    db.close()


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

    now = datetime.now().isoformat()
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
    db.commit()
    return {"success": True}


# ------------------------------------------------------------------
# 라우트
# ------------------------------------------------------------------
ACTIONS = {
    "verify": lambda db, body: verify_employee(db, body.get("empId"), body.get("name")),
    "submit": submit_application,
    "config": lambda db, body: get_config(db),
    "adminLogin": lambda db, body: admin_login(db, body.get("password")),
    "adminList": admin_list,
    "adminConfigUpdate": admin_config_update,
    "adminMasterList": admin_master_list,
    "adminMasterImportCsv": admin_master_import_csv,
    "adminMasterDeleteAll": admin_master_delete_all,
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


@app.route("/css/<path:filename>")
def serve_css(filename):
    return send_from_directory(os.path.join(BASE_DIR, "css"), filename)


@app.route("/js/<path:filename>")
def serve_js(filename):
    return send_from_directory(os.path.join(BASE_DIR, "js"), filename)


init_db()

if __name__ == "__main__":
    app.run(debug=True)
