"""
fb_page_editor.py
Thêm Editor/Admin vào Fanpage qua Playwright + IX Browser
"""

import asyncio
import time
from pathlib import Path


# ─────────────────────────────────────────────
# Add Editor / Admin
# ─────────────────────────────────────────────

ROLES = {
    "admin": "Admin",
    "editor": "Editor",
    "moderator": "Moderator",
    "advertiser": "Advertiser",
    "analyst": "Analyst",
}


async def add_page_editor(page, page_url: str, editor_email_or_url: str,
                           role: str = "editor") -> dict:
    """
    Thêm Editor/Admin vào page.
    page: Playwright page object đã login với acc chủ page
    page_url: URL của Fanpage (https://www.facebook.com/pagename hoặc /pages/.../id)
    editor_email_or_url: email hoặc profile URL của acc cần add
    role: admin | editor | moderator | advertiser | analyst
    """
    result = {"success": False, "editor": editor_email_or_url, "role": role, "error": ""}
    try:
        print(f"[fb_page_editor] Add {role}: {editor_email_or_url} vào {page_url}")

        # Mở trang Page Roles
        # Thử URL cài đặt page roles mới (New Pages Experience)
        if "/pages/" in page_url and not page_url.endswith("/"):
            page_url = page_url + "/"

        settings_url = page_url.rstrip("/") + "/settings/?tab=admin_roles"
        await page.goto(settings_url, wait_until="networkidle", timeout=30000)
        await asyncio.sleep(3)

        # Nếu không vào được settings, thử route khác
        if "settings" not in page.url:
            # New Pages Experience - Page Access
            alt_url = page_url.rstrip("/") + "/manage/access/"
            await page.goto(alt_url, wait_until="networkidle", timeout=20000)
            await asyncio.sleep(3)

        # Tìm nút "Add New Page Role" hoặc "Give access"
        add_btn_selectors = [
            'button:has-text("Add New Page Role")',
            'button:has-text("Give access")',
            'button:has-text("Add People")',
            'button:has-text("Thêm người")',
            '[aria-label*="Add role"]',
        ]
        clicked = False
        for sel in add_btn_selectors:
            try:
                btn = page.locator(sel).first
                if await btn.is_visible(timeout=3000):
                    await btn.click()
                    clicked = True
                    await asyncio.sleep(2)
                    break
            except Exception:
                continue

        if not clicked:
            result["error"] = "Không tìm thấy nút Add Role"
            return result

        # Nhập email/URL của editor
        input_sel = [
            'input[placeholder*="Search for people"]',
            'input[placeholder*="Name or email"]',
            'input[aria-label*="Search"]',
            'input[type="text"]',
        ]
        for sel in input_sel:
            try:
                inp = page.locator(sel).first
                if await inp.is_visible(timeout=3000):
                    await inp.click()
                    await inp.fill(editor_email_or_url)
                    await asyncio.sleep(2)
                    break
            except Exception:
                continue

        # Chọn gợi ý người dùng đầu tiên
        try:
            suggestion = page.locator('[role="option"], [data-testid*="search-result"]').first
            if await suggestion.is_visible(timeout=5000):
                await suggestion.click()
                await asyncio.sleep(1)
        except Exception:
            pass

        # Chọn role
        role_label = ROLES.get(role, "Editor")
        try:
            role_dropdown = page.locator('select, [role="listbox"], [aria-label*="Role"]').first
            if await role_dropdown.is_visible(timeout=3000):
                await role_dropdown.select_option(label=role_label)
                await asyncio.sleep(1)
        except Exception:
            # Thử click vào radio/option
            try:
                role_opt = page.locator(f'text="{role_label}"').first
                if await role_opt.is_visible(timeout=3000):
                    await role_opt.click()
                    await asyncio.sleep(1)
            except Exception:
                pass

        # Xác nhận / Submit
        confirm_selectors = [
            'button:has-text("Save")',
            'button:has-text("Add")',
            'button:has-text("Submit")',
            'button:has-text("Lưu")',
            'button:has-text("Thêm")',
        ]
        for sel in confirm_selectors:
            try:
                btn = page.locator(sel).first
                if await btn.is_visible(timeout=3000):
                    await btn.click()
                    await asyncio.sleep(3)
                    break
            except Exception:
                continue

        # Cập nhật DB
        from fb_page import update_page, get_all_pages
        pages = get_all_pages()
        for p in pages:
            if p.get("page_url", "").rstrip("/") == page_url.rstrip("/") or \
               page_url.rstrip("/").endswith(p.get("page_id", "NOPE")):
                editors = p.get("editors", [])
                if editor_email_or_url not in editors:
                    editors.append({"email_or_url": editor_email_or_url, "role": role,
                                    "added_at": time.strftime("%Y-%m-%d %H:%M:%S")})
                update_page(p["page_id"], editors=editors)
                break

        result["success"] = True
        print(f"[fb_page_editor] ✓ Add {role} thành công: {editor_email_or_url}")

    except Exception as e:
        result["error"] = str(e)
        print(f"[fb_page_editor] ✗ Lỗi: {e}")

    return result


async def batch_add_editors(tasks: list) -> list:
    """
    Thêm editor hàng loạt.
    tasks: [{
        "profile_id": int,         # IX profile của acc chủ page
        "page_url": str,
        "editor_email": str,       # email của acc cần add
        "role": str                # editor | admin | moderator
    }]
    """
    from ix_browser import connect_playwright, disconnect_playwright

    results = []
    for i, task in enumerate(tasks):
        print(f"\n[fb_page_editor] [{i+1}/{len(tasks)}] Xử lý: {task.get('page_url')}")
        profile_id = task.get("profile_id")
        if not profile_id:
            results.append({"success": False, "error": "Thiếu profile_id", **task})
            continue

        pw, browser, ctx, playwright_page = await connect_playwright(
            profile_id, task.get("page_url", "https://www.facebook.com")
        )
        if not playwright_page:
            results.append({"success": False, "error": "Browser không mở được", **task})
            continue

        try:
            r = await add_page_editor(
                playwright_page,
                page_url=task.get("page_url", ""),
                editor_email_or_url=task.get("editor_email", ""),
                role=task.get("role", "editor"),
            )
            results.append(r)
        except Exception as e:
            results.append({"success": False, "error": str(e), **task})
        finally:
            await disconnect_playwright(pw, browser, profile_id)

        await asyncio.sleep(15)

    ok = sum(1 for r in results if r.get("success"))
    print(f"\n[fb_page_editor] Hoàn tất: {ok}/{len(results)} editor đã add")
    return results


async def remove_page_editor(page, page_url: str, editor_name: str) -> dict:
    """Xóa editor khỏi page"""
    result = {"success": False, "editor": editor_name, "error": ""}
    try:
        settings_url = page_url.rstrip("/") + "/settings/?tab=admin_roles"
        await page.goto(settings_url, wait_until="networkidle", timeout=30000)
        await asyncio.sleep(3)

        # Tìm editor trong danh sách và bấm Remove
        remove_btn = page.locator(f'text="{editor_name}"').locator('..').locator('button:has-text("Remove"), button:has-text("Xóa")')
        if await remove_btn.is_visible(timeout=5000):
            await remove_btn.click()
            await asyncio.sleep(2)
            confirm = page.locator('button:has-text("Confirm"), button:has-text("Remove"), button:has-text("Xác nhận")').first
            if await confirm.is_visible(timeout=3000):
                await confirm.click()
                await asyncio.sleep(2)
            result["success"] = True
            print(f"[fb_page_editor] ✓ Đã xóa {editor_name}")
        else:
            result["error"] = f"Không tìm thấy editor: {editor_name}"
    except Exception as e:
        result["error"] = str(e)
    return result
