const state = {
  currentCompanyId: null,
  summary: null,
  staticCompanies: null,
  staticCompanyDetails: new Map(),
};

const config = {
  mode: window.APP_DATA_MODE || "api",
  apiBase: (window.APP_API_BASE || "").replace(/\/$/, ""),
  staticBase: (window.APP_STATIC_BASE || ".").replace(/\/$/, ""),
};

function asArray(value) {
  return Array.isArray(value) ? value : [];
}

function initGlassSurface() {
  const surfaces = document.querySelectorAll("[data-glass]");
  surfaces.forEach((surface) => {
    surface.classList.remove("glass-surface--svg");
    surface.classList.add("glass-surface--fallback");
  });
}

function splitBlurText(text, mode) {
  if (mode === "letters") {
    return Array.from(text).map((segment) => ({
      text: segment === " " ? "\u00A0" : segment,
      isSpacer: segment === " ",
    }));
  }

  if (mode === "phrases") {
    return text
      .split(/(?<=与)|(?<=的)|(?<=及)|(?<=、)|(?<=网络)|(?<=系统)/)
      .map((segment) => segment.trim())
      .filter(Boolean)
      .map((segment, index, list) => ({
        text: index < list.length - 1 ? `${segment}\u00A0` : segment,
        isSpacer: false,
      }));
  }

  return text.split(" ").map((segment, index, list) => ({
    text: index < list.length - 1 ? `${segment}\u00A0` : segment,
    isSpacer: false,
  }));
}

function initBlurTextHeadings() {
  const targets = document.querySelectorAll("[data-blur-text]");
  targets.forEach((element) => {
    if (element.dataset.blurReady === "true") return;

    const text = (element.textContent || "").trim();
    if (!text) return;

    const animateBy = element.dataset.animateBy || "words";
    const direction = element.dataset.direction || "top";
    const parts = splitBlurText(text, animateBy);
    const fragment = document.createDocumentFragment();

    element.textContent = "";
    element.classList.add("blur-text");
    element.dataset.blurReady = "true";

    parts.forEach((part, index) => {
      const span = document.createElement("span");
      span.className = "blur-text__segment";
      span.textContent = part.text;
      span.style.setProperty("--blur-delay", `${index * (animateBy === "letters" ? 42 : 110)}ms`);
      span.dataset.direction = direction;
      if (part.isSpacer) {
        span.classList.add("blur-text__segment--space");
      }
      fragment.appendChild(span);
    });

    element.appendChild(fragment);
  });

  requestAnimationFrame(() => {
    document.querySelectorAll(".blur-text").forEach((element) => {
      element.classList.add("blur-text--active");
    });
  });
}

async function fetchJSON(url) {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return response.json();
}

function buildApiUrl(path) {
  return `${config.apiBase}${path}`;
}

function buildStaticUrl(path) {
  return `${config.staticBase}${path}`;
}

function formatNumber(value, digits = 0) {
  if (value === null || value === undefined || value === "") return "未披露";
  const number = Number(value);
  if (Number.isNaN(number)) return value;
  return number.toLocaleString("zh-CN", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

function formatScore(value) {
  if (value === null || value === undefined) return "未披露";
  return Number(value).toFixed(6);
}

function renderBarList(containerId, rows, valueKey = "count", className = "") {
  const container = document.getElementById(containerId);
  container.innerHTML = "";
  const safeRows = asArray(rows);
  if (safeRows.length === 0) {
    container.innerHTML = `<div class="empty-state">暂无可展示数据</div>`;
    return;
  }
  const max = Math.max(...safeRows.map((item) => Number(item[valueKey]) || 0), 1);
  safeRows.forEach((item) => {
    const row = document.createElement("div");
    const featureGroup =
      item.group || (String(item.label || item.name || "").includes("图谱表征") ? "graph" : "structured");
    row.className = `bar-row ${className} feature-card feature-card--${featureGroup}`.trim();
    row.innerHTML = `
      <div class="bar-meta">
        <span>${item.label || item.name}</span>
        <span>${valueKey === "importance" ? formatNumber(item[valueKey], 4) : formatNumber(item[valueKey])}</span>
      </div>
      <div class="bar-track">
        <div class="bar-fill ${featureGroup}" style="width:${((Number(item[valueKey]) || 0) / max) * 100}%"></div>
      </div>
    `;
    container.appendChild(row);
  });
}

function renderSummaryCards(cards) {
  const container = document.getElementById("summary-cards");
  container.innerHTML = "";
  asArray(cards).forEach((card) => {
    const node = document.createElement("div");
    node.className = "summary-card";
    node.innerHTML = `
      <div class="label">${card.label}</div>
      <div class="value">${card.value}</div>
      <div class="hint">${card.hint}</div>
    `;
    container.appendChild(node);
  });
}

function renderMetricPanels(metrics) {
  const container = document.getElementById("metric-panels");
  container.innerHTML = "";
  const graphsage = metrics?.graphsage || {};
  const fusion = metrics?.fusion || {};
  const items = [
    {
      title: "GraphSAGE 图谱表征",
      value: `F1 ${formatNumber(graphsage.test_f1, 4)}`,
      hint: `AUC ${formatNumber(graphsage.test_auc, 4)} / 节点 ${formatNumber(graphsage.nodes)}`,
    },
    {
      title: "XGBoost 融合模型",
      value: `F1 ${formatNumber(fusion.test_f1, 4)}`,
      hint: `AUC ${formatNumber(fusion.test_auc, 4)} / 训练样本 ${formatNumber(fusion.train_size)}`,
    },
  ];
  items.forEach((item) => {
    const node = document.createElement("div");
    node.className = "metric-card";
    node.innerHTML = `
      <div class="title">${item.title}</div>
      <div class="value">${item.value}</div>
      <div class="hint">${item.hint}</div>
    `;
    container.appendChild(node);
  });
}

function renderLevelLegendCard() {
  const container = document.getElementById("level-legend-card");
  if (!container) return;
  const items = [
    ["A", "优先推荐"],
    ["B", "重点跟进"],
    ["C", "审慎评估"],
    ["D", "持续观察"],
  ];
  container.innerHTML = `
    <div class="level-legend-title">档位说明</div>
    <div class="level-legend-list">
      ${items
        .map(
          ([level, text]) => `
            <div class="level-legend-item">
              <span class="level-legend-badge level-${level.toLowerCase()}">${level}</span>
              <span class="level-legend-text">${text}</span>
            </div>
          `
        )
        .join("")}
    </div>
  `;
}

function buildGuangdongBaseMap() {
  return `
    <div class="gd-map-image-mask">
      <img
        class="gd-map-image"
        src="/Users/lyh/Desktop/5.15产学研文献/d38d2edb-d45c-46b0-b40b-7fc660a5cafc.png"
        alt="广东省样本企业空间分布图"
      />
    </div>
  `;
}

function renderGuangdongMap(rows) {
  const container = document.getElementById("guangdong-map");
  if (!container) return;

  container.innerHTML = buildGuangdongBaseMap();
}

function populateFilters(filterOptions) {
  const map = [
    ["level-select", filterOptions?.levels],
    ["city-select", filterOptions?.cities],
    ["chain-select", filterOptions?.chains],
  ];
  map.forEach(([id, values]) => {
    const select = document.getElementById(id);
    while (select.options.length > 1) {
      select.remove(1);
    }
    asArray(values).forEach((value) => {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = value;
      select.appendChild(option);
    });
  });
}

function renderCompanyTable(payload) {
  const body = document.getElementById("company-table-body");
  body.innerHTML = "";
  const items = asArray(payload?.items);
  document.getElementById("table-count").textContent = `${payload?.total ?? items.length} 家样本企业`;
  if (items.length === 0) {
    body.innerHTML = `<tr><td colspan="7" class="empty-row">当前筛选条件下暂无企业</td></tr>`;
    return;
  }
  items.forEach((item, index) => {
    const row = document.createElement("tr");
    row.dataset.companyId = item.company_id;
    if (!state.currentCompanyId && index === 0) {
      state.currentCompanyId = item.company_id;
    }
    if (item.company_id === state.currentCompanyId) {
      row.classList.add("active");
    }
    row.innerHTML = `
      <td class="cell-rank">${item.display_rank_label}</td>
      <td class="cell-company" title="${item.company_name}">${item.company_name}</td>
      <td class="cell-level level-${String(item.demo_white_list_level || item.white_list_level || "").toLowerCase()}">${item.demo_white_list_level || item.white_list_level || "未分层"}</td>
      <td class="cell-city">${item.city}</td>
      <td class="cell-chain">${item.chain_position}</td>
      <td class="cell-score">${formatScore(item.xgb_fusion_score)}</td>
      <td class="cell-score">${formatScore(item.graphsage_score)}</td>
    `;
    row.addEventListener("click", async () => {
      state.currentCompanyId = item.company_id;
      document.querySelectorAll("#company-table-body tr").forEach((tr) => tr.classList.remove("active"));
      row.classList.add("active");
      await loadCompanyDetail(item.company_id);
    });
    body.appendChild(row);
  });
}

function buildInfoGrid(items) {
  return items
    .map(
      ([key, value]) => `
        <div class="info-item">
          <span class="key">${key}</span>
          <span class="val" title="${value || "未披露"}">${value || "未披露"}</span>
        </div>
      `
    )
    .join("");
}

function renderCompanyDetail(payload) {
  const container = document.getElementById("company-detail");
  const template = document.getElementById("detail-template");
  const node = template.content.firstElementChild.cloneNode(true);

  node.querySelector(".detail-eyebrow").textContent = `${payload.basic_info.city} · ${payload.basic_info.chain_position}`;
  node.querySelector(".detail-title").textContent = payload.basic_info.company_name;
  node.querySelector(".detail-subtitle").textContent = `${payload.basic_info.company_id} · 原模型等级 ${payload.model_info.original_white_list_level}`;
  node.querySelector(".level-badge").textContent = payload.model_info.demo_white_list_level;

  const metricList = [
    ["分层等级", payload.model_info.demo_white_list_level],
    ["融合分数", formatScore(payload.model_info.xgb_fusion_score)],
    ["GraphSAGE", formatScore(payload.model_info.graphsage_score)],
    ["排序位次", payload.model_info.display_rank_label],
  ];
  node.querySelector(".detail-metrics").innerHTML = metricList
    .map(
      ([label, value]) => `
        <div class="metric-pill">
          <div class="label">${label}</div>
          <div class="value">${value}</div>
        </div>
      `
    )
    .join("");

  node.querySelector(".detail-report").textContent = payload.generated_report;
  node.querySelector(".detail-positive").textContent = payload.model_info.top_positive;
  node.querySelector(".detail-negative").textContent = payload.model_info.top_negative;

  const graphItems = [
    ["产业链连接数", payload.graph_snapshot.chain_degree],
    ["区域连接数", payload.graph_snapshot.region_degree],
    ["风险事件数", payload.graph_snapshot.risk_event_count],
    ["专利连接数", payload.graph_snapshot.patent_degree],
  ];
  node.querySelector(".graph-grid").innerHTML = buildInfoGrid(graphItems);

  const infoItems = [
    ["城市 / 区县", `${payload.basic_info.city} / ${payload.basic_info.district}`],
    ["企业规模", payload.basic_info.company_size],
    ["企业类型", payload.basic_info.company_type],
    ["注册资本", payload.basic_info.registered_capital],
    ["参保人数", formatNumber(payload.basic_info.insured_count)],
    ["登记状态", payload.basic_info.status],
    ["法定代表人", payload.basic_info.legal_representative],
    ["产业链判定依据", payload.basic_info.chain_basis],
  ];
  node.querySelector(".info-grid").innerHTML = buildInfoGrid(infoItems);
  node.querySelector(".detail-scope").textContent = payload.scope;

  container.innerHTML = "";
  container.appendChild(node);
  initBlurTextHeadings();
}

function getActiveFilters() {
  return {
    search: document.getElementById("search-input").value.trim(),
    level: document.getElementById("level-select").value,
    city: document.getElementById("city-select").value,
    chain: document.getElementById("chain-select").value,
  };
}

function filterStaticCompanies(items, filters) {
  const search = (filters.search || "").toLowerCase();
  return asArray(items).filter((company) => {
    const matchesSearch =
      !search ||
      String(company.company_name || "").toLowerCase().includes(search) ||
      String(company.company_id || "").toLowerCase().includes(search);
    const matchesLevel = !filters.level || company.demo_white_list_level === filters.level;
    const matchesCity = !filters.city || company.city === filters.city;
    const matchesChain = !filters.chain || company.chain_position === filters.chain;
    return matchesSearch && matchesLevel && matchesCity && matchesChain;
  });
}

async function getSummary() {
  if (config.mode === "static") {
    if (!state.summary) {
      state.summary = await fetchJSON(buildStaticUrl("/data/summary.json"));
    }
    return state.summary;
  }
  return fetchJSON(buildApiUrl("/api/summary"));
}

async function getCompanies(filters) {
  if (config.mode === "static") {
    if (!state.staticCompanies) {
      state.staticCompanies = await fetchJSON(buildStaticUrl("/data/companies.json"));
    }
    const items = filterStaticCompanies(state.staticCompanies.items, filters);
    return {
      total: items.length,
      items,
    };
  }

  const params = new URLSearchParams(filters);
  return fetchJSON(buildApiUrl(`/api/companies?${params.toString()}`));
}

async function getCompanyDetail(companyId) {
  if (config.mode === "static") {
    if (!state.staticCompanyDetails.has(companyId)) {
      const payload = await fetchJSON(buildStaticUrl(`/data/company/${encodeURIComponent(companyId)}.json`));
      state.staticCompanyDetails.set(companyId, payload);
    }
    return state.staticCompanyDetails.get(companyId);
  }
  return fetchJSON(buildApiUrl(`/api/company/${encodeURIComponent(companyId)}`));
}

async function loadCompanyDetail(companyId) {
  const payload = await getCompanyDetail(companyId);
  renderCompanyDetail(payload);
}

async function loadCompanies() {
  const filters = getActiveFilters();
  const payload = await getCompanies(filters);
  const items = asArray(payload?.items);
  if (!items.some((item) => item.company_id === state.currentCompanyId)) {
    state.currentCompanyId = items[0]?.company_id || null;
  }
  renderCompanyTable(payload);
  if (state.currentCompanyId) {
    await loadCompanyDetail(state.currentCompanyId);
  }
}

async function init() {
  initGlassSurface();
  initBlurTextHeadings();
  renderLevelLegendCard();
  const summary = await getSummary();
  document.getElementById("sample-size-chip").textContent = summary.sample_size ?? "39";
  renderSummaryCards(summary.summary_cards);
  renderMetricPanels(summary.model_metrics || {});
  renderBarList("feature-importance", summary.top_features || [], "importance");
  renderGuangdongMap(summary.city_distribution || []);
  populateFilters(summary.filter_options || {});
  await loadCompanies();
}

document.getElementById("filter-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  await loadCompanies();
});

init().catch((error) => {
  const container = document.getElementById("company-detail");
  container.textContent = `加载失败：${error.message}`;
});
