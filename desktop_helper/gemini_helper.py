import json
import time
import ctypes
from ctypes import wintypes
import threading
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
import pyperclip

PORT = 8765

VK_MENU = 0x12       # Alt
VK_CONTROL = 0x11    # Ctrl
VK_V = 0x56          # V
VK_RETURN = 0x0D     # Enter
KEYEVENTF_KEYUP = 0x0002
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

def attach_to_default_desktop():
    try:
        h_default = user32.OpenDesktopW("default", 0, False, 0x01FF)
        if h_default:
            user32.SetThreadDesktop(h_default)
            return h_default
    except Exception as e:
        print(f"[Helper] Failed to attach to default desktop: {e}")
    return None

def send_key_combo(modifier_vk, key_vk):
    user32.keybd_event(modifier_vk, 0, 0, 0)
    time.sleep(0.06)
    user32.keybd_event(key_vk, 0, 0, 0)
    time.sleep(0.06)
    user32.keybd_event(key_vk, 0, KEYEVENTF_KEYUP, 0)
    time.sleep(0.06)
    user32.keybd_event(modifier_vk, 0, KEYEVENTF_KEYUP, 0)

def send_tap_key(key_vk):
    user32.keybd_event(key_vk, 0, 0, 0)
    time.sleep(0.06)
    user32.keybd_event(key_vk, 0, KEYEVENTF_KEYUP, 0)

def bring_window_to_foreground(hwnd):
    try:
        user32.AllowSetForegroundWindow(-1)
        fore_hwnd = user32.GetForegroundWindow()
        fore_thread = user32.GetWindowThreadProcessId(fore_hwnd, None)
        my_thread = kernel32.GetCurrentThreadId()

        user32.AttachThreadInput(my_thread, fore_thread, True)
        user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
        user32.AttachThreadInput(my_thread, fore_thread, False)
    except Exception as e:
        print(f"[Helper] Error in bring_to_foreground: {e}")

def find_gemini_window(h_desktop):
    gemini_candidates = []
    chrome_candidates = []

    def enum_cb(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            buf = ctypes.create_unicode_buffer(512)
            user32.GetWindowTextW(hwnd, buf, 512)
            title = buf.value
            if title:
                rect = wintypes.RECT()
                user32.GetWindowRect(hwnd, ctypes.byref(rect))
                w = rect.right - rect.left
                h = rect.bottom - rect.top
                if w > 200 and h > 200:
                    t_lower = title.lower()
                    if "gemini" in t_lower:
                        gemini_candidates.append((hwnd, title, rect))
                    elif "chrome" in t_lower:
                        chrome_candidates.append((hwnd, title, rect))
        return True

    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    user32.EnumDesktopWindows(h_desktop, WNDENUMPROC(enum_cb), 0)

    if gemini_candidates:
        return gemini_candidates[0]
    return chrome_candidates[0] if chrome_candidates else (None, None, None)

def execute_auto_paste_and_submit(prompt):
    try:
        h_desk = attach_to_default_desktop()

        for vk in [VK_MENU, VK_CONTROL, 0x10]:
            user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)

        # 1. Copy prompt + report screen data to clipboard
        pyperclip.copy(prompt)
        print(f"[Helper] Prompt & Screen Data copied to clipboard ({len(prompt)} chars).")

        # 2. Poll for Gemini window over 4 seconds
        target_hwnd = None
        target_rect = None
        target_title = None

        start_time = time.time()
        while time.time() - start_time < 4.0:
            hwnd, title, rect = find_gemini_window(h_desk)
            if hwnd and "gemini" in (title or "").lower():
                target_hwnd = hwnd
                target_rect = rect
                target_title = title
                break
            time.sleep(0.4)

        if not target_hwnd:
            hwnd, title, rect = find_gemini_window(h_desk)
            target_hwnd = hwnd
            target_rect = rect
            target_title = title

        # Allow Gemini SPA DOM to settle
        time.sleep(1.8)

        if target_hwnd:
            print(f"[Helper] Focusing Gemini window: [{target_hwnd}] '{target_title}'")
            bring_window_to_foreground(target_hwnd)
            time.sleep(0.3)

            rect = wintypes.RECT()
            user32.GetWindowRect(target_hwnd, ctypes.byref(rect))
            w = rect.right - rect.left
            h = rect.bottom - rect.top

            # Click near bottom center of the window (Gemini's '+ Ask Gemini' prompt bar)
            cx = rect.left + (w // 2)
            cy = rect.bottom - 75
            print(f"[Helper] Clicking prompt input area at ({cx}, {cy})...")
            user32.SetCursorPos(cx, cy)
            time.sleep(0.1)
            user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
            time.sleep(0.05)
            user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
            time.sleep(0.3)

        # 3. Paste with Ctrl + V
        print("[Helper] Dispatching Ctrl + V into Gemini...")
        send_key_combo(VK_CONTROL, VK_V)
        time.sleep(0.5)

        # 4. Press Enter to submit
        print("[Helper] Dispatching Enter to submit...")
        send_tap_key(VK_RETURN)
        print("[Helper] Automation sequence complete! Prompt posted successfully.")

    except Exception as e:
        print(f"[Helper] Error in auto-submit: {e}")

class GeminiHelperHandler(BaseHTTPRequestHandler):
    def _send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Requested-With")
        self.send_header("Access-Control-Allow-Private-Network", "true")
        self.send_header("Access-Control-Max-Age", "86400")

    def do_OPTIONS(self):
        self.send_response(204)
        self._send_cors_headers()
        self.end_headers()

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self._send_cors_headers()
        self.end_headers()
        resp = json.dumps({
            "status": "ok",
            "service": "ERPNext Gemini Screen & Sidebar Helper",
            "port": PORT
        })
        self.wfile.write(resp.encode("utf-8"))

    def do_POST(self):
        if self.path != "/ask-gemini":
            self.send_response(404)
            self._send_cors_headers()
            self.end_headers()
            return

        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length)

        try:
            payload = json.loads(post_data.decode("utf-8")) if post_data else {}
        except Exception:
            payload = {}

        prompt = payload.get("prompt", "").strip()

        if not prompt:
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps({"status": "error", "message": "Prompt is empty"}).encode("utf-8"))
            return

        print(f"[Helper] Received prompt + report table ({len(prompt)} chars)")

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(json.dumps({
            "status": "success",
            "message": "Automation triggered"
        }).encode("utf-8"))

        threading.Thread(target=execute_auto_paste_and_submit, args=(prompt,), daemon=True).start()

    def log_message(self, format, *args):
        print(f"[HTTP] {self.address_string()} - {format % args}")

def run():
    server_address = ("127.0.0.1", PORT)
    httpd = ThreadingHTTPServer(server_address, GeminiHelperHandler)
    print("============================================================")
    print(f"  ERPNext Gemini Screen & Sidebar Helper running on port {PORT}")
    print(f"  Listening on: http://127.0.0.1:{PORT}")
    print("  Ready to paste & submit prompt + report screen data!")
    print("============================================================")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping helper...")
        httpd.server_close()

if __name__ == '__main__':
    run()
