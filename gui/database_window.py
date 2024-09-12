import platform, subprocess, os, re
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

class DatabaseWindow:
    def __init__(self, master, data_manager):
        self.master = master
        self.data_manager = data_manager
        self.arctic = data_manager.arctic
    
        # Detect and store the operating system
        self.operating_system = self.detect_operating_system()
        print(f"Operating System Detected: {self.operating_system}")

        self.init_window()

    def detect_operating_system(self):
        """Detect and return the current operating system."""
        os_name = platform.system()
        if os_name == 'Windows':
            return 'Windows'
        elif os_name == 'Linux':
            return 'Linux'
        elif os_name == 'Darwin':  # macOS
            return 'macOS'
        else:
            return 'Unknown OS'
        
    def init_window(self):
        self.master.title(f"{'Database Manager'}")
        self.master.geometry("1000x600")

        # Create tabs
        self.notebook = ttk.Notebook(self.master)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Data view tab
        self.data_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.data_tab, text='Data View')
        self.setup_data_tab()

        # Task scheduler tab
        self.task_tab = ttk.Frame(self.notebook)  # Initialize the frame for the Task Scheduler tab
        self.notebook.add(self.task_tab, text='Task Scheduler')
        self.setup_task_scheduler_tab()

        self.notebook.pack(expand=1, fill="both")

    def setup_data_tab(self):
        connection_info = f"Connected to {str(self.data_manager.arctic).split('endpoint=')[1].split(',')[0]}" \
                         if "endpoint=" in str(self.data_manager.arctic) else "Connected locally"
        connection_label = ttk.Label(self.data_tab, text=connection_info)
        connection_label.pack(side=tk.TOP, pady=10)

        # Control frame to hold comboboxes and button
        control_frame = ttk.Frame(self.data_tab)
        control_frame.pack(fill=tk.X, pady=5)

        # Library selection
        self.library_var = tk.StringVar()
        libraries = self.data_manager.arctic.list_libraries()
        self.library_combo = ttk.Combobox(control_frame, textvariable=self.library_var,
                                          values=libraries, width=20)
        self.library_combo.pack(side=tk.LEFT, padx=10, pady=5)
        self.library_combo.bind("<<ComboboxSelected>>", self.update_symbol_options)

        # Symbol selection
        self.symbol_var = tk.StringVar()
        self.symbol_combo = ttk.Combobox(control_frame, textvariable=self.symbol_var, width=20)
        self.symbol_combo.pack(side=tk.LEFT, padx=10, pady=5)

        # Load Data button
        load_button = ttk.Button(control_frame, text="Load Data", command=self.load_data)
        load_button.pack(side=tk.LEFT, padx=10, pady=5)

        # Add Delete Table button
        delete_button = ttk.Button(control_frame, text="Delete Table", command=self.delete_table)
        delete_button.pack(side=tk.LEFT, padx=10, pady=5)

        # Add View in PandasGUI button
        view_pandasgui_button = ttk.Button(control_frame, text="View in PandasGUI", command=self.view_in_pandasgui)
        view_pandasgui_button.pack(side=tk.LEFT, padx=10, pady=5)

        # Treeview frame for scrollbar management
        tree_frame = ttk.Frame(self.data_tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Treeview for data display
        self.tree = ttk.Treeview(tree_frame, show='headings')
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)  # Set `expand=True` for scrollbar

        vert_scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        vert_scroll.pack(side='right', fill='y')  # Use `fill=tk.Y` for vertical scrollbar
        self.tree.configure(yscrollcommand=vert_scroll.set)

        horiz_scroll = ttk.Scrollbar(self.data_tab, orient="horizontal", command=self.tree.xview)
        horiz_scroll.pack(side='bottom', fill='x')  # Pack horizontal scrollbar
        self.tree.configure(xscrollcommand=horiz_scroll.set)

    def load_data(self):
        library_name = self.library_combo.get()
        symbol = self.symbol_combo.get()
        if not library_name or not symbol:
            messagebox.showinfo("Information", "Please select a library and a symbol first.")
            return

        # Fetch data from DataManager
        self.data_df = self.data_manager.get_data_from_arctic(library_name, symbol)
        data_df = self.data_df
        if data_df is None or data_df.empty:
            messagebox.showinfo("Information", "No data available for the selected symbol.")
            return

        # Include DataFrame index as the first column in the Treeview
        data_df.reset_index(inplace=True)  # Resets the index and makes it a column
        data_df.columns = ['Index'] + list(data_df.columns[1:])  # Rename the first column to 'Index'

        # Update the treeview to accommodate the dataframe columns dynamically
        self.tree['columns'] = data_df.columns.tolist()
        for col in self.tree['columns']:
            self.tree.heading(col, text=col, command=lambda _col=col: self.treeview_sort_column(_col, False))
            self.tree.column(col, minwidth=50, width=80, stretch=False, anchor=tk.CENTER)  # Set a default width

        # Clear existing entries in the tree
        for i in self.tree.get_children():
            self.tree.delete(i)

        # Populate the tree with new data
        for row in data_df.itertuples(index=False, name=None):
            self.tree.insert('', 'end', values=row)
    
    def treeview_sort_column(self, col, reverse):
        """ Sort treeview contents when a column header is clicked. """
        l = [(self.tree.set(k, col), k) for k in self.tree.get_children('')]
        l.sort(reverse=reverse)

        # rearrange items in sorted positions
        for index, (val, k) in enumerate(l):
            self.tree.move(k, '', index)

        # reverse sort next time
        self.tree.heading(col, command=lambda: self.treeview_sort_column(col, not reverse))

    def update_symbol_options(self, event=None):
        print("in update_symbol_options func")
        selected_library = self.library_combo.get()
        print(f"Selected Library: {selected_library}")  # Debug prin
        try:
            # Safely attempt to access the library and list symbols
            symbols = self.arctic.get_library(selected_library).list_symbols()
            print(symbols)
            self.symbol_combo['values'] = symbols
            if symbols:
                self.symbol_combo.set(symbols[0])
        except Exception as e:
            messagebox.showerror("Error", f"Failed to fetch symbols: {e}")

    def delete_table(self):
        library_name = self.library_combo.get()
        symbol = self.symbol_combo.get()
        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete {symbol} from {library_name}?"):
            self.arctic.get_library(library_name).delete(symbol)
            messagebox.showinfo("Information", f"{symbol} deleted from {library_name}.")
            self.update_symbol_options()  # Refresh symbols after deletion

    def view_in_pandasgui(self):
        from pandasgui import show
        library_name = self.library_combo.get()
        symbol = self.symbol_combo.get()
        
        try:
            if self.data_df is not None and not self.data_df.empty:
                show(self.data_df)
            else:
                messagebox.showinfo("Information", "No data available to display in PandasGUI.")
        except:
            self.data_df = self.data_manager.get_data_from_arctic(library_name, symbol)
            show(self.data_df)

    # SETUP TASK TAB
    def setup_task_scheduler_tab(self):
        """Set up the Task Scheduler tab."""

        # Ensure self.task_scheduler_frame is initialized
        self.task_scheduler_frame = ttk.Frame(self.task_tab)
        self.task_scheduler_frame.pack(fill=tk.BOTH, expand=True)  # Ensure the frame is packed

        # Create a paned window for vertical split
        paned_window = ttk.PanedWindow(self.task_scheduler_frame, orient=tk.HORIZONTAL)
        paned_window.pack(fill=tk.BOTH, expand=True)

        # Left frame (Scheduled Tasks)
        left_frame = ttk.Frame(paned_window, width=500)
        paned_window.add(left_frame, weight=3)
        self.setup_left_panel(left_frame)

        # Right frame (Task Creation)
        self.right_frame = ttk.Frame(paned_window, width=300)
        paned_window.add(self.right_frame, weight=1)
        self.setup_right_panel(self.right_frame)
        
    def setup_left_panel(self, parent):
        """Setup the left panel in the Task Scheduler tab."""
        header_label = ttk.Label(parent, text="Scheduled Tasks", font=("Arial", 16))
        header_label.pack(pady=10)

       # Create a frame to hold the Listbox and the Scrollbar
        listbox_frame = tk.Frame(parent)
        listbox_frame.pack(pady=10, fill=tk.BOTH, expand=True)

        # Listbox to display scheduled tasks (initially empty)
        self.task_listbox = tk.Listbox(listbox_frame, height=20, width=40)
        self.task_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Scrollbar for the Listbox
        task_scrollbar = tk.Scrollbar(listbox_frame)
        task_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Link the Scrollbar and the Listbox
        self.task_listbox.config(yscrollcommand=task_scrollbar.set)
        task_scrollbar.config(command=self.task_listbox.yview)

        # Populate the Listbox with tasks
        self.refresh_task_list()
        

    def setup_right_panel(self, parent):
        """Setup the right panel in the Task Scheduler tab."""
        label = ttk.Label(parent, text="Add New Task", font=("Arial", 16))
        label.pack(pady=10)

        # Label to display the selected file path in abbreviated form
        self.file_display_var = tk.StringVar()
        file_display_label = ttk.Label(parent, textvariable=self.file_display_var, width=50, anchor="center")
        file_display_label.pack(pady=5)

        # Button to open file dialog
        select_file_button = ttk.Button(parent, text="Select Python File", command=self.open_file_dialog)
        select_file_button.pack(pady=5)

        # Input field for the time (e.g., 14:00 for 2:00 PM)
        time_label = ttk.Label(parent, text="Time (HH:MM):")
        time_label.pack(pady=5)
        self.time_var = tk.StringVar()
        self.time_entry = ttk.Entry(parent, textvariable=self.time_var, width=10)
        self.time_entry.pack(pady=5)

        # Dropdown for frequency (daily, weekly, etc.)
        frequency_label = ttk.Label(parent, text="Frequency:")
        frequency_label.pack(pady=5)
        self.frequency_var = tk.StringVar(value="Daily")
        frequency_combo = ttk.Combobox(parent, textvariable=self.frequency_var, 
                                    values=["Daily", "Weekly", "Monthly"])
        frequency_combo.pack(pady=5)

        # Button to schedule the task
        schedule_button = ttk.Button(parent, text="Schedule Task", command=self.schedule_task)
        schedule_button.pack(pady=5)

        self.hint_label = ttk.Label(parent,text="Select a Python File to schedule a new task.")
        self.hint_label.pack(pady=100)

    def open_file_dialog(self):
        """Open a file dialog for the user to select a Python file."""
        file_path = filedialog.askopenfilename(
            title="Select Python File",
            filetypes=[("Python Files", "*.py"), ("All Files", "*.*")]
        )
        if file_path:
            # Abbreviate the file path and display it
            abbreviated_path = self.abbreviate_path(file_path)
            self.file_display_var.set(abbreviated_path)
            self.file_path = file_path  # Store the full path for later use
            print(f"Selected file: {file_path}")
            self.hint_label.config(text=f"Selected file: {abbreviated_path}")
            self.master.update_idletasks()

    def abbreviate_path(self, path, max_length=40):
        """Abbreviate a file path to fit within a specified max length."""
        if len(path) <= max_length:
            return path
        head, tail = os.path.split(path)
        if len(tail) > max_length - 5:  # Leave room for "..."
            return f".../{tail}"
        return f"{head[:max_length//2]}.../{tail}"

    def schedule_task(self):
        """Schedule the selected Python file as a task."""
        # self.time_entry.update_idletasks()  # Force GUI update

        file_path = getattr(self, 'file_path', None)  # Get the stored file path
        time_of_day = self.time_entry.get().strip()
        frequency = self.frequency_var.get()

        if not file_path:
            messagebox.showerror("Error", "Please select a Python file first.")
            return

        # Validate time format (HH:MM)
        if not self.validate_time_format(time_of_day):
            messagebox.showerror("Error", "Please enter a valid time in HH:MM format.")
            return

        if not frequency:
            messagebox.showerror("Error", "Please enter a frequency for the task.")
            return
        
        cron_notation = self.convert_to_cron(time_of_day, frequency)

        file = file_path.split("/")[-1]
        self.data_manager.save_new_job(file,cron_notation,self.operating_system)
        print(f"Successfully saved job for {file}")

        # Update the task list
        self.refresh_task_list()

        # Now, schedule the task based on the operating system
        if self.operating_system == 'Windows':
            self.schedule_task_windows(file_path, time_of_day, frequency)
        elif self.operating_system == 'Linux' or self.operating_system == 'macOS':
            self.schedule_task_unix(file_path, time_of_day, frequency)
        else:
            messagebox.showerror("Error", "Unsupported operating system.")


    def validate_time_format(self, time_str):
        """Validate that the time string is in HH:MM format."""
        time_pattern = re.compile(r'^\d{2}:\d{2}$')
        if not time_pattern.match(time_str):
            return False

        hours, minutes = time_str.split(":")
        if not (0 <= int(hours) < 24 and 0 <= int(minutes) < 60):
            return False

        return True

    def convert_to_cron(self, time_of_day, frequency):
        """Convert time and frequency to cron notation."""
        hour, minute = time_of_day.split(":")
        cron_time = f"{minute} {hour} * * *"  # Default to daily

        if frequency == "Weekly":
            cron_time = f"{minute} {hour} * * 0"  # Sunday
        elif frequency == "Monthly":
            cron_time = f"{minute} {hour} 1 * *"  # 1st of every month
        
        return cron_time

    def schedule_task_windows(self, file_path, time_of_day, frequency):
        """Schedule the task using Windows Task Scheduler."""
        try:
            # Construct the schtasks command
            if frequency == "Daily":
                schedule_type = "DAILY"
            elif frequency == "Weekly":
                schedule_type = "WEEKLY"
            elif frequency == "Monthly":
                schedule_type = "MONTHLY"
            
            # Build the command
            command = f'schtasks /create /tn "Python Script Task" /tr "python {file_path}" /sc {schedule_type} /st {time_of_day}'
            subprocess.run(command, check=True, shell=True)

            # Update the task list and status
            self.update_task_list(f"Task: {file_path} at {time_of_day} ({frequency})")
            self.hint_label.config(f"Task scheduled successfully for {file_path}!")
        except subprocess.CalledProcessError as e:
            messagebox.showerror("Error", f"Failed to schedule task on Windows: {e}")

    def schedule_task_unix(self, file_path, time_of_day, frequency):
        """Schedule the task using cron (for Linux/macOS) with logging."""
        try:
            # Parse the time
            hour, minute = time_of_day.split(":")
            cron_time = f"{minute} {hour} * * *"  # Default to daily

            if frequency == "Weekly":
                cron_time = f"{minute} {hour} * * 0"  # Sunday
            elif frequency == "Monthly":
                cron_time = f"{minute} {hour} 1 * *"  # 1st of every month

            # Derive log file path: same directory, base filename with .txt extension
            base_name = os.path.splitext(file_path)[0]
            log_file = f"{base_name}.txt"

            # Add the cron job with logging
            cron_command = f'(crontab -l; echo "{cron_time} python {file_path} >> {log_file} 2>&1") | crontab -'
            subprocess.run(cron_command, check=True, shell=True)

            self.hint_label.config(text=f"Task scheduled successfully for {file_path}!")
        except subprocess.CalledProcessError as e:
            messagebox.showerror("Error", f"Failed to schedule task on {self.operating_system}: {e}")

    def refresh_task_list(self):
        """Retrieve saved jobs from ArcticDB and update the left pane."""
        jobs_df = self.data_manager.get_saved_jobs()

        # Clear the current task list in the GUI
        self.task_listbox.delete(0, tk.END)

        # Populate the task list with saved jobs
        if jobs_df.empty:
            self.task_listbox.insert(tk.END, "No scheduled tasks")
        else:
            for _, row in jobs_df.iterrows():
                task_description = f"{row['filename']}   {row['cron_notation']}   saved on {row['operating_system']}"
                self.task_listbox.insert(tk.END, task_description)


def open_database_window(data_manager):
    root = tk.Tk()
    app = DatabaseWindow(root, data_manager)
    root.mainloop()