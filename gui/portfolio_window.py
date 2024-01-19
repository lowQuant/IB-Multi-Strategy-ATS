import tkinter as tk
from tkinter import ttk
from data_and_research import ac, fetch_strategies

def open_portfolio_window(ib):
    window = tk.Toplevel()
    window.title("Portfolio")
    window.geometry("600x400")

    # Assuming get_portfolio_data() fetches data from IB and returns a list of dictionaries
    portfolio_data = get_portfolio_data(ib)
    strategies,strat_df = fetch_strategies()  # Fetch list of strategies

    # Add a scrollbar
    scrollbar = tk.Scrollbar(window)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    # Create the treeview
    columns = ("symbol", "class", "position", "% of NAV", "strategy")
    tree = ttk.Treeview(window, columns=columns, show='headings', yscrollcommand=scrollbar.set)
    tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    # Define the column headings
    for col in columns:
        tree.column(col, stretch=tk.YES, minwidth=0, width=60)  # Enable stretching, set a min width and a proportional initial width
        tree.heading(col, text=col.capitalize())

    # Adding data to the treeview
    for item in portfolio_data:
        percent_nav = calculate_percent_nav(item, portfolio_data)  # Calculate % of NAV
        tree.insert("", tk.END, values=(item["symbol"], item["class"], item["position"], f"{percent_nav:.2f}", " "))

    # Add a strategy dropdown for each row in a separate column
    def on_strategy_cell_click(event):
        # Get the row and column clicked
        region = tree.identify("region", event.x, event.y)
        if region == "cell":
            column = tree.identify_column(event.x)
            row = tree.identify_row(event.y)
            if tree.heading(column, "text").lower() == "strategy":
                # Position the combobox
                x, y, width, height = tree.bbox(row, column)
                pady = height // 2

                # Create a Combobox widget
                strategy_cb = ttk.Combobox(window, values=strategies)
                strategy_cb.place(x=x, y=y+pady, anchor="w", width=width)

                # Set the current strategy if assigned, e.g., from a database
                current_strategy = " "  # Example placeholder
                strategy_cb.set(current_strategy)

                # Bind the selection event
                strategy_cb.bind("<<ComboboxSelected>>", lambda e, i=row: assign_strategy(i, strategy_cb.get()))

    tree.bind("<Button-1>", on_strategy_cell_click)

    scrollbar.config(command=tree.yview)

def get_portfolio_data(ib):
    # This is pseudo data. Replace this function to fetch real data from IB
    return [
        {"symbol": "AAPL", "class": "Stock", "position": 100, "marketValue": 15000},
        {"symbol": "GOOGL", "class": "Stock", "position": 50, "marketValue": 10000},
        {"symbol": "TSLA", "class": "Stock", "position": 150, "marketValue": 12000},
        {"symbol": "VXM22", "class": "Future", "position": -2, "marketValue": -5000},
        {"symbol": "EURUSD", "class": "Forex", "position": 10000, "marketValue": 12000},
    ]

def calculate_percent_nav(item, portfolio_data):
    # Dummy calculation for % of NAV
    total_nav = sum(d['marketValue'] for d in portfolio_data)
    percent_nav = (item['marketValue'] / total_nav) * 100
    return percent_nav

def get_strategies(arctic_lib):
    # Fetch list of strategies from ArcticDB
    pass

def assign_strategy(item_id, strategy, arctic_lib):
    # Function to assign a strategy to a portfolio item and update in ArcticDB
    pass
