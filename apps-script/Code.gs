// ============================================================
// DB → DC 퇴직연금 제도전환 신청 - Apps Script 백엔드
// 이 파일을 Google Sheets의 확장 프로그램 > Apps Script 에 붙여넣고
// "웹앱으로 배포"하면 index.html / admin.html의 API_URL로 사용할 수 있습니다.
// ============================================================

const SHEET_SUBMISSIONS = "제출데이터";
const SHEET_MASTER = "사번마스터";
const SHEET_CONFIG = "설정";

function doPost(e) {
  let result;
  try {
    const body = JSON.parse(e.postData.contents);
    switch (body.action) {
      case "verify":
        result = verifyEmployee(body.empId, body.name);
        break;
      case "submit":
        result = submitApplication(body);
        break;
      case "config":
        result = getConfig();
        break;
      case "adminLogin":
        result = adminLogin(body.password);
        break;
      case "adminList":
        result = adminList(body);
        break;
      default:
        result = { success: false, message: "알 수 없는 요청입니다." };
    }
  } catch (err) {
    result = { success: false, message: "서버 오류: " + err.message };
  }
  return jsonResponse(result);
}

function doGet(e) {
  return jsonResponse(getConfig());
}

function jsonResponse(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(
    ContentService.MimeType.JSON
  );
}

function getSheet(name) {
  return SpreadsheetApp.getActiveSpreadsheet().getSheetByName(name);
}

// 설정 시트를 { 항목명: 값 } 형태의 객체로 변환
// 시트 구조: 1행 = 항목명(헤더), 2행 = 값 (예: A1 관리자비밀번호 / A2 4829)
function getConfigMap() {
  const sheet = getSheet(SHEET_CONFIG);
  const data = sheet.getDataRange().getValues();
  const headers = data[0] || [];
  const values = data[1] || [];
  const map = {};
  headers.forEach((h, i) => {
    if (h) map[h.toString().trim()] = values[i];
  });
  return map;
}

function getConfig() {
  const map = getConfigMap();
  return { success: true, round: map["현재접수회차"] || "" };
}

// 사번+성명이 사번마스터 시트와 일치하는지 확인
function verifyEmployee(empId, name) {
  empId = (empId || "").toString().trim();
  name = (name || "").toString().trim();

  if (!empId || !name) {
    return { success: false, message: "사번과 성명을 모두 입력해주세요." };
  }

  const sheet = getSheet(SHEET_MASTER);
  const data = sheet.getDataRange().getValues();

  for (let i = 1; i < data.length; i++) {
    const row = data[i];
    if (!row[0]) continue;
    if (row[0].toString().trim() === empId && row[1].toString().trim() === name) {
      return {
        success: true,
        employee: {
          empId: row[0].toString().trim(),
          name: row[1].toString().trim(),
          dept: row[2] ? row[2].toString().trim() : "",
          position: row[3] ? row[3].toString().trim() : "",
        },
      };
    }
  }

  return {
    success: false,
    message: "사번 또는 성명을 다시 확인해주세요. 계속 문제가 있으면 인사담당자에게 문의해주세요.",
  };
}

// 신청 내용 제출 (동일 사번 재제출 시 최신 값으로 덮어쓰기)
function submitApplication(body) {
  // 제출 시점에도 사번마스터 대조를 서버단에서 다시 한번 확인 (프런트엔드 우회 방지)
  const verify = verifyEmployee(body.empId, body.name);
  if (!verify.success) return verify;

  const required = ["empId", "name", "dept", "position", "company"];
  for (const key of required) {
    if (!body[key] || !body[key].toString().trim()) {
      return { success: false, message: "필수 항목이 누락되었습니다." };
    }
  }
  if (body.company === "기타" && !(body.companyOther || "").toString().trim()) {
    return { success: false, message: "기타 금융사명을 입력해주세요." };
  }

  const sheet = getSheet(SHEET_SUBMISSIONS);
  const data = sheet.getDataRange().getValues();
  const empId = body.empId.toString().trim();
  const now = new Date();
  const round = getConfigMap()["현재접수회차"] || "";

  let existingRowIndex = -1; // 1-based 시트 행 번호
  let prevSubmittedAt = "";
  for (let i = 1; i < data.length; i++) {
    if (data[i][0] && data[i][0].toString().trim() === empId) {
      existingRowIndex = i + 1;
      prevSubmittedAt = data[i][7] || "";
      break;
    }
  }

  const rowValues = [
    body.empId,
    body.name,
    body.dept,
    body.position,
    body.company,
    body.company === "기타" ? body.companyOther : "",
    round,
    now,
    prevSubmittedAt,
  ];

  if (existingRowIndex > 0) {
    sheet.getRange(existingRowIndex, 1, 1, rowValues.length).setValues([rowValues]);
  } else {
    sheet.appendRow(rowValues);
  }

  return { success: true, submittedAt: now.toISOString() };
}

function checkAdminPassword(password) {
  const map = getConfigMap();
  return (password || "").toString() === (map["관리자비밀번호"] || "").toString();
}

function adminLogin(password) {
  if (checkAdminPassword(password)) {
    return { success: true };
  }
  return { success: false, message: "비밀번호가 올바르지 않습니다." };
}

// 관리자 목록 조회 (검색/필터는 프런트엔드에서 2차로 한 번 더 처리)
function adminList(body) {
  if (!checkAdminPassword(body.password)) {
    return { success: false, message: "인증이 필요합니다. 다시 로그인해주세요." };
  }

  const sheet = getSheet(SHEET_SUBMISSIONS);
  const data = sheet.getDataRange().getValues();
  const rows = [];

  for (let i = 1; i < data.length; i++) {
    const r = data[i];
    if (!r[0]) continue;
    rows.push({
      empId: r[0].toString(),
      name: r[1] ? r[1].toString() : "",
      dept: r[2] ? r[2].toString() : "",
      position: r[3] ? r[3].toString() : "",
      company: r[5] ? r[4] + " (" + r[5] + ")" : r[4],
      round: r[6] ? r[6].toString() : "",
      submittedAt: r[7] instanceof Date ? r[7].toISOString() : r[7],
    });
  }

  return { success: true, rows: rows };
}
