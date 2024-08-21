import tkinter as tk
from tkinter import ttk, messagebox

class DatabaseWindow:
    def __init__(self, master, data_manager):
        self.master = master
        self.data_manager = data_manager
        self.arctic = data_manager.arctic
        self.init_window()

    def init_window(self):
        self.master.title(f"{'Database Manager'}")
        self.master.geometry("800x600")

        # Create tabs
        self.tab_control = ttk.Notebook(self.master)

        # Data view tab
        self.data_tab = ttk.Frame(self.tab_control)
        self.tab_control.add(self.data_tab, text='Data View')
        self.setup_data_tab()

        # Task scheduler tab
        self.task_tab = ttk.Frame(self.tab_control)
        self.tab_control.add(self.task_tab, text='Task Scheduler')
        self.setup_task_tab()

        self.tab_control.pack(expand=1, fill="both")

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

    # SETUP TAB
    def setup_task_tab(self):
        # Example label
        label = ttk.Label(self.task_tab, text="Task Scheduler Area")
        label.pack(pady=10)

        # Example scheduler setup
        schedule_button = ttk.Button(self.task_tab, text="Schedule Task", command=self.schedule_task)
        schedule_button.pack()

    def schedule_task(self):
        # This function could schedule data-related tasks
        messagebox.showinfo("Information", "Task scheduled successfully!")

def open_database_window(data_manager):
    root = tk.Tk()
    app = DatabaseWindow(root, data_manager)
    root.mainloop()
