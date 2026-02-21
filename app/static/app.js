const form = document.getElementById("plan-form");
const resultEl = document.getElementById("result");
const statusEl = document.getElementById("status");

const setStatus = (text, cls) => {
  statusEl.textContent = text;
  statusEl.className = `status ${cls || ""}`.trim();
};

const renderList = (items, emptyText) => {
  if (!items || items.length === 0) {
    return `<p class="muted">${emptyText}</p>`;
  }
  const li = items
    .map((item) => `<li>${typeof item === "string" ? item : JSON.stringify(item)}</li>`)
    .join("");
  return `<ul>${li}</ul>`;
};

const renderPlan = (data) => {
  const plan = data.plan || {};
  const days = plan.days || [];
  const attractions = plan.attractions || [];
  const hotels = plan.hotels || [];

  const dayBlocks = days
    .map((day) => {
      const schedule = renderList(day.schedule, "暂无安排");
      return `
        <div class="day">
          <h5>第 ${day.day_index} 天 · ${day.title || "行程"}</h5>
          ${schedule}
        </div>
      `;
    })
    .join("");

  return `
    <div class="section">
      <h4>总览</h4>
      <p>${plan.overview || "暂无总览"}</p>
    </div>
    <div class="section">
      <h4>每日安排</h4>
      ${dayBlocks || "<p>暂无日程</p>"}
    </div>
    <div class="section">
      <h4>景点推荐</h4>
      ${renderList(attractions.map((p) => p.name || p.address || JSON.stringify(p)), "暂无景点")}
    </div>
    <div class="section">
      <h4>酒店推荐</h4>
      ${renderList(hotels.map((p) => p.name || p.address || JSON.stringify(p)), "暂无酒店")}
    </div>
  `;
};

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  setStatus("生成中...", "busy");
  resultEl.classList.remove("empty");
  resultEl.innerHTML = "<p>正在请求，请稍等...</p>";

  const formData = new FormData(form);
  const payload = {
    origin_city: formData.get("origin_city"),
    destination_city: formData.get("destination_city"),
    start_date: formData.get("start_date"),
    days: Number(formData.get("days")),
    travelers: Number(formData.get("travelers")),
    budget_level: formData.get("budget_level"),
    hotel_level: formData.get("hotel_level"),
    preferences: String(formData.get("preferences") || "")
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean),
    pace: formData.get("pace"),
  };

  try {
    const res = await fetch("/plan", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      const text = await res.text();
      throw new Error(text || `HTTP ${res.status}`);
    }

    const data = await res.json();
    resultEl.innerHTML = renderPlan(data);
    setStatus("完成", "ok");
  } catch (err) {
    resultEl.innerHTML = `<p>请求失败：${err.message}</p>`;
    setStatus("失败", "error");
  }
});
