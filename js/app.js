// 12개사 + 기타 (plan.md 2.4 참고) / 교보생명만 간사기관 뱃지 표시
const COMPANIES = [
  { name: "교보생명", badge: "간사기관" },
  { name: "삼성증권" },
  { name: "국민은행" },
  { name: "삼성화재" },
  { name: "농협은행" },
  { name: "신한은행" },
  { name: "미래에셋" },
  { name: "하나은행" },
  { name: "산업은행" },
  { name: "한국투자증권" },
  { name: "삼성생명" },
  { name: "NH투자증권" },
  { name: "기타" },
];

// 신청자 정보를 담아두는 상태 객체 (단계를 넘어가며 계속 채워짐)
const state = {
  empId: "",
  name: "",
  dept: "",
  position: "",
  company: "",
  companyOther: "",
  verified: false,
};

const $ = (id) => document.getElementById(id);

function showStep(stepNo) {
  ["step1", "step2", "step3", "step4"].forEach((id, idx) => {
    $(id).classList.toggle("hidden", idx + 1 !== stepNo);
  });
  $("stepDone").classList.add("hidden");

  document.querySelectorAll(".steps .step").forEach((el) => {
    const n = Number(el.dataset.step);
    el.classList.toggle("active", n === stepNo);
    el.classList.toggle("done", n < stepNo);
  });
}

function showMessage(containerId, text, type) {
  const el = $(containerId);
  if (!text) {
    el.innerHTML = "";
    return;
  }
  el.innerHTML = `<div class="message ${type}">${text}</div>`;
}

// 접수회차 표시 (설정 시트 값)
async function loadConfig() {
  try {
    const res = await callApi("config", {});
    $("roundDisplay").textContent = "접수회차: " + (res.round || "미설정");
  } catch (err) {
    $("roundDisplay").textContent = "접수회차: 확인 불가";
  }
}

// 1단계: 사번+성명 검증
$("btnVerify").addEventListener("click", async () => {
  const empId = $("inputEmpId").value.trim();
  const name = $("inputName").value.trim();

  $("inputEmpId").classList.remove("invalid");
  $("inputName").classList.remove("invalid");

  if (!empId || !name) {
    if (!empId) $("inputEmpId").classList.add("invalid");
    if (!name) $("inputName").classList.add("invalid");
    showMessage("verifyMessage", "사번과 성명을 모두 입력해주세요.", "error");
    return;
  }

  $("btnVerify").disabled = true;
  $("btnVerify").textContent = "확인 중...";

  try {
    const res = await callApi("verify", { empId, name });

    if (res.success) {
      state.empId = res.employee.empId;
      state.name = res.employee.name;
      state.verified = true;

      $("viewEmpId").value = state.empId;
      $("viewName").value = state.name;

      // 사번마스터에 부서/직급이 미리 있으면 자동 채움 (본인이 다시 수정 가능)
      if (res.employee.dept) $("inputDept").value = res.employee.dept;
      if (res.employee.position) $("inputPosition").value = res.employee.position;

      showMessage("verifyMessage", "", "");
      showStep(2);
    } else {
      // 불일치 시 안내 문구만 보여주고, 바로 다시 입력/재시도할 수 있게 둔다
      showMessage("verifyMessage", res.message, "error");
    }
  } catch (err) {
    showMessage("verifyMessage", "확인 중 오류가 발생했습니다: " + err.message, "error");
  } finally {
    $("btnVerify").disabled = false;
    $("btnVerify").textContent = "확인";
  }
});

// 카드 밖 보조 액션: 신청정보 확인하기 모달 열기 (사번/성명은 모달 안에서 별도로 입력받음)
$("btnMySubmission").addEventListener("click", () => {
  $("modalEmpId").value = "";
  $("modalName").value = "";
  $("modalEmpId").classList.remove("invalid");
  $("modalName").classList.remove("invalid");
  showMessage("mySubmissionModalMessage", "", "");
  $("mySubmissionTable").classList.add("hidden");
  $("mySubmissionModal").classList.remove("hidden");
});

$("btnMySubmissionModalClose").addEventListener("click", () => {
  $("mySubmissionModal").classList.add("hidden");
});

$("btnMySubmissionModalSearch").addEventListener("click", async () => {
  const empId = $("modalEmpId").value.trim();
  const name = $("modalName").value.trim();

  $("modalEmpId").classList.remove("invalid");
  $("modalName").classList.remove("invalid");

  if (!empId || !name) {
    if (!empId) $("modalEmpId").classList.add("invalid");
    if (!name) $("modalName").classList.add("invalid");
    showMessage("mySubmissionModalMessage", "사번과 성명을 모두 입력해주세요.", "error");
    return;
  }

  $("btnMySubmissionModalSearch").disabled = true;
  $("btnMySubmissionModalSearch").textContent = "조회 중...";
  $("mySubmissionTable").classList.add("hidden");

  try {
    const res = await callApi("mySubmission", { empId, name });

    if (!res.success) {
      showMessage("mySubmissionModalMessage", res.message, "error");
    } else if (res.submission) {
      const s = res.submission;
      const dt = s.submittedAt ? new Date(s.submittedAt).toLocaleString("ko-KR") : "";
      $("mySubmissionTable").innerHTML = `
        <tr><th>제출일시</th><td>${dt}</td></tr>
        <tr><th>접수회차</th><td>${s.round || ""}</td></tr>
        <tr><th>부서</th><td>${s.dept}</td></tr>
        <tr><th>직위</th><td>${s.position}</td></tr>
        <tr><th>희망 금융사</th><td>${s.company}</td></tr>
      `;
      showMessage("mySubmissionModalMessage", "", "");
      $("mySubmissionTable").classList.remove("hidden");
    } else {
      showMessage("mySubmissionModalMessage", "아직 제출한 신청 내역이 없어요. 닫기 후 사번확인부터 신규로 입력해주세요.", "info");
    }
  } catch (err) {
    showMessage("mySubmissionModalMessage", "확인 중 오류가 발생했습니다: " + err.message, "error");
  } finally {
    $("btnMySubmissionModalSearch").disabled = false;
    $("btnMySubmissionModalSearch").textContent = "조회";
  }
});

// 2단계: 인적사항 -> 3단계
$("btnStep2Next").addEventListener("click", () => {
  const dept = $("inputDept").value.trim();
  const position = $("inputPosition").value.trim();

  $("inputDept").classList.remove("invalid");
  $("inputPosition").classList.remove("invalid");

  let ok = true;
  if (!dept) { $("inputDept").classList.add("invalid"); ok = false; }
  if (!position) { $("inputPosition").classList.add("invalid"); ok = false; }
  if (!ok) return;

  state.dept = dept;
  state.position = position;
  showStep(3);
});

// 3단계: 금융사 카드 그리드 렌더링 (design.md: 2열 터치형 카드)
function renderCompanyList() {
  const wrap = $("companyList");
  wrap.innerHTML = COMPANIES.map((c) => `
    <label class="company-card" data-company="${c.name}">
      ${c.badge ? `<span class="badge-tag">${c.badge}</span>` : ""}
      <input type="radio" name="company" value="${c.name}" />
      <span>${c.name}</span>
    </label>
  `).join("");

  wrap.querySelectorAll(".company-card").forEach((item) => {
    item.addEventListener("click", () => {
      wrap.querySelectorAll(".company-card").forEach((i) => i.classList.remove("selected"));
      item.classList.add("selected");
      item.querySelector("input").checked = true;

      const company = item.dataset.company;
      $("companyOtherWrap").classList.toggle("hidden", company !== "기타");
    });
  });
}
renderCompanyList();

// 3단계: 다음
$("btnStep3Next").addEventListener("click", () => {
  const selected = document.querySelector('input[name="company"]:checked');
  if (!selected) {
    alert("희망 금융사를 선택해주세요.");
    return;
  }

  const company = selected.value;
  let companyOther = "";

  if (company === "기타") {
    companyOther = $("inputCompanyOther").value.trim();
    $("inputCompanyOther").classList.remove("invalid");
    if (!companyOther) {
      $("inputCompanyOther").classList.add("invalid");
      alert("기타 금융사명을 입력해주세요.");
      return;
    }
  }

  state.company = company;
  state.companyOther = companyOther;

  $("sumEmpId").textContent = state.empId;
  $("sumName").textContent = state.name;
  $("sumDept").textContent = state.dept;
  $("sumPosition").textContent = state.position;
  $("sumCompany").textContent = company === "기타" ? `기타 (${companyOther})` : company;

  showMessage("submitMessage", "", "");
  showStep(4);
});

// 4단계: 이전 버튼들 공통 처리
document.querySelectorAll("[data-back]").forEach((btn) => {
  btn.addEventListener("click", () => {
    showStep(Number(btn.dataset.back));
  });
});

// 4단계: 제출
$("btnSubmit").addEventListener("click", async () => {
  $("btnSubmit").disabled = true;
  $("btnSubmit").textContent = "제출 중...";
  showMessage("submitMessage", "", "");

  try {
    const res = await callApi("submit", {
      empId: state.empId,
      name: state.name,
      dept: state.dept,
      position: state.position,
      company: state.company,
      companyOther: state.companyOther,
    });

    if (res.success) {
      const dt = new Date(res.submittedAt);
      $("doneAt").textContent = "제출 일시 " + dt.toLocaleString("ko-KR");
      showStep(0);
      $("stepDone").classList.remove("hidden");
    } else {
      showMessage("submitMessage", res.message || "제출에 실패했습니다.", "error");
      $("btnSubmit").disabled = false;
      $("btnSubmit").textContent = "제출하기";
    }
  } catch (err) {
    showMessage("submitMessage", "제출 중 오류가 발생했습니다: " + err.message, "error");
    $("btnSubmit").disabled = false;
    $("btnSubmit").textContent = "제출하기";
  }
});

loadConfig();
