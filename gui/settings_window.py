from tkinter import Toplevel, ttk, Frame, Label, Text, Entry, Button, Checkbutton, IntVar, messagebox, StringVar
from arcticdb import Arctic
import pandas as pd
from data_and_research import ac, fetch_strategies, fetch_strategy_params, update_params_in_db, get_strategy_allocation_bounds, update_weights

changes_made = False
overview_tab = None
details_tab = None

def get_settings_from_db():
    lib = ac.get_library("general")
    df = lib.read("settings").data
    settings_dict = df.to_dict()
    
    return settings_dict['Value']

def open_settings_window(main_window):
    
    settings_window = Toplevel(main_window)
    settings_window.title("Settings")
    settings_window.geometry("520x585")

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
    if db_s3:
        if not test_aws_s3_connection(aws_access_id, aws_access_key, aws_bucket_name, aws_region):
            messagebox.showerror("Error", "Test connection failed. Double check your S3 connection credentials.")
            return  # Stop the function if S3 connection test fails
    
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
        lib = ac.get_library("general")
        lib.write("settings", settings_df, metadata={'source': 'gui'})
        messagebox.showinfo("Success", "Settings saved successfully. Restart Application to make changes effective.")
        changes_made = False
    except Exception as e:
        messagebox.showerror("Error", f"Failed to save settings: {e}")
    # Reset changes_made only if save is successful
    changes_made = False

# Error Handling functions for func 'save_general_settings'
def test_aws_s3_connection(aws_access_id, aws_access_key, bucket_name, region):
    try:
        test_connection =Arctic(f's3://s3.{region}.amazonaws.com:{bucket_name}?region={region}&access={aws_access_id}&secret={aws_access_key}')
        connection_worked = None
        try:
            test_connection.create_library('test_connection')
            test_connection.delete_library('test_connection')
            connection_worked = True
        except:
            connection_worked = False
        return connection_worked
    except Exception as e:
        messagebox.showerror("Connection Error", f"Failed to connect to AWS S3: {e}")
        return False

def exit_settings(settings_window):
    global changes_made
    if changes_made:
        if messagebox.askyesno("Close Settings", "Do you want to exit without saving your changes?"):
            settings_window.master.destroy()
    else:
        settings_window.master.destroy()

def populate_strategies_tab(tab_frame, tab_control):
    global overview_tab
    global details_tab
    sub_tab_control = ttk.Notebook(tab_frame)
    overview_tab = Frame(sub_tab_control)
    details_tab = Frame(sub_tab_control)

    sub_tab_control.add(overview_tab, text='Strategy Overview')
    sub_tab_control.add(details_tab, text='Strategy Details')

    sub_tab_control.pack(expand=1, fill="both")
    
    populate_overview_tab(overview_tab, details_tab)
    populate_details_tab(details_tab)

# Function to update the overview tab
def update_overview_tab(tab_frame):
    for widget in tab_frame.winfo_children():
        widget.destroy()
    populate_overview_tab(tab_frame, tab_frame.master)

def update_details_tab(details_tab):
    for widget in details_tab.winfo_children():
        widget.destroy()
    populate_details_tab(details_tab)

def populate_overview_tab(tab_frame, details_tab):
    strategies, df = fetch_strategies()  # Assuming this returns a list of strategy names and a DataFrame
    active_vars = {}

    if strategies:
        # Display the existing strategies in a table format
        Label(tab_frame, text="Symbol", font=("bold")).grid(row=0, column=0, padx=5, pady=5)
        Label(tab_frame, text="Name", font=("bold")).grid(row=0, column=1, padx=5, pady=5)
        Label(tab_frame, text="Filename", font=("bold")).grid(row=0, column=2, padx=5, pady=5)
        Label(tab_frame, text="Target Weight", font=("bold")).grid(row=0, column=3, padx=5, pady=5)
        Label(tab_frame, text="active", font=("bold")).grid(row=0, column=4, padx=5, pady=5)

        for index, strategy in enumerate(strategies):
            Label(tab_frame, text=strategy).grid(row=index + 1, column=0, padx=5, pady=5)
            Label(tab_frame, text=df.loc[strategy, 'name']).grid(row=index + 1, column=1, padx=5, pady=5)
            Label(tab_frame, text=df.loc[strategy, 'filename']).grid(row=index + 1, column=2, padx=5, pady=5)
            Label(tab_frame, text=df.loc[strategy, 'target_weight']).grid(row=index + 1, column=3, padx=5, pady=5)
            active_state = df.loc[strategy, 'active'] == "True"
            active_var = IntVar(value=int(active_state))
            active_vars[strategy] = active_var
            Checkbutton(tab_frame, variable=active_var, command=lambda s=strategy, v=active_var: update_active_state(s, v)).grid(row=index + 1, column=4, padx=5, pady=5)
        
        Button(tab_frame, text="Add another Strategy", command=lambda: add_strategy_window(tab_frame,details_tab)).grid(row=98, column=0, columnspan=3, pady=10, padx=10)
    else:
        Label(tab_frame, text="""
              No Strategies found in the database. 
              Please add a new Strategy.""").grid(row=1, column=0, rowspan=2, columnspan=3, sticky='w', padx=0, pady=5)
        # Add Strategy Button
        Button(tab_frame, text="Add a Strategy", command=lambda: add_strategy_window(tab_frame,details_tab)).grid(row=98, column=0, columnspan=3, pady=10, padx=10)

    def update_active_state(strategy_symbol, active_var):
        new_state = bool(active_var.get())
        lib = ac.get_library('general')
        strat_df = lib.read("strategies").data
        strat_df.loc[strategy_symbol, "active"] = str(new_state)
        lib.write("strategies", strat_df, metadata={'source': 'gui update'})
        print(f"Updated 'active' state for {strategy_symbol} to {new_state}")

def add_strategy_window(tab_frame,details_tab):
    new_window = Toplevel()
    new_window.title("Add Strategy")
    new_window.geometry("360x400")
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
    # min_weight_entry.insert(0,weight_entry.get()*0.8)

    # Max Weight
    Label(new_window, text="Maximum Weight:").grid(row=6, column=0, padx=5, pady=5)
    max_weight_entry = Entry(new_window)
    max_weight_entry.grid(row=6, column=1, padx=5, pady=5)
    # max_weight_entry.insert(0,weight_entry.get()*1.2)

    # Filename
    Label(new_window, text="Filename:").grid(row=7, column=0, padx=10, pady=5)
    file_entry = Entry(new_window)
    file_entry.grid(row=7, column=1, padx=5, pady=5)
    Label(new_window, text='''Save your ".py" file in "/strategy_manager/strategies/".''').grid(row=8, column=0, columnspan=2, padx=5, pady=5)

    # Function to save the strategy details and close the window
    def save_and_exit():
        # Saving Strategy Details
        strategy_symbol = symbol_entry.get()
        strategies, _ = fetch_strategies()

        if strategy_symbol in strategies:
            messagebox.showerror("Error", f"Strategy Symbol already exists. Choose a different.")
        else:
            # Creating a dictionary of strategy details
            details_dict = {
                "name": name_entry.get(),
                "filename": file_entry.get(),
                "description": description_text.get('1.0', 'end-1c'),
                "target_weight": weight_entry.get(),
                'min_weight': min_weight_entry.get(),
                'max_weight': max_weight_entry.get(),
                'params': "",
                'active': str(True)
            }

            # Convert dictionary to DataFrame
            details_df = pd.DataFrame([details_dict], index=[symbol_entry.get()])
            # details_df = pd.DataFrame.from_dict(details_dict, orient='index', columns=['Value'])

            # Write settings to Arctic
            try:
                lib = ac.get_library('general', create_if_missing=True)
                lib.append(f"strategies", details_df)#, metadata={'source': 'gui'})
                messagebox.showinfo("Success", f"{name_entry.get()} saved successfully.")
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save settings: {e}")

            # ...
            update_overview_tab(tab_frame)  # Refresh the overview tab after saving
            update_details_tab(details_tab)
            new_window.destroy()

    # Exit Button
    Button(new_window, text="Save & Exit", command=save_and_exit).grid(row=98, column=0, padx=5, pady=5)
    Button(new_window, text="Cancel", command=new_window.destroy).grid(row=98, column=1, padx=5, pady=5)
    
def populate_details_tab(tab_frame):
    strategies, _ = fetch_strategies()
    selected_strategy = StringVar()
    entry_widgets = {}  # Dictionary to hold the Entry widgets
    weight_widgets = {}  # Dictionary to hold weight Entry widgets

    Label(tab_frame, text='''Select a Strategy to see Strategy Parameters''').grid(row=0, column=0, columnspan=2, padx=5, pady=5)
    strategy_dropdown = ttk.Combobox(tab_frame, textvariable=selected_strategy, values=strategies)
    strategy_dropdown.grid(row=1, column=0, padx=10, pady=5)

    strategy_details_frame = Frame(tab_frame)
    strategy_details_frame.grid(row=3, column=0, padx=5, pady=5)

    def on_strategy_select(event):
        # Clear previous details
        for widget in strategy_details_frame.winfo_children():
            widget.destroy()
        entry_widgets.clear()  # Reset the dictionary here
        weight_widgets.clear() 

        strategy_symbol = selected_strategy.get()
        if strategy_symbol:
            # display weights
            tw, min_w, max_w = get_strategy_allocation_bounds(strategy_symbol)
            Label(strategy_details_frame, text="target_weight").grid(row=1, column=0, padx=5, pady=5)
            target_weight_entry = Entry(strategy_details_frame)
            target_weight_entry.insert(0, str(tw))
            target_weight_entry.grid(row=1, column=1, padx=5, pady=5)
            weight_widgets['target_weight'] = target_weight_entry

            Label(strategy_details_frame, text="min_weight").grid(row=2, column=0, padx=5, pady=5)
            min_weight_entry = Entry(strategy_details_frame)
            min_weight_entry.insert(0, str(min_w))
            min_weight_entry.grid(row=2, column=1, padx=5, pady=5)
            weight_widgets['min_weight'] = min_weight_entry

            Label(strategy_details_frame, text="max_weight").grid(row=3, column=0, padx=5, pady=5)
            max_weight_entry = Entry(strategy_details_frame)
            max_weight_entry.insert(0, str(max_w))
            max_weight_entry.grid(row=3, column=1, padx=5, pady=5)
            weight_widgets['max_weight'] = max_weight_entry

            # Fetch and display strategy details
            parameters = fetch_strategy_params(strategy_symbol)
            if parameters and type(parameters) != str:
                row = 4
                for i, (param, value) in enumerate(parameters.items()):
                    Label(strategy_details_frame, text=param).grid(row=row, column=0, padx=5, pady=5)
                    entry = Entry(strategy_details_frame)
                    entry.insert(0, str(value))
                    entry.grid(row=row, column=1, padx=5, pady=5)
                    entry_widgets[param] = entry  # Store the Entry widget

                    row += 1
                
                # Button for saving changes
                Button(strategy_details_frame, text="Save Changes", command=lambda: save_changes(strategy_symbol)).grid(row=99, column=0, padx=5, pady=5)
                Button(strategy_details_frame, text="Delete Strategy", command=lambda: delete_strat(strategy_symbol)).grid(row=99, column=1, padx=5, pady=5)

            elif type(parameters) == str:
                Label(strategy_details_frame, text=parameters, wraplength=380).grid(row=4, rowspan=3, columnspan=2 ,column=0, padx=5, pady=5)
                Button(strategy_details_frame, text="Delete Strategy", command=lambda: delete_strat(strategy_symbol)).grid(row=99, column=0, padx=5, pady=5)
            else:
                Label(strategy_details_frame, text="Please add a global PARAMS variable of type <dict> to your strategy.py file", wraplength=380).grid(row=4, rowspan=3, column=0,columnspan=2, padx=5, pady=5)
                Button(strategy_details_frame, text="Delete Strategy", command=lambda: delete_strat(strategy_symbol)).grid(row=99, column=0, padx=5, pady=5)

    def save_changes(strategy_symbol):
        # Update weights
        target_weight_value = weight_widgets['target_weight'].get()
        min_weight_value = weight_widgets['min_weight'].get()
        max_weight_value = weight_widgets['max_weight'].get()
        update_weights(strategy_symbol,target_weight_value,min_weight_value, max_weight_value)

        # Retrieve values directly from Entry widgets and save changes
        updated_parameters = {param: entry.get() for param, entry in entry_widgets.items()}
        update_params_in_db(strategy_symbol,updated_parameters)
  
    def delete_strat(strategy_symbol):
        # Ask for confirmation before deletion
        response = messagebox.askyesno("WARNING", f"Are you sure you want to delete the strategy '{strategy_symbol}'?")
        if response:
            try:
                # Proceed with deletion
                lib = ac.get_library('general')
                strat_df = lib.read("strategies").data

                # Check if the strategy exists in the DataFrame
                if strategy_symbol in strat_df.index:
                    # Delete the strategy
                    strat_df = strat_df.drop(strategy_symbol)
                    lib.write("strategies", strat_df, metadata={'source': 'gui delete'})
                    messagebox.showinfo("Success", f"Strategy '{strategy_symbol}' has been successfully deleted.")

                    # Update the Strategy tabs
                    update_overview_tab(tab_frame)  # Refresh the overview tab after saving
                    update_details_tab(details_tab)
                else:
                    messagebox.showerror("Error", f"Strategy '{strategy_symbol}' not found in the database.")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete strategy: {e}")
        else:
            print(f"Deletion cancelled for {strategy_symbol}")

    strategy_dropdown.bind("<<ComboboxSelected>>", on_strategy_select)
