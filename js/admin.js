const $ = (id) => document.getElementById(id);

// 로그인한 비밀번호는 브라우저 탭이 열려있는 동안만 sessionStorage에 보관합니다.
// (탭을 닫으면 사라짐 / localStorage와 달리 영구 저장되지 않음)
// 목록 조회 등 모든 요청에 이 비밀번호를 함께 보내고, Apps Script 서버에서 매번 재검증합니다.
let adminPassword = sessionStorage.getItem("adminPassword") || "";
let allRows = [];

function showMessage(containerId, text, type) {
  const el = $(containerId);
  el.innerHTML = text ? `<div class="message ${type}">${text}</div>` : "";
}

$("btnLogin").addEventListener("click", async () => {
  const password = $("inputPassword").value;
  if (!password) {
    showMessage("loginMessage", "비밀번호를 입력해주세요.", "error");
    return;
  }

  $("btnLogin").disabled = true;
  $("btnLogin").textContent = "확인 중...";

  try {
    const res = await callApi("adminLogin", { password });
    if (res.success) {
      adminPassword = password;
      sessionStorage.setItem("adminPassword", password);
      $("loginSection").classList.add("hidden");
      $("listSection").classList.remove("hidden");
      await loadList();
    } else {
      showMessage("loginMessage", res.message || "비밀번호가 올바르지 않습니다.", "error");
    }
  } catch (err) {
    showMessage("loginMessage", "로그인 중 오류: " + err.message, "error");
  } finally {
    $("btnLogin").disabled = false;
    $("btnLogin").textContent = "로그인";
  }
});

async function loadList() {
  $("resultCount").textContent = "불러오는 중...";
  try {
    const res = await callApi("adminList", { password: adminPassword });
    if (!res.success) {
      // 비밀번호가 만료/변경된 경우 다시 로그인 화면으로
      sessionStorage.removeItem("adminPassword");
      $("listSection").classList.add("hidden");
      $("loginSection").classList.remove("hidden");
      showMessage("loginMessage", res.message || "다시 로그인해주세요.", "error");
      return;
    }
    allRows = res.rows;
    populateFilters(allRows);
    applyFilters();
  } catch (err) {
    $("resultCount").textContent = "목록을 불러오지 못했습니다: " + err.message;
  }
}

function populateFilters(rows) {
  const rounds = [...new Set(rows.map((r) => r.round).filter(Boolean))];
  const companies = [...new Set(rows.map((r) => r.company).filter(Boolean))];

  const roundSelect = $("filterRound");
  const keepRound = roundSelect.value;
  roundSelect.innerHTML = '<option value="">전체 접수회차</option>' +
    rounds.map((r) => `<option value="${r}">${r}</option>`).join("");
  roundSelect.value = keepRound;

  const companySelect = $("filterCompany");
  const keepCompany = companySelect.value;
  companySelect.innerHTML = '<option value="">전체 희망금융사</option>' +
    companies.map((c) => `<option value="${c}">${c}</option>`).join("");
  companySelect.value = keepCompany;
}

function applyFilters() {
  const search = $("searchInput").value.trim();
  const round = $("filterRound").value;
  const company = $("filterCompany").value;

  let filtered = allRows;
  if (search) {
    filtered = filtered.filter(
      (r) =>
        String(r.empId).includes(search) ||
        r.name.includes(search) ||
        r.dept.includes(search)
    );
  }
  if (round) filtered = filtered.filter((r) => r.round === round);
  if (company) filtered = filtered.filter((r) => r.company === company);

  renderTable(filtered);
}

function renderTable(rows) {
  $("resultCount").textContent = `총 ${rows.length}건`;
  $("tableBody").innerHTML = rows
    .map((r, idx) => {
      const dt = r.submittedAt ? new Date(r.submittedAt).toLocaleString("ko-KR") : "";
      return `
        <tr data-idx="${idx}">
          <td>${r.round || ""}</td>
          <td>${dt}</td>
          <td>${r.empId}</td>
          <td>${r.name}</td>
          <td>${r.dept}</td>
          <td>${r.position}</td>
          <td>${r.company}</td>
        </tr>
      `;
    })
    .join("");

  $("tableBody").querySelectorAll("tr").forEach((tr) => {
    tr.addEventListener("click", () => showDetail(rows[Number(tr.dataset.idx)]));
  });
}

function showDetail(row) {
  const dt = row.submittedAt ? new Date(row.submittedAt).toLocaleString("ko-KR") : "";
  $("detailTable").innerHTML = `
    <tr><th>접수회차</th><td>${row.round || ""}</td></tr>
    <tr><th>제출일시</th><td>${dt}</td></tr>
    <tr><th>사번</th><td>${row.empId}</td></tr>
    <tr><th>성명</th><td>${row.name}</td></tr>
    <tr><th>부서</th><td>${row.dept}</td></tr>
    <tr><th>직급</th><td>${row.position}</td></tr>
    <tr><th>희망금융사</th><td>${row.company}</td></tr>
  `;
  $("detailModal").classList.remove("hidden");
}

$("btnCloseModal").addEventListener("click", () => {
  $("detailModal").classList.add("hidden");
});

$("searchInput").addEventListener("input", applyFilters);
$("filterRound").addEventListener("change", applyFilters);
$("filterCompany").addEventListener("change", applyFilters);
$("btnRefresh").addEventListener("click", loadList);

// 신청 목록 <-> 설정/사번마스터 관리 화면 전환
$("btnShowList").addEventListener("click", () => {
  $("listView").classList.remove("hidden");
  $("manageView").classList.add("hidden");
});

$("btnShowManage").addEventListener("click", async () => {
  $("listView").classList.add("hidden");
  $("manageView").classList.remove("hidden");
  await loadMasterList();
});

// 접수회차 저장
$("btnSaveRound").addEventListener("click", async () => {
  const round = $("inputRound").value.trim();
  try {
    const res = await callApi("adminConfigUpdate", { password: adminPassword, round });
    showMessage(
      "configMessage",
      res.success ? "저장되었습니다." : res.message || "저장에 실패했습니다.",
      res.success ? "success" : "error"
    );
  } catch (err) {
    showMessage("configMessage", "저장 중 오류: " + err.message, "error");
  }
});

// 관리자 비밀번호 변경
$("btnSavePassword").addEventListener("click", async () => {
  const newPassword = $("inputNewPassword").value;
  if (!newPassword) {
    showMessage("configMessage", "새 비밀번호를 입력해주세요.", "error");
    return;
  }
  try {
    const res = await callApi("adminConfigUpdate", { password: adminPassword, newPassword });
    if (res.success) {
      // 방금 바꾼 비밀번호로 세션을 갱신해야 이후 요청도 계속 인증됨
      adminPassword = newPassword;
      sessionStorage.setItem("adminPassword", newPassword);
      $("inputNewPassword").value = "";
      showMessage("configMessage", "비밀번호가 변경되었습니다.", "success");
    } else {
      showMessage("configMessage", res.message || "변경에 실패했습니다.", "error");
    }
  } catch (err) {
    showMessage("configMessage", "변경 중 오류: " + err.message, "error");
  }
});

// 사번마스터 목록 조회 (등록 인원 수 + 테이블)
let masterRows = [];

async function loadMasterList() {
  try {
    const res = await callApi("adminMasterList", { password: adminPassword });
    if (res.success) {
      masterRows = res.rows;
      $("masterCount").textContent = `현재 등록 인원: ${masterRows.length}명`;
      renderMasterTable();
    } else {
      $("masterCount").textContent = "";
    }
  } catch (err) {
    $("masterCount").textContent = "";
  }
}

function renderMasterTable() {
  $("masterTableBody").innerHTML = masterRows
    .map(
      (r) => `
        <tr>
          <td>${r.empId}</td>
          <td>${r.name}</td>
          <td>${r.dept}</td>
          <td>${r.position}</td>
          <td><button class="btn-icon-remove" data-remove-emp-id="${r.empId}">−</button></td>
        </tr>
      `
    )
    .join("");

  $("masterTableBody").querySelectorAll("[data-remove-emp-id]").forEach((btn) => {
    btn.addEventListener("click", () => removeMasterRow(btn.dataset.removeEmpId));
  });
}

async function removeMasterRow(empId) {
  if (!confirm(`사번 ${empId}을(를) 사번마스터에서 삭제하시겠습니까?`)) return;
  try {
    const res = await callApi("adminMasterDelete", { password: adminPassword, empId });
    if (res.success) {
      showMessage("masterMessage", "삭제되었습니다.", "success");
      await loadMasterList();
    } else {
      showMessage("masterMessage", res.message || "삭제에 실패했습니다.", "error");
    }
  } catch (err) {
    showMessage("masterMessage", "삭제 중 오류: " + err.message, "error");
  }
}

// 사번마스터 1명 추가/수정
$("btnAddMaster").addEventListener("click", async () => {
  const empId = $("inputAddEmpId").value.trim();
  const name = $("inputAddName").value.trim();
  const dept = $("inputAddDept").value.trim();
  const position = $("inputAddPosition").value.trim();

  if (!empId || !name) {
    showMessage("masterMessage", "사번과 성명은 필수입니다.", "error");
    return;
  }

  try {
    const res = await callApi("adminMasterAdd", { password: adminPassword, empId, name, dept, position });
    if (res.success) {
      showMessage("masterMessage", "추가되었습니다.", "success");
      $("inputAddEmpId").value = "";
      $("inputAddName").value = "";
      $("inputAddDept").value = "";
      $("inputAddPosition").value = "";
      await loadMasterList();
    } else {
      showMessage("masterMessage", res.message || "추가에 실패했습니다.", "error");
    }
  } catch (err) {
    showMessage("masterMessage", "추가 중 오류: " + err.message, "error");
  }
});

// CSV 붙여넣기로 사번마스터 일괄 등록/업데이트 (기존 사번은 덮어씀)
$("btnImportMaster").addEventListener("click", async () => {
  const csv = $("inputMasterCsv").value.trim();
  if (!csv) {
    showMessage("masterMessage", "CSV 내용을 입력해주세요.", "error");
    return;
  }
  try {
    const res = await callApi("adminMasterImportCsv", { password: adminPassword, csv });
    if (res.success) {
      showMessage("masterMessage", `${res.count}명 등록/업데이트 완료`, "success");
      $("inputMasterCsv").value = "";
      await loadMasterList();
    } else {
      showMessage("masterMessage", res.message || "등록에 실패했습니다.", "error");
    }
  } catch (err) {
    showMessage("masterMessage", "등록 중 오류: " + err.message, "error");
  }
});

// 사번마스터 전체 삭제 (접수 종료 후 검증 차단 용도)
$("btnDeleteAllMaster").addEventListener("click", async () => {
  if (!confirm("사번마스터 전체를 삭제하시겠습니까? 이후 신청자 검증이 모두 실패 처리됩니다.")) return;
  try {
    const res = await callApi("adminMasterDeleteAll", { password: adminPassword });
    if (res.success) {
      showMessage("masterMessage", "전체 삭제되었습니다.", "success");
      await loadMasterList();
    } else {
      showMessage("masterMessage", res.message || "삭제에 실패했습니다.", "error");
    }
  } catch (err) {
    showMessage("masterMessage", "삭제 중 오류: " + err.message, "error");
  }
});

// 이미 로그인 되어 있으면(같은 탭에서 새로고침) 바로 목록 화면으로
if (adminPassword) {
  $("loginSection").classList.add("hidden");
  $("listSection").classList.remove("hidden");
  loadList();
}
