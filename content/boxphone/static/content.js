// ── CONTENT MANAGER ──
async function addContent() {
    const title = document.getElementById('ctTitle').value.trim();
    const video = document.getElementById('ctVideo').value.trim();
    const caption = document.getElementById('ctCaption').value.trim();
    const hashtags = document.getElementById('ctHashtags').value.trim();
    const tags = document.getElementById('ctTags').value.trim();
    const product = document.getElementById('ctProduct').value.trim();
    const link = document.getElementById('ctLink').value.trim();
    if (!title || !video) { alert('Nhập Tiêu đề và Đường dẫn video!'); return; }
    const r = await fetch('/api/content', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title, video_path: video, caption, hashtags, tags, product_name: product || null, product_link: link || null })
    }).then(x => x.json());
    if (r.success) {
        showToast('Đã thêm nội dung!', 'success');
        loadContent();
        document.getElementById('ctTitle').value = '';
        document.getElementById('ctVideo').value = '';
        document.getElementById('ctCaption').value = '';
    } else {
        showToast('Lỗi: ' + r.error, 'error');
    }
}

async function loadContent() {
    const r = await fetch('/api/content').then(x => x.json());
    const tb = document.getElementById('contentTable');
    if (!r.contents || !r.contents.length) {
        tb.innerHTML = '<tr><td colspan="7" style="text-align:center;color:#666">Chưa có nội dung</td></tr>';
        return;
    }
    tb.innerHTML = r.contents.map(c => `
        <tr>
            <td>${c.id}</td>
            <td>${c.title}</td>
            <td><span title="${c.video_path}" style="font-size:0.75rem">${c.video_path ? c.video_path.split(/[\\/]/).pop() : '-'}</span></td>
            <td style="max-width:150px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${c.caption || '-'}</td>
            <td>${c.hashtags || '-'}</td>
            <td>${c.used_count || 0}</td>
            <td><button class="btn btn-danger btn-sm" onclick="deleteContent(${c.id})">🗑️</button></td>
        </tr>`).join('');
    loadContentStats(r.contents);
}

function loadContentStats(contents) {
    const total = contents.length;
    const used = contents.filter(c => c.used_count > 0).length;
    const unused = total - used;
    const el = document.getElementById('contentStats');
    if (el) el.innerHTML = `
        <div style="background:#16213e;padding:10px 18px;border-radius:8px;text-align:center">
            <div style="font-size:1.4rem;font-weight:700;color:#e91e63">${total}</div>
            <div>Tổng nội dung</div>
        </div>
        <div style="background:#16213e;padding:10px 18px;border-radius:8px;text-align:center">
            <div style="font-size:1.4rem;font-weight:700;color:#2ecc71">${used}</div>
            <div>Đã dùng</div>
        </div>
        <div style="background:#16213e;padding:10px 18px;border-radius:8px;text-align:center">
            <div style="font-size:1.4rem;font-weight:700;color:#f39c12">${unused}</div>
            <div>Chưa dùng</div>
        </div>`;
}

async function deleteContent(id) {
    if (!confirm('Xoá nội dung #' + id + '?')) return;
    const r = await fetch('/api/content/' + id, { method: 'DELETE' }).then(x => x.json());
    if (r.success) { showToast('Đã xoá!', 'success'); loadContent(); }
    else showToast('Lỗi: ' + r.error, 'error');
}

async function importContentFolder() {
    const folder = prompt('Nhập đường dẫn thư mục chứa video:');
    if (!folder) return;
    const r = await fetch('/api/content/import_folder', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ folder_path: folder })
    }).then(x => x.json());
    if (r.success) { showToast('Import xong: ' + r.imported + ' video', 'success'); loadContent(); }
    else showToast('Lỗi: ' + r.error, 'error');
}

async function createCampaign() {
    const name = document.getElementById('campName').value.trim();
    const schedule_type = document.getElementById('campSchedule').value;
    const note = document.getElementById('campNote').value.trim();
    if (!name) { alert('Nhập tên campaign!'); return; }
    const r = await fetch('/api/campaigns', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, schedule_type, note })
    }).then(x => x.json());
    if (r.success) { showToast('Đã tạo campaign!', 'success'); loadCampaigns(); }
    else showToast('Lỗi: ' + r.error, 'error');
}

async function loadCampaigns() {
    const r = await fetch('/api/campaigns').then(x => x.json());
    const el = document.getElementById('campaignList');
    if (!r.campaigns || !r.campaigns.length) { el.innerHTML = '<div style="color:#666">Chưa có campaign</div>'; return; }
    el.innerHTML = r.campaigns.map(c => `
        <div style="background:#16213e;border-radius:8px;padding:10px 14px;margin-bottom:8px;display:flex;justify-content:space-between;align-items:center">
            <div>
                <span style="font-weight:700;color:#e91e63">${c.name}</span>
                <span style="color:#888;font-size:0.78rem;margin-left:10px">${c.schedule_type}</span>
                ${c.note ? '<span style="color:#aaa;font-size:0.75rem;margin-left:8px">— ' + c.note + '</span>' : ''}
            </div>
            <button class="btn btn-danger btn-sm" onclick="deleteCampaign(${c.id})">🗑️</button>
        </div>`).join('');
}

async function deleteCampaign(id) {
    if (!confirm('Xoá campaign #' + id + '?')) return;
    await fetch('/api/campaigns/' + id, { method: 'DELETE' });
    loadCampaigns();
}
