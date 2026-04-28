// ── SCHEDULER ──
async function addSchedule() {
    const serial = document.getElementById('schSerial').value.trim();
    const action = document.getElementById('schAction').value;
    const time = document.getElementById('schTime').value;
    const repeat = document.getElementById('schRepeat').value;
    const video = document.getElementById('schVideo').value.trim();
    const caption = document.getElementById('schCaption').value.trim();
    const note = document.getElementById('schNote').value.trim();
    if (!serial || !time) { alert('Nhập Serial và Thời gian!'); return; }
    const body = { serial, action, scheduled_time: time, repeat_type: repeat || null, note };
    if (action === 'upload') { body.video_path = video; body.caption = caption; }
    const r = await fetch('/api/scheduler', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
    }).then(x => x.json());
    if (r.success) {
        showToast('Đã tạo lịch!', 'success');
        loadSchedules();
        document.getElementById('schSerial').value = '';
        document.getElementById('schTime').value = '';
        document.getElementById('schNote').value = '';
    } else {
        showToast('Lỗi: ' + r.error, 'error');
    }
}

async function loadSchedules() {
    const el = document.getElementById('schedulerStatus');
    if (el) el.textContent = 'Đang tải...';
    const r = await fetch('/api/scheduler').then(x => x.json());
    const tb = document.getElementById('scheduleTable');
    if (!r.schedules || !r.schedules.length) {
        tb.innerHTML = '<tr><td colspan="8" style="text-align:center;color:#666">Chưa có lịch</td></tr>';
        if (el) el.textContent = '';
        return;
    }
    tb.innerHTML = r.schedules.map(s => `
        <tr>
            <td>${s.id}</td>
            <td><code style="font-size:0.75rem">${s.serial}</code></td>
            <td>${s.action}</td>
            <td>${s.scheduled_time ? s.scheduled_time.substring(0, 16) : '-'}</td>
            <td>${s.repeat_type || 'Không'}</td>
            <td><span class="badge-${s.status === 'done' ? 'online' : s.status === 'pending' ? 'warn' : 'offline'}">${s.status}</span></td>
            <td>${s.note || '-'}</td>
            <td><button class="btn btn-danger btn-sm" onclick="deleteSchedule(${s.id})">🗑️</button></td>
        </tr>`).join('');
    if (el) el.textContent = r.schedules.length + ' lịch';
}

async function deleteSchedule(id) {
    if (!confirm('Xoá lịch #' + id + '?')) return;
    const r = await fetch('/api/scheduler/' + id, { method: 'DELETE' }).then(x => x.json());
    if (r.success) { showToast('Đã xoá!', 'success'); loadSchedules(); }
    else showToast('Lỗi: ' + r.error, 'error');
}
