const GDELT_ENDPOINT = "https://api.gdeltproject.org/api/v2/doc/doc";

const DEFAULT_TERMS = [
  "banking compliance",
  "anti money laundering",
  "prudential regulation",
  "bank enforcement action",
  "financial crime controls",
  "payment systems regulation",
  "cybersecurity banking",
  "Basel III capital adequacy",
  "DORA digital operational resilience",
  "sanctions screening compliance"
];

const RELEVANCE_TERMS = [
  "compliance",
  "regulation",
  "regulatory",
  "supervision",
  "aml",
  "anti money laundering",
  "kyc",
  "sanctions",
  "prudential",
  "capital",
  "conduct",
  "enforcement",
  "risk",
  "governance",
  "bank",
  "banking",
  "dora",
  "basel"
];

const HIGH_TRUST_TLDS = [".gov", ".gob", ".gc.ca", ".eu", ".int", ".org"];
const REGULATOR_HINTS = [
  "bank",
  "centralbank",
  "fca",
  "finra",
  "sec",
  "prudential",
  "supervision",
  "regulator",
  "authority",
  "fincen",
  "fatf",
  "esma",
  "eba",
  "mas",
  "hkma",
  "osfi",
  "cfpb",
  "fdic",
  "occ",
  "bis",
  "bcbs"
];

const SOURCE_TYPE_RULES = [
  ["Regulator", ["fca", "sec", "finra", "fma", "fsa", "centralbank", "supervision", "authority", "prudential", "fdic", "occ", "mas", "hkma"]],
  ["Legislation", ["parliament", "legislation", "gazette", "congress", "senate", "assembly", "laws", "bill"]],
  ["Enforcement", ["enforcement", "sanction", "penalty", "attorneygeneral", "justice", "cease-desist", "revocation"]],
  ["FIU/AML", ["fiu", "aml", "moneylaundering", "fintrac", "fincen", "fatf"]],
  ["Industry", ["association", "bankingassociation", "trade", "chamber", "federation"]],
  ["Media", ["news", "media", "press", "reuters", "blog"]]
];

const REGULATOR_RSS_FEEDS = [
  "https://www.fca.org.uk/news/rss.xml",
  "https://www.bankofengland.co.uk/rss/publications",
  "https://www.eba.europa.eu/rss/press-releases",
  "https://www.esma.europa.eu/rss/press-news.xml",
  "https://www.fsb.org/feed/",
  "https://www.bis.org/rss/bcbspubl.rss",
  "https://www.federalreserve.gov/feeds/press_all.xml",
  "https://www.occ.gov/rss/rss-news.xml",
  "https://www.fdic.gov/resources/rss.xml",
  "https://www.sec.gov/rss/litigation/litreleases.xml",
  "https://www.fincen.gov/rss.xml",
  "https://www.mas.gov.sg/news/rss",
  "https://www.hkma.gov.hk/eng/rss/_rss_press-releases.xml",
  "https://www.osfi-bsif.gc.ca/en/news-communications/feed"
];

const DEFAULT_COVERED = [
  "fca.org.uk",
  "bankofengland.co.uk",
  "ecb.europa.eu",
  "eba.europa.eu",
  "esma.europa.eu",
  "federalreserve.gov",
  "occ.gov",
  "fdic.gov",
  "sec.gov",
  "fincen.gov"
];

// Hard-rule exclusion list from covered sources provided by your team.
const HARD_RULE_COVERED = [
  "adgm.com",
  "centralbank.ae",
  "sca.gov.ae",
  "uaefiu.gov.ae",
  "legiscan.com",
  "asc.alabama.gov",
  "banking.alabama.gov",
  "alabamaag.gov",
  "law.alaska.gov",
  "commerce.alaska.gov",
  "fiu.gov.al",
  "bankofalbania.org",
  "aksk.gov.al",
  "bcra.gob.ar",
  "argentina.gob.ar",
  "cnv.gov.ar",
  "azcc.gov",
  "difi.az.gov",
  "asic.gov.au",
  "accc.gov.au",
  "apra.gov.au",
  "austrac.gov.au",
  "rba.gov.au",
  "legislation.gov.au",
  "fma.gv.at",
  "oenb.at",
  "beac.int",
  "nbb.be",
  "ccb.belgium.be",
  "fsma.be",
  "sipa.gov.ba",
  "abrs.ba",
  "cbbh.ba",
  "fba.ba",
  "bcb.gov.br",
  "gov.br",
  "bcsc.bc.ca",
  "bcfsa.ca",
  "parliament.bg",
  "bnb.bg",
  "frbsf.org",
  "cppa.ca.gov",
  "dfpi.ca.gov",
  "oag.ca.gov",
  "parl.ca",
  "osfi-bsif.gc.ca",
  "fintrac-canafe.canada.ca",
  "cmfchile.cl",
  "bcentral.cl",
  "csrc.gov.cn",
  "superfinanciera.gov.co",
  "banrep.gov.co",
  "portal.ct.gov",
  "sugef.fi.cr",
  "bccr.fi.cr",
  "hanfa.hr",
  "hnb.hr",
  "cnb.cz",
  "fau.gov.cz",
  "dfsa.ae",
  "cbe.org.eg",
  "fi.ee",
  "efrag.org",
  "eba.europa.eu",
  "eiopa.europa.eu",
  "esma.europa.eu",
  "ecb.europa.eu",
  "bankingsupervision.europa.eu",
  "esrb.europa.eu",
  "finanssivalvonta.fi",
  "acpr.banque-france.fr",
  "amf-france.org",
  "bafin.de",
  "bundesbank.de",
  "fsc.gi",
  "bankofgreece.gr",
  "hcmc.gr",
  "hkma.gov.hk",
  "sfc.hk",
  "mpfa.org.hk",
  "mnb.hu",
  "rbcz",
  "rbi.org.in",
  "sebi.gov.in",
  "bi.go.id",
  "ojk.go.id",
  "centralbank.ie",
  "consob.it",
  "bancaditalia.it",
  "fsa.go.jp",
  "boj.or.jp",
  "centralbank.go.ke",
  "bqk-kos.org",
  "bank.lv",
  "lb.lt",
  "bankal-maghrib.ma",
  "bnm.gov.my",
  "mma.gov.mv",
  "mfsa.mt",
  "fiaumalta.org",
  "banxico.org.mx",
  "cnbv.gob.mx",
  "mld.nv.gov",
  "dfs.ny.gov",
  "rbnz.govt.nz",
  "fma.govt.nz",
  "cbn.gov.ng",
  "finanstilsynet.no",
  "nbs.rs",
  "mas.gov.sg",
  "fsca.co.za",
  "resbank.co.za",
  "fss.or.kr",
  "fsc.go.kr",
  "sepblac.es",
  "cnmv.es",
  "fi.se",
  "finma.ch",
  "fsc.gov.tw",
  "bank.gov.ua",
  "fca.org.uk",
  "bankofengland.co.uk",
  "cftc.gov",
  "consumerfinance.gov",
  "fdic.gov",
  "federalreserve.gov",
  "fincen.gov",
  "finra.org",
  "occ.gov",
  "sec.gov",
  "sama.gov.sa",
  "cma.org.sa",
  "bis.org",
  "fatf-gafi.org",
  "fsb.org"
];

let latestFindings = [];
const hasChromeApi = typeof chrome !== "undefined";

const runNowBtn = document.getElementById("runNowBtn");
const exportBtn = document.getElementById("exportBtn");
const notifyCheck = document.getElementById("notifyCheck");
const statusText = document.getElementById("statusText");
const coveredDomains = document.getElementById("coveredDomains");
const findingsBody = document.getElementById("findingsBody");
const historySelect = document.getElementById("historySelect");
const loadHistoryBtn = document.getElementById("loadHistoryBtn");
const historyInfo = document.getElementById("historyInfo");
const tabFindings = document.getElementById("tabFindings");
const tabCurrentSources = document.getElementById("tabCurrentSources");
const panelFindings = document.getElementById("panelFindings");
const panelCurrentSources = document.getElementById("panelCurrentSources");
const currentSourcesBody = document.getElementById("currentSourcesBody");
const currentSourcesCount = document.getElementById("currentSourcesCount");

init();

async function init() {
  const stored = await storageGet(["notifyOnComplete", "scanHistory"]);
  notifyCheck.checked = stored.notifyOnComplete !== false;

  hydrateHistory(stored.scanHistory || []);

  notifyCheck.addEventListener("change", async () => {
    await storageSet({ notifyOnComplete: notifyCheck.checked });
  });

  runNowBtn.addEventListener("click", runScan);
  exportBtn.addEventListener("click", exportFindingsCsv);
  loadHistoryBtn.addEventListener("click", loadSelectedHistory);
  tabFindings.addEventListener("click", () => activateTab("findings"));
  tabCurrentSources.addEventListener("click", () => activateTab("sources"));

  renderCurrentSources();
}

async function runScan() {
  try {
    runNowBtn.disabled = true;
    exportBtn.disabled = true;
    setStatus("Status: Running scan...");

    const covered = new Set([...DEFAULT_COVERED, ...HARD_RULE_COVERED].map(normalizeDomain).filter(Boolean));
    const allArticles = [];

    setStatus("Status: Fetching regulator feeds...");
    const regulatorArticles = await fetchRegulatorFeeds();
    allArticles.push(...regulatorArticles);

    setStatus("Status: Searching banking terms...");
    const termArticles = await fetchTermArticles();
    allArticles.push(...termArticles);

    setStatus("Status: Building findings...");
    const findings = buildFindings(allArticles, covered);
    latestFindings = findings;
    renderFindings(findings);
    await saveScanHistory(findings);

    exportBtn.disabled = findings.length === 0;
    setStatus(`Status: Scan complete. ${findings.length} new sources found.`);

    if (notifyCheck.checked) {
      notifyComplete(findings.length);
    }
  } catch (error) {
    console.error(error);
    setStatus(`Status: Scan failed (${error.message || "Unknown error"})`);
  } finally {
    runNowBtn.disabled = false;
  }
}

function setStatus(text) {
  statusText.textContent = text;
}

function parseCoveredDomains(raw) {
  const lines = raw
    .split(/\r?\n/)
    .map((s) => normalizeDomain(s.trim()))
    .filter(Boolean);
  return new Set(lines);
}

function normalizeDomain(value) {
  if (!value) return "";
  let v = value.trim().toLowerCase();
  v = v.replace(/^https?:\/\//, "");
  v = v.replace(/^www\./, "");
  v = v.split("/")[0];
  return v;
}

function domainIsKnown(domain, coveredSet) {
  const candidate = normalizeDomain(domain);
  if (!candidate) return false;

  for (const known of coveredSet) {
    if (!known) continue;
    if (candidate === known) return true;
    if (candidate.endsWith(`.${known}`)) return true;
    if (known.endsWith(`.${candidate}`)) return true;
  }
  return false;
}

async function fetchRegulatorFeeds() {
  const items = [];
  for (const feed of REGULATOR_RSS_FEEDS) {
    try {
      const res = await fetch(feed);
      if (!res.ok) continue;
      const xmlText = await res.text();
      const parsed = parseFeedXml(xmlText);
      for (const p of parsed) {
        items.push({
          domain: normalizeDomain(p.url),
          title: p.title || "",
          seenDate: p.date || "",
          url: p.url || "",
          searchTerm: "regulator_feed"
        });
      }
    } catch {
      // Ignore per-feed failures so scan still completes.
    }
  }
  return items;
}

function parseFeedXml(xmlText) {
  const out = [];
  const doc = new DOMParser().parseFromString(xmlText, "text/xml");

  const entries = [...doc.querySelectorAll("entry")];
  if (entries.length > 0) {
    for (const entry of entries) {
      const title = entry.querySelector("title")?.textContent?.trim() || "";
      let link = "";
      const linkNode = entry.querySelector("link[rel='alternate']") || entry.querySelector("link");
      if (linkNode) link = linkNode.getAttribute("href") || "";
      const date = entry.querySelector("published")?.textContent || entry.querySelector("updated")?.textContent || "";
      if (link) out.push({ title, url: link, date });
    }
    return out;
  }

  const rssItems = [...doc.querySelectorAll("channel > item")];
  for (const item of rssItems) {
    const title = item.querySelector("title")?.textContent?.trim() || "";
    const link = item.querySelector("link")?.textContent?.trim() || "";
    const date = item.querySelector("pubDate")?.textContent || "";
    if (link) out.push({ title, url: link, date });
  }
  return out;
}

async function fetchTermArticles() {
  const combined = [];
  for (const term of DEFAULT_TERMS) {
    const [gdelt, gnews] = await Promise.allSettled([
      fetchGdelt(term),
      fetchGoogleNews(term)
    ]);

    if (gdelt.status === "fulfilled") combined.push(...gdelt.value);
    if (gnews.status === "fulfilled") combined.push(...gnews.value);
  }
  return combined;
}

async function fetchGdelt(term) {
  const params = new URLSearchParams({
    query: `"${term}"`,
    mode: "ArtList",
    format: "json",
    // Request the widest provider-supported window; no local cap is applied.
    maxrecords: "250",
    timespan: "7 days",
    sort: "DateDesc"
  });

  const res = await fetch(`${GDELT_ENDPOINT}?${params.toString()}`);
  if (!res.ok) return [];
  const payload = await res.json();
  const articles = payload.articles || [];

  return articles.map((a) => {
    const sourceUrl = a.sourceurl || a.url || "";
    return {
      searchTerm: term,
      title: a.title || "",
      url: sourceUrl,
      domain: normalizeDomain(sourceUrl),
      seenDate: a.seendate || ""
    };
  }).filter((a) => a.domain);
}

async function fetchGoogleNews(term) {
  const params = new URLSearchParams({
    q: `${term} when:7d`,
    hl: "en-GB",
    gl: "GB",
    ceid: "GB:en"
  });

  const res = await fetch(`https://news.google.com/rss/search?${params.toString()}`);
  if (!res.ok) return [];
  const xmlText = await res.text();
  const doc = new DOMParser().parseFromString(xmlText, "text/xml");
  const items = [...doc.querySelectorAll("channel > item")];

  return items.map((item) => {
    const sourceNode = item.querySelector("source");
    const sourceUrl = sourceNode?.getAttribute("url") || item.querySelector("link")?.textContent || "";
    return {
      searchTerm: term,
      title: item.querySelector("title")?.textContent || "",
      url: sourceUrl,
      domain: normalizeDomain(sourceUrl),
      seenDate: item.querySelector("pubDate")?.textContent || ""
    };
  }).filter((a) => a.domain);
}

function relevanceScore(text) {
  const lowered = (text || "").toLowerCase();
  return RELEVANCE_TERMS.reduce((acc, term) => acc + (lowered.includes(term) ? 1 : 0), 0);
}

function tldTrustScore(domain) {
  if (HIGH_TRUST_TLDS.some((tld) => domain.endsWith(tld))) return 2;
  if (domain.endsWith(".com")) return 0;
  return 1;
}

function regulatorHintScore(domain, title) {
  const haystack = `${domain} ${title}`.toLowerCase();
  return REGULATOR_HINTS.some((hint) => haystack.includes(hint)) ? 2 : 0;
}

function classifySourceType(domain, title) {
  const haystack = `${domain} ${title}`.toLowerCase().replace(/\s+/g, "");
  for (const [label, hints] of SOURCE_TYPE_RULES) {
    if (hints.some((h) => haystack.includes(h))) return label;
  }
  return "Other";
}

function relevanceBand(score) {
  if (score >= 4) return "Very Strong";
  if (score >= 3) return "Strong";
  if (score >= 2) return "Moderate";
  return "Early Signal";
}

function priorityScore(maxRelevance, articleCount, trust, regulator) {
  return (maxRelevance * 2.0) + (Math.min(articleCount, 5) * 1.25) + (trust * 1.5) + (regulator * 1.5);
}

function buildFindings(articles, coveredSet) {
  const byUrl = new Map();
  for (const item of articles) {
    if (!item.domain || !item.url) continue;
    if (!byUrl.has(item.url)) byUrl.set(item.url, item);
  }

  const grouped = new Map();
  for (const item of byUrl.values()) {
    const domain = item.domain;
    const row = grouped.get(domain) || {
      domain,
      articleCount: 0,
      maxRelevance: 0,
      latestSeen: "",
      sampleTitle: item.title || "",
      sourceType: "Other"
    };

    row.articleCount += 1;
    const rel = relevanceScore(`${item.title} ${item.searchTerm}`);
    row.maxRelevance = Math.max(row.maxRelevance, rel);

    if (!row.latestSeen || new Date(item.seenDate || 0) > new Date(row.latestSeen || 0)) {
      row.latestSeen = item.seenDate || row.latestSeen;
    }

    if (!row.sampleTitle && item.title) row.sampleTitle = item.title;
    row.sourceType = classifySourceType(domain, row.sampleTitle);

    grouped.set(domain, row);
  }

  const findings = [];
  for (const row of grouped.values()) {
    if (domainIsKnown(row.domain, coveredSet)) continue;

    const trust = tldTrustScore(row.domain);
    const regulator = regulatorHintScore(row.domain, row.sampleTitle);
    const pScore = priorityScore(row.maxRelevance, row.articleCount, trust, regulator);

    findings.push({
      sourceDomain: row.domain,
      sourceType: row.sourceType,
      sourceRelevance: relevanceBand(row.maxRelevance),
      updateCadence: estimateCadence(row.articleCount),
      mentionCount: row.articleCount,
      priorityScore: Number(pScore.toFixed(2))
    });
  }

  findings.sort((a, b) => b.priorityScore - a.priorityScore || b.mentionCount - a.mentionCount);
  return findings;
}

function formatDate(value) {
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "";
  return d.toISOString().slice(0, 10);
}

function renderFindings(findings) {
  findingsBody.innerHTML = "";

  if (!findings.length) {
    findingsBody.innerHTML = `<tr><td colspan="4" class="empty">No new sources found beyond your covered list.</td></tr>`;
    return;
  }

  for (const f of findings) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${escapeHtml(f.sourceDomain)}</td>
      <td>${escapeHtml(f.sourceType)}</td>
      <td>${renderBadge(f.sourceRelevance)}</td>
      <td>${escapeHtml(f.updateCadence)}</td>
    `;
    findingsBody.appendChild(tr);
  }
}

function renderBadge(relevance) {
  const cls = relevance.toLowerCase().replace(/\s+/g, "-");
  return `<span class="badge ${cls}">${escapeHtml(relevance)}</span>`;
}

function escapeHtml(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function exportFindingsCsv() {
  if (!latestFindings.length) return;

  const header = [
    "Source Domain",
    "Source Type",
    "Source Relevance",
    "Banking Update Cadence",
    "Priority Score"
  ];

  const rows = latestFindings.map((f) => [
    f.sourceDomain,
    f.sourceType,
    f.sourceRelevance,
    f.updateCadence,
    String(f.priorityScore)
  ]);

  const csv = [header, ...rows].map((r) => r.map(csvEscape).join(",")).join("\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);

  const a = document.createElement("a");
  a.href = url;
  a.download = `banking_compliance_findings_${new Date().toISOString().replace(/[:.]/g, "-")}.csv`;
  a.click();

  URL.revokeObjectURL(url);
}

function csvEscape(value) {
  const s = String(value ?? "");
  if (/[",\n]/.test(s)) return `"${s.replaceAll('"', '""')}"`;
  return s;
}

function notifyComplete(count) {
  if (!hasChromeApi || !chrome.notifications) {
    return;
  }
  chrome.notifications.create({
    type: "basic",
    iconUrl: "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgYAAAAAMAASsJTYQAAAAASUVORK5CYII=",
    title: "Scan Completed",
    message: `${count} new source${count === 1 ? "" : "s"} found for Banking vertical.`,
    priority: 1
  });
}

function estimateCadence(articleCount) {
  if (articleCount >= 12) return "Very Frequent";
  if (articleCount >= 6) return "Frequent";
  if (articleCount >= 3) return "Regular";
  return "Occasional";
}

async function storageGet(keys) {
  if (hasChromeApi && chrome.storage?.local) {
    return chrome.storage.local.get(keys);
  }

  const out = {};
  for (const key of keys) {
    const raw = localStorage.getItem(`banking-ext-${key}`);
    if (raw !== null) {
      try {
        out[key] = JSON.parse(raw);
      } catch {
        out[key] = raw;
      }
    }
  }
  return out;
}

async function storageSet(payload) {
  if (hasChromeApi && chrome.storage?.local) {
    await chrome.storage.local.set(payload);
    return;
  }

  for (const [key, value] of Object.entries(payload)) {
    localStorage.setItem(`banking-ext-${key}`, JSON.stringify(value));
  }
}

function hydrateHistory(history) {
  historySelect.innerHTML = "";

  if (!history.length) {
    const option = document.createElement("option");
    option.value = "";
    option.textContent = "No previous scans";
    historySelect.appendChild(option);
    historySelect.disabled = true;
    loadHistoryBtn.disabled = true;
    historyInfo.textContent = "No history yet.";
    return;
  }

  historySelect.disabled = false;
  loadHistoryBtn.disabled = false;

  for (const entry of history) {
    const option = document.createElement("option");
    option.value = entry.id;
    option.textContent = `${entry.runAt} - ${entry.count} source${entry.count === 1 ? "" : "s"}`;
    historySelect.appendChild(option);
  }

  const latest = history[0];
  historyInfo.textContent = `Latest saved scan: ${latest.runAt} (${latest.count} sources)`;
}

async function saveScanHistory(findings) {
  const stored = await storageGet(["scanHistory"]);
  const history = stored.scanHistory || [];

  const entry = {
    id: `${Date.now()}`,
    runAt: new Date().toLocaleString(),
    count: findings.length,
    findings
  };

  const updated = [entry, ...history].slice(0, 30);
  await storageSet({ scanHistory: updated });
  hydrateHistory(updated);
}

async function loadSelectedHistory() {
  const selectedId = historySelect.value;
  if (!selectedId) {
    return;
  }

  const stored = await storageGet(["scanHistory"]);
  const history = stored.scanHistory || [];
  const found = history.find((h) => h.id === selectedId);
  if (!found) {
    return;
  }

  latestFindings = found.findings || [];
  renderFindings(latestFindings);
  exportBtn.disabled = latestFindings.length === 0;
  setStatus(`Status: Loaded history from ${found.runAt}.`);
  historyInfo.textContent = `Viewing scan from ${found.runAt} (${found.count} sources).`;
}

function activateTab(tabName) {
  const findingsActive = tabName === "findings";

  tabFindings.classList.toggle("active", findingsActive);
  tabCurrentSources.classList.toggle("active", !findingsActive);
  tabFindings.setAttribute("aria-selected", String(findingsActive));
  tabCurrentSources.setAttribute("aria-selected", String(!findingsActive));

  panelFindings.classList.toggle("active", findingsActive);
  panelCurrentSources.classList.toggle("active", !findingsActive);
}

function renderCurrentSources() {
  const covered = [...new Set([...DEFAULT_COVERED, ...HARD_RULE_COVERED].map(normalizeDomain).filter(Boolean))]
    .sort((a, b) => a.localeCompare(b));

  currentSourcesBody.innerHTML = "";
  currentSourcesCount.textContent = `${covered.length} covered source domains currently excluded from findings.`;

  for (const domain of covered) {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${escapeHtml(domain)}</td>`;
    currentSourcesBody.appendChild(tr);
  }
}
