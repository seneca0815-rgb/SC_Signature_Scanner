# test_overlay.py
import tkinter as tk

root = tk.Tk()
root.overrideredirect(True)
root.attributes("-topmost", True)
root.attributes("-alpha", 0.9)
root.configure(bg="black")
root.wm_attributes("-transparentcolor", "black")
root.geometry("+100+100")

label = tk.Label(
    root,
    text="ℹ  Overlay funktioniert! (Fenster schließen: Alt+F4)",
    bg="#111827",
    fg="#e2c97e",
    font=("Consolas", 13),
    padx=12, pady=8,
)
label.pack()
root.mainloop()