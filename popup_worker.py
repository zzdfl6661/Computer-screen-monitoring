import sys
import json
import platform
import ctypes
import tkinter as tk
import math
import time


def _prepare_tk_dpi():
    if platform.system() != 'Windows':
        return
    try:
        user32 = ctypes.WinDLL('user32', use_last_error=True)
        user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except Exception:
        try:
            shcore = ctypes.WinDLL('shcore', use_last_error=True)
            shcore.SetProcessDpiAwareness(2)
        except Exception:
            pass


def show(message, activity_type):
    _prepare_tk_dpi()
    root = tk.Tk()
    root.title("学习小提醒")
    root.overrideredirect(True)
    root.resizable(False, False)
    root.configure(bg="#fff7ed")
    root.attributes("-topmost", True)
    root.attributes("-alpha", 0.0)

    card = tk.Frame(root, bg="#fff7ed", highlightbackground="#fdba74", highlightthickness=2)
    card.pack(fill="both", expand=True)

    tk.Label(card, text="🌟", bg="#fff7ed", fg="#fb923c",
             font=("Segoe UI Emoji", 32)).pack(pady=(14, 0))
    tk.Label(card, text="学习小提醒", bg="#fff7ed", fg="#9a3412",
             font=("Microsoft YaHei UI", 16, "bold")).pack(pady=(0, 4))
    subtitle = "休息一下，再继续加油吧～" if activity_type == "entertainment" else "慢慢来，你做得很好～"
    tk.Label(card, text=subtitle, bg="#fff7ed", fg="#c2410c",
             font=("Microsoft YaHei UI", 10)).pack()
    tk.Label(card, text=message, bg="#fff7ed", fg="#431407",
             font=("Microsoft YaHei UI", 13), wraplength=420,
             justify="center").pack(padx=28, pady=(9, 10))
    countdown = tk.Label(card, bg="#fed7aa", fg="#9a3412",
                         font=("Microsoft YaHei UI", 9))
    countdown.pack(fill="x", padx=28)

    closing = [False]

    def finish():
        if closing[0]:
            return
        closing[0] = True

        def out(frame=0):
            alpha = max(0.0, 1 - frame / 22)
            try:
                root.attributes("-alpha", alpha)
                if frame < 22:
                    root.after(60, lambda: out(frame + 1))
                else:
                    root.destroy()
            except tk.TclError:
                pass
        out()

    button = tk.Button(card, text="知道啦 ✨", bg="#fb923c", fg="white",
                       activebackground="#f97316", relief="flat", bd=0,
                       cursor="hand2", font=("Microsoft YaHei UI", 11, "bold"),
                       padx=18, pady=7, command=finish)
    button.pack(pady=14)

    root.update_idletasks()
    width = max(490, root.winfo_reqwidth())
    height = max(245, root.winfo_reqheight())
    x = max(0, root.winfo_pointerx() - width // 2)
    y = max(0, root.winfo_pointery() - height // 2)
    base_y = y
    started = time.monotonic()

    def animate(frame=0):
        if closing[0]:
            return
        elapsed = time.monotonic() - started
        if frame < 14:
            progress = frame / 13
            root.attributes("-alpha", min(1.0, progress * 1.25))
            root.geometry(f"{width}x{height}+{x}+{base_y + int((1-progress)**2 * 32)}")
        else:
            root.geometry(f"{width}x{height}+{x}+{base_y + int(math.sin(elapsed * 3) * 3)}")
        left = max(0, int(12 - elapsed))
        countdown.config(text=f" {left} 秒后会轻轻消失" + "·" * (1 + frame % 3))
        if elapsed >= 12:
            finish()
            return
        root.after(50, lambda: animate(frame + 1))

    root.bind("<Return>", lambda _e: finish())
    root.bind("<Escape>", lambda _e: finish())
    root.geometry(f"{width}x{height}+{x}+{base_y + 32}")
    root.lift()
    root.focus_force()
    root.after(0, animate)
    root.mainloop()


if __name__ == "__main__":
    try:
        data = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {
            "message": "休息一下", "activity_type": "entertainment"
        }
        show(data.get("message", ""), data.get("activity_type", "entertainment"))
    except Exception as e:
        print(f"popup error: {e}", file=sys.stderr)
        sys.exit(1)
