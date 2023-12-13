from tkinter import Toplevel, ttk, Frame, Label, Text, Entry, Button, Checkbutton, IntVar, messagebox, Toplevel, StringVar
import pyperclip
import pandas as pd
from data_and_research import ac, fetch_strategies, fetch_strategy_params

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
    populate_strategies_tab(strategies_tab, tab_control)

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
    # Creating a dictionary of settings
    settings_dict = {
        "ib_port": port,
        "s3_db_management": "True" if db_s3 else "False",
        "aws_access_id": aws_access_id,
        "aws_access_key": aws_access_key,
        "bucket_name": aws_bucket_name,
        "region": aws_region,
        "start_tws": "true" if tws_auto_start else "false",
        "username": username,
        "password": password
    }

    # Convert dictionary to DataFrame
    settings_df = pd.DataFrame.from_dict(settings_dict, orient='index', columns=['Value'])

    # Write settings to Arctic
    try:
        lib = ac.get_library("settings")
        lib.write("settings", settings_df, metadata={'source': 'gui'})
        messagebox.showinfo("Success", "Settings saved successfully.")
        changes_made = False
    except Exception as e:
        messagebox.showerror("Error", f"Failed to save settings: {e}")
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

def populate_strategies_tab(tab_frame, tab_control):
    sub_tab_control = ttk.Notebook(tab_frame)
    overview_tab = Frame(sub_tab_control)
    details_tab = Frame(sub_tab_control)

    sub_tab_control.add(overview_tab, text='Strategy Overview')
    sub_tab_control.add(details_tab, text='Strategy Details')

    sub_tab_control.pack(expand=1, fill="both")

    populate_overview_tab(overview_tab, tab_control)
    populate_details_tab(details_tab)

def populate_overview_tab(tab_frame, tab_control):
    strategies, df = fetch_strategies()  # Assuming this returns a list of strategy names and a DataFrame

    if strategies:
        # Display the existing strategies in a table format
        Label(tab_frame, text="Symbol", font=("bold")).grid(row=0, column=0, padx=5, pady=5)
        Label(tab_frame, text="Name", font=("bold")).grid(row=0, column=1, padx=5, pady=5)
        Label(tab_frame, text="Target Weight", font=("bold")).grid(row=0, column=2, padx=5, pady=5)

        for index, strategy in enumerate(strategies):
            Label(tab_frame, text=strategy).grid(row=index + 1, column=0, padx=5, pady=5)
            Label(tab_frame, text=df.loc[strategy, 'name']).grid(row=index + 1, column=1, padx=5, pady=5)
            Label(tab_frame, text=df.loc[strategy, 'target_weight']).grid(row=index + 1, column=2, padx=5, pady=5)
    else:
        Label(tab_frame, text="No Strategies found in the database. Please add a new Strategy.").grid(row=1, column=0, columnspan=3, sticky='w', padx=10, pady=5)

    Button(tab_frame, text="Add a Strategy", command=lambda: add_strategy_window(tab_frame, tab_control)).grid(row=98, column=0, columnspan=3, pady=10, padx=10)

def add_strategy_window(tab_frame, tab_control):
    new_window = Toplevel()
    new_window.title("Add Strategy")
    new_window.geometry("380x360")
    new_window.transient(tab_frame)  # Set the new window to be a child of tab_frame
    new_window.grab_set()  # Set the new window to be modal

    # Strategy Name
    Label(new_window, text="Strategy Name:").grid(row=0, column=0, padx=5, pady=5)
    name_entry = Entry(new_window)
    name_entry.grid(row=0, column=1, padx=5, pady=5)

    # Strategy Symbol
    Label(new_window, text="Strategy Symbol:").grid(row=1, column=0, padx=5, pady=5)
    symbol_entry = Entry(new_window)
    symbol_entry.grid(row=1, column=1, padx=5, pady=5)

    # Description
    Label(new_window, text="Description:").grid(row=2, column=0, padx=5, pady=5)
    description_text = Text(new_window, height=3, width=42)
    description_text.grid(row=3, column=0,columnspan=2, padx=10, pady=5)

    # Target Weight
    Label(new_window, text="Target Weight:").grid(row=4, column=0, padx=5, pady=5)
    weight_entry = Entry(new_window)
    weight_entry.grid(row=4, column=1, padx=5, pady=5)

    # Min Weight
    Label(new_window, text="Minimun Weight:").grid(row=5, column=0, padx=5, pady=5)
    min_weight_entry = Entry(new_window)
    min_weight_entry.grid(row=5, column=1, padx=5, pady=5)
    # min_weight_entry.insert(0,int(weight_entry.get())*0.8)

    # Max Weight
    Label(new_window, text="Maximum Weight:").grid(row=6, column=0, padx=5, pady=5)
    max_weight_entry = Entry(new_window)
    max_weight_entry.grid(row=6, column=1, padx=5, pady=5)
    # max_weight_entry.insert(0,int(weight_entry.get())*1.2)

    # Filename
    Label(new_window, text="Filename:").grid(row=7, column=0, padx=10, pady=5)
    file_entry = Entry(new_window)
    file_entry.grid(row=7, column=1, padx=5, pady=5)
    Label(new_window, text='''Save your ".py" file in "/strategy_manager/strategies/".''').grid(row=8, column=0, columnspan=2, padx=5, pady=5)

    # Function to save the strategy details and close the window
    def save_and_exit():
        # Saving Strategy Details
    # Creating a dictionary of strategy details
        details_dict = {
            "name": [name_entry.get()],
            "filename": [file_entry.get()],
            "description": [description_text.get('1.0', 'end-1c')],
            "target_weight": [weight_entry.get()],
            'min_weight': [min_weight_entry.get()],
            'max_weight': [max_weight_entry.get()],
            'params': [""]
        }

        # Convert dictionary to DataFrame
        details_df = pd.DataFrame.from_dict(details_dict)
        details_df.index = [symbol_entry.get()]  # Set symbol as the index

        # Write settings to Arctic
        try:
            lib = ac.get_library('strategies', create_if_missing=True)
            lib.write(f"strategies", details_df, metadata={'source': 'gui'})
            messagebox.showinfo("Success", f"{name_entry.get()} saved successfully.")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save settings: {e}")

        # ...
        new_window.destroy()

    # Exit Button
    Button(new_window, text="Save & Exit", command=save_and_exit).grid(row=98, column=0, padx=5, pady=5)
    Button(new_window, text="Cancel", command=new_window.destroy).grid(row=98, column=1, padx=5, pady=5)
    

def populate_details_tab(tab_frame):
    strategies, _ = fetch_strategies()

    selected_strategy = StringVar()
    strategy_dropdown = ttk.Combobox(tab_frame, textvariable=selected_strategy, values=strategies)
    strategy_dropdown.grid(row=0, column=0, padx=5, pady=5)

    strategy_details_frame = Frame(tab_frame)
    strategy_details_frame.grid(row=1, column=0, padx=5, pady=5)

    def on_strategy_select(event):
        # Clear previous details
        for widget in strategy_details_frame.winfo_children():
            widget.destroy()

        strategy_name = selected_strategy.get()
        if strategy_name:
            # Fetch and display strategy details
            parameters = fetch_strategy_params(strategy_name)
            for i, (param, value) in enumerate(parameters.items()):
                Label(strategy_details_frame, text=param).grid(row=i, column=0, padx=5, pady=5)
                Entry(strategy_details_frame, textvariable=StringVar(value=str(value))).grid(row=i, column=1, padx=5, pady=5)

    strategy_dropdown.bind("<<ComboboxSelected>>", on_strategy_select)