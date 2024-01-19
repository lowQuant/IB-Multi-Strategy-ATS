import tkinter as tk
from tkinter import ttk
from data_and_research import ac, fetch_strategies

def on_combobox_select(event, tree, row_id):
    strategy = event.widget.get()
    print("select fct called")
    symbol = tree.set(row_id, 'symbol')
    row = tree.set(row_id)
    print(row)
    print(strategy,symbol)

def build_strategy_combobox(window, tree, strategies, row_id):
    # Column index for the strategy column
    strategy_column_index = "#5"
    
    # Check if the bounding box can be retrieved, otherwise return
    bbox = tree.bbox(row_id, strategy_column_index)
    if not bbox:
        print(f"Could not get bbox for row: {row_id}")
        return None
    
    x, y, width, height = bbox
    pady = height // 2

    # Create a Combobox widget with the list of strategies
    strategy_cb = ttk.Combobox(window, values=strategies)
    strategy_cb.place(x=x, y=y+pady, anchor="w", width=width)
    strategy_cb.set("")  # Placeholder text

    # Bind the Combobox to the assign_strategy function when a selection is made
    strategy_cb.bind("<<ComboboxSelected>>", lambda e: on_combobox_select(e, tree, row_id))
    return strategy_cb  # Return the combobox to manage it later if needed

def open_portfolio_window(ib):
    window = tk.Toplevel()
    window.title("Portfolio")
    window.geometry("600x400")

    portfolio_data = get_portfolio_data(ib)  # Fetch the data
    strategies, strat_df = fetch_strategies()  # Fetch list of strategies

    # Add a scrollbar
    scrollbar = tk.Scrollbar(window)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    # Create the treeview
    columns = ("symbol", "class", "position", "% of NAV", "strategy")
    tree = ttk.Treeview(window, columns=columns, show='headings', yscrollcommand=scrollbar.set)
    tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    # Define the column headings
    for col in columns:
        tree.column(col, stretch=tk.YES, minwidth=0, width=100)  # Adjust the width as needed
        tree.heading(col, text=col.capitalize())

    # Adding data to the treeview
    for item in portfolio_data:
        #!  TODO: WRITE A FUNCTION: match_position_with_db
        # in this function it will check the db for an entry in the symbol and asset class
        # if no entry we can proceed as below. if one entry do item.position - entry.position and display the result in a row
        # display the residual in the next row - user has to select a strategy for that
        # also calculate avg px etc.

        percent_nav = calculate_percent_nav(item, portfolio_data)  # Calculate % of NAV
        row_id = tree.insert("", tk.END, values=(item["symbol"], item["class"], item["position"], f"{percent_nav:.2f}", ""))
        
    # After adding all items to the treeview
    window.update_idletasks()  # Update the GUI to ensure treeview is drawn

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
                strategy_cb.bind("<<ComboboxSelected>>", lambda e: on_combobox_select(e, tree, row_id))

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
