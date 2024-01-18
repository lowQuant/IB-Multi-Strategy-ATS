
from pathlib import Path

# from tkinter import *
from tkinter import Tk, Canvas, Entry, Text, Button, PhotoImage, Label

# My imports
from .utils import start_trading, stop_trading, exit_application, launch_jupyter
from .log import log_buffer, log_lock, start_event
from .settings_window import open_settings_window

OUTPUT_PATH = Path(__file__).parent
ASSETS_PATH = OUTPUT_PATH / "assets" / "frame0"

def update_gui_with_logs():
    with log_lock:
        if log_buffer:
            updated_log = '\n'.join(list(log_buffer)[-10:])
            canvas.itemconfigure(log_text, text=updated_log)
    window.after(100, update_gui_with_logs)  # Schedule the next check

def relative_to_assets(path: str) -> Path:
    return ASSETS_PATH / Path(path)

window = Tk()
window.geometry("814x555")
window.configure(bg = "#FFFFFF")

canvas = Canvas(window,bg = "#FFFFFF",
    height = 555,width = 814,
    bd = 0,highlightthickness = 0,relief = "ridge")

canvas.place(x = 0, y = 0)
image_image_1 = PhotoImage(
    file=relative_to_assets("image_1.png"))
image_1 = canvas.create_image(
    407.0,
    277.0,
    image=image_image_1
)

canvas.create_text(269.0,15.0,anchor="nw",text="Automated Trading System",fill="#000000",font=("InriaSans Regular", 24 * -1))

log_text = canvas.create_text(79, 214,anchor="nw",text="",fill="#000000",font=("InriaSans Regular", 10),width=500)

# Exit Button
exit_btn_img = PhotoImage(
    file=relative_to_assets("exit.png"))
exit_btn = Button(image=exit_btn_img,
    borderwidth=0,highlightthickness=0,
    command=lambda: exit_application(window), 
    relief="flat"
)
exit_btn.place(x=622.0,y=489.0,width=178.0,height=58.0)

# Settings Button
settings_btn_img = PhotoImage(
    file=relative_to_assets("settings.png"))
settings_btn = Button(image=settings_btn_img,
    borderwidth=0,highlightthickness=0,
    command=lambda: open_settings_window(window),
    relief="flat"
)
settings_btn.place(x=589.0,y=144.0,width=201.0,height=71.0)

# Stop Trading Button
stop_btn_img = PhotoImage(
    file=relative_to_assets("stop_trading.png"))
stop_btn = Button(image=stop_btn_img,
    borderwidth=0,highlightthickness=0,
    command=lambda: stop_trading(stop_btn, start_btn, window),
    relief="flat"
)
stop_btn.place(x=48.0, y=79.0, width=178.0, height=58.0)

# Start Trading Button
start_btn_img = PhotoImage(
    file=relative_to_assets("start_trading.png"))
start_btn = Button(image=start_btn_img,
    borderwidth=0,highlightthickness=0,
    command=lambda: start_trading(stop_btn, start_btn, window, start_event),
    relief="flat"
)
start_btn.place(x=48.0, y=79.0, width=178.0, height=58.0)

# Research Button
research_btn_img = PhotoImage(file=relative_to_assets("research.png"))
research_btn = Button(image=research_btn_img,
    borderwidth=0,highlightthickness=0,
    command=lambda: launch_jupyter(),
    relief="flat")
research_btn.place(x=16.0,y=506.0,width=181.0,height=36.0)

# Portfolio Button
portfolio_btn_img = PhotoImage(file=relative_to_assets("portfolio.png"))
portfolio_btn = Button(image=portfolio_btn_img,
    borderwidth=0,highlightthickness=0,
    command=lambda: print("portfolio clicked"),
    relief="flat")
portfolio_btn.place(x=365.0, y=86.0, width=143.0, height=47.0)

# Database Button
# database_btn_img = PhotoImage(file=relative_to_assets("database.png"))
# database_btn = Button(image=database_btn_img,
#     borderwidth=0,highlightthickness=0,
#     command=lambda: print("database clicked"),
#     relief="flat")
# database_btn.place(x=608.0,y=96.0,width=124.0,height=34.0)

# Bottom Screen Textbox - Advertisement
canvas.create_text(330.0,534.0,anchor="nw",
    text="www.lange-invest.com",
    fill="#000000",
    font=("InriaSans Regular", 14 * -1))

window.resizable(False, False)

def run_gui():
    global window, canvas, log_text
    update_gui_with_logs()
    # Code to create the GUI window and start the Tkinter mainloop
    window.mainloop()
