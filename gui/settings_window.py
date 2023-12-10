from tkinter import Toplevel, ttk, Frame, Label, Entry, Button, Checkbutton, IntVar, messagebox, Toplevel, StringVar
import pyperclip
from data_and_research import ac

changes_made = False

def get_settings_from_db():
    lib = ac.get_library("settings")
    df = lib.read("settings").data
    settings_dict = df.to_dict()
    return settings_dict['Value']

def open_settings_window(main_window):
    settings_window = Toplevel(main_window)
    settings_window.title("Settings")
    settings_window.geometry("407x555")

    tab_control = ttk.Notebook(settings_window)
    general_tab = Frame(tab_control)
    strategies_tab = Frame(tab_control)

    tab_control.add(general_tab, text='General')
    tab_control.add(strategies_tab, text='Strategies')

    tab_control.pack(expand=1, fill="both")

    populate_general_tab(general_tab, tab_control)
    populate_strategies_tab(strategies_tab)

    settings_window.transient(main_window)
    settings_window.grab_set()

def populate_general_tab(tab_frame, tab_control):
    global changes_made
    settings_dict = get_settings_from_db() # Fetch settings from the database


    def mark_changes(*args):
        global changes_made
        changes_made = True

    # IB Port Setting
    Label(tab_frame, text="IB Port:").grid(row=0, column=0, sticky='w', padx=10, pady=10)
    port_entry = Entry(tab_frame)
    port_entry.grid(row=0, column=1, padx=10, pady=10)
    port_entry.insert(0, settings_dict.get("ib_port", "7497"))
    port_entry.bind("<KeyRelease>", mark_changes)
    

    # Database Management Section
    Label(tab_frame, text="Database Management - Local or AWS S3?").grid(row=1, column=0, columnspan=2, sticky='w', padx=10, pady=5)
    db_local_var = IntVar()
    db_s3_var = IntVar()
    Checkbutton(tab_frame, text="Local", variable=db_local_var).grid(row=2, column=0, sticky='w', padx=10, pady=5)
    Checkbutton(tab_frame, text="AWS S3", variable=db_s3_var, command=lambda: [aws_access_id_entry.config(state='normal' if db_s3_var.get() else 'disabled'), aws_access_key_entry.config(state='normal' if db_s3_var.get() else 'disabled'), aws_bucket_name_entry.config(state='normal' if db_s3_var.get() else 'disabled'), aws_region_entry.config(state='normal' if db_s3_var.get() else 'disabled')]).grid(row=2, column=1, sticky='w', padx=10, pady=5)
    
    Label(tab_frame, text="Use S3 if ATS will run on multiple computers").grid(row=3, column=0, columnspan=2, sticky='w', padx=10, pady=0)

    
    # AWS S3 Credentials
    aws_access_id_entry = Entry(tab_frame)
    aws_access_key_entry = Entry(tab_frame)
    aws_bucket_name_entry = Entry(tab_frame)
    aws_region_entry = Entry(tab_frame)

    # If AWS S3 is selected, enable the entries; else keep them disabled
    if settings_dict.get("s3_db_management") == "True":
        aws_access_id_entry.config(state='normal')
        aws_access_key_entry.config(state='normal')
        aws_bucket_name_entry.config(state='normal')
        aws_region_entry.config(state='normal')
    else:
        aws_access_id_entry.config(state='disabled')
        aws_access_key_entry.config(state='disabled')
        aws_bucket_name_entry.config(state='disabled')
        aws_region_entry.config(state='disabled')

    aws_access_id_entry.grid(row=4, column=1, padx=10, pady=5)
    aws_access_key_entry.grid(row=5, column=1, padx=10, pady=5)
    aws_bucket_name_entry.grid(row=6, column=1, padx=10, pady=5)
    aws_region_entry.grid(row=7, column=1, padx=10, pady=5)

    # Set the Values from Settings
    db_local_var.set(1 if settings_dict.get("s3_db_management") == "False" else 0)
    db_s3_var.set(1 if settings_dict.get("s3_db_management") == "True" else 0)
    aws_access_id_entry.insert(0, settings_dict.get("aws_access_id", ""))
    aws_access_key_entry.insert(0, settings_dict.get("aws_access_key", ""))
    aws_bucket_name_entry.insert(0, settings_dict.get("bucket_name", ""))
    aws_region_entry.insert(0, settings_dict.get("region", ""))

    # Bind the event handlers to AWS entries
    aws_access_id_entry.bind("<KeyRelease>", mark_changes)
    aws_access_key_entry.bind("<KeyRelease>", mark_changes)
    aws_bucket_name_entry.bind("<KeyRelease>", mark_changes)
    aws_region_entry.bind("<KeyRelease>", mark_changes)

    # Bind the Checkbutton change events
    db_local_var.trace_add("write", mark_changes)
    db_s3_var.trace_add("write", mark_changes)
    

    Label(tab_frame, text="AWS Access ID:").grid(row=4, column=0, sticky='w', padx=10, pady=5)
    Label(tab_frame, text="AWS Access Key:").grid(row=5, column=0, sticky='w', padx=10, pady=5)
    Label(tab_frame, text="Bucket Name:").grid(row=6, column=0, sticky='w', padx=10, pady=5)
    Label(tab_frame, text="Region:").grid(row=7, column=0, sticky='w', padx=10, pady=5)

    # TWS Automatic Start (Beta)
    tws_auto_start_var = IntVar()
    # TWS Auto-Start Checkbox and Entry fields
    Checkbutton(tab_frame, text="Start TWS Automatically (Beta)", variable=tws_auto_start_var, command=lambda: [username_entry.config(state='normal' if tws_auto_start_var.get() else 'disabled'), password_entry.config(state='normal' if tws_auto_start_var.get() else 'disabled')]).grid(row=8, column=0, columnspan=2, sticky='w', padx=10, pady=10)
    tws_auto_start_var.set(1 if settings_dict.get("start_tws") == "true" else 0)
    tws_auto_start_var.trace_add("write", mark_changes)

    username_entry = Entry(tab_frame, state='disabled')
    password_entry = Entry(tab_frame, show="*", state='disabled')
    username_entry.grid(row=9, column=1, padx=10, pady=5)
    password_entry.grid(row=10, column=1, padx=10, pady=5)
    Label(tab_frame, text="TWS Username:").grid(row=9, column=0, sticky='w', padx=10, pady=5)
    Label(tab_frame, text="TWS Password:").grid(row=10, column=0, sticky='w', padx=10, pady=5)

    username_entry.insert(0, settings_dict.get("username", ""))
    password_entry.insert(0, settings_dict.get("password", ""))

    username_entry.bind("<KeyRelease>", mark_changes)
    password_entry.bind("<KeyRelease>", mark_changes)

    # Save and Exit Buttons
    Button(tab_frame, text="Save", command=lambda: save_general_settings(port_entry.get(), db_local_var.get(), db_s3_var.get(), aws_access_id_entry.get(), aws_access_key_entry.get(), aws_bucket_name_entry.get(), aws_region_entry.get(), tws_auto_start_var.get(), username_entry.get(), password_entry.get())).grid(row=99, column=0, pady=10, padx=5)
    Button(tab_frame, text="Exit", command=lambda: exit_settings(tab_control)).grid(row=99, column=1, pady=10, padx=5)

def toggle_supabase_settings(check_var, url_entry, key_entry):
    if check_var.get() == 1:
        url_entry.config(state='normal')
        key_entry.config(state='normal')
    else:
        url_entry.config(state='disabled')
        key_entry.config(state='disabled')

def copy_sql_to_clipboard():
    # SQL code for creating the account table
    # Add your SQL code here
    sql_code = "YOUR SQL CODE"
    pyperclip.copy(sql_code)
    messagebox.showinfo("SQL Copied", "SQL code has been copied to clipboard.")

def toggle_tws_auto_start(check_var, username_entry, password_entry):
    if check_var.get() == 1:
        username_entry.config(state='normal')
        password_entry.config(state='normal')
    else:
        username_entry.config(state='disabled')
        password_entry.config(state='disabled')


def toggle_tws_auto_start(check_var, username_entry, password_entry):
    if check_var.get() == 1:
        username_entry.config(state='normal')
        password_entry.config(state='normal')
    else:
        username_entry.config(state='disabled')
        password_entry.config(state='disabled')

def save_general_settings(port, db_local, db_s3, aws_access_id, aws_access_key, aws_bucket_name, aws_region, tws_auto_start, username, password):
    global changes_made

    # Add your validation logic here
    if db_local and db_s3:
        messagebox.showerror("Error","Please select only one Database Management Method")
        return
    # Example: Check if required fields are filled
    if db_s3 and not (aws_access_id and aws_access_key and aws_bucket_name and aws_region):
        messagebox.showerror("Error", "Please fill all AWS S3 credentials.")
        return
    if tws_auto_start and not (username and password):
        messagebox.showerror("Error","Username and/or Password missing")

    # Proceed with saving settings
    # Save settings logic here

    # Reset changes_made only if save is successful
    changes_made = False
    # messagebox.showinfo("Success", "Settings saved successfully.")


def exit_settings(settings_window):
    global changes_made
    if changes_made:
        if messagebox.askyesno("Close Settings", "Do you want to exit without saving your changes?"):
            settings_window.master.destroy()
    else:
        settings_window.master.destroy()


def populate_strategies_tab(tab_frame):
    # Code to populate the Strategies tab
    pass

# Additional functions like save_general_settings, save_strategy_settings etc.
