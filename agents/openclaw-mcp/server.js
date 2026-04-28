// MCP HTTP server (Streamable HTTP transport) cho OpenClaw
// Tool: crawl_and_save
// - Nhận keyword (search Douyin) hoặc URLs → crawl metadata → append vào Google Sheet.

import express from "express";
import { randomUUID } from "node:crypto";
import { readFileSync, existsSync } from "node:fs";
import { google } from "googleapis";
import { z } from "zod";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js";

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------

const PORT = parseInt(process.env.PORT || "7799", 10);
const SPREADSHEET_ID = process.env.SPREADSHEET_ID || "";
const SHEET_NAME = process.env.SHEET_NAME || "Crawled";
const DEFAULT_TOPIC = process.env.DEFAULT_TOPIC || "";
const DEDUPLICATE = (process.env.DEDUPLICATE || "true").toLowerCase() !== "false";
const SA_FILE = process.env.GOOGLE_SERVICE_ACCOUNT_JSON_FILE || "";
const SA_INLINE = process.env.GOOGLE_SERVICE_ACCOUNT_JSON || "";
const DOUYIN_COOKIES_FILE = process.env.DOUYIN_COOKIES_FILE || "";

const SHEET_HEADERS = [
  "Created At", "Platform", "URL", "Video ID",
  "Title", "Author", "Topic", "Type", "Description", "Note",
  "Status", "AI_Score",
];

const MOBILE_UA =
  "Mozilla/5.0 (iPhone; CPU iPhone OS 16_5 like Mac OS X) " +
  "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Mobile/15E148 Safari/604.1";

const DESKTOP_UA =
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 " +
  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36";

// ---------------------------------------------------------------------------
// Douyin cookies (lazy load)
// ---------------------------------------------------------------------------

let _douyinCookieStr = null;
function getDouyinCookieStr() {
  if (_douyinCookieStr !== null) return _douyinCookieStr;
  if (!DOUYIN_COOKIES_FILE || !existsSync(DOUYIN_COOKIES_FILE)) {
    _douyinCookieStr = "";
    return _douyinCookieStr;
  }
  try {
    const raw = JSON.parse(readFileSync(DOUYIN_COOKIES_FILE, "utf-8"));
    _douyinCookieStr = raw
      .filter(c => c.name && c.value)
      .map(c => `${c.name}=${c.value}`)
      .join("; ");
    console.log(`[crawler-mcp] loaded ${raw.length} Douyin cookies`);
  } catch (e) {
    console.error("[crawler-mcp] failed to load Douyin cookies:", e.message);
    _douyinCookieStr = "";
  }
  return _douyinCookieStr;
}

// ---------------------------------------------------------------------------
// Douyin search by keyword (uses cookies)
// ---------------------------------------------------------------------------

async function searchDouyin(keyword, count = 10) {
  const cookies = getDouyinCookieStr();
  if (!cookies) return { ok: false, error: "Douyin cookies chưa cấu hình (DOUYIN_COOKIES_FILE)" };

  const params = new URLSearchParams({
    keyword,
    search_channel: "aweme_video_web",
    sort_type: 0,
    publish_time: 0,
    filter_duration: 0,
    count: String(count),
    offset: "0",
    need_filter_settings: "0",
    list_type: "single",
    device_platform: "webapp",
    aid: "6383",
    version_name: "23.5.0",
  });

  const url = `https://www.douyin.com/aweme/v1/web/search/item/?${params}`;
  try {
    const r = await fetch(url, {
      headers: {
        "User-Agent": DESKTOP_UA,
        "Referer": `https://www.douyin.com/search/${encodeURIComponent(keyword)}`,
        "Cookie": cookies,
        "Accept": "application/json, text/plain, */*",
      },
    });
    if (!r.ok) return { ok: false, error: `HTTP ${r.status}` };
    const data = await r.json();
    if (data.status_code !== 0) {
      return { ok: false, error: `API status ${data.status_code}: ${data.status_msg || "unknown"}` };
    }
    const items = data.data || [];
    const results = items.map(item => {
      const aweme = item.aweme_info || item;
      const vid = aweme.aweme_id || "";
      const desc = aweme.desc || "";
      const author = (aweme.author || {}).nickname || "";
      const videoUrl = `https://www.douyin.com/video/${vid}`;
      return {
        ok: true,
        platform: "douyin",
        video_id: vid,
        title: desc.slice(0, 200),
        author,
        type: "video",
        description: desc,
        url: videoUrl,
      };
    }).filter(r => r.video_id);
    return { ok: true, results };
  } catch (e) {
    return { ok: false, error: `search error: ${e.message}` };
  }
}

// ---------------------------------------------------------------------------
// Google Sheets client (lazy init)
// ---------------------------------------------------------------------------

let sheetsClient = null;
async function getSheets() {
  if (sheetsClient) return sheetsClient;
  if (!SPREADSHEET_ID) throw new Error("SPREADSHEET_ID chưa cấu hình");

  let creds;
  if (SA_INLINE) {
    creds = JSON.parse(SA_INLINE);
  } else if (SA_FILE) {
    creds = JSON.parse(readFileSync(SA_FILE, "utf-8"));
  } else {
    throw new Error("Chưa cấu hình GOOGLE_SERVICE_ACCOUNT_JSON_FILE hoặc GOOGLE_SERVICE_ACCOUNT_JSON");
  }

  const auth = new google.auth.GoogleAuth({
    credentials: creds,
    scopes: ["https://www.googleapis.com/auth/spreadsheets"],
  });
  sheetsClient = google.sheets({ version: "v4", auth });
  return sheetsClient;
}

async function ensureSheetWithHeader() {
  const sheets = await getSheets();
  const meta = await sheets.spreadsheets.get({ spreadsheetId: SPREADSHEET_ID });
  const titles = (meta.data.sheets || []).map(s => s.properties.title);
  if (!titles.includes(SHEET_NAME)) {
    await sheets.spreadsheets.batchUpdate({
      spreadsheetId: SPREADSHEET_ID,
      requestBody: {
        requests: [{ addSheet: { properties: { title: SHEET_NAME } } }],
      },
    });
  }
  const lastCol = String.fromCharCode("A".charCodeAt(0) + SHEET_HEADERS.length - 1);
  const rng = `${SHEET_NAME}!A1:${lastCol}1`;
  const r = await sheets.spreadsheets.values.get({
    spreadsheetId: SPREADSHEET_ID, range: rng,
  });
  if (!r.data.values || r.data.values.length === 0) {
    await sheets.spreadsheets.values.update({
      spreadsheetId: SPREADSHEET_ID, range: rng,
      valueInputOption: "RAW",
      requestBody: { values: [SHEET_HEADERS] },
    });
  }
}

async function appendRow(row) {
  const sheets = await getSheets();
  await sheets.spreadsheets.values.append({
    spreadsheetId: SPREADSHEET_ID,
    range: `${SHEET_NAME}!A1`,
    valueInputOption: "RAW",
    insertDataOption: "INSERT_ROWS",
    requestBody: { values: [row] },
  });
}

async function existingUrls() {
  const sheets = await getSheets();
  try {
    const r = await sheets.spreadsheets.values.get({
      spreadsheetId: SPREADSHEET_ID, range: `${SHEET_NAME}!C2:C`,
    });
    return new Set((r.data.values || []).map(row => row[0]).filter(Boolean));
  } catch {
    return new Set();
  }
}

// ---------------------------------------------------------------------------
// Crawl helpers
// ---------------------------------------------------------------------------

function detectPlatform(url) {
  let host = "";
  try { host = new URL(url).host.toLowerCase(); } catch { return "unknown"; }
  if (host.includes("xiaohongshu") || host.includes("xhslink")) return "xiaohongshu";
  if (host.includes("douyin") || host.includes("iesdouyin")) return "douyin";
  return "unknown";
}

async function resolveRedirect(url) {
  try {
    const r = await fetch(url, {
      method: "HEAD", redirect: "follow",
      headers: { "User-Agent": MOBILE_UA },
    });
    return r.url || url;
  } catch {
    return url;
  }
}

// ----- Xiaohongshu -----

const XHS_NOTE_ID_RE = /\/(?:explore|discovery\/item)\/([a-zA-Z0-9]+)/;
const XHS_INITIAL_STATE_RE = /window\.__INITIAL_STATE__\s*=\s*(\{[\s\S]*?\})<\/script>/;

function xhsExtractNoteId(url) {
  const m = url.match(XHS_NOTE_ID_RE);
  return m ? m[1] : "";
}

function xhsParseState(html) {
  const m = html.match(XHS_INITIAL_STATE_RE);
  if (!m) return null;
  const raw = m[1].replace(/undefined/g, "null");
  try { return JSON.parse(raw); } catch { return null; }
}

function xhsWalkNote(state) {
  function walk(obj) {
    if (Array.isArray(obj)) {
      for (const it of obj) {
        const r = walk(it);
        if (r) return r;
      }
      return null;
    }
    if (obj && typeof obj === "object") {
      const t = obj.type;
      if ((t === "normal" || t === "video") &&
          (obj.video || obj.imageList || obj.images)) {
        return obj;
      }
      for (const v of Object.values(obj)) {
        const r = walk(v);
        if (r) return r;
      }
    }
    return null;
  }
  return walk(state);
}

async function crawlXhs(url) {
  const fullUrl = url.includes("xhslink") ? await resolveRedirect(url) : url;
  const noteId = xhsExtractNoteId(fullUrl);

  let res;
  try {
    res = await fetch(fullUrl, {
      headers: {
        "User-Agent": MOBILE_UA,
        "Referer": "https://www.xiaohongshu.com/",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
      },
      redirect: "follow",
    });
  } catch (e) {
    return { ok: false, error: `http error: ${e.message}` };
  }
  if (!res.ok) return { ok: false, error: `HTTP ${res.status}` };

  const html = await res.text();
  const state = xhsParseState(html);
  if (!state) return { ok: false, error: "no __INITIAL_STATE__ (anti-bot?)" };

  const note = xhsWalkNote(state);
  if (!note) return { ok: false, error: "no note object found" };

  const desc = note.desc || "";
  const title = note.title || (desc ? desc.slice(0, 80) : "");
  const type = note.video ? "video"
    : (note.imageList || note.images) ? "image"
    : "unknown";
  const user = note.user || {};
  const author = user.nickname || user.nickName || user.name || "";

  return {
    ok: true,
    platform: "xiaohongshu",
    video_id: noteId || note.noteId || note.id || "",
    title,
    author,
    type,
    description: desc,
    url: fullUrl,
  };
}

// ----- Douyin -----

const DY_VIDEO_ID_RE = /\/(?:video|note)\/(\d+)/;
function dyExtractVideoId(url) {
  const m = url.match(DY_VIDEO_ID_RE);
  return m ? m[1] : "";
}

async function crawlDouyin(url) {
  if (url.includes("v.douyin.com")) {
    url = await resolveRedirect(url);
  }
  const videoId = dyExtractVideoId(url);

  if (videoId) {
    const api = `https://www.iesdouyin.com/web/api/v2/aweme/iteminfo/?item_ids=${videoId}`;
    try {
      const r = await fetch(api, {
        headers: { "User-Agent": MOBILE_UA, "Referer": "https://www.douyin.com/" },
      });
      if (r.ok) {
        const data = await r.json();
        const it = (data.item_list || [])[0];
        if (it) {
          const author = (it.author || {}).nickname || "";
          return {
            ok: true,
            platform: "douyin",
            video_id: videoId,
            title: (it.desc || "").slice(0, 200),
            author,
            type: "video",
            description: it.desc || "",
            url,
          };
        }
      }
    } catch { /* fall through */ }
  }

  // Fallback: parse og:title trên trang share
  try {
    const shareUrl = videoId
      ? `https://www.iesdouyin.com/share/video/${videoId}/`
      : url;
    const r = await fetch(shareUrl, {
      headers: { "User-Agent": MOBILE_UA, "Referer": "https://www.douyin.com/" },
    });
    if (!r.ok) return { ok: false, error: `HTTP ${r.status}` };
    const html = await r.text();
    const titleM = html.match(/<meta\s+property="og:title"\s+content="([^"]+)"/);
    const descM = html.match(/<meta\s+property="og:description"\s+content="([^"]+)"/);
    const title = titleM ? titleM[1] : "";
    const desc = descM ? descM[1] : "";
    return {
      ok: true,
      platform: "douyin",
      video_id: videoId,
      title: title || desc.slice(0, 80),
      author: "",
      type: "video",
      description: desc,
      url,
    };
  } catch (e) {
    return { ok: false, error: `http error: ${e.message}` };
  }
}

async function crawlOne(url) {
  const platform = detectPlatform(url);
  if (platform === "xiaohongshu") return crawlXhs(url);
  if (platform === "douyin") return crawlDouyin(url);
  return { ok: false, error: `platform không hỗ trợ: ${url}` };
}

function nowStr() {
  const d = new Date();
  const pad = n => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ` +
         `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

// ---------------------------------------------------------------------------
// MCP server
// ---------------------------------------------------------------------------

function buildMcpServer() {
  const server = new McpServer({
    name: "contenfactory-crawler",
    version: "0.1.0",
  });

  server.tool(
    "crawl_and_save",
    "Search Douyin theo keyword HOẶC nhận URLs Douyin/Xiaohongshu → crawl metadata → ghi vào Google Sheet. " +
    "Dùng keyword để tìm video trên Douyin; dùng urls để crawl link có sẵn.",
    {
      keyword: z.string().optional().describe("Từ khóa search trên Douyin (vd: 'review phim ngôn tình'). Nếu có keyword thì không cần urls."),
      count: z.number().optional().describe("Số video muốn lấy khi search keyword (mặc định 10, tối đa 20)"),
      urls: z.array(z.string()).optional().describe("Danh sách URL Douyin/Xiaohongshu có sẵn. Nếu có urls thì không cần keyword."),
      topic: z.string().optional().describe("Chủ đề / category (vd: review_phim)"),
      note: z.string().optional().describe("Ghi chú thêm (optional, áp dụng cho tất cả)"),
    },
    async ({ keyword, count, urls, topic, note }) => {
      // --- Resolve URLs: from keyword search or direct input ---
      let resolvedUrls = [];
      let searchMetas = null;

      if (keyword && keyword.trim()) {
        const max = Math.min(count || 10, 20);
        const sr = await searchDouyin(keyword.trim(), max);
        if (!sr.ok) {
          return { content: [{ type: "text", text: `ERROR search: ${sr.error}` }] };
        }
        searchMetas = sr.results;
        resolvedUrls = sr.results.map(r => r.url);
      } else if (Array.isArray(urls) && urls.length > 0) {
        resolvedUrls = urls;
      } else {
        return { content: [{ type: "text", text: "ERROR: cần keyword hoặc urls" }] };
      }
      const t = topic || DEFAULT_TOPIC;
      const n = note || "";
      try {
        await ensureSheetWithHeader();
      } catch (e) {
        return { content: [{ type: "text", text: `ERROR Sheets: ${e.message}` }] };
      }
      const existing = DEDUPLICATE ? await existingUrls() : new Set();
      const ok = [], skip = [], fail = [];

      for (let i = 0; i < resolvedUrls.length; i++) {
        const url = (resolvedUrls[i] || "").trim();
        if (!url.startsWith("http")) { fail.push(`${url} (URL invalid)`); continue; }
        if (existing.has(url)) { skip.push(url); continue; }

        // If we got metadata from search, use it directly; otherwise crawl
        const meta = (searchMetas && searchMetas[i]) ? searchMetas[i] : await crawlOne(url);
        if (!meta.ok) { fail.push(`${url} (${meta.error})`); continue; }

        const row = [
          nowStr(), meta.platform, meta.url, meta.video_id,
          meta.title, meta.author, t, meta.type,
          (meta.description || "").slice(0, 1000), n,
          "new", "",
        ];
        try {
          await appendRow(row);
          existing.add(url);
          ok.push(`[${meta.platform}] ${meta.video_id} - ${(meta.title || "").slice(0, 60)}`);
        } catch (e) {
          fail.push(`${url} (append: ${e.message})`);
        }
        if (resolvedUrls.length > 1) await new Promise(r => setTimeout(r, 400));
      }

      const lines = [
        `DONE: OK=${ok.length} | SKIP=${skip.length} | FAIL=${fail.length}`,
      ];
      if (ok.length) lines.push("", "OK:", ...ok.map(x => `  - ${x}`));
      if (skip.length) lines.push("", "SKIP:", ...skip.map(x => `  - ${x}`));
      if (fail.length) lines.push("", "FAIL:", ...fail.map(x => `  - ${x}`));
      return { content: [{ type: "text", text: lines.join("\n") }] };
    },
  );

  server.tool(
    "sheet_manage",
    "Đọc hoặc cập nhật dữ liệu trên Google Sheet. " +
    "action=read: lấy danh sách video (lọc theo status, platform, topic). " +
    "action=update: cập nhật cột cho 1 hoặc nhiều dòng theo row number.",
    {
      action: z.enum(["read", "update"]).describe("read = đọc dữ liệu, update = cập nhật dòng"),
      status: z.string().optional().describe("[read] Lọc theo status (vd: 'new', 'approved', 'downloaded')"),
      platform: z.string().optional().describe("[read] Lọc theo platform (vd: 'douyin', 'xiaohongshu')"),
      topic: z.string().optional().describe("[read] Lọc theo topic"),
      limit: z.number().optional().describe("[read] Số dòng tối đa trả về (mặc định 20)"),
      updates: z.array(z.object({
        row: z.number().describe("Số dòng (2-indexed, dòng 2 = dòng data đầu tiên)"),
        column: z.string().describe("Tên cột: Status, Topic, Note, AI_Score"),
        value: z.string().describe("Giá trị mới"),
      })).optional().describe("[update] Danh sách cập nhật"),
    },
    async ({ action, status, platform, topic, limit, updates }) => {
      try {
        await ensureSheetWithHeader();
      } catch (e) {
        return { content: [{ type: "text", text: `ERROR Sheets: ${e.message}` }] };
      }
      const sheets = await getSheets();

      if (action === "read") {
        const max = Math.min(limit || 20, 100);
        try {
          const r = await sheets.spreadsheets.values.get({
            spreadsheetId: SPREADSHEET_ID,
            range: `${SHEET_NAME}!A1:L`,
          });
          const rows = r.data.values || [];
          if (rows.length <= 1) {
            return { content: [{ type: "text", text: "Sheet rỗng (chỉ có header)" }] };
          }
          const header = rows[0];
          const colIdx = {};
          header.forEach((h, i) => { colIdx[h.toLowerCase().replace(/\s+/g, "_")] = i; });

          let dataRows = rows.slice(1).map((row, i) => ({ rowNum: i + 2, data: row }));

          if (status) {
            const si = colIdx["status"];
            if (si !== undefined) dataRows = dataRows.filter(r => (r.data[si] || "").toLowerCase() === status.toLowerCase());
          }
          if (platform) {
            const pi = colIdx["platform"];
            if (pi !== undefined) dataRows = dataRows.filter(r => (r.data[pi] || "").toLowerCase() === platform.toLowerCase());
          }
          if (topic) {
            const ti = colIdx["topic"];
            if (ti !== undefined) dataRows = dataRows.filter(r => (r.data[ti] || "").toLowerCase() === topic.toLowerCase());
          }

          dataRows = dataRows.slice(0, max);

          if (dataRows.length === 0) {
            return { content: [{ type: "text", text: "Không tìm thấy dòng nào khớp filter" }] };
          }

          const lines = [`Tìm thấy ${dataRows.length} dòng:`, ""];
          for (const r of dataRows) {
            const d = r.data;
            lines.push(
              `Row ${r.rowNum}: [${d[colIdx["platform"]] || ""}] ${(d[colIdx["title"]] || "").slice(0, 60)} ` +
              `| author=${d[colIdx["author"]] || ""} | topic=${d[colIdx["topic"]] || ""} ` +
              `| status=${d[colIdx["status"]] || "n/a"}`
            );
          }
          return { content: [{ type: "text", text: lines.join("\n") }] };

        } catch (e) {
          return { content: [{ type: "text", text: `ERROR read: ${e.message}` }] };
        }
      }

      if (action === "update") {
        if (!Array.isArray(updates) || updates.length === 0) {
          return { content: [{ type: "text", text: "ERROR: updates rỗng" }] };
        }

        const COLUMN_MAP = {
          "status": "K", "topic": "G", "note": "J", "ai_score": "L",
          "Status": "K", "Topic": "G", "Note": "J", "AI_Score": "L",
        };

        const results = [];
        for (const u of updates) {
          const col = COLUMN_MAP[u.column] || COLUMN_MAP[u.column.toLowerCase()];
          if (!col) {
            results.push(`Row ${u.row}: ERROR cột "${u.column}" không hợp lệ (dùng: Status, Topic, Note, AI_Score)`);
            continue;
          }
          try {
            await sheets.spreadsheets.values.update({
              spreadsheetId: SPREADSHEET_ID,
              range: `${SHEET_NAME}!${col}${u.row}`,
              valueInputOption: "RAW",
              requestBody: { values: [[u.value]] },
            });
            results.push(`Row ${u.row}: ${u.column} = "${u.value}" ✓`);
          } catch (e) {
            results.push(`Row ${u.row}: ERROR ${e.message}`);
          }
        }
        return { content: [{ type: "text", text: results.join("\n") }] };
      }

      return { content: [{ type: "text", text: "ERROR: action phải là 'read' hoặc 'update'" }] };
    },
  );

  return server;
}

// ---------------------------------------------------------------------------
// HTTP transport (stateless: spawn 1 transport per request)
// ---------------------------------------------------------------------------

const app = express();
app.use(express.json({ limit: "4mb" }));

app.get("/healthz", (_req, res) => res.json({ ok: true }));

app.post("/mcp", async (req, res) => {
  try {
    const server = buildMcpServer();
    const transport = new StreamableHTTPServerTransport({
      sessionIdGenerator: () => randomUUID(),
      enableJsonResponse: true,
    });
    res.on("close", () => {
      transport.close().catch(() => {});
      server.close().catch(() => {});
    });
    await server.connect(transport);
    await transport.handleRequest(req, res, req.body);
  } catch (e) {
    console.error("MCP /mcp error:", e);
    if (!res.headersSent) {
      res.status(500).json({
        jsonrpc: "2.0",
        error: { code: -32603, message: `Internal error: ${e.message}` },
        id: null,
      });
    }
  }
});

// MCP spec: GET/DELETE /mcp khi chưa init session → 405.
app.get("/mcp", (_req, res) => res.status(405).json({ error: "Method Not Allowed" }));
app.delete("/mcp", (_req, res) => res.status(405).json({ error: "Method Not Allowed" }));

app.listen(PORT, "0.0.0.0", () => {
  console.log(`[crawler-mcp] listening on http://0.0.0.0:${PORT}/mcp`);
  console.log(`[crawler-mcp] spreadsheet=${SPREADSHEET_ID || "(unset)"} sheet=${SHEET_NAME}`);
});
