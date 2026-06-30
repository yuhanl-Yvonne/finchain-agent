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
    row.className = `bar-row ${className}`.trim();
    row.innerHTML = `
      <div class="bar-meta">
        <span>${item.label || item.name}</span>
        <span>${valueKey === "importance" ? formatNumber(item[valueKey], 4) : formatNumber(item[valueKey])}</span>
      </div>
      <div class="bar-track">
        <div class="bar-fill ${item.group || ""}" style="width:${((Number(item[valueKey]) || 0) / max) * 100}%"></div>
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

function normalizeCityName(name) {
  return String(name || "").replace(/市|区|县/g, "").trim();
}

function getGuangdongCityAnchors() {
  return {
    广州: { x: 190, y: 238, labelDx: 0, labelDy: -32, valueDx: 0, valueDy: 22 },
    深圳: { x: 255, y: 326, labelDx: 26, labelDy: 4, valueDx: 0, valueDy: -26 },
    珠海: { x: 198, y: 343, labelDx: -6, labelDy: 24, valueDx: 0, valueDy: -24 },
    佛山: { x: 172, y: 248, labelDx: -32, labelDy: 2, valueDx: 0, valueDy: 24 },
    东莞: { x: 228, y: 296, labelDx: -34, labelDy: 2, valueDx: 0, valueDy: 22 },
    中山: { x: 198, y: 312, labelDx: -24, labelDy: 18, valueDx: 0, valueDy: -24 },
    惠州: { x: 274, y: 264, labelDx: 30, labelDy: -2, valueDx: 0, valueDy: 22 },
    汕头: { x: 358, y: 257, labelDx: 28, labelDy: 2, valueDx: 0, valueDy: 22 },
    汕尾: { x: 326, y: 282, labelDx: 30, labelDy: 0, valueDx: 0, valueDy: 22 },
    揭阳: { x: 345, y: 236, labelDx: 30, labelDy: -2, valueDx: 0, valueDy: 22 },
    潮州: { x: 367, y: 228, labelDx: 30, labelDy: -10, valueDx: 0, valueDy: 22 },
    湛江: { x: 66, y: 344, labelDx: -8, labelDy: 24, valueDx: 0, valueDy: -24 },
    茂名: { x: 95, y: 288, labelDx: -28, labelDy: 0, valueDx: 0, valueDy: 22 },
    阳江: { x: 120, y: 272, labelDx: -30, labelDy: 0, valueDx: 0, valueDy: 22 },
    江门: { x: 142, y: 298, labelDx: -30, labelDy: 12, valueDx: 0, valueDy: -24 },
    肇庆: { x: 122, y: 214, labelDx: -32, labelDy: -4, valueDx: 0, valueDy: 22 },
    清远: { x: 185, y: 167, labelDx: -10, labelDy: -28, valueDx: 0, valueDy: 22 },
    韶关: { x: 206, y: 112, labelDx: 0, labelDy: -30, valueDx: 0, valueDy: 22 },
    河源: { x: 274, y: 162, labelDx: 28, labelDy: -2, valueDx: 0, valueDy: 22 },
    梅州: { x: 332, y: 154, labelDx: 28, labelDy: -6, valueDx: 0, valueDy: 22 },
    云浮: { x: 104, y: 237, labelDx: -26, labelDy: -8, valueDx: 0, valueDy: 22 },
  };
}

function buildGuangdongBaseMap() {
  return `
    <svg viewBox="0 0 430 410" class="gd-map-svg" role="img" aria-label="广东省样本城市分布图">
      <defs>
        <linearGradient id="gd-surface" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stop-color="#f6fbff" />
          <stop offset="100%" stop-color="#dceeff" />
        </linearGradient>
        <linearGradient id="gd-sea" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stop-color="#f7fbff" />
          <stop offset="100%" stop-color="#e0f1ff" />
        </linearGradient>
      </defs>
      <rect x="0" y="0" width="430" height="410" rx="28" fill="url(#gd-sea)" />
      <path
        class="gd-coast-haze"
        d="M292 80
           C334 104 374 140 392 182
           C406 214 404 270 372 322
           L430 322 L430 0 L286 0 Z"
      />
      <path
        class="gd-sea-band"
        d="M302 92
           C338 116 368 150 383 187
           C399 227 394 266 370 305
           C355 330 336 347 318 360
           L430 360 L430 20 L304 20 Z"
      />
      <path
        class="gd-map-outline"
        d="M105 77
           L162 54 L219 60 L278 72 L334 96 L364 132
           L372 177 L387 218 L370 264 L342 305
           L299 342 L244 358 L185 356 L140 338
           L102 354 L72 338 L56 303 L41 263
           L56 217 L70 178 L86 144 L92 110 Z"
      />
      <path
        class="gd-map-inner"
        d="M105 77
           L162 54 L219 60 L278 72 L334 96 L364 132
           L372 177 L387 218 L370 264 L342 305
           L299 342 L244 358 L185 356 L140 338
           L102 354 L72 338 L56 303 L41 263
           L56 217 L70 178 L86 144 L92 110 Z"
        fill="url(#gd-surface)"
      />
      <path
        class="gd-river-line"
        d="M98 228 C130 220 156 226 178 240 C203 255 233 262 271 258 C301 255 328 244 353 230"
      />
      <path
        class="gd-river-line gd-river-line--soft"
        d="M176 122 C196 142 214 162 235 182 C247 193 263 210 280 228"
      />
    </svg>
  `;
}

function renderGuangdongMap(rows) {
  const container = document.getElementById("guangdong-map");
  if (!container) return;

  const safeRows = asArray(rows);
  const anchors = getGuangdongCityAnchors();
  const normalizedRows = safeRows
    .map((item) => {
      const key = normalizeCityName(item.label || item.name);
      return {
        key,
        label: item.label || item.name,
        count: Number(item.count) || 0,
        point: anchors[key],
      };
    })
    .filter((item) => item.point);

  container.innerHTML = buildGuangdongBaseMap();
  if (normalizedRows.length === 0) {
    container.insertAdjacentHTML("beforeend", `<div class="empty-state">暂无城市分布数据</div>`);
    return;
  }

  const max = Math.max(...normalizedRows.map((item) => item.count), 1);
  const overlay = document.createElement("div");
  overlay.className = "gd-bubble-layer";

  normalizedRows.forEach((item) => {
    const bubble = document.createElement("button");
    const size = 18 + (item.count / max) * 34;
    bubble.type = "button";
    bubble.className = "gd-bubble";
    bubble.style.left = `${item.point.x}px`;
    bubble.style.top = `${item.point.y}px`;
    bubble.style.width = `${size}px`;
    bubble.style.height = `${size}px`;
    bubble.innerHTML = `
      <span class="gd-bubble-core"></span>
      <span class="gd-bubble-label" style="--label-dx:${item.point.labelDx || 0}px; --label-dy:${item.point.labelDy || 0}px;">${item.label}</span>
      <span class="gd-bubble-value" style="--value-dx:${item.point.valueDx || 0}px; --value-dy:${item.point.valueDy || 0}px;">${formatNumber(item.count)}</span>
    `;
    bubble.setAttribute("aria-label", `${item.label}，${item.count}家企业`);
    overlay.appendChild(bubble);
  });

  container.appendChild(overlay);
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
    body.innerHTML = `<tr><td colspan="9" class="empty-row">当前筛选条件下暂无企业</td></tr>`;
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
      <td class="cell-bucket">${item.score_bucket || "待更新"}</td>
      <td class="cell-city">${item.city}</td>
      <td class="cell-chain">${item.chain_position}</td>
      <td class="cell-score">${formatScore(item.xgb_fusion_score)}</td>
      <td class="cell-score">${formatScore(item.graphsage_score)}</td>
      <td class="cell-risk">${formatNumber(item.risk_events)}</td>
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
