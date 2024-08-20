import tkinter as tk
from tkinter import ttk, messagebox

class DatabaseWindow:
    def __init__(self, master, data_manager):
        self.master = master
        self.data_manager = data_manager
        self.init_window()

    def init_window(self):
        self.master.title(f"{self.data_manager.arctic}")
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
        # Create the treeview for data display
        self.tree = ttk.Treeview(self.data_tab, columns=("One", "Two", "Three"), show='headings')
        self.tree.heading("One", text="Column 1")
        self.tree.heading("Two", text="Column 2")
        self.tree.heading("Three", text="Column 3")
        self.tree.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # Sample data load button
        load_button = ttk.Button(self.data_tab, text="Load Data", command=self.load_data)
        load_button.pack(side=tk.BOTTOM, pady=10)

    def setup_task_tab(self):
        # Example label
        label = ttk.Label(self.task_tab, text="Task Scheduler Area")
        label.pack(pady=10)

        # Example scheduler setup
        schedule_button = ttk.Button(self.task_tab, text="Schedule Task", command=self.schedule_task)
        schedule_button.pack()

    def load_data(self):
        # This function should interact with the DataManager to fetch data
        data = [("1", "Item 1", "Value 1"), ("2", "Item 2", "Value 2"), ("3", "Item 3", "Value 3")]
        for item in data:
            self.tree.insert('', 'end', values=item)
        messagebox.showinfo("Information", "Data loaded successfully!")

    def schedule_task(self):
        # This function could schedule data-related tasks
        messagebox.showinfo("Information", "Task scheduled successfully!")

def open_database_window(data_manager):
    root = tk.Tk()
    app = DatabaseWindow(root, data_manager)
    root.mainloop()
