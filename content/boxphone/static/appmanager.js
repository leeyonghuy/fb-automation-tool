// ── APP MANAGER ──
function amLog(msg) {
    const el = document.getElementById('amLog');
    if (el) { el.innerHTML += '<div>[' + new Date().toLocaleTimeString() + '] ' + msg + '</div>'; el.scrollTop = el.scrollHeight; }
}

function amGetSerials() {
    const sel = document.getElementById('amSerials');
    return Array.from(sel.selectedOptions).map(o => o.value).filter(v => v);
}

function amGetPackage() {
    return document.getElementById('amPackage').value.trim();
}

async function amGetApps() {
    const serials = amGetSerials();
    if (!serials.length) { alert('Chọn ít nhất 1 thiết bị!'); return; }
    const serial = serials[0];
    amLog('Đang lấy danh sách app: ' + serial);
    const r = await fetch('/api/app_manager/' + serial + '/list_apps').then(x => x.json());
    if (r.success) {
        document.getElementById('amAppsCard').style.display = 'block';
        document.getElementById('amAppsList').innerHTML = (r.packages || []).join('<br>');
        amLog('Tìm thấy ' + (r.packages || []).length + ' app');
    } else amLog('❌ ' + r.error);
}

async function amOpenApp() {
    const serials = amGetSerials();
    const pkg = amGetPackage();
    if (!serials.length || !pkg) { alert('Chọn thiết bị và nhập package name!'); return; }
    for (const serial of serials) {
        amLog('Mở app ' + pkg + ' trên ' + serial);
        const r = await fetch('/api/app_manager/' + serial + '/open', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ package: pkg })
        }).then(x => x.json());
        amLog((r.success ? '✅' : '❌') + ' ' + serial + ': ' + (r.error || 'OK'));
    }
}

async function amForceStop() {
    const serials = amGetSerials();
    const pkg = amGetPackage();
    if (!serials.length || !pkg) { alert('Chọn thiết bị và nhập package name!'); return; }
    for (const serial of serials) {
        amLog('Force stop ' + pkg + ' trên ' + serial);
        const r = await fetch('/api/app_manager/' + serial + '/force_stop', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ package: pkg })
        }).then(x => x.json());
        amLog((r.success ? '✅' : '❌') + ' ' + serial + ': ' + (r.error || 'OK'));
    }
}

async function amClearData() {
    const serials = amGetSerials();
    const pkg = amGetPackage();
    if (!serials.length || !pkg) { alert('Chọn thiết bị và nhập package name!'); return; }
    if (!confirm('Xoá toàn bộ data của ' + pkg + ' trên ' + serials.length + ' thiết bị?')) return;
    for (const serial of serials) {
        amLog('Clear data ' + pkg + ' trên ' + serial);
        const r = await fetch('/api/app_manager/' + serial + '/clear_data', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ package: pkg })
        }).then(x => x.json());
        amLog((r.success ? '✅' : '❌') + ' ' + serial + ': ' + (r.error || 'OK'));
    }
}

async function amUninstall() {
    const serials = amGetSerials();
    const pkg = amGetPackage();
    if (!serials.length || !pkg) { alert('Chọn thiết bị và nhập package name!'); return; }
    if (!confirm('Gỡ cài đặt ' + pkg + ' trên ' + serials.length + ' thiết bị?')) return;
    for (const serial of serials) {
        amLog('Gỡ ' + pkg + ' trên ' + serial);
        const r = await fetch('/api/app_manager/' + serial + '/uninstall', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ package: pkg })
        }).then(x => x.json());
        amLog((r.success ? '✅' : '❌') + ' ' + serial + ': ' + (r.error || 'OK'));
    }
}

async function amInstallApk() {
    const serials = amGetSerials();
    const apk = document.getElementById('amApkPath').value.trim();
    if (!serials.length || !apk) { alert('Chọn thiết bị và nhập đường dẫn APK!'); return; }
    for (const serial of serials) {
        amLog('Cài APK ' + apk + ' → ' + serial);
        const r = await fetch('/api/app_manager/' + serial + '/install', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ apk_path: apk })
        }).then(x => x.json());
        amLog((r.success ? '✅' : '❌') + ' ' + serial + ': ' + (r.error || 'OK'));
    }
}

async function amReboot() {
    const serials = amGetSerials();
    if (!serials.length) { alert('Chọn thiết bị!'); return; }
    if (!confirm('Reboot ' + serials.length + ' thiết bị?')) return;
    for (const serial of serials) {
        amLog('Reboot ' + serial);
        const r = await fetch('/api/app_manager/' + serial + '/reboot', { method: 'POST' }).then(x => x.json());
        amLog((r.success ? '✅' : '❌') + ' ' + serial);
    }
}

async function amWake() {
    const serials = amGetSerials();
    if (!serials.length) { alert('Chọn thiết bị!'); return; }
    for (const serial of serials) {
        await fetch('/api/devices/' + serial + '/keyevent', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ keycode: 224 })
        });
        amLog('Wake ' + serial);
    }
}

async function amLock() {
    const serials = amGetSerials();
    if (!serials.length) { alert('Chọn thiết bị!'); return; }
    for (const serial of serials) {
        await fetch('/api/devices/' + serial + '/keyevent', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ keycode: 26 })
        });
        amLog('Lock ' + serial);
    }
}

async function amBattery() {
    const serials = amGetSerials();
    if (!serials.length) { alert('Chọn thiết bị!'); return; }
    for (const serial of serials) {
        const r = await fetch('/api/app_manager/' + serial + '/battery').then(x => x.json());
        amLog(serial + ' 🔋 ' + (r.battery || r.error || 'N/A'));
    }
}

async function amStorage() {
    const serials = amGetSerials();
    if (!serials.length) { alert('Chọn thiết bị!'); return; }
    for (const serial of serials) {
        const r = await fetch('/api/app_manager/' + serial + '/storage').then(x => x.json());
        amLog(serial + ' 💾 ' + (r.storage || r.error || 'N/A'));
    }
}

async function amScreenTimeout() {
    const serials = amGetSerials();
    if (!serials.length) { alert('Chọn thiết bị!'); return; }
    for (const serial of serials) {
        const r = await fetch('/api/app_manager/' + serial + '/screen_timeout', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ timeout_ms: 600000 })
        }).then(x => x.json());
        amLog((r.success ? '✅' : '❌') + ' Screen timeout 10p: ' + serial);
    }
}

async function amShellRun() {
    const serials = amGetSerials();
    const cmd = document.getElementById('amShell').value.trim();
    if (!serials.length || !cmd) { alert('Chọn thiết bị và nhập lệnh!'); return; }
    for (const serial of serials) {
        const r = await fetch('/api/app_manager/' + serial + '/shell', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ command: cmd })
        }).then(x => x.json());
        amLog(serial + ' → ' + (r.output || r.error || 'OK'));
    }
}

// Populate amSerials khi vào tab appmanager
async function loadAmDevices() {
    const r = await fetch('/api/devices').then(x => x.json());
    const sel = document.getElementById('amSerials');
    sel.innerHTML = '';
    (r.devices || []).filter(d => d.adb_status === 'device').forEach(d => {
        sel.innerHTML += `<option value="${d.serial}">${d.model || d.serial} (${d.serial})</option>`;
    });
    if (!sel.options.length) sel.innerHTML = '<option value="">Không có thiết bị online</option>';
}
