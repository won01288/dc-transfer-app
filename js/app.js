// 12개사 + 기타 (plan.md 2.4 참고)
const COMPANIES = [
  "교보생명 (간사기관)",
  "삼성증권",
  "국민은행",
  "삼성화재",
  "농협은행",
  "신한은행",
  "미래에셋",
  "하나은행",
  "산업은행",
  "한국투자증권",
  "삼성생명",
  "NH투자증권",
  "기타",
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
  blocked: false,
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
  if (state.blocked) return;

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
      // plan.md 2.2: 불일치 시 이후 입력 차단
      state.blocked = true;
      $("inputEmpId").disabled = true;
      $("inputName").disabled = true;
      $("btnVerify").disabled = true;
      showMessage("verifyMessage", res.message, "error");
    }
  } catch (err) {
    showMessage("verifyMessage", "확인 중 오류가 발생했습니다: " + err.message, "error");
    $("btnVerify").disabled = false;
    $("btnVerify").textContent = "확인";
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

// 3단계: 금융사 라디오 리스트 렌더링
function renderCompanyList() {
  const wrap = $("companyList");
  wrap.innerHTML = COMPANIES.map((c, idx) => `
    <label class="radio-item" data-company="${c}">
      <input type="radio" name="company" value="${c}" />
      <span>${c}</span>
    </label>
  `).join("");

  wrap.querySelectorAll(".radio-item").forEach((item) => {
    item.addEventListener("click", () => {
      wrap.querySelectorAll(".radio-item").forEach((i) => i.classList.remove("selected"));
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
      $("doneAt").textContent = "제출 일시: " + dt.toLocaleString("ko-KR");
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
